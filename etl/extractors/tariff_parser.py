"""
Parser de cuadros tarifarios basado en puntaje de líneas candidatas.

Los cuadros tarifarios de las ~28 distribuidoras argentinas no comparten
estructura: cada una ordena categorías, columnas (abastecimiento, VAD,
total, con/sin subsidio) y unidades a su manera. En lugar de buscar una
sección fija ("TARIFA 3"), el parser:

1. Recorre las líneas del texto (filas de planilla con celdas separadas
   por `` | ``, o líneas de PDF).
2. Considera **candidata a tarifa de compra** cada línea con un cargo en
   ``$/kWh`` (en la línea, propagado desde el encabezado de la columna, o
   en la línea anterior para filas de banda horaria) cuyo contexto (la
   línea y hasta ``CONTEXT_LINES`` anteriores) menciona una categoría no
   residencial de medianas/grandes demandas o general/comercial.
3. Descarta líneas de categorías que no representan a un usuario
   agroindustrial: residencial, tarifa social, subsidios, VAD (sólo
   componente de distribución), peaje, alumbrado público, clubes,
   electrodependientes, valores en $/MWh.
4. Puntúa: grandes demandas / T3 / baja tensión > medianas demandas / T2
   > general/comercial; suma un punto a la banda horaria **"Resto"**
   (05–18 h), la representativa del consumo diurno de un gasificador.
5. Toma la mejor candidata (ante empate, la primera del documento) y
   usa la mediana de sus importes plausibles: en filas con varias
   columnas (subcategorías, con/sin subsidio) la mediana es robusta a la
   columna subsidiada.

La tarifa de inyección (usuario-generador, Ley 27.424) se toma de las
líneas que mencionan energía inyectada / ingresada a la red, excluyendo
las de usuarios residenciales o subsidiados, como mediana de los
importes.

Todas las líneas usadas quedan registradas en el resultado
(``lineas_compra`` / ``lineas_inyeccion``) para auditar el parseo.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass
from typing import Any, Final

# Rango plausible de cargos de energía (ARS/kWh sin impuestos, 2025-2026).
# El mínimo descarta componentes parciales (VAD, peaje, cargos de
# transporte) y números de horario ("05 a 18 hs").
PRICE_MIN: Final[float] = 30.0
PRICE_MAX: Final[float] = 2000.0
CONTEXT_LINES: Final[int] = 15

AR_NUMBER: Final[str] = r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+,\d+|\d+"
EN_NUMBER: Final[str] = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d+|\d+"
KWH_UNIT: Final[re.Pattern[str]] = re.compile(
    r"\$\s*/\s*kwh|\[\s*\$\s*/\s*kwh|\bpor\s+(?:cada\s+)?kwh|\$\s*kwh",
    re.IGNORECASE,
)
OTHER_UNIT: Final[re.Pattern[str]] = re.compile(
    r"\$\s*[/-]\s*(?:mes|bim|kw\s*-?\s*mes|usuario)|\$\s*/\s*mwh|kw-mes",
    re.IGNORECASE,
)
MWH_UNIT: Final[re.Pattern[str]] = re.compile(r"\$\s*/\s*mwh", re.IGNORECASE)
MONTH_UNIT: Final[re.Pattern[str]] = re.compile(
    r"\$\s*[/-]\s*mes\b|\bpor\s+mes\b", re.IGNORECASE
)
BAND: Final[re.Pattern[str]] = re.compile(
    r"\b(?:pico|punta|resto|restantes?|valle)\b|\(\s*[PRV]\s*\)|®", re.IGNORECASE
)
RESTO: Final[re.Pattern[str]] = re.compile(
    r"\bresto\b(?!\s+(?:de|del)\b)|\brestantes?\b|\(\s*R\s*\)|®", re.IGNORECASE
)

CATEGORY_SCORES: Final[list[tuple[re.Pattern[str], int]]] = [
    (re.compile(
        r"grandes?\s+(?:demandas?|consumos?|usuarios?)|\bT\s*-?\s*3\b|"
        r"tarifa\s*n?\s*[º°o]?\s*\.?\s*3\b|\bgudi|baja\s+tensi[oó]n|"
        r">\s*50\s*kw|<\s*300\s*kw", re.IGNORECASE), 3),
    (re.compile(
        r"medianas?\s+demandas?|\bT\s*-?\s*2\b|tarifa\s*n?\s*[º°o]?\s*\.?\s*2\b|"
        r">\s*10\s*kw", re.IGNORECASE), 2),
    (re.compile(r"\bgeneral(?:es)?\b|comercial|industrial", re.IGNORECASE), 1),
]

EXCLUDE_LINE: Final[re.Pattern[str]] = re.compile(
    r"residencial|social|subsid|bonific|electro\s*-?\s*dependiente|clubes|"
    r"\bsef\b|943/25|\bvad\b|alumbrado|peaje|f\.\s*e\.\s*p|\bzona\b|"
    r"inyect|inyecci|ingresada\s+a\s+la\s+red|generador|renabap|"
    r"bien\s+p[uú]blico|entidades|deportiv|jubilad|\bmt\b|media\s+tensi|"
    r"alta\s+tensi|costo\s+(?:de\s+)?compra",
    re.IGNORECASE,
)
BIG_USER: Final[re.Pattern[str]] = re.compile(
    r"(?:>\s*=?|≥|igual\s+o\s+mayor\s+(?:a|que)|mayor(?:\s+o\s+igual)?\s+(?:a|que)|"
    r"m[aá]s\s+de)\s*300\s*kw|\bgudi",
    re.IGNORECASE,
)
MIN_SCORE: Final[int] = 2
EXCLUDE_CONTEXT: Final[re.Pattern[str]] = re.compile(
    r"peaje|alumbrado\s+p[uú]blico|otros\s+distribuidores", re.IGNORECASE
)
INJECTION_LINE: Final[re.Pattern[str]] = re.compile(
    r"inyect|inyecci|ingresada\s+a\s+la\s+red|entregada\s+a\s+la\s+red",
    re.IGNORECASE,
)
# Encabezado de una tabla de precios de inyección: las filas debajo no
# repiten la palabra "inyección" (p.ej. APE: "Código | Demanda | ... |
# Tarifa de inyección").
INJECTION_CONTEXT: Final[re.Pattern[str]] = re.compile(
    r"tarifas?\s+de\s+inyecci|entregada\s+al\s+sistema|energ[ií]a\s+inyectada",
    re.IGNORECASE,
)
INJECTION_CONTEXT_LINES: Final[int] = 8
# Cuadros especiales (régimen subsidiado o de una categoría puntual): si el
# título del documento los nombra, no se usan como tarifa de compra.
SPECIAL_DOCUMENT: Final[re.Pattern[str]] = re.compile(
    r"clubes\s+de\s+barrio|tarifa\s+social|subsidio\s+del\s+estado|"
    r"electro\s*-?\s*dependiente|bien\s+p[uú]blico|medidores\s+autoadministrados",
    re.IGNORECASE,
)
TITLE_LINES: Final[int] = 6
EXCLUDE_INJECTION: Final[re.Pattern[str]] = re.compile(
    r"residencial|residen\.|social|subsid|\bsef\b|943/25|consumo\s+base|"
    r"electro\s*-?\s*dependiente",
    re.IGNORECASE,
)
CARGO_FIJO: Final[re.Pattern[str]] = re.compile(
    r"cargo\s+fijo|cargo\s+comercial|cuota\s+fija|cargo\s+comercializaci",
    re.IGNORECASE,
)


_EN_FORMAT = False  # se ajusta por documento en parse_tariff_text


def detect_english_format(text: str) -> bool:
    """
    True si el documento usa punto decimal y coma de miles (``662,591.7``).

    Algunos cuadros (p.ej. EDESE) se exportan con formato inglés. Se
    comparan evidencias inequívocas de cada formato: separador de miles
    seguido de decimales (``1,234.5`` vs ``1.234,5``) pesa triple; un
    separador decimal con 1-2 o 4+ dígitos (``156.66`` vs ``156,6643``)
    suma uno.
    """
    en = 3 * len(re.findall(r"\d,\d{3}\.\d", text)) + len(
        re.findall(r"(?<![\d.,])\d+\.(?:\d{1,2}|\d{4,})(?![\d.,])", text)
    )
    ar = 3 * len(re.findall(r"\d\.\d{3},\d", text)) + len(
        re.findall(r"(?<![\d.,])\d+,(?:\d{1,2}|\d{4,})(?![\d.,])", text)
    )
    return en > ar


def parse_ar_number(token: str) -> float | None:
    """Número en formato argentino (``1.234,56``) → float."""
    t = token.strip().replace("$", "").replace(" ", "")
    if not t:
        return None
    if _EN_FORMAT:
        try:
            return float(t.replace(",", ""))
        except ValueError:
            return None
    try:
        if "," in t:
            return float(t.replace(".", "").replace(",", "."))
        if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", t):
            return float(t.replace(".", ""))
        return float(t)
    except ValueError:
        return None


def _plausible(
    values: list[float], vmin: float = PRICE_MIN, vmax: float = PRICE_MAX
) -> list[float]:
    return [v for v in values if vmin <= v <= vmax]


def _numbers(text: str) -> list[float]:
    out = []
    for tok in re.findall(EN_NUMBER if _EN_FORMAT else AR_NUMBER, text):
        v = parse_ar_number(tok)
        if v is not None:
            out.append(v)
    return out


def _is_label(cell: str) -> bool:
    """Celda con texto (no sólo número y/o unidad)."""
    stripped = KWH_UNIT.sub("", OTHER_UNIT.sub("", cell))
    stripped = re.sub(r"\[[^\]]*\]", "", stripped)
    stripped = re.sub(EN_NUMBER if _EN_FORMAT else AR_NUMBER, "", stripped)
    return bool(re.search(r"[A-Za-zÁÉÍÓÚáéíóúñÑ]{2,}", stripped))


def line_kwh_values(line: str, prefer_resto: bool = True) -> list[float]:
    """
    Importes en $/kWh de una línea, celda a celda.

    - Celdas con importe y unidad propagada (``266,8 $/KWh [... Resto ...]``):
      si alguna es de la banda "Resto" se usan sólo esas.
    - Fila ``etiqueta | unidad | v1 | v2 ...``: importes de las celdas
      numéricas que siguen a la etiqueta, hasta la próxima etiqueta (otra
      tabla en paralelo en la misma fila).
    - Línea de PDF sin celdas: importes que siguen a la unidad ``$/kWh``.
    """
    cells = [c.strip() for c in line.split("|")]
    if len(cells) == 1:
        text = cells[0]
        m = list(KWH_UNIT.finditer(text))
        if m:
            # Hasta la próxima etiqueta (PDF con dos tablas lado a lado).
            tail = text[m[-1].end():]
            stop = re.search(r"[A-Za-zÁÉÍÓÚáéíóúñÑ]{2,}", tail)
            after = _numbers(tail[: stop.start()] if stop else tail)
            if after:
                return after
            before = _numbers(text[: m[0].start()])
            return before[-1:]
        return _numbers(text)

    tagged = [
        c for c in cells
        if KWH_UNIT.search(c) and _numbers(KWH_UNIT.split(c)[0]) and not MWH_UNIT.search(c)
    ]
    if tagged:
        if prefer_resto:
            resto = [c for c in tagged if RESTO.search(c)]
            if resto:
                tagged = resto
        vals: list[float] = []
        for c in tagged:
            vals.extend(_numbers(KWH_UNIT.split(c)[0])[-1:])
        return vals

    # etiqueta | (unidad) | valores...
    vals = []
    started = False
    for c in cells:
        if not started:
            if _is_label(c) and not KWH_UNIT.fullmatch(c.strip()):
                started = True
            continue
        if _is_label(c) or OTHER_UNIT.search(c):
            # Varias celdas de texto seguidas (código | categoría | concepto)
            # se saltean; una etiqueta después de importes es otra tabla.
            if vals:
                break
            continue
        vals.extend(_numbers(KWH_UNIT.sub("", c)))
    return vals


@dataclass
class Candidate:
    """Línea candidata a tarifa de compra."""

    index: int
    score: int
    values: list[float]
    line: str


def _has_kwh_unit(lines: list[str], i: int, assume_kwh: bool = False) -> bool:
    line = lines[i]
    if assume_kwh and not OTHER_UNIT.search(line):
        return True
    if KWH_UNIT.search(line) and not MWH_UNIT.search(line):
        return True
    # Fila de banda horaria sin unidad: la unidad está en la(s) línea(s)
    # anterior(es) ("Por consumo de energía | $/kWh") o en el encabezado
    # de la tabla ("Energía en horas Resto | 138,76", EMSA).
    if BAND.search(line) and not OTHER_UNIT.search(line):
        if re.search(r"energ[ií]a", line, re.IGNORECASE):
            return True
        for j in range(max(0, i - 3), i):
            if KWH_UNIT.search(lines[j]) and not MWH_UNIT.search(lines[j]):
                return True
    return False


VOLTAGE: Final[re.Pattern[str]] = re.compile(
    r"\b(baja|media|alta)\s+tensi[oó]n|\b(BT|MT|AT)\b|vinculaci[oó]n\s+(superior)|"
    r"\b(13[,.]2|33|66|132)\s*kv",
    re.IGNORECASE,
)


def _voltage_level(lines: list[str], i: int, lookback: int = 10) -> str | None:
    """Nivel de tensión del bloque (``baja``/``media``/``alta``) o None."""
    for j in range(i, max(-1, i - lookback), -1):
        m = VOLTAGE.search(lines[j])
        if m:
            if m.group(4):
                return "media"
            word = (m.group(1) or m.group(2) or m.group(3)).lower()
            return {"bt": "baja", "mt": "media", "at": "alta", "superior": "alta"}.get(
                word, word
            )
    return None


def _category_score(context: str) -> int:
    best = 0
    for pattern, score in CATEGORY_SCORES:
        if pattern.search(context):
            best = max(best, score)
    return best


def _label(lines: list[str], i: int) -> str:
    """
    Etiqueta efectiva de una línea.

    En PDFs con la tabla desarmada, una línea puede traer sólo
    ``$/kWh 92,94`` y su concepto ("Por la energía inyectada...") quedar
    1-3 líneas arriba. En ese caso se toma la etiqueta de las líneas
    previas sin importes.
    """
    line = lines[i]
    if _is_label(line):
        return line
    prev: list[str] = []
    for j in range(i - 1, max(-1, i - 4), -1):
        if _is_label(lines[j]) and not _numbers(lines[j]):
            prev.append(lines[j])
        elif _numbers(lines[j]):
            break
    return "\n".join(reversed(prev)) + "\n" + line


def find_purchase_candidates(
    lines: list[str], injection_document: bool = False
) -> list[Candidate]:
    """
    Lista las líneas candidatas a tarifa de compra con su puntaje.

    Con ``injection_document`` (planilla cuyo título es "Tarifas de
    inyección ... $/kWh") se aplica el mismo criterio de categoría para
    elegir el precio de inyección representativo: la unidad está en el
    título y no se excluyen las líneas por mencionar inyección.
    """
    cands: list[Candidate] = []
    exclude = EXCLUDE_LINE if not injection_document else re.compile(
        EXCLUDE_LINE.pattern.replace(
            r"inyect|inyecci|ingresada\s+a\s+la\s+red|generador|", ""
        ),
        re.IGNORECASE,
    )
    for i, line in enumerate(lines):
        if not _has_kwh_unit(lines, i, injection_document) or exclude.search(
            _label(lines, i)
        ):
            continue
        context = "\n".join(lines[max(0, i - CONTEXT_LINES): i + 1])
        nearby = "\n".join(lines[max(0, i - 4): i + 1])
        if EXCLUDE_CONTEXT.search(nearby):
            continue
        if not injection_document and INJECTION_CONTEXT.search(
            "\n".join(lines[max(0, i - INJECTION_CONTEXT_LINES): i + 1])
        ):
            continue
        # Un PP30 (25 kW) se conecta en baja tensión.
        if _voltage_level(lines, i) in {"media", "alta"}:
            continue
        score = _category_score(context)
        if score == 0:
            continue
        values = _plausible(line_kwh_values(line))
        if not values:
            continue
        if RESTO.search(_label(lines, i)):
            score += 1
        # Categorías de 300 kW o más no representan a un PP30 (25 kW).
        if BIG_USER.search(nearby):
            score -= 2
        cands.append(Candidate(i, score, values, line.strip()))
    return cands


def find_injection_values(lines: list[str]) -> tuple[list[float], list[str]]:
    """Importes de inyección (usuario-generador) y las líneas usadas."""
    vals: list[float] = []
    used: list[str] = []
    for i, line in enumerate(lines):
        label = _label(lines, i)
        in_table = INJECTION_CONTEXT.search(
            "\n".join(lines[max(0, i - INJECTION_CONTEXT_LINES): i])
        )
        if not (INJECTION_LINE.search(label) or in_table) or EXCLUDE_INJECTION.search(label):
            continue
        if not _has_kwh_unit(lines, i):
            continue
        v = _plausible(line_kwh_values(line, prefer_resto=False))
        if v:
            vals.extend(v)
            used.append(line.strip())
    return vals, used


def find_fixed_charge(lines: list[str], index: int) -> float | None:
    """Cargo fijo mensual más cercano hacia arriba de la línea elegida."""
    for j in range(index, max(-1, index - CONTEXT_LINES - 10), -1):
        line = lines[j]
        if CARGO_FIJO.search(line) and MONTH_UNIT.search(line):
            cells = [c for c in line.split("|")]
            nums: list[float] = []
            for c in cells:
                if MONTH_UNIT.search(c):
                    nums.extend(_numbers(MONTH_UNIT.split(c)[0])[-1:])
            if not nums:
                after = MONTH_UNIT.split(line, maxsplit=1)[-1]
                nums = _numbers(after)
            nums = [n for n in nums if n >= 1.0]
            if nums:
                return nums[0]
    return None


def parse_tariff_text(text: str) -> dict[str, Any]:
    """
    Extrae tarifa de compra, de inyección y cargo fijo de un cuadro.

    Returns:
        Diccionario con ``tarifa_compra_kwh``, ``tarifa_inyeccion_kwh``,
        ``cargo_fijo_mensual`` (None si no se hallaron), ``seccion_compra``
        (línea elegida), ``puntaje_compra``, ``valores_*_detectados`` y
        ``lineas_*`` para auditoría.
    """
    global _EN_FORMAT
    _EN_FORMAT = detect_english_format(text)
    lines = [ln for ln in text.splitlines() if ln.strip()]
    result: dict[str, Any] = {
        "tarifa_compra_kwh": None,
        "tarifa_inyeccion_kwh": None,
        "cargo_fijo_mensual": None,
        "seccion_compra": None,
        "puntaje_compra": 0,
        "valores_compra_detectados": [],
        "valores_inyeccion_detectados": [],
        "lineas_compra": [],
        "lineas_inyeccion": [],
    }
    title = "\n".join(
        ln for ln in lines[:TITLE_LINES] if "|" not in ln and not ln.startswith("# HOJA")
    )
    injection_document = bool(INJECTION_CONTEXT.search(title)) and bool(
        re.search(r"kwh", title, re.IGNORECASE)
    )
    result["documento_especial"] = bool(SPECIAL_DOCUMENT.search(title))
    result["documento_inyeccion"] = injection_document
    if injection_document:
        cands = [c for c in find_purchase_candidates(lines, True) if c.score >= MIN_SCORE]
        if cands:
            best_score = max(c.score for c in cands)
            best = next(c for c in cands if c.score == best_score)
            result["tarifa_inyeccion_kwh"] = round(statistics.median(best.values), 5)
            result["valores_inyeccion_detectados"] = best.values
            result["lineas_inyeccion"] = [best.line[:200]]
        return result
    if result["documento_especial"]:
        # Cuadro de un régimen especial: no representa la tarifa plena.
        return result

    cands = [c for c in find_purchase_candidates(lines) if c.score >= MIN_SCORE]
    if cands:
        best_score = max(c.score for c in cands)
        best = next(c for c in cands if c.score == best_score)
        result["tarifa_compra_kwh"] = round(statistics.median(best.values), 5)
        result["valores_compra_detectados"] = best.values
        result["seccion_compra"] = best.line[:200]
        result["puntaje_compra"] = best.score
        result["lineas_compra"] = [c.line[:200] for c in cands if c.score == best_score][:5]
        result["cargo_fijo_mensual"] = find_fixed_charge(lines, best.index)

    iny, used = find_injection_values(lines)
    if iny:
        result["tarifa_inyeccion_kwh"] = round(statistics.median(iny), 5)
        result["valores_inyeccion_detectados"] = iny
        result["lineas_inyeccion"] = [u[:200] for u in used][:5]
    return result

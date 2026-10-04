"""
Descarga cuadros tarifarios oficiales y extrae las tarifas de referencia.

Fuentes (compra T2/T3 e inyección de usuario-generador, Ley 27.424):

- EPEC (Córdoba): índice https://www.epec.com.ar/docs/cuadro-tarifario/
- EPE (Santa Fe): https://www.epe.santafe.gov.ar/institucional/usuarios
- EDEMSA (Mendoza): https://edemsa.com/segmentacion-tarifaria/
- EDENOR (AMBA): https://www.edenor.com/files/YYYY-MM/Cuadro-Tarifario.pdf

Flujo por distribuidora:

    1. Descubrir el PDF vigente: se descarga la página índice y se toman
       los enlaces ``.pdf`` cuyo nombre contiene palabras clave
       (``tarif``, ``cuadro``). Se ordenan por la fecha embebida en el
       nombre (más reciente primero). Las URLs fijas quedan sólo como
       respaldo.
    2. Validar que el binario sea realmente un PDF (firma ``%PDF``): los
       portales devuelven a veces HTML (login, 404 "amigable") con
       HTTP 200.
    3. Extraer texto (``pypdf``) y localizar la sección de la categoría
       objetivo (T3 grandes demandas / T2 medianas demandas).
    4. Parsear los cargos variables de energía ($/kWh, formato numérico
       argentino ``1.234,5678``) y el cargo fijo ($/mes).
    5. Validar plausibilidad (rango, compra > inyección, variación
       máxima respecto de la corrida previa).
    6. Escribir ``data/reference/YYYYMMDDHHMMSS_tarifas.json`` con
       trazabilidad **por campo**: ``parsed_pdf`` (extraído en esta
       corrida), ``fallback_previous`` (se conservó el valor previo
       porque no se pudo extraer/validar) o ``baseline_manual``.

Errores corregidos respecto de la versión anterior:

- No se extraía ningún valor: el JSON siempre copiaba el baseline
  manual (o el JSON previo) aunque los PDF se descargaran.
- Las URL de EPEC eran PDFs fijos de 2025 (desactualizados).
- No se verificaba que la descarga fuera un PDF.
- ``parse_status`` no distinguía valor extraído de valor heredado.
"""

from __future__ import annotations

import io
import json
import logging
import re
import statistics
from collections.abc import Callable, Iterator
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Final
from urllib.parse import urljoin

import httpx

from etl.extractors.io_utils import (
    JSON_SUFFIX,
    PDF_SUFFIX,
    REF_STEM_TARIFAS,
    build_timestamped_filename,
    find_latest_raw,
)

logger = logging.getLogger(__name__)

# ====================== CONFIGURACIÓN ======================

RAW_TARIFAS_DIR: Final[Path] = Path("./data/raw/tarifas")
REFERENCE_DIR: Final[Path] = Path("./data/reference")

REQUEST_TIMEOUT: Final[float] = 60.0
FOLLOW_REDIRECTS: Final[bool] = True
USER_AGENT: Final[str] = (
    "Mozilla/5.0 (compatible; OPTIMIA-HV-ETL/1.0; +research)"
)
HEADERS: Final[dict[str, str]] = {"User-Agent": USER_AGENT}

PDF_MAGIC: Final[bytes] = b"%PDF"

# Rango plausible de cargos variables de energía (ARS/kWh, sin impuestos).
# Fuera de este rango el valor se descarta (suele ser un cargo de potencia
# en $/kW-mes, un porcentaje o un número de resolución mal capturado).
PRICE_MIN_ARS_KWH: Final[float] = 1.0
PRICE_MAX_ARS_KWH: Final[float] = 2000.0
# Variación máxima aceptada respecto de la corrida previa (factor).
MAX_CHANGE_FACTOR: Final[float] = 4.0

TARIFF_FIELDS: Final[tuple[str, ...]] = (
    "tarifa_compra_kwh",
    "tarifa_inyeccion_kwh",
    "cargo_fijo_mensual",
)

STATUS_PARSED: Final[str] = "parsed_pdf"
STATUS_FALLBACK: Final[str] = "fallback_previous"
STATUS_BASELINE: Final[str] = "baseline_manual"

# EDENOR publica bajo /files/YYYY-MM/Cuadro-Tarifario.pdf
EDENOR_PDF_TEMPLATE: Final[str] = (
    "https://www.edenor.com/files/{year_month}/Cuadro-Tarifario.pdf"
)

EPE_INDEX_URL: Final[str] = (
    "https://www.epe.santafe.gov.ar/institucional/usuarios"
)
EDEMSA_INDEX_URL: Final[str] = "https://edemsa.com/segmentacion-tarifaria/"
EPEC_INDEX_URL: Final[str] = "https://www.epec.com.ar/docs/cuadro-tarifario/"

# Respaldo si el índice de EPEC no lista PDFs (pueden estar vencidos).
EPEC_PDF_FALLBACKS: Final[list[str]] = [
    "https://www.epec.com.ar/docs/cuadro-tarifario/"
    "cuadro-tarifario-publicado-290825-aplicacion-010925.pdf",
]

# Patrones de sección por categoría, en orden de preferencia. Un PP30
# (25 kW) instalado en un establecimiento agroindustrial encuadra en
# medianas/grandes demandas (T2/T3), no en residencial.
SECTION_PATTERNS_COMPRA: Final[list[str]] = [
    r"TARIFA\s*N?\s*[º°o]?\s*\.?\s*3\b",
    r"\bT\s*3\b",
    r"GRANDES\s+(?:CONSUMOS|DEMANDAS)",
    r"TARIFA\s*N?\s*[º°o]?\s*\.?\s*2\b",
    r"\bT\s*2\b",
    r"MEDIANAS?\s+DEMANDAS?",
]
SECTION_PATTERNS_INYECCION: Final[list[str]] = [
    r"INYECCI[OÓ]N",
    r"GENERACI[OÓ]N\s+DISTRIBUIDA",
    r"USUARIOS?[\s-]+GENERADOR(?:ES)?",
    r"EXCEDENTES?",
]
# Fin de sección: comienzo de otra tarifa/categoría.
SECTION_END_PATTERN: Final[str] = (
    r"\n\s*(?:TARIFA\s*N?\s*[º°o]?\s*\.?\s*\d|T\s*\d\s*[-–:])"
)
SECTION_MAX_CHARS: Final[int] = 6000

# Número argentino: 1.234.567,89 | 54,04222 | 1234,5 | 210
AR_NUMBER_PATTERN: Final[str] = r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+,\d+|\d+"
KWH_UNIT_PATTERN: Final[str] = r"\$?\s*/\s*kWh|\$\s*kWh|por\s+kWh"
MONTH_UNIT_PATTERN: Final[str] = r"\$?\s*/\s*mes|por\s+mes|mensual"

# Baseline numérico del proyecto (referencia manual). Se usa sólo si no
# hay JSON previo ni valores extraídos. NO verificado contra los cuadros
# vigentes: ver REPORTE_CAMBIOS.md.
BASELINE_TARIFAS: Final[dict[str, Any]] = {
    "descripcion": (
        "Cuadros tarifarios regionales de Argentina para Generacion "
        "Distribuida (Tarifas Comerciales T2/T3)"
    ),
    "unidad_moneda": "ARS",
    "unidad_tarifas": "ARS/kWh sin impuestos; cargo fijo en ARS/mes",
    "parametros_pp30": {
        "consumo_especifico_kg_kwh": 1.1,
        "humedad_pct_default": 12.0,
        "factor_autoconsumo_default": 0.6,
        "potencia_nominal_kw": 25.0,
        "disponibilidad": 0.8,
        "fraccion_recuperable_default": 0.5,
    },
    "distribuidoras": {
        "EPEC_CORDOBA": {
            "provincia": "Córdoba",
            "tarifa_compra_kwh": 210.0,
            "tarifa_inyeccion_kwh": 42.0,
            "cargo_fijo_mensual": 12500.0,
            "fuente_url": EPEC_INDEX_URL,
            "es_proxy": False,
        },
        "EPE_SANTA_FE": {
            "provincia": "Santa Fe",
            "tarifa_compra_kwh": 175.0,
            "tarifa_inyeccion_kwh": 38.0,
            "cargo_fijo_mensual": 11200.0,
            "fuente_url": EPE_INDEX_URL,
            "es_proxy": False,
        },
        "EDEMSA_MENDOZA": {
            "provincia": "Mendoza",
            "tarifa_compra_kwh": 135.0,
            "tarifa_inyeccion_kwh": 33.0,
            "cargo_fijo_mensual": 9800.0,
            "fuente_url": EDEMSA_INDEX_URL,
            "es_proxy": False,
        },
        "EDENOR_AMBA": {
            "provincia": "Buenos Aires / AMBA",
            "tarifa_compra_kwh": 85.0,
            "tarifa_inyeccion_kwh": 26.5,
            "cargo_fijo_mensual": 8500.0,
            "fuente_url": "https://www.edenor.com/",
            # EDENOR sólo abastece el AMBA norte/oeste. Los departamentos
            # agrícolas bonaerenses los atienden EDEN/EDEA/EDES y
            # cooperativas (cuadros OCEBA): la tarifa es una aproximación.
            "es_proxy": True,
        },
    },
    "provincia_a_distribuidora": {
        "cordoba": "EPEC_CORDOBA",
        "santa fe": "EPE_SANTA_FE",
        "mendoza": "EDEMSA_MENDOZA",
        "buenos aires": "EDENOR_AMBA",
    },
}


# ====================== PARSEO NUMÉRICO ======================

def parse_ar_number(token: str) -> float | None:
    """
    Convierte un número en formato argentino a float.

    Reglas: si hay coma, la coma es decimal y los puntos son miles
    (``1.234,56`` → 1234.56). Sin coma, los puntos en grupos de 3 son
    miles (``12.500`` → 12500); un único punto con != 3 decimales se
    interpreta como decimal (``54.04`` → 54.04).

    Args:
        token: Texto numérico.

    Returns:
        Valor float o None si no es interpretable.
    """
    t = token.strip().replace("$", "").replace(" ", "")
    if not t:
        return None
    try:
        if "," in t:
            return float(t.replace(".", "").replace(",", "."))
        if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", t):
            return float(t.replace(".", ""))
        return float(t)
    except ValueError:
        return None


# ====================== PARSEO DE TEXTO ======================

def iter_sections(
    text: str,
    patterns: list[str],
    max_chars: int = SECTION_MAX_CHARS,
) -> Iterator[tuple[str, str]]:
    """
    Itera los bloques de texto cuyo encabezado coincide con los patrones.

    Cada bloque va desde el encabezado hasta el próximo encabezado de
    tarifa (o ``max_chars``). Se recorren los patrones en orden de
    preferencia y, dentro de cada uno, todas sus ocurrencias (la primera
    puede ser un índice o una nota sin importes).

    Args:
        text: Texto completo del cuadro tarifario.
        patterns: Regex de encabezado, en orden de preferencia.
        max_chars: Longitud máxima del bloque.

    Yields:
        Tuplas (patrón, bloque).
    """
    for pat in patterns:
        for m in re.finditer(pat, text, flags=re.IGNORECASE):
            rest = text[m.end(): m.end() + max_chars]
            end = re.search(SECTION_END_PATTERN, rest, flags=re.IGNORECASE)
            yield pat, text[m.start(): m.end() + (end.start() if end else len(rest))]


def first_section_with_values(
    text: str,
    patterns: list[str],
    unit_pattern: str = r"\$?\s*/\s*kWh|\$\s*kWh|por\s+kWh",
) -> tuple[str, str, list[float]] | None:
    """Primer bloque (en orden de preferencia) con valores plausibles $/kWh."""
    for pat, block in iter_sections(text, patterns):
        vals = extract_unit_values(
            block, unit_pattern, PRICE_MIN_ARS_KWH, PRICE_MAX_ARS_KWH
        )
        if vals:
            return pat, block, vals
    return None


def extract_unit_values(
    block: str,
    unit_pattern: str,
    vmin: float | None = None,
    vmax: float | None = None,
) -> list[float]:
    """
    Extrae los valores numéricos asociados a una unidad en un bloque.

    Considera cada línea que contiene la unidad y toma el último número
    de la línea (en los cuadros tarifarios el importe suele estar a la
    derecha de la descripción y la unidad). Si la unidad está en una
    línea y el valor en la siguiente, también se captura.

    Args:
        block: Texto de la sección.
        unit_pattern: Regex de la unidad (p.ej. ``$/kWh``).
        vmin: Mínimo plausible (incl.).
        vmax: Máximo plausible (incl.).

    Returns:
        Lista de valores plausibles en orden de aparición.
    """
    values: list[float] = []
    lines = block.splitlines()
    for i, line in enumerate(lines):
        if not re.search(unit_pattern, line, flags=re.IGNORECASE):
            continue
        # Se elimina la unidad para no capturar el "2" de "kWh/m2", etc.
        cleaned = re.sub(unit_pattern, " ", line, flags=re.IGNORECASE)
        nums = re.findall(AR_NUMBER_PATTERN, cleaned)
        if not nums and i + 1 < len(lines):
            nums = re.findall(AR_NUMBER_PATTERN, lines[i + 1])
        if not nums:
            continue
        val = parse_ar_number(nums[-1])
        if val is None:
            continue
        if vmin is not None and val < vmin:
            continue
        if vmax is not None and val > vmax:
            continue
        values.append(val)
    return values


def parse_tariff_text(text: str) -> dict[str, Any]:
    """
    Extrae tarifa de compra, de inyección y cargo fijo de un cuadro.

    - Compra: mediana de los cargos variables $/kWh de la sección T3/T2
      (si hay bandas pico/resto/valle o escalones, la mediana representa
      la banda central).
    - Inyección: mediana de los $/kWh de la sección de inyección /
      generación distribuida.
    - Cargo fijo: primer valor $/mes de la sección de compra.

    Args:
        text: Texto plano del PDF.

    Returns:
        Diccionario con los valores encontrados (None si no se halló),
        la sección usada y los valores crudos detectados.
    """
    result: dict[str, Any] = {
        "tarifa_compra_kwh": None,
        "tarifa_inyeccion_kwh": None,
        "cargo_fijo_mensual": None,
        "seccion_compra": None,
        "valores_compra_detectados": [],
        "valores_inyeccion_detectados": [],
    }
    compra = first_section_with_values(text, SECTION_PATTERNS_COMPRA, KWH_UNIT_PATTERN)
    if compra is not None:
        pat, block, vals = compra
        result["seccion_compra"] = pat
        result["valores_compra_detectados"] = vals
        result["tarifa_compra_kwh"] = round(statistics.median(vals), 5)
        fijos = extract_unit_values(block, MONTH_UNIT_PATTERN, 1.0, None)
        if fijos:
            result["cargo_fijo_mensual"] = fijos[0]

    iny = first_section_with_values(text, SECTION_PATTERNS_INYECCION, KWH_UNIT_PATTERN)
    if iny is not None:
        _, _, vals = iny
        result["valores_inyeccion_detectados"] = vals
        result["tarifa_inyeccion_kwh"] = round(statistics.median(vals), 5)
    return result


def extract_pdf_text(content: bytes) -> str:
    """
    Extrae el texto plano de un PDF con ``pypdf``.

    Args:
        content: Binario del PDF.

    Returns:
        Texto concatenado de todas las páginas.

    Raises:
        ValueError: Si el contenido no es un PDF.
    """
    if not is_pdf(content):
        raise ValueError("El contenido descargado no es un PDF")
    from pypdf import PdfReader  # import diferido: dependencia sólo del extractor

    reader = PdfReader(io.BytesIO(content))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


# ====================== VALIDACIÓN ======================

def validate_parsed(
    parsed: dict[str, Any],
    previous: dict[str, Any] | None,
) -> dict[str, str]:
    """
    Valida los valores extraídos. Devuelve el motivo de rechazo por campo.

    Reglas:
        - Inyección < compra (la energía inyectada se remunera a precio
          mayorista, inferior a la tarifa de venta al usuario).
        - Variación respecto del valor previo dentro de
          [1/MAX_CHANGE_FACTOR, MAX_CHANGE_FACTOR].

    Args:
        parsed: Salida de ``parse_tariff_text``.
        previous: Bloque previo de la distribuidora (o None).

    Returns:
        Diccionario campo → motivo de rechazo (vacío si todo es válido).
    """
    rejected: dict[str, str] = {}
    compra = parsed.get("tarifa_compra_kwh")
    iny = parsed.get("tarifa_inyeccion_kwh")
    if compra is not None and iny is not None and iny >= compra:
        rejected["tarifa_inyeccion_kwh"] = (
            f"inyección ({iny}) >= compra ({compra})"
        )
    if previous:
        for field in TARIFF_FIELDS:
            new = parsed.get(field)
            old = previous.get(field)
            if new is None or field in rejected or not old:
                continue
            ratio = new / float(old)
            if not (1.0 / MAX_CHANGE_FACTOR <= ratio <= MAX_CHANGE_FACTOR):
                rejected[field] = (
                    f"variación ×{ratio:.2f} respecto del valor previo {old}"
                )
    return rejected


def merge_distribuidora(
    code: str,
    parsed: dict[str, Any] | None,
    previous: dict[str, Any] | None,
    baseline: dict[str, Any],
    documento: str | None,
    fecha: str,
) -> dict[str, Any]:
    """
    Combina valores extraídos, previos y baseline con trazabilidad por campo.

    Args:
        code: Código de distribuidora.
        parsed: Salida de ``parse_tariff_text`` (None si no hubo PDF).
        previous: Bloque de la corrida previa (None si no existe).
        baseline: Bloque del baseline manual.
        documento: URL/ruta del PDF usado.
        fecha: Fecha ISO de la corrida.

    Returns:
        Bloque de distribuidora para el JSON de referencia.
    """
    block: dict[str, Any] = {
        k: v for k, v in baseline.items() if k not in TARIFF_FIELDS
    }
    estado: dict[str, str] = {}
    rejected = validate_parsed(parsed, previous) if parsed else {}
    prev_estado = (previous or {}).get("estado_campos", {})
    for field in TARIFF_FIELDS:
        new = (parsed or {}).get(field)
        if new is not None and field not in rejected:
            block[field] = new
            estado[field] = STATUS_PARSED
        elif previous is not None and previous.get(field) is not None:
            block[field] = previous[field]
            # Un valor previo heredado conserva su origen (si era baseline
            # sigue siendo baseline; si fue extraído, ahora es fallback).
            prev = prev_estado.get(field, previous.get("parse_status", STATUS_BASELINE))
            estado[field] = STATUS_BASELINE if prev == STATUS_BASELINE else STATUS_FALLBACK
        else:
            block[field] = baseline.get(field)
            estado[field] = STATUS_BASELINE
    block["estado_campos"] = estado
    block["parse_status"] = (
        STATUS_PARSED if all(v == STATUS_PARSED for v in estado.values())
        else STATUS_BASELINE if all(v == STATUS_BASELINE for v in estado.values())
        else "mixto"
    )
    if parsed is not None:
        block["documento_fuente"] = documento
        block["fecha_extraccion"] = fecha
        block["seccion_detectada"] = parsed.get("seccion_compra")
        block["valores_detectados"] = {
            "compra": parsed.get("valores_compra_detectados", []),
            "inyeccion": parsed.get("valores_inyeccion_detectados", []),
        }
    elif previous is not None:
        for k in ("documento_fuente", "fecha_extraccion"):
            if k in previous:
                block[k] = previous[k]
    if rejected:
        block["rechazos_validacion"] = rejected
        logger.warning("[tarifas] %s: valores rechazados %s", code, rejected)
    return block


# ====================== HTTP ======================

def download_bytes(url: str) -> bytes:
    """
    Descarga el contenido binario de una URL.

    Raises:
        httpx.HTTPStatusError: Si el servidor responde error HTTP.
        httpx.RequestError: Si falla la comunicación.
    """
    response = httpx.get(
        url,
        headers=HEADERS,
        follow_redirects=FOLLOW_REDIRECTS,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.content


def try_download(
    url: str,
    downloader: Callable[[str], bytes] = download_bytes,
) -> bytes | None:
    """Intenta descargar una URL; devuelve None si falla o viene vacía."""
    try:
        content = downloader(url)
    except (httpx.HTTPError, OSError) as exc:
        logger.warning("[tarifas] Falla descarga %s: %s", url, exc)
        return None
    if not content:
        logger.warning("[tarifas] Respuesta vacía: %s", url)
        return None
    return content


def is_pdf(content: bytes) -> bool:
    """True si el binario tiene firma PDF (tolera BOM/espacios iniciales)."""
    return PDF_MAGIC in content[:1024]


# ====================== DESCUBRIMIENTO DE PDF ======================

_DATE_IN_NAME = re.compile(
    r"(?P<ymd>20\d{2})[-_]?(?P<m>[01]\d)(?:[-_]?(?P<d>[0-3]\d))?"
    r"|(?P<d2>[0-3]\d)(?P<m2>[01]\d)(?P<y2>\d{2})"
)


def _date_score(url: str) -> int:
    """
    Puntaje temporal a partir de la fecha embebida en el nombre del PDF.

    Reconoce ``YYYY-MM``, ``YYYYMMDD`` y ``DDMMYY`` (EPEC:
    ``...-publicado-290825-aplicacion-010925.pdf``). Se usa la fecha
    más alta encontrada (la de aplicación). Sin fecha → 0.
    """
    best = 0
    name = url.rsplit("/", 1)[-1]
    for m in _DATE_IN_NAME.finditer(url if "files/" in url else name):
        if m.group("ymd"):
            y, mo, d = int(m.group("ymd")), int(m.group("m")), int(m.group("d") or 1)
        else:
            y, mo, d = 2000 + int(m.group("y2")), int(m.group("m2")), int(m.group("d2"))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            best = max(best, y * 10000 + mo * 100 + d)
    return best


def discover_pdf_links(
    html: str,
    base_url: str,
    keywords: tuple[str, ...] = ("tarif", "cuadro"),
) -> list[str]:
    """
    Lista enlaces a PDF de una página índice, más recientes primero.

    Args:
        html: HTML de la página índice.
        base_url: URL de la página (para resolver enlaces relativos).
        keywords: Al menos una debe aparecer en la URL o el texto del enlace.

    Returns:
        URLs absolutas ordenadas por fecha embebida descendente.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []
    for a in soup.find_all("a", href=True):
        href = str(a["href"]).strip()
        if ".pdf" not in href.lower():
            continue
        haystack = (href + " " + a.get_text(" ", strip=True)).lower()
        if not any(k in haystack for k in keywords):
            continue
        url = urljoin(base_url, href)
        if url not in links:
            links.append(url)
    return sorted(links, key=_date_score, reverse=True)


def edenor_candidate_urls(now: datetime) -> list[str]:
    """URLs mensuales EDENOR: mes corriente y anterior."""
    prev = now.replace(day=1) - timedelta(days=1)
    yms = list(dict.fromkeys([now.strftime("%Y-%m"), prev.strftime("%Y-%m")]))
    return [EDENOR_PDF_TEMPLATE.format(year_month=ym) for ym in yms]


# Configuración por distribuidora: índice + URLs de respaldo.
SOURCES: Final[dict[str, dict[str, Any]]] = {
    "EPEC_CORDOBA": {"index": EPEC_INDEX_URL, "fallbacks": EPEC_PDF_FALLBACKS},
    "EPE_SANTA_FE": {"index": EPE_INDEX_URL, "fallbacks": []},
    "EDEMSA_MENDOZA": {"index": EDEMSA_INDEX_URL, "fallbacks": []},
    "EDENOR_AMBA": {"index": None, "fallbacks": "edenor"},
}


def candidate_pdf_urls(
    code: str,
    now: datetime,
    raw_dir: Path,
    downloader: Callable[[str], bytes] = download_bytes,
) -> list[str]:
    """
    Resuelve las URLs candidatas de PDF de una distribuidora.

    Guarda el HTML del índice en ``raw_dir`` como evidencia de la corrida.
    """
    spec = SOURCES[code]
    urls: list[str] = []
    if spec["index"]:
        html = try_download(spec["index"], downloader)
        if html is not None:
            name = build_timestamped_filename(
                f"{code.lower()}_index", suffix=".html", ts=now
            )
            save_bytes(html, raw_dir / name)
            urls.extend(
                discover_pdf_links(html.decode("utf-8", "ignore"), spec["index"])
            )
    fallbacks = spec["fallbacks"]
    if fallbacks == "edenor":
        fallbacks = edenor_candidate_urls(now)
    urls.extend(u for u in fallbacks if u not in urls)
    return urls


def fetch_and_parse(
    code: str,
    now: datetime,
    raw_dir: Path,
    downloader: Callable[[str], bytes] = download_bytes,
    text_extractor: Callable[[bytes], str] = extract_pdf_text,
    max_candidates: int = 3,
) -> tuple[dict[str, Any] | None, str | None]:
    """
    Descarga el primer PDF válido de la distribuidora y lo parsea.

    Se prueban hasta ``max_candidates`` URLs (más recientes primero) y se
    acepta la primera que sea PDF y de la que se extraiga al menos la
    tarifa de compra.

    Returns:
        Tupla (resultado de ``parse_tariff_text`` o None, URL usada).
    """
    for url in candidate_pdf_urls(code, now, raw_dir, downloader)[:max_candidates]:
        content = try_download(url, downloader)
        if content is None:
            continue
        if not is_pdf(content):
            logger.warning("[tarifas] %s: %s no es PDF (¿HTML de error?)", code, url)
            continue
        name = build_timestamped_filename(code.lower(), suffix=PDF_SUFFIX, ts=now)
        save_bytes(content, raw_dir / name)
        try:
            text = text_extractor(content)
        except Exception as exc:  # PDF corrupto / cifrado
            logger.warning("[tarifas] %s: no se pudo leer %s: %s", code, url, exc)
            continue
        parsed = parse_tariff_text(text)
        if parsed["tarifa_compra_kwh"] is None:
            logger.warning(
                "[tarifas] %s: %s sin cargos $/kWh reconocibles", code, url
            )
            continue
        logger.info(
            "[tarifas] %s: compra=%s inyección=%s (sección %s) desde %s",
            code,
            parsed["tarifa_compra_kwh"],
            parsed["tarifa_inyeccion_kwh"],
            parsed["seccion_compra"],
            url,
        )
        return parsed, url
    return None, None


# ====================== ALMACENAMIENTO ======================

def save_bytes(content: bytes, output_path: Path) -> Path:
    """Persiste contenido binario creando directorios padre."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(content)
    return output_path.resolve()


def save_json(data: dict[str, Any], output_path: Path) -> Path:
    """Persiste un diccionario como JSON UTF-8 indentado."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return output_path.resolve()


def load_previous_reference(ref_dir: Path) -> dict[str, Any] | None:
    """Carga el JSON de tarifas más reciente, o None si no existe."""
    try:
        previous = find_latest_raw(ref_dir, REF_STEM_TARIFAS, suffix=JSON_SUFFIX)
    except FileNotFoundError:
        return None
    with previous.open(encoding="utf-8") as handle:
        return json.load(handle)


# ====================== REFERENCIA CONSOLIDADA ======================

def build_reference_payload(
    parsed_by_code: dict[str, tuple[dict[str, Any] | None, str | None]],
    previous: dict[str, Any] | None,
    ts: datetime | None = None,
) -> dict[str, Any]:
    """
    Construye el JSON de referencia consumido por ``energy_finance``.

    Los parámetros operativos y el mapeo provincial se heredan del JSON
    previo (pueden haber sido ajustados a mano); las claves nuevas del
    baseline se agregan si faltan.

    Args:
        parsed_by_code: Código → (parseo, URL) de esta corrida.
        previous: JSON previo o None.
        ts: Timestamp de la corrida.

    Returns:
        Diccionario listo para serializar.
    """
    now = ts or datetime.now()
    fecha = now.strftime("%Y-%m-%dT%H:%M:%S")
    base = json.loads(json.dumps(BASELINE_TARIFAS))  # deep copy
    payload: dict[str, Any] = {
        k: v for k, v in base.items() if k != "distribuidoras"
    }
    if previous:
        params = dict(base["parametros_pp30"])
        params.update(previous.get("parametros_pp30", {}))
        payload["parametros_pp30"] = params
        if "provincia_a_distribuidora" in previous:
            payload["provincia_a_distribuidora"] = previous["provincia_a_distribuidora"]

    prev_dist = (previous or {}).get("distribuidoras", {})
    payload["distribuidoras"] = {}
    for code, base_block in base["distribuidoras"].items():
        parsed, url = parsed_by_code.get(code, (None, None))
        payload["distribuidoras"][code] = merge_distribuidora(
            code, parsed, prev_dist.get(code), base_block, url, fecha
        )

    payload["ultima_actualizacion"] = now.strftime("%Y-%m")
    payload["generado_en"] = fecha
    n_parsed = sum(
        1 for b in payload["distribuidoras"].values()
        if b["estado_campos"].get("tarifa_compra_kwh") == STATUS_PARSED
    )
    payload["resumen_extraccion"] = {
        "distribuidoras_con_tarifa_extraida": n_parsed,
        "distribuidoras_totales": len(payload["distribuidoras"]),
    }
    return payload


# ====================== EJECUCIÓN ======================

def run_extractor(
    raw_dir: Path | str | None = None,
    reference_dir: Path | str | None = None,
    downloader: Callable[[str], bytes] = download_bytes,
    text_extractor: Callable[[bytes], str] = extract_pdf_text,
) -> Path:
    """
    Descarga cuadros, extrae tarifas y escribe la referencia consolidada.

    Nunca falla por una distribuidora caída: en ese caso conserva el
    valor previo y lo marca como ``fallback_previous``.

    Args:
        raw_dir: Destino de PDFs/HTML (default ``data/raw/tarifas``).
        reference_dir: Destino del JSON (default ``data/reference``).
        downloader: Función de descarga (inyectable para tests).
        text_extractor: Función PDF → texto (inyectable para tests).

    Returns:
        Path absoluto del ``YYYYMMDDHHMMSS_tarifas.json`` generado.
    """
    now = datetime.now()
    raw_path = Path(raw_dir) if raw_dir is not None else RAW_TARIFAS_DIR
    ref_path = Path(reference_dir) if reference_dir is not None else REFERENCE_DIR
    raw_path.mkdir(parents=True, exist_ok=True)
    ref_path.mkdir(parents=True, exist_ok=True)

    previous = load_previous_reference(ref_path)
    parsed_by_code = {
        code: fetch_and_parse(code, now, raw_path, downloader, text_extractor)
        for code in SOURCES
    }
    payload = build_reference_payload(parsed_by_code, previous, ts=now)

    out_name = build_timestamped_filename(REF_STEM_TARIFAS, suffix=JSON_SUFFIX, ts=now)
    out_path = save_json(payload, ref_path / out_name)
    logger.info(
        "[tarifas] Referencia escrita: %s (%s)",
        out_path,
        payload["resumen_extraccion"],
    )
    return out_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_extractor()

"""
Descarga cuadros tarifarios oficiales de todas las distribuidoras del país
y extrae las tarifas de referencia, con historial de cambios.

Fuentes (ver ``etl/reference/distribuidoras.py``):

1. **Portal nacional** de la Secretaría de Energía: una página por
   distribuidora con los cuadros mensuales (PDF/XLSX/ZIP) desde 2025.
   También se prueban las URLs directas con el patrón
   ``cuadros_tarifarios_desde_2025/<DIR>/<AAAA>_<MM>_<DIR>.<ext>``.
2. **Fuente propia** de la distribuidora o de su ente regulador (OCEBA,
   EPRE, etc.): páginas índice, URLs directas y plantillas por mes.

Flujo por distribuidora:

    1. Armar la lista de documentos candidatos (más recientes primero).
    2. Descargar y validar el formato por firma binaria (PDF, XLSX, ZIP);
       un HTML de error con HTTP 200 se descarta.
    3. Convertir a texto (``tariff_documents``) y parsear los cargos
       ``$/kWh`` de la categoría objetivo (T3/T2) y de inyección.
    4. Determinar la **vigencia** del cuadro (AAAA-MM) por el nombre del
       archivo o por el texto ("vigencia a partir del 1° de ...").
    5. Registrar cada documento procesado en el **historial**
       ``data/reference/tarifas_historial.csv`` (append-only, dedupe por
       SHA-256).
    6. Elegir, por distribuidora, el cuadro de vigencia más reciente,
       validarlo y escribir ``data/reference/AAAAMMDDHHMMSS_tarifas.json``
       con trazabilidad por campo:
       ``extraido`` | ``fallback_previous`` | ``baseline_manual`` | ``sin_dato``.

Uso:
    python -m etl.extractors.scrape_tarifas                # vigentes
    python -m etl.extractors.scrape_tarifas --historial    # + backfill 2025→hoy
    python -m etl.extractors.scrape_tarifas --solo EPEC EDESAL
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
from collections.abc import Callable
from datetime import datetime
from html import unescape
from pathlib import Path
from typing import Any, Final
from urllib.parse import urljoin, urlparse

import httpx

from etl.extractors import tariff_parser as _parser
from etl.extractors.io_utils import (
    JSON_SUFFIX,
    REF_STEM_TARIFAS,
    build_timestamped_filename,
    find_latest_raw,
)
from etl.extractors.tariff_documents import (
    PDF_MAGIC,
    detect_format,
    document_to_texts,
)
from etl.loaders.tariff_history import append_history
from etl.reference.distribuidoras import (
    DEPARTAMENTO_A_DISTRIBUIDORA,
    DISTRIBUIDORAS,
    DISTRIBUIDORAS_PROXY,
    INDEX_KEYWORDS,
    NATIONAL_EXTENSIONS,
    NATIONAL_FILES_BASE,
    NATIONAL_PAGE_BASE,
    PROVINCIA_A_DISTRIBUIDORA,
)

logger = logging.getLogger(__name__)

# ====================== CONFIGURACIÓN ======================

RAW_TARIFAS_DIR: Final[Path] = Path("./data/raw/tarifas")
REFERENCE_DIR: Final[Path] = Path("./data/reference")

REQUEST_TIMEOUT: Final[float] = 30.0
FOLLOW_REDIRECTS: Final[bool] = True
USER_AGENT: Final[str] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/139.0 Safari/537.36 OPTIMIA-HV-ETL/1.0"
)
HEADERS: Final[dict[str, str]] = {"User-Agent": USER_AGENT}

# Meses hacia atrás que se prueban con plantillas de URL por fecha.
MONTHS_BACK: Final[int] = 6
# Máximo de descargas de documentos por distribuidora y tipo de fuente
# en una corrida normal (evita martillar portales caídos).
MAX_DOWNLOADS_PER_SOURCE: Final[int] = 8
BACKFILL_START: Final[str] = "2025-01"

# Variación máxima aceptada respecto de la corrida previa (factor).
MAX_CHANGE_FACTOR: Final[float] = 4.0

TARIFF_FIELDS: Final[tuple[str, ...]] = (
    "tarifa_compra_kwh",
    "tarifa_inyeccion_kwh",
    "cargo_fijo_mensual",
)

STATUS_PARSED: Final[str] = "extraido"
STATUS_FALLBACK: Final[str] = "fallback_previous"
STATUS_BASELINE: Final[str] = "baseline_manual"
STATUS_MISSING: Final[str] = "sin_dato"
# Estados de corridas anteriores que equivalen a "extraído".
_PARSED_ALIASES: Final[frozenset[str]] = frozenset({STATUS_PARSED, "parsed_pdf"})

SOURCE_NATIONAL: Final[str] = "nacional"
SOURCE_OWN: Final[str] = "propia"
SOURCE_MANUAL: Final[str] = "manual"

# EPE Santa Fe: los archivos se bajan de una API con una clave pública que
# el propio sitio incluye en su JavaScript (``_astro/httpClient.*.js``).
# Si la cambian, se puede indicar la nueva en la variable EPE_API_KEY.
EPE_DOWNLOAD_BASE: Final[str] = "https://epe.santafe.gov.ar/institucional-api/download/"
HOST_HEADERS: Final[dict[str, dict[str, str]]] = {
    "epe.santafe.gov.ar": {
        "x-api-key": os.environ.get("EPE_API_KEY", "d745e6f4-6dd6-41b8-9a21-859e9bd1284b"),
    },
}
ASTRO_FILE: Final[re.Pattern[str]] = re.compile(
    r'"fileName":\[0,"([^"]+)"\].{0,400}?"fileHash":\[0,"([0-9a-fA-F-]{36})"\]',
    re.DOTALL,
)

# Carpeta para cuadros descargados a mano de fuentes que bloquean la
# descarga automática (EPEC y EPE: 403/API con clave; ESJ, SPSE, DPE).
# Estructura: data/reference/cuadros_manuales/<CODIGO>/<archivo>.pdf|xlsx|zip
MANUAL_DIR_NAME: Final[str] = "cuadros_manuales"

DOC_EXTENSIONS: Final[tuple[str, ...]] = (".pdf", ".xlsx", ".xls", ".zip")

# Códigos usados por versiones anteriores del JSON → códigos actuales.
LEGACY_CODES: Final[dict[str, str]] = {
    "EPEC_CORDOBA": "EPEC",
    "EPE_SANTA_FE": "EPE",
    "EDEMSA_MENDOZA": "EDEMSA",
    "EDENOR_AMBA": "EDENOR",
}

MESES: Final[dict[str, int]] = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5,
    "junio": 6, "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9,
    "octubre": 10, "noviembre": 11, "diciembre": 12,
}
MES_NOMBRE: Final[dict[int, str]] = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
    7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre",
    11: "Noviembre", 12: "Diciembre",
}

PARAMETROS_PP30_DEFAULT: Final[dict[str, float]] = {
    "consumo_especifico_kg_kwh": 1.1,
    "humedad_pct_default": 12.0,
    "factor_autoconsumo_default": 0.6,
    "potencia_nominal_kw": 25.0,
    "disponibilidad": 0.8,
    "fraccion_recuperable_default": 0.5,
}

# Los valores cargados a mano en versiones anteriores del proyecto (no
# verificados) ya no se usan: una distribuidora sin cuadro extraído queda
# ``sin_dato`` en lugar de usar un número inventado. ``STATUS_BASELINE``
# se mantiene para reconocer JSON viejos.


# ====================== PARSEO ======================
# El parseo de cuadros vive en ``tariff_parser`` (puntaje de líneas
# candidatas); se re-exporta acá por compatibilidad.
parse_ar_number = _parser.parse_ar_number
parse_tariff_text = _parser.parse_tariff_text


# ====================== VIGENCIA ======================

def _ym(year: int, month: int) -> str | None:
    if 2000 <= year <= 2100 and 1 <= month <= 12:
        return f"{year:04d}-{month:02d}"
    return None


def vigencia_from_name(url: str) -> str | None:
    """
    Vigencia AAAA-MM a partir del nombre/ruta del documento.

    Reconoce ``AAAA_MM`` / ``AAAA-MM`` (portal nacional, EDENOR),
    ``Mes_AAAA`` (EDESA, EDEA, EDERSA), carpetas ``AAAA/mes/``
    (OCEBA) y ``DDMMAA`` (EPEC: se toma la
    fecha más alta, la de aplicación). Devuelve None si no hay fecha.
    Si la URL trae el nombre de archivo como fragmento (descargas por API
    de EPE), se usa sólo ese nombre.
    """
    parsed = urlparse(url)
    path = (parsed.fragment or parsed.path).lower()
    name = path.rsplit("/", 1)[-1]
    candidates: list[str] = []
    for m in re.finditer(r"ct_?(20\d{2})_?(0[1-9]|1[0-2])(?:[0-3]\d)?(?!\d)", path):
        candidates.append(_ym(int(m.group(1)), int(m.group(2))) or "")
    for m in re.finditer(r"(20\d{2})[_-](0[1-9]|1[0-2])(?!\d)", path):
        candidates.append(_ym(int(m.group(1)), int(m.group(2))) or "")
    for mes, num in MESES.items():
        for m in re.finditer(rf"{mes}[\s_-]*(20\d{{2}})", name):
            candidates.append(_ym(int(m.group(1)), num) or "")
        # Carpetas por año y mes (OCEBA: cuadros-tarifarios/2023/junio-2/).
        for m in re.finditer(rf"(20\d{{2}})/{mes}(?:-\d+)?/", path):
            candidates.append(_ym(int(m.group(1)), num) or "")
    for m in re.finditer(r"(?<!\d)([0-3]\d)([01]\d)(\d{2})(?!\d)", name):
        d, mo, y = int(m.group(1)), int(m.group(2)), 2000 + int(m.group(3))
        if 1 <= d <= 31:
            candidates.append(_ym(y, mo) or "")
    candidates = [c for c in candidates if c]
    return max(candidates) if candidates else None


def vigencia_explicit(text: str) -> str | None:
    """
    Vigencia declarada en el texto.

    Reconoce "vigencia a partir del 1° de junio de 2026", "Vigencia: 01 de
    Mayo al 31 de Julio de 2026" (se toma el **inicio**: mayo), "a partir
    del 01/06/26" y "a partir de los consumos del ... de junio 2026". Tiene
    prioridad sobre el nombre del archivo, que a veces indica el mes de
    publicación y no el de vigencia.
    """
    head = text[:4000].lower()
    month_re = r"\b(" + "|".join(MESES) + r")\b"
    for m in re.finditer(r"vigen\w*|a\s+partir", head):
        window = head[m.end(): m.end() + 120]
        numeric = re.search(r"\b([0-3]?\d)/([01]?\d)/((?:20)?\d{2})\b", window)
        month = re.search(month_re, window)
        if numeric and (month is None or numeric.start() < month.start()):
            year = int(numeric.group(3))
            ym = _ym(year if year > 100 else 2000 + year, int(numeric.group(2)))
            if ym:
                return ym
        if month:
            year = re.search(r"\b(20\d{2})\b", window[month.end():])
            if year:
                ym = _ym(int(year.group(1)), MESES[month.group(1)])
                if ym:
                    return ym
    return None


def vigencia_from_text(text: str) -> str | None:
    """
    Vigencia AAAA-MM a partir del texto del cuadro.

    Reconoce "a partir del 1° de septiembre de 2026", "Periodo: OCTUBRE
    2025", "vigencia: 01/09/2026". Se toma la fecha más alta encontrada en
    los primeros 3000 caracteres (el encabezado).
    """
    head = text[:3000].lower()
    found: list[str] = []
    for mes, num in MESES.items():
        for m in re.finditer(rf"{mes}\s+(?:de\s+|del?\s+)?(20\d{{2}})", head):
            found.append(_ym(int(m.group(1)), num) or "")
    for m in re.finditer(r"(?<!\d)([0-3]?\d)/([01]?\d)/(20\d{2})(?!\d)", head):
        found.append(_ym(int(m.group(3)), int(m.group(2))) or "")
    found = [f for f in found if f]
    return max(found) if found else None


# ====================== VALIDACIÓN ======================

def _is_parsed_status(status: str | None) -> bool:
    return status in _PARSED_ALIASES or status == STATUS_FALLBACK


def validate_parsed(
    parsed: dict[str, Any],
    previous: dict[str, Any] | None,
) -> dict[str, str]:
    """
    Valida los valores extraídos. Devuelve el motivo de rechazo por campo.

    Reglas:
        - Inyección < compra (la energía inyectada se remunera a precio
          mayorista, inferior a la tarifa de venta al usuario).
        - Variación respecto del valor previo **extraído** dentro de
          [1/MAX_CHANGE_FACTOR, MAX_CHANGE_FACTOR]. No se compara contra
          valores ``baseline_manual`` (no verificados): un valor real no
          puede rechazarse por diferir de uno inventado.

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
        estados = previous.get("estado_campos", {})
        for field in TARIFF_FIELDS:
            new = parsed.get(field)
            old = previous.get(field)
            if new is None or field in rejected or not old:
                continue
            if not _is_parsed_status(estados.get(field)):
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
    fecha: str,
) -> dict[str, Any]:
    """
    Combina valores extraídos, previos y baseline con trazabilidad por campo.

    Prioridad por campo: valor extraído en esta corrida (si pasa la
    validación) → valor extraído en una corrida previa → ``None``.

    Args:
        code: Código de distribuidora.
        parsed: Documento elegido (``parse_tariff_text`` + metadatos de
            documento) o None si no se pudo extraer.
        previous: Bloque de la corrida previa (None si no existe).
        fecha: Fecha ISO de la corrida.

    Returns:
        Bloque de distribuidora para el JSON de referencia.
    """
    info = DISTRIBUIDORAS[code]
    block: dict[str, Any] = {
        "nombre": info["nombre"],
        "jurisdiccion": info["jurisdiccion"],
        "es_proxy": code in DISTRIBUIDORAS_PROXY,
    }
    estado: dict[str, str] = {}
    rejected = validate_parsed(parsed, previous) if parsed else {}
    prev_estado = (previous or {}).get("estado_campos", {})
    for field in TARIFF_FIELDS:
        new = (parsed or {}).get(field)
        if new is not None and field not in rejected:
            block[field] = new
            estado[field] = STATUS_PARSED
        elif (
            previous is not None
            and previous.get(field) is not None
            and _is_parsed_status(
                prev_estado.get(field, previous.get("parse_status", STATUS_BASELINE))
            )
        ):
            # Valor extraído en una corrida anterior: se conserva como fallback.
            # Los valores ``baseline_manual`` de JSON viejos no se heredan.
            block[field] = previous[field]
            estado[field] = STATUS_FALLBACK
        else:
            block[field] = None
            estado[field] = STATUS_MISSING
    block["estado_campos"] = estado
    states = set(estado.values())
    block["parse_status"] = states.pop() if len(states) == 1 else "mixto"
    if parsed is not None:
        for key in ("documento", "fuente_tipo", "vigencia", "sha256", "seccion_compra"):
            block[key] = parsed.get(key)
        block["fecha_extraccion"] = fecha
        block["valores_detectados"] = {
            "compra": parsed.get("valores_compra_detectados", []),
            "inyeccion": parsed.get("valores_inyeccion_detectados", []),
        }
    elif previous is not None:
        for key in ("documento", "fuente_tipo", "vigencia", "sha256", "fecha_extraccion"):
            if key in previous:
                block[key] = previous[key]
    if rejected:
        block["rechazos_validacion"] = rejected
        logger.warning("[tarifas] %s: valores rechazados %s", code, rejected)
    return block


# ====================== HTTP ======================

# Hosts cuyo HTTPS falla desde redes no argentinas (el servidor corta el
# handshake TLS) pero sirven los mismos archivos por HTTP.
HTTP_ONLY_HOSTS: Final[frozenset[str]] = frozenset({"www.energia.gob.ar", "energia.gob.ar"})
MIN_SECONDS_BETWEEN_REQUESTS: Final[float] = 1.0
RETRY_STATUS: Final[frozenset[int]] = frozenset({403, 429, 503})
RETRY_WAIT_SECONDS: Final[float] = 5.0
# Errores de conexión consecutivos para dar un host por caído.
DEAD_HOST_FAILURES: Final[int] = 2
_last_request_at: dict[str, float] = {}


def normalize_url(url: str) -> str:
    """
    Normaliza enlaces de los portales.

    - Quita el prefijo ``blank:#`` que el portal nacional antepone a
      algunos enlaces.
    - Usa HTTP para ``energia.gob.ar`` (ver ``HTTP_ONLY_HOSTS``).
    """
    url = re.sub(r"^blank:#", "", url.strip())
    parsed = urlparse(url)
    if parsed.scheme == "https" and parsed.netloc in HTTP_ONLY_HOSTS:
        url = "http://" + url[len("https://"):]
    return url


def astro_file_links(html: str) -> list[str]:
    """
    Enlaces de descarga de páginas Astro de EPE Santa Fe.

    El sitio no publica enlaces ``<a href>``: cada archivo viene como
    propiedades serializadas (``"fileName":[0,"CUT_T2_Septiembre_2026.pdf"]``,
    ``"fileHash":[0,"<uuid>"]``) y se descarga con ``GET
    /institucional-api/download/<uuid>``. El nombre se agrega como fragmento
    de la URL para conservar la vigencia (``Mes_AAAA``) y la trazabilidad.
    Sólo se toman los cuadros tarifarios (``CUT_*``).
    """
    text = unescape(html)
    links: list[str] = []
    for name, file_hash in ASTRO_FILE.findall(text):
        if name.upper().startswith("CUT_"):
            url = f"{EPE_DOWNLOAD_BASE}{file_hash}#{name}"
            if url not in links:
                links.append(url)
    return links


def download_bytes(url: str) -> bytes:
    """
    Descarga el contenido binario de una URL.

    Respeta un intervalo mínimo entre pedidos al mismo host y reintenta
    una vez ante 403/429/503 (los portales limitan ráfagas de descargas).

    Raises:
        httpx.HTTPStatusError: Si el servidor responde error HTTP.
        httpx.RequestError: Si falla la comunicación.
    """
    import time

    url = normalize_url(url)
    host = urlparse(url).netloc
    for attempt in range(2):
        wait = MIN_SECONDS_BETWEEN_REQUESTS - (time.monotonic() - _last_request_at.get(host, 0.0))
        if wait > 0:
            time.sleep(wait)
        _last_request_at[host] = time.monotonic()
        try:
            response = httpx.get(
                url,
                headers={**HEADERS, **HOST_HEADERS.get(host, {})},
                follow_redirects=FOLLOW_REDIRECTS,
                timeout=REQUEST_TIMEOUT,
            )
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError):
            if attempt == 0:
                time.sleep(RETRY_WAIT_SECONDS)
                continue
            raise
        if response.status_code in RETRY_STATUS and attempt == 0:
            time.sleep(RETRY_WAIT_SECONDS)
            continue
        response.raise_for_status()
        return response.content
    raise AssertionError("inalcanzable")


def try_download(
    url: str,
    downloader: Callable[[str], bytes] = download_bytes,
) -> bytes | None:
    """Intenta descargar una URL; devuelve None si falla o viene vacía."""
    try:
        content = downloader(url)
    except (httpx.HTTPError, OSError) as exc:
        logger.debug("[tarifas] Falla descarga %s: %s", url, exc)
        return None
    if not content:
        logger.debug("[tarifas] Respuesta vacía: %s", url)
        return None
    return content


def with_dead_host_guard(
    downloader: Callable[[str], bytes],
) -> Callable[[str], bytes]:
    """
    Envuelve un downloader para no reintentar hosts inalcanzables.

    Tras ``DEAD_HOST_FAILURES`` errores de conexión o respuestas 403
    consecutivas (no un 404) el host se marca como caído y las siguientes URLs de ese host
    fallan de inmediato. Evita cientos de timeouts cuando un portal está
    fuera de servicio.
    """
    failures: dict[str, int] = {}
    dead: set[str] = set()

    def guarded(url: str) -> bytes:
        host = urlparse(url).netloc
        if host in dead:
            raise httpx.ConnectError(f"host marcado como caído: {host}")
        try:
            content = downloader(url)
        except httpx.HTTPStatusError as exc:
            # 403 sostenido = bloqueo del sitio (WAF/geo): se trata igual que
            # un host caído. Un 404 es sólo un archivo inexistente.
            if exc.response.status_code != 403:
                failures[host] = 0
                raise
            failures[host] = failures.get(host, 0) + 1
            if failures[host] >= DEAD_HOST_FAILURES:
                dead.add(host)
                logger.warning("[tarifas] Host bloquea las descargas (403): %s", host)
            raise
        except (httpx.ConnectError, httpx.ConnectTimeout):
            failures[host] = failures.get(host, 0) + 1
            if failures[host] >= DEAD_HOST_FAILURES:
                dead.add(host)
                logger.warning(
                    "[tarifas] Host inalcanzable, se omite en esta corrida: %s", host
                )
            raise
        failures[host] = 0
        return content

    return guarded


def is_pdf(content: bytes) -> bool:
    """True si el binario tiene firma PDF (tolera BOM/espacios iniciales)."""
    return PDF_MAGIC in content[:1024]


# ====================== DESCUBRIMIENTO ======================

def _date_score(url: str) -> str:
    """Clave de orden temporal (vigencia del nombre o cadena vacía)."""
    return vigencia_from_name(url) or ""


def discover_document_links(
    html: str,
    base_url: str,
    keywords: tuple[str, ...] = (),
    exclude_keywords: tuple[str, ...] = (),
) -> list[str]:
    """
    Lista enlaces a documentos tarifarios de una página, recientes primero.

    Args:
        html: HTML de la página índice.
        base_url: URL de la página (para resolver enlaces relativos).
        keywords: Si se indican, al menos una debe aparecer en la URL o en
            el texto del enlace (para índices compartidos entre varias
            distribuidoras). Sin keywords se exige "tarif" o "cuadro"
            salvo en el portal nacional (que sólo enlaza cuadros).
        exclude_keywords: Enlaces que mencionan otra distribuidora del
            mismo índice (documentos combinados) se descartan.

    Returns:
        URLs absolutas ordenadas por vigencia embebida descendente.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    national = "argentina.gob.ar" in base_url
    required = keywords or (() if national else ("tarif", "cuadro", "ct_", "ct-"))
    # Enlaces <a> y, además, URLs de documentos embebidas en el HTML
    # (JSON/JS de sitios que arman la lista en el navegador, p.ej. REFSA).
    pairs = [(str(a["href"]), a.get_text(" ", strip=True)) for a in soup.find_all("a", href=True)]
    pairs += [
        (m, "") for m in re.findall(
            r"""["'](https?://[^"'\s]+?\.(?:pdf|xlsx?|zip))["']""", html, flags=re.IGNORECASE
        )
    ]
    links: list[str] = []
    for raw_href, text in pairs:
        href = normalize_url(raw_href)
        lower = href.lower().split("?")[0]
        if not lower.endswith(DOC_EXTENSIONS) and "files.php" not in lower:
            continue
        haystack = (href + " " + text).lower()
        if required and not any(re.search(rf"\b{re.escape(k)}", haystack) for k in required):
            continue
        if any(re.search(rf"\b{re.escape(k)}\b", haystack) for k in exclude_keywords):
            continue
        url = normalize_url(urljoin(base_url, href))
        if url not in links:
            links.append(url)
    return sorted(links, key=_date_score, reverse=True)


# Alias de compatibilidad con la versión anterior.
discover_pdf_links = discover_document_links


def months_back(now: datetime, n: int = MONTHS_BACK) -> list[tuple[int, int]]:
    """Lista (año, mes) desde el mes actual hacia atrás, ``n`` meses."""
    out = []
    y, m = now.year, now.month
    for _ in range(n):
        out.append((y, m))
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    return out


def months_since(start: str, now: datetime) -> list[tuple[int, int]]:
    """Lista (año, mes) desde ``now`` hasta ``start`` (AAAA-MM), descendente."""
    sy, sm = (int(x) for x in start.split("-"))
    n = (now.year - sy) * 12 + (now.month - sm) + 1
    return months_back(now, max(n, 0))


def format_template(template: str, year: int, month: int) -> str:
    """Formatea una plantilla de URL por mes (ver ``distribuidoras``)."""
    mes = MES_NOMBRE[month]
    return template.format(
        year=f"{year:04d}", month=f"{month:02d}", ym=f"{year:04d}-{month:02d}",
        mes=mes, mes_upper=mes.upper(), mes_lower=mes.lower(),
    )


def national_file_urls(code: str, months: list[tuple[int, int]]) -> list[str]:
    """URLs directas del portal nacional para los meses indicados."""
    d = DISTRIBUIDORAS[code]["dir_nacional"]
    if not d:
        return []
    return [
        f"{NATIONAL_FILES_BASE}{d}/{y:04d}_{m:02d}_{d}.{ext}"
        for y, m in months
        for ext in NATIONAL_EXTENSIONS
    ]


def candidate_documents(
    code: str,
    now: datetime,
    downloader: Callable[[str], bytes] = download_bytes,
    raw_dir: Path | None = None,
    months: list[tuple[int, int]] | None = None,
    index_cache: dict[str, bytes | None] | None = None,
) -> dict[str, list[str]]:
    """
    Resuelve los documentos candidatos de una distribuidora por fuente.

    Args:
        code: Código de distribuidora.
        now: Fecha de la corrida.
        downloader: Función de descarga.
        raw_dir: Si se indica, se guarda el HTML de cada índice.
        months: Meses a probar con plantillas (default: últimos 6).
        index_cache: Caché de índices compartidos (OCEBA, EPRE) por corrida.

    Returns:
        ``{"nacional": [...], "propia": [...]}`` con URLs recientes primero.
    """
    info = DISTRIBUIDORAS[code]
    months = months or months_back(now)
    cache = index_cache if index_cache is not None else {}

    def fetch_index(url: str) -> str | None:
        if url not in cache:
            cache[url] = try_download(url, downloader)
            if cache[url] is not None and raw_dir is not None:
                host = urlparse(url).netloc.replace(".", "_")
                save_bytes(
                    cache[url],  # type: ignore[arg-type]
                    raw_dir / "indices" / build_timestamped_filename(host, ".html", now),
                )
        content = cache[url]
        return content.decode("utf-8", "ignore") if content else None

    national: list[str] = []
    for slug in info["slug_nacional"]:
        page = NATIONAL_PAGE_BASE + slug
        html = fetch_index(page)
        if html:
            # El portal a veces enlaza archivos de otra distribuidora (p.ej.
            # la página de EDET apuntaba a un cuadro de EDESE).
            tag = (info["dir_nacional"] or code).lower()
            national.extend(
                u for u in discover_document_links(html, page)
                if tag in urlparse(u).path.lower().rsplit("/", 1)[-1] and u not in national
            )
    national.sort(key=_date_score, reverse=True)
    national.extend(u for u in national_file_urls(code, months) if u not in national)

    own: list[str] = []
    keywords = INDEX_KEYWORDS.get(code, ())
    others = tuple(
        k for c, ks in INDEX_KEYWORDS.items() if c != code and keywords for k in ks
    )
    for index in info["indices"]:
        html = fetch_index(index)
        if html:
            own.extend(u for u in astro_file_links(html) if u not in own)
            own.extend(
                u for u in discover_document_links(html, index, keywords, others)
                if u not in own
            )
    own.extend(u for u in info["urls"] if u not in own)
    for template in info["url_templates"]:
        for y, m in months:
            url = format_template(template, y, m)
            if url not in own:
                own.append(url)
    return {SOURCE_NATIONAL: national, SOURCE_OWN: own}


# ====================== PROCESAMIENTO DE DOCUMENTOS ======================

def process_document(
    code: str,
    url: str,
    content: bytes,
    fuente_tipo: str,
    now: datetime,
    raw_dir: Path | None = None,
    text_extractor: Callable[[bytes, str], list[tuple[str, str]]] = document_to_texts,
) -> dict[str, Any] | None:
    """
    Convierte, parsea y fecha un documento tarifario.

    Si el documento contiene varios archivos (ZIP), se usa el primero con
    tarifa de compra reconocible.

    Returns:
        Diccionario con valores extraídos y metadatos (documento,
        vigencia, sha256, fuente_tipo) o None si no se reconocen tarifas.
    """
    fmt = detect_format(content, url)
    if fmt is None:
        logger.debug("[tarifas] %s: %s no es un documento soportado", code, url)
        return None
    sha = hashlib.sha256(content).hexdigest()
    if raw_dir is not None:
        ext = "pdf" if fmt == "pdf" else fmt
        save_bytes(content, raw_dir / code.lower() / f"{sha[:16]}.{ext}")
    try:
        texts = text_extractor(content, url)
    except Exception as exc:  # documento corrupto / cifrado
        logger.warning("[tarifas] %s: no se pudo leer %s: %s", code, url, exc)
        return None
    best: dict[str, Any] | None = None
    injection: dict[str, Any] | None = None
    for member, text in texts:
        parsed = parse_tariff_text(text)
        # Un ZIP puede traer el precio de inyección en otro archivo
        # ("Tarifas de Inyección de Generación Distribuida").
        if parsed["tarifa_inyeccion_kwh"] is not None and (
            injection is None or parsed.get("documento_inyeccion")
        ):
            injection = parsed
        if parsed["tarifa_compra_kwh"] is None:
            continue
        parsed.update({
            "documento": member or url,
            "fuente_tipo": fuente_tipo,
            "sha256": sha,
            "vigencia": (
                vigencia_explicit(text)
                or vigencia_from_name(url)
                or vigencia_from_name(member or "")
                or vigencia_from_text(text)
            ),
            "fecha_extraccion": now.strftime("%Y-%m-%dT%H:%M:%S"),
        })
        # En un ZIP con varios cuadros (pleno, con subsidio, regímenes
        # especiales) se toma el de mejor categoría y, a igualdad, la
        # tarifa más alta: la plena, sin bonificaciones.
        if best is None or _doc_rank(parsed) > _doc_rank(best):
            best = parsed
    if best is None:
        logger.debug("[tarifas] %s: %s sin cargos $/kWh reconocibles", code, url)
        return None
    if injection is not None and (
        best["tarifa_inyeccion_kwh"] is None or injection.get("documento_inyeccion")
    ):
        best["tarifa_inyeccion_kwh"] = injection["tarifa_inyeccion_kwh"]
        best["valores_inyeccion_detectados"] = injection["valores_inyeccion_detectados"]
        best["lineas_inyeccion"] = injection["lineas_inyeccion"]
    return best


def _doc_rank(parsed: dict[str, Any]) -> tuple[int, float]:
    """Orden de preferencia entre cuadros de una misma vigencia."""
    return (int(parsed.get("puntaje_compra") or 0), float(parsed["tarifa_compra_kwh"]))


def history_record(code: str, parsed: dict[str, Any]) -> dict[str, Any]:
    """Fila del historial a partir de un documento procesado."""
    return {
        "distribuidora": code,
        "vigencia": parsed.get("vigencia"),
        "tarifa_compra_kwh": parsed.get("tarifa_compra_kwh"),
        "tarifa_inyeccion_kwh": parsed.get("tarifa_inyeccion_kwh"),
        "cargo_fijo_mensual": parsed.get("cargo_fijo_mensual"),
        "seccion_compra": parsed.get("seccion_compra"),
        "puntaje_compra": parsed.get("puntaje_compra"),
        "n_valores_compra": len(parsed.get("valores_compra_detectados", [])),
        "n_valores_inyeccion": len(parsed.get("valores_inyeccion_detectados", [])),
        "fuente_tipo": parsed.get("fuente_tipo"),
        "documento": parsed.get("documento"),
        "sha256": parsed.get("sha256"),
        "fecha_extraccion": parsed.get("fecha_extraccion"),
    }


def fetch_distribuidora(
    code: str,
    now: datetime,
    raw_dir: Path | None = None,
    downloader: Callable[[str], bytes] = download_bytes,
    text_extractor: Callable[[bytes, str], list[tuple[str, str]]] = document_to_texts,
    months: list[tuple[int, int]] | None = None,
    max_downloads: int | None = MAX_DOWNLOADS_PER_SOURCE,
    stop_at_first: bool = True,
    index_cache: dict[str, bytes | None] | None = None,
    desde: str | None = None,
    manual_dir: Path | None = None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """
    Descarga y procesa los cuadros de una distribuidora.

    En modo normal (``stop_at_first``) se procesan, por tipo de fuente, los
    documentos de la vigencia más reciente disponible y se elige el de
    mejor categoría y mayor tarifa (cuadro pleno). Entre fuentes gana la
    vigencia más reciente. En modo historial se procesan todos los
    candidatos.

    Returns:
        Tupla (documento vigente elegido o None, lista de documentos
        procesados para el historial).
    """
    cands = candidate_documents(code, now, downloader, raw_dir, months, index_cache)

    def vig(p: dict[str, Any]) -> str:
        # Vigencia desconocida: menor prioridad que cualquier fecha conocida
        # (un documento sin fecha puede ser viejo, p.ej. un índice histórico).
        return p.get("vigencia") or ""

    processed: list[dict[str, Any]] = []
    best_by_source: dict[str, dict[str, Any]] = {}
    seen_sha: set[str] = set()
    # Cuadros cargados a mano (siempre se procesan todos).
    if manual_dir is not None and (manual_dir / code).is_dir():
        for path in sorted((manual_dir / code).iterdir()):
            if not path.is_file() or path.name.startswith("."):
                continue
            parsed = process_document(
                code, path.as_posix(), path.read_bytes(), SOURCE_MANUAL, now, None,
                text_extractor,
            )
            if parsed is None or parsed["sha256"] in seen_sha:
                logger.warning("[tarifas] %s: cuadro manual sin tarifa reconocible: %s",
                               code, path.name)
                continue
            seen_sha.add(parsed["sha256"])
            processed.append(parsed)
            best = best_by_source.get(SOURCE_MANUAL)
            if best is None or (vig(parsed), _doc_rank(parsed)) > (vig(best), _doc_rank(best)):
                best_by_source[SOURCE_MANUAL] = parsed
    for fuente, urls in cands.items():
        downloads = 0
        for url in urls:
            if max_downloads is not None and downloads >= max_downloads:
                break
            # Documentos anteriores al inicio del historial (los índices de
            # OCEBA listan cuadros desde 2020): se omiten sin descargarlos.
            name_vig = vigencia_from_name(url)
            if desde is not None and name_vig is not None and name_vig < desde:
                continue
            best = best_by_source.get(fuente)
            # En modo normal se siguen procesando sólo documentos de la misma
            # vigencia (varios anexos por mes: pleno, con subsidio, ...); los
            # más antiguos no pueden ganar.
            if (stop_at_first and best is not None and name_vig is not None
                    and name_vig < vig(best)):
                break
            content = try_download(url, downloader)
            if content is None:
                continue
            downloads += 1
            parsed = process_document(code, url, content, fuente, now, raw_dir, text_extractor)
            if parsed is None or parsed["sha256"] in seen_sha:
                continue
            seen_sha.add(parsed["sha256"])
            processed.append(parsed)
            if best is None or (vig(parsed), _doc_rank(parsed)) > (vig(best), _doc_rank(best)):
                best_by_source[fuente] = parsed
    if not processed:
        logger.warning("[tarifas] %s: sin cuadro tarifario reconocible", code)
        return None, []
    chosen = max(best_by_source.values(), key=lambda p: (vig(p), _doc_rank(p)))
    logger.info(
        "[tarifas] %s: compra=%s inyección=%s vigencia=%s (%s) %s",
        code, chosen["tarifa_compra_kwh"], chosen["tarifa_inyeccion_kwh"],
        chosen.get("vigencia"), chosen["fuente_tipo"], chosen["documento"],
    )
    return chosen, processed


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
    """
    Carga el JSON de tarifas más reciente, migrando códigos antiguos.

    Returns:
        JSON previo o None si no existe.
    """
    try:
        previous = find_latest_raw(ref_dir, REF_STEM_TARIFAS, suffix=JSON_SUFFIX)
    except FileNotFoundError:
        return None
    with previous.open(encoding="utf-8") as handle:
        data = json.load(handle)
    dist = data.get("distribuidoras", {})
    data["distribuidoras"] = {LEGACY_CODES.get(k, k): v for k, v in dist.items()}
    return data


# ====================== REFERENCIA CONSOLIDADA ======================

def build_reference_payload(
    parsed_by_code: dict[str, dict[str, Any] | None],
    previous: dict[str, Any] | None,
    ts: datetime | None = None,
) -> dict[str, Any]:
    """
    Construye el JSON de referencia consumido por ``energy_finance``.

    Los parámetros operativos PP30 se heredan del JSON previo (pueden
    haber sido ajustados a mano). El mapeo geográfico sale siempre del
    registro ``etl/reference/distribuidoras.py`` (fuente de verdad).

    Args:
        parsed_by_code: Código → documento vigente elegido (o None). Las
            distribuidoras ausentes (corrida con ``--solo``) conservan el
            bloque del JSON previo.
        previous: JSON previo o None.
        ts: Timestamp de la corrida.

    Returns:
        Diccionario listo para serializar.
    """
    now = ts or datetime.now()
    fecha = now.strftime("%Y-%m-%dT%H:%M:%S")
    params = dict(PARAMETROS_PP30_DEFAULT)
    if previous:
        params.update(previous.get("parametros_pp30", {}))
    payload: dict[str, Any] = {
        "descripcion": (
            "Tarifas de energía eléctrica por distribuidora (categorías "
            "T2/T3 y usuario-generador, Ley 27.424) extraídas de los "
            "cuadros tarifarios oficiales."
        ),
        "unidad_moneda": "ARS",
        "unidad_tarifas": "ARS/kWh sin impuestos; cargo fijo en ARS/mes",
        "parametros_pp30": params,
        "provincia_a_distribuidora": PROVINCIA_A_DISTRIBUIDORA,
        "departamento_a_distribuidora": DEPARTAMENTO_A_DISTRIBUIDORA,
        "distribuidoras": {},
    }
    prev_dist = (previous or {}).get("distribuidoras", {})
    for code in DISTRIBUIDORAS:
        if code not in parsed_by_code and code in prev_dist:
            # No procesada en esta corrida (``--solo``): se conserva tal cual.
            payload["distribuidoras"][code] = prev_dist[code]
            continue
        payload["distribuidoras"][code] = merge_distribuidora(
            code, parsed_by_code.get(code), prev_dist.get(code), fecha
        )

    payload["ultima_actualizacion"] = now.strftime("%Y-%m")
    payload["generado_en"] = fecha
    estados = [b["estado_campos"]["tarifa_compra_kwh"] for b in payload["distribuidoras"].values()]
    payload["resumen_extraccion"] = {
        "distribuidoras_totales": len(estados),
        "extraidas_en_esta_corrida": estados.count(STATUS_PARSED),
        "fallback_previous": estados.count(STATUS_FALLBACK),
        "baseline_manual": estados.count(STATUS_BASELINE),
        "sin_dato": estados.count(STATUS_MISSING),
    }
    return payload


# ====================== EJECUCIÓN ======================

def run_extractor(
    raw_dir: Path | str | None = None,
    reference_dir: Path | str | None = None,
    downloader: Callable[[str], bytes] = download_bytes,
    text_extractor: Callable[[bytes, str], list[tuple[str, str]]] = document_to_texts,
    codes: list[str] | None = None,
    historial: bool = False,
    desde: str = BACKFILL_START,
) -> Path:
    """
    Descarga cuadros, extrae tarifas, actualiza el historial y escribe la
    referencia consolidada.

    Nunca falla por una distribuidora caída: en ese caso conserva el
    valor previo y lo marca como ``fallback_previous``.

    Args:
        raw_dir: Destino de documentos e índices (default ``data/raw/tarifas``).
        reference_dir: Destino del JSON y del historial (``data/reference``).
        downloader: Función de descarga (inyectable para tests).
        text_extractor: Función documento → [(nombre, texto)] (inyectable).
        codes: Subconjunto de distribuidoras (default: todas).
        historial: Si True, procesa todos los cuadros mensuales desde
            ``desde`` (backfill del historial).
        desde: Mes inicial AAAA-MM para el backfill.

    Returns:
        Path absoluto del ``AAAAMMDDHHMMSS_tarifas.json`` generado.
    """
    now = datetime.now()
    raw_path = Path(raw_dir) if raw_dir is not None else RAW_TARIFAS_DIR
    ref_path = Path(reference_dir) if reference_dir is not None else REFERENCE_DIR
    raw_path.mkdir(parents=True, exist_ok=True)
    ref_path.mkdir(parents=True, exist_ok=True)

    selected = [LEGACY_CODES.get(c, c) for c in (codes or list(DISTRIBUIDORAS))]
    unknown = sorted(set(selected) - set(DISTRIBUIDORAS))
    if unknown:
        raise ValueError(f"Distribuidoras desconocidas: {unknown}")

    previous = load_previous_reference(ref_path)
    downloader = with_dead_host_guard(downloader)
    months = months_since(desde, now) if historial else months_back(now)
    index_cache: dict[str, bytes | None] = {}
    parsed_by_code: dict[str, dict[str, Any] | None] = {}
    records: list[dict[str, Any]] = []
    for code in selected:
        chosen, processed = fetch_distribuidora(
            code, now, raw_path, downloader, text_extractor,
            months=months,
            max_downloads=None if historial else MAX_DOWNLOADS_PER_SOURCE,
            stop_at_first=not historial,
            index_cache=index_cache,
            desde=desde if historial else None,
            manual_dir=ref_path / MANUAL_DIR_NAME,
        )
        parsed_by_code[code] = chosen
        records.extend(history_record(code, p) for p in processed)

    hist_path, n_new = append_history(records, ref_path)
    payload = build_reference_payload(parsed_by_code, previous, ts=now)
    payload["historial"] = {"archivo": hist_path.name, "filas_nuevas": n_new}

    out_name = build_timestamped_filename(REF_STEM_TARIFAS, suffix=JSON_SUFFIX, ts=now)
    out_path = save_json(payload, ref_path / out_name)
    logger.info(
        "[tarifas] Referencia escrita: %s (%s)",
        out_path,
        payload["resumen_extraccion"],
    )
    return out_path


def main() -> None:
    """Entrypoint CLI."""
    parser = argparse.ArgumentParser(description="Extractor de cuadros tarifarios")
    parser.add_argument("--historial", action="store_true",
                        help="Backfill de todos los cuadros mensuales desde --desde")
    parser.add_argument("--desde", default=BACKFILL_START, help="Mes inicial AAAA-MM")
    parser.add_argument("--solo", nargs="*", default=None,
                        help="Códigos de distribuidora a procesar")
    parser.add_argument("--raw-dir", default=None)
    parser.add_argument("--reference-dir", default=None)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run_extractor(
        raw_dir=args.raw_dir,
        reference_dir=args.reference_dir,
        codes=args.solo,
        historial=args.historial,
        desde=args.desde,
    )


if __name__ == "__main__":
    main()

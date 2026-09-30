"""
Descarga cuadros tarifarios oficiales y actualiza la referencia PP30.

Fuentes documentadas (compra T2/T3 e inyección GD / PEE):

- EPEC (Córdoba): PDFs en
  https://www.epec.com.ar/docs/cuadro-tarifario/
- EPE (Santa Fe): sección Usuarios
  https://www.epe.santafe.gov.ar/institucional/usuarios
- EDEMSA (Mendoza): EPRE / EDEMSA
  https://edemsa.com/segmentacion-tarifaria/
- EDENOR (AMBA): PDFs mensuales
  https://www.edenor.com/files/YYYY-MM/Cuadro-Tarifario.pdf

Limitación conocida: los cuadros son PDF heterogéneos (tablas multi
página, T1/T2/T3, franjas horarias, segmentación). Este extractor
descarga los binarios a ``data/raw/tarifas/`` y escribe un JSON de
referencia consolidado en ``data/reference/`` con el schema que consume
``energy_finance``. Los valores numéricos del JSON se toman del
baseline de referencia del proyecto hasta que exista un parser por
distribuidora; cada corrida versiona el archivo con
``YYYYMMDDHHMMSS_tarifas.json``.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Final

import httpx

from etl.extractors.io_utils import (
    JSON_SUFFIX,
    PDF_SUFFIX,
    REF_STEM_TARIFAS,
    build_timestamped_filename,
    find_latest_raw,
)

# ====================== CONFIGURACIÓN ======================

RAW_TARIFAS_DIR: Final[Path] = Path("./data/raw/tarifas")
REFERENCE_DIR: Final[Path] = Path("./data/reference")

REQUEST_TIMEOUT: Final[float] = 60.0
FOLLOW_REDIRECTS: Final[bool] = True
USER_AGENT: Final[str] = (
    "Mozilla/5.0 (compatible; OPTIMIA-HV-ETL/1.0; +research)"
)
HEADERS: Final[dict[str, str]] = {"User-Agent": USER_AGENT}

# URLs de descarga directa conocidas (pueden rotar mensualmente).
# EDENOR publica bajo /files/YYYY-MM/Cuadro-Tarifario.pdf
EDENOR_PDF_TEMPLATE: Final[str] = (
    "https://www.edenor.com/files/{year_month}/Cuadro-Tarifario.pdf"
)

# Último PDF EPEC indexado públicamente (nombre cambia por publicación).
EPEC_PDF_CANDIDATES: Final[list[str]] = [
    "https://www.epec.com.ar/docs/cuadro-tarifario/"
    "cuadro-tarifario-publicado-290825-aplicacion-010925.pdf",
    "https://www.epec.com.ar/docs/cuadro-tarifario/"
    "cuadro-tarifario-publicado-170125-aplicacion-190125.pdf",
]

# Páginas índice (no siempre ofrecen URL estable al PDF vigente).
EPE_INDEX_URL: Final[str] = (
    "https://www.epe.santafe.gov.ar/institucional/usuarios"
)
EDEMSA_INDEX_URL: Final[str] = "https://edemsa.com/segmentacion-tarifaria/"
EPEC_INDEX_URL: Final[str] = "https://www.epec.com.ar/docs/cuadro-tarifario/"

# Baseline numérico del proyecto (referencia manual / guías PP30 2026-09).
# Se reescribe en cada corrida junto con metadatos de descarga.
BASELINE_TARIFAS: Final[dict[str, Any]] = {
    "descripcion": (
        "Cuadros tarifarios regionales de Argentina para Generacion "
        "Distribuida (Tarifas Comerciales T2/T3)"
    ),
    "unidad_moneda": "ARS",
    "parametros_pp30": {
        "consumo_especifico_kg_kwh": 1.1,
        "humedad_pct_default": 12.0,
        "factor_autoconsumo_default": 0.6,
        "potencia_nominal_kw": 25.0,
    },
    "distribuidoras": {
        "EPEC_CORDOBA": {
            "provincia": "Córdoba",
            "tarifa_compra_kwh": 210.0,
            "tarifa_inyeccion_kwh": 42.0,
            "cargo_fijo_mensual": 12500.0,
            "fuente_url": EPEC_INDEX_URL,
            "parse_status": "baseline_manual",
        },
        "EPE_SANTA_FE": {
            "provincia": "Santa Fe",
            "tarifa_compra_kwh": 175.0,
            "tarifa_inyeccion_kwh": 38.0,
            "cargo_fijo_mensual": 11200.0,
            "fuente_url": EPE_INDEX_URL,
            "parse_status": "baseline_manual",
        },
        "EDEMSA_MENDOZA": {
            "provincia": "Mendoza",
            "tarifa_compra_kwh": 135.0,
            "tarifa_inyeccion_kwh": 33.0,
            "cargo_fijo_mensual": 9800.0,
            "fuente_url": EDEMSA_INDEX_URL,
            "parse_status": "baseline_manual",
        },
        "EDENOR_AMBA": {
            "provincia": "Buenos Aires / AMBA",
            "tarifa_compra_kwh": 85.0,
            "tarifa_inyeccion_kwh": 26.5,
            "cargo_fijo_mensual": 8500.0,
            "fuente_url": "https://www.edenor.com/",
            "parse_status": "baseline_manual",
        },
    },
    "provincia_a_distribuidora": {
        "cordoba": "EPEC_CORDOBA",
        "santa fe": "EPE_SANTA_FE",
        "mendoza": "EDEMSA_MENDOZA",
        "buenos aires": "EDENOR_AMBA",
    },
    "cultivos_biomasa": {
        "maiz": {"pci_kcal_kg": 3900, "consumo_especifico_kg_kwh": 1.1},
        "trigo": {"pci_kcal_kg": 3800, "consumo_especifico_kg_kwh": 1.1},
        "soja": {"pci_kcal_kg": 3700, "consumo_especifico_kg_kwh": 1.1},
        "sorgo": {"pci_kcal_kg": 3850, "consumo_especifico_kg_kwh": 1.1},
    },
}


# ====================== HTTP ======================

def download_bytes(url: str) -> bytes:
    """
    Descarga el contenido binario de una URL.

    Args:
        url: URL del recurso.

    Returns:
        Contenido binario.

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


def try_download(url: str) -> bytes | None:
    """
    Intenta descargar una URL; devuelve None si falla.

    Args:
        url: URL del recurso.

    Returns:
        Contenido binario o None.
    """
    try:
        content = download_bytes(url)
    except (httpx.HTTPError, OSError) as exc:
        print(f"[tarifas] Falla descarga {url}: {exc}")
        return None
    if not content:
        print(f"[tarifas] Respuesta vacía: {url}")
        return None
    return content


# ====================== ALMACENAMIENTO ======================

def save_bytes(content: bytes, output_path: Path) -> Path:
    """
    Persiste contenido binario creando directorios padre si hace falta.

    Args:
        content: Bytes a guardar.
        output_path: Ruta destino.

    Returns:
        Path absoluto del archivo escrito.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(content)
    return output_path.resolve()


def save_json(data: dict[str, Any], output_path: Path) -> Path:
    """
    Persiste un diccionario como JSON UTF-8 indentado.

    Args:
        data: Estructura a serializar.
        output_path: Ruta destino.

    Returns:
        Path absoluto del archivo escrito.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return output_path.resolve()


# ====================== DESCARGA POR DISTRIBUIDORA ======================

def download_edenor_pdf(
    raw_dir: Path,
    ts: datetime | None = None,
) -> Path | None:
    """
    Descarga el cuadro tarifario mensual de EDENOR si está publicado.

    Prueba el mes corriente y el anterior (``YYYY-MM``).

    Args:
        raw_dir: Directorio ``data/raw/tarifas``.
        ts: Timestamp de la corrida.

    Returns:
        Path del PDF guardado o None si ninguna URL respondió.
    """
    now = ts or datetime.now()
    year_months = [
        now.strftime("%Y-%m"),
        (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m"),
    ]
    # dedupe preserving order
    seen: set[str] = set()
    ordered: list[str] = []
    for ym in year_months:
        if ym not in seen:
            seen.add(ym)
            ordered.append(ym)

    for ym in ordered:
        url = EDENOR_PDF_TEMPLATE.format(year_month=ym)
        content = try_download(url)
        if content is None:
            continue
        name = build_timestamped_filename(
            f"edenor_{ym.replace('-', '')}",
            suffix=PDF_SUFFIX,
            ts=now,
        )
        path = save_bytes(content, raw_dir / name)
        print(f"[tarifas] EDENOR PDF: {path} ({len(content)} bytes)")
        return path
    return None


def download_epec_pdf(
    raw_dir: Path,
    ts: datetime | None = None,
) -> Path | None:
    """
    Descarga un PDF candidato de EPEC.

    Args:
        raw_dir: Directorio ``data/raw/tarifas``.
        ts: Timestamp de la corrida.

    Returns:
        Path del PDF guardado o None.
    """
    now = ts or datetime.now()
    for url in EPEC_PDF_CANDIDATES:
        content = try_download(url)
        if content is None:
            continue
        name = build_timestamped_filename("epec", suffix=PDF_SUFFIX, ts=now)
        path = save_bytes(content, raw_dir / name)
        print(f"[tarifas] EPEC PDF: {path} ({len(content)} bytes)")
        return path
    return None


def record_index_pages(raw_dir: Path, ts: datetime | None = None) -> list[Path]:
    """
    Guarda HTML de páginas índice (EPE, EDEMSA, EPEC) para auditoría.

    No parsea tarifas desde el HTML: solo deja evidencia de la corrida
    y facilita completar parsers después.

    Args:
        raw_dir: Directorio ``data/raw/tarifas``.
        ts: Timestamp de la corrida.

    Returns:
        Lista de paths HTML guardados.
    """
    now = ts or datetime.now()
    saved: list[Path] = []
    targets = {
        "epe_index": EPE_INDEX_URL,
        "edemsa_index": EDEMSA_INDEX_URL,
        "epec_index": EPEC_INDEX_URL,
    }
    for stem, url in targets.items():
        content = try_download(url)
        if content is None:
            continue
        name = build_timestamped_filename(stem, suffix=".html", ts=now)
        path = save_bytes(content, raw_dir / name)
        print(f"[tarifas] Índice {stem}: {path}")
        saved.append(path)
    return saved


# ====================== REFERENCIA CONSOLIDADA ======================

def build_reference_payload(
    downloads: dict[str, str | None],
    ts: datetime | None = None,
) -> dict[str, Any]:
    """
    Construye el JSON de referencia consumido por energy_finance.

    Args:
        downloads: Mapa distribuidora/código → path o URL descargada.
        ts: Timestamp de la corrida.

    Returns:
        Diccionario listo para serializar.
    """
    now = ts or datetime.now()
    payload = json.loads(json.dumps(BASELINE_TARIFAS))  # deep copy
    payload["ultima_actualizacion"] = now.strftime("%Y-%m")
    payload["generado_en"] = now.strftime("%Y-%m-%dT%H:%M:%S")
    payload["descargas"] = downloads
    payload["nota"] = (
        "Valores numéricos en baseline_manual hasta implementar parser "
        "por PDF/HTML. Los binarios/HTML de la corrida están en "
        "data/raw/tarifas/."
    )
    return payload


def seed_reference_from_existing(
    reference_dir: Path,
    source: Path | None = None,
) -> Path:
    """
    Escribe un JSON timestamped a partir de un baseline existente.

    Útil para migrar ``config/tarifas.json`` sin re-scrape.

    Args:
        reference_dir: ``data/reference``.
        source: JSON de origen. Si None, usa ``BASELINE_TARIFAS``.

    Returns:
        Path del archivo creado.
    """
    now = datetime.now()
    if source is not None and Path(source).is_file():
        with Path(source).open(encoding="utf-8") as handle:
            data = json.load(handle)
    else:
        data = json.loads(json.dumps(BASELINE_TARIFAS))
    data["ultima_actualizacion"] = now.strftime("%Y-%m")
    data["generado_en"] = now.strftime("%Y-%m-%dT%H:%M:%S")
    name = build_timestamped_filename(
        REF_STEM_TARIFAS, suffix=JSON_SUFFIX, ts=now
    )
    return save_json(data, reference_dir / name)


# ====================== EJECUCIÓN ======================

def run_extractor(
    raw_dir: Path | str | None = None,
    reference_dir: Path | str | None = None,
) -> Path:
    """
    Ejecuta descarga de cuadros y escribe la referencia consolidada.

    Args:
        raw_dir: Destino de PDFs/HTML (default ``data/raw/tarifas``).
        reference_dir: Destino del JSON vigente timestamped
            (default ``data/reference``).

    Returns:
        Path absoluto del ``YYYYMMDDHHMMSS_tarifas.json`` generado.
    """
    now = datetime.now()
    raw_path = Path(raw_dir) if raw_dir is not None else RAW_TARIFAS_DIR
    ref_path = (
        Path(reference_dir) if reference_dir is not None else REFERENCE_DIR
    )
    raw_path.mkdir(parents=True, exist_ok=True)
    ref_path.mkdir(parents=True, exist_ok=True)

    downloads: dict[str, str | None] = {
        "EDENOR_AMBA": None,
        "EPEC_CORDOBA": None,
        "EPE_SANTA_FE": None,
        "EDEMSA_MENDOZA": None,
    }

    edenor = download_edenor_pdf(raw_path, ts=now)
    if edenor is not None:
        downloads["EDENOR_AMBA"] = str(edenor)

    epec = download_epec_pdf(raw_path, ts=now)
    if epec is not None:
        downloads["EPEC_CORDOBA"] = str(epec)

    # EPE / EDEMSA: solo índices HTML (sin URL PDF estable en el extractor).
    record_index_pages(raw_path, ts=now)
    downloads["EPE_SANTA_FE"] = EPE_INDEX_URL
    downloads["EDEMSA_MENDOZA"] = EDEMSA_INDEX_URL

    # Si existe un JSON previo, conservar valores numéricos del más reciente.
    try:
        previous = find_latest_raw(ref_path, REF_STEM_TARIFAS, suffix=JSON_SUFFIX)
        with previous.open(encoding="utf-8") as handle:
            prev_data = json.load(handle)
        payload = build_reference_payload(downloads, ts=now)
        if "distribuidoras" in prev_data:
            for code, block in prev_data["distribuidoras"].items():
                if code in payload["distribuidoras"]:
                    for key in (
                        "tarifa_compra_kwh",
                        "tarifa_inyeccion_kwh",
                        "cargo_fijo_mensual",
                    ):
                        if key in block:
                            payload["distribuidoras"][code][key] = block[key]
        if "parametros_pp30" in prev_data:
            payload["parametros_pp30"] = prev_data["parametros_pp30"]
        if "provincia_a_distribuidora" in prev_data:
            payload["provincia_a_distribuidora"] = prev_data[
                "provincia_a_distribuidora"
            ]
        if "cultivos_biomasa" in prev_data:
            payload["cultivos_biomasa"] = prev_data["cultivos_biomasa"]
    except FileNotFoundError:
        payload = build_reference_payload(downloads, ts=now)

    out_name = build_timestamped_filename(
        REF_STEM_TARIFAS, suffix=JSON_SUFFIX, ts=now
    )
    out_path = save_json(payload, ref_path / out_name)
    print(f"[tarifas] Referencia escrita: {out_path}")
    return out_path


if __name__ == "__main__":
    run_extractor()

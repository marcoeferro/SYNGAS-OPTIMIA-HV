"""
Utilidades de E/S compartidas por los extractors.

Centraliza la generación de nombres de archivo con timestamp y la
resolución del artefacto raw más reciente por patrón. Garantiza un
contrato de nombres uniforme entre extractors y el pipeline de
transformación.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Final

# =============================================================
# Constantes de configuración
# =============================================================
TIMESTAMP_FORMAT: Final[str] = "%Y%m%d%H%M%S"
TIMESTAMP_PATTERN: Final[str] = r"^(\d{14})_"
RAW_STEM_CBA: Final[str] = "datos_bolsa_granos_cba"
RAW_STEM_MAGYP: Final[str] = "datos_estimaciones"
RAW_STEM_NACION: Final[str] = "datos_bolsa_cereales_nacion"
REF_STEM_TARIFAS: Final[str] = "tarifas"
RAW_STEM_TARIFAS_PDF: Final[str] = "cuadro_tarifario"
CSV_SUFFIX: Final[str] = ".csv"
XLSX_SUFFIX: Final[str] = ".xlsx"
JSON_SUFFIX: Final[str] = ".json"
PDF_SUFFIX: Final[str] = ".pdf"


def build_timestamped_filename(
    stem: str,
    suffix: str = CSV_SUFFIX,
    ts: datetime | None = None,
) -> str:
    """
    Construye un nombre de archivo con prefijo temporal.

    Formato: ``YYYYMMDDHHMMSS_<stem><suffix>``.

    Args:
        stem: Nombre base sin extensión (ej. ``datos_bolsa_granos_cba``).
        suffix: Extensión incluyendo el punto (default ``.csv``).
        ts: Timestamp a usar. Si es None, se toma ``datetime.now()``.

    Returns:
        Nombre de archivo con timestamp.
    """
    stamp = (ts or datetime.now()).strftime(TIMESTAMP_FORMAT)
    if not suffix.startswith("."):
        suffix = f".{suffix}"
    return f"{stamp}_{stem}{suffix}"


def find_latest_raw(
    raw_dir: Path | str,
    stem: str,
    suffix: str = CSV_SUFFIX,
) -> Path:
    """
    Resuelve el artefacto raw más reciente para un stem dado.

    Busca archivos ``{YYYYMMDDHHMMSS}_{stem}{suffix}``. Si no hay
    coincidencias con timestamp, intenta el nombre legacy sin prefijo
    (``{stem}{suffix}``) para compatibilidad con extracciones previas.

    Args:
        raw_dir: Directorio de datos crudos.
        stem: Nombre base sin extensión.
        suffix: Extensión incluyendo el punto.

    Returns:
        Path al archivo más reciente.

    Raises:
        FileNotFoundError: Si no existe ningún archivo coincidente.
    """
    raw_dir = Path(raw_dir)
    if not suffix.startswith("."):
        suffix = f".{suffix}"

    pattern = re.compile(
        rf"^(\d{{14}})_{re.escape(stem)}{re.escape(suffix)}$"
    )
    candidates: list[tuple[str, Path]] = []
    if raw_dir.is_dir():
        for path in raw_dir.iterdir():
            if not path.is_file():
                continue
            match = pattern.match(path.name)
            if match:
                candidates.append((match.group(1), path))

    if candidates:
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]

    legacy = raw_dir / f"{stem}{suffix}"
    if legacy.is_file():
        return legacy

    raise FileNotFoundError(
        f"No se encontró artefacto raw para stem='{stem}' "
        f"en {raw_dir.resolve()}"
    )

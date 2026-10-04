"""
Limpieza y estandarización de fuentes primarias (CBA y MAGYP).

Extrae la lógica de lectura + normalización que antes vivía embebida
en el pipeline, dejando funciones puras reutilizables por el entrypoint
y por tests. Cada función recibe un DataFrame o una ruta y devuelve un
DataFrame con columnas canónicas, sin efectos de lado sobre el input.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Final

import pandas as pd

from etl.reference.crop_taxonomy import CROP_TAXONOMY
from etl.transformers.crop_consolidation import resolve_crops
from etl.transformers.geography import flag_invalid_geo, normalize_geo
from etl.transformers.string_utils import clean_str

logger = logging.getLogger(__name__)

# =============================================================
# Constantes de configuración
# =============================================================
CBA_RENAME_MAP: Final[dict[str, str]] = {
    "PROVINCIA": "Provincia",
    "DEPARTAMENTO": "Departamento",
    "CULTIVO": "Cultivo",
    "CAMPAÑA": "Campaña",
}

CBA_DROP_COLUMNS: Final[list[str]] = [
    "RENDIMIENTO GRANO LIMPIO Y SECO",
    "PRODUCCIÓN GRANO LIMPIO Y SECO",
]

# Clave natural en el esquema crudo CBA (antes del rename).
CBA_RAW_KEY: Final[list[str]] = ["PROVINCIA", "DEPARTAMENTO", "CULTIVO", "CAMPAÑA"]

# Columnas numéricas centrales de CBA. Sobre estas (más la clave) se
# detectan las filas replicadas por el producto cartesiano del merge
# outer del extractor (ver ``dedupe_cba_merge_artifacts``).
CBA_CORE_COLUMNS: Final[list[str]] = [
    "SEMBRADAS",
    "COSECHADAS",
    "RENDIMIENTO",
    "PRODUCCIÓN",
]

MAGYP_NUM_COLS: Final[list[str]] = [
    "Sup. Sembrada",
    "Sup. Cosechada",
    "Producción",
    "Rendimiento",
]

GROUP_KEYS: Final[list[str]] = [
    "Campaña",
    "Provincia",
    "Departamento",
    "Cultivo",
]

FUENTE_CBA: Final[str] = "bolsa_cereales_cba"
FUENTE_MAGYP: Final[str] = "magyp_estimaciones"

CANONICAL_COLUMNS: Final[list[str]] = [
    "Provincia",
    "Departamento",
    "Campaña",
    "Cultivo",
    "Superficie (Ha)",
    "Produccion (Tn)",
    "Rendimiento (Tn/Ha)",
    "fuente",
]


def load_cba_raw(path: Path | str) -> pd.DataFrame:
    """
    Lee el CSV crudo de Bolsa de Cereales de Córdoba.

    Args:
        path: Ruta al CSV timestamped o legacy.

    Returns:
        DataFrame sin transformar.
    """
    return pd.read_csv(path)


def load_magyp_raw(path: Path | str) -> pd.DataFrame:
    """
    Lee el CSV crudo de estimaciones agrícolas MAGyP.

    Args:
        path: Ruta al CSV timestamped o legacy.

    Returns:
        DataFrame sin transformar.
    """
    return pd.read_csv(path, encoding="utf-8-sig")


def dedupe_cba_merge_artifacts(df: pd.DataFrame) -> pd.DataFrame:
    """
    Elimina filas CBA replicadas por el merge outer del extractor.

    Las hojas "Rendimiento" y "Producción" del Excel de la BCCBA pueden
    traer más de una fila por clave natural (variantes de "grano limpio
    y seco"). El merge outer por clave genera entonces un producto
    cartesiano: la misma superficie y producción aparecen 2, 4, ...
    veces, y el ``groupby(...).sum()`` posterior las multiplica.

    Se conserva una única fila por (clave natural + columnas núcleo).
    Si tras deduplicar persisten claves repetidas con valores núcleo
    distintos, se registra un warning (son datos reales distintos y no
    se descartan silenciosamente).

    Args:
        df: DataFrame crudo CBA (esquema original, columnas en mayúscula).

    Returns:
        DataFrame sin filas replicadas.
    """
    key = [c for c in CBA_RAW_KEY if c in df.columns]
    core = [c for c in CBA_CORE_COLUMNS if c in df.columns]
    n_before = len(df)
    out = df.drop_duplicates(subset=key + core, keep="first")
    n_removed = n_before - len(out)
    if n_removed:
        logger.warning(
            "CBA: %d filas replicadas por merge cartesiano eliminadas "
            "(evita doble/cuádruple conteo de producción).",
            n_removed,
        )
    residual = out.duplicated(subset=key, keep=False).sum()
    if residual:
        logger.warning(
            "CBA: %d filas comparten clave natural con valores distintos; "
            "se sumarán en la agrupación.",
            residual,
        )
    return out.reset_index(drop=True)


def process_cba(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica limpieza léxica, geográfica y de cultivos a la fuente CBA.

    No agrupa ni estandariza el esquema numérico; eso ocurre en
    ``group_and_standardize``.

    Args:
        df: DataFrame crudo CBA.

    Returns:
        DataFrame normalizado con columnas renombradas.
    """
    out = df.copy()
    drop_cols = [c for c in CBA_DROP_COLUMNS if c in out.columns]
    if drop_cols:
        out = out.drop(columns=drop_cols)
    out = dedupe_cba_merge_artifacts(out)
    # Sólo se descartan filas sin producción o superficie cosechada: un
    # dropna global eliminaría filas útiles por nulos en columnas
    # accesorias.
    required = [c for c in ("COSECHADAS", "PRODUCCIÓN") if c in out.columns]
    out = out.dropna(subset=required)
    out = out.rename(columns=CBA_RENAME_MAP)
    out["Cultivo"] = out["Cultivo"].apply(clean_str)
    out = normalize_geo(out)
    out = flag_invalid_geo(out)
    out = resolve_crops(out, CROP_TAXONOMY)
    if "_dept_valido" in out.columns:
        out = out.drop(columns=["_dept_valido"])
    return out


def process_magyp(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica limpieza léxica, geográfica y de cultivos a la fuente MAGYP.

    Args:
        df: DataFrame crudo MAGYP.

    Returns:
        DataFrame normalizado con columnas numéricas coercidas.
    """
    out = df.copy()
    out["Cultivo"] = out["Cultivo"].apply(clean_str)
    out = normalize_geo(out)
    out = flag_invalid_geo(out)
    out = resolve_crops(out, CROP_TAXONOMY)
    if "_dept_valido" in out.columns:
        out = out.drop(columns=["_dept_valido"])
    for col in MAGYP_NUM_COLS:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def group_and_standardize(df: pd.DataFrame, fuente: str) -> pd.DataFrame:
    """
    Agrupa por clave natural y estandariza el esquema de columnas.

    Args:
        df: DataFrame ya procesado por ``process_cba`` o ``process_magyp``.
        fuente: Identificador de fuente (``bolsa_cereales_cba`` o
            ``magyp_estimaciones``).

    Returns:
        DataFrame con columnas canónicas y columna ``fuente``.
    """
    # ``min_count=1``: si todos los valores del grupo son NaN (p.ej. "SD"
    # = sin dato en MAGYP), el resultado es NaN y no 0. Con el ``sum``
    # por defecto un faltante se convertía en producción cero.
    if fuente == FUENTE_MAGYP:
        grouped = (
            df.groupby(GROUP_KEYS, as_index=False)[["Sup. Cosechada", "Producción"]]
            .sum(min_count=1)
        )
        grouped["Rendimiento (Tn/Ha)"] = (
            grouped["Producción"] / grouped["Sup. Cosechada"]
        )
        grouped = grouped.rename(
            columns={
                "Sup. Cosechada": "Superficie (Ha)",
                "Producción": "Produccion (Tn)",
            }
        )
    elif fuente == FUENTE_CBA:
        grouped = (
            df.groupby(GROUP_KEYS, as_index=False)[["COSECHADAS", "PRODUCCIÓN"]]
            .sum(min_count=1)
        )
        grouped["Rendimiento (Tn/Ha)"] = (
            grouped["PRODUCCIÓN"] / grouped["COSECHADAS"]
        )
        grouped = grouped.rename(
            columns={
                "COSECHADAS": "Superficie (Ha)",
                "PRODUCCIÓN": "Produccion (Tn)",
            }
        )
    else:
        raise ValueError(f"Fuente desconocida: {fuente}")

    # Rendimiento indefinido cuando no hay superficie cosechada.
    grouped["Rendimiento (Tn/Ha)"] = grouped["Rendimiento (Tn/Ha)"].where(
        grouped["Superficie (Ha)"] > 0
    )
    grouped = grouped[CANONICAL_COLUMNS[:-1]].copy()
    grouped["fuente"] = fuente
    return grouped

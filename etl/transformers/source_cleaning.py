"""
Limpieza y estandarización de fuentes primarias (CBA y MAGYP).

Extrae la lógica de lectura + normalización que antes vivía embebida
en el pipeline, dejando funciones puras reutilizables por el entrypoint
y por tests. Cada función recibe un DataFrame o una ruta y devuelve un
DataFrame con columnas canónicas, sin efectos de lado sobre el input.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pandas as pd

from etl.reference.crop_taxonomy import CROP_TAXONOMY
from etl.transformers.crop_consolidation import resolve_crops
from etl.transformers.geography import flag_invalid_geo, normalize_geo
from etl.transformers.string_utils import clean_str

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
    out = out.dropna()
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
    if fuente == FUENTE_MAGYP:
        grouped = (
            df.groupby(GROUP_KEYS, as_index=False)
            .agg({"Sup. Cosechada": "sum", "Producción": "sum"})
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
            df.groupby(GROUP_KEYS, as_index=False)
            .agg({"COSECHADAS": "sum", "PRODUCCIÓN": "sum"})
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

    grouped = grouped[CANONICAL_COLUMNS[:-1]].copy()
    grouped["fuente"] = fuente
    return grouped

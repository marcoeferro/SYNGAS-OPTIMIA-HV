"""
Resolución de coexistencia agregado/componente en la dimensión cultivo.

Algunas fuentes reportan, para una misma clave natural (Campaña,
Provincia, Departamento), un registro agregado ('soja total') junto con
sus componentes ('soja 1ra', 'soja 2da'). Sumar ambos produce doble
conteo. La función resolve_crops aplica prioridad jerárquica:
si existe al menos un agregado en el grupo, se conservan únicamente los
agregados; en caso contrario, se conservan los componentes para que el
groupby posterior los sume.
"""

from __future__ import annotations

import pandas as pd

from etl.reference.crop_taxonomy import CROP_TAXONOMY, CropEntry

# =============================================================
# Constantes de configuración
# =============================================================
DEFAULT_RAW_COL = "Cultivo"
DEFAULT_KEYS: tuple[str, ...] = ("Campaña", "Provincia", "Departamento")
SOURCE_CULTIVO_COL = "_source_cultivo"


def resolve_crops(
    df: pd.DataFrame,
    taxonomy: dict[str, CropEntry] = CROP_TAXONOMY,
    raw_col: str = DEFAULT_RAW_COL,
    keys: tuple[str, ...] = DEFAULT_KEYS,
) -> pd.DataFrame:
    """
    Resuelve coexistencia de agregados y componentes por clave natural.

    Preserva trazabilidad mediante la columna `_source_cultivo`, que
    registra el nombre raw que originó cada registro resuelto.

    Falla con ValueError (fail-fast) si existen valores en raw_col que
    no están en la taxonomía. Esto previene merges accidentales ante
    incorporación de nuevos cultivos en futuras actualizaciones.

    Args:
        df: DataFrame con columna de cultivo raw.
        taxonomy: Diccionario canónico de cultivos.
        raw_col: Nombre de la columna con el nombre raw del cultivo.
        keys: Columnas que definen la clave natural para detección de
              coexistencia agregado-componente.

    Returns:
        DataFrame con cultivos resueltos y columna 'Cultivo' renombrada
        al canónico.

    Raises:
        ValueError: Si algún valor de raw_col no está en taxonomy.
    """
    df = df.copy()

    # --- Validación fail-fast de cobertura taxonómica ---
    unmapped = sorted(set(df[raw_col].unique()) - set(taxonomy.keys()))
    if unmapped:
        raise ValueError(
            f"Cultivos sin mapeo en CROP_TAXONOMY: {unmapped}. "
            "Agregar explícitamente antes de continuar."
        )

    # --- Enriquecimiento con metadata canónica ---
    meta = df[raw_col].map(taxonomy)
    df["_canonical"] = meta.map(lambda x: x["canonical"])
    df["_is_aggregate"] = meta.map(lambda x: x["is_aggregate"])

    # --- Detección de coexistencia por clave natural ---
    gkey = list(keys) + ["_canonical"]
    df["_has_aggregate"] = (
        df.groupby(gkey, dropna=False)["_is_aggregate"].transform("any")
    )

    # --- Regla de prioridad: agregado prevalece sobre componentes ---
    keep_mask = (~df["_has_aggregate"]) | (df["_is_aggregate"])
    resolved = df.loc[keep_mask].copy()

    # --- Trazabilidad y limpieza de columnas auxiliares ---
    resolved[SOURCE_CULTIVO_COL] = resolved[raw_col]
    resolved = resolved.drop(columns=[raw_col, "_is_aggregate", "_has_aggregate"])
    resolved = resolved.rename(columns={"_canonical": "Cultivo"})
    return resolved.reset_index(drop=True)
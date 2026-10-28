"""
Reconciliación multi-fuente con política de mayor producción declarada.

Cuando dos fuentes reportan valores divergentes para la misma clave
natural (Provincia, Departamento, Campaña, Cultivo), prevalece el
registro con mayor producción declarada. Fundamento: la información
productiva declarada ante AFIP (SISA, RG Conjunta MAGyP-AFIP 5236)
tiene carácter de declaración jurada y condiciona el tratamiento
fiscal del productor. En ausencia de validación contra ground truth,
preservar la mayor magnitud reportada minimiza subrepresentación del
potencial de biomasa residual.

Los registros descartados se conservan en un DataFrame de auditoría
para permitir reconstrucción de decisiones.
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)

# =============================================================
# Constantes de configuración
# =============================================================
DEFAULT_KEY: list[str] = ["Provincia", "Departamento", "Campaña", "Cultivo"]
PROD_COL = "Produccion (Tn)"
SUP_COL = "Superficie (Ha)"
FUENTE_COL = "fuente"

VALID_SOURCES: frozenset[str] = frozenset(
    {"magyp_estimaciones", "bolsa_cereales_cba"}
)

# Desempate determinístico cuando ambas fuentes declaran exactamente la
# misma producción: prevalece la fuente oficial (MAGYP). Sin este
# criterio el resultado dependía del orden de concatenación.
SOURCE_PRIORITY: dict[str, int] = {
    "magyp_estimaciones": 0,
    "bolsa_cereales_cba": 1,
}
_PRIORITY_COL = "_prioridad_fuente"


def reconciliar_por_mayor_produccion(
    df: pd.DataFrame,
    key: list[str] | None = None,
    prod_col: str = PROD_COL,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Aplica política de reconciliación por mayor producción declarada.

    Para cada clave natural, si existen múltiples registros (de distintas
    fuentes), conserva el de mayor producción. Los registros descartados
    se retornan en un DataFrame separado para auditoría.

    Args:
        df: DataFrame concatenado con columna 'fuente'.
        key: Columnas que definen la clave natural. Si None, usa
             DEFAULT_KEY.
        prod_col: Columna sobre la cual ordenar.

    Returns:
        Tupla (df_final, df_descartado):
            df_final: DataFrame sin duplicados por clave.
            df_descartado: Registros no seleccionados.
    """
    key = key or DEFAULT_KEY.copy()
    sort_cols = key + [prod_col, _PRIORITY_COL]
    ascending = [True] * len(key) + [False, True]

    # --- Diagnóstico previo ---
    n_original = len(df)
    work = df.copy()
    work[_PRIORITY_COL] = work[FUENTE_COL].map(SOURCE_PRIORITY).fillna(99)

    # --- Ordenamiento: producción descendente (NaN al final) y, ante
    # empate, prioridad de fuente. ``kind="mergesort"`` es estable.
    df_sorted = work.sort_values(
        sort_cols, ascending=ascending, na_position="last", kind="mergesort"
    )
    is_dup = df_sorted.duplicated(subset=key, keep="first")

    # --- Selección del máximo por clave ---
    df_final = (
        df_sorted[~is_dup]
        .drop(columns=[_PRIORITY_COL])
        .reset_index(drop=True)
    )

    # --- Dataset de auditoría: todo lo no seleccionado ---
    df_descartado = (
        df_sorted[is_dup]
        .drop(columns=[_PRIORITY_COL])
        .reset_index(drop=True)
    )

    logger.info(
        "Reconciliación: %d registros originales, %d finales, %d descartados",
        n_original, len(df_final), len(df_descartado),
    )
    return df_final, df_descartado


def coverage_report(df: pd.DataFrame, key: list[str] | None = None) -> pd.DataFrame:
    """
    Reporta cobertura por número de fuentes por clave.

    Args:
        df: DataFrame concatenado con columna 'fuente'.
        key: Columnas de la clave natural.

    Returns:
        DataFrame con conteo de claves por número de fuentes.
    """
    key = key or DEFAULT_KEY.copy()
    return (
        df.groupby(key)[FUENTE_COL]
        .nunique()
        .value_counts()
        .rename_axis("n_fuentes")
        .to_frame("n_celdas")
    )

def compute_discrepancies(
    df: pd.DataFrame,
    key: list[str] | None = None,
    ref_source: str = "bolsa_cereales_cba",
    other_source: str = "magyp_estimaciones",
) -> pd.DataFrame:
    """
    Cuantifica discrepancias entre fuentes en claves cubiertas por ambas.

    Para cada clave con registros de las dos fuentes calcula la
    diferencia relativa ``(otra - ref) / ref`` de superficie y producción.
    Es el artefacto ``discrepancias_cba_vs_magyp.parquet`` (antes se
    persistía vacío).

    Args:
        df: DataFrame concatenado pre-reconciliación con columna ``fuente``.
        key: Clave natural.
        ref_source: Fuente de referencia (denominador).
        other_source: Fuente comparada.

    Returns:
        DataFrame plano con una fila por clave solapada.
    """
    key = key or DEFAULT_KEY.copy()
    both = df[df[FUENTE_COL].isin([ref_source, other_source])]
    pivot = both.pivot_table(
        index=key,
        columns=FUENTE_COL,
        values=[SUP_COL, PROD_COL],
        aggfunc="sum",
    )
    if pivot.empty or ref_source not in pivot.columns.get_level_values(1) \
            or other_source not in pivot.columns.get_level_values(1):
        return pd.DataFrame(columns=key)
    pivot = pivot.dropna(subset=[(PROD_COL, ref_source), (PROD_COL, other_source)])
    out = pd.DataFrame(index=pivot.index)
    for var, short in ((SUP_COL, "superficie"), (PROD_COL, "produccion")):
        ref = pivot[(var, ref_source)]
        oth = pivot[(var, other_source)]
        out[f"{short}_{ref_source}"] = ref
        out[f"{short}_{other_source}"] = oth
        out[f"diff_rel_{short}"] = (oth - ref) / ref.where(ref != 0)
    return out.reset_index()

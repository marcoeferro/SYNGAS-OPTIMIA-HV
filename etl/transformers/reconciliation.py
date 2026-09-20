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
    ascending = [True] * len(key) + [False]

    # --- Diagnóstico previo ---
    n_original = len(df)
    duplicados_mask = df.duplicated(subset=key, keep=False)
    df_duplicados = df[duplicados_mask].copy()

    # --- Ordenamiento por producción descendente ---
    df_sorted = df.sort_values(
        key + [prod_col], ascending=ascending
    ).copy()

    # --- Selección del máximo por clave ---
    df_final = (
        df_sorted
        .drop_duplicates(subset=key, keep="first")
        .reset_index(drop=True)
    )

    # --- Construcción del dataset de auditoría ---
    df_descartado = df_duplicados.sort_values(
        key + [prod_col], ascending=ascending
    ).copy()
    df_descartado["resultado"] = (
        df_descartado.duplicated(subset=key, keep="first")
        .map({True: "descartado", False: "seleccionado"})
    )
    df_descartado = (
        df_descartado[df_descartado["resultado"] == "descartado"]
        .drop(columns=["resultado"])
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
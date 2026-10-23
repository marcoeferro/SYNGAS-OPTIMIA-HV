"""
Invariantes de integridad para las capas intermedias y curadas.

Este módulo agrupa las validaciones post-transformación. Cada función
levanta AssertionError si una invariante se viola, forzando el fallo
temprano del pipeline. Las validaciones son puras y no modifican datos.
"""

from __future__ import annotations

import pandas as pd

import numpy as np

from optimia_hv.biomasa.transformers.reconciliation import (
    DEFAULT_KEY,
    PROD_COL,
    SUP_COL,
    VALID_SOURCES,
)

# =============================================================
# Constantes de configuración
# =============================================================
FUENTE_COL = "fuente"


def validar_reconciliacion(
    df_final: pd.DataFrame,
    df_all: pd.DataFrame,
    key: list[str] | None = None,
) -> None:
    """
    Valida invariantes de la reconciliación multi-fuente.

    Invariantes verificadas:
        1. No hay duplicados por clave natural.
        2. La fuente es un dominio válido.
        3. La cobertura de claves del df_final coincide con df_all.
        4. Superficie y producción son no negativas.
        5. Cada registro final es el máximo de producción de su clave.

    Args:
        df_final: DataFrame reconciliado.
        df_all: DataFrame concatenado pre-reconciliación.
        key: Columnas de la clave natural.

    Raises:
        AssertionError: Si alguna invariante se viola.

    Note:
        Se usa ``raise AssertionError`` explícito en lugar de ``assert``
        para que las validaciones no se desactiven con ``python -O``.
        Los valores faltantes (NaN, "SD" en MAGYP) no violan las
        invariantes de signo.
    """
    key = key or DEFAULT_KEY.copy()

    _check(df_final.duplicated(key).sum() == 0,
           "Invariante rota: duplicados por clave")

    _check(df_final[FUENTE_COL].isin(VALID_SOURCES).all(),
           "Invariante rota: fuente fuera de dominio")

    _check(not (df_final[SUP_COL] < 0).any(),
           "Invariante rota: superficie negativa")

    _check(not (df_final[PROD_COL] < 0).any(),
           "Invariante rota: producción negativa")

    _check(set(map(tuple, df_final[key].values)) == set(
        map(tuple, df_all[key].drop_duplicates().values)
    ), "Invariante rota: cobertura incompleta de claves")

    # --- Verificar selección efectiva del máximo ---
    max_prod = (
        df_all.groupby(key, dropna=False)[PROD_COL]
        .max()
        .reset_index()
        .rename(columns={PROD_COL: "_prod_max"})
    )
    check = df_final.merge(max_prod, on=key, how="left", validate="1:1")
    same = (check[PROD_COL] == check["_prod_max"]) | (
        check[PROD_COL].isna() & check["_prod_max"].isna()
    )
    _check(same.all(), "Invariante rota: no se seleccionó la mayor producción")


def validar_biomasa(df: pd.DataFrame) -> None:
    """
    Valida invariantes del dataset de biomasa.

    Invariantes verificadas:
        1. No hay infinitos en columnas derivadas.
        2. Registros válidos tienen residuo no negativo.
        3. Superficie de registros válidos es estrictamente positiva.

    Args:
        df: DataFrame con biomasa calculada.

    Raises:
        AssertionError: Si alguna invariante se viola.
    """
    residuo_col = "Residuo de Biomasa (Tn)"
    flag_valido = "_valido_biomasa"

    validos = df[df[flag_valido]]

    _check(not validos[residuo_col].isin([np.inf, -np.inf]).any(),
           "Invariante rota: infinitos en residuo")

    _check((validos[residuo_col] >= 0).all(),
           "Invariante rota: residuo negativo en registros válidos")

    _check((validos[SUP_COL] > 0).all(),
           "Invariante rota: superficie no positiva en registros válidos")


def _check(condition: bool, message: str) -> None:
    """Levanta AssertionError si la condición es falsa (inmune a -O)."""
    if not bool(condition):
        raise AssertionError(message)
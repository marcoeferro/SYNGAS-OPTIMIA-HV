"""
Cálculo de biomasa residual agrícola.

Modelo:
    Biomasa Residual = Producción × FR
    FR = (1 - IC) / IC

El cálculo se realiza a nivel de registro individual. La agregación
posterior (por provincia, cultivo, campaña) debe sumar los residuos
individuales, nunca recalcular sobre agregados con un IC único.

Manejo de valores faltantes:
    El missingness en biomasa es estructural: se concentra en cultivos
    sin IC documentado en la tabla de referencia. Se generan flags de
    validez explícitos en lugar de aplicar dropna global, permitiendo
    cuantificar la cobertura del análisis.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# =============================================================
# Constantes de configuración
# =============================================================
CULTIVO_COL = "Cultivo"
PROD_COL = "Produccion (Tn)"
SUP_COL = "Superficie (Ha)"
REND_COL = "Rendimiento (Tn/Ha)"
FR_COL = "FR"
RESIDUO_COL = "Residuo de Biomasa (Tn)"
RESIDUO_HA_COL = "Residuo de Biomasa (Tn/Ha)"
PROD_HA_COL = "Produccion (Tn/Ha)"

FLAG_TIENE_IC = "_tiene_ic"
FLAG_REND_INVALIDO = "_rendimiento_invalido"
FLAG_VALIDO_BIOMASA = "_valido_biomasa"


def compute_biomass(
    df: pd.DataFrame,
    df_ic: pd.DataFrame,
    cultivo_col: str = CULTIVO_COL,
    prod_col: str = PROD_COL,
    fr_col: str = FR_COL,
    residuo_col: str = RESIDUO_COL,
) -> pd.DataFrame:
    """
    Calcula biomasa residual por registro.

    Hace merge con la tabla IC por columna 'Cultivo' (left join),
    preservando registros sin IC con FR=NaN. Reemplaza valores
    infinitos por NaN en columnas derivadas.

    Args:
        df: DataFrame con producción.
        df_ic: DataFrame con columnas Cultivo y FR.
        cultivo_col: Nombre de la columna de cultivo.
        prod_col: Nombre de la columna de producción.
        fr_col: Nombre de la columna de factor de residuo.
        residuo_col: Nombre de la columna de salida.

    Returns:
        DataFrame con columna de residuo de biomasa agregada.
    """
    df = df.copy()
    df = df.merge(
        df_ic[[cultivo_col, fr_col]].drop_duplicates(subset=cultivo_col),
        on=cultivo_col,
        how="left",
    )
    df[residuo_col] = df[prod_col] * df[fr_col]
    df[residuo_col] = df[residuo_col].replace([np.inf, -np.inf], np.nan)
    df[REND_COL] = df[REND_COL].replace([np.inf, -np.inf], np.nan)
    return df


def add_validity_flags(
    df: pd.DataFrame,
    sup_col: str = SUP_COL,
    rend_col: str = REND_COL,
    fr_col: str = FR_COL,
    residuo_col: str = RESIDUO_COL,
) -> pd.DataFrame:
    """
    Agrega flags de validez al dataset de biomasa.

    Flags generados:
        _tiene_ic:          True si el cultivo tiene FR definido.
        _rendimiento_invalido: True si la superficie es <= 0 o el
                            rendimiento es nulo.
        _valido_biomasa:    True si el residuo es finito y no nulo.

    Args:
        df: DataFrame con columnas requeridas.
        sup_col: Columna de superficie.
        rend_col: Columna de rendimiento.
        fr_col: Columna de factor de residuo.
        residuo_col: Columna de residuo de biomasa.

    Returns:
        DataFrame con flags agregados.
    """
    df = df.copy()
    df[FLAG_TIENE_IC] = df[fr_col].notna()
    df[FLAG_REND_INVALIDO] = (
        df[sup_col].le(0) | df[rend_col].isna()
    )
    df[FLAG_VALIDO_BIOMASA] = (
        df[residuo_col].notna()
        & df[residuo_col].apply(
            lambda v: np.isfinite(v) if pd.notna(v) else False
        )
    )
    return df


def add_density_columns(
    df: pd.DataFrame,
    sup_col: str = SUP_COL,
    prod_col: str = PROD_COL,
    residuo_col: str = RESIDUO_COL,
    residuo_ha_col: str = RESIDUO_HA_COL,
    prod_ha_col: str = PROD_HA_COL,
) -> pd.DataFrame:
    """
    Agrega columnas de densidad (por hectárea).

    Args:
        df: DataFrame con columnas requeridas (idealmente ya filtrado
            por _valido_biomasa para evitar división por cero).
        sup_col: Columna de superficie.
        prod_col: Columna de producción.
        residuo_col: Columna de residuo de biomasa.
        residuo_ha_col: Columna de salida para densidad de residuo.
        prod_ha_col: Columna de salida para densidad de producción.

    Returns:
        DataFrame con columnas de densidad agregadas.
    """
    df = df.copy()
    df[residuo_ha_col] = df[residuo_col] / df[sup_col]
    df[prod_ha_col] = df[prod_col] / df[sup_col]
    return df


def report_exclusion_impact(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cuantifica el impacto del filtro por validez de biomasa.

    Args:
        df: DataFrame con flags de validez ya aplicados.

    Returns:
        DataFrame con columnas: n_registros, produccion_total,
        superficie_total, pct_registros, pct_produccion, pct_superficie.
    """
    impacto = (
        df.groupby(FLAG_VALIDO_BIOMASA)
        .agg(
            n_registros=(PROD_COL, "size"),
            produccion_total=(PROD_COL, "sum"),
            superficie_total=(SUP_COL, "sum"),
        )
    )
    impacto["pct_registros"] = (
        impacto["n_registros"] / impacto["n_registros"].sum() * 100
    ).round(2)
    impacto["pct_produccion"] = (
        impacto["produccion_total"] / impacto["produccion_total"].sum() * 100
    ).round(2)
    impacto["pct_superficie"] = (
        impacto["superficie_total"] / impacto["superficie_total"].sum() * 100
    ).round(2)
    return impacto
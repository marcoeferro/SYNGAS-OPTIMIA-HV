"""
Cálculo de biomasa residual agrícola.

Modelo:
    Biomasa Residual (t MS) = Producción × MS × FR
    FR = (1 - IC) / IC
    Residuo Recuperable (t MS) = Biomasa Residual × fracción_recuperable

El IC se define sobre materia seca; la producción se reporta a humedad
comercial (granos) o en fresco (papa, ajo). Sin el factor MS el residuo
quedaba sobreestimado (≈ +15% en granos y ×3–5 en papa/ajo). La
fracción recuperable descuenta el rastrojo que debe quedar en el lote
para cobertura de suelo y balance de materia orgánica.

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
MS_COL = "MS"
RESIDUO_REC_COL = "Residuo Recuperable (Tn)"
DEFAULT_FRACCION_RECUPERABLE = 0.5
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
    ic_cols = [cultivo_col, fr_col] + ([MS_COL] if MS_COL in df_ic.columns else [])
    df = df.merge(
        df_ic[ic_cols].drop_duplicates(subset=cultivo_col),
        on=cultivo_col,
        how="left",
    )
    if MS_COL not in df.columns:
        df[MS_COL] = 1.0
    df[residuo_col] = df[prod_col] * df[MS_COL] * df[fr_col]
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
        _rendimiento_invalido: True si superficie es nula/<=0 o el
                            rendimiento es nulo.
        _valido_biomasa:    True si tiene IC, superficie usable (>0) y
                            residuo finito. Es el criterio de inclusión
                            en el dataset curado.

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
    # Superficie nula o no positiva, o rendimiento nulo → no usable para densidades
    df[FLAG_REND_INVALIDO] = (
        df[sup_col].isna() | df[sup_col].le(0) | df[rend_col].isna()
    )
    residuo = pd.to_numeric(df[residuo_col], errors="coerce")
    residuo_ok = residuo.notna() & np.isfinite(residuo.to_numpy(dtype="float64"))
    # Válido solo si hay IC, superficie usable y residuo finito
    df[FLAG_VALIDO_BIOMASA] = (
        df[FLAG_TIENE_IC] & ~df[FLAG_REND_INVALIDO] & residuo_ok
    )
    return df


def add_recoverable_residue(
    df: pd.DataFrame,
    fraccion_recuperable: float = DEFAULT_FRACCION_RECUPERABLE,
    residuo_col: str = RESIDUO_COL,
    out_col: str = RESIDUO_REC_COL,
) -> pd.DataFrame:
    """
    Calcula el residuo efectivamente recolectable.

    No todo el rastrojo puede retirarse: una parte debe quedar en el
    lote para proteger el suelo de la erosión y sostener la materia
    orgánica. Usar el 100% del residuo teórico sobreestima el potencial
    energético.

    Args:
        df: DataFrame con la columna de residuo total.
        fraccion_recuperable: Fracción ∈ (0, 1] retirable del lote.
        residuo_col: Columna de residuo total (t MS).
        out_col: Columna de salida.

    Returns:
        Copia del DataFrame con la columna de residuo recuperable.
    """
    if not (0.0 < fraccion_recuperable <= 1.0):
        raise ValueError(
            f"fraccion_recuperable debe estar en (0, 1]: {fraccion_recuperable}"
        )
    df = df.copy()
    df[out_col] = df[residuo_col] * fraccion_recuperable
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
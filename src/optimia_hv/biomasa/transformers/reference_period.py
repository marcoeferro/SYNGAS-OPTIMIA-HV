"""
Selección del período de referencia y anualización del potencial.

El dataset curado contiene todas las campañas disponibles (MAGYP desde
1969/70). Sumar residuo, kWh o ARS sobre todas las campañas no tiene
interpretación física ni económica: el potencial energético es un flujo
**anual**. Este módulo:

    1. Detecta campañas incompletas (la campaña en curso suele tener sólo
       una fracción de los registros: cultivos aún no cosechados).
    2. Selecciona las últimas N campañas completas como período de
       referencia.
    3. Anualiza: promedio por campaña de las magnitudes extensivas
       (suma en el período / N). Una clave ausente en una campaña se
       interpreta como "sin producción" y cuenta como 0 en el promedio.
"""

from __future__ import annotations

import logging
from typing import Final

import pandas as pd

logger = logging.getLogger(__name__)

# =============================================================
# Constantes de configuración
# =============================================================
CAMPANA_COL: Final[str] = "Campaña"
DEFAULT_N_CAMPANAS: Final[int] = 5
DEFAULT_MIN_RATIO: Final[float] = 0.8
DEFAULT_WINDOW: Final[int] = 5


def campaign_sort_key(campana: str) -> int:
    """Clave de orden para campañas ``YYYY/YY`` (usa el año inicial)."""
    try:
        return int(str(campana).split("/")[0])
    except ValueError:
        return -1


def detect_incomplete_campaigns(
    df: pd.DataFrame,
    campana_col: str = CAMPANA_COL,
    min_ratio: float = DEFAULT_MIN_RATIO,
    window: int = DEFAULT_WINDOW,
) -> list[str]:
    """
    Detecta campañas recientes con cobertura anormalmente baja.

    Una campaña se considera incompleta si su número de registros es
    menor a ``min_ratio`` × mediana de las ``window`` campañas previas.
    Sólo se evalúan campañas al final de la serie (las incompletas son
    las que todavía se están relevando).

    Args:
        df: DataFrame con columna de campaña.
        campana_col: Columna de campaña.
        min_ratio: Umbral relativo de cobertura.
        window: Ventana de campañas previas para la mediana.

    Returns:
        Lista de campañas incompletas (orden cronológico).
    """
    counts = df[campana_col].value_counts()
    ordered = sorted(counts.index, key=campaign_sort_key)
    incomplete: list[str] = []
    # Recorre desde la más reciente hacia atrás mientras sean incompletas.
    for i in range(len(ordered) - 1, window - 1, -1):
        camp = ordered[i]
        prev = [ordered[j] for j in range(i - window, i)]
        ref = counts[prev].median()
        if counts[camp] < min_ratio * ref:
            incomplete.append(camp)
        else:
            break
    return sorted(incomplete, key=campaign_sort_key)


def select_reference_campaigns(
    df: pd.DataFrame,
    n_campanas: int = DEFAULT_N_CAMPANAS,
    campana_col: str = CAMPANA_COL,
    exclude_incomplete: bool = True,
) -> list[str]:
    """
    Devuelve las últimas ``n_campanas`` campañas completas.

    Args:
        df: DataFrame con columna de campaña.
        n_campanas: Cantidad de campañas del período de referencia.
        campana_col: Columna de campaña.
        exclude_incomplete: Si True excluye campañas en curso.

    Returns:
        Lista de campañas (orden cronológico).
    """
    if n_campanas < 1:
        raise ValueError("n_campanas debe ser >= 1")
    camps = sorted(df[campana_col].dropna().unique(), key=campaign_sort_key)
    if exclude_incomplete:
        incompletas = set(detect_incomplete_campaigns(df, campana_col))
        if incompletas:
            logger.info("Campañas incompletas excluidas: %s", sorted(incompletas))
        camps = [c for c in camps if c not in incompletas]
    return camps[-n_campanas:]


def annualize(
    df: pd.DataFrame,
    campanas: list[str],
    group_cols: list[str],
    value_cols: list[str],
    campana_col: str = CAMPANA_COL,
) -> pd.DataFrame:
    """
    Promedio anual de magnitudes extensivas en el período de referencia.

    ``valor_anual = Σ_{campañas del período} valor / N``. No se usa
    ``mean`` del groupby porque ignoraría las campañas sin registro
    (sesgando hacia arriba a claves que producen sólo algunos años).

    Args:
        df: DataFrame por campaña.
        campanas: Campañas del período de referencia.
        group_cols: Dimensiones de agregación.
        value_cols: Columnas extensivas (t, kWh, ARS, ...).
        campana_col: Columna de campaña.

    Returns:
        DataFrame con una fila por grupo y columnas ``value_cols`` anuales
        más ``n_campanas_con_dato``.
    """
    if not campanas:
        raise ValueError("Lista de campañas vacía")
    n = len(campanas)
    sub = df[df[campana_col].isin(campanas)]
    out = sub.groupby(group_cols, as_index=False, dropna=False)[value_cols].sum(
        min_count=1
    )
    out[value_cols] = out[value_cols] / n
    n_con_dato = (
        sub.groupby(group_cols, dropna=False)[campana_col]
        .nunique()
        .rename("n_campanas_con_dato")
        .reset_index()
    )
    out = out.merge(n_con_dato, on=group_cols, how="left")
    out["periodo_referencia"] = f"{campanas[0]}–{campanas[-1]} (N={n})"
    return out

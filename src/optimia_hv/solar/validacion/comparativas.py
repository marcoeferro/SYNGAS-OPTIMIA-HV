"""Tablas de comparación modelo vs. generación real.

Reemplazan las consultas SQL con ``JOIN`` de los scripts de
``ValidarModelo/``, ``modeloViejo/`` y ``EstimarEnergia/grafico.py``: reciben
las tablas como DataFrames y devuelven la tabla lista para graficar o
calcular métricas (``validacion/metricas.py``).
"""

from __future__ import annotations

from datetime import date
from typing import Final

import pandas as pd

from optimia_hv.solar.configuracion import ParametrosModeloViejo
from optimia_hv.solar.modelos.modelo_viejo import estimar_energia_diaria

INTERVALOS_POR_HORA: Final[int] = 4   # 15 min


def _rango(df: pd.DataFrame, col: str, desde: date | None, hasta: date | None) -> pd.DataFrame:
    fechas = pd.to_datetime(df[col]).dt.date
    mask = pd.Series(True, index=df.index)
    if desde is not None:
        mask &= fechas >= desde
    if hasta is not None:
        mask &= fechas <= hasta
    return df[mask]


def intradia_real_vs_estimada(
    energia_estimada: pd.DataFrame,
    real_intradia: pd.DataFrame,
    desde: date | None = None,
    hasta: date | None = None,
) -> pd.DataFrame:
    """Potencia real vs. estimada cada 15 min (campana diaria, comparativa de 5 días).

    La energía estimada del intervalo (kWh en 15 min) se pasa a potencia
    media: ``kWh × 1000 × 4`` W. Los intervalos sin dato de Growatt quedan
    en 0 W, como en la consulta original (``LEFT JOIN`` + ``COALESCE``).

    Args:
        energia_estimada: ``energia_estimada_15min`` (o ``energia_pronosticada``).
        real_intradia: ``growatt_produccion_intradia``.
        desde: Primer día (inclusive).
        hasta: Último día (inclusive).

    Returns:
        ``fecha_hora``, ``potencia_real_w``, ``potencia_estimada_w``.
    """
    est = _rango(energia_estimada, "fecha_hora", desde, hasta)[
        ["fecha_hora", "energia_estimada_kwh"]
    ].copy()
    est["fecha_hora"] = pd.to_datetime(est["fecha_hora"])
    real = real_intradia[["fecha_hora", "potencia_w"]].copy()
    real["fecha_hora"] = pd.to_datetime(real["fecha_hora"])
    df = est.merge(real, on="fecha_hora", how="left").sort_values("fecha_hora")
    return pd.DataFrame({
        "fecha_hora": df["fecha_hora"],
        "potencia_real_w": df["potencia_w"].fillna(0.0),
        "potencia_estimada_w": df["energia_estimada_kwh"] * 1000 * INTERVALOS_POR_HORA,
    }).reset_index(drop=True)


def pronosticada_vs_real(
    energia_pronosticada: pd.DataFrame,
    real_intradia: pd.DataFrame,
    fecha: date,
) -> pd.DataFrame:
    """Energía pronosticada vs. real de un día (ex ``EstimarEnergia/grafico.py``).

    Sólo los intervalos presentes en las dos tablas. La potencia real (W)
    se pasa a energía del intervalo: ``W × 0,25 h / 1000``.

    Returns:
        ``fecha_hora``, ``energia_estimada_kwh``, ``energia_real_kwh``.
    """
    est = _rango(energia_pronosticada, "fecha_hora", fecha, fecha)[
        ["fecha_hora", "energia_estimada_kwh"]
    ].copy()
    est["fecha_hora"] = pd.to_datetime(est["fecha_hora"])
    real = _rango(real_intradia, "fecha_hora", fecha, fecha)[["fecha_hora", "potencia_w"]].copy()
    real["fecha_hora"] = pd.to_datetime(real["fecha_hora"])
    real["energia_real_kwh"] = real["potencia_w"] / INTERVALOS_POR_HORA / 1000.0
    df = est.merge(real[["fecha_hora", "energia_real_kwh"]], on="fecha_hora", how="inner")
    return df.sort_values("fecha_hora").reset_index(drop=True)


def diaria_real_vs_modelo_viejo(
    clima_diario: pd.DataFrame,
    real_diaria: pd.DataFrame,
    desde: date | None = None,
    hasta: date | None = None,
    params: ParametrosModeloViejo | None = None,
) -> pd.DataFrame:
    """Energía diaria real vs. modelo viejo (ex ``calcularModeloViejo.py`` / ``grafico5dias.py``).

    Args:
        clima_diario: ``clima_historico_openmeteo``.
        real_diaria: ``growatt_produccion`` (``fecha``, ``energia``).
        desde: Primer día (inclusive).
        hasta: Último día (inclusive).
        params: Parámetros del modelo viejo.

    Returns:
        ``fecha``, clima del día, ``energia_real_kwh`` (0 si Growatt no tiene
        el día) y ``energia_estimada_vieja``.
    """
    clima = _rango(clima_diario, "fecha", desde, hasta).copy()
    clima["fecha"] = pd.to_datetime(clima["fecha"]).dt.date
    real = real_diaria[["fecha", "energia"]].copy()
    real["fecha"] = pd.to_datetime(real["fecha"]).dt.date
    df = clima.merge(real, on="fecha", how="left").sort_values("fecha")
    df["energia_real_kwh"] = df.pop("energia").fillna(0.0)
    df["energia_estimada_vieja"] = estimar_energia_diaria(df, params)
    return df.reset_index(drop=True)

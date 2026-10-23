"""Modelo físico de energía fotovoltaica cada 15 minutos.

Unifica ``energia_pronosticada_15min.py`` (sobre el pronóstico) y
``estimacionEnergia15min.py`` (sobre el clima observado, para validar): el
cálculo era idéntico y sólo cambiaba la tabla de entrada. Fórmulas y
justificación: ``docs/02_metodologia/solar/metodologia_solar.md``.

Pasos:

1. Irradiancia efectiva sobre el panel inclinado:
   ``G_ef = G_dir · (1 + 0,18 · sen(β)) + G_dif``.
2. Temperatura de celda (NOCT, con atenuación por viento):
   ``T_c = T + (G / 0,8) · (NOCT − 20) / 800 · e^(−0,05 · v)``.
3. Factores: térmico ``1 + γ (T_c − 25)``, humedad, presión y nubes.
4. PR dinámico = PR_base × factores.
5. Energía del intervalo: ``G_ef · P_pico · η_inv · PR · 0,25 h``.
"""

from __future__ import annotations

from typing import Final

import numpy as np
import pandas as pd

from optimia_hv.solar.configuracion import ParametrosModelo15min

FACTOR_15MIN: Final[float] = 0.25    # 15 min = 0,25 h
VIENTO_DEFECTO: Final[float] = 2.0
NUBES_DEFECTO: Final[float] = 20.0
PRESION_DEFECTO: Final[float] = 1013.25
FRACCION_DIRECTA: Final[float] = 0.7
FRACCION_DIFUSA: Final[float] = 0.3

# Columnas de entrada del modelo (nombres cortos internos).
ENTRADA: Final[list[str]] = [
    "fecha_hora", "temp", "hum", "rad_global", "viento", "nubes", "presion",
    "rad_directa", "rad_difusa",
]
# Columnas de salida (las de las tablas energia_pronosticada y energia_estimada_15min).
SALIDA: Final[list[str]] = [
    "fecha_hora", "fecha", "hora", "temp_c", "humedad_relativa", "velocidad_viento",
    "cobertura_nubes", "presion_hpa", "radiacion_inclinada_kwhm2", "energia_estimada_kwh",
]

# Cómo se llaman las columnas en cada tabla de clima de 15 min.
MAPEO_PRONOSTICO: Final[dict[str, str]] = {
    "temp_c": "temp", "humedad_relativa": "hum", "radiacion_global_wm2": "rad_global",
    "velocidad_viento": "viento", "cobertura_nubes": "nubes", "presion_hpa": "presion",
    "radiacion_directa_wm2": "rad_directa", "radiacion_difusa_wm2": "rad_difusa",
}
MAPEO_HISTORICO: Final[dict[str, str]] = {
    "temperatura": "temp", "humedad_relativa": "hum", "radiacion_solar": "rad_global",
    "velocidad_viento": "viento", "cobertura_nubes": "nubes",
    "presion_superficie": "presion", "radiacion_directa": "rad_directa",
    "radiacion_difusa": "rad_difusa",
}


def ahora() -> pd.Timestamp:
    """Momento actual (función aparte para poder fijarlo en los tests)."""
    return pd.Timestamp.now()


def preparar_entrada(df: pd.DataFrame, mapeo: dict[str, str]) -> pd.DataFrame:
    """Renombra una tabla de clima a las columnas del modelo y completa faltantes.

    Equivale a los ``COALESCE`` de las consultas SQL originales: viento 2 m/s,
    nubes 20 %, presión 1013,25 hPa, directa 70 % y difusa 30 % de la global.

    Args:
        df: ``pronostico_15min_5days`` o ``clima_15min_openmeteo``.
        mapeo: :data:`MAPEO_PRONOSTICO` o :data:`MAPEO_HISTORICO`.
    """
    out = df.rename(columns=mapeo)[ENTRADA].copy()
    out["fecha_hora"] = pd.to_datetime(out["fecha_hora"])
    numericas = [c for c in ENTRADA if c != "fecha_hora"]
    out[numericas] = out[numericas].astype(float)
    out["viento"] = out["viento"].fillna(VIENTO_DEFECTO)
    out["nubes"] = out["nubes"].fillna(NUBES_DEFECTO)
    out["presion"] = out["presion"].fillna(PRESION_DEFECTO)
    out["rad_directa"] = out["rad_directa"].fillna(out["rad_global"] * FRACCION_DIRECTA)
    out["rad_difusa"] = out["rad_difusa"].fillna(out["rad_global"] * FRACCION_DIFUSA)
    return out.sort_values("fecha_hora").reset_index(drop=True)


def estimar_energia_15min(
    df: pd.DataFrame,
    params: ParametrosModelo15min | None = None,
) -> pd.DataFrame:
    """Energía estimada (kWh) en cada intervalo de 15 minutos.

    Args:
        df: Salida de :func:`preparar_entrada` (columnas :data:`ENTRADA`).
        params: Parámetros de la planta; por defecto los de ``config/solar.yaml``.

    Returns:
        DataFrame con las columnas :data:`SALIDA`.
    """
    p = params or ParametrosModelo15min()
    df = df.copy()

    # Las APIs dan W/m²; el modelo trabaja en kW/m².
    rad = ["rad_global", "rad_directa", "rad_difusa"]
    if df["rad_global"].max() > 10:
        df[rad] = df[rad] / 1000.0

    # 1. Irradiancia efectiva sobre el plano inclinado.
    factor_inclinacion = 1.0 + 0.18 * np.sin(np.radians(p.inclinacion_panel))
    df["rad_efectiva"] = df["rad_directa"] * factor_inclinacion + df["rad_difusa"]

    # 2. Temperatura de celda y factor térmico. Se conserva la fórmula original
    # (G en kW/m²): ver la observación 5 de la metodología solar.
    factor_viento = np.exp(-0.05 * df["viento"])
    df["t_cell"] = df["temp"] + ((df["rad_global"] / 0.8) * (p.noct - 20) / 800) * factor_viento
    f_termico = 1 + p.gamma * (df["t_cell"] - 25)

    # 3. Atenuaciones ambientales.
    f_humedad = 1 - 0.002 * (df["hum"] / 100)
    f_presion = 1 + 0.00005 * (df["presion"] - PRESION_DEFECTO)
    f_nubes = 1 - 0.0005 * df["nubes"]

    # 4. Performance ratio dinámico.
    pr = p.pr_base * f_termico * f_humedad * f_presion * f_nubes

    # 5. Energía del intervalo.
    energia = df["rad_efectiva"] * p.potencia_pico_kwp * p.eficiencia_inversor * pr * FACTOR_15MIN
    df["energia_estimada_kwh"] = np.where(df["rad_efectiva"] > 0, energia.round(4), 0.0)

    fh = pd.to_datetime(df["fecha_hora"])
    return pd.DataFrame({
        "fecha_hora": fh,
        "fecha": fh.dt.date,
        "hora": fh.dt.time,
        "temp_c": df["temp"],
        "humedad_relativa": df["hum"],
        "velocidad_viento": df["viento"],
        "cobertura_nubes": df["nubes"],
        "presion_hpa": df["presion"],
        "radiacion_inclinada_kwhm2": df["rad_efectiva"],
        "energia_estimada_kwh": df["energia_estimada_kwh"],
    })[SALIDA]


def energia_pronosticada(
    pronostico: pd.DataFrame,
    desde: pd.Timestamp | None = None,
    params: ParametrosModelo15min | None = None,
) -> pd.DataFrame:
    """Energía sobre el pronóstico de 15 min (ex ``energia_pronosticada_15min.py``).

    Args:
        pronostico: Tabla ``pronostico_15min_5days``. Si tiene varias
            consultas para el mismo intervalo, se usa la más reciente.
        desde: Sólo intervalos desde este momento (por defecto, ahora).
        params: Parámetros del modelo.
    """
    df = pronostico.copy()
    df["fecha_hora"] = pd.to_datetime(df["fecha_hora"])
    if "fecha_consulta" in df.columns:
        df = df.sort_values("fecha_consulta").drop_duplicates("fecha_hora", keep="last")
    limite = ahora() if desde is None else desde
    df = df[df["fecha_hora"] >= limite]
    if df.empty:
        return pd.DataFrame(columns=SALIDA)
    return estimar_energia_15min(preparar_entrada(df, MAPEO_PRONOSTICO), params)


def energia_estimada_historica(
    clima_15min: pd.DataFrame,
    params: ParametrosModelo15min | None = None,
) -> pd.DataFrame:
    """Energía sobre el clima observado de 15 min (ex ``estimacionEnergia15min.py``)."""
    if clima_15min.empty:
        return pd.DataFrame(columns=SALIDA)
    return estimar_energia_15min(preparar_entrada(clima_15min, MAPEO_HISTORICO), params)

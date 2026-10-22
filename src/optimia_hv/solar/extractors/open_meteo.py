"""Clima histórico y pronóstico de Open-Meteo (diario y cada 15 min).

Unifica cinco scripts anteriores; cada función devuelve la tabla que
guardaba el script original, con las mismas columnas:

- :func:`historico_diario` → ``clima_historico_openmeteo``
  (ex ``climaHistorico_openmeteo.py`` y ``climaHistoricoOpenMeteo_diario.py``).
- :func:`pronostico_diario` → ``clima_pronosticado``
  (ex ``pronostico_diario_openMeteo.py``).
- :func:`pronostico_15min` → ``pronostico_15min_5days``
  (ex ``pronostico_15min_5days.py``).
- :func:`historico_15min` → ``clima_15min_openmeteo``
  (ex ``climaHistorico_OP_15min.py``).

La radiación diaria viene en MJ/m² y se guarda en kWh/m² (÷ 3,6), igual
que NASA POWER, para poder compararlas. La de 15 min viene en W/m² y se
guarda así (el modelo la pasa a kW/m²).
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Final

import httpx
import pandas as pd

from optimia_hv.comun.http_retry import request_with_retry

logger = logging.getLogger(__name__)

URL_ARCHIVO: Final[str] = "https://archive-api.open-meteo.com/v1/archive"
URL_PRONOSTICO: Final[str] = "https://api.open-meteo.com/v1/forecast"
TIMEOUT_SECONDS: Final[float] = 30.0
MJ_POR_KWH: Final[float] = 3.6

# Valores por defecto cuando falta una variable de 15 min (mismos que el
# script original y que el modelo, ver modelos/modelo_15min.py).
VIENTO_DEFECTO: Final[float] = 2.0
NUBES_DEFECTO: Final[float] = 20.0
PRESION_DEFECTO: Final[float] = 1013.25
FRACCION_DIRECTA: Final[float] = 0.7
FRACCION_DIFUSA: Final[float] = 0.3

VARIABLES_15MIN_PRONOSTICO: Final[list[str]] = [
    "temperature_2m", "relative_humidity_2m", "surface_pressure", "cloud_cover",
    "wind_speed_10m", "shortwave_radiation", "direct_radiation", "diffuse_radiation",
]
# El script de validación pedía la irradiancia directa NORMAL (DNI), no la
# directa horizontal del pronóstico. Se conserva para no cambiar los
# resultados ya publicados; ver docs/02_metodologia/solar/metodologia_solar.md.
VARIABLES_15MIN_HISTORICO: Final[list[str]] = [
    "temperature_2m", "relative_humidity_2m", "shortwave_radiation", "wind_speed_10m",
    "cloud_cover", "surface_pressure", "direct_normal_irradiance", "diffuse_radiation",
]

COLUMNAS_HISTORICO_DIARIO: Final[list[str]] = [
    "fecha", "temperatura_media", "humedad_relativa", "radiacion_solar",
]
COLUMNAS_PRONOSTICO_DIARIO: Final[list[str]] = [
    "fecha_consulta", "fecha_pronosticada", "temp_predicha",
    "humedad_relativa_predicha", "radiacion_predicha",
]
COLUMNAS_PRONOSTICO_15MIN: Final[list[str]] = [
    "fecha_consulta", "fecha_hora", "temp_c", "humedad_relativa", "velocidad_viento",
    "cobertura_nubes", "presion_hpa", "radiacion_global_wm2", "radiacion_directa_wm2",
    "radiacion_difusa_wm2",
]
COLUMNAS_HISTORICO_15MIN: Final[list[str]] = [
    "fecha_hora", "temperatura", "humedad_relativa", "radiacion_solar", "velocidad_viento",
    "cobertura_nubes", "presion_superficie", "radiacion_directa", "radiacion_difusa",
]


def mj_a_kwh(valor: float | None, decimales: int = 4) -> float | None:
    """MJ/m² → kWh/m² (÷ 3,6); ``None`` si no hay valor."""
    return None if valor is None else round(valor / MJ_POR_KWH, decimales)


# =============================================================
# Parseo (funciones puras, sin red)
# =============================================================
def parsear_historico_diario(res_json: dict[str, Any]) -> pd.DataFrame:
    """Respuesta diaria del archivo histórico → ``clima_historico_openmeteo``.

    Se descartan los días con alguna variable nula.
    """
    d = res_json["daily"]
    filas = []
    for fecha, t, h, r in zip(
        d["time"], d["temperature_2m_mean"], d["relative_humidity_2m_mean"],
        d["shortwave_radiation_sum"], strict=True,
    ):
        if t is None or h is None or r is None:
            continue
        filas.append((date.fromisoformat(fecha), t, h, mj_a_kwh(r, 4)))
    return pd.DataFrame(filas, columns=COLUMNAS_HISTORICO_DIARIO)


def parsear_pronostico_diario(res_json: dict[str, Any], fecha_consulta: date) -> pd.DataFrame:
    """Respuesta diaria del pronóstico → ``clima_pronosticado``."""
    d = res_json["daily"]
    filas = [
        (fecha_consulta, date.fromisoformat(f), t, h, mj_a_kwh(r, 2))
        for f, t, h, r in zip(
            d["time"], d["temperature_2m_max"], d["relative_humidity_2m_max"],
            d["shortwave_radiation_sum"], strict=True,
        )
    ]
    return pd.DataFrame(filas, columns=COLUMNAS_PRONOSTICO_DIARIO)


def parsear_pronostico_15min(res_json: dict[str, Any], fecha_consulta: date) -> pd.DataFrame:
    """Respuesta ``minutely_15`` del pronóstico → ``pronostico_15min_5days``.

    Los nulos se conservan: el modelo les asigna valores por defecto.
    """
    m = res_json["minutely_15"]
    df = pd.DataFrame({
        "fecha_consulta": fecha_consulta,
        "fecha_hora": pd.to_datetime(m["time"]),
        "temp_c": m["temperature_2m"],
        "humedad_relativa": m["relative_humidity_2m"],
        "velocidad_viento": m["wind_speed_10m"],
        "cobertura_nubes": m["cloud_cover"],
        "presion_hpa": m["surface_pressure"],
        "radiacion_global_wm2": m["shortwave_radiation"],
        "radiacion_directa_wm2": m["direct_radiation"],
        "radiacion_difusa_wm2": m["diffuse_radiation"],
    })
    return df[COLUMNAS_PRONOSTICO_15MIN]


def parsear_historico_15min(minutely_15: dict[str, Any]) -> pd.DataFrame:
    """Bloque ``minutely_15`` histórico → ``clima_15min_openmeteo``.

    Descarta los intervalos sin temperatura o humedad y completa los demás
    faltantes con los valores por defecto (radiación global 0; directa y
    difusa 70 % / 30 % de la global).
    """
    def col(nombre: str) -> list[Any]:
        valores = list(minutely_15.get(nombre) or [])
        return valores + [None] * (len(minutely_15["time"]) - len(valores))

    df = pd.DataFrame({
        "fecha_hora": pd.to_datetime(minutely_15["time"]),
        "temperatura": col("temperature_2m"),
        "humedad_relativa": col("relative_humidity_2m"),
        "radiacion_solar": col("shortwave_radiation"),
        "velocidad_viento": col("wind_speed_10m"),
        "cobertura_nubes": col("cloud_cover"),
        "presion_superficie": col("surface_pressure"),
        "radiacion_directa": col("direct_normal_irradiance"),
        "radiacion_difusa": col("diffuse_radiation"),
    })
    df = df.dropna(subset=["temperatura", "humedad_relativa"]).copy()
    numericas = [c for c in COLUMNAS_HISTORICO_15MIN if c != "fecha_hora"]
    df[numericas] = df[numericas].astype(float)
    df["radiacion_solar"] = df["radiacion_solar"].fillna(0.0)
    df["velocidad_viento"] = df["velocidad_viento"].fillna(VIENTO_DEFECTO)
    df["cobertura_nubes"] = df["cobertura_nubes"].fillna(NUBES_DEFECTO)
    df["presion_superficie"] = df["presion_superficie"].fillna(PRESION_DEFECTO)
    df["radiacion_directa"] = df["radiacion_directa"].fillna(
        df["radiacion_solar"] * FRACCION_DIRECTA
    )
    df["radiacion_difusa"] = df["radiacion_difusa"].fillna(
        df["radiacion_solar"] * FRACCION_DIFUSA
    )
    return df[COLUMNAS_HISTORICO_15MIN].reset_index(drop=True)


# =============================================================
# Descargas (red)
# =============================================================
def _get(url: str, params: dict[str, Any], client: httpx.Client | None) -> dict[str, Any]:
    # Un cliente recibido no se cierra: historico_15min lo usa dos veces.
    if client is not None:
        response = request_with_retry(client, "GET", url, params=params)
    else:
        with httpx.Client(timeout=TIMEOUT_SECONDS) as c:
            response = request_with_retry(c, "GET", url, params=params)
    datos: dict[str, Any] = response.json()
    return datos


def historico_diario(
    latitud: float, longitud: float, desde: date, hasta: date, zona_horaria: str,
    client: httpx.Client | None = None,
) -> pd.DataFrame:
    """Clima diario observado (archivo histórico) entre dos fechas."""
    logger.info("Open-Meteo histórico diario: %s a %s", desde, hasta)
    res = _get(URL_ARCHIVO, {
        "latitude": latitud, "longitude": longitud,
        "start_date": desde.isoformat(), "end_date": hasta.isoformat(),
        "daily": "temperature_2m_mean,relative_humidity_2m_mean,shortwave_radiation_sum",
        "timezone": zona_horaria,
    }, client)
    return parsear_historico_diario(res)


def pronostico_diario(
    latitud: float, longitud: float, zona_horaria: str,
    fecha_consulta: date | None = None, client: httpx.Client | None = None,
) -> pd.DataFrame:
    """Pronóstico diario (7 días) de temperatura y humedad máximas y radiación."""
    logger.info("Open-Meteo pronóstico diario")
    res = _get(URL_PRONOSTICO, {
        "latitude": latitud, "longitude": longitud,
        "daily": "temperature_2m_max,relative_humidity_2m_max,shortwave_radiation_sum",
        "timezone": zona_horaria,
    }, client)
    return parsear_pronostico_diario(res, fecha_consulta or date.today())


def pronostico_15min(
    latitud: float, longitud: float, dias: int, zona_horaria: str,
    fecha_consulta: date | None = None, client: httpx.Client | None = None,
) -> pd.DataFrame:
    """Pronóstico cada 15 min para los próximos ``dias`` días."""
    logger.info("Open-Meteo pronóstico 15 min (%d días)", dias)
    res = _get(URL_PRONOSTICO, {
        "latitude": latitud, "longitude": longitud,
        "minutely_15": ",".join(VARIABLES_15MIN_PRONOSTICO),
        "forecast_days": dias,
        "timezone": zona_horaria,
    }, client)
    return parsear_pronostico_15min(res, fecha_consulta or date.today())


def historico_15min(
    latitud: float, longitud: float, desde: date, hasta: date, zona_horaria: str,
    client: httpx.Client | None = None,
) -> pd.DataFrame:
    """Clima cada 15 min entre dos fechas (para validar el modelo).

    Prueba primero el archivo histórico y, si no tiene datos (días muy
    recientes), la API de pronóstico, que también acepta fechas pasadas.

    Raises:
        RuntimeError: Si ninguna de las dos APIs devolvió datos.
    """
    params = {
        "latitude": latitud, "longitude": longitud,
        "start_date": desde.isoformat(), "end_date": hasta.isoformat(),
        "minutely_15": ",".join(VARIABLES_15MIN_HISTORICO),
        "timezone": zona_horaria,
    }
    for url in (URL_ARCHIVO, URL_PRONOSTICO):
        try:
            m15 = _get(url, params, client).get("minutely_15")
        except httpx.HTTPError as exc:
            logger.warning("Open-Meteo 15 min falló en %s: %s", url, exc)
            continue
        if m15 and m15.get("time"):
            logger.info("Open-Meteo 15 min %s a %s desde %s", desde, hasta, url)
            return parsear_historico_15min(m15)
    raise RuntimeError(f"Open-Meteo no devolvió datos de 15 min para {desde} a {hasta}")

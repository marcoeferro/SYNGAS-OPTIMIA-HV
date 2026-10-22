"""Clima diario de NASA POWER (temperatura, humedad y radiación).

Unifica ``climaHistorico_NASA.py`` (carga completa) y
``climaHistoricoNASA_diario.py`` (ventana de los últimos 30 días): es la
misma consulta con otro rango de fechas.

NASA publica la radiación con 4-5 días de atraso y marca los datos que
todavía no tiene con ``-999``. Sólo se guardan los días con las **tres**
variables completas; como la carga diaria revisa los últimos 30 días, el
día se completa apenas aparece la radiación.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Final

import httpx
import pandas as pd

from optimia_hv.comun.http_retry import request_with_retry

logger = logging.getLogger(__name__)

URL: Final[str] = "https://power.larc.nasa.gov/api/temporal/daily/point"
PARAMETROS: Final[str] = "T2M,RH2M,ALLSKY_SFC_SW_DWN"
VALOR_FALTANTE: Final[float] = -900.0   # NASA usa -999 para "sin dato"
TIMEOUT_SECONDS: Final[float] = 60.0
COLUMNAS: Final[list[str]] = [
    "fecha", "temperatura_media", "humedad_relativa", "radiacion_solar",
]


def parsear_respuesta(res_json: dict[str, Any]) -> pd.DataFrame:
    """Convierte la respuesta JSON de NASA POWER en una tabla diaria.

    Args:
        res_json: Respuesta de la API ``temporal/daily/point``.

    Returns:
        DataFrame con ``fecha`` (date), ``temperatura_media`` (°C),
        ``humedad_relativa`` (%) y ``radiacion_solar`` (kWh/m²/día). Los días
        con alguna variable faltante (``-999``) se descartan.
    """
    params = res_json["properties"]["parameter"]
    temp, hum, rad = params["T2M"], params["RH2M"], params["ALLSKY_SFC_SW_DWN"]
    filas = []
    for fecha_str, t in temp.items():
        h, r = hum.get(fecha_str), rad.get(fecha_str)
        if h is None or r is None:
            continue
        if t > VALOR_FALTANTE and h > VALOR_FALTANTE and r > VALOR_FALTANTE:
            filas.append((pd.to_datetime(fecha_str, format="%Y%m%d").date(), t, h, r))
    return pd.DataFrame(filas, columns=COLUMNAS)


def descargar_diario(
    latitud: float,
    longitud: float,
    desde: date,
    hasta: date,
    client: httpx.Client | None = None,
) -> pd.DataFrame:
    """Descarga el clima diario de NASA POWER entre dos fechas (inclusive).

    Args:
        latitud: Latitud de la planta.
        longitud: Longitud de la planta.
        desde: Primer día.
        hasta: Último día.
        client: Cliente HTTP (para tests); si es None se crea uno.

    Returns:
        Ver :func:`parsear_respuesta`.
    """
    params = {
        "parameters": PARAMETROS,
        "community": "RE",
        "longitude": longitud,
        "latitude": latitud,
        "start": desde.strftime("%Y%m%d"),
        "end": hasta.strftime("%Y%m%d"),
        "format": "JSON",
    }
    logger.info("NASA POWER: %s a %s", desde, hasta)
    if client is not None:
        response = request_with_retry(client, "GET", URL, params=params)
    else:
        with httpx.Client(timeout=TIMEOUT_SECONDS) as c:
            response = request_with_retry(c, "GET", URL, params=params)
    return parsear_respuesta(response.json())

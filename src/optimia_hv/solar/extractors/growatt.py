"""Generación real de la planta desde el portal web de Growatt.

Unifica los cuatro scripts anteriores (``growatt_historico.py``,
``growatt_diaria.py``, ``growatt_diaria_15min.py`` y
``growatt_intradia.py``), que repetían el login y la consulta:

- Energía **diaria** (kWh/día): gráfico mensual ``getDevicesMonthChart``.
- Potencia **intradía** (W cada 5 min): gráfico diario ``getDevicesDayChart``;
  se puede quedar con un punto cada 15 min.

Las funciones que transforman la respuesta (``rellenar_huecos``,
``serie_diaria_mes``, ``serie_intradia``) son puras y se testean sin red.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterable, Sequence
from datetime import date, datetime, timedelta
from typing import Any, Final

import httpx
import pandas as pd

from optimia_hv.comun.http_retry import request_with_retry
from optimia_hv.solar.configuracion import CredencialesGrowatt

logger = logging.getLogger(__name__)

BASE_URL: Final[str] = "https://server.growatt.com"
URL_LOGIN: Final[str] = f"{BASE_URL}/login"
URL_MES: Final[str] = f"{BASE_URL}/energy/compare/getDevicesMonthChart"
URL_DIA: Final[str] = f"{BASE_URL}/energy/compare/getDevicesDayChart"
USER_AGENT: Final[str] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
)
TIMEOUT_SECONDS: Final[float] = 15.0
PASO_GROWATT_MIN: Final[int] = 5      # Growatt devuelve la potencia cada 5 min
PAUSA_ENTRE_CONSULTAS_S: Final[float] = 2.0  # cortesía para que no bloquee la cuenta

COLUMNAS_DIARIA: Final[list[str]] = ["fecha", "energia"]
COLUMNAS_INTRADIA: Final[list[str]] = ["fecha_hora", "potencia_w"]


# =============================================================
# Funciones puras (sin red)
# =============================================================
def rellenar_huecos(
    valores: Sequence[float | str | None],
    previo: float = 0.0,
    un_vecino: bool = True,
) -> list[float]:
    """Reemplaza los días en 0 (inversor desconectado) por sus vecinos.

    Si el día anterior y el siguiente tienen energía, se usa el promedio.
    Con ``un_vecino=True`` (carga histórica), si sólo uno tiene energía se
    copia ese valor; con ``False`` (carga diaria) el día queda en 0 y se
    vuelve a intentar al día siguiente, cuando ya exista el valor posterior.

    Args:
        valores: Energía de cada día del mes, en el orden de Growatt.
        previo: Último valor positivo del mes anterior (puente entre meses).
        un_vecino: Si se acepta completar con un solo vecino.

    Returns:
        Lista del mismo largo con los huecos completados donde se pudo.
    """
    serie = [float(v) if v not in (None, "") else 0.0 for v in valores]
    salida = list(serie)
    for i, valor in enumerate(serie):
        if valor != 0.0:
            continue
        anterior = serie[i - 1] if i > 0 else previo
        siguiente = serie[i + 1] if i + 1 < len(serie) else 0.0
        if anterior > 0 and siguiente > 0:
            salida[i] = (anterior + siguiente) / 2
        elif un_vecino and anterior > 0:
            salida[i] = anterior
        elif un_vecino and siguiente > 0:
            salida[i] = siguiente
    return salida


def ultimo_positivo(valores: Iterable[float | str | None], defecto: float = 0.0) -> float:
    """Último valor mayor que 0 de la lista (o ``defecto``)."""
    positivos = [float(v) for v in valores if v not in (None, "") and float(v) > 0]
    return positivos[-1] if positivos else defecto


def serie_diaria_mes(
    mes: str,
    valores: Sequence[float | str | None],
    hasta: date,
    previo: float = 0.0,
    un_vecino: bool = True,
    conservar_ceros: bool = False,
) -> pd.DataFrame:
    """Arma la serie diaria de un mes a partir del gráfico mensual de Growatt.

    Args:
        mes: Mes consultado, ``YYYY-MM``.
        valores: Energía por día (índice 0 = día 1).
        hasta: Último día a incluir (normalmente ayer: hoy está incompleto).
        previo: Último valor positivo del mes anterior.
        un_vecino: Ver :func:`rellenar_huecos`.
        conservar_ceros: Si se devuelven los días que quedaron en 0.

    Returns:
        DataFrame con ``fecha`` (date) y ``energia`` (kWh, 2 decimales).
    """
    completos = rellenar_huecos(valores, previo=previo, un_vecino=un_vecino)
    inicio = date.fromisoformat(f"{mes}-01")
    filas = []
    for i, energia in enumerate(completos):
        dia = inicio + timedelta(days=i)
        if dia.month != inicio.month or dia > hasta:
            break
        if energia > 0 or conservar_ceros:
            filas.append((dia, round(energia, 2)))
    return pd.DataFrame(filas, columns=COLUMNAS_DIARIA)


def serie_intradia(
    fecha: date | str,
    pac: Sequence[float | str | None],
    paso_min: int = 15,
) -> pd.DataFrame:
    """Potencia instantánea de un día, cada ``paso_min`` minutos.

    Args:
        fecha: Día consultado.
        pac: Potencia (W) cada 5 min, desde las 00:00, como la da Growatt.
        paso_min: 5 para guardar todo, 15 para alinear con el modelo.

    Returns:
        DataFrame con ``fecha_hora`` (datetime) y ``potencia_w``.
    """
    if paso_min % PASO_GROWATT_MIN:
        raise ValueError(f"paso_min debe ser múltiplo de {PASO_GROWATT_MIN}")
    dia = date.fromisoformat(fecha) if isinstance(fecha, str) else fecha
    base = datetime.combine(dia, datetime.min.time())
    filas = []
    for i, pot in enumerate(pac):
        minutos = i * PASO_GROWATT_MIN
        if minutos >= 24 * 60:
            break
        if minutos % paso_min:
            continue
        valor = float(pot) if pot not in (None, "") else 0.0
        filas.append((base + timedelta(minutes=minutos), round(valor, 2)))
    return pd.DataFrame(filas, columns=COLUMNAS_INTRADIA)


def _datos_respuesta(res_json: dict[str, Any]) -> dict[str, Any] | None:
    obj = res_json.get("obj") or []
    if not obj:
        return None
    datos = obj[0].get("datas")
    return datos if isinstance(datos, dict) else None


def meses_entre(desde: date, hasta: date) -> list[str]:
    """Meses ``YYYY-MM`` desde el de ``desde`` hasta el de ``hasta`` inclusive."""
    meses = []
    actual = date(desde.year, desde.month, 1)
    while actual <= hasta:
        meses.append(actual.strftime("%Y-%m"))
        actual = date(actual.year + actual.month // 12, actual.month % 12 + 1, 1)
    return meses


# =============================================================
# Cliente (red)
# =============================================================
class ClienteGrowatt:
    """Sesión autenticada contra el portal web de Growatt.

    Se usa como context manager::

        with ClienteGrowatt(CredencialesGrowatt.desde_entorno()) as cliente:
            cliente.energia_mensual("2026-09")
    """

    def __init__(self, credenciales: CredencialesGrowatt, client: httpx.Client | None = None):
        """Prepara el cliente; el login se hace al entrar al ``with``."""
        self.credenciales = credenciales
        self._client = client or httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT_SECONDS,
            follow_redirects=True,
        )

    def __enter__(self) -> ClienteGrowatt:
        """Inicia sesión (las cookies quedan en el cliente)."""
        self.login()
        return self

    def __exit__(self, *exc: object) -> None:
        """Cierra la conexión."""
        self._client.close()

    def login(self) -> None:
        """Abre la sesión en el portal (las cookies quedan en el cliente)."""
        request_with_retry(
            self._client, "POST", URL_LOGIN,
            data={
                "account": self.credenciales.usuario,
                "password": self.credenciales.clave,
                "validateCode": "",
            },
        )

    def _grafico(self, url: str, fecha: str, params: str) -> dict[str, Any] | None:
        plant = self.credenciales.plant_id
        payload = {
            "plantId": plant,
            "date": fecha,
            "jsonData": json.dumps([{"type": "plant", "sn": plant, "params": params}]),
        }
        response = request_with_retry(self._client, "POST", url, data=payload)
        try:
            return _datos_respuesta(response.json())
        except ValueError:
            # Sesión vencida: Growatt devuelve la página de login en HTML.
            logger.warning("Growatt no devolvió JSON para %s (¿sesión vencida?)", fecha)
            return None

    def energia_mensual(self, mes: str) -> list[float | str | None]:
        """Energía diaria (kWh) de un mes ``YYYY-MM``; lista vacía si no hay datos."""
        datos = self._grafico(URL_MES, mes, "energy,autoEnergy")
        return list(datos.get("energy", [])) if datos else []

    def potencia_dia(self, fecha: date | str) -> list[float | str | None]:
        """Potencia (W) cada 5 min de un día; lista vacía si no hay datos."""
        datos = self._grafico(URL_DIA, str(fecha), "pac")
        return list(datos.get("pac", [])) if datos else []


# =============================================================
# Cargas (lo que llama el pipeline)
# =============================================================
def diaria_mes_actual(cliente: ClienteGrowatt, hoy: date | None = None) -> pd.DataFrame:
    """Energía diaria del mes en curso hasta ayer (ex ``growatt_diaria.py``).

    Los días en 0 sin dos vecinos con energía se guardan en 0 y se corrigen
    en la corrida siguiente (cuando ya existe el día posterior).
    """
    hoy = hoy or date.today()
    ayer = hoy - timedelta(days=1)
    # El día 1 no hay días cerrados del mes en curso: se revisa el anterior.
    mes = ayer.strftime("%Y-%m")
    valores = cliente.energia_mensual(mes)
    return serie_diaria_mes(mes, valores, hasta=ayer, un_vecino=False, conservar_ceros=True)


def diaria_historica(
    cliente: ClienteGrowatt,
    desde: date,
    hasta: date | None = None,
    pausa_s: float = PAUSA_ENTRE_CONSULTAS_S,
) -> pd.DataFrame:
    """Energía diaria de todos los meses entre ``desde`` y ayer (ex ``growatt_historico.py``)."""
    hasta = hasta or date.today() - timedelta(days=1)
    partes = []
    previo = 0.0
    for mes in meses_entre(desde, hasta):
        valores = cliente.energia_mensual(mes)
        if valores:
            df = serie_diaria_mes(mes, valores, hasta=hasta, previo=previo)
            partes.append(df[df["fecha"] >= desde])
            previo = ultimo_positivo(valores, defecto=previo)
            logger.info("Growatt %s: %d días", mes, len(df))
        else:
            logger.warning("Growatt %s: sin datos", mes)
        time.sleep(pausa_s)
    if not partes:
        return pd.DataFrame(columns=COLUMNAS_DIARIA)
    return pd.concat(partes, ignore_index=True)


def intradia(
    cliente: ClienteGrowatt,
    fechas: Iterable[date | str],
    paso_min: int = 15,
    pausa_s: float = PAUSA_ENTRE_CONSULTAS_S,
) -> pd.DataFrame:
    """Potencia intradía de varios días (ex ``growatt_diaria_15min.py`` / ``growatt_intradia.py``).

    Args:
        cliente: Sesión de Growatt.
        fechas: Días a descargar.
        paso_min: 15 (alineado con el modelo) o 5 (todo lo que da Growatt).
        pausa_s: Pausa entre días.
    """
    partes = []
    for fecha in fechas:
        pac = cliente.potencia_dia(fecha)
        if pac:
            partes.append(serie_intradia(fecha, pac, paso_min=paso_min))
        else:
            logger.warning("Growatt intradía %s: sin datos", fecha)
        time.sleep(pausa_s)
    if not partes:
        return pd.DataFrame(columns=COLUMNAS_INTRADIA)
    return pd.concat(partes, ignore_index=True)

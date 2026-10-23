"""Tests del parseo de NASA POWER y Open-Meteo con respuestas grabadas."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pytest

from optimia_hv.solar.extractors import nasa_power, open_meteo

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "solar"


def _fixture(nombre: str) -> dict[str, Any]:
    datos: dict[str, Any] = json.loads((FIXTURES / nombre).read_text(encoding="utf-8"))
    return datos


class TestNasaPower:
    def test_descarta_dias_con_alguna_variable_faltante(self) -> None:
        df = nasa_power.parsear_respuesta(_fixture("nasa_power_diario.json"))
        # La respuesta grabada tiene 12 días; sólo 5 con las tres variables.
        assert len(df) == 5
        assert (df[["temperatura_media", "humedad_relativa", "radiacion_solar"]] > -900).all().all()
        assert df["fecha"].iloc[0] == date(2026, 10, 10)

    def test_columnas(self) -> None:
        df = nasa_power.parsear_respuesta(_fixture("nasa_power_diario.json"))
        assert list(df.columns) == nasa_power.COLUMNAS

    def test_descarga_arma_parametros(self) -> None:
        pedido: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            pedido.update(dict(request.url.params))
            return httpx.Response(200, json=_fixture("nasa_power_diario.json"))

        client = httpx.Client(transport=httpx.MockTransport(handler))
        df = nasa_power.descargar_diario(
            -33.6, -65.4, date(2026, 10, 10), date(2026, 10, 21), client
        )
        assert pedido["start"] == "20261010" and pedido["end"] == "20261021"
        assert pedido["parameters"] == "T2M,RH2M,ALLSKY_SFC_SW_DWN"
        assert not df.empty


class TestOpenMeteo:
    def test_mj_a_kwh(self) -> None:
        assert open_meteo.mj_a_kwh(3.6) == 1.0
        assert open_meteo.mj_a_kwh(10.79, 4) == 2.9972
        assert open_meteo.mj_a_kwh(None) is None

    def test_historico_diario_en_kwh(self) -> None:
        df = open_meteo.parsear_historico_diario(_fixture("open_meteo_historico_diario.json"))
        assert list(df.columns) == open_meteo.COLUMNAS_HISTORICO_DIARIO
        assert df["radiacion_solar"].tolist() == [round(4.38 / 3.6, 4), round(10.79 / 3.6, 4)]

    def test_historico_diario_descarta_nulos(self) -> None:
        res = _fixture("open_meteo_historico_diario.json")
        res["daily"]["temperature_2m_mean"][0] = None
        df = open_meteo.parsear_historico_diario(res)
        assert len(df) == 1

    def test_pronostico_diario(self) -> None:
        df = open_meteo.parsear_pronostico_diario(
            _fixture("open_meteo_pronostico_diario.json"), date(2026, 10, 22)
        )
        assert list(df.columns) == open_meteo.COLUMNAS_PRONOSTICO_DIARIO
        assert (df["fecha_consulta"] == date(2026, 10, 22)).all()
        assert df["radiacion_predicha"].iloc[0] == round(19.09 / 3.6, 2)

    def test_pronostico_15min_conserva_nulos(self) -> None:
        df = open_meteo.parsear_pronostico_15min(
            _fixture("open_meteo_pronostico_15min.json"), date(2026, 10, 22)
        )
        assert list(df.columns) == open_meteo.COLUMNAS_PRONOSTICO_15MIN
        assert len(df) == 12
        assert df["velocidad_viento"].isna().sum() == 1

    def test_historico_15min_completa_faltantes(self) -> None:
        m15 = {
            "time": ["2026-09-15T12:00", "2026-09-15T12:15", "2026-09-15T12:30"],
            "temperature_2m": [20.0, None, 21.0],
            "relative_humidity_2m": [40.0, 41.0, 42.0],
            "shortwave_radiation": [800.0, 810.0, None],
            "wind_speed_10m": [None, 3.0, 3.0],
            "cloud_cover": [10.0, 10.0, None],
            "surface_pressure": [None, 950.0, 950.0],
            "direct_normal_irradiance": [None, 600.0, 600.0],
            "diffuse_radiation": [100.0, 100.0, None],
        }
        df = open_meteo.parsear_historico_15min(m15)
        assert len(df) == 2  # el intervalo sin temperatura se descarta
        primera, segunda = df.iloc[0], df.iloc[1]
        assert primera["velocidad_viento"] == 2.0
        assert primera["presion_superficie"] == 1013.25
        assert primera["radiacion_directa"] == pytest.approx(800 * 0.7)
        assert segunda["radiacion_solar"] == 0.0
        assert segunda["cobertura_nubes"] == 20.0
        assert segunda["radiacion_difusa"] == 0.0

    def test_historico_15min_prueba_pronostico_si_archivo_vacio(self) -> None:
        urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            urls.append(request.url.host)
            if "archive" in request.url.host:
                return httpx.Response(200, json={"minutely_15": None})
            return httpx.Response(200, json={"minutely_15": {
                "time": ["2026-09-15T12:00"], "temperature_2m": [20.0],
                "relative_humidity_2m": [40.0], "shortwave_radiation": [500.0],
            }})

        client = httpx.Client(transport=httpx.MockTransport(handler))
        df = open_meteo.historico_15min(
            -33.6, -65.4, date(2026, 9, 15), date(2026, 9, 15), "America/Argentina/San_Luis",
            client,
        )
        assert urls == ["archive-api.open-meteo.com", "api.open-meteo.com"]
        assert len(df) == 1

    def test_historico_15min_sin_datos(self) -> None:
        client = httpx.Client(transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json={})
        ))
        with pytest.raises(RuntimeError):
            open_meteo.historico_15min(
                -33.6, -65.4, date(2026, 9, 15), date(2026, 9, 15), "UTC", client
            )

"""Contrato con las APIs reales de la tesis solar (red; corre en nightly).

Verifica que NASA POWER, Open-Meteo y Growatt sigan respondiendo con las
variables y unidades que usan los extractores. Growatt necesita
``GROWATT_USER``, ``GROWATT_PASSWORD`` y ``GROWATT_PLANT_ID`` (secretos del
repo); sin ellos el test se saltea.
"""

from __future__ import annotations

import os
from datetime import date, timedelta

import pytest

from optimia_hv.solar.configuracion import ConfigSolar, CredencialesGrowatt
from optimia_hv.solar.extractors import growatt, nasa_power, open_meteo

CFG = ConfigSolar()
HOY = date.today()


def test_nasa_power_diario() -> None:
    df = nasa_power.descargar_diario(CFG.latitud, CFG.longitud, HOY - timedelta(days=40),
                                     HOY - timedelta(days=10))
    assert list(df.columns) == nasa_power.COLUMNAS
    assert not df.empty
    assert df["radiacion_solar"].between(0, 15).all()  # kWh/m²/día


def test_open_meteo_historico_diario() -> None:
    df = open_meteo.historico_diario(CFG.latitud, CFG.longitud, HOY - timedelta(days=15),
                                     HOY - timedelta(days=8), CFG.zona_horaria)
    assert len(df) >= 7
    assert df["radiacion_solar"].between(0, 15).all()  # ya convertida a kWh/m²


def test_open_meteo_pronosticos() -> None:
    diario = open_meteo.pronostico_diario(CFG.latitud, CFG.longitud, CFG.zona_horaria)
    m15 = open_meteo.pronostico_15min(CFG.latitud, CFG.longitud, 1, CFG.zona_horaria)
    assert list(diario.columns) == open_meteo.COLUMNAS_PRONOSTICO_DIARIO
    assert len(m15) == 96
    assert m15["radiacion_global_wm2"].max() > 10  # W/m²


def test_open_meteo_historico_15min() -> None:
    dia = HOY - timedelta(days=10)
    df = open_meteo.historico_15min(CFG.latitud, CFG.longitud, dia, dia, CFG.zona_horaria)
    assert len(df) == 96


@pytest.mark.skipif(
    not all(os.environ.get(v) for v in ("GROWATT_USER", "GROWATT_PASSWORD", "GROWATT_PLANT_ID")),
    reason="sin credenciales de Growatt",
)
def test_growatt() -> None:
    ayer = HOY - timedelta(days=1)
    with growatt.ClienteGrowatt(CredencialesGrowatt.desde_entorno()) as cliente:
        mes = cliente.energia_mensual(ayer.strftime("%Y-%m"))
        pac = cliente.potencia_dia(ayer)
    assert len(mes) >= ayer.day
    assert len(pac) >= 24 * 60 // growatt.PASO_GROWATT_MIN

"""Tests de los modelos de energía (15 min y viejo)."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from optimia_hv.solar.configuracion import ParametrosModelo15min, ParametrosModeloViejo
from optimia_hv.solar.modelos import modelo_15min, modelo_viejo


def _entrada(**valores: float) -> pd.DataFrame:
    base = {
        "fecha_hora": pd.Timestamp("2026-09-15 12:00"),
        "temp": 25.0, "hum": 0.0, "rad_global": 1000.0, "viento": 0.0, "nubes": 0.0,
        "presion": 1013.25, "rad_directa": 700.0, "rad_difusa": 300.0,
    }
    base.update(valores)
    return pd.DataFrame([base])


def test_calculo_a_mano() -> None:
    """Un intervalo calculado a mano con las fórmulas de la metodología."""
    p = ParametrosModelo15min()
    out = modelo_15min.estimar_energia_15min(_entrada())
    g_ef = 0.7 * (1 + 0.18 * math.sin(math.radians(35))) + 0.3
    t_cell = 25 + (1.0 / 0.8) * (45 - 20) / 800
    pr = 0.78 * (1 - 0.0035 * (t_cell - 25))
    esperado = round(g_ef * 2.25 * 0.93 * pr * 0.25, 4)
    assert out["energia_estimada_kwh"].iloc[0] == pytest.approx(esperado)
    assert out["radiacion_inclinada_kwhm2"].iloc[0] == pytest.approx(g_ef)
    assert p.potencia_pico_kwp == 2.25


def test_noche_da_cero() -> None:
    out = modelo_15min.estimar_energia_15min(
        _entrada(rad_global=0.0, rad_directa=0.0, rad_difusa=0.0)
    )
    assert out["energia_estimada_kwh"].iloc[0] == 0.0


def test_calor_y_nubes_bajan_la_energia() -> None:
    base = modelo_15min.estimar_energia_15min(_entrada())["energia_estimada_kwh"].iloc[0]
    caliente = modelo_15min.estimar_energia_15min(_entrada(temp=40.0))
    nublado = modelo_15min.estimar_energia_15min(_entrada(nubes=100.0))
    assert caliente["energia_estimada_kwh"].iloc[0] < base
    assert nublado["energia_estimada_kwh"].iloc[0] < base


def test_acepta_kw_por_m2() -> None:
    w = modelo_15min.estimar_energia_15min(_entrada())
    kw = modelo_15min.estimar_energia_15min(
        _entrada(rad_global=1.0, rad_directa=0.7, rad_difusa=0.3)
    )
    assert w["energia_estimada_kwh"].iloc[0] == kw["energia_estimada_kwh"].iloc[0]


def test_columnas_de_salida() -> None:
    out = modelo_15min.estimar_energia_15min(_entrada())
    assert list(out.columns) == modelo_15min.SALIDA
    assert str(out["fecha"].iloc[0]) == "2026-09-15"
    assert str(out["hora"].iloc[0]) == "12:00:00"


def test_preparar_entrada_completa_faltantes() -> None:
    df = pd.DataFrame({
        "fecha_hora": ["2026-09-15 12:00"], "temp_c": [20.0], "humedad_relativa": [50.0],
        "radiacion_global_wm2": [500.0], "velocidad_viento": [None], "cobertura_nubes": [None],
        "presion_hpa": [None], "radiacion_directa_wm2": [None], "radiacion_difusa_wm2": [None],
    })
    out = modelo_15min.preparar_entrada(df, modelo_15min.MAPEO_PRONOSTICO)
    fila = out.iloc[0]
    assert (fila["viento"], fila["nubes"], fila["presion"]) == (2.0, 20.0, 1013.25)
    assert fila["rad_directa"] == pytest.approx(350.0)
    assert fila["rad_difusa"] == pytest.approx(150.0)


def test_energia_pronosticada_usa_la_consulta_mas_reciente() -> None:
    fila = {
        "fecha_hora": pd.Timestamp("2026-10-23 12:00"), "temp_c": 20.0,
        "humedad_relativa": 50.0, "velocidad_viento": 2.0, "cobertura_nubes": 0.0,
        "presion_hpa": 1013.25, "radiacion_directa_wm2": 0.0, "radiacion_difusa_wm2": 0.0,
    }
    df = pd.DataFrame([
        {**fila, "fecha_consulta": "2026-10-21", "radiacion_global_wm2": 0.0},
        {**fila, "fecha_consulta": "2026-10-22", "radiacion_global_wm2": 900.0,
         "radiacion_directa_wm2": 600.0, "radiacion_difusa_wm2": 300.0},
    ])
    out = modelo_15min.energia_pronosticada(df, desde=pd.Timestamp("2026-10-22"))
    assert len(out) == 1
    assert out["energia_estimada_kwh"].iloc[0] > 0


def test_energia_pronosticada_filtra_el_pasado() -> None:
    df = pd.DataFrame({
        "fecha_hora": ["2026-10-20 12:00"], "temp_c": [20.0], "humedad_relativa": [50.0],
        "radiacion_global_wm2": [500.0], "velocidad_viento": [2.0], "cobertura_nubes": [0.0],
        "presion_hpa": [1013.0], "radiacion_directa_wm2": [300.0],
        "radiacion_difusa_wm2": [200.0],
    })
    out = modelo_15min.energia_pronosticada(df, desde=pd.Timestamp("2026-10-22"))
    assert out.empty and list(out.columns) == modelo_15min.SALIDA


def test_modelo_viejo_a_mano() -> None:
    clima = pd.DataFrame({
        "temperatura_media": [25.0, 15.0], "humedad_relativa": [0.0, 50.0],
        "radiacion_solar": [5.0, 4.0],
    })
    out = modelo_viejo.estimar_energia_diaria(clima)
    assert out.iloc[0] == pytest.approx(5 * 2.25 * 0.93 * 0.88)
    f = (1 - 0.0035 * (15 - 25)) * (1 - 0.002 * 0.5)
    assert out.iloc[1] == pytest.approx(4 * 2.25 * 0.93 * 0.88 * f)
    assert out.name == "energia_estimada_vieja"


def test_modelo_viejo_nunca_negativo() -> None:
    clima = pd.DataFrame({
        "temperatura_media": [500.0], "humedad_relativa": [0.0], "radiacion_solar": [5.0],
    })
    out = modelo_viejo.estimar_energia_diaria(clima, ParametrosModeloViejo())
    assert out.iloc[0] == 0.0
    assert not np.isnan(out.iloc[0])

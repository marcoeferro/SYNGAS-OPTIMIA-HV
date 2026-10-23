"""Regresión del modelo solar: los resultados sobre datos fijos no cambian sin querer.

Los valores esperados se calcularon con los modelos tal como estaban en
``EstimarEnergia/energia_pronosticada_15min.py`` y
``modeloViejo/calcularModeloViejo.py`` (mismas fórmulas y parámetros) sobre
las respuestas grabadas en ``tests/fixtures/solar/``. Si un cambio en el
modelo es intencional, actualizar estos números en el mismo PR y explicarlo.

Pendiente (fase 0 de la propuesta): acordar umbrales de error contra la
generación real (p. ej. MAE diario máximo) y agregar aquí un dataset fijo
de Growatt para controlarlos.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from optimia_hv.solar.extractors import open_meteo
from optimia_hv.solar.modelos import modelo_15min, modelo_viejo

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "solar"

ENERGIA_15MIN_ESPERADA = [
    0.1273, 0.1494, 0.1748, 0.18, 0.1797, 0.1729,
    0.1681, 0.1724, 0.1881, 0.2073, 0.2224, 0.2243,
]
ENERGIA_DIARIA_VIEJA_ESPERADA = [2.4077, 5.8866]


def _json(nombre: str) -> dict:
    return json.loads((FIXTURES / nombre).read_text(encoding="utf-8"))


def test_modelo_15min_sobre_pronostico_grabado() -> None:
    pron = open_meteo.parsear_pronostico_15min(
        _json("open_meteo_pronostico_15min.json"), date(2026, 10, 22)
    )
    out = modelo_15min.energia_pronosticada(pron, desde=pd.Timestamp("2026-10-22"))
    assert out["energia_estimada_kwh"].tolist() == pytest.approx(ENERGIA_15MIN_ESPERADA, abs=1e-4)


def test_modelo_viejo_sobre_clima_grabado() -> None:
    clima = open_meteo.parsear_historico_diario(_json("open_meteo_historico_diario.json"))
    out = modelo_viejo.estimar_energia_diaria(clima)
    assert out.tolist() == pytest.approx(ENERGIA_DIARIA_VIEJA_ESPERADA, abs=1e-4)

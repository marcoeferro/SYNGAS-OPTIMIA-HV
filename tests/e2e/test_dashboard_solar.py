"""Humo de las páginas solares: renderizan con y sin datos del pipeline solar."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

from optimia_hv.dashboard import data_loader as dl  # noqa: E402
from optimia_hv.solar.loaders import almacen  # noqa: E402

APP = Path(__file__).resolve().parents[2] / "src" / "optimia_hv" / "dashboard" / "app.py"
PAGINAS = ["solar/generacion.py", "solar/pronostico.py", "solar/validacion.py"]


def _correr(pagina: str) -> AppTest:
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.run()
    at.switch_page(str(Path("vistas") / pagina))
    at.run()
    return at


@pytest.mark.parametrize("pagina", PAGINAS)
def test_pagina_solar_sin_datos(
    pagina: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(dl, "SOLAR_DIR", tmp_path)
    at = _correr(pagina)
    assert not at.exception, [e.message for e in at.exception]


@pytest.mark.parametrize("pagina", PAGINAS)
def test_pagina_solar_con_datos(
    pagina: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    horas = pd.date_range("2026-09-15 06:00", periods=48, freq="15min")
    manana = pd.date_range(pd.Timestamp.now().floor("D") + pd.Timedelta(days=1),
                           periods=48, freq="15min")
    tablas = {
        "growatt_produccion": pd.DataFrame({
            "fecha": pd.date_range("2026-09-01", periods=20).date, "energia": 8.0,
        }),
        "clima_historico_openmeteo": pd.DataFrame({
            "fecha": pd.date_range("2026-09-01", periods=20).date,
            "temperatura_media": 18.0, "humedad_relativa": 50.0, "radiacion_solar": 5.0,
        }),
        "growatt_produccion_intradia": pd.DataFrame({"fecha_hora": horas, "potencia_w": 900.0}),
        "energia_estimada_15min": pd.DataFrame({
            "fecha_hora": horas, "energia_estimada_kwh": 0.2,
        }),
        "energia_pronosticada": pd.DataFrame({
            "fecha_hora": manana, "energia_estimada_kwh": 0.2,
        }),
        "clima_pronosticado": pd.DataFrame({
            "fecha_consulta": [date(2026, 10, 22)], "fecha_pronosticada": [date(2026, 10, 23)],
            "temp_predicha": [20.0], "humedad_relativa_predicha": [60.0],
            "radiacion_predicha": [6.0],
        }),
    }
    for tabla, df in tablas.items():
        almacen.upsert_parquet(tmp_path, tabla, df)
    monkeypatch.setattr(dl, "SOLAR_DIR", tmp_path)
    at = _correr(pagina)
    assert not at.exception, [e.message for e in at.exception]

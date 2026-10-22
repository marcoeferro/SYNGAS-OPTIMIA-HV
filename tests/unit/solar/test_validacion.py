"""Tests de métricas y comparativas modelo vs. real."""

from __future__ import annotations

import math
from datetime import date

import pandas as pd
import pytest

from optimia_hv.solar.validacion import comparativas, metricas


class TestMetricas:
    real = pd.Series([10.0, 20.0, 30.0, None])
    est = pd.Series([12.0, 18.0, 33.0, 5.0])

    def test_mae_rmse_sesgo(self) -> None:
        assert metricas.mae(self.real, self.est) == pytest.approx((2 + 2 + 3) / 3)
        assert metricas.rmse(self.real, self.est) == pytest.approx(math.sqrt((4 + 4 + 9) / 3))
        assert metricas.sesgo(self.real, self.est) == pytest.approx((2 - 2 + 3) / 3)

    def test_error_relativo_total(self) -> None:
        assert metricas.error_relativo_total(self.real, self.est) == pytest.approx(3 / 60)

    def test_resumen(self) -> None:
        r = metricas.resumen(self.real, self.est)
        assert r.n == 3
        assert set(r.como_dict()) == {"n", "mae", "rmse", "sesgo", "error_relativo_total"}

    def test_sin_pares(self) -> None:
        assert math.isnan(metricas.mae(pd.Series([None]), pd.Series([1.0])))
        assert math.isnan(metricas.error_relativo_total(pd.Series([0.0]), pd.Series([1.0])))


def test_intradia_real_vs_estimada() -> None:
    est = pd.DataFrame({
        "fecha_hora": pd.to_datetime(["2026-09-15 12:00", "2026-09-15 12:15",
                                      "2026-09-16 12:00"]),
        "energia_estimada_kwh": [0.25, 0.30, 0.10],
    })
    real = pd.DataFrame({
        "fecha_hora": pd.to_datetime(["2026-09-15 12:00", "2026-09-15 12:05"]),
        "potencia_w": [900.0, 950.0],
    })
    df = comparativas.intradia_real_vs_estimada(est, real, date(2026, 9, 15), date(2026, 9, 15))
    assert df["potencia_estimada_w"].tolist() == [1000.0, 1200.0]
    assert df["potencia_real_w"].tolist() == [900.0, 0.0]  # sin dato real → 0 W


def test_pronosticada_vs_real_solo_intervalos_comunes() -> None:
    est = pd.DataFrame({
        "fecha_hora": pd.to_datetime(["2026-09-15 12:00", "2026-09-15 12:15"]),
        "energia_estimada_kwh": [0.25, 0.30],
    })
    real = pd.DataFrame({
        "fecha_hora": pd.to_datetime(["2026-09-15 12:15"]), "potencia_w": [1000.0],
    })
    df = comparativas.pronosticada_vs_real(est, real, date(2026, 9, 15))
    assert len(df) == 1
    assert df["energia_real_kwh"].iloc[0] == pytest.approx(0.25)


def test_diaria_real_vs_modelo_viejo() -> None:
    clima = pd.DataFrame({
        "fecha": [date(2026, 9, 1), date(2026, 9, 2), date(2026, 10, 1)],
        "temperatura_media": [25.0, 25.0, 25.0], "humedad_relativa": [0.0, 0.0, 0.0],
        "radiacion_solar": [5.0, 4.0, 3.0],
    })
    real = pd.DataFrame({"fecha": [date(2026, 9, 1)], "energia": [8.5]})
    df = comparativas.diaria_real_vs_modelo_viejo(clima, real, hasta=date(2026, 9, 30))
    assert len(df) == 2
    assert df["energia_real_kwh"].tolist() == [8.5, 0.0]
    assert df["energia_estimada_vieja"].iloc[0] == pytest.approx(5 * 2.25 * 0.93 * 0.88)

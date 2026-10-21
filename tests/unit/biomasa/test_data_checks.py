"""Tests de los controles de calidad de datos del ETL."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from optimia_hv.biomasa.transformers.data_checks import (
    check_energy_change,
    check_tariff_jumps,
    run_data_checks,
)

EST = {"tarifa_compra_kwh": "extraido"}


def _hist(rows: list[tuple[str, str, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        [{"distribuidora": d, "vigencia": v, "tarifa_compra_kwh": t, "puntaje_compra": 4}
         for d, v, t in rows]
    )


def test_salto_de_tarifa_contra_el_cuadro_anterior() -> None:
    cfg = {"distribuidoras": {
        "A": {"tarifa_compra_kwh": 200.0, "vigencia": "2026-09", "estado_campos": EST},
        "B": {"tarifa_compra_kwh": 110.0, "vigencia": "2026-09", "estado_campos": EST},
        # Valor arrastrado: no se compara aunque difiera.
        "C": {"tarifa_compra_kwh": 300.0, "vigencia": "2026-09",
              "estado_campos": {"tarifa_compra_kwh": "fallback_previous"}},
    }}
    hist = _hist([
        ("A", "2026-07", 90.0), ("A", "2026-08", 100.0), ("A", "2026-09", 200.0),
        ("B", "2026-08", 100.0), ("C", "2026-08", 100.0),
    ])
    alertas = check_tariff_jumps(cfg, hist)
    assert [a["entidad"] for a in alertas] == ["A"]
    assert alertas[0]["valor_anterior"] == 100.0       # vigencia previa más reciente
    assert alertas[0]["variacion"] == pytest.approx(1.0)


def _anual(valores: dict[str, float]) -> pd.DataFrame:
    return pd.DataFrame({
        "Provincia": list(valores),
        "kwh_generados": list(valores.values()),
        "beneficio_total_ars": [v * 100 for v in valores.values()],
    })


def test_cambio_de_energia_total_y_por_provincia() -> None:
    antes = _anual({"cordoba": 1000.0, "chaco": 100.0, "jujuy": 1.0})
    # Chaco cae 60 %; Jujuy (< 1 % del total) se ignora aunque se duplique.
    ahora = _anual({"cordoba": 1000.0, "chaco": 40.0, "jujuy": 2.0})
    alertas = check_energy_change(ahora, antes)
    assert [(a["control"], a["entidad"]) for a in alertas] == [("cambio_provincia", "chaco")]

    # Una fuente incompleta: Córdoba cae 60 % y arrastra el total.
    alertas = check_energy_change(_anual({"cordoba": 400.0, "chaco": 100.0}), antes)
    assert {a["control"] for a in alertas} == {"cambio_total", "cambio_provincia"}


def test_sin_corrida_anterior_no_hay_alertas() -> None:
    assert check_energy_change(_anual({"cordoba": 1.0}), None) == []
    out = run_data_checks({"distribuidoras": {}}, pd.DataFrame(), _anual({"x": 1.0}), None)
    assert out.empty and "fecha" in out.columns


def test_modo_estricto_corta_solo_con_alertas() -> None:
    from optimia_hv.biomasa.pipelines.run_biomasa import DataQualityError, quality_gate

    alerta = run_data_checks(
        {"distribuidoras": {}}, pd.DataFrame(),
        _anual({"cordoba": 500.0}), _anual({"cordoba": 1000.0}),
    )
    assert len(alerta) == 2                      # energía y dinero totales
    quality_gate(alerta, estricto=False, path=Path("x"))
    quality_gate(alerta.iloc[0:0], estricto=True, path=Path("x"))
    with pytest.raises(DataQualityError):
        quality_gate(alerta, estricto=True, path=Path("x"))

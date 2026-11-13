"""Ejemplo trazable de la tesis (Sección 6.8).

10.000 t de maíz en un departamento abastecido por EDEN, escenario central
(fracción retirada 0,4), con los parámetros de la ficha del PP30 y las
tarifas de EDEN de septiembre de 2026.
"""

from __future__ import annotations

import pandas as pd
import pytest

from etl.transformers.energy_finance import (
    COL_BENEFICIO,
    COL_EQUIPOS,
    COL_KWH_TOTALES,
    add_energy_finance_columns,
)

CFG = {
    "parametros_pp30": {
        "consumo_especifico_seco_kg_kwh": 1.0,
        "humedad_pct_default": 12.0,
        "factor_autoconsumo_default": 0.6,
        "potencia_nominal_kw": 22.0,
        "disponibilidad": 0.8,
    },
    "distribuidoras": {
        "EDEN": {"tarifa_compra_kwh": 135.2341, "tarifa_inyeccion_kwh": 124.0227},
    },
    "provincia_a_distribuidora": {"buenos aires": "EDEN"},
}


def test_ejemplo_trazable_maiz_escenario_central() -> None:
    ic, ms, f = 0.47, 0.855, 0.4
    biomasa_t = 10_000 * ms * (1 - ic) / ic
    assert biomasa_t == pytest.approx(9641.5, abs=1)

    df = pd.DataFrame({"Provincia": ["buenos aires"], "Residuo Recuperable (Tn)": [biomasa_t * f]})
    out = add_energy_finance_columns(df, config=CFG)

    assert out[COL_KWH_TOTALES].iloc[0] == pytest.approx(3_856_600, rel=1e-3)
    assert out["masa_alimentada_kg"].iloc[0] == pytest.approx(4_382_500, rel=1e-3)
    assert out[COL_EQUIPOS].iloc[0] == pytest.approx(25.0, abs=0.1)
    assert out[COL_BENEFICIO].iloc[0] == pytest.approx(504.25e6, rel=1e-3)

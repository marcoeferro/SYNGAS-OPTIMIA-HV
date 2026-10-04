"""Tests de regresión de los errores corregidos en el ETL."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from etl.transformers.biomass import (
    RESIDUO_REC_COL,
    add_recoverable_residue,
    compute_biomass,
)
from etl.transformers.reconciliation import (
    compute_discrepancies,
    reconciliar_por_mayor_produccion,
)
from etl.transformers.reference_period import (
    annualize,
    detect_incomplete_campaigns,
    select_reference_campaigns,
)
from etl.transformers.source_cleaning import (
    FUENTE_CBA,
    FUENTE_MAGYP,
    dedupe_cba_merge_artifacts,
    group_and_standardize,
)
from etl.transformers.validation import validar_reconciliacion


def _cba_row(gls: float) -> dict:
    return {
        "PROVINCIA": "Córdoba", "DEPARTAMENTO": "RIO CUARTO", "CULTIVO": "MANI",
        "CAMPAÑA": "2022/23", "SEMBRADAS": 100.0, "COSECHADAS": 100.0,
        "RENDIMIENTO": 30.0, "PRODUCCIÓN": 300.0,
        "PRODUCCIÓN GRANO LIMPIO Y SECO": gls,
    }


def test_cba_merge_cartesiano_no_multiplica_produccion() -> None:
    raw = pd.DataFrame([_cba_row(79.0), _cba_row(2785.0)] * 2)
    out = dedupe_cba_merge_artifacts(raw.drop(columns=["PRODUCCIÓN GRANO LIMPIO Y SECO"]))
    assert len(out) == 1
    assert out["PRODUCCIÓN"].sum() == 300.0


def test_magyp_sd_no_se_convierte_en_cero() -> None:
    df = pd.DataFrame({
        "Campaña": ["2020/21"], "Provincia": ["x"], "Departamento": ["y"],
        "Cultivo": ["maiz"], "Sup. Cosechada": [np.nan], "Producción": [np.nan],
    })
    out = group_and_standardize(df, FUENTE_MAGYP)
    assert pd.isna(out["Produccion (Tn)"].iloc[0])


def test_rendimiento_nan_sin_superficie() -> None:
    df = pd.DataFrame({
        "Campaña": ["2020/21"], "Provincia": ["x"], "Departamento": ["y"],
        "Cultivo": ["maiz"], "COSECHADAS": [0.0], "PRODUCCIÓN": [0.0],
    })
    out = group_and_standardize(df, FUENTE_CBA)
    assert pd.isna(out["Rendimiento (Tn/Ha)"].iloc[0])


def _two_sources(prod_magyp: float, prod_cba: float) -> pd.DataFrame:
    return pd.DataFrame({
        "Provincia": ["cordoba"] * 2, "Departamento": ["rio cuarto"] * 2,
        "Campaña": ["2020/21"] * 2, "Cultivo": ["soja"] * 2,
        "Superficie (Ha)": [1000.0, 900.0],
        "Produccion (Tn)": [prod_magyp, prod_cba],
        "Rendimiento (Tn/Ha)": [3.0, 3.0],
        "fuente": ["magyp_estimaciones", "bolsa_cereales_cba"],
    })


@pytest.mark.parametrize("order", [[0, 1], [1, 0]])
def test_empate_prefiere_magyp_independiente_del_orden(order: list[int]) -> None:
    df = _two_sources(3000.0, 3000.0).iloc[order].reset_index(drop=True)
    final, desc = reconciliar_por_mayor_produccion(df)
    assert final["fuente"].iloc[0] == "magyp_estimaciones"
    assert desc["fuente"].iloc[0] == "bolsa_cereales_cba"


def test_reconciliacion_con_nan_prefiere_valor() -> None:
    df = _two_sources(np.nan, 2500.0)
    final, _ = reconciliar_por_mayor_produccion(df)
    assert final["Produccion (Tn)"].iloc[0] == 2500.0
    validar_reconciliacion(final, df)  # NaN no rompe invariantes


def test_validacion_detecta_fuente_invalida() -> None:
    df = _two_sources(3000.0, 2000.0)
    final, _ = reconciliar_por_mayor_produccion(df)
    final.loc[0, "fuente"] = "otra"
    with pytest.raises(AssertionError, match="fuente"):
        validar_reconciliacion(final, df)


def test_discrepancias_no_vacias() -> None:
    out = compute_discrepancies(_two_sources(3000.0, 2000.0))
    assert len(out) == 1
    assert out["diff_rel_produccion"].iloc[0] == pytest.approx(0.5)


def test_biomasa_en_base_seca() -> None:
    df = pd.DataFrame({"Cultivo": ["papa"], "Produccion (Tn)": [1000.0],
                       "Rendimiento (Tn/Ha)": [30.0]})
    ic = pd.DataFrame({"Cultivo": ["papa"], "FR": [0.35], "MS": [0.2]})
    out = compute_biomass(df, ic)
    assert out["Residuo de Biomasa (Tn)"].iloc[0] == pytest.approx(1000 * 0.2 * 0.35)


def test_residuo_recuperable() -> None:
    df = pd.DataFrame({"Residuo de Biomasa (Tn)": [100.0]})
    assert add_recoverable_residue(df, 0.4)[RESIDUO_REC_COL].iloc[0] == 40.0
    with pytest.raises(ValueError):
        add_recoverable_residue(df, 0.0)


def _campaign_df() -> pd.DataFrame:
    rows = []
    for year, n in [(2018, 10), (2019, 10), (2020, 10), (2021, 10), (2022, 10),
                    (2023, 10), (2024, 3)]:
        camp = f"{year}/{str(year + 1)[-2:]}"
        rows += [{"Campaña": camp, "k": i, "v": 1.0} for i in range(n)]
    return pd.DataFrame(rows)


def test_detecta_campana_incompleta() -> None:
    assert detect_incomplete_campaigns(_campaign_df()) == ["2024/25"]
    assert select_reference_campaigns(_campaign_df(), 2) == ["2022/23", "2023/24"]


def test_annualize_divide_por_n_campanas() -> None:
    df = pd.DataFrame({"Campaña": ["2020/21", "2021/22"], "k": ["a", "a"],
                       "v": [10.0, 20.0]})
    out = annualize(df, ["2019/20", "2020/21", "2021/22"], ["k"], ["v"])
    # campaña sin registro cuenta como 0: (10 + 20) / 3
    assert out["v"].iloc[0] == pytest.approx(10.0)
    assert out["n_campanas_con_dato"].iloc[0] == 2

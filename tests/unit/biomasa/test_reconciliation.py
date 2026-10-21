"""Tests de reconciliación multi-fuente."""

from __future__ import annotations

import pandas as pd

from optimia_hv.biomasa.transformers.reconciliation import (
    DEFAULT_KEY,
    PROD_COL,
    coverage_report,
    reconciliar_por_mayor_produccion,
)


def test_reconciliacion_selecciona_max_produccion(
    df_reconciliation_sample: pd.DataFrame,
) -> None:
    df_final, df_descartado = reconciliar_por_mayor_produccion(
        df_reconciliation_sample, DEFAULT_KEY, PROD_COL
    )
    assert len(df_final) == 1
    assert df_final.iloc[0][PROD_COL] == 3500.0
    assert df_final.iloc[0]["fuente"] == "bolsa_cereales_cba"
    assert len(df_descartado) == 1


def test_coverage_report(df_reconciliation_sample: pd.DataFrame) -> None:
    coverage = coverage_report(df_reconciliation_sample, DEFAULT_KEY)
    assert coverage.loc[2, "n_celdas"] == 1  # una clave cubierta por 2 fuentes


def test_reconciliacion_sin_duplicados() -> None:
    df = pd.DataFrame({
        "Provincia": ["cordoba"],
        "Departamento": ["rio cuarto"],
        "Campaña": ["2020/21"],
        "Cultivo": ["soja"],
        "Superficie (Ha)": [1000.0],
        "Produccion (Tn)": [3000.0],
        "fuente": ["magyp_estimaciones"],
    })
    df_final, df_descartado = reconciliar_por_mayor_produccion(df, DEFAULT_KEY, PROD_COL)
    assert len(df_final) == 1
    assert len(df_descartado) == 0
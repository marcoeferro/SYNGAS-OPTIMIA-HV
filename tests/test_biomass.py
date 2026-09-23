"""Tests de cálculo de biomasa residual."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from etl.transformers.biomass import (
    add_density_columns,
    add_validity_flags,
    compute_biomass,
)


@pytest.fixture
def df_biomasa_input() -> pd.DataFrame:
    return pd.DataFrame({
        "Cultivo": ["soja", "trigo", "alpiste"],
        "Superficie (Ha)": [1000.0, 500.0, 200.0],
        "Produccion (Tn)": [3000.0, 1500.0, 300.0],
        "Rendimiento (Tn/Ha)": [3.0, 3.0, 1.5],
    })


@pytest.fixture
def df_ic_input() -> pd.DataFrame:
    return pd.DataFrame({
        "Cultivo": ["soja", "trigo"],
        "FR": [1.2222, 1.8571],
    })


def test_compute_biomass(
    df_biomasa_input: pd.DataFrame, df_ic_input: pd.DataFrame
) -> None:
    out = compute_biomass(df_biomasa_input, df_ic_input)
    assert "Residuo de Biomasa (Tn)" in out.columns
    # soja: 3000 * 1.2222 = 3666.6
    assert out.loc[out["Cultivo"] == "soja", "Residuo de Biomasa (Tn)"].iloc[0] == pytest.approx(3666.6, rel=1e-3)
    # alpiste: sin IC, debe ser NaN
    assert pd.isna(out.loc[out["Cultivo"] == "alpiste", "Residuo de Biomasa (Tn)"].iloc[0])


def test_add_validity_flags(
    df_biomasa_input: pd.DataFrame, df_ic_input: pd.DataFrame
) -> None:
    df = compute_biomass(df_biomasa_input, df_ic_input)
    df = add_validity_flags(df)
    assert df[df["Cultivo"] == "soja"]["_valido_biomasa"].iloc[0]
    assert not df[df["Cultivo"] == "alpiste"]["_valido_biomasa"].iloc[0]


def test_add_density_columns(
    df_biomasa_input: pd.DataFrame, df_ic_input: pd.DataFrame
) -> None:
    df = compute_biomass(df_biomasa_input, df_ic_input)
    df = add_validity_flags(df)
    validos = df[df["_valido_biomasa"]].copy()
    out = add_density_columns(validos)
    assert "Residuo de Biomasa (Tn/Ha)" in out.columns
    assert "Produccion (Tn/Ha)" in out.columns

def test_zero_surface_not_valid() -> None:
    """Superficie <= 0 no debe marcarse como biomasa válida."""
    df = pd.DataFrame({
        "Cultivo": ["soja", "trigo"],
        "Superficie (Ha)": [0.0, 100.0],
        "Produccion (Tn)": [50.0, 300.0],
        "Rendimiento (Tn/Ha)": [np.nan, 3.0],
    })
    df_ic = pd.DataFrame({"Cultivo": ["soja", "trigo"], "FR": [1.2, 1.8]})
    out = add_validity_flags(compute_biomass(df, df_ic))
    assert not bool(out.loc[out["Cultivo"] == "soja", "_valido_biomasa"].iloc[0])
    assert bool(out.loc[out["Cultivo"] == "trigo", "_valido_biomasa"].iloc[0])
    assert bool(out.loc[out["Cultivo"] == "soja", "_rendimiento_invalido"].iloc[0])
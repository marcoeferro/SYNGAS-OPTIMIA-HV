"""Tests de resolución de agregados vs componentes."""

from __future__ import annotations

import pandas as pd
import pytest

from etl.reference.crop_taxonomy import CROP_TAXONOMY
from etl.transformers.crop_consolidation import resolve_crops


def test_total_prevalece_sobre_componentes(df_crops_basic: pd.DataFrame) -> None:
    out = resolve_crops(df_crops_basic, CROP_TAXONOMY)
    assert len(out) == 1
    assert out.iloc[0]["Cultivo"] == "soja"
    assert out.iloc[0]["_source_cultivo"] == "soja total"


def test_base_canonico_no_agregado() -> None:
    df = pd.DataFrame({
        "Campaña": ["2020/21"], "Provincia": ["cordoba"],
        "Departamento": ["rio cuarto"], "Cultivo": ["soja"],
        "Producción": [1000],
    })
    out = resolve_crops(df, CROP_TAXONOMY)
    assert len(out) == 1
    assert out.iloc[0]["Cultivo"] == "soja"


def test_componentes_se_conservan_sin_total() -> None:
    df = pd.DataFrame({
        "Campaña": ["2020/21"] * 2, "Provincia": ["cordoba"] * 2,
        "Departamento": ["rio cuarto"] * 2,
        "Cultivo": ["soja 1ra", "soja 2da"], "Producción": [1000, 500],
    })
    out = resolve_crops(df, CROP_TAXONOMY)
    assert len(out) == 2
    assert set(out["Cultivo"]) == {"soja"}


def test_trigo_candeal_no_consolida_con_trigo() -> None:
    df = pd.DataFrame({
        "Campaña": ["2020/21"] * 2, "Provincia": ["cordoba"] * 2,
        "Departamento": ["rio cuarto"] * 2,
        "Cultivo": ["trigo total", "trigo candeal"],
        "Producción": [10000, 2000],
    })
    out = resolve_crops(df, CROP_TAXONOMY)
    assert set(out["Cultivo"]) == {"trigo", "trigo candeal"}


def test_cultivo_compuesto_no_se_colapsa() -> None:
    df = pd.DataFrame({
        "Campaña": ["2020/21"], "Provincia": ["cordoba"],
        "Departamento": ["rio cuarto"], "Cultivo": ["cana de azucar"],
        "Producción": [5000],
    })
    out = resolve_crops(df, CROP_TAXONOMY)
    assert out.iloc[0]["Cultivo"] == "cana de azucar"


def test_fail_fast_ante_cultivo_no_mapeado() -> None:
    df = pd.DataFrame({
        "Campaña": ["2020/21"], "Provincia": ["x"],
        "Departamento": ["y"], "Cultivo": ["quinoa"],
        "Producción": [100],
    })
    with pytest.raises(ValueError, match="quinoa"):
        resolve_crops(df, CROP_TAXONOMY)
"""Tests de normalización geográfica."""

from __future__ import annotations

import pandas as pd
import pytest

from optimia_hv.biomasa.transformers.geography import (
    expand_abbrevs,
    flag_invalid_geo,
    normalize_geo,
    resolve_dept_alias,
)


def test_expand_abbrevs_token_wise() -> None:
    assert expand_abbrevs("gral san martin") == "general san martin"
    assert expand_abbrevs("pte roque saenz pena") == "presidente roque saenz pena"
    assert expand_abbrevs("grales") == "grales"  # no expande dentro de token


def test_resolve_dept_alias_scoped_by_province() -> None:
    assert resolve_dept_alias("tucuman", "j b alberdi") == "juan b alberdi"
    assert resolve_dept_alias("cordoba", "j b alberdi") == "j b alberdi"


def test_normalize_geo_collapses_abbrevs(df_geo_basic: pd.DataFrame) -> None:
    out = normalize_geo(df_geo_basic)
    assert out["Departamento"].nunique() == 1
    assert out["Departamento"].iloc[0] == "general san martin"


def test_flag_invalid_geo() -> None:
    df = pd.DataFrame({"Departamento": ["capital", "sin definir", "rio cuarto"]})
    out = flag_invalid_geo(df)
    assert out["_dept_valido"].tolist() == [True, False, True]

@pytest.mark.parametrize(
    ("provincia", "dept", "esperado"),
    [
        ("santiago del estero", "juan f ibarra", "juan felipe ibarra"),
        ("san luis", "libertador san martin", "libertador general san martin"),
    ],
)
def test_alias_unifica_nombres_entre_fuentes(provincia: str, dept: str, esperado: str) -> None:
    """MAGyP y la Bolsa de Córdoba: sin alias se sumaban ambas fuentes."""
    assert resolve_dept_alias(provincia, dept) == esperado

"""Tests de las utilidades del dashboard (claves geográficas y formato)."""

from __future__ import annotations

import pandas as pd
import pytest

from dashboard import data_loader as dl


@pytest.mark.parametrize(
    ("provincia", "departamento", "esperado"),
    [
        ("buenos aires", "25 de mayo", "buenosaires|veinticincodemayo"),
        ("chaco", "12 de octubre", "chaco|docedeoctubre"),
        ("chaco", "1 de mayo", "chaco|primerodemayo"),
        ("la rioja", "general angel v penaloza", "larioja|generalangelvicentepenaloza"),
        ("san luis", "juan martin de pueyrredon", "sanluis|lacapital"),
        ("cordoba", "rio cuarto", "cordoba|riocuarto"),
    ],
)
def test_clave_de_departamento_para_gadm(provincia: str, departamento: str, esperado: str) -> None:
    assert dl.dept_geo_key(dl.norm_key(provincia), dl.norm_key(departamento)) == esperado


def test_partido_en_dos_poligonos_comparte_id() -> None:
    props = {"NAME_1": "BuenosAires", "NAME_2": "SanFernando(2)"}
    assert dl._geo_dept_id(props) == "buenosaires|sanfernando"


def test_casi_todos_los_departamentos_tienen_poligono() -> None:
    """Los que faltan son 'sin definir' o departamentos posteriores a GADM 4.1."""
    ids = {f["id"] for f in dl.load_geojson_departments()["features"]}
    datos = pd.DataFrame({
        "Provincia": ["buenos aires", "chaco", "santa fe", "buenos aires"],
        "Departamento": ["9 de julio", "2 de abril", "general lopez", "lezama"],
    })
    claves = [
        dl.dept_geo_key(dl.norm_key(p), dl.norm_key(d))
        for p, d in zip(datos["Provincia"], datos["Departamento"], strict=True)
    ]
    assert [c in ids for c in claves] == [True, False, True, False]


def test_nombre_legible() -> None:
    assert dl.nice_name("santiago del estero") == "Santiago del Estero"
    assert dl.format_ars(7.54e12) == "$ 7.54 billones"

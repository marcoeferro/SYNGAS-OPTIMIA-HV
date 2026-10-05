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


def test_cache_relee_el_parquet_cuando_el_etl_lo_reescribe(tmp_path) -> None:
    """Antes la caché ignoraba el archivo y mostraba datos viejos hasta reiniciar."""
    import os

    path = tmp_path / "x.parquet"
    pd.DataFrame({"a": [1]}).to_parquet(path)
    assert dl._load(path)["a"].tolist() == [1]
    pd.DataFrame({"a": [2]}).to_parquet(path)
    st_ = path.stat()
    os.utime(path, (st_.st_atime, st_.st_mtime + 10))
    assert dl._load(path)["a"].tolist() == [2]
    assert dl._load(tmp_path / "no_existe.parquet") is None


def _df_escenarios() -> pd.DataFrame:
    # Fila 0: inyección publicada (real); fila 1: estimada (compra × 0,9).
    return pd.DataFrame({
        dl.COL_RECUPERABLE: [1.0, 1.0],
        dl.COL_KWH: [1000.0, 1000.0],
        dl.COL_EQUIPOS: [0.01, 0.01],
        "tarifa_compra_kwh": [100.0, 100.0],
        "tarifa_inyeccion_kwh": [80.0, 90.0],
        "tarifa_inyeccion_estimada": [False, True],
    })


BASE = dl.Supuestos(autoconsumo=0.6, consumo_especifico=1.0, fraccion_recuperable=0.5)


def test_supuestos_del_etl_no_cambian_nada() -> None:
    df = _df_escenarios()
    assert dl.apply_supuestos(df, BASE, BASE) is df


@pytest.mark.parametrize(
    ("escenario", "iny_estimada"),
    [(dl.INYECCION_CONSERVADOR, 0.0), (dl.INYECCION_CENTRAL, 90.0), (dl.INYECCION_ALTO, 100.0)],
)
def test_escenarios_de_inyeccion_solo_cambian_las_estimadas(
    escenario: str, iny_estimada: float
) -> None:
    sup = dl.Supuestos(autoconsumo=0.6, inyeccion=escenario,
                       consumo_especifico=1.0, fraccion_recuperable=0.5)
    out = dl.apply_supuestos(_df_escenarios(), sup, dl.Supuestos(autoconsumo=0.5))
    assert out["tarifa_inyeccion_kwh"].tolist() == [80.0, iny_estimada]
    # 600 kWh × 100 + 400 kWh × inyección
    assert out[dl.COL_BENEFICIO].tolist() == pytest.approx(
        [60_000 + 400 * 80, 60_000 + 400 * iny_estimada]
    )


def test_consumo_especifico_y_fraccion_recuperable_escalan_la_energia() -> None:
    sup = dl.Supuestos(autoconsumo=0.6, consumo_especifico=1.1, fraccion_recuperable=0.3)
    out = dl.apply_supuestos(_df_escenarios(), sup, BASE)
    assert out[dl.COL_KWH].iloc[0] == pytest.approx(1000 * 0.3 / 0.5 / 1.1)
    assert out[dl.COL_RECUPERABLE].iloc[0] == pytest.approx(0.6)
    assert out[dl.COL_EQUIPOS].iloc[0] == pytest.approx(0.01 * 0.6 / 1.1)

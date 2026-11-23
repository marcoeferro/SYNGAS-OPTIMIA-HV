"""Tests del historial de tarifas (etl/loaders/tariff_history.py)."""

from __future__ import annotations

import warnings

from etl.loaders.tariff_history import append_history, history_path, load_history

BASE = {
    "distribuidora": "EPEC",
    "vigencia": "2026-10",
    "tarifa_compra_kwh": 150.5,
    "tarifa_inyeccion_kwh": 80.25,
    "cargo_fijo_mensual": 1200.0,
    "seccion_compra": "T3",
    "puntaje_compra": 10,
    "n_valores_compra": 1,
    "n_valores_inyeccion": 0,
    "fuente_tipo": "nacional",
    "documento": "https://ejemplo.test/a.pdf",
    "sha256": "aaa",
    "fecha_extraccion": "2026-10-05",
}


def test_filas_con_columnas_vacias_no_cambian_el_historial(tmp_path):
    append_history([BASE], tmp_path)
    before = history_path(tmp_path).read_text(encoding="utf-8").splitlines()

    # Documento nuevo sin inyección, cargo fijo ni conteos: columnas todas
    # vacías. En pandas 2.x esto daba FutureWarning en el concat.
    nuevo = {
        "distribuidora": "EPEC",
        "vigencia": "2026-11",
        "tarifa_compra_kwh": 160.0,
        "documento": "https://ejemplo.test/b.pdf",
        "sha256": "bbb",
        "fecha_extraccion": "2026-11-05",
    }
    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        _, n_new = append_history([nuevo], tmp_path)

    assert n_new == 1
    after = history_path(tmp_path).read_text(encoding="utf-8").splitlines()
    # Las filas previas quedan escritas igual (10, no 10.0).
    assert set(before) <= set(after)
    assert ",10,1,0," in after[1]
    assert after[-1] == "EPEC,2026-11,160.0,,,,,,,,https://ejemplo.test/b.pdf,bbb,2026-11-05"
    assert len(load_history(tmp_path)) == 2


def test_documento_repetido_no_se_duplica(tmp_path):
    append_history([BASE], tmp_path)
    _, n_new = append_history([BASE], tmp_path)
    assert n_new == 0
    assert len(load_history(tmp_path)) == 1

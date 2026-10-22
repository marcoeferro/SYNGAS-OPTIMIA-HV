"""Tests de la lectura de config/solar.yaml."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from optimia_hv.solar.configuracion import (
    DEFAULT_CONFIG_PATH,
    PROJECT_ROOT,
    ConfigSolar,
    cargar_config,
)


def test_config_versionada_coincide_con_los_valores_por_defecto() -> None:
    cfg = cargar_config(DEFAULT_CONFIG_PATH)
    base = ConfigSolar()
    assert cfg.latitud == base.latitud and cfg.longitud == base.longitud
    assert cfg.historico_desde == date(2024, 8, 1)
    assert cfg.modelo_15min == base.modelo_15min
    assert cfg.modelo_viejo == base.modelo_viejo
    assert cfg.almacen_dir == base.almacen_dir


def test_archivo_inexistente_usa_defectos(tmp_path: Path) -> None:
    assert cargar_config(tmp_path / "no_existe.yaml") == ConfigSolar()


def test_claves_parciales(tmp_path: Path) -> None:
    path = tmp_path / "solar.yaml"
    destino = (tmp_path / "x").as_posix()
    path.write_text(
        f"modelo_15min:\n  pr_base: 0.8\nalmacen:\n  dir: '{destino}'\n", encoding="utf-8"
    )
    cfg = cargar_config(path)
    assert cfg.modelo_15min.pr_base == 0.8
    assert cfg.modelo_15min.noct == 45.0
    assert cfg.almacen_dir == tmp_path / "x"


def test_rutas_relativas_a_la_raiz(tmp_path: Path) -> None:
    path = tmp_path / "solar.yaml"
    path.write_text("almacen:\n  dir: data/otra\n", encoding="utf-8")
    assert cargar_config(path).almacen_dir == PROJECT_ROOT / "data" / "otra"

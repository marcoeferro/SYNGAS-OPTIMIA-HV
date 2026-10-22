"""Pipeline solar completo con respuestas grabadas (sin red) y disco temporal."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from optimia_hv.solar.configuracion import ConfigSolar
from optimia_hv.solar.extractors import growatt, nasa_power, open_meteo
from optimia_hv.solar.loaders import almacen
from optimia_hv.solar.pipelines import run_solar

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "solar"
HOY = date(2026, 10, 22)


def _fixture(nombre: str) -> dict[str, Any]:
    datos: dict[str, Any] = json.loads((FIXTURES / nombre).read_text(encoding="utf-8"))
    return datos


class GrowattFalso:
    """Reemplaza al cliente real: no hay red ni credenciales en los tests."""

    def __init__(self, *_: object) -> None:
        pass

    def __enter__(self) -> GrowattFalso:
        return self

    def __exit__(self, *_: object) -> None:
        pass

    def energia_mensual(self, mes: str) -> list[float]:
        return [8.0, 0.0, 9.0] + [7.5] * 28

    def potencia_dia(self, fecha: object) -> list[float]:
        return [0.0] * 100 + [1200.0] * 50 + [0.0] * 138


@pytest.fixture
def cfg(tmp_path: Path) -> ConfigSolar:
    return ConfigSolar(almacen_dir=tmp_path / "solar")


@pytest.fixture
def sin_red(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROWATT_USER", "u")
    monkeypatch.setenv("GROWATT_PASSWORD", "p")
    monkeypatch.setenv("GROWATT_PLANT_ID", "1")
    monkeypatch.delenv("SOLAR_DB_URL", raising=False)
    monkeypatch.setattr(growatt, "ClienteGrowatt", GrowattFalso)
    monkeypatch.setattr(growatt.time, "sleep", lambda _: None)
    monkeypatch.setattr(
        nasa_power, "descargar_diario",
        lambda *a, **k: nasa_power.parsear_respuesta(_fixture("nasa_power_diario.json")),
    )
    monkeypatch.setattr(
        open_meteo, "historico_diario",
        lambda *a, **k: open_meteo.parsear_historico_diario(
            _fixture("open_meteo_historico_diario.json")),
    )
    monkeypatch.setattr(
        open_meteo, "pronostico_diario",
        lambda *a, fecha_consulta, **k: open_meteo.parsear_pronostico_diario(
            _fixture("open_meteo_pronostico_diario.json"), fecha_consulta),
    )
    monkeypatch.setattr(
        open_meteo, "pronostico_15min",
        lambda *a, fecha_consulta, **k: open_meteo.parsear_pronostico_15min(
            _fixture("open_meteo_pronostico_15min.json"), fecha_consulta),
    )
    # El pronóstico grabado es del 22/10 a la mañana: "ahora" es antes.
    monkeypatch.setattr(run_solar.modelo_15min, "ahora", lambda: pd.Timestamp("2026-10-22"))


@pytest.mark.usefixtures("sin_red")
def test_corrida_diaria_guarda_las_siete_tablas(cfg: ConfigSolar) -> None:
    r = run_solar.run_diario(cfg, hoy=HOY)
    assert r.ok, r.errores
    for tabla in (
        "growatt_produccion", "clima_historico_nasa", "clima_historico_openmeteo",
        "clima_pronosticado", "growatt_produccion_intradia", "pronostico_15min_5days",
        "energia_pronosticada",
    ):
        assert almacen.ruta_tabla(cfg.almacen_dir, tabla).is_file(), tabla

    diaria = almacen.leer(cfg.almacen_dir, "growatt_produccion")
    assert diaria["fecha"].max() == date(2026, 10, 21)  # hoy no se procesa
    assert diaria.set_index("fecha").loc[date(2026, 10, 2), "energia"] == 8.5  # hueco promediado

    intradia = almacen.leer(cfg.almacen_dir, "growatt_produccion_intradia")
    assert len(intradia) == 96  # un día cada 15 min

    energia = almacen.leer(cfg.almacen_dir, "energia_pronosticada")
    assert len(energia) == 12
    assert (energia["energia_estimada_kwh"] > 0).all()


@pytest.mark.usefixtures("sin_red")
def test_corrida_repetida_no_duplica(cfg: ConfigSolar) -> None:
    run_solar.run_diario(cfg, hoy=HOY)
    run_solar.run_diario(cfg, hoy=HOY)
    assert len(almacen.leer(cfg.almacen_dir, "clima_historico_nasa")) == 5
    assert len(almacen.leer(cfg.almacen_dir, "pronostico_15min_5days")) == 12


@pytest.mark.usefixtures("sin_red")
def test_un_paso_caido_no_frena_a_los_demas(
    cfg: ConfigSolar, monkeypatch: pytest.MonkeyPatch
) -> None:
    def caida(*_: object, **__: object) -> pd.DataFrame:
        raise ConnectionError("NASA caída")

    monkeypatch.setattr(nasa_power, "descargar_diario", caida)
    r = run_solar.run_diario(cfg, hoy=HOY)
    assert set(r.errores) == {"nasa"}
    assert almacen.ruta_tabla(cfg.almacen_dir, "energia_pronosticada").is_file()


@pytest.mark.usefixtures("sin_red")
def test_energia_usa_pronostico_guardado_si_no_se_descarga(cfg: ConfigSolar) -> None:
    run_solar.run_diario(cfg, hoy=HOY, solo=["pronostico_15min"])
    r = run_solar.run_diario(cfg, hoy=HOY, solo=["energia_pronosticada"])
    assert r.ok, r.errores
    assert r.guardadas["energia_pronosticada"] == 12


def test_sin_credenciales_growatt_falla_solo_growatt(
    cfg: ConfigSolar, monkeypatch: pytest.MonkeyPatch
) -> None:
    for var in ("GROWATT_USER", "GROWATT_PASSWORD", "GROWATT_PLANT_ID"):
        monkeypatch.delenv(var, raising=False)
    r = run_solar.run_diario(cfg, hoy=HOY, solo=["growatt_diaria", "growatt_15min"])
    assert set(r.errores) == {"growatt_diaria", "growatt_15min"}
    assert "GROWATT_USER" in r.errores["growatt_diaria"]


def test_upsert_reemplaza_por_clave(tmp_path: Path) -> None:
    almacen.upsert_parquet(tmp_path, "growatt_produccion", pd.DataFrame({
        "fecha": [date(2026, 9, 1), date(2026, 9, 2)], "energia": [0.0, 7.0],
    }))
    almacen.upsert_parquet(tmp_path, "growatt_produccion", pd.DataFrame({
        "fecha": ["2026-09-02", "2026-09-03"], "energia": [7.5, 8.0],
    }))
    df = almacen.leer(tmp_path, "growatt_produccion")
    assert df["fecha"].tolist() == [date(2026, 9, 1), date(2026, 9, 2), date(2026, 9, 3)]
    assert df["energia"].tolist() == [0.0, 7.5, 8.0]


def test_replica_e_importa_desde_sql(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("sqlalchemy")
    url = f"sqlite:///{tmp_path / 'datos.sqlite'}"
    monkeypatch.setenv("SOLAR_DB_URL", url)
    origen = tmp_path / "origen"
    almacen.guardar(origen, "growatt_produccion", pd.DataFrame({
        "fecha": [date(2026, 9, 1)], "energia": [5.0],
    }))
    almacen.guardar(origen, "growatt_produccion", pd.DataFrame({
        "fecha": [date(2026, 9, 1)], "energia": [6.0],
    }))
    destino = tmp_path / "destino"
    importadas = almacen.importar_desde_sql(url, destino, ["growatt_produccion", "no_existe"])
    assert importadas == {"growatt_produccion": 1}
    assert almacen.leer(destino, "growatt_produccion")["energia"].tolist() == [6.0]

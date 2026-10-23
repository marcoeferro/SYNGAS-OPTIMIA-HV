"""CLI del pipeline solar: código de salida y avisos (lo que ve el cron)."""

from __future__ import annotations

from pathlib import Path

import pytest

from optimia_hv.solar.configuracion import ConfigSolar
from optimia_hv.solar.pipelines import run_solar


@pytest.fixture
def avisos(monkeypatch: pytest.MonkeyPatch) -> list[tuple[tuple, dict]]:
    llamadas: list[tuple[tuple, dict]] = []
    monkeypatch.setattr(run_solar, "notify_run_result",
                        lambda *a, **k: llamadas.append((a, k)))
    monkeypatch.setattr(run_solar, "setup_logging", lambda *_: None)
    return llamadas


def _resultado(errores: dict[str, str]) -> run_solar.Resultado:
    r = run_solar.Resultado()
    r.errores.update(errores)
    return r


def test_corrida_diaria_ok_sale_con_0(
    avisos: list, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pedidos: list[object] = []
    monkeypatch.setattr(run_solar, "run_diario",
                        lambda cfg, solo=None: pedidos.append(solo) or _resultado({}))
    assert run_solar.main(["--config", str(tmp_path / "no_existe.yaml")]) == 0
    assert pedidos == [None]
    args, kwargs = avisos[0]
    assert not args
    assert kwargs["etiqueta"] == run_solar.ETIQUETA_AVISOS


def test_paso_con_error_sale_con_1_y_avisa(
    avisos: list, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(run_solar, "run_diario",
                        lambda cfg, solo=None: _resultado({"nasa": "timeout"}))
    assert run_solar.main(["--config", str(tmp_path / "x.yaml")]) == 1
    args, _ = avisos[0]
    assert "nasa: timeout" in str(args[0])


def test_solo_pasa_los_pasos_elegidos(
    avisos: list, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pedidos: list[object] = []
    monkeypatch.setattr(run_solar, "run_diario",
                        lambda cfg, solo=None: pedidos.append(solo) or _resultado({}))
    run_solar.main(["--config", str(tmp_path / "x.yaml"), "--solo", "nasa", "open_meteo"])
    assert pedidos == [["nasa", "open_meteo"]]


def test_historico_y_validar_son_excluyentes(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        run_solar.main(["--historico", "--validar", "2026-09-01", "2026-09-02"])


def test_config_inexistente_usa_valores_por_defecto(tmp_path: Path) -> None:
    from optimia_hv.solar.configuracion import cargar_config

    assert cargar_config(tmp_path / "no_existe.yaml").latitud == ConfigSolar().latitud

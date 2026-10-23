"""Pipeline de biomasa completo, sin red, sobre una copia de los datos del repo.

Es lo que corre el cron todos los días (``run_biomasa``), con la extracción
apagada: usa los raw y las tarifas versionados en ``data/`` copiados a
``tmp_path``, así el test no toca los datos reales.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd
import pytest
import yaml

from optimia_hv.biomasa.pipelines import run_biomasa
from optimia_hv.biomasa.transformers.energy_finance import COL_BENEFICIO, COL_KWH_TOTALES
from optimia_hv.comun.io_utils import RAW_STEM_CBA, RAW_STEM_MAGYP

DATA = Path(__file__).resolve().parents[3] / "data"


@pytest.fixture
def config(tmp_path: Path) -> Path:
    """Arma data/ en ``tmp_path`` con los raw y la referencia versionados."""
    raw = tmp_path / "raw"
    ref = tmp_path / "reference"
    raw.mkdir()
    ref.mkdir()
    for stem in (RAW_STEM_CBA, RAW_STEM_MAGYP):
        shutil.copy(DATA / "raw" / f"{stem}.csv", raw)
    for nombre in ("ic_fr.csv", "tarifas_historial.csv"):
        shutil.copy(DATA / "reference" / nombre, ref)
    shutil.copy(max((DATA / "reference").glob("*_tarifas.json")), ref)

    path = tmp_path / "paths.yaml"
    path.write_text(yaml.safe_dump({"data": {
        "raw": str(raw),
        "reference": str(ref),
        "interim": str(tmp_path / "interim"),
        "processed": str(tmp_path / "processed"),
        "audit": str(tmp_path / "audit"),
    }}), encoding="utf-8")
    return path


def _correr(config: Path, **kwargs: object) -> dict:
    return run_biomasa.run(config, skip_extract=True, skip_tarifas=True, **kwargs)


def test_corrida_offline_publica_los_artefactos(config: Path) -> None:
    paths = _correr(config)
    for clave in ("biomasa", "potencial_anual", "descartados", "discrepancias",
                  "alertas_calidad"):
        assert paths[clave].is_file(), clave

    anual = pd.read_parquet(paths["potencial_anual"])
    assert not anual.empty
    assert anual[["Provincia", "Departamento", "Cultivo"]].notna().all().all()
    assert not anual.duplicated(["Provincia", "Departamento", "Cultivo"]).any()
    # Lo que muestra el dashboard: energía y dinero positivos en total.
    assert anual[COL_KWH_TOTALES].sum() > 0
    assert anual[COL_BENEFICIO].sum() > 0

    biomasa = pd.read_parquet(paths["biomasa"])
    assert biomasa["_valido_biomasa"].all()
    assert (biomasa["Residuo de Biomasa (Tn)"] >= 0).all()


def test_corrida_repetida_da_el_mismo_resultado(config: Path) -> None:
    primera = pd.read_parquet(_correr(config)["potencial_anual"])
    segunda = pd.read_parquet(_correr(config)["potencial_anual"])
    pd.testing.assert_frame_equal(primera, segunda)


def test_modo_estricto_no_pisa_los_datos_publicados(
    config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    publicado = _correr(config)["potencial_anual"]
    antes = publicado.stat().st_mtime_ns

    alerta = pd.DataFrame({"control": ["x"], "mensaje": ["alerta forzada"]})
    monkeypatch.setattr(run_biomasa, "run_data_checks", lambda *a, **k: alerta)
    with pytest.raises(run_biomasa.DataQualityError):
        _correr(config, estricto=True)
    assert publicado.stat().st_mtime_ns == antes


def test_fraccion_recuperable_escala_la_energia(config: Path) -> None:
    mitad = pd.read_parquet(_correr(config, fraccion_recuperable=0.5)["potencial_anual"])
    todo = pd.read_parquet(_correr(config, fraccion_recuperable=1.0)["potencial_anual"])
    assert todo[COL_KWH_TOTALES].sum() == pytest.approx(2 * mitad[COL_KWH_TOTALES].sum())


# =============================================================
# CLI (lo que ejecuta el cron)
# =============================================================
@pytest.fixture
def avisos(monkeypatch: pytest.MonkeyPatch) -> list[tuple[tuple, dict]]:
    """Captura los avisos en vez de mandarlos (webhook / Telegram)."""
    llamadas: list[tuple[tuple, dict]] = []
    monkeypatch.setattr(run_biomasa, "notify_run_result",
                        lambda *a, **k: llamadas.append((a, k)))
    monkeypatch.setattr(run_biomasa, "setup_logging", lambda *_: None)
    return llamadas


def test_main_sale_con_0_y_avisa_exito(
    config: Path, avisos: list, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.argv", ["optimia-biomasa", "--config", str(config),
                                     "--skip-extract", "--skip-tarifas"])
    assert run_biomasa.main() == 0
    assert len(avisos) == 1
    args, _ = avisos[0]
    assert not args  # sin excepción


def test_main_sale_con_1_y_avisa_el_error(
    tmp_path: Path, avisos: list, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "paths.yaml"
    config.write_text(yaml.safe_dump({"data": {
        k: str(tmp_path / k) for k in ("raw", "reference", "interim", "processed", "audit")
    }}), encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["optimia-biomasa", "--config", str(config),
                                     "--skip-extract", "--skip-tarifas"])
    assert run_biomasa.main() == 1
    args, _ = avisos[0]
    assert isinstance(args[0], Exception)


# =============================================================
# Extracción: una fuente caída no frena el pipeline
# =============================================================
class _Extractor:
    def __init__(self, salida: Path | None = None, fallas: int = 0) -> None:
        self.salida = salida
        self.fallas = fallas
        self.llamadas = 0

    def run_extractor(self, output_dir: Path) -> Path:
        self.llamadas += 1
        if self.llamadas <= self.fallas:
            raise ConnectionError("fuente caída")
        assert self.salida is not None
        return self.salida


def test_extract_reintenta_y_si_sigue_caida_usa_el_raw_en_disco(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    previo = tmp_path / f"20260101000000_{RAW_STEM_MAGYP}.csv"
    previo.write_text("x", encoding="utf-8")
    cba = _Extractor(tmp_path / "cba_nuevo.csv", fallas=1)  # se recupera
    magyp = _Extractor(fallas=99)  # no se recupera
    monkeypatch.setattr(run_biomasa, "extract_cba", cba)
    monkeypatch.setattr(run_biomasa, "extract_magyp", magyp)

    paths = run_biomasa.run_extract_stage(tmp_path, retry_wait=0)
    assert paths == {"cba": tmp_path / "cba_nuevo.csv", "magyp": previo}
    assert cba.llamadas == 2
    assert magyp.llamadas == 2


def test_tarifas_caidas_no_frenan_el_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def caida(**_: object) -> Path:
        raise ConnectionError("energia.gob.ar caída")

    monkeypatch.setattr(run_biomasa.extract_tarifas, "run_extractor", caida)
    assert run_biomasa.run_tarifas_stage(tmp_path / "raw", tmp_path / "ref") is None

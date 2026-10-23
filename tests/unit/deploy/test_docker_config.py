"""Coherencia de la configuración de Docker / Dokploy / cron.

No levanta contenedores (eso lo hace el job ``imagen`` del CI): revisa que
el crontab apunte a módulos y configs que existen y que el compose de
producción cumpla lo que pide Dokploy.
"""

from __future__ import annotations

import importlib.util
import re
import shlex
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
CRONTAB = ROOT / "config" / "crontab"
ENTRYPOINT = ROOT / "deploy" / "cron-entrypoint.sh"
COMPOSE_DEV = ROOT / "docker-compose.yml"
COMPOSE_DOKPLOY = ROOT / "deploy" / "docker-compose.dokploy.yml"

# minuto, hora, día del mes, mes, día de la semana
_RANGOS = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 7)]


def _jobs() -> list[tuple[list[str], list[str]]]:
    """(campos de horario, comando) de cada línea activa del crontab."""
    jobs = []
    for linea in CRONTAB.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        partes = linea.split()
        jobs.append((partes[:5], shlex.split(" ".join(partes[5:]))))
    return jobs


def _compose(path: Path) -> dict[str, Any]:
    datos: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return datos


def _campo_valido(campo: str, minimo: int, maximo: int) -> bool:
    for parte in campo.split(","):
        base, _, paso = parte.partition("/")
        if paso and not paso.isdigit():
            return False
        if base == "*":
            continue
        extremos = base.split("-")
        if not all(e.isdigit() and minimo <= int(e) <= maximo for e in extremos):
            return False
    return True


# =============================================================
# Crontab
# =============================================================
def test_crontab_tiene_los_dos_pipelines() -> None:
    modulos = {cmd[2] for _, cmd in _jobs()}
    assert modulos == {
        "optimia_hv.biomasa.pipelines.run_biomasa",
        "optimia_hv.solar.pipelines.run_solar",
    }


@pytest.mark.parametrize("horario,comando", _jobs())
def test_job_del_crontab_es_valido(horario: list[str], comando: list[str]) -> None:
    assert len(horario) == 5, "supercronic usa 5 campos (sin segundos, no es Ofelia)"
    for campo, (minimo, maximo) in zip(horario, _RANGOS, strict=True):
        assert _campo_valido(campo, minimo, maximo), campo

    assert comando[:2] == ["python", "-m"]
    assert importlib.util.find_spec(comando[2]) is not None, comando[2]
    config = comando[comando.index("--config") + 1]
    assert (ROOT / config).is_file(), config


def test_entrypoint_lanza_supercronic_con_el_crontab() -> None:
    texto = ENTRYPOINT.read_text(encoding="utf-8")
    assert "exec supercronic config/crontab" in texto
    for modulo in re.findall(r"python -m (\S+)", texto):
        assert importlib.util.find_spec(modulo) is not None, modulo


def test_scripts_de_la_imagen_se_versionan_con_lf() -> None:
    attrs = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "*.sh text eol=lf" in attrs
    assert "config/crontab text eol=lf" in attrs


# =============================================================
# Compose
# =============================================================
@pytest.mark.parametrize("path", [COMPOSE_DEV, COMPOSE_DOKPLOY], ids=["dev", "dokploy"])
def test_compose_sin_ofelia_ni_socket_de_docker(path: Path) -> None:
    texto = path.read_text(encoding="utf-8")
    assert "ofelia" not in texto.lower()
    assert "docker.sock" not in texto
    servicios = _compose(path)["services"]
    assert {"cron", "dashboard"} <= set(servicios)
    assert servicios["cron"]["command"] == ["sh", "deploy/cron-entrypoint.sh"]


def test_dokploy_sin_container_name_ni_puertos_al_host() -> None:
    for nombre, servicio in _compose(COMPOSE_DOKPLOY)["services"].items():
        assert "container_name" not in servicio, nombre
        assert "ports" not in servicio, f"{nombre}: el dominio lo publica Traefik"
    assert "8501" in _compose(COMPOSE_DOKPLOY)["services"]["dashboard"]["expose"]


def test_dokploy_guarda_los_datos_en_volumenes_con_nombre() -> None:
    compose = _compose(COMPOSE_DOKPLOY)
    nombrados = set(compose["volumes"])
    for nombre, servicio in compose["services"].items():
        for volumen in servicio.get("volumes", []):
            origen = volumen.split(":")[0]
            # Un bind mount relativo se borra en cada deploy (git clone).
            assert origen in nombrados, f"{nombre}: {volumen}"
    montajes = compose["services"]["cron"]["volumes"]
    assert any(v.endswith(":/app/data") for v in montajes)


def test_dokploy_construye_desde_la_raiz_y_lee_el_env() -> None:
    compose = _compose(COMPOSE_DOKPLOY)
    for nombre, servicio in compose["services"].items():
        build = servicio["build"]
        assert (COMPOSE_DOKPLOY.parent / build["context"] / build["dockerfile"]).is_file()
        assert servicio["env_file"][0]["path"] == ".env", nombre
    assert "healthcheck" in compose["services"]["dashboard"]


def test_variables_del_env_example_llegan_al_cron_en_dev() -> None:
    """Toda variable de .env.example que use un pipeline debe pasar al cron."""
    ejemplo = (ROOT / ".env.example").read_text(encoding="utf-8")
    variables = set(re.findall(r"^([A-Z_]+)=", ejemplo, flags=re.MULTILINE))
    variables -= {"DASHBOARD_PORT"}  # sólo la usa el dashboard
    entorno = _compose(COMPOSE_DEV)["services"]["cron"]["environment"]
    pasadas = {e.split("=")[0] for e in entorno}
    assert variables <= pasadas, variables - pasadas


# =============================================================
# Deploy (GitHub Actions → Dokploy)
# =============================================================
def test_deploy_usa_la_api_de_dokploy_y_no_el_webhook() -> None:
    """El webhook de Dokploy responde 400 con el Autodeploy apagado."""
    texto = (ROOT / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")
    assert "/api/compose.deploy" in texto
    assert "x-api-key" in texto
    assert "DOKPLOY_WEBHOOK_URL" not in texto

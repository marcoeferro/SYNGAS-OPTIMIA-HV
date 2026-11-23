"""Tests del logging estructurado (etl/logging_setup.py)."""

from __future__ import annotations

import io
import json
import logging
import re
import warnings
from pathlib import Path

import httpx
import pytest

from etl.extractors.http_retry import request_with_retry
from etl.logging_setup import (
    ContainerStreamHandler,
    JsonFormatter,
    bind_context,
    get_context,
    new_trace_id,
    set_context,
)
from etl.pipelines.run_etl import setup_logging

# Misma expresión que usa Alloy en el VPS para el label "level"
# (/etc/alloy/config.alloy, loki.process "containers").
ALLOY_LEVEL_RE = re.compile(
    r"(?i)^(?P<net>info|warn|fail|crit|dbug|trce):\s|"
    r"(?:level[\"=:\s]+\"?(?P<lvl>error|err|critical|crit|fatal|panic|warn|warning|"
    r"info|information|notice|debug|trace)\b)|"
    r"(?P<kw>\bprisma:error\b|⨯|\bpanic:|\bfatal\b|\bunhandled\b|\bexception\b|\berror\b)"
)

LOGGING_YML = Path(__file__).resolve().parent.parent / "config" / "logging.yml"


@pytest.fixture
def capture():
    """Logger aislado con JsonFormatter; devuelve (logger, buffer)."""
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(JsonFormatter())
    log = logging.getLogger("etl.test_logging_setup")
    log.handlers = [handler]
    log.setLevel(logging.DEBUG)
    log.propagate = False
    token_ctx = get_context()
    yield log, buf
    set_context(**dict.fromkeys(get_context()))
    set_context(**token_ctx)
    log.handlers = []


def _lines(buf: io.StringIO) -> list[dict]:
    return [json.loads(line) for line in buf.getvalue().splitlines() if line]


def test_linea_json_con_campos_de_ubicacion(capture, monkeypatch):
    log, buf = capture
    log.info("hola %s", "mundo")
    (rec,) = _lines(buf)
    assert rec["level"] == "info"
    assert rec["message"] == "hola mundo"
    assert rec["logger"] == "etl.test_logging_setup"
    assert rec["file"] == "tests/test_logging_setup.py"
    assert rec["function"] == "test_linea_json_con_campos_de_ubicacion"
    assert isinstance(rec["line"], int)
    assert rec["service"] == "etl-biomasa"
    assert {"timestamp", "environment", "host", "pid"} <= rec.keys()
    # Hora con zona horaria (ISO 8601).
    assert re.match(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}[+-]\d\d:\d\d$", rec["timestamp"])


def test_level_va_antes_del_mensaje(capture):
    log, buf = capture
    log.info("error: none")
    line = buf.getvalue().strip()
    assert list(json.loads(line))[:3] == ["timestamp", "level", "message"]
    # Alloy toma el nivel declarado aunque el mensaje diga "error".
    m = ALLOY_LEVEL_RE.search(line)
    assert m and m.group("lvl") == "info"


def test_environment_desde_app_env(monkeypatch, capture):
    monkeypatch.setenv("APP_ENV", "staging")
    log, buf = capture
    log.handlers[0].setFormatter(JsonFormatter())
    log.info("x")
    assert _lines(buf)[0]["environment"] == "staging"


def test_contexto_y_extra(capture):
    log, buf = capture
    trace = new_trace_id()
    set_context(trace_id=trace, stage="extract")
    with bind_context(source="magyp"):
        log.warning("falla", extra={"status_code": 500})
    log.info("afuera")
    dentro, afuera = _lines(buf)
    assert dentro["trace_id"] == trace and len(trace) == 32
    assert dentro["stage"] == "extract"
    assert dentro["source"] == "magyp"
    assert dentro["status_code"] == 500
    assert afuera["trace_id"] == trace
    assert "source" not in afuera


def test_excepcion_con_traza(capture):
    log, buf = capture
    try:
        raise ValueError("dato inválido")
    except ValueError:
        log.exception("Fallo")
    (rec,) = _lines(buf)
    assert rec["level"] == "error"
    assert rec["exception"]["type"] == "ValueError"
    assert rec["exception"]["message"] == "dato inválido"
    assert "Traceback" in rec["exception"]["stacktrace"]


def test_valores_no_serializables_no_rompen(capture):
    log, buf = capture
    log.info("ruta", extra={"path": Path("data/raw")})
    assert _lines(buf)[0]["path"] in ("data/raw", "data\\raw")


def test_request_id_en_reintentos_http(capture, monkeypatch):
    log, buf = capture
    retry_logger = logging.getLogger("etl.extractors.http_retry")
    monkeypatch.setattr(retry_logger, "handlers", log.handlers)
    monkeypatch.setattr(retry_logger, "propagate", False)
    monkeypatch.setattr("etl.extractors.http_retry.time.sleep", lambda s: None)

    calls = iter([500, 500, 200])
    transport = httpx.MockTransport(lambda req: httpx.Response(next(calls)))
    with httpx.Client(transport=transport) as client:
        request_with_retry(client, "get", "https://ejemplo.test/x")
    first, second = _lines(buf)
    assert first["level"] == "warning"
    assert first["request_id"] == second["request_id"]
    assert len(first["request_id"]) == 16
    assert first["status_code"] == 500
    assert first["http_method"] == "GET"
    assert first["url"] == "https://ejemplo.test/x"
    assert (first["attempt"], second["attempt"]) == (1, 2)
    assert first["max_attempts"] == 6
    assert "request_id" not in get_context()

    buf.truncate(0)
    buf.seek(0)
    calls = iter([500, 200])
    with httpx.Client(transport=transport) as client:
        request_with_retry(client, "get", "https://ejemplo.test/y")
    assert _lines(buf)[0]["request_id"] != first["request_id"]


def test_container_stream_handler_escribe_en_log_stream(tmp_path, monkeypatch):
    target = tmp_path / "fd1"
    monkeypatch.setenv("LOG_STREAM", str(target))
    handler = ContainerStreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.emit(logging.makeLogRecord({"msg": "a", "levelno": 20, "levelname": "INFO"}))
    handler.close()
    assert json.loads(target.read_text(encoding="utf-8"))["message"] == "a"


def test_container_stream_handler_vuelve_a_stdout(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LOG_STREAM", str(tmp_path / "no" / "existe"))
    handler = ContainerStreamHandler()
    assert "no se pudo abrir" in capsys.readouterr().err
    handler.close()


@pytest.fixture
def restore_logging():
    etl_logger = logging.getLogger("etl")
    root = logging.getLogger()
    saved = (etl_logger.handlers[:], etl_logger.level, etl_logger.propagate,
             root.handlers[:], root.level)
    yield
    for h in etl_logger.handlers + root.handlers:
        if h not in saved[0] + saved[3]:
            h.close()
    etl_logger.handlers, etl_logger.level, etl_logger.propagate = saved[:3]
    root.handlers, root.level = saved[3], saved[4]
    logging.captureWarnings(False)


def test_setup_logging_json_y_warnings(tmp_path, monkeypatch, restore_logging):
    out = tmp_path / "stream.log"
    monkeypatch.setenv("LOG_STREAM", str(out))
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    monkeypatch.chdir(tmp_path)  # logs/pipeline.log queda en tmp
    setup_logging(LOGGING_YML)

    logging.getLogger("etl.algo").info("no sale por consola (LOG_LEVEL=WARNING)")
    logging.getLogger("etl.algo").warning("sí sale")
    with warnings.catch_warnings():
        warnings.simplefilter("always")
        warnings.warn("concat con vacíos", FutureWarning, stacklevel=1)
    for h in logging.getLogger().handlers + logging.getLogger("etl").handlers:
        h.flush()

    recs = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert [r["message"] for r in recs][0] == "sí sale"
    assert recs[1]["logger"] == "py.warnings"
    assert recs[1]["level"] == "warning"
    assert "FutureWarning" in recs[1]["message"]
    # El archivo guarda todo (DEBUG), también en JSON.
    file_lines = (tmp_path / "logs" / "pipeline.log").read_text(encoding="utf-8").splitlines()
    assert json.loads(file_lines[0])["message"].startswith("no sale")


def test_setup_logging_formato_texto(tmp_path, monkeypatch, restore_logging):
    out = tmp_path / "stream.log"
    monkeypatch.setenv("LOG_STREAM", str(out))
    monkeypatch.setenv("LOG_FORMAT", "text")
    monkeypatch.chdir(tmp_path)
    setup_logging(LOGGING_YML)
    logging.getLogger("etl.algo").info("legible")
    for h in logging.getLogger("etl").handlers:
        h.flush()
    assert "| INFO     | etl.algo | legible" in out.read_text(encoding="utf-8")

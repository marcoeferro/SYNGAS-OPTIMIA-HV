"""
Logging estructurado del ETL: una línea JSON por evento.

Cada línea responde qué pasó, cuándo, dónde y en qué corrida::

    {"timestamp": "2026-11-23T06:02:16.412-03:00", "level": "warning",
     "message": "HTTP 500 en intento 1/6 (...). Reintento en 2 s",
     "logger": "etl.extractors.http_retry", "module": "http_retry",
     "function": "request_with_retry", "file": "etl/extractors/http_retry.py",
     "line": 98, "service": "etl-biomasa", "version": "0.4.0",
     "environment": "production", "host": "b9a99ee8be79", "pid": 812,
     "trace_id": "4f1c...", "stage": "extract", "source": "magyp",
     "request_id": "a1b2c3d4e5f60718", "http_method": "GET", "url": "...",
     "status_code": 500, "attempt": 1, "max_attempts": 6, "retry_in_s": 2.0}

- ``level`` va segundo, antes del mensaje: Alloy (VPS) toma el primer
  ``"level":"..."`` de la línea, así un mensaje que menciona "error" no
  cambia el nivel.
- ``trace_id`` identifica la corrida completa; ``request_id``, cada pedido
  HTTP con sus reintentos. Se agregan con :func:`set_context` o
  :func:`bind_context` y viajan solos a todos los logs de esa corrida.
- Los campos pasados con ``extra={...}`` se suman a la línea.
- Una excepción agrega ``exception`` con tipo, mensaje y traza.

Variables de entorno:

- ``APP_ENV``: entorno (``production``, ``staging``, ``local``).
- ``LOG_LEVEL``: nivel mínimo de la consola (por defecto ``INFO``).
- ``LOG_FORMAT``: ``json`` (por defecto) o ``text`` para leer a mano.
- ``LOG_STREAM``: archivo donde escribe la consola en vez de stdout. En
  ``etl_worker`` vale ``/proc/1/fd/1``: la salida del proceso principal
  del contenedor, para que los logs salgan en ``docker logs
  biomasa_etl_worker`` a medida que ocurren, y no todos juntos dentro del
  mensaje de Ofelia al terminar la corrida.
"""

from __future__ import annotations

import contextlib
import contextvars
import json
import logging
import os
import socket
import sys
import uuid
from collections.abc import Iterator
from datetime import datetime
from importlib import metadata
from pathlib import Path
from typing import IO, Any, Final

SERVICE_NAME: Final[str] = "etl-biomasa"
DEFAULT_ENVIRONMENT: Final[str] = "local"

_context: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "etl_log_context", default=None
)


def _current() -> dict[str, Any]:
    return _context.get() or {}

# Atributos propios de LogRecord: lo que no esté acá vino por ``extra``.
_RECORD_ATTRS: Final[frozenset[str]] = frozenset(
    vars(logging.LogRecord("", 0, "", 0, "", None, None)).keys()
    | {"message", "asctime", "taskName"}
)

_PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent


def new_trace_id() -> str:
    """Identificador de corrida (32 hex, compatible con W3C trace-id)."""
    return uuid.uuid4().hex


def new_request_id() -> str:
    """Identificador corto de un pedido HTTP (16 hex)."""
    return uuid.uuid4().hex[:16]


def get_context() -> dict[str, Any]:
    """Copia del contexto que se agrega a cada línea."""
    return dict(_current())


def set_context(**fields: Any) -> None:
    """
    Agrega campos al contexto hasta el final de la corrida (o del hilo).

    Un valor ``None`` borra el campo.
    """
    ctx = {**_current(), **fields}
    _context.set({k: v for k, v in ctx.items() if v is not None})


@contextlib.contextmanager
def bind_context(**fields: Any) -> Iterator[None]:
    """Agrega campos al contexto solo dentro del bloque ``with``."""
    token = _context.set(
        {k: v for k, v in {**_current(), **fields}.items() if v is not None}
    )
    try:
        yield
    finally:
        _context.reset(token)


def _package_version() -> str | None:
    try:
        return metadata.version(SERVICE_NAME)
    except metadata.PackageNotFoundError:
        return None


def _relative_path(pathname: str) -> str:
    """Ruta del archivo relativa al proyecto (``etl/...``) si se puede."""
    try:
        return Path(pathname).resolve().relative_to(_PROJECT_ROOT).as_posix()
    except ValueError:
        return pathname


class JsonFormatter(logging.Formatter):
    """Formatea cada registro como una línea JSON (ver docstring del módulo)."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._static = {
            "service": SERVICE_NAME,
            "version": _package_version(),
            "environment": os.environ.get("APP_ENV") or DEFAULT_ENVIRONMENT,
            "host": socket.gethostname(),
        }

    def format(self, record: logging.LogRecord) -> str:
        """Devuelve el registro como una línea JSON."""
        timestamp = (
            datetime.fromtimestamp(record.created)
            .astimezone()
            .isoformat(timespec="milliseconds")
        )
        payload: dict[str, Any] = {
            "timestamp": timestamp,
            "level": record.levelname.lower(),
            "message": record.getMessage(),
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "file": _relative_path(record.pathname),
            "line": record.lineno,
            **{k: v for k, v in self._static.items() if v is not None},
            "pid": record.process,
        }
        if record.threadName and record.threadName != "MainThread":
            payload["thread"] = record.threadName
        payload.update(_current())
        for key, value in vars(record).items():
            if key not in _RECORD_ATTRS and not key.startswith("_"):
                payload[key] = value

        if record.exc_info and record.exc_info[0] is not None:
            exc_type, exc_value, _tb = record.exc_info
            payload["exception"] = {
                "type": exc_type.__name__,
                "message": str(exc_value),
                "stacktrace": self.formatException(record.exc_info),
            }
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


class ContainerStreamHandler(logging.StreamHandler):
    """
    StreamHandler que escribe en ``LOG_STREAM`` si está definida.

    Si no se puede abrir (fuera de Docker, sin permiso), vuelve a stdout y
    lo avisa una vez por stderr.
    """

    def __init__(self, stream: IO[str] | None = None) -> None:
        target = os.environ.get("LOG_STREAM")
        opened: IO[str] | None = None
        if target:
            try:
                opened = open(target, "a", encoding="utf-8", buffering=1)  # noqa: SIM115
            except OSError as exc:
                print(
                    f"LOG_STREAM={target} no se pudo abrir ({exc}); se usa stdout",
                    file=sys.stderr,
                )
        self._owned = opened
        out = opened or stream or sys.stdout
        # Consola de Windows (cp1252): "→" o "ó" cortaban la línea con un
        # "Logging error". Los logs se escriben siempre en UTF-8.
        encoding = (getattr(out, "encoding", None) or "").lower().replace("-", "")
        if opened is None and encoding not in ("", "utf8") and hasattr(out, "reconfigure"):
            out.reconfigure(encoding="utf-8")
        super().__init__(out)

    def close(self) -> None:
        """Cierra el handler y el archivo de ``LOG_STREAM`` si lo abrió."""
        try:
            super().close()
        finally:
            if self._owned is not None:
                self._owned.close()
                self._owned = None

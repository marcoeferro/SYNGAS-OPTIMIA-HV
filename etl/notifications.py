"""
Avisos del ETL: fallas y alertas de calidad.

Sin avisos, un ETL que falla o publica datos dudosos sólo deja rastro en el
log. Este módulo manda un mensaje corto a los canales configurados por
variables de entorno (ninguno por defecto):

- ``NOTIFY_WEBHOOK_URL``: webhook entrante de Slack, Discord, Microsoft
  Teams o Google Chat (se envía JSON con ``text`` y ``content``, que cubre a
  todos), o cualquier servicio que acepte ese formato.
- ``TELEGRAM_BOT_TOKEN`` y ``TELEGRAM_CHAT_ID``: mensaje de un bot de
  Telegram.
- ``NOTIFY_ON_SUCCESS``: ``1``/``true`` para avisar también las corridas
  sin problemas (por defecto sólo fallas y alertas).

Un aviso que no se puede enviar nunca hace fallar el ETL: se registra en el
log y se sigue.
"""

from __future__ import annotations

import logging
import os
import socket
from typing import Final

import httpx
import pandas as pd

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS: Final[float] = 15.0
MAX_ALERTAS_EN_MENSAJE: Final[int] = 10
TELEGRAM_API: Final[str] = "https://api.telegram.org/bot{token}/sendMessage"
ICONOS: Final[dict[str, str]] = {"error": "🔴", "alerta": "🟠", "ok": "🟢"}


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "si", "sí", "yes"}


def canales_configurados() -> list[str]:
    """Nombres de los canales con configuración completa."""
    canales = []
    if os.environ.get("NOTIFY_WEBHOOK_URL"):
        canales.append("webhook")
    if os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"):
        canales.append("telegram")
    return canales


def notify(nivel: str, titulo: str, detalle: str = "") -> list[str]:
    """
    Envía un aviso a todos los canales configurados.

    Args:
        nivel: ``"error"``, ``"alerta"`` u ``"ok"``.
        titulo: Primera línea del mensaje.
        detalle: Texto adicional (opcional).

    Returns:
        Canales a los que se envió con éxito.
    """
    host = socket.gethostname()
    texto = f"{ICONOS.get(nivel, '')} ETL biomasa ({host}): {titulo}".strip()
    if detalle:
        texto += f"\n{detalle}"
    enviados: list[str] = []
    webhook = os.environ.get("NOTIFY_WEBHOOK_URL")
    if webhook:
        try:
            r = httpx.post(
                webhook, json={"text": texto, "content": texto[:2000]},
                timeout=TIMEOUT_SECONDS,
            )
            r.raise_for_status()
            enviados.append("webhook")
        except httpx.HTTPError as exc:
            # El mensaje de httpx incluye la URL, que es secreta: no se loguea.
            logger.warning("No se pudo enviar el aviso por webhook (%s)", type(exc).__name__)
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat:
        try:
            r = httpx.post(
                TELEGRAM_API.format(token=token),
                json={"chat_id": chat, "text": texto[:4000]},
                timeout=TIMEOUT_SECONDS,
            )
            r.raise_for_status()
            enviados.append("telegram")
        except httpx.HTTPError as exc:
            # El mensaje de httpx incluye la URL con el token: no se loguea.
            logger.warning(
                "No se pudo enviar el aviso por Telegram (%s)", type(exc).__name__
            )
    return enviados


def resumen_alertas(df_alertas: pd.DataFrame) -> str:
    """Una línea por alerta (hasta ``MAX_ALERTAS_EN_MENSAJE``)."""
    lineas = []
    for a in df_alertas.head(MAX_ALERTAS_EN_MENSAJE).itertuples(index=False):
        var = f"{a.variacion:+.0%}" if pd.notna(a.variacion) else "s/d"
        lineas.append(f"• {a.control} · {a.entidad}: {var} (umbral {a.umbral:.0%})")
    resto = len(df_alertas) - MAX_ALERTAS_EN_MENSAJE
    if resto > 0:
        lineas.append(f"… y {resto} más")
    return "\n".join(lineas)


def notify_run_result(
    error: BaseException | None = None,
    df_alertas: pd.DataFrame | None = None,
    estricto: bool = False,
) -> list[str]:
    """
    Aviso de fin de corrida según el resultado.

    - Falla → error (con la causa).
    - Alertas de calidad → alerta (en modo estricto, además, los datos
      publicados no se reemplazaron).
    - Sin problemas → sólo si ``NOTIFY_ON_SUCCESS`` está activo.
    """
    if not canales_configurados():
        return []
    hay_alertas = df_alertas is not None and not df_alertas.empty
    if error is not None and not (estricto and hay_alertas):
        return notify("error", "la corrida falló", f"{type(error).__name__}: {error}"[:1500])
    if hay_alertas:
        assert df_alertas is not None
        titulo = f"{len(df_alertas)} alerta(s) de calidad"
        if estricto:
            titulo += " — modo estricto: NO se publicaron los datos nuevos"
        detalle = resumen_alertas(df_alertas)
        detalle += "\nDetalle: dashboard → Auditoría de datos → Alertas de calidad."
        return notify("alerta", titulo, detalle)
    if _env_flag("NOTIFY_ON_SUCCESS"):
        return notify("ok", "corrida completada sin alertas")
    return []

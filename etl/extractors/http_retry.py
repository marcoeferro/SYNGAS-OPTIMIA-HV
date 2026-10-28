"""
Política de reintentos HTTP compartida por los extractores.

Los servidores de las fuentes devuelven errores transitorios: MAGyP limita
ráfagas con 429 y SharePoint (Bolsa de Cereales de Córdoba) responde 503
cuando aplica *throttling*, aunque el archivo esté disponible. Ante esos
códigos, y ante cortes de red, se reintenta con backoff exponencial;
si el servidor envía ``Retry-After`` se respeta ese tiempo.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Final

import httpx

logger = logging.getLogger(__name__)

MAX_RETRIES: Final[int] = 6
INITIAL_RETRY_DELAY: Final[float] = 2.0
MAX_RETRY_DELAY: Final[float] = 60.0
RETRYABLE_STATUS_CODES: Final[frozenset[int]] = frozenset({429, 500, 502, 503, 504})
RETRYABLE_ERRORS: Final[tuple[type[Exception], ...]] = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.RemoteProtocolError,
)


def _retry_after(response: httpx.Response, default: float) -> float:
    """Segundos indicados por ``Retry-After`` (si es numérico) o ``default``."""
    value = response.headers.get("Retry-After")
    try:
        return min(float(value), MAX_RETRY_DELAY) if value else default
    except ValueError:
        return default


def request_with_retry(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    max_retries: int = MAX_RETRIES,
    initial_delay: float = INITIAL_RETRY_DELAY,
    retry_status: frozenset[int] = RETRYABLE_STATUS_CODES,
    **kwargs: Any,
) -> httpx.Response:
    """
    Realiza una solicitud HTTP con reintentos ante errores transitorios.

    Se reintenta ante los códigos de ``retry_status`` (429, 500, 502, 503,
    504) y ante errores de red (conexión rechazada o cortada, timeouts),
    con backoff exponencial (2, 4, 8, ... s, máximo 60 s) o el tiempo de
    ``Retry-After``.

    Args:
        client: Cliente HTTP utilizado para realizar la solicitud.
        method: Método HTTP, por ejemplo GET o POST.
        url: URL del recurso solicitado.
        max_retries: Cantidad máxima de intentos.
        initial_delay: Espera antes del segundo intento (se duplica).
        retry_status: Códigos HTTP que se reintentan.
        **kwargs: Argumentos adicionales para ``client.request()``.

    Returns:
        Respuesta HTTP exitosa.

    Raises:
        httpx.HTTPStatusError: Ante un error HTTP no reintentable o si se
            agotan los intentos.
        httpx.RequestError: Si persiste el error de red.
    """
    delay = initial_delay
    for attempt in range(1, max_retries + 1):
        last = attempt == max_retries
        try:
            response = client.request(method, url, **kwargs)
        except RETRYABLE_ERRORS as exc:
            if last:
                raise
            logger.warning(
                "%s en intento %d/%d (%s). Reintento en %.0f s",
                type(exc).__name__, attempt, max_retries, url, delay,
            )
            time.sleep(delay)
            delay = min(delay * 2, MAX_RETRY_DELAY)
            continue

        if response.status_code not in retry_status or last:
            response.raise_for_status()
            return response

        wait = _retry_after(response, delay)
        logger.warning(
            "HTTP %d en intento %d/%d (%s). Reintento en %.0f s",
            response.status_code, attempt, max_retries, url, wait,
        )
        time.sleep(wait)
        delay = min(delay * 2, MAX_RETRY_DELAY)
    raise AssertionError("inalcanzable")

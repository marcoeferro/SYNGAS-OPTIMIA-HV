"""Tests de los avisos del ETL (``etl.notifications``)."""

from __future__ import annotations

from typing import Any

import httpx
import pandas as pd
import pytest

from etl import notifications as nt

ENV_VARS = ("NOTIFY_WEBHOOK_URL", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "NOTIFY_ON_SUCCESS")


@pytest.fixture
def enviados(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Captura los POST en lugar de enviarlos; sin canales configurados."""
    for var in ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    calls: list[dict[str, Any]] = []

    def fake_post(url: str, json: dict[str, Any], timeout: float) -> httpx.Response:
        calls.append({"url": url, "json": json})
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr(nt.httpx, "post", fake_post)
    return calls


def _alertas(n: int = 1) -> pd.DataFrame:
    return pd.DataFrame({
        "control": ["salto_tarifa"] * n,
        "entidad": ["ENERSA"] * n,
        "variacion": [0.94] * n,
        "umbral": [0.5] * n,
    })


def test_sin_canales_no_envia_nada(enviados: list[dict[str, Any]]) -> None:
    assert nt.notify_run_result(RuntimeError("x")) == []
    assert enviados == []


def test_falla_avisa_por_webhook_y_telegram(
    enviados: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NOTIFY_WEBHOOK_URL", "https://hooks.example/abc")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    out = nt.notify_run_result(RuntimeError("MAGyP no responde"))
    assert out == ["webhook", "telegram"]
    assert "falló" in enviados[0]["json"]["text"]
    assert "MAGyP no responde" in enviados[0]["json"]["text"]
    assert enviados[1]["url"] == "https://api.telegram.org/bot123:tok/sendMessage"
    assert enviados[1]["json"]["chat_id"] == "42"


def test_alertas_y_modo_estricto(
    enviados: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NOTIFY_WEBHOOK_URL", "https://hooks.example/abc")
    nt.notify_run_result(RuntimeError("estricto"), _alertas(12), estricto=True)
    texto = enviados[0]["json"]["text"]
    assert "12 alerta(s)" in texto and "NO se publicaron" in texto
    assert "salto_tarifa · ENERSA: +94%" in texto
    assert "… y 2 más" in texto


def test_exito_sin_alertas_solo_si_se_pide(
    enviados: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NOTIFY_WEBHOOK_URL", "https://hooks.example/abc")
    assert nt.notify_run_result(df_alertas=_alertas(0)) == []
    monkeypatch.setenv("NOTIFY_ON_SUCCESS", "1")
    assert nt.notify_run_result(df_alertas=_alertas(0)) == ["webhook"]


def test_un_aviso_fallido_no_rompe_el_etl(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NOTIFY_WEBHOOK_URL", "https://hooks.example/abc")

    def falla(*args: Any, **kwargs: Any) -> httpx.Response:
        raise httpx.ConnectError("sin red")

    monkeypatch.setattr(nt.httpx, "post", falla)
    assert nt.notify("error", "x") == []

"""Tests del extractor de Growatt (funciones puras y cliente con transporte simulado)."""

from __future__ import annotations

import json
from datetime import date, datetime

import httpx
import pytest

from optimia_hv.solar.configuracion import CredencialesGrowatt
from optimia_hv.solar.extractors import growatt


class TestRellenarHuecos:
    def test_promedia_entre_dos_vecinos(self) -> None:
        assert growatt.rellenar_huecos([10, 0, 20]) == [10, 15, 20]

    def test_historico_usa_un_solo_vecino(self) -> None:
        assert growatt.rellenar_huecos([0, 8, 0], un_vecino=True) == [8, 8, 8]

    def test_diario_deja_en_cero_sin_dos_vecinos(self) -> None:
        assert growatt.rellenar_huecos([0, 8, 0], un_vecino=False) == [0, 8, 0]

    def test_puente_con_mes_anterior(self) -> None:
        assert growatt.rellenar_huecos([0, 12], previo=10) == [11, 12]

    def test_usa_valores_originales_no_rellenados(self) -> None:
        # Dos ceros seguidos: el segundo no usa el primero ya rellenado.
        assert growatt.rellenar_huecos([10, 0, 0, 20], un_vecino=False) == [10, 0, 0, 20]

    def test_acepta_textos_y_nulos(self) -> None:
        assert growatt.rellenar_huecos(["10", None, "20"]) == [10, 15, 20]


def test_ultimo_positivo() -> None:
    assert growatt.ultimo_positivo([5, 7, 0, 0]) == 7
    assert growatt.ultimo_positivo([0, 0], defecto=3) == 3


class TestSerieDiariaMes:
    def test_corta_en_el_limite_y_redondea(self) -> None:
        df = growatt.serie_diaria_mes("2026-09", [1.234, 2, 3, 4], hasta=date(2026, 9, 2))
        assert df["fecha"].tolist() == [date(2026, 9, 1), date(2026, 9, 2)]
        assert df["energia"].tolist() == [1.23, 2.0]

    def test_descarta_ceros_salvo_que_se_pida(self) -> None:
        valores = [0, 5, 6]
        sin = growatt.serie_diaria_mes("2026-09", valores, date(2026, 9, 30), un_vecino=False)
        con = growatt.serie_diaria_mes(
            "2026-09", valores, date(2026, 9, 30), un_vecino=False, conservar_ceros=True
        )
        assert len(sin) == 2
        assert len(con) == 3 and con["energia"].iloc[0] == 0

    def test_no_pasa_de_fin_de_mes(self) -> None:
        df = growatt.serie_diaria_mes("2026-02", [1.0] * 31, hasta=date(2026, 12, 31))
        assert len(df) == 28


class TestSerieIntradia:
    def test_filtra_cada_15_min(self) -> None:
        pac = list(range(12))  # 00:00 a 00:55 cada 5 min
        df = growatt.serie_intradia("2026-09-15", pac, paso_min=15)
        assert df["fecha_hora"].tolist() == [
            datetime(2026, 9, 15, 0, m) for m in (0, 15, 30, 45)
        ]
        assert df["potencia_w"].tolist() == [0, 3, 6, 9]

    def test_cada_5_min_y_nulos_en_cero(self) -> None:
        df = growatt.serie_intradia(date(2026, 9, 15), [None, "", 100.456], paso_min=5)
        assert df["potencia_w"].tolist() == [0.0, 0.0, 100.46]

    def test_corta_a_las_24_horas(self) -> None:
        df = growatt.serie_intradia("2026-09-15", [1.0] * 300, paso_min=5)
        assert len(df) == 288

    def test_paso_invalido(self) -> None:
        with pytest.raises(ValueError):
            growatt.serie_intradia("2026-09-15", [1.0], paso_min=7)


def test_meses_entre_cruza_el_anio() -> None:
    assert growatt.meses_entre(date(2025, 11, 20), date(2026, 2, 1)) == [
        "2025-11", "2025-12", "2026-01", "2026-02",
    ]


def _cliente_simulado(respuestas: dict[str, object]) -> growatt.ClienteGrowatt:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/login":
            return httpx.Response(200, json={"result": 1})
        return httpx.Response(200, json=respuestas[request.url.path])

    creds = CredencialesGrowatt(usuario="u", clave="c", plant_id="123")
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return growatt.ClienteGrowatt(creds, client=client)


def test_cliente_lee_energia_mensual_y_potencia() -> None:
    cliente = _cliente_simulado({
        "/energy/compare/getDevicesMonthChart": {"obj": [{"datas": {"energy": [1, 2]}}]},
        "/energy/compare/getDevicesDayChart": {"obj": [{"datas": {"pac": [0, 50]}}]},
    })
    with cliente:
        assert cliente.energia_mensual("2026-09") == [1, 2]
        assert cliente.potencia_dia("2026-09-15") == [0, 50]


def test_cliente_respuesta_vacia() -> None:
    cliente = _cliente_simulado({"/energy/compare/getDevicesMonthChart": {"obj": []}})
    with cliente:
        assert cliente.energia_mensual("2026-09") == []


def test_payload_incluye_planta() -> None:
    enviados: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        enviados.append(request.content.decode())
        return httpx.Response(200, json={"obj": [{"datas": {"energy": []}}]})

    creds = CredencialesGrowatt(usuario="u", clave="c", plant_id="999")
    client = httpx.Client(transport=httpx.MockTransport(handler))
    cliente = growatt.ClienteGrowatt(creds, client=client)
    cliente.energia_mensual("2026-09")
    cuerpo = httpx.QueryParams(enviados[0])
    assert cuerpo["plantId"] == "999"
    assert json.loads(cuerpo["jsonData"])[0]["sn"] == "999"


def test_diaria_mes_actual_dia_1_revisa_mes_anterior() -> None:
    class Falso:
        def energia_mensual(self, mes: str) -> list[float]:
            assert mes == "2026-09"
            return [5.0] * 30

    df = growatt.diaria_mes_actual(Falso(), hoy=date(2026, 10, 1))  # type: ignore[arg-type]
    assert df["fecha"].max() == date(2026, 9, 30)


def test_credenciales_faltantes(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("GROWATT_USER", "GROWATT_PASSWORD", "GROWATT_PLANT_ID"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(RuntimeError, match="GROWATT_USER"):
        CredencialesGrowatt.desde_entorno()

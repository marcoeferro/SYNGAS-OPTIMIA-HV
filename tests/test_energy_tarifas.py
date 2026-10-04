"""Tests del cálculo energético-financiero y del extractor de tarifas."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pandas as pd
import pytest

from etl.extractors import scrape_tarifas as st
from etl.transformers.energy_finance import (
    COL_BENEFICIO,
    COL_EQUIPOS,
    COL_KWH_TOTALES,
    COL_TARIFA_PROXY,
    add_energy_finance_columns,
)

CFG = {
    "parametros_pp30": {
        "consumo_especifico_kg_kwh": 1.1,
        "humedad_pct_default": 12.0,
        "factor_autoconsumo_default": 0.6,
        "potencia_nominal_kw": 25.0,
        "disponibilidad": 0.8,
    },
    "distribuidoras": {
        "A": {"tarifa_compra_kwh": 100.0, "tarifa_inyeccion_kwh": 40.0},
        "B": {"tarifa_compra_kwh": 80.0, "tarifa_inyeccion_kwh": 30.0, "es_proxy": True},
    },
    "provincia_a_distribuidora": {"cordoba": "A", "buenos aires": "B"},
}


def test_cadena_energetica_no_descuenta_humedad_dos_veces() -> None:
    df = pd.DataFrame({"Provincia": ["cordoba"], "Residuo Recuperable (Tn)": [1.0]})
    out = add_energy_finance_columns(df, config=CFG)
    # 1000 kg MS -> 1000/0.88 kg tal cual -> /1.1 kg/kWh
    kwh = 1000 / 0.88 / 1.1
    assert out[COL_KWH_TOTALES].iloc[0] == pytest.approx(kwh)
    beneficio = kwh * 0.6 * 100 + kwh * 0.4 * 40
    assert out[COL_BENEFICIO].iloc[0] == pytest.approx(beneficio)
    assert out[COL_EQUIPOS].iloc[0] == pytest.approx(kwh / 25 / (8760 * 0.8))


def test_tarifa_proxy_y_provincia_sin_tarifa() -> None:
    df = pd.DataFrame({"Provincia": ["buenos aires", "chaco"],
                       "Residuo Recuperable (Tn)": [1.0, 1.0]})
    out = add_energy_finance_columns(df, config=CFG)
    assert bool(out[COL_TARIFA_PROXY].iloc[0])
    assert pd.isna(out[COL_BENEFICIO].iloc[1])


# ---------------- Extractor de tarifas ----------------

PDF_TEXT = """CUADRO TARIFARIO
Indice: TARIFA Nº 3 pag. 4
TARIFA Nº 2 - GENERAL Y DE SERVICIOS
Primeros 150 kWh/mes $/kWh 54,04222
TARIFA Nº 3 - GRANDES CONSUMOS
Cargo Fijo $/mes 25.300,00
Cargo por potencia $/kW-mes 9.876,54
Energía Pico $/kWh 70,1234
Energía Resto $/kWh 65,5000
Energía Valle $/kWh 60,0000
TARIFA Nº 4 - RURAL
USUARIOS GENERADORES - Ley 27.424
Energía inyectada $/kWh 35,21
"""


def test_parse_ar_number() -> None:
    assert st.parse_ar_number("1.234,56") == 1234.56
    assert st.parse_ar_number("12.500") == 12500.0
    assert st.parse_ar_number("54,04222") == pytest.approx(54.04222)
    assert st.parse_ar_number("abc") is None


def test_parse_tariff_text_toma_t3_y_omite_indice() -> None:
    out = st.parse_tariff_text(PDF_TEXT)
    assert out["valores_compra_detectados"] == [70.1234, 65.5, 60.0]
    assert out["tarifa_compra_kwh"] == 65.5
    assert out["tarifa_inyeccion_kwh"] == 35.21
    assert out["cargo_fijo_mensual"] == 25300.0


def test_discover_pdf_links_ordena_por_fecha() -> None:
    html = (
        '<a href="cuadro-tarifario-publicado-170125-aplicacion-190125.pdf">a</a>'
        '<a href="/docs/cuadro-tarifario/cuadro-tarifario-publicado-290825-'
        'aplicacion-010925.pdf">b</a><a href="formulario.pdf">c</a>'
    )
    links = st.discover_pdf_links(html, st.EPEC_INDEX_URL)
    assert len(links) == 2
    assert "010925" in links[0]


def test_validacion_rechaza_saltos_e_inyeccion_mayor() -> None:
    parsed = {"tarifa_compra_kwh": 1000.0, "tarifa_inyeccion_kwh": 2000.0,
              "cargo_fijo_mensual": None}
    rej = st.validate_parsed(parsed, {"tarifa_compra_kwh": 100.0})
    assert "tarifa_inyeccion_kwh" in rej and "tarifa_compra_kwh" in rej


def _fake_downloader(pages: dict[str, bytes]):
    def download(url: str) -> bytes:
        if url in pages:
            return pages[url]
        request = httpx.Request("GET", url)
        raise httpx.HTTPStatusError("404", request=request,
                                    response=httpx.Response(404, request=request))
    return download


def test_run_extractor_end_to_end(tmp_path: Path) -> None:
    pdf_url = st.EPEC_INDEX_URL + "cuadro-tarifario-publicado-010926-aplicacion-010926.pdf"
    pages = {
        st.EPEC_INDEX_URL: f'<a href="{pdf_url}">Cuadro tarifario</a>'.encode(),
        pdf_url: b"%PDF-1.4 fake",
        # EPE devuelve HTML con HTTP 200 en lugar de PDF: debe ignorarse.
        st.EPE_INDEX_URL: b'<a href="/cuadro_tarifario.pdf">x</a>',
        "https://www.epe.santafe.gov.ar/cuadro_tarifario.pdf": b"<html>login</html>",
    }
    out = st.run_extractor(
        raw_dir=tmp_path / "raw",
        reference_dir=tmp_path / "ref",
        downloader=_fake_downloader(pages),
        text_extractor=lambda content: PDF_TEXT,
    )
    data = json.loads(out.read_text(encoding="utf-8"))
    epec = data["distribuidoras"]["EPEC_CORDOBA"]
    assert epec["tarifa_compra_kwh"] == 65.5
    assert epec["estado_campos"]["tarifa_compra_kwh"] == st.STATUS_PARSED
    assert epec["documento_fuente"] == pdf_url
    epe = data["distribuidoras"]["EPE_SANTA_FE"]
    assert epe["estado_campos"]["tarifa_compra_kwh"] == st.STATUS_BASELINE
    assert data["resumen_extraccion"]["distribuidoras_con_tarifa_extraida"] == 1

    # Segunda corrida sin red: EPEC conserva el valor extraído como fallback.
    # Se renombra la primera salida a un timestamp anterior para evitar
    # colisión de nombres dentro del mismo segundo.
    out.rename(out.with_name("20000101000000_tarifas.json"))
    out2 = st.run_extractor(
        raw_dir=tmp_path / "raw",
        reference_dir=tmp_path / "ref",
        downloader=_fake_downloader({}),
        text_extractor=lambda content: PDF_TEXT,
    )
    data2 = json.loads(out2.read_text(encoding="utf-8"))
    epec2 = data2["distribuidoras"]["EPEC_CORDOBA"]
    assert epec2["tarifa_compra_kwh"] == 65.5
    assert epec2["estado_campos"]["tarifa_compra_kwh"] == st.STATUS_FALLBACK

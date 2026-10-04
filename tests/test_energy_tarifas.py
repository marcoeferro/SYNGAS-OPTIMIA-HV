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
    # Banda "Resto" de la T3 (no la T2 ni el índice).
    assert out["valores_compra_detectados"] == [65.5]
    assert out["tarifa_compra_kwh"] == 65.5
    assert out["tarifa_inyeccion_kwh"] == 35.21
    assert out["cargo_fijo_mensual"] == 25300.0


def test_discover_links_ordena_por_vigencia() -> None:
    base = "https://www.epec.com.ar/docs/cuadro-tarifario/"
    html = (
        '<a href="cuadro-tarifario-publicado-170125-aplicacion-190125.pdf">a</a>'
        '<a href="/docs/cuadro-tarifario/cuadro-tarifario-publicado-290825-'
        'aplicacion-010925.pdf">b</a><a href="formulario.pdf">c</a>'
    )
    links = st.discover_document_links(html, base)
    assert len(links) == 2
    assert "010925" in links[0]


def test_indice_compartido_filtra_por_distribuidora() -> None:
    html = (
        '<a href="/adj/IF-1.pdf">Cuadro tarifario EDEN S.A.</a>'
        '<a href="/adj/IF-2.pdf">Cuadro tarifario EDEA S.A.</a>'
    )
    links = st.discover_document_links(html, "https://oceba.gba.gov.ar/x", ("edea",))
    assert links == ["https://oceba.gba.gov.ar/adj/IF-2.pdf"]


@pytest.mark.parametrize(("url", "esperado"), [
    ("https://x/cuadros_tarifarios_desde_2025/DPEC/2026_04_DPEC.pdf", "2026-04"),
    ("https://www.edenor.com/files/2026-01/Cuadro-Tarifario.pdf", "2026-01"),
    ("https://x/Cuadro_Tarifario_Marzo_2026_EDESA.pdf", "2026-03"),
    ("https://x/cuadro-tarifario-publicado-290825-aplicacion-010925.pdf", "2025-09"),
    ("https://x/CuadroTarifario.pdf", None),
])
def test_vigencia_from_name(url: str, esperado: str | None) -> None:
    assert st.vigencia_from_name(url) == esperado


def test_vigencia_from_text() -> None:
    txt = "Cuadro Tarifario vigencia a partir del 1° de septiembre de 2026 EDESUR"
    assert st.vigencia_from_text(txt) == "2026-09"
    assert st.vigencia_from_text("Periodo: OCTUBRE 2025 TARIFA RESIDENCIAL") == "2025-10"


def test_registro_cubre_todas_las_provincias_salvo_chubut() -> None:
    from etl.reference.distribuidoras import DISTRIBUIDORAS, PROVINCIA_A_DISTRIBUIDORA

    provincias = {
        "buenos aires", "catamarca", "chaco", "cordoba", "corrientes", "entre rios",
        "formosa", "jujuy", "la pampa", "la rioja", "mendoza", "misiones", "neuquen",
        "rio negro", "salta", "san juan", "san luis", "santa cruz", "santa fe",
        "santiago del estero", "tierra del fuego", "tucuman",
    }
    assert provincias <= set(PROVINCIA_A_DISTRIBUIDORA)
    for codes in PROVINCIA_A_DISTRIBUIDORA.values():
        for c in codes if isinstance(codes, list) else [codes]:
            assert c in DISTRIBUIDORAS
    assert len(DISTRIBUIDORAS) == 28


def test_validacion_rechaza_saltos_e_inyeccion_mayor() -> None:
    parsed = {"tarifa_compra_kwh": 1000.0, "tarifa_inyeccion_kwh": 2000.0,
              "cargo_fijo_mensual": None}
    prev = {"tarifa_compra_kwh": 100.0, "estado_campos": {"tarifa_compra_kwh": "extraido"}}
    rej = st.validate_parsed(parsed, prev)
    assert "tarifa_inyeccion_kwh" in rej and "tarifa_compra_kwh" in rej


def test_validacion_no_compara_contra_baseline() -> None:
    parsed = {"tarifa_compra_kwh": 54.0, "tarifa_inyeccion_kwh": None}
    prev = {"tarifa_compra_kwh": 2100.0,
            "estado_campos": {"tarifa_compra_kwh": "baseline_manual"}}
    assert st.validate_parsed(parsed, prev) == {}


def test_xlsx_con_unidad_en_encabezado() -> None:
    from etl.extractors.tariff_documents import rows_to_text

    rows = [
        ["TARIFA Nº 3 - GRANDES DEMANDAS", None, None],
        ["Concepto", "Cargo fijo $/mes", "Cargo variable $/kWh"],
        ["Pico", 25300.0, 70.1234],
        ["Resto", None, 65.5],
        ["Valle", None, 60.0],
    ]
    out = st.parse_tariff_text(rows_to_text(rows))
    assert out["valores_compra_detectados"] == [65.5]
    assert out["cargo_fijo_mensual"] == 25300.0


def test_detect_format() -> None:
    import io
    import zipfile

    from etl.extractors.tariff_documents import detect_format

    assert detect_format(b"%PDF-1.4 ...") == "pdf"
    assert detect_format(b"<html>login</html>") is None
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("2026_05_X.pdf", b"%PDF-1.4")
    assert detect_format(buf.getvalue()) == "zip"


def _fake_downloader(pages: dict[str, bytes]):
    def download(url: str) -> bytes:
        if url in pages:
            return pages[url]
        request = httpx.Request("GET", url)
        raise httpx.HTTPStatusError("404", request=request,
                                    response=httpx.Response(404, request=request))
    return download


def _fake_extractor(content: bytes, name: str) -> list[tuple[str, str]]:
    if not content.startswith(b"%PDF"):
        raise ValueError("no soportado")
    return [(name, content.decode("latin1").split("\n", 1)[1])]


def test_run_extractor_end_to_end_con_historial(tmp_path: Path) -> None:
    from etl.loaders.tariff_history import load_history, tariff_series
    from etl.reference.distribuidoras import NATIONAL_FILES_BASE, NATIONAL_PAGE_BASE

    url_jun = f"{NATIONAL_FILES_BASE}EPEC/2026_06_EPEC.pdf"
    url_may = f"{NATIONAL_FILES_BASE}EPEC/2026_05_EPEC.pdf"
    texto_may = PDF_TEXT.replace("65,5000", "50,0000")
    pages = {
        NATIONAL_PAGE_BASE + "epec": (
            f'<a href="{url_may}">05-2026</a><a href="{url_jun}">06-2026</a>'
        ).encode(),
        url_jun: b"%PDF-1.4\n" + PDF_TEXT.encode("latin1"),
        url_may: b"%PDF-1.4\n" + texto_may.encode("latin1"),
        # EDESAL devuelve HTML con HTTP 200 en lugar de PDF: debe ignorarse.
        "https://oficinavirtualedesal.com.ar/ove/upload/CuadroTarifario.pdf": b"<html/>",
    }
    out = st.run_extractor(
        raw_dir=tmp_path / "raw", reference_dir=tmp_path / "ref",
        downloader=_fake_downloader(pages), text_extractor=_fake_extractor,
        codes=["EPEC", "EDESAL"], historial=True, desde="2026-04",
    )
    data = json.loads(out.read_text(encoding="utf-8"))
    epec = data["distribuidoras"]["EPEC"]
    assert epec["tarifa_compra_kwh"] == 65.5          # vigencia más reciente (junio)
    assert epec["vigencia"] == "2026-06"
    assert epec["estado_campos"]["tarifa_compra_kwh"] == st.STATUS_PARSED
    assert epec["fuente_tipo"] == st.SOURCE_NATIONAL
    edesal = data["distribuidoras"]["EDESAL"]
    assert edesal["estado_campos"]["tarifa_compra_kwh"] == st.STATUS_MISSING
    assert data["distribuidoras"]["EDEN"]["parse_status"] == st.STATUS_MISSING

    hist = load_history(tmp_path / "ref")
    assert list(hist["vigencia"]) == ["2026-05", "2026-06"]
    serie = tariff_series(hist)
    assert serie.loc["2026-05", "EPEC"] == 50.0       # banda Resto del cuadro de mayo
    n_filas = len(hist)

    # Segunda corrida sin red: conserva el valor como fallback y el
    # historial no duplica documentos.
    out.rename(out.with_name("20000101000000_tarifas.json"))
    out2 = st.run_extractor(
        raw_dir=tmp_path / "raw", reference_dir=tmp_path / "ref",
        downloader=_fake_downloader({}), text_extractor=_fake_extractor,
        codes=["EPEC"],
    )
    epec2 = json.loads(out2.read_text(encoding="utf-8"))["distribuidoras"]["EPEC"]
    assert epec2["tarifa_compra_kwh"] == 65.5
    assert epec2["estado_campos"]["tarifa_compra_kwh"] == st.STATUS_FALLBACK
    assert len(load_history(tmp_path / "ref")) == n_filas


def test_dead_host_guard() -> None:
    calls: list[str] = []

    def down(url: str) -> bytes:
        calls.append(url)
        raise httpx.ConnectError("caído")

    guarded = st.with_dead_host_guard(down)
    for _ in range(4):
        with pytest.raises(httpx.ConnectError):
            guarded("https://caido.example/a.pdf")
    # Tras DEAD_HOST_FAILURES errores consecutivos no se vuelve a intentar.
    assert len(calls) == st.DEAD_HOST_FAILURES


def test_resolver_promedia_provincias_con_varias_distribuidoras() -> None:
    from etl.transformers.energy_finance import TariffResolver

    cfg = {
        "distribuidoras": {
            "EDEN": {"tarifa_compra_kwh": 100.0, "tarifa_inyeccion_kwh": 40.0,
                     "estado_campos": {"tarifa_compra_kwh": "extraido"}},
            "EDEA": {"tarifa_compra_kwh": 120.0, "tarifa_inyeccion_kwh": 50.0,
                     "estado_campos": {"tarifa_compra_kwh": "extraido"}},
            "EDES": {"tarifa_compra_kwh": None},
            "EDELAP": {"tarifa_compra_kwh": 90.0, "tarifa_inyeccion_kwh": 30.0},
        },
        "provincia_a_distribuidora": {"buenos aires": ["EDEN", "EDEA", "EDES"]},
        "departamento_a_distribuidora": {"buenos aires": {"la plata": "EDELAP"}},
    }
    r = TariffResolver(cfg)
    prov = r.resolve("Buenos Aires", "Pergamino")
    assert prov["compra"] == pytest.approx(110.0) and prov["es_proxy"]
    assert prov["origen"] == "extraido"
    lp = r.resolve("buenos aires", "La Plata")
    assert lp["distribuidora"] == "EDELAP" and lp["compra"] == 90.0 and not lp["es_proxy"]
    assert r.resolve("chubut")["distribuidora"] is None


def test_xlsx_y_zip_reales_de_punta_a_punta() -> None:
    import io
    import zipfile

    from openpyxl import Workbook

    from etl.extractors.tariff_documents import document_to_texts

    wb = Workbook()
    ws = wb.active
    for row in [
        ["Cuadro tarifario vigencia a partir del 1 de mayo de 2026"],
        ["TARIFA Nº 3 - GRANDES DEMANDAS"],
        ["Concepto", "Cargo fijo $/mes", "Cargo variable $/kWh"],
        ["Pico", 25300.0, 70.1234],
        ["Resto", None, 65.5],
        ["Valle", None, 60.0],
        ["USUARIO GENERADOR - Ley 27.424"],
        ["Energía inyectada", "Precio $/kWh"],
        ["", 35.21],
    ]:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("2026_05_EPEC.xlsx", buf.getvalue())

    for content in (buf.getvalue(), zbuf.getvalue()):
        [(_, text)] = document_to_texts(content, "x")
        out = st.parse_tariff_text(text)
        assert out["tarifa_compra_kwh"] == 65.5
        assert out["tarifa_inyeccion_kwh"] == 35.21
        assert out["cargo_fijo_mensual"] == 25300.0
        assert st.vigencia_from_text(text) == "2026-05"


def test_dead_host_guard_403_sostenido_y_404_no() -> None:
    calls: list[str] = []

    def down(url: str) -> bytes:
        calls.append(url)
        code = 403 if "bloqueado" in url else 404
        request = httpx.Request("GET", url)
        raise httpx.HTTPStatusError(str(code), request=request,
                                    response=httpx.Response(code, request=request))

    guarded = st.with_dead_host_guard(down)
    for _ in range(4):
        with pytest.raises(httpx.HTTPError):
            guarded("https://bloqueado.example/a.pdf")
        with pytest.raises(httpx.HTTPError):
            guarded("https://normal.example/a.pdf")
    assert sum("bloqueado" in c for c in calls) == st.DEAD_HOST_FAILURES
    assert sum("normal" in c for c in calls) == 4


def test_vigencia_carpetas_oceba() -> None:
    base = "https://oceba.gba.gov.ar/nueva_web/adjuntos/"
    assert st.vigencia_from_name(base + "ct20250502/IF-2025-16721231-GDEBA-GMOCEBA.pdf") == "2025-05"
    assert st.vigencia_from_name(base + "ct202609/IF-2026-27723597-GDEBA-GMOCEBA.pdf") == "2026-09"

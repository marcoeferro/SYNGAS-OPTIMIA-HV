"""
Tests del parser de cuadros tarifarios con fragmentos de documentos reales.

Cada fixture reproduce (recortado) el texto que ``tariff_documents``
obtiene de un cuadro publicado por la distribuidora o por el portal de la
Secretaría de Energía (relevados en octubre de 2026).
"""

from __future__ import annotations

import io
import zipfile

import pytest
from openpyxl import Workbook

from etl.extractors.tariff_documents import document_to_texts, rows_to_text
from etl.extractors.tariff_parser import detect_english_format, parse_tariff_text

# SECHEEP (Chaco) 2026-06, planilla del portal nacional.
SECHEEP = """\
Cód. Tarifario | Categorías | Escala Mensual | Unidad | Abastecimiento | VAD | Total Neto
RESIDENCIAL | Cargo Fijo | $-mes | 0 | 2959,82 | 2959,82
0111 | Familiar | Primeros 50 Kwh | $/KWh | 156,9462 | 25,3733 | 182,3195
COMERCIAL | Cargo Fijo | $-mes | 0 | 6783,81 | 6783,81
2A | <50KW-Particulares.y Oficiales. | Primeros 250 Kwh. | $/KWh | 151,0281 | 71,8721 | 222,9002
60 y 65 | Baja Tensión < 300 KW | Cargo Fijo | $-mes | 0 | 30591,87 | 30591,87
60 y 65 | Baja Tensión < 300 KW | Cargo Energía Pico | $/KWh | 118,9627 | 3,5597 | 122,5224
Cargo Energía Resto | $/KWh | 115,719 | 3,5597 | 119,2787
Cargo Energía Valle | $/KWh | 114,2091 | 3,5597 | 117,7688
0112-0113 | Por cada KWh inyectado a la red | $/KWh | 89,9122 | 0 | 89,9122
0112-0113 | Decreto PEN 943/25 - SEF | Por cada KWh inyectado a la red | $/KWh | 39,9617 | 0 | 39,9617
2A-2B-04 | <50KW - Part. Nac. Prov. Mun. | Por cada KWh inyectado a la red | $/KWh | 90,2979 | 0 | 90,2979
"""

# ENERSA (Entre Ríos) 2026-05: bloques por nivel de tensión.
ENERSA = """\
TARIFA 3 - GRANDES DEMANDAS | No Residencial  (<300 kW) | GUDIs (>= 300 kW)
Vinculación Superior
Cargo fijo | $/mes | 554665,19 | 554665,19
Por consumo de energía | $/kWh
Período horas restantes | 110,06 | 110,28
Vinculación Inferior en Media Tensión
Cargo fijo | $/mes | 418910,65 | 418910,65
Por consumo de energía | $/kWh
Período horas restantes | 112,87 | 113,1
Vinculación Inferior en Baja Tensión
Cargo fijo | $/mes | 131733,69 | 131733,69 | 131733,69
Cargo fijo por potencia adquirida | $/kW-mes | 5567,74 | 12736,27 | 12736,27
Por consumo de energía | $/kWh
Período horas restantes | 57,77 | 130,84 | 131,1
Período horas de valle nocturno | 57,06 | 129,02 | 129,28
Usuario  Generador -  T1, T2 y T3 | Residen. Sin Subsidio Nacional | No Residencial  (<300 kW)
Credito por Energia Ingresada a la Red | $/kWh | 93,36 | 40,12 | 93,74 | 93,93
TARIFA DE PEAJE | GRANDES DEMANDAS | No Residencial  (<300 kW)
Vinculación Inferior en Baja Tensión
Cargo variable por energía | $/kWh
Período horas restantes | $/kWh | 21,18 | 9,39 | 9,39 | 0 | 21,26 | 21,3
"""

# OCEBA, cuadro de EDEN S.A. 2026-09 (PDF).
OCEBA_EDEN = """\
ANEXO 3
CUADRO TARIFARIO DE EDEN S.A.
T1 - PEQUEÑAS DEMANDAS (menos de 10 kW de demanda)
CARGO VARIABLE R1 (consumo en kWH-Mes <= 100) 228,3509 $/kWh
T2 - MEDIANAS DEMANDAS
CARGO FIJO 41.208,33 $/mes
CARGO VARIABLE POR ENERGÍA DEMANDADA EN PICO 118,1234 $/kWh
CARGO VARIABLE POR ENERGÍA DEMANDADA EN RESTO 114,9777 $/kWh
CARGO VARIABLE POR ENERGÍA DEMANDADA EN VALLE 112,4321 $/kWh
"""

# EDESE (Santiago del Estero) 2026-09: PDF con formato numérico inglés y
# dos tablas lado a lado en la misma línea.
EDESE = """\
Baja Tensión con Pot < 300 kW
T3-BT Cargo por Cap.de Sum.Cont. en Punta $/kW-mes 31,033.55
T3-BT Cargo Variable por Energía en hs.Pico $/kWh 161.096 Conexiones Domiciliarias
T3-BT Cargo Variable por Energía en hs.Restantes $/kWh 156.655 Conexiones Comunes:
T3-BT Cargo Variable por Energía en hs.Valle $/kWh 155.603          Aéreas Monofásicas $/Cliente 78,432.4
Baja Tensión con Pot > ó = 300 kW          Aéreas Trifásicas $/Cliente 231,551.9
T3-BT Cargo Variable por Energía en hs.Restantes $/kWh 175.386          Subterráneas Monofásicas $/Cliente 662,591.7
"""

# EDELAR (La Rioja), PDF propio: etiqueta y valor en líneas separadas.
EDELAR = """\
TARIFA Nº 2 - Grandes Demandas (más de 10 kW)
Grandes Demandas entre 10 y 300 kW
Por consumo de energía en horas restantes:
$/kWh 100,0425 98,6745 95,7195
Grandes Demandas igual o mayor a 300 kW (Org. Publicos Salud y Educacion)
Resto 75,9100
$/kWh 75,9100
Por la Energia Inyectada a la red de Distribucion
Unidad Precios
$/kWh 92,9430
"""


def test_secheep_resto_baja_tension_e_inyeccion_sin_subsidio() -> None:
    out = parse_tariff_text(SECHEEP)
    # Mediana de abastecimiento y total de la banda Resto (VAD < mínimo).
    assert out["tarifa_compra_kwh"] == pytest.approx((115.719 + 119.2787) / 2)
    assert out["cargo_fijo_mensual"] == 30591.87
    # La fila con subsidio (SEF, Decreto 943/25) no participa.
    assert out["tarifa_inyeccion_kwh"] == pytest.approx((89.9122 + 90.2979) / 2)


def test_enersa_toma_baja_tension_no_vinculacion_superior_ni_peaje() -> None:
    out = parse_tariff_text(ENERSA)
    assert out["tarifa_compra_kwh"] == 130.84
    assert out["tarifa_inyeccion_kwh"] == pytest.approx(93.55)


def test_oceba_pdf_banda_resto() -> None:
    out = parse_tariff_text(OCEBA_EDEN)
    assert out["tarifa_compra_kwh"] == 114.9777
    assert out["cargo_fijo_mensual"] == 41208.33


def test_formato_numerico_ingles_y_tablas_lado_a_lado() -> None:
    assert detect_english_format(EDESE)
    out = parse_tariff_text(EDESE)
    # < 300 kW (no la categoría >= 300 kW ni el cargo de conexión de 662.591,7)
    assert out["tarifa_compra_kwh"] == 156.655


def test_linea_sin_etiqueta_usa_concepto_anterior() -> None:
    out = parse_tariff_text(EDELAR)
    assert out["tarifa_compra_kwh"] == 98.6745        # 10-300 kW, no >= 300 kW
    assert out["tarifa_inyeccion_kwh"] == 92.943      # no se confunde con compra


def test_residencial_sola_no_produce_tarifa() -> None:
    texto = "RESIDENCIAL | Cargo Fijo | $-mes | 2959,82\n0111 | Familiar | $/KWh | 182,3195\n"
    assert parse_tariff_text(texto)["tarifa_compra_kwh"] is None


def test_edesa_planilla_con_encabezados_de_columna() -> None:
    rows = [
        ["TARIFA 3"],
        ["> 50 Kw", "Cargo Fijo $/mes", "Cargo Variable Horas Pico $/kwh",
         "Cargo Variable Horas Resto $/KWh", "Cargo Variable Horas Valle $/KWh"],
        ["BT-MD", 39435.881323, 270.314784, 266.808787, 265.176812],
        ["MT-MD", 252884.086133, 293.941113, 290.786762, 289.318471],
    ]
    out = parse_tariff_text(rows_to_text(rows))
    assert out["tarifa_compra_kwh"] == pytest.approx(266.80879, rel=1e-6)


def test_emsa_media_tension_en_kv_no_aplica() -> None:
    texto = (
        "GRANDES | Energía en horas Resto | 138,76\n"
        "USUARIOS EN 13,2 KV | Energía en horas Valle | 138,366\n"
    )
    assert parse_tariff_text(texto)["tarifa_compra_kwh"] is None


def _xlsx(rows: list[list[object]]) -> bytes:
    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_zip_edenor_elige_cuadro_pleno() -> None:
    from datetime import datetime

    from etl.extractors.scrape_tarifas import process_document

    def cuadro(titulo: str, resto: float) -> bytes:
        return _xlsx([
            [titulo], ["vigencia a partir del 1° de junio de 2026"], ["EDENOR"],
            ["Tarifa 3 - BT"], ["Cargo Fijo", "$/mes", 177533.46],
            ["Cargo Variable Pico", "$/kWh", resto + 3], ["Cargo Variable Resto", "$/kWh", resto],
        ])

    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w") as zf:
        zf.writestr("2026_07_EDENOR 1.xlsx", cuadro("Clubes de Barrio - Res. SE 742/2022", 46.599))
        zf.writestr("2026_07_EDENOR 2.xlsx", cuadro("Cuadro Tarifario", 108.369))
    url = "http://www.energia.gob.ar/x/EDENOR/2026_06_EDENOR.zip"
    out = process_document("EDENOR", url, zbuf.getvalue(), "nacional", datetime(2026, 10, 4))
    assert out is not None
    assert out["tarifa_compra_kwh"] == 108.369
    assert out["documento"].endswith("EDENOR 2.xlsx")
    # La vigencia declarada en el texto prevalece sobre el nombre del miembro (07).
    assert out["vigencia"] == "2026-06"
    [(_, text)] = document_to_texts(cuadro("x", 1.0), "y.xlsx")
    assert "Cargo Variable Resto" in text


def test_cuadro_especial_clubes_de_barrio_no_es_tarifa_de_compra() -> None:
    texto = (
        "Cuadro Tarifario\n"
        "Clubes de Barrio y de Pueblo-Resolución SE N° 742/2022\n"
        "vigencia a partir de 1° de diciembre de 2025\nEDENOR\n"
        "Tarifa 3 - BT\nCargo Variable Resto | $/kWh | 32,567\n"
    )
    out = parse_tariff_text(texto)
    assert out["documento_especial"]
    assert out["tarifa_compra_kwh"] is None


def test_hoja_de_tarifas_de_inyeccion() -> None:
    # EDENOR, anexo "gd" (2025-12): la unidad está sólo en el título.
    texto = (
        "Tarifas de Inyección de Generación Distribuida - $/kwh\n"
        "vigentes a partir del 1° de diciembre 2025\n"
        "Residencial Nivel 1 | 77,218\n"
        "General | 67,188\n"
        "Tarifa 3 - BT <300\n"
        "Cargo Variable Pico | 69,02\nCargo Variable Resto | 67,188\n"
        "Tarifa 3 - MT <300\nCargo Variable Resto | 63,853\n"
    )
    out = parse_tariff_text(texto)
    assert out["documento_inyeccion"]
    assert out["tarifa_compra_kwh"] is None
    assert out["tarifa_inyeccion_kwh"] == 67.188


def test_indice_de_categorias_no_marca_documento_especial() -> None:
    # EPEN 2026-08: el PDF empieza con el índice de tarifas.
    texto = (
        "TARIFA Nº 1 - PEQUEÑAS DEMANDAS RESIDENCIALES - ESTACIONALES Y ELECTRODEPENDIENTES\n"
        "TARIFA Nº 3 - GRANDES DEMANDAS (CAPACIDADES DE SUMINISTRO IGUALES O SUPERIORES A 50 kW)\n"
        "Servicio en Baja Tensión\n"
        "Capacidad de suministro menor a 300 KW\n"
        "Por consumo de energía en período horas restante 359,733 $/KWh\n"
    )
    out = parse_tariff_text(texto)
    assert not out["documento_especial"]
    assert out["tarifa_compra_kwh"] == 359.733


def test_refsa_unidad_kw_hs() -> None:
    texto = (
        "TARIFA 3 - GRANDES DEMANDAS < 300 KW\n"
        "Grandes Demandas En Baja Tensión <300 Kw\n"
        "Por Consumo de Energía : Período Horas de Punta [$/KW-Hs] 139,1754$\n"
        "Período Horas de Valle (Nocturnas) [$/KW-Hs] 133,4738$\n"
        "Período Horas Restantes [$/KW-Hs] 135,2848$\n"
    )
    assert parse_tariff_text(texto)["tarifa_compra_kwh"] == 135.2848

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


# ECSAPEM (Misiones) 2026-05: columnas de baja y media tensión en paralelo
# y hoja de generación distribuida con filas "energía inyectada".
ECSAPEM = """\
T3 | GRANDES DEMANDAS CON CONSUMOS MENORES A 300 KW | Nivel de Tensión de Suministro: | Baja Tensión | Media Tensión
Nivel de Tensión de Suministro: | Baja Tensión | Media Tensión | UNIDAD | VAD | MEM | TOTAL
UNIDAD | VAD | MEM | TOTAL | VAD | MEM | TOTAL
Cargo Variable por Consumo de Energía | Cargo Variable por Consumo de Energía
Período Horas Punta | $/KWh. | 0 | 109,4238 | 109,423776 | 0 | 99,4512 | 99,451241
Período Horas Resto | $/KWh. | 0 | 106,0597 | 106,059715 | 0 | 96,3938 | 96,39377
Período Horas Valle Nocturno | $/KWh. | 0 | 104,4892 | 104,489246 | 0 | 94,9662 | 94,966216
"""


def test_ecsapem_columnas_bt_mt_toma_baja_tension() -> None:
    out = parse_tariff_text(ECSAPEM)
    assert out["tarifa_compra_kwh"] == pytest.approx(106.06, abs=0.01)


def test_fila_de_inyeccion_no_arrastra_filas_siguientes() -> None:
    texto = (
        "T2 | MEDIANAS DEMANDAS | UNIDAD | TOTAL\n"
        "Cargo variable por energia inyectada | $/KWh | 80,5\n"
        "Período Horas Resto | $/KWh. | 106,2884\n"
    )
    out = parse_tariff_text(texto)
    assert out["tarifa_inyeccion_kwh"] == pytest.approx(80.5)
    assert out["tarifa_compra_kwh"] == pytest.approx(106.2884)


# OCEBA (EDEN) 2026-09, anexo 3: la tarifa a distribuidores municipales
# (mayorista) precede a la de usuarios finales dentro de T3 BT.
OCEBA_MUNICIPALES = """\
CUADRO TARIFARIO DE EDEN S.A.
T3 - GRANDES DEMANDAS
T3BT - SUMINISTROS EN BAJA TENSIÓN
SUMINISTROS >= a 50 kW de demanda (Distribuidores Municipales)
CARGOS VARIABLES
DISTRIBUIDORES MUNICIPALES(Usuarios finales < a 10 kW T4R.)
CARGO VARIABLE POR ENERGÍA DEMANDADA EN PICO 117,5969 $/kWh
CARGO VARIABLE POR ENERGÍA DEMANDADA EN RESTO 114,9777 $/kWh
DIST. MUNICIPALES (Usuarios finales Suministros entre 10 y 300kW de Demanda)
CARGO VARIABLE POR ENERGÍA DEMANDADA EN RESTO 124,0227 $/kWh
USUARIOS FINALES Suministros entre 50 y 300kW de Demanda
CARGO VARIABLE POR ENERGÍA DEMANDADA EN PICO 137,9288 $/kWh
CARGO VARIABLE POR ENERGÍA DEMANDADA EN RESTO 135,0549 $/kWh
USUARIOS FINALES Suministros Mayor o igual a 300 kW de Demanda
CARGO VARIABLE POR ENERGÍA DEMANDADA EN RESTO 149,5025 $/kWh
"""


def test_oceba_excluye_distribuidores_municipales() -> None:
    out = parse_tariff_text(OCEBA_MUNICIPALES)
    assert out["tarifa_compra_kwh"] == pytest.approx(135.0549)


def test_pdf_con_decimales_partidos() -> None:
    """OCEBA 2025-09: el PDF parte los importes ("104,10 37", "9 ,0896")."""
    texto = OCEBA_MUNICIPALES.replace("135,0549", "104,10 37")
    assert parse_tariff_text(texto)["tarifa_compra_kwh"] == pytest.approx(104.1037)


def test_cantidad_de_kwh_no_es_precio() -> None:
    """EDEMSA 2025-09: "hasta 800 kWh mes $/kWh" no es una tarifa de 800."""
    texto = (
        "T2 - MEDIANAS DEMANDAS - BAJA TENSIÓN\n"
        "-Baja (de 23 a 14hs.) hasta 800 kWh mes $/kWh\n"
    )
    assert parse_tariff_text(texto)["tarifa_compra_kwh"] is None


# EPE (Santa Fe) 2026-09, CUT_T2: la tensión sólo figura en el código de
# fila ("2 B1" baja tensión, "2M11" media) y las bandas son columnas.
EPE_T2 = """\
Cargo energía hs. Pico ($/kWh) Cargo energía hs. Resto ($/kWh) Cargo energía hs. Valle ($/kWh)
2 B1 Demandas menores a 300 kW 151,41966 146,77374 145,67246
2 B2 - O B2 Demandas mayores o iguales a 300 kW 171,82228 166,45516 165,18272
2M11 Demandas menores a 300 kW 143,90237 139,48710 138,44049
TARIFA 2 - GRANDES DEMANDAS
"""


def test_fila_indicada_en_registro_epe() -> None:
    from etl.reference.distribuidoras import DISTRIBUIDORAS

    out = parse_tariff_text(EPE_T2, DISTRIBUIDORAS["EPE"]["fila_tarifa"])
    assert out["tarifa_compra_kwh"] == pytest.approx(146.77374)
    # Un cuadro sin esa fila (T4, T6, residencial) no aporta compra.
    otro = parse_tariff_text("Residencial $/kWh 200,5\n", DISTRIBUIDORAS["EPE"]["fila_tarifa"])
    assert otro["tarifa_compra_kwh"] is None


# APE (La Pampa) 2025-12: precio = costo de compra de energía + VAD.
APE = """\
T1NRI         CATEGORÍA INDUSTRIALES | Unidad | Precio de Venta Máximo | Subsidio Estado Nacional
Costo Compra de Energía | $/kWh | 110,86959 | 0 | 110,86959
VAD Cooperativa | $/kWh | 69,69 | 69,69 | 0,055
T2I | Consumos mayores a 4000 kWh/mes
Cargo Fijo | $/mes | 3543,9 | 3543,9
Costo Compra de Energía | $/kWh | 110,86959 | 0 | 110,86959
VAD primeros 4000 kWh | $/kWh | 66,08 | 66,08 | 0,055
VAD excedente de 4000 kWh | $/kWh | 58,53 | 58,53 | 0,055
"""

# EMSA (Misiones) 2025-11, CT Pleno: cargo de energía único por categoría.
EMSA = """\
CUADRO TARIFARIO  Nº  568
3 | INDUSTRIAL | 3.a 1    Menor o igual a 2000 KWh
Primeros 800KWh | 187,29 | 6073,7
3.b   Mayor a 4000 KWh
Energía | 204,058 | 7594,7
4.b   Mayor a 4000 KWh
Energía | 212,193 | 11190,5
"""


@pytest.mark.parametrize(
    ("codigo", "texto", "esperado"),
    [("APE", APE, 110.86959 + 58.53), ("EMSA", EMSA, 204.058)],
)
def test_filas_ancladas_del_registro(codigo: str, texto: str, esperado: float) -> None:
    from etl.reference.distribuidoras import DISTRIBUIDORAS

    out = parse_tariff_text(texto, DISTRIBUIDORAS[codigo]["fila_tarifa"])
    assert out["tarifa_compra_kwh"] == pytest.approx(esperado)


def test_proyecto_de_cuadro_no_es_vigente() -> None:
    texto = "PROYECTO DE CUADRO TARIFARIO Nº 574\nTarifas Sin Subsidios\n" + EMSA
    assert parse_tariff_text(texto)["documento_especial"]

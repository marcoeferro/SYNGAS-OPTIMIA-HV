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


# EDESA (Salta) 2026-09, PDF propio leído con layout: tablas lado a lado,
# la T2 (10-50 kW) y la T3 (> 50 kW) traen filas "BT - MD".
EDESA_PDF_LAYOUT = """\
Cuadro Tarifario EDESA S.A        Según Resolución ENRESP N° 1510/26
            Abastecimiento/RES. SE. N° 222/26     SEPTIEMBRE 2026
  T1AP   -   372,0006   T3 - BT - MD   14.886,26   909,39   74,4982   Tarifas Balance Neto
   Medianas y Gr   andes Demandas (> = 10KW)   Balance Neto - Origen Solar   T_BN_SOL   90,2547
   Balance Neto - Origen Biomasa   T_BN_BIO   37,7622
   Demandas > 10 < 50 KW   contratada - $ / KW-mes   $/Mes   $/KWh   T3- AT - GD   160,73
  BT- MD   19.229,76   26.573,47   236,9380
   T4 - BT - MD   8.362,28   773,66   42.064,23   90,7261   90,1217   89,9784
   TARIF   A 3Cargo por máx. cap.   de sum.  contratada   Cargo ﬁjo   T5 - BT - MD   9.690,94
   Demandas > 50 KW   de sum. contratada - $ / KW-mes   en hs. de punta   $/Mes   horas resto
   -  $ / KW-mes   $/KWh   $/KWh   $/KWh   T5 - BT - GD   9.690,94   638,69   42.064,23
  BT   - MD   17.287,27   5.495,78   42.064,23   318,3957   313,5895   312,4502   T6 - MT- MD
  BT   - GD   17.287,27   5.495,78   42.064,23   339,5023   333,9500   332,6337   BT =
"""

# EDESA 2026-06, planilla del portal nacional (mismas filas del registro).
EDESA_NACIONAL = [
    ["TARIFA 3"],
    ["> 50 Kw", "Cargo por Máx. cap. de sum. contratada $/KW-mes",
     "Cargo por Cap. de Sum. contratada en Hs. de Punta $/KW-mes", "Cargo Fijo $/mes",
     "Cargo Variable Horas Pico $/kwh", "Cargo Variable Horas Resto $/KWh",
     "Cargo Variable Horas Valle $/KWh"],
    ["BT-MD", 16170.405475, 5276.988136, 39435.881323, 270.314784, 266.808787, 265.176812],
    ["TARIFAS BALANCE NETO"],
    ["GENERADORES", "Tipo GEN", "Cargo Variable $/KWh"],
    ["Balance Neto - Origen Solar", "T_BN_SOL", 84.3557],
    ["Balance Neto - Origen Biomasa", "T_BN_BIO", 35.294077],
]


@pytest.mark.parametrize(("texto", "compra", "inyeccion"), [
    (EDESA_PDF_LAYOUT, 313.5895, 37.7622),
    (rows_to_text(EDESA_NACIONAL), 266.80879, 35.29408),
])
def test_edesa_filas_del_registro(texto: str, compra: float, inyeccion: float) -> None:
    from etl.reference.distribuidoras import DISTRIBUIDORAS

    info = DISTRIBUIDORAS["EDESA"]
    out = parse_tariff_text(texto, info["fila_tarifa"], info["fila_inyeccion"])
    assert out["tarifa_compra_kwh"] == pytest.approx(compra)       # T3 BT-MD resto
    assert out["tarifa_inyeccion_kwh"] == pytest.approx(inyeccion)  # Balance Neto biomasa


def test_edesa_cuadros_de_otros_servicios_no_aportan() -> None:
    # La página de EDESA enlaza también el cargo de alumbrado público (IAP).
    from etl.reference.distribuidoras import DISTRIBUIDORAS

    info = DISTRIBUIDORAS["EDESA"]
    iap = (
        "CARGOS DE INCIDENCIA DEL ALUMBRADO PÚBLICO\n"
        "Tarifa   KWH IAP   Tarifa   KWH IAP\n"
        "T3BT   203,933   T7A   67,822\n"
    )
    out = parse_tariff_text(iap, info["fila_tarifa"], info["fila_inyeccion"])
    assert out["tarifa_compra_kwh"] is None
    assert out["tarifa_inyeccion_kwh"] is None


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


# EPEC (Córdoba) 2026-10, fragmento del PDF tal como lo devuelve pypdf: la
# banda horaria en una línea y el importe (en letras y números) en la de
# abajo. El encabezado "TARIFA Nº 3" sale después de su primera sección.
EPEC = """\
CUADRO TARIFARIO EPEC S/RES. GRAL. ERSeP Nº 25/2026 - Letra: D
3.1.1.   BAJA TENSION (220/380 V):
a.1.
a.1.1.
Por cada kWh consumido, se facturará:
En Horario de Pico
(Pesos treinta y seis con noventa y dos mil novecientos tres cienmilésimos) $ 36,92903
En Horario de Horas Restantes
(Pesos treinta y seis con tres mil quinientos treinta y siete cienmilésimos) $ 36,03537
a.1.2. Por cada consumo no incluido en el apartado anterior, se facturará:
 - Por cada kW de "Demanda de Potencia" por mes (Horario Fuera de Punta)
(Pesos diecinueve mil trescientos dos con nueve mil siete diezmilésimos) $ 19.302,9007
Por cada kWh consumido, se facturará:
En Horario de Pico
(Pesos ciento cuarenta y cuatro con sesenta y siete mil cincuenta y un cienmilésimos) $ 144,67051
En Horario de Horas Restantes
(Pesos ciento cuarenta con veintitres mil setenta cienmilésimos) $ 140,23070
TARIFA Nº 3 - GRANDES CONSUMOS
a.2.
En Horario de Horas Restantes
(Pesos ciento cincuenta y nueve con tres mil ochocientos noventa y ocho cienmilésimos) $ 159,03898
GENERACION DISTRIBUIDA
3.1.   BAJA TENSION (220/380 V):
a.1.
a.1.1.
En Horario de Horas Restantes
(Pesos treinta y tres con veinte mil seiscientos treinta y cinco cienmilésimos) $ 33,20635
a.1.2. Por cada kWh inyectado de suministros no incluidos en el apartado anterior:
En Horario de Horas Restantes
(Pesos ciento treinta y siete con cuarenta mil ciento sesenta y ocho cienmilésimos) $ 137,40168
a.2.
Por cada kWh inyectado:
En Horario de Horas Restantes
(Pesos ciento cincuenta y seis con veinte mil novecientos noventa y cinco cienmilésimos) $ 156,20995
"""


def test_epec_tarifa_3_baja_tension_compra_e_inyeccion() -> None:
    from etl.reference.distribuidoras import DISTRIBUIDORAS

    info = DISTRIBUIDORAS["EPEC"]
    out = parse_tariff_text(EPEC, info["fila_tarifa"], info["fila_inyeccion"])
    # < 300 kW, no clubes (a.1.2), banda Horas Restantes; no la de clubes
    # (36,04) ni la de grandes usuarios ≥ 300 kW (159,04).
    assert out["tarifa_compra_kwh"] == pytest.approx(140.2307)
    assert out["tarifa_inyeccion_kwh"] == pytest.approx(137.40168)


# Cuadro de inyección conjunto de OCEBA: una columna por empresa
# (EDEA | EDEN | EDES).
OCEBA_INYECCION = """\
 ANEXO 83
CUADRO TARIFARIO DE INYECCIÓN EXCEDENTES S/RESOLUCIÓN MIYSP N° 463/23
T3 - GRANDES DEMANDAS
T3BT - SUMINISTROS EN BAJA TENSIÓN USUARIOS FINALES (Suministros entre 50 y 300 KW)
PRECIO VARIABLE POR ENERGÍA EN PICO $/kWh 127,4117 126,9041 126,9041
PRECIO VARIABLE POR ENERGÍA EN RESTO $/kWh 124,5188 124,0227 124,0227
T3BT - SUMINISTROS EN BAJA TENSIÓN USUARIOS FINALES (Suministros >= 300 KW)
PRECIO VARIABLE POR ENERGÍA EN RESTO $/kWh 138,3487 137,7976 137,7976
"""

# Resolución del ENRE (EDENOR y EDESUR): sólo inyección, punto decimal.
ENRE_INYECCION = """\
Tarifas de Inyección de Generación Distribuida - $/kwh
vigentes a partir del 1° de mayo de 2026
General 105.100
Tarifa 3 - BT <300
Cargo Variable Pico 108.335
Cargo Variable Resto 105.100
Tarifa 3 - BT >300
Cargo Variable Resto 105.320
"""


@pytest.mark.parametrize(
    ("codigo", "texto", "esperado"),
    [
        ("EDEA", OCEBA_INYECCION, 124.5188),
        ("EDEN", OCEBA_INYECCION, 124.0227),
        ("EDESUR", ENRE_INYECCION, 105.1),
    ],
)
def test_documentos_solo_de_inyeccion(codigo: str, texto: str, esperado: float) -> None:
    from etl.reference.distribuidoras import DISTRIBUIDORAS

    info = DISTRIBUIDORAS[codigo]
    out = parse_tariff_text(texto, info["fila_tarifa"], info["fila_inyeccion"])
    assert out["documento_inyeccion"]
    assert out["tarifa_compra_kwh"] is None
    assert out["tarifa_inyeccion_kwh"] == pytest.approx(esperado)


def test_punto_decimal_con_tres_decimales_sin_comas() -> None:
    assert detect_english_format(ENRE_INYECCION)
    assert not detect_english_format("Cargo fijo 1.234,56 $/mes\nEnergía 105,1 $/kWh")


# Naturgy San Juan (ESJ) 2026-09: T3 BT < 300 kW y el cuadro de valores a
# reconocer al usuario generador (cargos fijos en cero) con la misma tabla.
ESJ = """\
Cargo fijo (haya o no consumo) $/bimestre 4557.54 15737.24 23463.07
Unidad BT MT 13,2 R MT 13,2 B MT 33 AT
Potencias menores a 300 kW-mes
En horas de punta $/kWh 157.9653 139.2069 138.8110 135.1750
En horas restantes $/kWh 153.2696 135.0688 134.6847 131.1568
Potencias mayores o iguales a 300 kW-mes
En horas restantes $/kWh 173.1618 152.5989 152.1649 148.1791
Cargo fijo (haya o no consumo) $/bimestre 0.0000 0.0000 0.0000
Unidad BT MT 13,2 R MT 13,2 B MT 33 AT
Potencias menores a 300 kW-mes
En horas restantes $/kWh 150.0000 135.0688 134.6847 131.1568
Valores Tarifarios a Reconocer al Usuario Generador por la
Energía Inyectada
"""

# EJESA (Jujuy) 2026-08/09: texto desordenado; la fila T3 BT < 300 kW es la
# primera "cargo fijo | $/kW | 6 importes" después del cuadro de generador.
EJESA = """\
CUADRO TARIFARIO
117.308 159,9846             181,0471               177,7814            177,3984                   196,3388                  191,5834                 190,4561
USUARIO GENERADOR Energía Entregada a la Red
   99,1230                                                      100,6320
   42,5448                                                      35,7765
   107,6080                                                      121,5400
   120,5300                                                     138,2140
199.424 38.411        181,0471                 177,7814                   177,3984               196,3388                     191,5834                  190,4561
199.424 38.411        197,1112                 193,3936           192,9587               217,2224                     211,7287                  210,4263
"""


@pytest.mark.parametrize(
    ("codigo", "texto", "compra", "inyeccion"),
    [("ESJ", ESJ, 153.2696, 150.0), ("EJESA", EJESA, 191.5834, 121.54)],
)
def test_filas_de_compra_e_inyeccion(
    codigo: str, texto: str, compra: float, inyeccion: float
) -> None:
    from etl.reference.distribuidoras import DISTRIBUIDORAS

    info = DISTRIBUIDORAS[codigo]
    out = parse_tariff_text(texto, info["fila_tarifa"], info["fila_inyeccion"])
    assert out["tarifa_compra_kwh"] == pytest.approx(compra)
    assert out["tarifa_inyeccion_kwh"] == pytest.approx(inyeccion)


# EDERSA (Río Negro) 2026-10, fragmento del PDF tal como lo devuelve pypdf:
# el cuadro general (sin inyección) y el de usuarios-generadores (UGER),
# con la inyección residencial y general antes de la T2.
EDERSA = """\
T2 con Potencias entre 10 y 50 Kw
T2N_1BTb T2N_1BTr
CGC T2 $/mes 111691,36 111691,36
CARGO TRANSP. OTROS AGENTES $/kWh 11,09 11,50
CARGO ENERGIA (P) $/kWh 157,886 163,802
CARGO ENERGIA (R) $/kWh 155,298 161,117
CARGO ENERGIA (V) $/kWh 154,275 160,056
T2 con Potencias entre 50 y 300 Kw
CARGO TRANSP. OTROS AGENTES $/kWh 11,09 11,50 10,88
CARGO ENERGIA (R) $/kWh 155,298 161,117 152,329
CUADRO TARIFARIO
Periodo: OCTUBRE 2026 UGER
TARIFA RESIDENCIAL
TARIFA INYECCIÓN $/kWh 63,110 63,110 148,235 148,235
TARIFA GENERAL
TARIFA INYECCIÓN $/kWh 173,078 173,078
T2 con Potencias entre 10 y 50 Kw
T2N_1BTb T2N_1BTr
CARGO TRANSP. OTROS AGENTES $/kWh 11,09 11,50
CARGO ENERGIA (R) $/kWh 155,298 161,117
Tarifa de Inyección (P) $/KWh 168,974 175,306
Tarifa de Inyección (R) $/KWh 166,386 172,621
Tarifa de Inyección (V) $/KWh 165,363 171,560
"""


def test_edersa_t2_compra_con_transporte_e_inyeccion_uger() -> None:
    from etl.extractors.scrape_tarifas import validate_parsed
    from etl.reference.distribuidoras import DISTRIBUIDORAS

    info = DISTRIBUIDORAS["EDERSA"]
    out = parse_tariff_text(EDERSA, info["fila_tarifa"], info["fila_inyeccion"])
    # Energía Resto + transporte de otros agentes (155,298 + 11,09); la
    # inyección de la misma categoría, no la mediana con la residencial.
    assert out["tarifa_compra_kwh"] == pytest.approx(166.388)
    assert out["tarifa_inyeccion_kwh"] == pytest.approx(166.386)
    assert validate_parsed(out, None) == {}
    # El último decimal del redondeo no la descarta (abril 2025).
    assert validate_parsed(
        {"tarifa_compra_kwh": 87.227, "tarifa_inyeccion_kwh": 87.229}, None
    ) == {}


# APE 2026-09, anexo V (texto de pypdf): tarifa de inyección por categoría.
APE_INYECCION = """\
ANEXO V - Resolución S.E.y M. Nº 039 / 26 - CUADRO TARIFARIO
SERVICIO DE DISTRIBUCIÓN DE ENERGÍA ELÉCTRICA
PRECIOS DE COMPRA DE ENERGÍA DE LAS  PRESTADORAS  A LOS USUARIOS GENERADORES
Vigencia: A partir de la facturación del período de septiembre 2026
Residenciales $/kWh 125,55
Demandas < o = 10 kW $/kWh 136,13
Demandas > 10 kW y < 300
kW $/kWh 140,00
Ti3b Demandas > o = 300 kW $/kWh 149,22
"""


def test_ape_inyeccion_del_anexo_v() -> None:
    from etl.reference.distribuidoras import DISTRIBUIDORAS

    info = DISTRIBUIDORAS["APE"]
    out = parse_tariff_text(APE_INYECCION, info["fila_tarifa"], info["fila_inyeccion"])
    assert out["tarifa_inyeccion_kwh"] == pytest.approx(140.0)
    assert out["tarifa_compra_kwh"] is None
    # El cuadro de compra no trae la fila de inyección.
    assert parse_tariff_text(APE, info["fila_tarifa"], info["fila_inyeccion"])[
        "tarifa_inyeccion_kwh"
    ] is None

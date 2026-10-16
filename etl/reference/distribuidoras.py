"""
Registro de distribuidoras eléctricas de Argentina y sus fuentes tarifarias.

Cada distribuidora tiene hasta dos tipos de fuente, que el extractor
``scrape_tarifas`` prueba en este orden:

1. **Portal nacional** (Secretaría de Energía): una página por
   distribuidora en
   ``argentina.gob.ar/economia/energia/energia-electrica/estadisticas/
   cuadros-tarifarios-<slug>`` que enlaza los cuadros mensuales alojados
   en ``energia.gob.ar/.../cuadros_tarifarios_desde_2025/<DIR>/
   <AAAA>_<MM>_<DIR>.<pdf|xlsx|zip>``. Es una fuente uniforme y con
   historial mensual desde 2025, por eso es la preferida.
2. **Fuente propia** de la distribuidora o de su ente regulador (página
   índice con enlaces a PDF y/o URLs directas o con plantilla de fecha).

Las URLs fueron relevadas en octubre de 2026 con búsqueda web; no se
pudieron verificar desde el entorno de desarrollo (la red bloqueaba esos
dominios). Si un portal cambia, basta con editar este registro.

Convenciones de plantillas de URL (``url_templates``): se formatean con
``year`` (AAAA), ``month`` (MM), ``ym`` (AAAA-MM) y ``mes`` (nombre del
mes en castellano con mayúscula inicial).
"""

from __future__ import annotations

from typing import Any, Final

NATIONAL_PAGE_BASE: Final[str] = (
    "https://www.argentina.gob.ar/economia/energia/energia-electrica/"
    "estadisticas/cuadros-tarifarios-"
)
# HTTP: el servidor corta el handshake TLS desde redes no argentinas.
NATIONAL_FILES_BASE: Final[str] = (
    "http://www.energia.gob.ar/contenidos/archivos/Reorganizacion/"
    "informacion_del_mercado/publicaciones/mercado_electrico/"
    "cuadros_tarifarios_desde_2025/"
)
NATIONAL_EXTENSIONS: Final[tuple[str, ...]] = ("pdf", "xlsx", "zip")
OCEBA_INDEX: Final[str] = "https://oceba.gba.gov.ar/nueva_web/s.php?i=17"

# ENRE: tarifas de inyección de EDENOR y EDESUR (Ley 27.424), un anexo por
# resolución; T3 BT < 300 kW, cargo variable Resto. Formato "105.100".
ENRE_INYECCION: Final[dict[str, Any]] = {
    "anclas": [r"Tarifas\s+de\s+Inyecci[oó]n", r"Tarifa\s+3\s*-\s*BT\s*<\s*300"],
    "filas": [(r"Cargo\s+Variable\s+Resto", 0)],
}
ENRE_INYECCION_URLS: Final[list[str]] = [
    # Vigente desde el 1° de mayo de 2026 (EX-2026-39929983-APN-SD#ENRE).
    "https://servicios.infoleg.gob.ar/infolegInternet/anexos/425000-429999/425422/res244-5.pdf",
]


# EDERSA: encabezado de la categoría T2 de 10 a 50 kW, en el cuadro general
# y en el de usuarios-generadores (UGER).
EDERSA_T2: Final[str] = r"^T2\s+con\s+Potencias\s+entre\s+10\s+y\s+50"


def _oceba_inyeccion(columna: int) -> dict[str, Any]:
    """
    Fila del "CUADRO TARIFARIO DE INYECCIÓN EXCEDENTES" de OCEBA.

    T3BT entre 50 y 300 kW, energía en Resto. El cuadro de EDEA, EDEN y
    EDES trae una columna por empresa (en ese orden); el de EDELAP, una.
    """
    return {
        "anclas": [
            r"CUADRO\s+TARIFARIO\s+DE\s+INYECCI",
            r"^T3BT\b.*entre\s+50\s+y\s+300",
        ],
        "filas": [(r"ENERG[IÍ]A\s+EN\s+RESTO", columna)],
    }


def _dist(
    nombre: str,
    jurisdiccion: str,
    slug: str | list[str] | None,
    *,
    dir_nacional: str | None = None,
    indices: list[str] | None = None,
    urls: list[str] | None = None,
    url_templates: list[str] | None = None,
    fila_tarifa: tuple[str, int] | dict[str, Any] | None = None,
    fila_inyeccion: dict[str, Any] | None = None,
    urls_inyeccion: list[str] | None = None,
    pdf_layout: bool = False,
    nota: str | None = None,
) -> dict[str, Any]:
    """
    Construye una entrada del registro.

    ``slug`` puede ser una lista: el portal nacional a veces crea una página
    nueva (sufijo ``-0``) y deja la anterior con enlaces vencidos.

    ``fila_tarifa`` fija la fila del cuadro de la que sale la tarifa de
    compra cuando el contexto no alcanza para reconocer la categoría:
    (regex de la fila, índice del importe tras la coincidencia).
    ``fila_inyeccion`` hace lo mismo con la tarifa de inyección (ver
    ``tariff_parser.find_hinted_row``). ``urls_inyeccion`` son documentos
    que sólo traen la tarifa de inyección (p.ej. resoluciones del ENRE).
    ``pdf_layout`` lee los PDF respetando la posición del texto (cuadros
    con varias tablas lado a lado, ver ``tariff_documents.pdf_to_text``).
    """
    slugs = [slug] if isinstance(slug, str) else list(slug or [])
    base = slugs[0].removesuffix("-0").removesuffix("-sa") if slugs else None
    return {
        "nombre": nombre,
        "jurisdiccion": jurisdiccion,
        "slug_nacional": slugs,
        "dir_nacional": dir_nacional or (base.upper() if base else None),
        "indices": indices or [],
        "urls": urls or [],
        "url_templates": url_templates or [],
        "fila_tarifa": fila_tarifa,
        "fila_inyeccion": fila_inyeccion,
        "urls_inyeccion": urls_inyeccion or [],
        "pdf_layout": pdf_layout,
        "nota": nota,
    }


# =============================================================
# Registro (código → fuentes)
# =============================================================
DISTRIBUIDORAS: Final[dict[str, dict[str, Any]]] = {
    # --- CABA / AMBA (jurisdicción nacional, ENRE) ---
    "EDENOR": _dist(
        "Empresa Distribuidora y Comercializadora Norte S.A.",
        "CABA (norte) y GBA norte/oeste",
        "edenor",
        url_templates=["https://www.edenor.com/files/{ym}/Cuadro-Tarifario.pdf"],
        fila_inyeccion=ENRE_INYECCION,
        urls_inyeccion=ENRE_INYECCION_URLS,
    ),
    "EDESUR": _dist(
        "Empresa Distribuidora Sur S.A.",
        "CABA (sur) y GBA sur",
        "edesur",
        indices=["https://www.edesur.com.ar/tarifas-cuadro-tarifario/"],
        fila_inyeccion=ENRE_INYECCION,
        urls_inyeccion=ENRE_INYECCION_URLS,
    ),
    # --- Provincia de Buenos Aires (OCEBA) ---
    "EDELAP": _dist(
        "Empresa Distribuidora La Plata S.A.",
        "Buenos Aires (Gran La Plata)",
        # El portal nacional sólo publica para las distribuidoras
        # bonaerenses un ZIP de componentes (CTT, cargos de transporte),
        # no el cuadro final: se usa OCEBA.
        None,
        indices=[OCEBA_INDEX],
        fila_inyeccion=_oceba_inyeccion(0),
    ),
    "EDEA": _dist(
        "Empresa Distribuidora de Energía Atlántica S.A.",
        "Buenos Aires (Costa Atlántica)",
        None,
        indices=[OCEBA_INDEX],
        url_templates=[
            "https://www.edeaweb.com.ar/wp-content/uploads/{year}/{month}/"
            "CT_EDEA_{mes_upper}_{year}.pdf",
            "https://www.edeaweb.com.ar/wp-content/uploads/{year}/{month}/"
            "Edea_CuadroTarifario_{mes}-1.pdf",
        ],
        fila_inyeccion=_oceba_inyeccion(0),
    ),
    "EDEN": _dist(
        "Empresa Distribuidora de Energía Norte S.A.",
        "Buenos Aires (norte y centro)",
        None,
        indices=[OCEBA_INDEX],
        fila_inyeccion=_oceba_inyeccion(1),
    ),
    "EDES": _dist(
        "Empresa Distribuidora de Energía Sur S.A.",
        "Buenos Aires (sur)",
        None,
        indices=[OCEBA_INDEX],
        fila_inyeccion=_oceba_inyeccion(2),
    ),
    # --- Resto de las provincias ---
    "ECSAPEM": _dist(
        "Energía de Catamarca S.A.P.E.M.",
        "Catamarca",
        "ecsapem",
        indices=["https://www.ecsapem.com.ar/"],
    ),
    "SECHEEP": _dist(
        "Servicios Energéticos del Chaco E.E.P.",
        "Chaco",
        "secheep",
        indices=["https://www.secheep.gob.ar/?page_id=5601"],
    ),
    "EPEC": _dist(
        "Empresa Provincial de Energía de Córdoba",
        "Córdoba",
        ["epec-0", "epec"],
        # Página Angular: los enlaces a los cuadros están en el bundle JS
        # (ver ``spa_bundle_links``). Un PDF por mes con todas las tarifas.
        indices=["https://www.epec.com.ar/informacion-comercial/grandes-clientes"],
        # Tarifa 3 (> 40 kW), baja tensión, < 300 kW, apartado a.1.2 (no
        # clubes de barrio), banda "Horas Restantes". El texto del PDF
        # pone la banda en una línea y el importe en la siguiente.
        fila_tarifa={
            "anclas": [r"^3\.1\.1\.\s*BAJA\s+TENSI", r"^a\.1\.2\."],
            "filas": [(r"Horas\s+Restantes", 0)],
        },
        # Generación distribuida (Ley 27.424 y Ley provincial 10.604),
        # misma categoría: "3.1. BAJA TENSION" → a.1.2 → Horas Restantes.
        fila_inyeccion={
            "anclas": [r"^3\.1\.\s+BAJA\s+TENSI", r"^a\.1\.2\..*inyectad"],
            "filas": [(r"Horas\s+Restantes", 0)],
        },
    ),
    "DPEC": _dist(
        "Dirección Provincial de Energía de Corrientes",
        "Corrientes",
        "dpec",
        indices=["https://www.dpec.com.ar/1500"],
    ),
    "ENERSA": _dist(
        "Energía de Entre Ríos S.A.",
        "Entre Ríos",
        "enersa",
        indices=[
            "https://www.enersa.com.ar/informacion-comercial/",
            "https://epre.gov.ar/web/",
        ],
    ),
    "REFSA": _dist(
        "Recursos y Energía Formosa S.A.",
        "Formosa",
        "refsa",
        indices=["https://recursosyenergia.com.ar/tarifas"],
    ),
    "EJESA": _dist(
        "Empresa Jujeña de Energía S.A.",
        "Jujuy",
        "ejesa",
        indices=[
            # Tarjetas con enlaces ".../GetFile?fileId=..." (ver
            # ``card_file_links``); el título dice la resolución SUSEPU.
            "https://www.ejesa.com.ar/info/pwa/institucional/costos-del-servicio",
            "https://susepu.jujuy.gob.ar/cuadros_tarifarios/",
        ],
        # T3 BT (>= 50 kW), comercios e industrias < 300 kW: fila
        # "Cargo fijo  $/kW  punta resto valle (mes 1)  punta resto valle
        # (mes 2)"; índice 4 = Resto del segundo mes (el más reciente). La
        # primera fila de ese formato después del cuadro de usuario
        # generador es la T3 BT < 300 kW (el texto del PDF sale desordenado).
        fila_tarifa={
            "anclas": [r"USUARIO\s+GENERADOR\s+Energ"],
            "filas": [(r"^\s*\d{1,3}\.\d{3}\s+\d{1,3}\.\d{3}(?=\s+\d{2,3},\d{4})", 4)],
        },
        # Usuario generador, "Servicios No Residenciales (T1G - T2 - T3)":
        # tercera fila de dos importes (mes 1 | mes 2), índice 1.
        fila_inyeccion={
            "anclas": [
                r"USUARIO\s+GENERADOR\s+Energ",
                r"^\s*\d{2,3},\d{4}\s+\d{2,3},\d{4}\s*$",
                r"^\s*\d{2,3},\d{4}\s+\d{2,3},\d{4}\s*$",
            ],
            "filas": [(r"^\s*(?=\d{2,3},\d{4}\s+\d{2,3},\d{4}\s*$)", 1)],
        },
    ),
    "APE": _dist(
        "Administración Provincial de Energía de La Pampa",
        "La Pampa",
        "ape",
        # El cuadro separa costo de compra de energía y VAD. Un PP30 en
        # autoconsumo (> 4000 kWh/mes, < 50 kW) es T2I industrial; se toma
        # el precio marginal: compra + VAD del excedente de 4000 kWh.
        fila_tarifa={
            "ancla": r"^T2I\b.*mayores\s+a\s+4000",
            "filas": [
                (r"^Costo\s+Compra\s+de\s+Energ", 0),
                (r"^VAD\s+excedente\s+de\s+4000", 0),
            ],
        },
        nota="Gran parte de La Pampa se abastece por cooperativas.",
    ),
    "EDELAR": _dist(
        "Empresa Distribuidora de Electricidad de La Rioja S.A.",
        "La Rioja",
        "edelar",
        urls=["https://www.edelar.com.ar/files.php?f=cuadro-tarifario.pdf"],
    ),
    "EDEMSA": _dist(
        "Empresa Distribuidora de Electricidad de Mendoza S.A.",
        "Mendoza (salvo zona este)",
        "edemsa",
        indices=[
            "https://www.edemsa.com/segmentacion-tarifaria/",
            "https://epremendoza.gob.ar/home/",
        ],
    ),
    "EDESTE": _dist(
        "Empresa Distribuidora de Electricidad del Este S.A.",
        "Mendoza (zona este)",
        "edeste",
        indices=["https://epremendoza.gob.ar/home/"],
    ),
    "EMSA": _dist(
        "Energía de Misiones S.A.",
        "Misiones",
        "emsa",
        indices=[
            "https://energia.misiones.gob.ar/cuadro-tarifario/",
            "http://www.energiademisiones.com.ar/servicios/cuadrotarifario_240.asp",
        ],
        # Sin categoría por demanda en BT: un PP30 en autoconsumo es
        # industrial 3.b (> 4000 kWh/mes), cargo de energía único.
        fila_tarifa={"ancla": r"^3\.b\b", "filas": [(r"^Energ[ií]a\b", 0)]},
    ),
    "EPEN": _dist(
        "Ente Provincial de Energía del Neuquén",
        "Neuquén",
        "epen",
        indices=["https://www.epen.gov.ar/index.php/cuadros-tarifarios/"],
    ),
    "EDERSA": _dist(
        "Empresa de Energía de Río Negro S.A.",
        "Río Negro",
        "edersa",
        indices=[
            "https://www.edersa.com.ar/usuarios/cuadro-tarifario/",
            "https://www.eprern.gov.ar/tarifas.html",
        ],
        # T2 entre 10 y 50 kW (un PP30 es de 25 kW), primera columna
        # (T2N_1BTb), banda Resto. El cargo de energía no incluye el de
        # transporte de otros agentes, que también se cobra por kWh: la
        # compra es la suma de ambos.
        fila_tarifa={
            "ancla": EDERSA_T2,
            "filas": [
                (r"CARGO\s+TRANSP\.?\s+OTROS\s+AGENTES", 0),
                (r"CARGO\s+ENERG[IÍ]A\s+\(R\)", 0),
            ],
        },
        # Tabla "UGER" (usuario-generador, Ley 27.424 y Ley provincial
        # 5.617), misma categoría. La inyección es energía + transporte.
        fila_inyeccion={
            "anclas": [r"Periodo:.*\bUGER\b", EDERSA_T2],
            "filas": [(r"Tarifa\s+de\s+Inyecci[oó]n\s+\(R\)", 0)],
        },
    ),
    "EDESA": _dist(
        "Empresa Distribuidora de Electricidad de Salta S.A.",
        "Salta",
        "edesa",
        # La página enlaza también los cuadros de ESED (sistemas aislados),
        # LUSAL (alumbrado) e IAP: no tienen la fila T3, no aportan compra.
        indices=["https://www.edesa.com.ar/cuadros-tarifarios/"],
        url_templates=[
            "https://www.edesa.com.ar/wp-content/uploads/{year}/{month}/"
            "Cuadro_Tarifario_{mes}_{year}_EDESA.pdf",
            "https://www.edesa.com.ar/wp-content/uploads/{year}/{month}/"
            "Cuadro_Tarifario_{mes}_{year}_EDESA-1.pdf",
        ],
        # T3 (> 50 kW) BT medianas demandas, horas resto: 5° importe tras
        # cargo por capacidad, capacidad en punta, cargo fijo y pico. Sirve
        # para la planilla nacional ("TARIFA 3 / > 50 Kw / BT-MD") y para
        # el PDF propio leído con layout ("Demandas > 50 KW / BT - MD").
        fila_tarifa={"ancla": r">\s*50\s*KW", "filas": [(r"^\s*BT\s*-\s*MD\b", 4)]},
        # "Tarifas Balance Neto": precio por origen de la generación; el
        # proyecto inyecta energía de biomasa (T_BN_BIO).
        fila_inyeccion={"ancla": r"Balance\s+Neto", "filas": [(r"\bT_BN_BIO\b", 0)]},
        pdf_layout=True,
    ),
    "ESJ": _dist(
        "Energía San Juan S.A.",
        "San Juan",
        ["esj-0", "esj"],
        # Energía San Juan hoy opera como Naturgy San Juan; el cuadro
        # mensual (PDF) está en la página de cuadros tarifarios de hogares.
        indices=[
            "https://www.naturgysj.com.ar/hogar/cuadro-tarifario/",
            "https://epresanjuan.gob.ar/",
        ],
        # T3 grandes demandas (>= 50 kW), BT, potencias < 300 kW, horas
        # restantes (primera columna = BT).
        fila_tarifa={
            "anclas": [r"^Unidad\s+BT\s+MT", r"Potencias\s+menores\s+a\s+300"],
            "filas": [(r"En\s+horas\s+restantes", 0)],
        },
        # "Valores Tarifarios a Reconocer al Usuario Generador": misma
        # tabla con cargos fijos en cero (el texto la ubica antes del
        # título). El EPRE reconoce el mismo cargo de energía de la T3.
        fila_inyeccion={
            "anclas": [
                r"Cargo\s+fijo.*\$/bimestre\s+0\.0000",
                r"^Unidad\s+BT\s+MT",
                r"Potencias\s+menores\s+a\s+300",
            ],
            "filas": [(r"En\s+horas\s+restantes", 0)],
        },
    ),
    "EDESAL": _dist(
        "Empresa Distribuidora San Luis S.A.",
        "San Luis",
        "edesal-sa",
        urls=["https://oficinavirtualedesal.com.ar/ove/upload/CuadroTarifario.pdf"],
    ),
    "SPSE": _dist(
        "Servicios Públicos Sociedad del Estado",
        "Santa Cruz",
        ["spse-0", "spse"],
        indices=["https://spse.ar/atencion-cliente"],
    ),
    "EPE": _dist(
        "Empresa Provincial de la Energía de Santa Fe",
        "Santa Fe",
        "epe",
        indices=[
            "https://www.epe.santafe.gov.ar/institucional/grandes-usuarios/",
            "https://www.epe.santafe.gov.ar/institucional/usuarios",
        ],
        # Tarifa 2 (grandes demandas > 20 kW), fila "2 B1": baja tensión,
        # demandas menores a 300 kW; columnas Pico | Resto | Valle.
        fila_tarifa=(r"^\s*2\s*B1\b.*?menores\s+a\s+300\s*kw", 1),
    ),
    "EDESE": _dist(
        "Empresa Distribuidora de Electricidad de Santiago del Estero S.A.",
        "Santiago del Estero",
        "edese",
        urls=[
            "https://www.edese.com.ar/public/assets/archivos/"
            "CuadroTarifarioVigente.pdf"
        ],
    ),
    "DPE_TDF": _dist(
        "Dirección Provincial de Energía de Tierra del Fuego",
        "Tierra del Fuego",
        "dpe",
        indices=["https://www.dpe.com.ar/usuarios/cuadro_tarifario/"],
    ),
    "EDET": _dist(
        "Empresa de Distribución Eléctrica de Tucumán S.A.",
        "Tucumán",
        "edet",
        indices=["https://www.edetsa.com/info/pwa/institucional/costos-del-servicio"],
    ),
}

# Palabras clave para reconocer el documento de cada distribuidora en
# índices compartidos (OCEBA, EPRE Mendoza): deben aparecer en la URL o
# en el texto del enlace.
INDEX_KEYWORDS: Final[dict[str, tuple[str, ...]]] = {
    "EDELAP": ("edelap",),
    "EDEA": ("edea",),
    "EDEN": ("eden",),
    "EDES": ("edes",),
    "EDEMSA": ("edemsa",),
    "EDESTE": ("edeste",),
}

# =============================================================
# Asignación geográfica
# =============================================================
# Provincia (normalizada con clean_str) → distribuidora o lista. Con una
# lista se usa el promedio de las tarifas disponibles y el resultado se
# marca como aproximado (``es_proxy``).
PROVINCIA_A_DISTRIBUIDORA: Final[dict[str, str | list[str]]] = {
    "ciudad autonoma de buenos aires": ["EDENOR", "EDESUR"],
    "capital federal": ["EDENOR", "EDESUR"],
    # Interior bonaerense: EDEN/EDEA/EDES + ~200 cooperativas (OCEBA).
    "buenos aires": ["EDEN", "EDEA", "EDES"],
    "catamarca": "ECSAPEM",
    "chaco": "SECHEEP",
    "cordoba": "EPEC",
    "corrientes": "DPEC",
    "entre rios": "ENERSA",
    "formosa": "REFSA",
    "jujuy": "EJESA",
    "la pampa": "APE",
    "la rioja": "EDELAR",
    "mendoza": "EDEMSA",
    "misiones": "EMSA",
    "neuquen": "EPEN",
    "rio negro": "EDERSA",
    "salta": "EDESA",
    "san juan": "ESJ",
    "san luis": "EDESAL",
    "santa cruz": "SPSE",
    "santa fe": "EPE",
    "santiago del estero": "EDESE",
    "tierra del fuego": "DPE_TDF",
    "tucuman": "EDET",
    # Chubut no tiene distribuidora provincial única (cooperativas como
    # SCPL Comodoro Rivadavia o la Cooperativa Eléctrica de Trelew): sin
    # mapeo, sus montos quedan en NaN.
}

# Excepciones por departamento (provincia → departamento normalizado →
# distribuidora). Sólo casos de área de concesión bien delimitada.
DEPARTAMENTO_A_DISTRIBUIDORA: Final[dict[str, dict[str, str]]] = {
    "mendoza": {
        "san martin": "EDESTE",
        "junin": "EDESTE",
        "rivadavia": "EDESTE",
        "santa rosa": "EDESTE",
        "la paz": "EDESTE",
    },
    "buenos aires": {
        "la plata": "EDELAP",
        "berisso": "EDELAP",
        "ensenada": "EDELAP",
        "brandsen": "EDELAP",
        "coronel brandsen": "EDELAP",
        "magdalena": "EDELAP",
        "punta indio": "EDELAP",
    },
}

# Distribuidoras con área parcial o compartida con cooperativas: su tarifa
# es una aproximación para el promedio provincial.
DISTRIBUIDORAS_PROXY: Final[frozenset[str]] = frozenset({"APE"})

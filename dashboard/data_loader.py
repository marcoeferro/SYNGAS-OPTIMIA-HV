"""
Carga de artefactos del ETL y utilidades de agregación y geografía.

Solo lectura. Usa DuckDB para leer los Parquet del pipeline y expone:

- ``load_biomasa``: registros válidos por campaña (biomasa, energía y
  dinero por registro).
- ``load_potencial``: potencial anual del período de referencia.
- ``load_tarifas`` / ``load_tarifas_historial``: referencia de tarifas por
  distribuidora y su historial.
- ``load_descartados`` / ``load_discrepancias``: auditoría de la
  reconciliación entre fuentes.
- Claves geográficas para unir los datos con los polígonos GADM.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import streamlit as st

# =============================================================
# Rutas
# =============================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent
GEO_DIR = Path(__file__).resolve().parent / "geo"
REFERENCE_DIR = PROJECT_ROOT / "data" / "reference"

# El pipeline persiste biomasa_validos en processed/ y una copia en audit/.
CANDIDATE_BIOMASA = [
    PROJECT_ROOT / "data" / "processed" / "biomasa_validos.parquet",
    PROJECT_ROOT / "data" / "audit" / "biomasa_validos.parquet",
]
PATH_POTENCIAL = PROJECT_ROOT / "data" / "processed" / "potencial_energetico_anual.parquet"
PATH_DESCARTADOS = PROJECT_ROOT / "data" / "audit" / "descartados_reconciliacion.parquet"
PATH_DISCREPANCIAS = PROJECT_ROOT / "data" / "audit" / "discrepancias_cba_vs_magyp.parquet"
PATH_HISTORIAL = REFERENCE_DIR / "tarifas_historial.csv"
PATH_ALERTAS = PROJECT_ROOT / "data" / "audit" / "alertas_calidad.parquet"

GEO_PROV = GEO_DIR / "gadm41_ARG_1.json"
GEO_DEPT = GEO_DIR / "gadm41_ARG_2.json"

# =============================================================
# Columnas y métricas
# =============================================================
COL_BIOMASA = "Residuo de Biomasa (Tn)"
COL_RECUPERABLE = "Residuo Recuperable (Tn)"
COL_KWH = "kwh_generados"
COL_KWH_AUTO = "kwh_autoconsumo"
COL_KWH_INY = "kwh_inyectados"
COL_EQUIPOS = "equipos_pp30_equivalentes"
COL_BENEFICIO = "beneficio_total_ars"
COL_AHORRO = "ahorro_autoconsumo_ars"
COL_CREDITO = "credito_inyeccion_ars"

SUM_COLS = [
    "Superficie (Ha)", "Produccion (Tn)", COL_BIOMASA, COL_RECUPERABLE,
    COL_KWH, COL_KWH_AUTO, COL_KWH_INY, COL_EQUIPOS,
    COL_AHORRO, COL_CREDITO, COL_BENEFICIO,
]

# Métrica → (columna, etiqueta, unidad mostrada, divisor de la columna).
METRICAS: dict[str, dict[str, Any]] = {
    "Biomasa residual": {
        "col": COL_BIOMASA, "unidad": "t MS/año", "divisor": 1.0,
        "titulo": "Biomasa residual",
    },
    "Energía": {
        "col": COL_KWH, "unidad": "GWh/año", "divisor": 1e6,
        "titulo": "Energía eléctrica generable (PP30)",
    },
    "Dinero": {
        "col": COL_BENEFICIO, "unidad": "millones de ARS/año", "divisor": 1e6,
        "titulo": "Beneficio bruto (ahorro + inyección)",
    },
}

# Escala secuencial de un solo tono (azul, claro → oscuro).
SEQ_SCALE = [
    [0.0, "#cde2fb"], [0.17, "#9ec5f4"], [0.33, "#6da7ec"], [0.5, "#3987e5"],
    [0.67, "#256abf"], [0.83, "#184f95"], [1.0, "#0d366b"],
]
SERIE_1 = "#2a78d6"   # autoconsumo
SERIE_2 = "#eb6834"   # inyección
NEUTRO = "#e1e0d9"    # polígonos sin dato
BORDE = "#898781"

ESTADOS_TARIFA = {
    "extraido": ("✅", "Extraída del cuadro vigente"),
    "parsed_pdf": ("✅", "Extraída del cuadro vigente"),
    "fallback_previous": ("⚠️", "Valor anterior (fuente caída)"),
    "baseline_manual": ("⚠️", "Valor manual"),
    "sin_dato": ("⛔", "Sin dato"),
}


def _resolve_biomasa_path() -> Path:
    for p in CANDIDATE_BIOMASA:
        if p.exists():
            return p
    raise FileNotFoundError(
        "No se encontró biomasa_validos.parquet en data/processed ni data/audit. "
        "Ejecutá el pipeline ETL primero (make etl o make docker-etl)."
    )


# =============================================================
# Claves geográficas
# =============================================================
def norm_key(s: object) -> str:
    """Normaliza texto para join geográfico (minúsculas, sin acentos, alfanumérico)."""
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    text = str(s).lower().strip()
    text = "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"[^a-z0-9]+", "", text)


# Números en nombres de departamento: GADM los escribe en letras
# ("VeinticincodeMayo", "NuevedeJulio", "DocedeOctubre").
NUMEROS = {
    "1": "primero", "2": "dos", "9": "nueve", "12": "doce", "25": "veinticinco",
}
# (provincia, departamento) normalizados → nombre GADM normalizado: nombres
# abreviados, truncados o renombrados en los datos respecto de GADM 4.1.
DEPT_GEO_ALIASES: dict[tuple[str, str], str] = {
    ("buenosaires", "coroneldemarinalrosales"): "coroneldemarinaleonardorosal",
    ("buenosaires", "florentinoameghino"): "ameghino",
    ("jujuy", "doctormanuelbelgrano"): "capital",
    ("larioja", "generalangelvpenaloza"): "generalangelvicentepenaloza",
    ("larioja", "generaljuanfquiroga"): "generaljuanfacundoquiroga",
    ("sanluis", "juanmartindepueyrredon"): "lacapital",
}


def dept_geo_key(prov_key: str, dept_key: str) -> str:
    """Clave ``provincia|departamento`` comparable con los polígonos GADM."""
    m = re.match(r"^(\d+)(de.*)$", dept_key)
    if m and m.group(1) in NUMEROS:
        dept_key = NUMEROS[m.group(1)] + m.group(2)
    dept_key = DEPT_GEO_ALIASES.get((prov_key, dept_key), dept_key)
    return f"{prov_key}|{dept_key}"


def _geo_dept_id(props: dict[str, Any]) -> str:
    # "SanFernando(1)" / "SanFernando(2)": un partido en dos polígonos.
    name = re.sub(r"\(\d+\)$", "", props["NAME_2"])
    return f"{norm_key(props['NAME_1'])}|{norm_key(name)}"


# =============================================================
# Carga
# =============================================================
@st.cache_resource
def get_connection() -> duckdb.DuckDBPyConnection:
    """Conexión DuckDB en memoria (resource cacheada por proceso Streamlit)."""
    return duckdb.connect(database=":memory:")


def _read_parquet(path: Path) -> pd.DataFrame:
    return get_connection().execute(
        f"SELECT * FROM read_parquet('{path.as_posix()}')"
    ).fetchdf()


_PARTICULAS = {"de", "del", "la", "las", "los", "y", "e"}


def nice_name(s: object) -> object:
    """Nombre legible: "santiago del estero" → "Santiago del Estero"."""
    if not isinstance(s, str):
        return s
    words = s.split()
    return " ".join(
        w if i and w in _PARTICULAS else w[:1].upper() + w[1:] for i, w in enumerate(words)
    )


def _add_geo_keys(df: pd.DataFrame) -> pd.DataFrame:
    # El ETL normaliza a minúsculas; para mostrar se capitaliza (las claves
    # geográficas se calculan igual sobre el texto normalizado).
    for col in ("Provincia", "Departamento", "Cultivo"):
        if col in df.columns:
            df[col] = df[col].map(nice_name)
    df["_prov_key"] = df["Provincia"].map(norm_key)
    df["_dept_key"] = df["Departamento"].map(norm_key)
    df["_geo_dept"] = [
        dept_geo_key(p, d) for p, d in zip(df["_prov_key"], df["_dept_key"], strict=True)
    ]
    return df


# Columnas que agrega la etapa de energía y dinero del ETL. Un Parquet sin
# ellas fue generado por una versión anterior del pipeline.
REQUIRED_ENERGY_COLS = (COL_KWH, COL_BENEFICIO)


def _mtime(path: Path) -> float | None:
    return path.stat().st_mtime if path.exists() else None


def horas_desde_ultima_corrida(path: Path = PATH_POTENCIAL) -> float | None:
    """
    Horas desde que el ETL publicó resultados por última vez.

    Se mira el potencial anual: el ETL lo reescribe en cada corrida exitosa
    (no en una fallida ni en modo estricto con alertas). None si no existe.
    """
    mtime = _mtime(path)
    if mtime is None:
        return None
    return (pd.Timestamp.now(tz="UTC").timestamp() - mtime) / 3600


def file_info(path: Path) -> str:
    """Ruta y fecha de modificación de un artefacto (para mensajes)."""
    mtime = _mtime(path)
    if mtime is None:
        return f"`{path.relative_to(PROJECT_ROOT)}` (no existe)"
    fecha = pd.Timestamp(mtime, unit="s", tz="UTC").tz_convert(
        "America/Argentina/Buenos_Aires"
    )
    return f"`{path.relative_to(PROJECT_ROOT)}` (modificado {fecha:%Y-%m-%d %H:%M})"


# La caché se indexa por (ruta, fecha de modificación): cuando el ETL
# reescribe un Parquet, el dashboard lo vuelve a leer sin reiniciarse.
# ``max_entries`` acota la memoria: sin límite, cada corrida del ETL dejaba
# en memoria otra copia de biomasa_validos (~93 MB) que nunca se liberaba.
# Con 4 archivos y 8 entradas se descartan las versiones viejas (LRU).
# Antes la caché no tenía en cuenta el archivo y, si el dashboard estaba
# abierto mientras corría el ETL, seguía mostrando los datos viejos (o
# "archivo inexistente") hasta reiniciar Streamlit.
@st.cache_data(show_spinner="Cargando datos…", max_entries=8)
def _load_parquet_cached(path: str, mtime: float, geo: bool) -> pd.DataFrame:
    # ``mtime`` sólo forma parte de la clave de caché (no lleva "_" adelante:
    # Streamlit excluye de la clave los parámetros que empiezan con "_").
    del mtime
    df = _read_parquet(Path(path))
    return _add_geo_keys(df) if geo else df


def _load(path: Path, geo: bool = False) -> pd.DataFrame | None:
    mtime = _mtime(path)
    if mtime is None:
        return None
    return _load_parquet_cached(str(path), mtime, geo)


def _stop_outdated(path: Path, missing: list[str]) -> None:
    st.error(
        f"El archivo {file_info(path)} fue generado por una versión anterior del ETL: "
        f"le faltan las columnas {', '.join(missing)}.\n\n"
        "Volvé a ejecutar el ETL con el código actual. En Docker la imagen guarda el "
        "código del ETL, así que hay que reconstruirla antes de correrlo:\n\n"
        "```\ndocker compose build etl_pipeline\n"
        "docker compose --profile etl run --rm etl_pipeline\n```\n\n"
        "(`.\\scripts\\Run-Etl.ps1` y `make docker-etl` ya reconstruyen la imagen.)"
    )
    st.stop()


def load_biomasa() -> pd.DataFrame:
    """Registros válidos por campaña con biomasa, energía y dinero."""
    path = _resolve_biomasa_path()
    df = _load(path, geo=True)
    missing = [c for c in REQUIRED_ENERGY_COLS if c not in df.columns]
    if missing:
        _stop_outdated(path, missing)
    return df


def load_potencial() -> pd.DataFrame | None:
    """Potencial anual (promedio del período de referencia)."""
    df = _load(PATH_POTENCIAL, geo=True)
    if df is not None:
        missing = [c for c in REQUIRED_ENERGY_COLS if c not in df.columns]
        if missing:
            _stop_outdated(PATH_POTENCIAL, missing)
    return df


def stop_missing_potencial() -> None:
    """Corta la página con un mensaje accionable si falta el potencial anual."""
    st.error(
        f"No se encontró {file_info(PATH_POTENCIAL)}.\n\n"
        "Lo genera el ETL actual (etapa 8, potencial anual). Si ya lo ejecutaste "
        "en Docker, probablemente corrió con una imagen vieja: la imagen guarda el "
        "código del ETL y hay que reconstruirla.\n\n"
        "```\ndocker compose build etl_pipeline\n"
        "docker compose --profile etl run --rm etl_pipeline\n```\n\n"
        "Revisá también que el log del ETL termine con \"Pipeline completado\"."
    )
    st.stop()


def load_descartados() -> pd.DataFrame | None:
    """Registros descartados en la reconciliación entre fuentes."""
    return _load(PATH_DESCARTADOS)


def load_alertas() -> pd.DataFrame | None:
    """Alertas de los controles de calidad de la última corrida del ETL."""
    return _load(PATH_ALERTAS)


def load_discrepancias() -> pd.DataFrame | None:
    """Diferencias CBA vs MAGyP de los pares reconciliados."""
    return _load(PATH_DISCREPANCIAS)


@st.cache_data(max_entries=2)
def _load_json_cached(path: str, mtime: float) -> dict[str, Any]:
    del mtime  # sólo para la clave de caché
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_tarifas() -> tuple[dict[str, Any] | None, Path | None]:
    """JSON de tarifas más reciente de ``data/reference`` y su ruta."""
    files = sorted(REFERENCE_DIR.glob("*_tarifas.json"))
    if not files:
        return None, None
    return _load_json_cached(str(files[-1]), files[-1].stat().st_mtime), files[-1]


@st.cache_data(max_entries=2)
def _load_historial_cached(mtime: float) -> pd.DataFrame:
    del mtime  # sólo para la clave de caché
    from etl.loaders.tariff_history import load_history, representative_by_month

    return representative_by_month(load_history(REFERENCE_DIR))


def load_tarifas_historial() -> pd.DataFrame | None:
    """Historial de cuadros tarifarios (un cuadro pleno por mes)."""
    mtime = _mtime(PATH_HISTORIAL)
    return None if mtime is None else _load_historial_cached(mtime)


def tarifas_table(cfg: dict[str, Any]) -> pd.DataFrame:
    """Tabla de distribuidoras con tarifa, vigencia, fuente y estado."""
    rows = []
    for code, info in cfg.get("distribuidoras", {}).items():
        estado = info.get("estado_campos", {}).get("tarifa_compra_kwh", "sin_dato")
        icono, texto = ESTADOS_TARIFA.get(estado, ("❔", estado))
        rows.append({
            "Distribuidora": code,
            "Jurisdicción": info.get("jurisdiccion") or info.get("provincia") or "",
            "Compra ($/kWh)": pd.to_numeric(info.get("tarifa_compra_kwh"), errors="coerce"),
            "Inyección ($/kWh)": pd.to_numeric(info.get("tarifa_inyeccion_kwh"), errors="coerce"),
            "Vigencia": info.get("vigencia"),
            "Fuente": info.get("fuente_tipo"),
            "Estado": f"{icono} {texto}",
            "Documento": info.get("documento"),
        })
    return pd.DataFrame(rows)


@st.cache_data
def load_geojson_provinces() -> dict:
    """Polígonos GADM de provincias con ``id`` normalizado."""
    with open(GEO_PROV, encoding="utf-8") as f:
        geo = json.load(f)
    for feat in geo["features"]:
        feat["id"] = norm_key(feat["properties"]["NAME_1"])
    return geo


@st.cache_data
def load_geojson_departments() -> dict:
    """Polígonos GADM de departamentos con ``id`` provincia|departamento."""
    with open(GEO_DEPT, encoding="utf-8") as f:
        geo = json.load(f)
    for feat in geo["features"]:
        feat["id"] = _geo_dept_id(feat["properties"])
    return geo


def geo_names(geo: dict, level: str) -> pd.DataFrame:
    """Id y nombre legible de cada polígono (para la capa de contornos)."""
    rows = []
    for feat in geo["features"]:
        p = feat["properties"]
        name = p["NAME_1"] if level == "provincia" else f"{p['NAME_2']} ({p['NAME_1']})"
        rows.append({"id": feat["id"], "nombre": re.sub(r"(?<=[a-zé])(?=[A-Z])", " ", name)})
    return pd.DataFrame(rows).drop_duplicates("id")


# =============================================================
# Filtros y agregaciones
# =============================================================
def filter_biomasa(
    df: pd.DataFrame,
    provincias: list[str] | None = None,
    departamentos: list[str] | None = None,
    cultivos: list[str] | None = None,
    campanas: list[str] | None = None,
) -> pd.DataFrame:
    """Aplica filtros opcionales. Listas vacías o None = sin filtro."""
    out = df
    if provincias:
        out = out[out["Provincia"].isin(provincias)]
    if departamentos:
        out = out[out["Departamento"].isin(departamentos)]
    if cultivos:
        out = out[out["Cultivo"].isin(cultivos)]
    if campanas and "Campaña" in out.columns:
        out = out[out["Campaña"].isin(campanas)]
    return out


def _sum_cols(df: pd.DataFrame) -> dict[str, str]:
    return {c: "sum" for c in SUM_COLS if c in df.columns}


def aggregate_by_province(df: pd.DataFrame, divisor: float = 1.0) -> pd.DataFrame:
    """Suma por provincia; ``divisor`` convierte a promedio anual (n campañas)."""
    g = df.groupby(["Provincia", "_prov_key"], as_index=False).agg(_sum_cols(df))
    num = [c for c in SUM_COLS if c in g.columns]
    g[num] = g[num] / divisor
    return g


def aggregate_by_department(df: pd.DataFrame, divisor: float = 1.0) -> pd.DataFrame:
    """Suma por departamento con la clave de polígono GADM."""
    g = df.groupby(
        ["Provincia", "Departamento", "_geo_dept"], as_index=False
    ).agg(_sum_cols(df))
    num = [c for c in SUM_COLS if c in g.columns]
    g[num] = g[num] / divisor
    return g


def dept_geo_coverage(df: pd.DataFrame) -> pd.DataFrame:
    """Departamentos de los datos sin polígono en el mapa (auditoría)."""
    ids = {f["id"] for f in load_geojson_departments()["features"]}
    g = df.groupby(["Provincia", "Departamento", "_geo_dept"], as_index=False)[
        COL_BIOMASA
    ].sum()
    return g[~g["_geo_dept"].isin(ids)].drop(columns="_geo_dept")


def default_campaigns(df: pd.DataFrame, n: int = 5) -> list[str]:
    """Últimas ``n`` campañas completas (excluye la campaña en curso)."""
    from etl.transformers.reference_period import select_reference_campaigns

    return select_reference_campaigns(df, n)


# =============================================================
# Formato
# =============================================================
def format_tn(x: float) -> str:
    """Toneladas con sufijo k / M."""
    if pd.isna(x):
        return "—"
    if abs(x) >= 1_000_000:
        return f"{x / 1_000_000:,.2f} M t"
    if abs(x) >= 1_000:
        return f"{x / 1_000:,.1f} k t"
    return f"{x:,.0f} t"


def format_kwh(x: float) -> str:
    """Energía (kWh) expresada en MWh, GWh o TWh."""
    if pd.isna(x):
        return "—"
    if abs(x) >= 1e9:
        return f"{x / 1e9:,.2f} TWh"
    if abs(x) >= 1e6:
        return f"{x / 1e6:,.1f} GWh"
    return f"{x / 1e3:,.0f} MWh"


def format_ars(x: float) -> str:
    """Pesos con escala (M, mil M, billones)."""
    if pd.isna(x):
        return "—"
    if abs(x) >= 1e12:
        return f"$ {x / 1e12:,.2f} billones"
    if abs(x) >= 1e9:
        return f"$ {x / 1e9:,.1f} mil M"
    if abs(x) >= 1e6:
        return f"$ {x / 1e6:,.1f} M"
    return f"$ {x:,.0f}"


def format_metric(metrica: str, x: float) -> str:
    """Formato del total de una métrica de ``METRICAS``."""
    return {"Biomasa residual": format_tn, "Energía": format_kwh, "Dinero": format_ars}[
        metrica
    ](x)

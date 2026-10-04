"""
Carga de Parquet y utilidades de normalización geográfica.

Solo lectura. Usa DuckDB para agregaciones eficientes sobre archivos
Parquet sin cargarlos completos en memoria cuando no es necesario.
"""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

# =============================================================
# Rutas
# =============================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent
GEO_DIR = Path(__file__).resolve().parent / "geo"

# El pipeline actual persiste biomasa_validos en audit/ (histórico).
# Se buscan ambas ubicaciones por compatibilidad.
CANDIDATE_BIOMASA = [
    PROJECT_ROOT / "data" / "processed" / "biomasa_validos.parquet",
    PROJECT_ROOT / "data" / "audit" / "biomasa_validos.parquet",
]
PATH_DESCARTADOS = PROJECT_ROOT / "data" / "audit" / "descartados_reconciliacion.parquet"
PATH_DISCREPANCIAS = PROJECT_ROOT / "data" / "audit" / "discrepancias_cba_vs_magyp.parquet"

GEO_PROV = GEO_DIR / "gadm41_ARG_1.json"
GEO_DEPT = GEO_DIR / "gadm41_ARG_2.json"


def _resolve_biomasa_path() -> Path:
    for p in CANDIDATE_BIOMASA:
        if p.exists():
            return p
    raise FileNotFoundError(
        "No se encontró biomasa_validos.parquet en data/processed ni data/audit. "
        "Ejecutá el pipeline ETL primero (make etl o make docker-etl)."
    )


def norm_key(s: object) -> str:
    """Normaliza texto para join geográfico (minúsculas, sin acentos, alfanumérico)."""
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    text = str(s).lower().strip()
    text = "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text


@st.cache_resource
def get_connection() -> duckdb.DuckDBPyConnection:
    """Conexión DuckDB en memoria (resource cacheada por proceso Streamlit)."""
    return duckdb.connect(database=":memory:")


@st.cache_data(show_spinner="Cargando biomasa…")
def load_biomasa() -> pd.DataFrame:
    path = _resolve_biomasa_path()
    con = get_connection()
    df = con.execute(
        f"SELECT * FROM read_parquet('{path.as_posix()}')"
    ).fetchdf()
    # Claves de join geográfico
    df["_prov_key"] = df["Provincia"].map(norm_key)
    df["_dept_key"] = df["Departamento"].map(norm_key)
    return df


@st.cache_data(show_spinner="Cargando descartados…")
def load_descartados() -> pd.DataFrame | None:
    if not PATH_DESCARTADOS.exists():
        return None
    con = get_connection()
    return con.execute(
        f"SELECT * FROM read_parquet('{PATH_DESCARTADOS.as_posix()}')"
    ).fetchdf()


@st.cache_data(show_spinner="Cargando discrepancias…")
def load_discrepancias() -> pd.DataFrame | None:
    if not PATH_DISCREPANCIAS.exists():
        return None
    con = get_connection()
    return con.execute(
        f"SELECT * FROM read_parquet('{PATH_DISCREPANCIAS.as_posix()}')"
    ).fetchdf()


@st.cache_data
def load_geojson_provinces() -> dict:
    with open(GEO_PROV, encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_geojson_departments() -> dict:
    with open(GEO_DEPT, encoding="utf-8") as f:
        return json.load(f)


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
    if campanas:
        out = out[out["Campaña"].isin(campanas)]
    return out


def aggregate_by_province(df: pd.DataFrame) -> pd.DataFrame:
    """Suma biomasa y producción por provincia (para mapa)."""
    if df.empty:
        return pd.DataFrame(columns=["Provincia", "_prov_key", "Residuo de Biomasa (Tn)", "Produccion (Tn)", "Superficie (Ha)"])
    g = (
        df.groupby(["Provincia", "_prov_key"], as_index=False)
        .agg(
            {
                "Residuo de Biomasa (Tn)": "sum",
                "Produccion (Tn)": "sum",
                "Superficie (Ha)": "sum",
            }
        )
    )
    return g


def aggregate_by_department(df: pd.DataFrame) -> pd.DataFrame:
    """Suma biomasa por provincia+departamento (para mapa departamental)."""
    if df.empty:
        return pd.DataFrame(
            columns=[
                "Provincia",
                "Departamento",
                "_prov_key",
                "_dept_key",
                "Residuo de Biomasa (Tn)",
                "Produccion (Tn)",
                "Superficie (Ha)",
            ]
        )
    g = (
        df.groupby(["Provincia", "Departamento", "_prov_key", "_dept_key"], as_index=False)
        .agg(
            {
                "Residuo de Biomasa (Tn)": "sum",
                "Produccion (Tn)": "sum",
                "Superficie (Ha)": "sum",
            }
        )
    )
    return g


def default_campaigns(df: pd.DataFrame, n: int = 5) -> list[str]:
    """Últimas ``n`` campañas completas (excluye la campaña en curso)."""
    from etl.transformers.reference_period import select_reference_campaigns

    return select_reference_campaigns(df, n)


def format_tn(x: float) -> str:
    if pd.isna(x):
        return "—"
    if abs(x) >= 1_000_000:
        return f"{x / 1_000_000:,.2f} M Tn"
    if abs(x) >= 1_000:
        return f"{x / 1_000:,.1f} k Tn"
    return f"{x:,.0f} Tn"

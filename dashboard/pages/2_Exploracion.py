"""Página Exploración: filtros cruzados, series y tablas detalladas."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.data_loader import (
    default_campaigns,
    filter_biomasa,
    format_tn,
    load_biomasa,
)

st.set_page_config(page_title="Exploración | Biomasa", page_icon="🔍", layout="wide")
st.title("Exploración")

df = load_biomasa()

with st.sidebar:
    st.header("Filtros")
    provincias = sorted(df["Provincia"].dropna().unique().tolist())
    sel_prov = st.multiselect("Provincia", provincias, default=[])

    depts_available = (
        sorted(df[df["Provincia"].isin(sel_prov)]["Departamento"].dropna().unique().tolist())
        if sel_prov
        else sorted(df["Departamento"].dropna().unique().tolist())
    )
    sel_dept = st.multiselect("Departamento", depts_available, default=[])

    cultivos = sorted(df["Cultivo"].dropna().unique().tolist())
    sel_cult = st.multiselect("Cultivo", cultivos, default=[])

    campanas = sorted(df["Campaña"].dropna().unique().tolist())
    default_camp = default_campaigns(df, 10)
    sel_camp = st.multiselect("Campaña", campanas, default=default_camp)

filtered = filter_biomasa(
    df,
    provincias=sel_prov or None,
    departamentos=sel_dept or None,
    cultivos=sel_cult or None,
    campanas=sel_camp or None,
)

c1, c2, c3 = st.columns(3)
c1.metric("Filas", f"{len(filtered):,}")
c2.metric("Biomasa residual", format_tn(filtered["Residuo de Biomasa (Tn)"].sum()))
c3.metric("Producción", format_tn(filtered["Produccion (Tn)"].sum()))

if filtered.empty:
    st.warning("Sin datos para los filtros elegidos.")
    st.stop()

# --- Serie temporal ---
st.subheader("Evolución por campaña")
by_camp = (
    filtered.groupby("Campaña", as_index=False)
    .agg(
        {
            "Residuo de Biomasa (Tn)": "sum",
            "Produccion (Tn)": "sum",
            "Superficie (Ha)": "sum",
        }
    )
    .sort_values("Campaña")
)
fig_ts = px.line(
    by_camp,
    x="Campaña",
    y=["Residuo de Biomasa (Tn)", "Produccion (Tn)"],
    markers=True,
    title="Biomasa residual y producción por campaña",
)
fig_ts.update_layout(legend_title_text="", height=400, xaxis_tickangle=-45)
st.plotly_chart(fig_ts, use_container_width=True)

# --- Comparación cultivo x provincia (si hay pocos) ---
st.subheader("Biomasa por cultivo")
by_cult = (
    filtered.groupby("Cultivo", as_index=False)["Residuo de Biomasa (Tn)"]
    .sum()
    .sort_values("Residuo de Biomasa (Tn)", ascending=False)
)
fig_cult = px.bar(
    by_cult,
    x="Cultivo",
    y="Residuo de Biomasa (Tn)",
    title="Total biomasa residual por cultivo (filtros aplicados)",
)
fig_cult.update_layout(height=400, xaxis_tickangle=-40)
st.plotly_chart(fig_cult, use_container_width=True)

# --- Tabla detalle ---
st.subheader("Detalle tabular")
show_cols = [
    "Provincia",
    "Departamento",
    "Campaña",
    "Cultivo",
    "Superficie (Ha)",
    "Produccion (Tn)",
    "Rendimiento (Tn/Ha)",
    "FR",
    "Residuo de Biomasa (Tn)",
    "Residuo de Biomasa (Tn/Ha)",
    "fuente",
]
show_cols = [c for c in show_cols if c in filtered.columns]

max_rows = st.slider("Máximo de filas a mostrar", 100, 5000, 1000, 100)
st.dataframe(
    filtered[show_cols]
    .sort_values(["Campaña", "Provincia", "Departamento", "Cultivo"])
    .head(max_rows)
    .style.format(
        {
            "Superficie (Ha)": "{:,.1f}",
            "Produccion (Tn)": "{:,.1f}",
            "Rendimiento (Tn/Ha)": "{:,.3f}",
            "FR": "{:,.3f}",
            "Residuo de Biomasa (Tn)": "{:,.1f}",
            "Residuo de Biomasa (Tn/Ha)": "{:,.3f}",
        },
        na_rep="—",
    ),
    use_container_width=True,
    hide_index=True,
)

csv = filtered[show_cols].to_csv(index=False).encode("utf-8")
st.download_button(
    "Descargar CSV filtrado",
    data=csv,
    file_name="biomasa_filtrada.csv",
    mime="text/csv",
)

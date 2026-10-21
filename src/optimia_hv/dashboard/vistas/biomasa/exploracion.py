"""Página Exploración: filtros cruzados, series y tablas detalladas."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from optimia_hv.dashboard.data_loader import (
    COL_BENEFICIO,
    COL_KWH,
    default_campaigns,
    filter_biomasa,
    format_ars,
    format_kwh,
    format_tn,
    load_biomasa,
)

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

c1, c2, c3, c4 = st.columns(4)
c1.metric("Filas", f"{len(filtered):,}")
c2.metric("Biomasa residual (suma)", format_tn(filtered["Residuo de Biomasa (Tn)"].sum()))
c3.metric("Energía (suma)", format_kwh(filtered[COL_KWH].sum()))
c4.metric("Beneficio bruto (suma)", format_ars(filtered[COL_BENEFICIO].sum()))
st.caption("Sumas de todas las campañas seleccionadas (no promedio anual).")

if filtered.empty:
    st.warning("Sin datos para los filtros elegidos.")
    st.stop()

# --- Serie temporal ---
# Una magnitud por gráfico (nunca dos escalas en un mismo eje).
st.subheader("Evolución por campaña")
by_camp = (
    filtered.groupby("Campaña", as_index=False)
    .agg({"Residuo de Biomasa (Tn)": "sum", "Produccion (Tn)": "sum", COL_KWH: "sum"})
    .sort_values("Campaña")
)
by_camp["Energía (GWh)"] = by_camp[COL_KWH] / 1e6
serie = st.segmented_control(
    "Serie", ["Residuo de Biomasa (Tn)", "Produccion (Tn)", "Energía (GWh)"],
    default="Residuo de Biomasa (Tn)", key="serie_exploracion",
) or "Residuo de Biomasa (Tn)"
fig_ts = px.line(by_camp, x="Campaña", y=serie, markers=True, title=f"{serie} por campaña")
fig_ts.update_traces(line={"width": 2, "color": "#2a78d6"}, marker={"size": 8})
fig_ts.update_layout(height=400, xaxis_tickangle=-45)
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
    color_discrete_sequence=["#2a78d6"],
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
    "Residuo Recuperable (Tn)",
    "kwh_generados",
    "distribuidora",
    "tarifa_compra_kwh",
    "beneficio_total_ars",
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
            "Residuo Recuperable (Tn)": "{:,.1f}",
            "kwh_generados": "{:,.0f}",
            "tarifa_compra_kwh": "{:,.2f}",
            "beneficio_total_ars": "{:,.0f}",
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

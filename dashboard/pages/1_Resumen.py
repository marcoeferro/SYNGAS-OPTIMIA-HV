"""Página Resumen: KPIs, rankings y mapas coropléticos."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.data_loader import (
    aggregate_by_department,
    default_campaigns,
    aggregate_by_province,
    filter_biomasa,
    format_tn,
    load_biomasa,
    load_geojson_departments,
    load_geojson_provinces,
    norm_key,
)

st.set_page_config(page_title="Resumen | Biomasa", page_icon="📊", layout="wide")
st.title("Resumen")

df = load_biomasa()

# --- Filtros globales de la página ---
with st.sidebar:
    st.header("Filtros")
    campanas = sorted(df["Campaña"].dropna().unique().tolist())
    # Últimas 5 campañas completas: la campaña en curso tiene datos parciales.
    default_camp = default_campaigns(df, 5)
    sel_campanas = st.multiselect("Campaña", campanas, default=default_camp)
    cultivos = sorted(df["Cultivo"].dropna().unique().tolist())
    sel_cultivos = st.multiselect("Cultivo", cultivos, default=[])
    st.caption("Vacío = todos los cultivos.")

filtered = filter_biomasa(df, cultivos=sel_cultivos or None, campanas=sel_campanas or None)

# --- KPIs ---
c1, c2, c3, c4 = st.columns(4)
total_bio = filtered["Residuo de Biomasa (Tn)"].sum()
total_prod = filtered["Produccion (Tn)"].sum()
total_sup = filtered["Superficie (Ha)"].sum()
n_dept = filtered[["Provincia", "Departamento"]].drop_duplicates().shape[0]

# Los totales se expresan como promedio anual: sumar varias campañas no
# representa ninguna magnitud física.
n_camp = max(filtered["Campaña"].nunique(), 1)
c1.metric("Biomasa residual (prom. anual)", format_tn(total_bio / n_camp))
c2.metric("Producción (prom. anual)", format_tn(total_prod / n_camp))
c3.metric(
    "Superficie (prom. anual)",
    f"{total_sup / n_camp:,.0f} Ha" if pd.notna(total_sup) else "—",
)
c4.metric("Deptos. con datos", f"{n_dept:,}")

if filtered.empty:
    st.warning("No hay datos con los filtros seleccionados.")
    st.stop()

# --- Rankings ---
st.subheader("Rankings")
col_a, col_b = st.columns(2)

with col_a:
    by_cult = (
        filtered.groupby("Cultivo", as_index=False)["Residuo de Biomasa (Tn)"]
        .sum()
        .sort_values("Residuo de Biomasa (Tn)", ascending=False)
        .head(12)
    )
    fig_c = px.bar(
        by_cult,
        x="Residuo de Biomasa (Tn)",
        y="Cultivo",
        orientation="h",
        title="Top cultivos por biomasa residual",
    )
    fig_c.update_layout(yaxis={"categoryorder": "total ascending"}, height=420)
    st.plotly_chart(fig_c, use_container_width=True)

with col_b:
    by_prov = (
        filtered.groupby("Provincia", as_index=False)["Residuo de Biomasa (Tn)"]
        .sum()
        .sort_values("Residuo de Biomasa (Tn)", ascending=False)
        .head(12)
    )
    fig_p = px.bar(
        by_prov,
        x="Residuo de Biomasa (Tn)",
        y="Provincia",
        orientation="h",
        title="Top provincias por biomasa residual",
    )
    fig_p.update_layout(yaxis={"categoryorder": "total ascending"}, height=420)
    st.plotly_chart(fig_p, use_container_width=True)

# --- Mapas ---
st.subheader("Mapas")
tab_prov, tab_dept = st.tabs(["Por provincia", "Por departamento"])

with tab_prov:
    geo_prov = load_geojson_provinces()
    agg_p = aggregate_by_province(filtered)
    # Feature id = norm NAME_1
    for feat in geo_prov["features"]:
        feat["id"] = norm_key(feat["properties"]["NAME_1"])
    fig_map_p = px.choropleth(
        agg_p,
        geojson=geo_prov,
        locations="_prov_key",
        featureidkey="id",
        color="Residuo de Biomasa (Tn)",
        hover_name="Provincia",
        hover_data={
            "Residuo de Biomasa (Tn)": ":,.0f",
            "Produccion (Tn)": ":,.0f",
            "Superficie (Ha)": ":,.0f",
            "_prov_key": False,
        },
        color_continuous_scale="YlOrRd",
        title="Biomasa residual por provincia",
    )
    fig_map_p.update_geos(fitbounds="locations", visible=False)
    fig_map_p.update_layout(height=560, margin=dict(l=0, r=0, t=40, b=0))
    st.plotly_chart(fig_map_p, use_container_width=True)

with tab_dept:
    st.caption(
        "Algunos departamentos con nombres numéricos o alias no matchean el GeoJSON GADM "
        "(~90 % de cobertura). Los no matcheados no se colorean."
    )
    geo_dept = load_geojson_departments()
    agg_d = aggregate_by_department(filtered)
    # id compuesto provincia|departamento
    for feat in geo_dept["features"]:
        pk = norm_key(feat["properties"]["NAME_1"])
        dk = norm_key(feat["properties"]["NAME_2"])
        feat["id"] = f"{pk}|{dk}"
    agg_d = agg_d.copy()
    agg_d["_loc"] = agg_d["_prov_key"] + "|" + agg_d["_dept_key"]
    fig_map_d = px.choropleth(
        agg_d,
        geojson=geo_dept,
        locations="_loc",
        featureidkey="id",
        color="Residuo de Biomasa (Tn)",
        hover_name="Departamento",
        hover_data={
            "Provincia": True,
            "Residuo de Biomasa (Tn)": ":,.0f",
            "Produccion (Tn)": ":,.0f",
            "_loc": False,
            "_prov_key": False,
            "_dept_key": False,
        },
        color_continuous_scale="YlOrRd",
        title="Biomasa residual por departamento",
    )
    fig_map_d.update_geos(fitbounds="locations", visible=False)
    fig_map_d.update_layout(height=620, margin=dict(l=0, r=0, t=40, b=0))
    st.plotly_chart(fig_map_d, use_container_width=True)

# --- Tabla resumen provincial ---
st.subheader("Tabla por provincia")
st.dataframe(
    aggregate_by_province(filtered)
    .sort_values("Residuo de Biomasa (Tn)", ascending=False)
    .drop(columns=["_prov_key"], errors="ignore")
    .style.format(
        {
            "Residuo de Biomasa (Tn)": "{:,.0f}",
            "Produccion (Tn)": "{:,.0f}",
            "Superficie (Ha)": "{:,.0f}",
        }
    ),
    use_container_width=True,
    hide_index=True,
)

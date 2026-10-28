"""Página Resumen: KPIs, rankings y mapas de biomasa, energía o dinero."""

from __future__ import annotations

import streamlit as st

from dashboard.charts import choropleth, hbar
from dashboard.data_loader import (
    COL_BENEFICIO,
    COL_BIOMASA,
    COL_KWH,
    METRICAS,
    aggregate_by_department,
    aggregate_by_province,
    default_campaigns,
    filter_biomasa,
    format_ars,
    format_kwh,
    format_metric,
    format_tn,
    load_biomasa,
    load_geojson_departments,
    load_geojson_provinces,
)

st.title("Resumen")

df = load_biomasa()

with st.sidebar:
    st.header("Filtros")
    campanas = sorted(df["Campaña"].dropna().unique().tolist())
    # Últimas 5 campañas completas: la campaña en curso tiene datos parciales.
    sel_campanas = st.multiselect("Campaña", campanas, default=default_campaigns(df, 5))
    cultivos = sorted(df["Cultivo"].dropna().unique().tolist())
    sel_cultivos = st.multiselect("Cultivo", cultivos, default=[])
    st.caption("Vacío = todos los cultivos.")

metrica = st.segmented_control(
    "Ver", list(METRICAS), default="Biomasa residual", key="metrica_resumen"
) or "Biomasa residual"
cfg = METRICAS[metrica]

filtered = filter_biomasa(df, cultivos=sel_cultivos or None, campanas=sel_campanas or None)
if filtered.empty:
    st.warning("No hay datos con los filtros seleccionados.")
    st.stop()

# Los totales son promedio anual: sumar campañas no es una magnitud física.
n_camp = max(filtered["Campaña"].nunique(), 1)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Biomasa residual (prom. anual)", format_tn(filtered[COL_BIOMASA].sum() / n_camp))
c2.metric("Energía generable (prom. anual)", format_kwh(filtered[COL_KWH].sum() / n_camp))
c3.metric("Beneficio bruto (prom. anual)", format_ars(filtered[COL_BENEFICIO].sum() / n_camp))
c4.metric(
    "Deptos. con datos", f"{filtered[['Provincia', 'Departamento']].drop_duplicates().shape[0]:,}"
)
st.caption(
    f"Promedio de {n_camp} campaña(s). Energía con gasificadores PP30 sobre el residuo "
    "recuperable; dinero a tarifas vigentes (beneficio bruto). Las provincias sin tarifa "
    "(ver Auditoría) no suman dinero."
)

col = cfg["col"]
div = cfg["divisor"]
label = f"{metrica} ({cfg['unidad']})"
agg_p = aggregate_by_province(filtered, n_camp)
agg_p["_valor"] = agg_p[col] / div

# --- Rankings ---
st.subheader("Rankings")
col_a, col_b = st.columns(2)
with col_a:
    by_cult = filtered.groupby("Cultivo", as_index=False)[col].sum()
    by_cult["_valor"] = by_cult[col] / n_camp / div
    st.plotly_chart(
        hbar(by_cult.nlargest(12, "_valor"), "_valor", "Cultivo",
             f"Top cultivos — {cfg['titulo'].lower()}", label),
        use_container_width=True,
    )
with col_b:
    st.plotly_chart(
        hbar(agg_p.nlargest(12, "_valor"), "_valor", "Provincia",
             f"Top provincias — {cfg['titulo'].lower()}", label),
        use_container_width=True,
    )

# --- Mapas ---
st.subheader("Mapas")
tab_prov, tab_dept = st.tabs(["Por provincia", "Por departamento"])
with tab_prov:
    st.plotly_chart(
        choropleth(agg_p, load_geojson_provinces(), "provincia", "_prov_key", "_valor",
                   label, "Provincia", f"{cfg['titulo']} por provincia"),
        use_container_width=True,
    )
with tab_dept:
    agg_d = aggregate_by_department(filtered, n_camp)
    agg_d["_valor"] = agg_d[col] / div
    agg_d["_nombre"] = agg_d["Departamento"] + " (" + agg_d["Provincia"] + ")"
    st.plotly_chart(
        choropleth(agg_d, load_geojson_departments(), "departamento", "_geo_dept", "_valor",
                   label, "_nombre", f"{cfg['titulo']} por departamento"),
        use_container_width=True,
    )
    st.caption(
        "Departamentos en gris: sin datos con los filtros elegidos. Algunos departamentos "
        "creados después de los límites de GADM 4.1 no tienen polígono (ver Auditoría)."
    )

# --- Tabla resumen provincial ---
st.subheader("Tabla por provincia (promedio anual)")
tabla = agg_p[["Provincia", COL_BIOMASA, COL_KWH, COL_BENEFICIO]].sort_values(col, ascending=False)
tabla = tabla.rename(columns={
    COL_BIOMASA: "Biomasa residual (t MS)",
    COL_KWH: "Energía (GWh)",
    COL_BENEFICIO: "Beneficio bruto (M ARS)",
})
tabla["Energía (GWh)"] /= 1e6
tabla["Beneficio bruto (M ARS)"] /= 1e6
st.dataframe(
    tabla.style.format(
        {"Biomasa residual (t MS)": "{:,.0f}", "Energía (GWh)": "{:,.1f}",
         "Beneficio bruto (M ARS)": "{:,.0f}"},
        na_rep="—",
    ),
    use_container_width=True, hide_index=True,
)
st.caption(f"Total de la vista: {format_metric(metrica, agg_p[col].sum())} por año.")

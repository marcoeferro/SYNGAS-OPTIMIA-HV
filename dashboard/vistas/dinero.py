"""Página Dinero: beneficio bruto y tarifas eléctricas por distribuidora."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from dashboard.charts import choropleth, stacked_hbar
from dashboard.data_loader import (
    COL_AHORRO,
    COL_BENEFICIO,
    COL_CREDITO,
    COL_KWH,
    SERIE_1,
    SERIE_2,
    aggregate_by_department,
    aggregate_by_province,
    filter_biomasa,
    format_ars,
    load_geojson_departments,
    load_geojson_provinces,
    load_potencial,
    load_tarifas,
    load_tarifas_historial,
    tarifas_table,
)

st.title("Dinero")

df = load_potencial()
if df is None or df.empty:
    st.error("No se encontró el potencial anual. Ejecutá el pipeline ETL.")
    st.stop()

st.caption(
    "Beneficio **bruto** anual a tarifas vigentes (pesos del último cuadro tarifario): "
    "autoconsumo × tarifa de compra + inyección × tarifa de inyección (Ley 27.424). "
    "No descuenta inversión, operación ni recolección y flete del rastrojo."
)

with st.sidebar:
    st.header("Filtros")
    sel_prov = st.multiselect("Provincia", sorted(df["Provincia"].unique()), default=[])
    sel_cult = st.multiselect("Cultivo", sorted(df["Cultivo"].unique()), default=[])

f = filter_biomasa(df, provincias=sel_prov or None, cultivos=sel_cult or None)
if f.empty:
    st.warning("Sin datos para los filtros elegidos.")
    st.stop()

kwh = f[COL_KWH].sum()
con_tarifa = f.loc[f["tarifa_compra_kwh"].notna(), COL_KWH].sum()
iny_est = f.loc[f["tarifa_inyeccion_estimada"].fillna(False).astype(bool), COL_KWH].sum()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Beneficio bruto (por año)", format_ars(f[COL_BENEFICIO].sum()))
c2.metric("Ahorro por autoconsumo (por año)", format_ars(f[COL_AHORRO].sum()))
c3.metric("Ingreso por inyección (por año)", format_ars(f[COL_CREDITO].sum()))
c4.metric("Energía con tarifa", f"{con_tarifa / kwh:.0%}" if kwh else "—")
if kwh and iny_est:
    st.caption(
        f"El {iny_est / kwh:.0%} de la energía usa una tarifa de inyección **estimada** "
        "(compra × ratio observado en las distribuidoras que publican ambos precios)."
    )

# --- Por provincia ---
agg_p = aggregate_by_province(f)
agg_p["ahorro_m"] = agg_p[COL_AHORRO] / 1e6
agg_p["credito_m"] = agg_p[COL_CREDITO] / 1e6
agg_p["beneficio_m"] = agg_p[COL_BENEFICIO] / 1e6
con_dinero = agg_p[agg_p["beneficio_m"] > 0]
st.plotly_chart(
    stacked_hbar(
        con_dinero.nlargest(20, "beneficio_m"), "Provincia",
        [("ahorro_m", "Ahorro por autoconsumo", SERIE_1),
         ("credito_m", "Ingreso por inyección", SERIE_2)],
        "Beneficio bruto por provincia", "millones de ARS/año",
    ),
    use_container_width=True,
)

# --- Mapas ---
st.subheader("Mapas de beneficio bruto")
tab_prov, tab_dept = st.tabs(["Por provincia", "Por departamento"])
with tab_prov:
    st.plotly_chart(
        choropleth(agg_p, load_geojson_provinces(), "provincia", "_prov_key", "beneficio_m",
                   "M ARS/año", "Provincia", "Beneficio bruto por provincia"),
        use_container_width=True,
    )
with tab_dept:
    agg_d = aggregate_by_department(f)
    agg_d["beneficio_m"] = agg_d[COL_BENEFICIO] / 1e6
    agg_d["_nombre"] = agg_d["Departamento"] + " (" + agg_d["Provincia"] + ")"
    st.plotly_chart(
        choropleth(agg_d, load_geojson_departments(), "departamento", "_geo_dept",
                   "beneficio_m", "M ARS/año", "_nombre", "Beneficio bruto por departamento"),
        use_container_width=True,
    )
st.caption("En gris: sin dato o sin tarifa disponible (p.ej. Córdoba, Chubut, Tucumán).")

# --- Tarifas ---
st.subheader("Tarifas por distribuidora")
cfg, path = load_tarifas()
if cfg is None:
    st.info("No hay JSON de tarifas en `data/reference`.")
else:
    tabla = tarifas_table(cfg).sort_values("Compra ($/kWh)", ascending=False, na_position="last")
    tabla = tabla.fillna({"Vigencia": "—", "Fuente": "—"})
    st.dataframe(
        tabla.style.format({"Compra ($/kWh)": "{:,.2f}", "Inyección ($/kWh)": "{:,.2f}"},
                           na_rep="—"),
        hide_index=True, use_container_width=True,
        column_config={"Documento": st.column_config.LinkColumn("Documento")},
    )
    st.caption(
        f"`{path.name}`. Tarifa de compra: categoría de medianas o grandes demandas en baja "
        "tensión, banda horaria \"Resto\", sin impuestos. Provincias con varias "
        "distribuidoras usan el promedio (Buenos Aires: EDEN, EDEA, EDES)."
    )

hist = load_tarifas_historial()
if hist is not None and not hist.empty:
    st.subheader("Historial de tarifas de compra")
    codes = sorted(hist["distribuidora"].unique())
    default = [c for c in ("EDEN", "EPE", "ENERSA") if c in codes]
    sel = st.multiselect("Distribuidoras", codes, default=default, max_selections=8)
    # Paleta categórica en orden fijo, asignada según el orden de selección
    # (máximo 8): agregar una distribuidora no repinta las ya elegidas.
    palette = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300",
               "#4a3aa7", "#e34948"]
    color = dict(zip(sel, palette, strict=False))
    fig = go.Figure()
    for code in sel:
        h = hist[hist["distribuidora"] == code].sort_values("vigencia")
        fig.add_trace(go.Scatter(
            x=h["vigencia"], y=h["tarifa_compra_kwh"], mode="lines+markers", name=code,
            line={"width": 2, "color": color[code]}, marker={"size": 8},
            hovertemplate=f"{code} %{{x}}: %{{y:,.2f}} $/kWh<extra></extra>",
        ))
    fig.update_layout(
        height=420, yaxis_title="$/kWh", xaxis_title="Vigencia",
        hovermode="x unified", legend={"orientation": "h", "y": -0.2},
        margin={"l": 10, "r": 10, "t": 20, "b": 40},
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Un cuadro pleno por mes (`data/reference/tarifas_historial.csv`). Los saltos "
        "responden a actualizaciones tarifarias; los meses sin punto no tienen cuadro publicado."
    )

"""Página Energía: energía generable con gasificadores PP30."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard.charts import choropleth, hbar, stacked_hbar
from dashboard.data_loader import (
    COL_EQUIPOS,
    COL_KWH,
    COL_KWH_AUTO,
    COL_KWH_INY,
    COL_RECUPERABLE,
    SERIE_1,
    SERIE_2,
    aggregate_by_department,
    aggregate_by_province,
    filter_biomasa,
    format_kwh,
    format_tn,
    load_geojson_departments,
    load_geojson_provinces,
    load_potencial,
    load_tarifas,
    stop_missing_potencial,
)

st.title("Energía")

df = load_potencial()
if df is None or df.empty:
    stop_missing_potencial()

periodo = df["periodo_referencia"].dropna().iloc[0] if "periodo_referencia" in df else "—"
st.caption(
    f"Potencial **anual** promedio del período de referencia ({periodo}): campañas "
    "completas, la campaña en curso se excluye."
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
c1, c2, c3, c4 = st.columns(4)
c1.metric("Energía generable (por año)", format_kwh(kwh))
c2.metric("Equipos PP30 equivalentes", f"{f[COL_EQUIPOS].sum():,.0f}")
c3.metric("Residuo recuperable (MS por año)", format_tn(f[COL_RECUPERABLE].sum()))
auto, iny = f[COL_KWH_AUTO].sum() / kwh, f[COL_KWH_INY].sum() / kwh
c4.metric("Autoconsumo / inyección", f"{auto:.0%} / {iny:.0%}")

# --- Por provincia y cultivo ---
agg_p = aggregate_by_province(f)
agg_p["auto_gwh"] = agg_p[COL_KWH_AUTO] / 1e6
agg_p["iny_gwh"] = agg_p[COL_KWH_INY] / 1e6
col_a, col_b = st.columns(2)
with col_a:
    st.plotly_chart(
        stacked_hbar(
            agg_p.nlargest(15, COL_KWH), "Provincia",
            [("auto_gwh", "Autoconsumo", SERIE_1), ("iny_gwh", "Inyección a la red", SERIE_2)],
            "Energía por provincia", "GWh/año", ",.1f",
        ),
        use_container_width=True,
    )
with col_b:
    by_cult = f.groupby("Cultivo", as_index=False)[COL_KWH].sum()
    by_cult["gwh"] = by_cult[COL_KWH] / 1e6
    st.plotly_chart(
        hbar(by_cult.nlargest(15, "gwh"), "gwh", "Cultivo", "Energía por cultivo",
             "GWh/año", value_format=",.1f"),
        use_container_width=True,
    )

# --- Mapas ---
st.subheader("Mapas de energía generable")
tab_prov, tab_dept = st.tabs(["Por provincia", "Por departamento"])
with tab_prov:
    agg_p["gwh"] = agg_p[COL_KWH] / 1e6
    st.plotly_chart(
        choropleth(agg_p, load_geojson_provinces(), "provincia", "_prov_key", "gwh",
                   "GWh/año", "Provincia", "Energía generable por provincia", ",.1f"),
        use_container_width=True,
    )
with tab_dept:
    agg_d = aggregate_by_department(f)
    agg_d["gwh"] = agg_d[COL_KWH] / 1e6
    agg_d["_nombre"] = agg_d["Departamento"] + " (" + agg_d["Provincia"] + ")"
    st.plotly_chart(
        choropleth(agg_d, load_geojson_departments(), "departamento", "_geo_dept", "gwh",
                   "GWh/año", "_nombre", "Energía generable por departamento", ",.2f"),
        use_container_width=True,
    )
    st.caption(
        "Por departamento se ve dónde se concentra el rastrojo: es la escala a la que se "
        "decide la logística de recolección de un gasificador."
    )

# --- Parámetros ---
cfg, _ = load_tarifas()
with st.expander("Parámetros y método de cálculo"):
    if cfg is not None:
        p = cfg.get("parametros_pp30", {})
        params = pd.DataFrame([
            ("Consumo específico", p.get("consumo_especifico_seco_kg_kwh"),
             "kg de materia seca por kWh (ficha de All Power Labs)"),
            ("Humedad operativa", p.get("humedad_pct_default"), "%"),
            ("Potencia de referencia", p.get("potencia_nominal_kw"),
             "kW (PP30 a 50 Hz, conectado a red)"),
            ("Disponibilidad", p.get("disponibilidad"), "fracción del año"),
            ("Fracción de autoconsumo", p.get("factor_autoconsumo_default"), "resto se inyecta"),
            ("Fracción recuperable", p.get("fraccion_recuperable_default"), "del residuo"),
        ], columns=["Parámetro", "Valor", "Unidad"])
        st.dataframe(params, hide_index=True, use_container_width=True)
    st.markdown(
        """
- **Residuo recuperable** = residuo (t de materia seca) × fracción recuperable.
- **Energía** = residuo recuperable (kg de materia seca) ÷ consumo específico
  (1,0 kg MS/kWh según la ficha de All Power Labs).
- **Masa alimentada** = residuo recuperable ÷ (1 − humedad): lo que efectivamente
  entra a la tolva, con su humedad.
- **Equipos PP30 equivalentes** = energía ÷ (22 kW × 8760 h × disponibilidad).

Los valores de esta tabla son los del ETL; los supuestos de la barra lateral
(⚙️) permiten simular otros. Detalle en `docs/02_metodologia/metodologia.md`.
"""
    )

# --- Tabla ---
st.subheader("Tabla por provincia")
t = agg_p[["Provincia", COL_RECUPERABLE, COL_KWH, COL_EQUIPOS]]
t = t.sort_values(COL_KWH, ascending=False)
t[COL_KWH] /= 1e6
st.dataframe(
    t.rename(columns={COL_RECUPERABLE: "Residuo recuperable (t MS/año)",
                      COL_KWH: "Energía (GWh/año)", COL_EQUIPOS: "Equipos PP30"})
    .style.format({"Residuo recuperable (t MS/año)": "{:,.0f}", "Energía (GWh/año)": "{:,.1f}",
                   "Equipos PP30": "{:,.0f}"}),
    hide_index=True, use_container_width=True,
)

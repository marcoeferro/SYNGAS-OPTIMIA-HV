"""Generación real de la planta solar (Growatt) y radiación observada."""

from __future__ import annotations

from datetime import timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from optimia_hv.dashboard.data_loader import (
    COLOR_REAL,
    load_solar,
    stop_sin_datos_solares,
)

st.title("Generación solar real")
st.markdown(
    "Energía diaria de la planta de **2,25 kWp** (5 paneles de 450 W, inversor Growatt) "
    "en Villa Mercedes, San Luis, y la radiación del día según NASA POWER y Open-Meteo. "
    "Los días en que el inversor no reportó se completan con el promedio de los días "
    "vecinos (ver la metodología solar)."
)

diaria = load_solar("growatt_produccion")
if diaria is None or diaria.empty:
    stop_sin_datos_solares("growatt_produccion")

diaria = diaria.assign(fecha=pd.to_datetime(diaria["fecha"])).sort_values("fecha")
fin = diaria["fecha"].max().date()
inicio_defecto = max(diaria["fecha"].min().date(), fin - timedelta(days=90))
rango = st.date_input(
    "Período", value=(inicio_defecto, fin),
    min_value=diaria["fecha"].min().date(), max_value=fin,
)
# Mientras se elige el rango, Streamlit devuelve una sola fecha.
desde, hasta = rango if isinstance(rango, tuple) and len(rango) == 2 else (inicio_defecto, fin)
sel = diaria[(diaria["fecha"].dt.date >= desde) & (diaria["fecha"].dt.date <= hasta)]

c1, c2, c3 = st.columns(3)
c1.metric("Energía del período", f"{sel['energia'].sum():,.1f} kWh")
c2.metric("Promedio diario", f"{sel['energia'].mean():,.2f} kWh/día")
c3.metric("Días sin dato (0 kWh)", int((sel["energia"] == 0).sum()))

fig = go.Figure()
fig.add_bar(x=sel["fecha"], y=sel["energia"], name="Energía real (Growatt)",
            marker_color=COLOR_REAL)
for tabla, nombre, color in (
    ("clima_historico_nasa", "Radiación NASA POWER", "#6da7ec"),
    ("clima_historico_openmeteo", "Radiación Open-Meteo", "#184f95"),
):
    clima = load_solar(tabla)
    if clima is None or clima.empty:
        continue
    clima = clima.assign(fecha=pd.to_datetime(clima["fecha"]))
    clima = clima[clima["fecha"].between(pd.Timestamp(desde), pd.Timestamp(hasta))]
    fig.add_scatter(x=clima["fecha"], y=clima["radiacion_solar"], name=nombre,
                    yaxis="y2", mode="lines", line={"color": color, "width": 1.5})
fig.update_layout(
    yaxis={"title": "Energía (kWh/día)"},
    yaxis2={"title": "Radiación (kWh/m²/día)", "overlaying": "y", "side": "right"},
    legend={"orientation": "h", "y": -0.2}, margin={"t": 20}, height=450,
)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Potencia intradía")
intradia = load_solar("growatt_produccion_intradia")
if intradia is None or intradia.empty:
    st.info("Todavía no hay datos intradía (se cargan todos los días con los de ayer).")
else:
    intradia = intradia.assign(fecha_hora=pd.to_datetime(intradia["fecha_hora"]))
    dias = sorted(intradia["fecha_hora"].dt.date.unique(), reverse=True)
    dia = st.selectbox("Día", dias, format_func=lambda d: d.strftime("%d/%m/%Y"))
    del_dia = intradia[intradia["fecha_hora"].dt.date == dia]
    fig = go.Figure(go.Scatter(
        x=del_dia["fecha_hora"], y=del_dia["potencia_w"], mode="lines+markers",
        marker={"size": 3}, line={"color": COLOR_REAL}, name="Potencia real",
    ))
    fig.update_layout(yaxis_title="Potencia (W)", margin={"t": 20}, height=380)
    st.plotly_chart(fig, use_container_width=True)

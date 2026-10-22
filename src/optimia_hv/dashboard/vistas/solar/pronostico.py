"""Energía pronosticada para los próximos días (modelo de 15 min)."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from optimia_hv.dashboard.data_loader import (
    COLOR_MODELO,
    load_solar,
    stop_sin_datos_solares,
)

st.title("Pronóstico de generación solar")
st.markdown(
    "Energía que generaría la planta cada 15 minutos según el **pronóstico de Open-Meteo** "
    "y el modelo físico (irradiancia sobre el panel inclinado a 35°, temperatura de "
    "celda, humedad, presión y nubosidad). Se recalcula todos los días con el "
    "pronóstico más reciente."
)

energia = load_solar("energia_pronosticada")
if energia is None or energia.empty:
    stop_sin_datos_solares("energia_pronosticada")

energia = energia.assign(fecha_hora=pd.to_datetime(energia["fecha_hora"]))
ahora = pd.Timestamp.now().floor("D")
futuro = energia[energia["fecha_hora"] >= ahora].sort_values("fecha_hora")
if futuro.empty:
    st.warning(
        "El último pronóstico guardado ya pasó: el pipeline solar no corrió en los "
        "últimos días. Se muestra el último disponible."
    )
    futuro = energia[energia["fecha_hora"].dt.date >= energia["fecha_hora"].max().date()
                     - pd.Timedelta(days=4)]

por_dia = (
    futuro.groupby(futuro["fecha_hora"].dt.date)["energia_estimada_kwh"].sum().rename("kWh")
)
cols = st.columns(min(len(por_dia), 5) or 1)
for col, (dia, kwh) in zip(cols, por_dia.head(5).items(), strict=False):
    col.metric(dia.strftime("%a %d/%m"), f"{kwh:,.2f} kWh")

fig = go.Figure(go.Scatter(
    x=futuro["fecha_hora"], y=futuro["energia_estimada_kwh"], mode="lines",
    line={"color": COLOR_MODELO}, fill="tozeroy", name="Energía pronosticada",
))
fig.update_layout(yaxis_title="Energía en 15 min (kWh)", margin={"t": 20}, height=420)
st.plotly_chart(fig, use_container_width=True)

pron = load_solar("clima_pronosticado")
if pron is not None and not pron.empty:
    st.subheader("Pronóstico diario del clima")
    ultima = pron["fecha_consulta"].max()
    tabla = pron[pron["fecha_consulta"] == ultima].rename(columns={
        "fecha_pronosticada": "Fecha", "temp_predicha": "Temp. máx. (°C)",
        "humedad_relativa_predicha": "Humedad máx. (%)",
        "radiacion_predicha": "Radiación (kWh/m²)",
    })
    st.caption(f"Consulta del {pd.Timestamp(ultima):%d/%m/%Y}.")
    st.dataframe(
        tabla[["Fecha", "Temp. máx. (°C)", "Humedad máx. (%)", "Radiación (kWh/m²)"]],
        hide_index=True, use_container_width=True,
    )

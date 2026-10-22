"""Validación del modelo solar contra la generación real."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from optimia_hv.dashboard.data_loader import (
    COLOR_MODELO,
    COLOR_MODELO_VIEJO,
    COLOR_REAL,
    load_solar,
)
from optimia_hv.solar.validacion import comparativas, metricas

st.title("Validación del modelo solar")
st.markdown(
    "Compara la generación real (Growatt) con lo que estima cada modelo usando el "
    "**clima observado**: el modelo de 15 minutos (actual) y el modelo viejo diario "
    "(línea de base, PR fijo de 0,88). Métricas: MAE y RMSE (error típico), sesgo "
    "(positivo = el modelo sobreestima) y error en la energía total del período."
)


def _tabla_metricas(res: metricas.ResumenMetricas, unidad: str) -> None:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("MAE", f"{res.mae:,.2f} {unidad}")
    c2.metric("RMSE", f"{res.rmse:,.2f} {unidad}")
    c3.metric("Sesgo", f"{res.sesgo:+,.2f} {unidad}")
    c4.metric("Error en energía total", f"{res.error_relativo_total:+.1%}")


st.subheader("Modelo de 15 minutos")
estimada = load_solar("energia_estimada_15min")
real_intradia = load_solar("growatt_produccion_intradia")
if estimada is None or estimada.empty or real_intradia is None or real_intradia.empty:
    st.info(
        "Faltan datos para comparar. Cargar un período con "
        "`python -m optimia_hv.solar.pipelines.run_solar --validar AAAA-MM-DD AAAA-MM-DD`."
    )
else:
    estimada = estimada.assign(fecha_hora=pd.to_datetime(estimada["fecha_hora"]))
    dias = sorted(estimada["fecha_hora"].dt.date.unique())
    desde, hasta = st.select_slider(
        "Días", options=dias, value=(dias[max(0, len(dias) - 5)], dias[-1]),
        format_func=lambda d: d.strftime("%d/%m/%Y"),
    ) if len(dias) > 1 else (dias[0], dias[0])
    comp = comparativas.intradia_real_vs_estimada(estimada, real_intradia, desde, hasta)
    _tabla_metricas(metricas.resumen(comp["potencia_real_w"], comp["potencia_estimada_w"]), "W")
    fig = go.Figure()
    fig.add_scatter(x=comp["fecha_hora"], y=comp["potencia_real_w"], name="Potencia real",
                    mode="lines+markers", marker={"size": 3}, line={"color": COLOR_REAL})
    fig.add_scatter(x=comp["fecha_hora"], y=comp["potencia_estimada_w"],
                    name="Potencia estimada (modelo)", mode="lines",
                    line={"color": COLOR_MODELO, "dash": "dash"})
    fig.update_layout(yaxis_title="Potencia (W)", margin={"t": 20}, height=420,
                      legend={"orientation": "h", "y": -0.2})
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "La energía estimada de cada intervalo se muestra como potencia media "
        "(kWh × 1000 × 4). Los intervalos sin dato de Growatt figuran en 0 W."
    )

st.subheader("Modelo viejo (diario)")
clima = load_solar("clima_historico_openmeteo")
real_diaria = load_solar("growatt_produccion")
if clima is None or clima.empty or real_diaria is None or real_diaria.empty:
    st.info("Faltan el clima diario de Open-Meteo o la generación diaria de Growatt.")
else:
    comp = comparativas.diaria_real_vs_modelo_viejo(clima, real_diaria)
    comp = comp[comp["fecha"] <= pd.to_datetime(real_diaria["fecha"]).max().date()]
    con_dato = comp[comp["energia_real_kwh"] > 0]
    _tabla_metricas(
        metricas.resumen(con_dato["energia_real_kwh"], con_dato["energia_estimada_vieja"]),
        "kWh",
    )
    fig = go.Figure()
    fig.add_scatter(x=comp["fecha"], y=comp["energia_real_kwh"], name="Energía real",
                    mode="lines", line={"color": COLOR_REAL})
    fig.add_scatter(x=comp["fecha"], y=comp["energia_estimada_vieja"],
                    name="Energía estimada (modelo viejo)", mode="lines",
                    line={"color": COLOR_MODELO_VIEJO, "dash": "dash"})
    fig.update_layout(yaxis_title="Energía diaria (kWh)", margin={"t": 20}, height=420,
                      legend={"orientation": "h", "y": -0.2})
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Las métricas excluyen los días sin dato de Growatt (0 kWh).")

"""Gráficos compartidos entre páginas (mapas coropléticos y barras)."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from optimia_hv.dashboard.data_loader import BORDE, NEUTRO, SEQ_SCALE, geo_names

MAP_HEIGHT = 620


def choropleth(
    data: pd.DataFrame,
    geo: dict,
    level: str,
    loc_col: str,
    value_col: str,
    value_label: str,
    hover_name_col: str,
    title: str,
    value_format: str = ",.0f",
) -> go.Figure:
    """
    Mapa coroplético con todos los contornos visibles.

    Una primera capa dibuja **todos** los polígonos en gris neutro con su
    borde (provincias o departamentos sin dato, p.ej. CABA o los que no
    tienen cultivos relevados). Encima, la capa de datos colorea con una
    escala secuencial de un solo tono. Antes sólo se dibujaban los
    polígonos con dato, y las jurisdicciones sin registros desaparecían.
    """
    names = geo_names(geo, level)
    fig = go.Figure()
    fig.add_trace(go.Choropleth(
        geojson=geo, featureidkey="id",
        locations=names["id"], z=[0] * len(names),
        colorscale=[[0, NEUTRO], [1, NEUTRO]], showscale=False,
        marker_line_color=BORDE, marker_line_width=0.6,
        text=names["nombre"],
        hovertemplate="%{text}<br>Sin dato<extra></extra>",
        name="Sin dato",
    ))
    shown = data.dropna(subset=[value_col])
    shown = shown[shown[value_col] > 0]
    fig.add_trace(go.Choropleth(
        geojson=geo, featureidkey="id",
        locations=shown[loc_col], z=shown[value_col],
        colorscale=SEQ_SCALE, zmin=0,
        marker_line_color=BORDE, marker_line_width=0.6,
        text=shown[hover_name_col],
        hovertemplate=f"%{{text}}<br>{value_label}: %{{z:{value_format}}}<extra></extra>",
        colorbar={"title": {"text": value_label, "side": "right"}, "thickness": 12},
        name=value_label,
    ))
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(
        title=title, height=MAP_HEIGHT, margin={"l": 0, "r": 0, "t": 40, "b": 0},
        geo={"bgcolor": "rgba(0,0,0,0)"},
    )
    return fig


def hbar(
    data: pd.DataFrame, x: str, y: str, title: str, x_title: str,
    color: str = "#2a78d6", value_format: str = ",.0f",
) -> go.Figure:
    """Barras horizontales de una serie, ordenadas de mayor a menor."""
    d = data.sort_values(x)
    fig = go.Figure(go.Bar(
        x=d[x], y=d[y], orientation="h", marker_color=color,
        hovertemplate=f"%{{y}}: %{{x:{value_format}}}<extra></extra>",
    ))
    fig.update_layout(
        title=title, height=max(320, 28 * len(d) + 80), xaxis_title=x_title,
        margin={"l": 10, "r": 10, "t": 40, "b": 40}, bargap=0.25,
    )
    return fig


def stacked_hbar(
    data: pd.DataFrame, y: str, series: list[tuple[str, str, str]],
    title: str, x_title: str, value_format: str = ",.0f",
) -> go.Figure:
    """Barras horizontales apiladas; ``series`` = [(columna, nombre, color)]."""
    d = data.assign(_total=data[[c for c, _, _ in series]].sum(axis=1)).sort_values("_total")
    fig = go.Figure()
    for col, name, color in series:
        fig.add_trace(go.Bar(
            x=d[col], y=d[y], orientation="h", name=name, marker_color=color,
            marker_line_color="rgba(0,0,0,0)",
            hovertemplate=f"%{{y}} · {name}: %{{x:{value_format}}}<extra></extra>",
        ))
    fig.update_layout(
        barmode="stack", title=title, height=max(320, 28 * len(d) + 100),
        xaxis_title=x_title, legend={"orientation": "h", "y": -0.15, "traceorder": "normal"},
        margin={"l": 10, "r": 10, "t": 40, "b": 40}, bargap=0.25,
    )
    return fig

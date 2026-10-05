"""
Página Auditoría de datos (última del menú).

Muestra dónde los resultados de las otras páginas son menos firmes:
registros descartados y discrepancias entre fuentes, estado de las
tarifas, cobertura de los mapas y campañas incompletas.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.data_loader import (
    COL_BIOMASA,
    COL_KWH,
    ESTADOS_TARIFA,
    dept_geo_coverage,
    load_biomasa,
    load_descartados,
    load_discrepancias,
    load_potencial,
    load_tarifas,
    tarifas_table,
)
from etl.transformers.reference_period import detect_incomplete_campaigns

st.title("Auditoría de datos")
st.caption(
    "Calidad y trazabilidad de los datos de las otras páginas. Solo lectura de "
    "`data/audit/`, `data/processed/` y `data/reference/`."
)

tab_rec, tab_disc, tab_tar, tab_geo, tab_camp = st.tabs([
    "Descartados en reconciliación",
    "Discrepancias CBA vs MAGyP",
    "Tarifas",
    "Cobertura de mapas",
    "Campañas",
])

# --- Reconciliación ---
with tab_rec:
    desc = load_descartados()
    st.markdown(
        "Cuando MAGyP y la Bolsa de Cereales de Córdoba informan el mismo departamento, "
        "cultivo y campaña, se conserva el registro de mayor producción y el otro se "
        "descarta aquí."
    )
    if desc is None or desc.empty:
        st.info("No hay archivo de descartados o está vacío.")
    else:
        st.metric("Registros descartados", f"{len(desc):,}")
        by_p = desc.groupby("Provincia", as_index=False).size().rename(columns={"size": "n"})
        fig = px.bar(by_p.sort_values("n", ascending=False), x="Provincia", y="n",
                     title="Descartados por provincia", color_discrete_sequence=["#2a78d6"])
        fig.update_layout(xaxis_tickangle=-40, height=360, yaxis_title="registros")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(desc, use_container_width=True, hide_index=True)
        st.download_button(
            "Descargar descartados CSV", desc.to_csv(index=False).encode("utf-8"),
            file_name="descartados_reconciliacion.csv", mime="text/csv",
        )

# --- Discrepancias ---
with tab_disc:
    disc = load_discrepancias()
    if disc is None or disc.empty:
        st.info("No hay archivo de discrepancias o está vacío.")
    else:
        d = disc.copy()
        if isinstance(d.columns, pd.MultiIndex):
            d.columns = ["_".join(str(x) for x in c if str(x)).strip("_") for c in d.columns]
        d = d.reset_index(drop=True)
        c1, c2 = st.columns(2)
        c1.metric("Pares comparados", f"{len(d):,}")
        if "diff_rel_produccion" in d:
            grande = (d["diff_rel_produccion"].abs() > 0.5).mean()
            c2.metric("Con diferencia de producción > 50 %", f"{grande:.0%}")
            fig = px.histogram(
                d, x="diff_rel_produccion", nbins=60,
                title="Diferencia relativa de producción (CBA vs MAGyP)",
                color_discrete_sequence=["#2a78d6"],
            )
            fig.update_layout(height=340, xaxis_title="diferencia relativa",
                              yaxis_title="pares", bargap=0.05)
            st.plotly_chart(fig, use_container_width=True)
        st.dataframe(d, use_container_width=True, hide_index=True)
        st.download_button(
            "Descargar discrepancias CSV", d.to_csv(index=False).encode("utf-8"),
            file_name="discrepancias_cba_vs_magyp.csv", mime="text/csv",
        )

# --- Tarifas ---
with tab_tar:
    cfg, path = load_tarifas()
    pot = load_potencial()
    if cfg is None:
        st.info("No hay JSON de tarifas en `data/reference`.")
    else:
        tabla = tarifas_table(cfg)
        resumen = cfg.get("resumen_extraccion", {})
        c1, c2, c3 = st.columns(3)
        c1.metric("Distribuidoras con tarifa extraída",
                  f"{resumen.get('extraidas_en_esta_corrida', '—')} de "
                  f"{resumen.get('distribuidoras_totales', '—')}")
        c2.metric("Con valor anterior (fuente caída)", resumen.get("fallback_previous", "—"))
        c3.metric("Sin dato", resumen.get("sin_dato", "—"))
        st.dataframe(
            tabla[["Distribuidora", "Jurisdicción", "Estado", "Vigencia", "Fuente", "Documento"]]
            .fillna({"Vigencia": "—", "Fuente": "—"}),
            hide_index=True, use_container_width=True,
            column_config={"Documento": st.column_config.LinkColumn("Documento")},
        )
        st.caption(
            "Leyenda: " + " · ".join(dict.fromkeys(f"{i} {t}" for i, t in ESTADOS_TARIFA.values()))
            + f". Archivo: `{path.name}`. El motivo de cada distribuidora sin dato está en "
            "`REPORTE_CAMBIOS.md`."
        )
    if pot is not None and not pot.empty:
        tot = pot[COL_KWH].sum()
        sin = (
            pot[pot["tarifa_compra_kwh"].isna()].groupby("Provincia", as_index=False)[COL_KWH]
            .sum().assign(pct=lambda x: x[COL_KWH] / tot)
            .sort_values("pct", ascending=False)
        )
        st.markdown("**Energía sin tarifa** (no suma dinero en las otras páginas)")
        st.dataframe(
            sin.rename(columns={COL_KWH: "kWh/año", "pct": "% de la energía"})
            .style.format({"kWh/año": "{:,.0f}", "% de la energía": "{:.1%}"}),
            hide_index=True, use_container_width=True,
        )
        est = pot["tarifa_inyeccion_estimada"].fillna(False).astype(bool)
        proxy = pot["tarifa_es_proxy"].fillna(False).astype(bool)
        st.markdown(
            f"**Tarifa de inyección estimada** en el {pot.loc[est, COL_KWH].sum() / tot:.0%} "
            "de la energía: la mayoría de las distribuidoras no publica precio de inyección y "
            "se usa compra × ratio observado. **Tarifa promediada** (provincia con varias "
            f"distribuidoras): {pot.loc[proxy, COL_KWH].sum() / tot:.0%}."
        )

# --- Cobertura geográfica ---
with tab_geo:
    bio = load_biomasa()
    faltan = dept_geo_coverage(bio)
    total = bio[COL_BIOMASA].sum()
    c1, c2 = st.columns(2)
    c1.metric("Departamentos sin polígono en el mapa", f"{len(faltan):,}")
    c2.metric("Biomasa que no se ve en el mapa departamental",
              f"{faltan[COL_BIOMASA].sum() / total:.2%}")
    st.markdown(
        "Incluye los registros con departamento **\"sin definir\"** en la fuente y "
        "departamentos sin polígono en GADM 4.1 (Lezama y Punta Indio en Buenos Aires, "
        "2 de Abril en Chaco, San Salvador en Entre Ríos, 9 de Julio en San Juan). Esos "
        "valores sí cuentan en los totales y en los mapas por provincia."
    )
    st.dataframe(
        faltan.sort_values(COL_BIOMASA, ascending=False)
        .rename(columns={COL_BIOMASA: "Biomasa residual (t MS, todas las campañas)"})
        .style.format({"Biomasa residual (t MS, todas las campañas)": "{:,.0f}"}),
        hide_index=True, use_container_width=True,
    )

# --- Campañas ---
with tab_camp:
    bio = load_biomasa()
    incompletas = detect_incomplete_campaigns(bio)
    por_camp = bio.groupby("Campaña", as_index=False).agg(
        registros=("Cultivo", "size"), biomasa=(COL_BIOMASA, "sum")
    )
    fig = px.bar(por_camp, x="Campaña", y="registros", title="Registros por campaña",
                 color_discrete_sequence=["#2a78d6"])
    fig.update_layout(height=360, xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)
    if incompletas:
        st.warning(
            f"Campañas incompletas (en curso o con pocos registros): {', '.join(incompletas)}. "
            "Se excluyen del período de referencia y de los filtros por defecto."
        )
    pot = load_potencial()
    if pot is not None and "periodo_referencia" in pot:
        periodo = pot["periodo_referencia"].iloc[0]
        st.caption(f"Período de referencia del potencial anual: {periodo}.")

"""Página Auditoría: descartados y discrepancias entre fuentes (nice-to-have)."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.data_loader import load_descartados, load_discrepancias

st.set_page_config(page_title="Auditoría | Biomasa", page_icon="🧾", layout="wide")
st.title("Auditoría")
st.caption(
    "Registros descartados en reconciliación y discrepancias CBA vs MAGYP. "
    "Solo lectura de los Parquet de `data/audit/`."
)

desc = load_descartados()
disc = load_discrepancias()

tab1, tab2 = st.tabs(["Descartados", "Discrepancias CBA vs MAGYP"])

with tab1:
    if desc is None or desc.empty:
        st.info("No hay archivo de descartados o está vacío.")
    else:
        st.metric("Registros descartados", f"{len(desc):,}")
        if "Provincia" in desc.columns:
            by_p = (
                desc.groupby("Provincia", as_index=False)
                .size()
                .rename(columns={"size": "n"})
                .sort_values("n", ascending=False)
            )
            fig = px.bar(by_p, x="Provincia", y="n", title="Descartados por provincia")
            fig.update_layout(xaxis_tickangle=-40, height=360)
            st.plotly_chart(fig, use_container_width=True)
        st.dataframe(desc, use_container_width=True, hide_index=True)
        st.download_button(
            "Descargar descartados CSV",
            data=desc.to_csv(index=False).encode("utf-8"),
            file_name="descartados_reconciliacion.csv",
            mime="text/csv",
        )

with tab2:
    if disc is None or disc.empty:
        st.info("No hay archivo de discrepancias o está vacío.")
    else:
        st.metric("Filas de discrepancia", f"{len(disc):,}")
        st.dataframe(disc, use_container_width=True)
        # MultiIndex columns from pivot — flatten for CSV
        flat = disc.copy()
        if isinstance(flat.columns, pd.MultiIndex):
            flat.columns = [
                "_".join(str(x) for x in col if str(x) != "").strip("_")
                for col in flat.columns.values
            ]
        st.download_button(
            "Descargar discrepancias CSV",
            data=flat.reset_index().to_csv(index=False).encode("utf-8"),
            file_name="discrepancias_cba_vs_magyp.csv",
            mime="text/csv",
        )

"""
Punto de entrada del dashboard Streamlit.

Multipágina: Resumen (home), Exploración, Auditoría.
Solo lectura de Parquet generados por el pipeline ETL.
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Biomasa Residual | Argentina",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("Biomasa Residual Agrícola — Argentina")
st.markdown(
    """
Dashboard de **solo lectura** sobre los artefactos Parquet del pipeline ETL.

Usá el menú lateral para navegar:

| Página | Contenido |
|--------|-----------|
| **Resumen** | KPIs globales, rankings y mapas (provincia / departamento) |
| **Exploración** | Filtros cruzados, tablas y gráficos detallados |
| **Auditoría** | Registros descartados y discrepancias entre fuentes |

Los datos se leen directamente desde `data/audit/` (o `data/processed/` si existe).
Ejecutá el ETL antes de usar el dashboard si los Parquet no están generados.
"""
)

st.info("Seleccioná una página en la barra lateral izquierda.")

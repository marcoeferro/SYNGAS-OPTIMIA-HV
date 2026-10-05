"""
Punto de entrada del dashboard Streamlit.

``streamlit run dashboard/app.py`` (local o Docker). Define la navegación
explícita (el orden de las páginas no depende del nombre de los archivos)
y agrega la raíz del proyecto al ``sys.path``: sin eso las páginas no
podían importar ``dashboard`` ni ``etl`` fuera de Docker, donde el
``PYTHONPATH`` lo fija la imagen.

Las páginas están en ``vistas/`` y no en ``pages/``: con una carpeta
``pages/`` Streamlit usa el modo multipágina anterior, que ejecuta cada
página sin pasar por este archivo.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

st.set_page_config(
    page_title="Biomasa Residual | Argentina",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

from dashboard.data_loader import horas_desde_ultima_corrida  # noqa: E402

# Aviso si el ETL dejó de publicar datos (scheduler detenido, fuente caída,
# corrida fallida). El ETL corre todos los días: 48 h son dos corridas.
DATOS_VIEJOS_HORAS = float(os.environ.get("DATOS_VIEJOS_HORAS", "48"))
horas = horas_desde_ultima_corrida()
if horas is not None and horas > DATOS_VIEJOS_HORAS:
    st.warning(
        f"⚠️ Los datos tienen {horas / 24:.1f} días: el ETL no publicó resultados "
        f"en las últimas {DATOS_VIEJOS_HORAS:.0f} horas. Revisar `logs/pipeline.log` "
        "y que el scheduler esté corriendo (ver docs/05_uso/solucion_de_problemas.md)."
    )

PAGES = Path(__file__).resolve().parent / "vistas"
nav = st.navigation([
    st.Page(PAGES / "inicio.py", title="Inicio", icon="🌾", default=True),
    st.Page(PAGES / "resumen.py", title="Resumen", icon="📊"),
    st.Page(PAGES / "energia.py", title="Energía", icon="⚡"),
    st.Page(PAGES / "dinero.py", title="Dinero", icon="💰"),
    st.Page(PAGES / "exploracion.py", title="Exploración", icon="🔍"),
    st.Page(PAGES / "auditoria.py", title="Auditoría de datos", icon="🧾"),
])
nav.run()

"""
Punto de entrada del dashboard Streamlit.

``streamlit run src/optimia_hv/dashboard/app.py`` (local o Docker). Define la navegación
explícita (el orden de las páginas no depende del nombre de los archivos)
y agrega ``src/`` al ``sys.path``: sin eso las páginas no podían importar
``optimia_hv`` si el paquete no está instalado (``pip install -e .``).

Las páginas están en ``vistas/<dominio>/`` y no en ``pages/``: con una carpeta
``pages/`` Streamlit usa el modo multipágina anterior, que ejecuta cada
página sin pasar por este archivo.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2]
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import streamlit as st  # noqa: E402

st.set_page_config(
    page_title="Biomasa Residual | Argentina",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

from optimia_hv.dashboard.data_loader import (  # noqa: E402
    INYECCION_ALTO,
    INYECCION_CENTRAL,
    INYECCION_CONSERVADOR,
    SUPUESTOS_KEYS,
    horas_desde_ultima_corrida,
    load_tarifas,
    supuestos_base,
)
from optimia_hv.biomasa.transformers.energy_finance import injection_ratio  # noqa: E402

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

# --- Supuestos del cálculo (valen para todas las páginas) ---
base = supuestos_base()
cfg_tarifas, _ = load_tarifas()
ratio = injection_ratio(cfg_tarifas) if cfg_tarifas else None
ratio_txt = f"compra × {ratio:.3f}".replace(".", ",") if ratio else "estimación del ETL"
with st.sidebar.expander("⚙️ Supuestos del cálculo", expanded=False):
    st.slider(
        "Autoconsumo (%)", 0, 100, int(round(base.autoconsumo * 100)), 5,
        key="sup_autoconsumo_pct",
        help="Parte de la energía que consume el propio establecimiento (ahorra la "
             "tarifa de compra). El resto se inyecta a la red.",
    )
    st.radio(
        "Inyección donde no hay precio publicado",
        [INYECCION_CONSERVADOR, INYECCION_CENTRAL, INYECCION_ALTO],
        index=1, key=SUPUESTOS_KEYS["inyeccion"],
        format_func={
            INYECCION_CONSERVADOR: "Conservador: 0 (sólo ahorro)",
            INYECCION_CENTRAL: f"Central: {ratio_txt}",
            INYECCION_ALTO: "Alto: igual a la compra",
        }.get,
        help="Sólo cambia las distribuidoras que no publican su tarifa de inyección; "
             "las que la publican usan siempre el valor real. Ver POL-TARIFF-002.",
    )
    st.radio(
        "Consumo específico del PP30",
        [1.0, 1.1],
        index=0 if base.consumo_especifico <= 1.05 else 1,
        key=SUPUESTOS_KEYS["consumo_especifico"],
        format_func={
            1.0: "1,0 kg MS/kWh (ficha de All Power Labs)",
            1.1: "1,1 kg MS/kWh (conservador)",
        }.get,
        help="Kilos de biomasa seca por kWh eléctrico.",
    )
    st.slider(
        "Fracción del rastrojo que se retira (%)", 20, 70,
        int(round(base.fraccion_recuperable * 100)), 5,
        key="sup_fraccion_pct",
        help="El resto queda en el lote para proteger el suelo. Ver la metodología.",
    )
    st.session_state[SUPUESTOS_KEYS["autoconsumo"]] = st.session_state["sup_autoconsumo_pct"] / 100
    st.session_state[SUPUESTOS_KEYS["fraccion_recuperable"]] = (
        st.session_state["sup_fraccion_pct"] / 100
    )
    if st.button("Volver a los valores del ETL"):
        for k in ("sup_autoconsumo_pct", "sup_fraccion_pct", *SUPUESTOS_KEYS.values()):
            st.session_state.pop(k, None)
        st.rerun()
modificados = (
    st.session_state.get(SUPUESTOS_KEYS["autoconsumo"], base.autoconsumo) != base.autoconsumo
    or st.session_state.get(SUPUESTOS_KEYS["inyeccion"], INYECCION_CENTRAL) != INYECCION_CENTRAL
    or st.session_state.get(SUPUESTOS_KEYS["consumo_especifico"], base.consumo_especifico)
    != base.consumo_especifico
    or st.session_state.get(SUPUESTOS_KEYS["fraccion_recuperable"], base.fraccion_recuperable)
    != base.fraccion_recuperable
)
if modificados:
    st.sidebar.caption(
        "⚠️ Supuestos modificados: energía y dinero no son los valores de referencia del ETL."
    )

PAGES = Path(__file__).resolve().parent / "vistas" / "biomasa"
SOLAR = Path(__file__).resolve().parent / "vistas" / "solar"
# Una sección por dominio. Los ``url_path`` de solar llevan prefijo para no
# chocar con los de biomasa (p. ej. "energia").
nav = st.navigation({
    "Biomasa": [
        st.Page(PAGES / "inicio.py", title="Inicio", icon="🌾", default=True),
        st.Page(PAGES / "resumen.py", title="Resumen", icon="📊"),
        st.Page(PAGES / "energia.py", title="Energía", icon="⚡"),
        st.Page(PAGES / "dinero.py", title="Dinero", icon="💰"),
        st.Page(PAGES / "exploracion.py", title="Exploración", icon="🔍"),
        st.Page(PAGES / "auditoria.py", title="Auditoría de datos", icon="🧾"),
    ],
    "Solar": [
        st.Page(SOLAR / "generacion.py", title="Generación real", icon="☀️",
                url_path="solar_generacion"),
        st.Page(SOLAR / "pronostico.py", title="Pronóstico", icon="🌤️",
                url_path="solar_pronostico"),
        st.Page(SOLAR / "validacion.py", title="Validación del modelo", icon="📐",
                url_path="solar_validacion"),
    ],
})
nav.run()

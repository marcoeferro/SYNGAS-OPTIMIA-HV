"""Página de inicio: qué muestra el dashboard y de dónde salen los datos."""

from __future__ import annotations

import streamlit as st

from dashboard.data_loader import load_tarifas

st.title("Biomasa residual agrícola — Argentina")
st.markdown(
    """
Potencial de la **biomasa residual agrícola** (rastrojos) para generar
electricidad con gasificadores **All Power Labs PP30** (25 kW) y su valor
económico a las tarifas eléctricas vigentes de cada distribuidora.

| Página | Contenido |
|--------|-----------|
| **Resumen** | Indicadores y mapas por provincia y departamento; se puede ver biomasa, energía o dinero |
| **Energía** | Energía generable, equipos PP30 equivalentes, autoconsumo e inyección |
| **Dinero** | Beneficio bruto, tarifas por distribuidora e historial de tarifas |
| **Exploración** | Filtros cruzados, series por campaña y tabla descargable |
| **Auditoría de datos** | Calidad de los datos: descartes, discrepancias entre fuentes, tarifas y cobertura de los mapas |

**Cadena de cálculo.** Producción (MAGyP + Bolsa de Cereales de Córdoba,
reconciliadas) → residuo en materia seca (índice de cosecha y materia seca
por cultivo) → residuo recuperable (fracción que se puede retirar del
lote) → energía (consumo específico del PP30 a humedad operativa) →
dinero (autoconsumo × tarifa de compra + inyección × tarifa de inyección,
Ley 27.424).

Los montos son **beneficio bruto** a tarifas vigentes: no descuentan
inversión, operación ni el costo de recolectar y transportar el rastrojo.
"""
)

cfg, path = load_tarifas()
if cfg is not None:
    st.caption(
        f"Tarifas: `{path.name}` (generado {cfg.get('generado_en', '—')}). "
        "Datos leídos de `data/processed`, `data/audit` y `data/reference`; "
        "ejecutá el ETL para actualizarlos."
    )

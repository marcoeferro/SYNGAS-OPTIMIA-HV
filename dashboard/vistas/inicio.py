"""Página de inicio: qué muestra el dashboard y de dónde salen los datos."""

from __future__ import annotations

import streamlit as st

from dashboard.data_loader import (
    CANDIDATE_BIOMASA,
    PATH_DESCARTADOS,
    PATH_POTENCIAL,
    file_info,
    load_tarifas,
)

st.title("Biomasa residual agrícola — Argentina")
st.markdown(
    """
Potencial de la **biomasa residual agrícola** (rastrojos) para generar
electricidad con gasificadores **All Power Labs PP30** (22 kW a 50 Hz) y su valor
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
lote) → energía (1,0 kg de materia seca por kWh, ficha del PP30) →
dinero (autoconsumo × tarifa de compra + inyección × tarifa de inyección,
Ley 27.424).

Los montos son **beneficio bruto** a tarifas vigentes: no descuentan
inversión, operación ni el costo de recolectar, acondicionar (triturar o
pelletizar) y transportar el rastrojo. Es un **potencial técnico**: el PP30
está aprobado por el fabricante para chips de madera, cáscaras y marlo; el
rastrojo requeriría acondicionamiento y ensayos.

En **⚙️ Supuestos del cálculo** (barra lateral) se puede cambiar el
autoconsumo, el escenario de inyección, el consumo específico y la fracción
de rastrojo que se retira.
"""
)

cfg, path = load_tarifas()
if cfg is not None:
    st.caption(
        f"Tarifas: `{path.name}` (generado {cfg.get('generado_en', '—')}). "
        "Datos leídos de `data/processed`, `data/audit` y `data/reference`; "
        "ejecutá el ETL para actualizarlos."
    )

with st.expander("Archivos de datos"):
    st.markdown(
        "\n".join(
            f"- {file_info(p)}"
            for p in (CANDIDATE_BIOMASA[0], PATH_POTENCIAL, PATH_DESCARTADOS)
        )
        + "\n\nSi las fechas no cambian después de correr el ETL, el ETL no llegó a "
        "persistir (revisá su log) o corrió con una imagen de Docker vieja."
    )


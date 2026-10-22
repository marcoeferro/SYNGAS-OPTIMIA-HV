"""Modelo viejo: energía diaria con un PR fijo (línea de base).

Ex ``modeloViejo/calcularModeloViejo.py`` y ``modeloViejo/grafico5dias.py``,
que repetían la misma fórmula y sólo cambiaban el rango de fechas y el
gráfico (los gráficos están en ``solar/graficos.py`` y ``analisis/solar/``).

La radiación diaria en kWh/m² equivale a las horas solares pico del día,
por eso se multiplica directamente por la potencia pico::

    E = H · P_pico · η_inv · PR_base · (1 + γ (T − 25)) · (1 − 0,002 · HR/100)
"""

from __future__ import annotations

import pandas as pd

from optimia_hv.solar.configuracion import ParametrosModeloViejo


def estimar_energia_diaria(
    clima_diario: pd.DataFrame,
    params: ParametrosModeloViejo | None = None,
) -> pd.Series:
    """Energía diaria estimada (kWh) con el modelo viejo.

    Args:
        clima_diario: Columnas ``temperatura_media`` (°C), ``humedad_relativa``
            (%) y ``radiacion_solar`` (kWh/m²/día), p. ej.
            ``clima_historico_openmeteo``.
        params: Parámetros del modelo.

    Returns:
        Serie ``energia_estimada_vieja`` (kWh, nunca negativa).
    """
    p = params or ParametrosModeloViejo()
    f_termico = 1 + p.gamma * (clima_diario["temperatura_media"] - 25)
    f_humedad = 1 - 0.002 * (clima_diario["humedad_relativa"] / 100)
    pr = p.pr_base * f_termico * f_humedad
    energia = clima_diario["radiacion_solar"] * p.potencia_pico_kwp * p.eficiencia_inversor * pr
    return energia.clip(lower=0).rename("energia_estimada_vieja")

"""Gráficos reutilizables de la tesis solar (matplotlib).

Cada función recibe una tabla de ``validacion/comparativas.py`` y devuelve
la figura, sin mostrarla ni guardarla: los scripts de ``analisis/solar/``
deciden si la muestran (``plt.show()``) o la guardan en
``outputs/figures/solar/``. Mantienen el estilo de los gráficos originales
(verde = real, naranja/rojo = modelo).
"""

from __future__ import annotations

from typing import Final

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure

COLOR_REAL: Final[str] = "#2ca02c"
COLOR_MODELO: Final[str] = "#ff7f0e"
COLOR_MODELO_VIEJO: Final[str] = "#d62728"


def _cuadricula_fina(ax: plt.Axes) -> None:
    ax.grid(True, which="major", color="#cccccc", linestyle="-", alpha=0.8)
    ax.grid(True, which="minor", color="#eeeeee", linestyle=":", alpha=0.5)


def potencia_intradia(
    df: pd.DataFrame,
    titulo: str,
    intervalo_horas: int = 1,
    formato: str = "%H:%M",
) -> Figure:
    """Potencia real vs. estimada cada 15 min.

    Sirve para la campana de un día (``intervalo_horas=1``) y para la
    comparativa de varios días (``intervalo_horas=6``, ``formato="%d/%m %H:%M"``).

    Args:
        df: Salida de ``comparativas.intradia_real_vs_estimada``.
        titulo: Título del gráfico.
        intervalo_horas: Separación de las marcas del eje X.
        formato: Formato de las marcas del eje X.
    """
    varios_dias = intervalo_horas > 1
    fig, ax = plt.subplots(figsize=(20, 7) if varios_dias else (14, 6))
    x = pd.to_datetime(df["fecha_hora"])
    ax.plot(
        x, df["potencia_real_w"], label="Potencia Real (Growatt)", color=COLOR_REAL,
        linewidth=1.2 if varios_dias else 2.0, marker="o",
        markersize=1.5 if varios_dias else 3,
    )
    ax.plot(
        x, df["potencia_estimada_w"], label="Potencia Estimada (Modelo)", color=COLOR_MODELO,
        linewidth=1.2 if varios_dias else 2.0, linestyle="--",
    )
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=intervalo_horas))
    ax.xaxis.set_major_formatter(mdates.DateFormatter(formato))
    ax.xaxis.set_minor_locator(mdates.MinuteLocator(interval=15))
    ax.set_title(titulo, fontsize=14, fontweight="bold")
    ax.set_xlabel("Hora del Día (Intervalos de 15 min)", fontsize=12)
    ax.set_ylabel("Potencia (W)", fontsize=12)
    _cuadricula_fina(ax)
    ax.legend(loc="upper right", fontsize=11)
    if len(x):
        ax.set_xlim(x.min(), x.max())
    plt.setp(ax.get_xticklabels(), rotation=45)
    fig.tight_layout()
    return fig


def energia_pronosticada_vs_real(df: pd.DataFrame, titulo: str) -> Figure:
    """Energía de cada intervalo: pronosticada vs. real (un día).

    Args:
        df: Salida de ``comparativas.pronosticada_vs_real``.
        titulo: Título del gráfico.
    """
    fig, ax = plt.subplots(figsize=(12, 6))
    horas = pd.to_datetime(df["fecha_hora"]).dt.strftime("%H:%M")
    ax.plot(
        horas, df["energia_estimada_kwh"], label="Energía Pronosticada (kWh)",
        color="orange", linestyle="--", marker="o", markersize=3,
    )
    ax.plot(
        horas, df["energia_real_kwh"], label="Energía Real Growatt (kWh)",
        color="green", marker="x", markersize=4,
    )
    ax.set_title(titulo, fontsize=14)
    ax.set_xlabel("Hora del Día", fontsize=12)
    ax.set_ylabel("Energía en 15 min (kWh)", fontsize=12)
    ax.set_xticks(range(0, len(df), 4))  # una etiqueta por hora
    plt.setp(ax.get_xticklabels(), rotation=45)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(fontsize=12)
    fig.tight_layout()
    return fig


def energia_diaria_modelo_viejo(
    df: pd.DataFrame,
    titulo: str,
    marcas_cada_dias: int | None = None,
) -> Figure:
    """Energía diaria real vs. modelo viejo.

    Args:
        df: Salida de ``comparativas.diaria_real_vs_modelo_viejo``.
        titulo: Título del gráfico.
        marcas_cada_dias: Si se indica (p. ej. 2 para un mes), una marca por
            cada N días con formato ``dd/mm/aaaa`` y puntos en las series.
    """
    mensual = marcas_cada_dias is not None
    fig, ax = plt.subplots(figsize=(12, 6) if mensual else (15, 6))
    x = pd.to_datetime(df["fecha"])
    ax.plot(
        x, df["energia_real_kwh"],
        label="Energía Real Diaria (Growatt)" if mensual else "Energía Real (Growatt)",
        color=COLOR_REAL, linewidth=1.5, marker="o" if mensual else None,
    )
    ax.plot(
        x, df["energia_estimada_vieja"], label="Energía Estimada (Modelo Viejo - Diario)",
        color=COLOR_MODELO_VIEJO, linewidth=1.5 if mensual else 1.2, linestyle="--",
        marker="x" if mensual else None,
    )
    if mensual:
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=marcas_cada_dias))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m/%Y"))
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    ax.set_title(titulo, fontsize=14, fontweight="bold")
    ax.set_xlabel("Fecha", fontsize=12)
    ax.set_ylabel("Energía Diaria (kWh)", fontsize=12)
    ax.grid(True, linestyle="--", alpha=0.6)
    ax.legend(fontsize=11)
    fig.tight_layout()
    return fig

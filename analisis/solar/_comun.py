"""Utilidades de los scripts de análisis solar: leer tablas y guardar figuras.

Los scripts de esta carpeta no se despliegan: generan las figuras de la
tesis a partir de las tablas que deja el pipeline solar
(``data/processed/solar/``). Las figuras van a ``outputs/figures/solar/``
(ignorado por git); las que van al informe se copian a ``docs/informes/img/``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure

from optimia_hv.solar.configuracion import PROJECT_ROOT, cargar_config
from optimia_hv.solar.loaders import almacen

FIGURAS = PROJECT_ROOT / "outputs" / "figures" / "solar"


def tabla(nombre: str) -> pd.DataFrame:
    """Lee una tabla solar; termina con un mensaje claro si no existe."""
    df = almacen.leer(cargar_config().almacen_dir, nombre)
    if df.empty:
        sys.exit(
            f"No hay datos en '{nombre}'. Correr antes el pipeline solar "
            "(ver docs/05_uso/ejecutar_solar.md)."
        )
    return df


def guardar(fig: Figure, nombre: str, mostrar: bool = True) -> Path:
    """Guarda la figura en outputs/figures/solar/ (300 dpi) y opcionalmente la muestra."""
    FIGURAS.mkdir(parents=True, exist_ok=True)
    path = FIGURAS / nombre
    fig.savefig(path, dpi=300)
    print(f"Gráfico guardado en {path}")
    if mostrar:
        plt.show()
    return path

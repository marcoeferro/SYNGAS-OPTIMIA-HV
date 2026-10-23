"""Campana de generación intradía de un día: potencia real vs. modelo de 15 min.

Ex ``ValidarModelo/campana_15sept.py``. Requiere haber cargado el período con
``python -m optimia_hv.solar.pipelines.run_solar --validar 2026-09-12 2026-09-16``.

Uso:
    python analisis/solar/campana_2026-09-15.py [--fecha 2026-09-15] [--no-mostrar]
"""

from __future__ import annotations

import argparse
from datetime import date

from _comun import guardar, tabla

from optimia_hv.solar import graficos
from optimia_hv.solar.validacion import comparativas, metricas

parser = argparse.ArgumentParser(description="Campana intradía: real vs. modelo de 15 min")
parser.add_argument("--fecha", type=date.fromisoformat, default=date(2026, 9, 15))
parser.add_argument("--no-mostrar", action="store_true")
args = parser.parse_args()

comp = comparativas.intradia_real_vs_estimada(
    tabla("energia_estimada_15min"), tabla("growatt_produccion_intradia"),
    args.fecha, args.fecha,
)
print(metricas.resumen(comp["potencia_real_w"], comp["potencia_estimada_w"]))
fig = graficos.potencia_intradia(comp, f"Campana de Generación Intradía 15 min: {args.fecha}")
guardar(fig, f"campana_generacion_{args.fecha}.png", mostrar=not args.no_mostrar)

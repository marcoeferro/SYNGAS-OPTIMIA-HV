"""Potencia real vs. modelo de 15 min en varios días seguidos.

Ex ``ValidarModelo/graficar_comparativa_5days.py`` (12 al 16/09/2026).

Uso:
    python analisis/solar/comparativa_5dias_15min.py [--desde 2026-09-12] [--hasta 2026-09-16]
"""

from __future__ import annotations

import argparse
from datetime import date

from _comun import guardar, tabla

from optimia_hv.solar import graficos
from optimia_hv.solar.validacion import comparativas, metricas

parser = argparse.ArgumentParser(description="Real vs. modelo de 15 min en varios días")
parser.add_argument("--desde", type=date.fromisoformat, default=date(2026, 9, 12))
parser.add_argument("--hasta", type=date.fromisoformat, default=date(2026, 9, 16))
parser.add_argument("--no-mostrar", action="store_true")
args = parser.parse_args()

comp = comparativas.intradia_real_vs_estimada(
    tabla("energia_estimada_15min"), tabla("growatt_produccion_intradia"),
    args.desde, args.hasta,
)
print(metricas.resumen(comp["potencia_real_w"], comp["potencia_estimada_w"]))
titulo = (
    "Comparación Intradía 15 min: Real vs Estimada "
    f"({args.desde:%d/%m} al {args.hasta:%d/%m})"
)
fig = graficos.potencia_intradia(comp, titulo, intervalo_horas=6, formato="%d/%m %H:%M")
guardar(fig, "comparativa_5_dias_15min.png", mostrar=not args.no_mostrar)

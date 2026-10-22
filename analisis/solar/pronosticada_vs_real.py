"""Energía pronosticada vs. real de un día (por defecto, ayer).

Ex ``EstimarEnergia/grafico.py``.

Uso:
    python analisis/solar/pronosticada_vs_real.py [--fecha 2026-09-25] [--no-mostrar]
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta

from _comun import guardar, tabla

from optimia_hv.solar import graficos
from optimia_hv.solar.validacion import comparativas

parser = argparse.ArgumentParser(description="Energía pronosticada vs. real de un día")
parser.add_argument("--fecha", type=date.fromisoformat,
                    default=date.today() - timedelta(days=1))
parser.add_argument("--no-mostrar", action="store_true")
args = parser.parse_args()

df = comparativas.pronosticada_vs_real(
    tabla("energia_pronosticada"), tabla("growatt_produccion_intradia"), args.fecha,
)
if df.empty:
    raise SystemExit(f"No hay suficientes datos para comparar en la fecha {args.fecha}.")
fig = graficos.energia_pronosticada_vs_real(
    df, f"Comparación de Energía: Pronosticada vs Real - {args.fecha}"
)
guardar(fig, f"pronosticada_vs_real_{args.fecha}.png", mostrar=not args.no_mostrar)

"""Validación del modelo viejo (diario) contra la generación real de Growatt.

Ex ``modeloViejo/calcularModeloViejo.py``: desde el 01/08/2024 hasta hoy.
Con un rango de un mes (``--desde``/``--hasta``) reemplaza también a
``modeloViejo/grafico5dias.py`` (una marca cada 2 días).

Uso:
    python analisis/solar/modelo_viejo_historico.py
    python analisis/solar/modelo_viejo_historico.py --desde 2026-09-01 --hasta 2026-09-30
"""

from __future__ import annotations

import argparse
from datetime import date

from _comun import guardar, tabla

from optimia_hv.solar import graficos
from optimia_hv.solar.validacion import comparativas, metricas

parser = argparse.ArgumentParser(description="Real vs. modelo viejo (diario)")
parser.add_argument("--desde", type=date.fromisoformat, default=date(2024, 8, 1))
parser.add_argument("--hasta", type=date.fromisoformat, default=date.today())
parser.add_argument("--no-mostrar", action="store_true")
args = parser.parse_args()

comp = comparativas.diaria_real_vs_modelo_viejo(
    tabla("clima_historico_openmeteo"), tabla("growatt_produccion"), args.desde, args.hasta,
)
con_dato = comp[comp["energia_real_kwh"] > 0]
print(metricas.resumen(con_dato["energia_real_kwh"], con_dato["energia_estimada_vieja"]))

if (args.hasta - args.desde).days <= 31:
    titulo = f"Comparación Mensual ({args.desde:%m/%Y}): Producción Real vs. Modelo Viejo"
    fig = graficos.energia_diaria_modelo_viejo(comp, titulo, marcas_cada_dias=2)
    nombre = "comparativa_modelo_viejo_mes.png"
else:
    titulo = "Validación Histórica: Producción Real vs. Modelo Viejo (Resolución Diaria)"
    fig = graficos.energia_diaria_modelo_viejo(comp, titulo)
    nombre = "comparativa_modelo_viejo_diario.png"
guardar(fig, nombre, mostrar=not args.no_mostrar)

"""Estimación de generación fotovoltaica (tesis solar).

Estructura (ver docs/04_arquitectura/propuesta_estructura_monorepo.md):

- ``extractors``: Growatt, NASA POWER y Open-Meteo (histórico, diario,
  15 min y pronóstico).
- ``modelos``: modelo de 15 min y modelo viejo (línea de base).
- ``validacion``: métricas y comparativas modelo vs. real.
- ``pipelines``: punto de entrada que corre el cron (``run_solar``).
"""

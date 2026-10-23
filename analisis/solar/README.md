# Análisis solar

Scripts que generan las figuras de la tesis solar a partir de las tablas
del pipeline (`data/processed/solar/`). No se despliegan ni se testean: la
lógica (comparativas, métricas, gráficos) vive en `src/optimia_hv/solar/` y
está testeada; acá sólo se elige el período y se guarda la figura en
`outputs/figures/solar/`.

| Script | Reemplaza a | Figura |
|---|---|---|
| `campana_2026-09-15.py` | `ValidarModelo/campana_15sept.py` | Campana intradía de un día |
| `comparativa_5dias_15min.py` | `ValidarModelo/graficar_comparativa_5days.py` | Real vs. modelo, varios días |
| `modelo_viejo_historico.py` | `modeloViejo/calcularModeloViejo.py` y `modeloViejo/grafico5dias.py` | Real vs. modelo viejo (histórico o un mes) |
| `pronosticada_vs_real.py` | `EstimarEnergia/grafico.py` | Pronosticada vs. real de un día |

Antes de correrlos hay que cargar los datos (ver
[ejecutar el pipeline solar](../../docs/05_uso/ejecutar_solar.md)):

```bash
python -m optimia_hv.solar.pipelines.run_solar --historico
python -m optimia_hv.solar.pipelines.run_solar --validar 2026-09-12 2026-09-16
python analisis/solar/campana_2026-09-15.py
```

Todos aceptan `--no-mostrar` para guardar la figura sin abrir la ventana.

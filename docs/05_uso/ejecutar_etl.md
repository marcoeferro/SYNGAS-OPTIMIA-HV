# Ejecutar el ETL

> El ETL es el programa que descarga los datos y calcula los resultados.
> Con Docker corre solo una vez por semana; esta guía explica cómo correrlo a
> mano, sus opciones y qué hacer con el resultado.

## Formas de correrlo

| Dónde | Comando |
|---|---|
| Docker, Windows | `.\scripts\Run-Etl.ps1` |
| Docker, Linux/Mac | `make docker-etl` o `docker compose --profile etl run --rm etl_pipeline` |
| Python local | `python -m etl.pipelines.run_etl` o `make etl` |
| Python local, Windows | `.\scripts\Run-Etl.ps1 -Local` |

`Run-Etl.ps1` y `make docker-etl` reconstruyen la imagen antes de correr,
así siempre se usa el código actual.

## Opciones

```bash
python -m etl.pipelines.run_etl [opciones]
```

| Opción | Qué hace | Cuándo usarla |
|---|---|---|
| `--skip-extract` | No descarga las fuentes agrícolas; usa la última descarga | Recalcular rápido, o si MAGyP / Córdoba no responden |
| `--skip-tarifas` | No descarga tarifas; usa el último JSON | Recalcular rápido |
| `--estricto` | Si hay alertas de calidad, no publica los datos nuevos y termina con error | Corridas automáticas cuando se prefiere no publicar datos dudosos |
| `--n-campanas N` | Campañas del período de referencia (por defecto 5) | Análisis de sensibilidad |
| `--fraccion-recuperable F` | Fracción del rastrojo que se retira (por defecto 0,5) | Análisis de sensibilidad |
| `--tarifas RUTA` | Usa un JSON de tarifas o una carpeta distinta | Pruebas |
| `--config RUTA` | Archivo de rutas (por defecto `config/paths.yaml`) | Otra estructura de carpetas |
| `--log-config RUTA` | Archivo de logging (por defecto `config/logging.yml`) | Cambiar el formato de logs |

En PowerShell: `.\scripts\Run-Etl.ps1 -SkipExtract -SkipTarifas` (con o
sin `-Local`).

Ejemplos:

```bash
python -m etl.pipelines.run_etl                                   # completo (descarga todo)
python -m etl.pipelines.run_etl --skip-extract --skip-tarifas     # sólo recalcular
python -m etl.pipelines.run_etl --fraccion-recuperable 0.3        # escenario conservador
```

Partes sueltas:

```bash
python -m etl.extractors.scrape_estimaciones_agricolas   # sólo descargar MAGyP
python -m etl.extractors.scrape_bolsa_cereales_cba       # sólo descargar Bolsa de Córdoba
python -m etl.extractors.scrape_tarifas                  # sólo tarifas (ver tarifas_electricas.md)
```

## Cuánto tarda

Unos minutos. Casi todo el tiempo es la descarga de MAGyP (≈ 540
pedidos, uno por departamento) y de los cuadros tarifarios. Con
`--skip-extract --skip-tarifas` tarda menos de un minuto.

## Si una fuente falla

El ETL no se detiene por una fuente caída:

1. Cada pedido se **reintenta** ante errores temporales (429, 500, 502,
   503, 504 y cortes de red) con espera creciente (2, 4, 8… segundos, máximo
   60 s entre intentos, hasta 6 reintentos), o el tiempo que pida el servidor (`Retry-After`).
2. Si la fuente sigue fallando, el ETL continúa con las otras y al final
   hace una **segunda pasada** (60 s después).
3. Si vuelve a fallar, usa la **última descarga** de esa fuente y lo deja
   en el log.

Para las tarifas: si una distribuidora no responde, se conserva su valor
anterior (`fallback_previous`); si falla todo el extractor, se usa el
último JSON.

## Qué genera

| Archivo | Contenido |
|---|---|
| `data/processed/biomasa_validos.parquet` | Biomasa, energía y dinero por departamento, cultivo y campaña |
| `data/processed/potencial_energetico_anual.parquet` | Lo mismo como promedio anual del período de referencia |
| `data/reference/AAAAMMDDhhmmss_tarifas.json` | Tarifas vigentes por distribuidora |
| `data/reference/tarifas_historial.csv` | Historial de cuadros tarifarios |
| `data/audit/*.parquet` | Descartados, discrepancias entre fuentes y alertas |

Detalle de columnas: [contratos de artefactos](../03_datos/contratos_de_artefactos.md).

## Cómo saber si salió bien

- La última línea del log dice `Pipeline completado`. El código de salida
  es 0 (1 si falló).
- En el dashboard, **Inicio → Archivos de datos** muestra la fecha nueva.
- En **Auditoría de datos → Alertas de calidad** no hay alertas, o las que
  hay tienen explicación (por ejemplo, una suba de tarifa real).

## Avisos

Si se configura un webhook (Slack, Discord, Teams, Google Chat) o un bot de
Telegram, el ETL manda un mensaje cuando falla o cuando genera alertas de
calidad. Ver [despliegue → avisos](../04_arquitectura/despliegue.md#avisos).

## Logs

Cada línea es un objeto JSON (`etl/logging_setup.py`):

```json
{"timestamp": "2026-11-23T06:02:16.412-03:00", "level": "warning",
 "message": "HTTP 500 en intento 1/6 (...). Reintento en 2 s",
 "logger": "etl.extractors.http_retry", "module": "http_retry",
 "function": "_request_loop", "file": "etl/extractors/http_retry.py", "line": 125,
 "service": "etl-biomasa", "version": "0.3.0", "environment": "production",
 "host": "b9a99ee8be79", "pid": 812,
 "trace_id": "4048b52eee7b4a1cac38be1be569a54e", "stage": "extract", "source": "magyp",
 "request_id": "a1b2c3d4e5f60718", "http_method": "GET", "url": "https://...",
 "status_code": 500, "attempt": 1, "max_attempts": 6, "retry_in_s": 2.0}
```

| Pregunta | Campos |
|---|---|
| ¿Qué pasó? | `level`, `message`, `event` (`run_started` / `run_finished`), `exception` (tipo, mensaje y traza) |
| ¿Cuándo? | `timestamp` (ISO 8601 con zona), `duration_s` al terminar |
| ¿Dónde? | `environment`, `host`, `service`, `version`, `logger`, `module`, `function`, `file`, `line` |
| ¿En qué corrida y pedido? | `trace_id` (toda la corrida), `request_id` (un pedido HTTP con sus reintentos), `stage`, `source`, `distribuidora` |

- Archivo: `logs/pipeline.log` (JSON, nivel DEBUG; rota a los 10 MB, guarda 5 anteriores).
- En Docker, las corridas programadas salen en `docker logs biomasa_etl_worker`
  línea por línea, a medida que ocurren (`LOG_STREAM=/proc/1/fd/1`). En
  `biomasa_scheduler` queda solo el inicio y el fin de cada corrida (Ofelia).
- En Grafana: `{container="biomasa_etl_worker"} | json | trace_id="..."`
  muestra una corrida completa; `| json | request_id="..."`, un pedido.
- Variables: `LOG_LEVEL` (nivel de la consola; `DEBUG` para ver cada pedido),
  `LOG_FORMAT=text` (texto plano para leer en local), `APP_ENV` (entorno).
- Los warnings de Python (p. ej. `FutureWarning` de pandas) salen como líneas
  del log con `"logger": "py.warnings"`.

Mensajes útiles del log:

| Mensaje | Significado |
|---|---|
| `Falló la extracción de …; se reintentará` | Una fuente no respondió; habrá segunda pasada |
| `se usa el raw más reciente en disco` | Se usó la descarga anterior |
| `Impacto de exclusión` | Registros y producción que quedaron fuera por cultivo sin coeficientes |
| `Período de referencia anual: [...]` | Campañas usadas para el promedio |
| `[control …] …` (WARNING) | Un control de calidad detectó un cambio sospechoso |
| `Controles de calidad: sin alertas` | Los controles no encontraron nada raro |
| `Pipeline completado` | Terminó bien |

# Ejecutar el pipeline solar

> Cómo correr el pipeline de la tesis solar, qué guarda y cómo pasar del
> esquema anterior (scripts sueltos + MySQL) al actual. Fórmulas y
> fuentes: [metodología solar](../02_metodologia/solar/metodologia_solar.md).

## Requisitos

1. Paquete instalado: `pip install -e ".[dev]"` (o la imagen Docker).
2. Credenciales de Growatt en `.env` (copiar `.env.example`):
   `GROWATT_USER`, `GROWATT_PASSWORD`, `GROWATT_PLANT_ID`. Sin ellas sólo
   fallan los pasos de Growatt; el clima y el pronóstico se descargan igual.
3. Parámetros de la planta en `config/solar.yaml` (coordenadas, potencia,
   PR, inclinación, carpeta de salida).

## Comandos

| Tarea | Comando |
|---|---|
| Corrida diaria (lo que hace el cron) | `python -m optimia_hv.solar.pipelines.run_solar` · `make solar` · `optimia-solar` |
| Sólo algunos pasos | `optimia-solar --solo nasa open_meteo pronostico_15min energia_pronosticada` |
| Carga histórica completa (desde `historico.desde`) | `optimia-solar --historico` · `make solar-historico` |
| Validar el modelo en un período | `optimia-solar --validar 2026-09-12 2026-09-16` |
| Traer el histórico de la base MySQL anterior | `pip install -e ".[solar]"` y `optimia-solar --importar-sql mysql+mysqlconnector://root:@localhost/datos` |
| Figuras de la tesis | scripts de [`analisis/solar/`](../../analisis/solar/README.md) |
| Con Docker | `docker compose exec etl_worker python -m optimia_hv.solar.pipelines.run_solar` |

El cron (`config/schedule.ini`, job `solar`) corre la corrida diaria a las
06:30. Cada paso es independiente: si uno falla (p. ej. Growatt caído) los
demás siguen, y al final se envía un aviso (mismos canales que biomasa,
ver [despliegue](../04_arquitectura/despliegue.md)) y el proceso sale con
código 1.

### Pasos de la corrida diaria

| # | Paso (`--solo`) | Qué hace | Tabla |
|---|---|---|---|
| 1 | `growatt_diaria` | Energía diaria del mes en curso hasta ayer, con huecos completados | `growatt_produccion` |
| 2 | `nasa` | Clima diario NASA POWER, últimos 30 días | `clima_historico_nasa` |
| 3 | `open_meteo` | Clima diario Open-Meteo, últimos 30 días (kWh/m²) | `clima_historico_openmeteo` |
| 4 | `pronostico_diario` | Pronóstico diario a 7 días | `clima_pronosticado` |
| 5 | `growatt_15min` | Potencia de ayer cada 15 min | `growatt_produccion_intradia` |
| 6 | `pronostico_15min` | Pronóstico cada 15 min a 5 días | `pronostico_15min_5days` |
| 7 | `energia_pronosticada` | Modelo de 15 min sobre el pronóstico (si el paso 6 falló, usa el último guardado) | `energia_pronosticada` |

`--validar DESDE HASTA` guarda `clima_15min_openmeteo` (clima observado
cada 15 min), `growatt_produccion_intradia` (cada 5 min) y
`energia_estimada_15min`, y escribe en el log MAE, RMSE, sesgo y error de
energía del período.

## Qué se guarda

Un Parquet por tabla en `data/processed/solar/` (no se versiona). Los
nombres de tablas y columnas son **los mismos que en la base MySQL
anterior**. Si la clave ya existe, la fila nueva reemplaza a la vieja (como
`REPLACE INTO`), así se corrigen los días que llegaron incompletos.

| Tabla | Clave | Columnas |
|---|---|---|
| `growatt_produccion` | `fecha` | `energia` (kWh) |
| `growatt_produccion_intradia` | `fecha_hora` | `potencia_w` |
| `clima_historico_nasa` | `fecha` | `temperatura_media` (°C), `humedad_relativa` (%), `radiacion_solar` (kWh/m²) |
| `clima_historico_openmeteo` | `fecha` | ídem |
| `clima_pronosticado` | `fecha_consulta`, `fecha_pronosticada` | `temp_predicha`, `humedad_relativa_predicha`, `radiacion_predicha` (kWh/m²) |
| `pronostico_15min_5days` | `fecha_consulta`, `fecha_hora` | `temp_c`, `humedad_relativa`, `velocidad_viento`, `cobertura_nubes`, `presion_hpa`, `radiacion_global_wm2`, `radiacion_directa_wm2`, `radiacion_difusa_wm2` |
| `clima_15min_openmeteo` | `fecha_hora` | `temperatura`, `humedad_relativa`, `radiacion_solar`, `velocidad_viento`, `cobertura_nubes`, `presion_superficie`, `radiacion_directa`, `radiacion_difusa` (W/m²) |
| `energia_pronosticada` | `fecha_hora` | `fecha`, `hora`, `temp_c`, `humedad_relativa`, `velocidad_viento`, `cobertura_nubes`, `presion_hpa`, `radiacion_inclinada_kwhm2`, `energia_estimada_kwh` |
| `energia_estimada_15min` | `fecha_hora` | ídem |

**Réplica en MySQL (opcional).** Con `SOLAR_DB_URL` definida (p. ej.
`mysql+mysqlconnector://root:@localhost/datos`), cada guardado también se
escribe en esa base, en las mismas tablas: las consultas y planillas que
ya existían siguen funcionando. Si la réplica falla, se registra en el log
y la corrida sigue (el Parquet ya quedó guardado).

## De los scripts anteriores al pipeline

| Antes | Ahora |
|---|---|
| `main_actualizaciones.py` | `optimia-solar` (corrida diaria) |
| `datosHistoricos/*.py` | `optimia-solar --historico` |
| `datosDiarios/*.py`, `EstimarEnergia/growatt_diaria_15min.py`, `EstimarEnergia/pronostico_15min_5days.py`, `EstimarEnergia/energia_pronosticada_15min.py` | pasos 1-7 de la corrida diaria |
| `ValidarModelo/climaHistorico_OP_15min.py`, `ValidarModelo/growatt_intradia.py`, `ValidarModelo/estimacionEnergia15min.py` | `optimia-solar --validar DESDE HASTA` |
| `ValidarModelo/campana_15sept.py`, `ValidarModelo/graficar_comparativa_5days.py`, `modeloViejo/*.py`, `EstimarEnergia/grafico.py` | `analisis/solar/*.py` |
| Usuario/clave de Growatt y conexión MySQL escritos en cada script | `.env` y `config/solar.yaml` |

Correspondencia por módulo: tabla "Dónde va cada archivo de la compañera"
de la [propuesta de estructura](../04_arquitectura/propuesta_estructura_monorepo.md).

## Problemas frecuentes

| Síntoma | Causa | Qué hacer |
|---|---|---|
| `Faltan variables de entorno de Growatt` | No hay `.env` o le faltan variables | Completar `GROWATT_*` y, en Docker, `docker compose up -d` para recrear el worker |
| `Growatt no devolvió JSON (¿sesión vencida?)` | Clave incorrecta o el portal cambió | Probar el login en la web; correr `pytest -m contract` |
| Faltan los últimos días de NASA | NASA publica la radiación con 4-5 días de atraso | Normal: se completan solos en las corridas siguientes |
| El dashboard solar dice "Todavía no hay datos" | El pipeline solar no corrió | `optimia-solar` (o `--historico` la primera vez) |

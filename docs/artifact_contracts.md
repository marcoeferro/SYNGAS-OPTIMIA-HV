# Contratos de artefactos intermedios

Definición de qué escribe cada etapa, dónde y con qué schema.
Pensado para orquestadores (Ofelia, n8n, CLI) y para tests de regresión.

Todas las rutas son relativas a la raíz del repositorio, configurables
en `config/paths.yaml`.

---

## 1. Extracción (`etl.extractors.*`)

| Artefacto | Path | Formato | Productor |
|-----------|------|---------|-----------|
| CBA raw | `data/raw/{YYYYMMDDHHMMSS}_datos_bolsa_granos_cba.csv` | CSV utf-8-sig | `scrape_bolsa_cereales_cba.run_extractor` |
| MAGYP raw | `data/raw/{YYYYMMDDHHMMSS}_datos_estimaciones.csv` | CSV utf-8-sig | `scrape_estimaciones_agricolas.run_extractor` |
| Nación raw (opcional) | `data/raw/{YYYYMMDDHHMMSS}_datos_bolsa_cereales_nacion.xlsx` | XLSX | `scrape_bolsa_cereales_nacion.run_extractor` |
| Caché provincias MAGYP | `data/raw/estimaciones_agricolas_provincias.json` | JSON | extractor MAGYP |
| Caché departamentos MAGYP | `data/raw/estimaciones_agricolas_departamentos.json` | JSON | extractor MAGYP |

**Reglas de nombre**

- Prefijo obligatorio: `YYYYMMDDHHMMSS_` (hora local del proceso).
- Stem fijo por fuente (`datos_bolsa_granos_cba`, `datos_estimaciones`, …).
- El pipeline resuelve el más reciente con `find_latest_raw`. Si no hay
  timestamped, acepta el nombre legacy sin prefijo (compatibilidad).

**Schema CBA raw (columnas)**

```
PROVINCIA, DEPARTAMENTO, CULTIVO, CAMPAÑA,
SEMBRADAS, COSECHADAS, RENDIMIENTO,
RENDIMIENTO GRANO LIMPIO Y SECO, PRODUCCIÓN, PRODUCCIÓN GRANO LIMPIO Y SECO
```

**Schema MAGYP raw (columnas típicas)**

```
Cultivo, Campaña, Provincia, Departamento,
Sup. Sembrada, Sup. Cosechada, Producción, Rendimiento
```

---

## 2. Transformación – fuentes normalizadas (en memoria)

No se persisten por defecto. Schema canónico post
`group_and_standardize`:

| Columna | Tipo | Notas |
|---------|------|-------|
| Provincia | str | normalizada (`clean_str` + geo) |
| Departamento | str | normalizada |
| Campaña | str | |
| Cultivo | str | canónico vía taxonomía |
| Superficie (Ha) | float | |
| Produccion (Tn) | float | |
| Rendimiento (Tn/Ha) | float | derivado |
| fuente | str | `bolsa_cereales_cba` \| `magyp_estimaciones` |

Clave natural: `(Campaña, Provincia, Departamento, Cultivo)`.

---

## 3. Reconciliación y biomasa

| Artefacto | Path | Formato | Contenido |
|-----------|------|---------|-----------|
| Biomasa válida | `data/processed/biomasa_validos.parquet` | Parquet snappy | Solo `_valido_biomasa=True` + densidades + energía/finanzas |
| Descartados | `data/audit/descartados_reconciliacion.parquet` | Parquet snappy | Perdedores de reconciliación multi-fuente |
| Discrepancias | `data/audit/discrepancias_cba_vs_magyp.parquet` | Parquet snappy | Auditoría CBA vs MAGYP (puede estar vacío) |

**Columnas adicionales de biomasa**

```
FR, Residuo de Biomasa (Tn), Residuo de Biomasa (Tn/Ha),
Produccion (Tn/Ha), _tiene_ic, _rendimiento_invalido, _valido_biomasa
```

**Columnas energéticas / financieras (PP30)**

```
masa_humeda_kg, masa_seca_kg,
kwh_generados, kwh_autoconsumo, kwh_inyectados, horas_operacion_estimadas,
tarifa_compra_kwh, tarifa_inyeccion_kwh, distribuidora,
ahorro_autoconsumo_ars, credito_inyeccion_ars, beneficio_total_ars
```

Parámetros y tarifas: JSON más reciente en `data/reference/*_tarifas.json`.

---

## 4. Referencia estática

| Artefacto | Path | Uso |
|-----------|------|-----|
| IC / FR | `data/reference/ic_fr.csv` | `Residuo = Produccion × FR` |
| Tarifas PP30 | `data/reference/{YYYYMMDDHHMMSS}_tarifas.json` | CE, humedad, α, tarifas por distribuidora |
| PDFs/HTML tarifarios | `data/raw/tarifas/` | Evidencia de scrape (`scrape_tarifas`) |

---

## 5. Invocación CLI (orquestadores)

```bash
# Full (extract + transform + load)
python -m etl.pipelines.run_etl --config config/paths.yaml

# Solo transform/load sobre el raw más reciente
python -m etl.pipelines.run_etl --skip-extract

# Extractors individuales
python -m etl.extractors.scrape_bolsa_cereales_cba
python -m etl.extractors.scrape_estimaciones_agricolas
```

Ofelia (`config/schedule.ini`) ejecuta el entrypoint completo del pipeline
(incluye extract). Para dos jobs separados, apuntar un job a cada
extractor y otro a `run_etl --skip-extract`.

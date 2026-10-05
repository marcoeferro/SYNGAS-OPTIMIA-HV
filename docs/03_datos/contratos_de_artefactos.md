# Contratos de artefactos

> Qué archivo escribe cada etapa, dónde y con qué columnas. Sirve para
> orquestadores (Ofelia, n8n, scripts), para quien consuma los resultados
> desde otra herramienta y para tests de regresión.

Rutas relativas a la raíz del repositorio. Las carpetas se configuran en
`config/paths.yaml`. Qué se versiona en git: `data/reference/` sí;
`data/raw/`, `data/processed/` y `data/audit/` no (se regeneran).

```
data/
├── raw/          descargas (no se versionan)
├── reference/    coeficientes, tarifas, historial, cuadros manuales (se versiona)
├── processed/    resultados para el dashboard (no se versionan)
└── audit/        auditoría y alertas (no se versionan)
```

---

## 1. Extracción → `data/raw/`

| Artefacto | Ruta | Formato | Productor |
|---|---|---|---|
| MAGyP | `data/raw/AAAAMMDDhhmmss_datos_estimaciones.csv` | CSV UTF-8 con BOM | `scrape_estimaciones_agricolas.run_extractor` |
| Bolsa de Córdoba | `data/raw/AAAAMMDDhhmmss_datos_bolsa_granos_cba.csv` | CSV UTF-8 con BOM | `scrape_bolsa_cereales_cba.run_extractor` |
| Catálogos MAGyP | `data/raw/estimaciones_agricolas_provincias.json`, `…_departamentos.json` | JSON | extractor MAGyP (caché) |
| Cuadros tarifarios | `data/raw/<código>/<sha256[:16]>.<pdf\|xlsx\|xls\|zip>` | original | `scrape_tarifas` |
| Páginas índice de tarifas | `data/raw/indices/AAAAMMDDhhmmss_<host>.html` | HTML | `scrape_tarifas` |

**Reglas de nombre**:
- Prefijo `AAAAMMDDhhmmss_` (hora local) y nombre fijo por fuente.
- El pipeline usa el más reciente (`find_latest_raw`). Si no hay archivos
  con prefijo, acepta el nombre sin prefijo (compatibilidad).
- Si una descarga falla, se reintenta y, como último recurso, se usa el
  último archivo existente (ver [ejecutar el ETL](../05_uso/ejecutar_etl.md)).

**Columnas MAGyP**: `Cultivo, Campaña, Provincia, Departamento, idProvincia,
idDepartamento, Sup. Sembrada, Sup. Cosechada, Producción, Rendimiento`.

**Columnas Bolsa de Córdoba**: `PROVINCIA, DEPARTAMENTO, CULTIVO, CAMPAÑA,
SEMBRADAS, COSECHADAS, RENDIMIENTO, RENDIMIENTO GRANO LIMPIO Y SECO,
PRODUCCIÓN, PRODUCCIÓN GRANO LIMPIO Y SECO`.

---

## 2. Referencia → `data/reference/`

| Artefacto | Ruta | Contenido |
|---|---|---|
| Coeficientes por cultivo | `ic_fr.csv` | `Cultivo, IC, Fuente bibliográfica, FR, MS, Fuente MS` |
| Tarifas vigentes | `AAAAMMDDhhmmss_tarifas.json` | Ver abajo. El pipeline usa el más reciente. |
| Historial de tarifas | `tarifas_historial.csv` | Un registro por documento procesado (sin duplicados por SHA-256) |
| Cuadros manuales | `cuadros_manuales/<CÓDIGO>/` | Cuadros bajados a mano (ver [tarifas](tarifas_electricas.md#carga-manual-de-cuadros)) |

**JSON de tarifas** (claves principales):

| Clave | Contenido |
|---|---|
| `parametros_pp30` | `consumo_especifico_kg_kwh`, `humedad_pct_default`, `factor_autoconsumo_default`, `potencia_nominal_kw`, `disponibilidad`, `fraccion_recuperable_default` |
| `provincia_a_distribuidora` | Provincia → código (o lista de códigos) |
| `departamento_a_distribuidora` | Excepciones por departamento (EDESTE, EDELAP) |
| `distribuidoras.<CÓDIGO>` | `tarifa_compra_kwh`, `tarifa_inyeccion_kwh`, `cargo_fijo_mensual`, `vigencia`, `fuente_tipo`, `documento`, `sha256`, `estado_campos` (estado por campo), `seccion_compra` (fila usada) |
| `resumen_extraccion` | Totales por estado (`extraidas_en_esta_corrida`, `fallback_previous`, `sin_dato`) |

**Columnas del historial**: `distribuidora, vigencia, tarifa_compra_kwh,
tarifa_inyeccion_kwh, cargo_fijo_mensual, seccion_compra, puntaje_compra,
n_valores_compra, n_valores_inyeccion, fuente_tipo, documento, sha256,
fecha_extraccion`.

---

## 3. Transformación (en memoria)

No se persiste. Esquema común de ambas fuentes después de
`group_and_standardize`:

| Columna | Tipo | Notas |
|---|---|---|
| Provincia, Departamento | str | Normalizados: minúsculas, sin tildes, con alias |
| Campaña | str | `AAAA/AA` |
| Cultivo | str | Nombre canónico (taxonomía) |
| Superficie (Ha), Produccion (Tn) | float | Faltante = NaN, nunca 0 |
| Rendimiento (Tn/Ha) | float | Derivado; NaN si la superficie es 0 |
| fuente | str | `magyp_estimaciones` \| `bolsa_cereales_cba` |

Clave natural: `(Provincia, Departamento, Campaña, Cultivo)`.

---

## 4. Resultados → `data/processed/`

### `biomasa_validos.parquet`

Un registro por provincia, departamento, campaña y cultivo, **sólo
registros válidos** (`_valido_biomasa = True`). Columnas:

| Grupo | Columnas |
|---|---|
| Clave y origen | `Provincia, Departamento, Campaña, Cultivo, fuente` |
| Producción | `Superficie (Ha), Produccion (Tn), Rendimiento (Tn/Ha), Produccion (Tn/Ha)` |
| Biomasa | `FR, MS, Residuo de Biomasa (Tn), Residuo de Biomasa (Tn/Ha), Residuo Recuperable (Tn)` |
| Marcas | `_tiene_ic, _rendimiento_invalido, _valido_biomasa` |
| Energía | `masa_seca_kg, masa_alimentada_kg, kwh_generados, horas_operacion_estimadas, equipos_pp30_equivalentes, kwh_autoconsumo, kwh_inyectados` |
| Tarifa | `distribuidora, tarifa_compra_kwh, tarifa_inyeccion_kwh, tarifa_es_proxy, tarifa_origen, tarifa_inyeccion_estimada` |
| Dinero | `ahorro_autoconsumo_ars, credito_inyeccion_ars, beneficio_total_ars` |

### `potencial_energetico_anual.parquet`

Promedio anual del período de referencia (5 campañas completas), por
provincia, departamento y cultivo. Mismas columnas de biomasa, energía,
tarifa y dinero, **expresadas por año**, más `n_campanas_con_dato` y
`periodo_referencia`. Sin `Campaña`.

---

## 5. Auditoría → `data/audit/`

| Artefacto | Contenido |
|---|---|
| `descartados_reconciliacion.parquet` | Registros que perdieron la reconciliación: `Provincia, Departamento, Campaña, Cultivo, Superficie (Ha), Produccion (Tn), Rendimiento (Tn/Ha), fuente` |
| `discrepancias_cba_vs_magyp.parquet` | Claves informadas por ambas fuentes: superficie y producción de cada una y `diff_rel_superficie`, `diff_rel_produccion` |
| `alertas_calidad.parquet` | Alertas de la última corrida: `control, entidad, valor_anterior, valor_actual, variacion, umbral, detalle, fecha` (vacío si no hubo) |
| `biomasa_validos.parquet` | Copia de `data/processed/biomasa_validos.parquet` |

---

## 6. Invocación (orquestadores)

```bash
python -m etl.pipelines.run_etl                         # completo
python -m etl.pipelines.run_etl --skip-extract          # sin descargar fuentes agrícolas
python -m etl.pipelines.run_etl --skip-tarifas          # sin descargar tarifas
python -m etl.pipelines.run_etl --estricto              # no publica si hay alertas

python -m etl.extractors.scrape_estimaciones_agricolas  # sólo MAGyP
python -m etl.extractors.scrape_bolsa_cereales_cba      # sólo Bolsa de Córdoba
python -m etl.extractors.scrape_tarifas                 # sólo tarifas
```

Código de salida: `0` si terminó bien, `1` si falló (incluye modo estricto
con alertas). El scheduler Ofelia (`config/schedule.ini`) ejecuta el
pipeline completo.

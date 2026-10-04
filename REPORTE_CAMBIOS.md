# Reporte de revisión y correcciones — ETL Biomasa Residual

Fecha: 2026-10-04 · Rama: `claude/magical-archimedes-n5hea8`

Este documento resume la revisión completa del repositorio (extractores, transformadores, pipeline, notebook `main.ipynb` y dashboard): los errores encontrados, por qué eran errores y cómo se corrigieron. Al final se listan las verificaciones realizadas y los puntos que quedan pendientes.

---

## 1. Resumen ejecutivo

| # | Severidad | Área | Error | Estado |
|---|---|---|---|---|
| E1 | **Crítica** | Scraper tarifas | No extraía ningún valor: el JSON siempre copiaba el baseline manual | Corregido (parser PDF + validación + trazabilidad) |
| E2 | **Crítica** | Extractor/limpieza CBA | Merge cartesiano replicaba filas → producción ×2/×4 | Corregido |
| E3 | **Crítica** | Metodología energía | La humedad se descontaba dos veces (energía −23 %) | Corregido |
| E4 | **Crítica** | Metodología | Se sumaban 57 campañas (1969–2026) en gráficos/totales | Corregido (período de referencia anual) |
| E5 | Alta | Metodología biomasa | IC (base seca) aplicado a producción húmeda/fresca (+16 % total; ×3–5 en papa/ajo) | Corregido (factor MS) |
| E6 | Alta | Metodología energía | Se usaba el 100 % del rastrojo como combustible | Corregido (fracción recuperable) |
| E7 | Alta | Limpieza MAGYP | `SD` (sin dato) se convertía en producción 0 | Corregido |
| E8 | Alta | Pipeline | El extractor de tarifas nunca se ejecutaba | Corregido |
| E9 | Media | Reconciliación | Empates resueltos según el orden de concatenación (no determinístico) | Corregido |
| E10 | Media | Auditoría | `discrepancias_cba_vs_magyp.parquet` se guardaba vacío | Corregido |
| E11 | Media | Validación | `assert` desactivable con `python -O`; no se validaba la fuente; NaN rompía invariantes | Corregido |
| E12 | Media | Tarifas | Buenos Aires mapeada a EDENOR (AMBA) sin advertencia | Marcado como `es_proxy` |
| E13 | Media | Notebook | `import geopandas` (no instalado) rompía la primera celda | Corregido |
| E14 | Media | Notebook | Flags de validez distintos a los del ETL (sin exigir superficie > 0) | Corregido |
| E15 | Media | Pipeline | Logging buscaba `config/logging.yaml` (el archivo es `.yml`) | Corregido |
| E16 | Baja | Extractores | Validaciones faltantes (HTML con HTTP 200, descargas parciales, caché en ruta fija) | Corregido |
| E17 | Baja | Taxonomía | `alfalfa` (presente en CBA) no estaba mapeada → fail-fast si trae producción | Corregido |
| E18 | Baja | Dashboard | Campañas por defecto incluían la campaña incompleta; KPIs sumaban campañas | Corregido |
| E19 | Baja | Dependencias | Faltaba `pypdf`; `curl_cffi` no declarado | Corregido / documentado |

---

## 2. Extracción (scraping)

### E1 — El scraper de tarifas no extraía los valores de referencia

**Archivo**: `etl/extractors/scrape_tarifas.py`

**Problema**. El extractor descargaba los PDF de EDENOR y EPEC y el HTML de EPE/EDEMSA, pero **nunca los leía**. Los valores numéricos del JSON (`tarifa_compra_kwh`, `tarifa_inyeccion_kwh`, `cargo_fijo_mensual`) salían siempre de `BASELINE_TARIFAS` (valores cargados a mano) o se copiaban del JSON anterior. Cada corrida generaba un archivo "nuevo" con los mismos números, lo que daba una falsa sensación de actualización. Además:

- Las URL de EPEC eran dos PDF fijos de enero y septiembre de 2025 (desactualizados).
- No se verificaba que lo descargado fuera un PDF (los portales devuelven HTML de login/404 con HTTP 200).
- No había forma de saber si un valor había sido extraído o heredado.

**Corrección**. Se reescribió el extractor:

1. **Descubrimiento del PDF vigente**: descarga la página índice de cada distribuidora, toma los enlaces `.pdf` que contienen `tarif`/`cuadro` y los ordena por la fecha embebida en el nombre (soporta `YYYY-MM`, `YYYYMMDD` y el formato `DDMMYY` de EPEC, p. ej. `...-aplicacion-010925.pdf`). Las URL fijas quedan sólo como respaldo.
2. **Validación de firma** `%PDF` antes de parsear.
3. **Extracción de texto** con `pypdf`.
4. **Parseo**: busca la sección de la categoría objetivo en orden de preferencia (T3 / Grandes consumos → T2 / Medianas demandas), recorre todas sus ocurrencias (la primera puede ser un índice sin importes) y toma los cargos con unidad `$/kWh` en formato numérico argentino (`1.234,5678`). La tarifa de compra es la **mediana** de los cargos (con bandas pico/resto/valle representa la banda central). Igual para la sección de inyección / usuario-generador. El cargo fijo se toma de la línea `$/mes`. Los cargos `$/kW-mes` (potencia) no se confunden con `$/kWh`.
5. **Validación de plausibilidad**: rango 1–2000 ARS/kWh, inyección < compra, variación máxima ×4 respecto de la corrida previa. Un valor que no pasa se rechaza y se registra en `rechazos_validacion`.
6. **Trazabilidad por campo** (`estado_campos`): `parsed_pdf`, `fallback_previous` (valor de una corrida anterior porque hoy no se pudo extraer) o `baseline_manual`. También se guardan `documento_fuente`, `fecha_extraccion`, `seccion_detectada` y `valores_detectados`, y un `resumen_extraccion` global.
7. Las funciones de descarga y de PDF→texto son **inyectables**, lo que permite testear el flujo completo sin red.

**Verificación**. Tests unitarios y end-to-end (`tests/test_energy_tarifas.py`) con un cuadro sintético: toma la sección T3 ignorando el índice, devuelve 65,50 ARS/kWh (mediana de pico/resto/valle), 35,21 de inyección y 25.300 de cargo fijo; ignora la respuesta HTML de EPE; y en una segunda corrida sin red conserva el valor como `fallback_previous`. Además se probó el recorrido real `PDF → pypdf → parser` con un PDF generado localmente.

> ⚠ **Limitación importante**: la política de red de este entorno bloquea `epec.com.ar`, `edenor.com`, `epe.santafe.gov.ar` y `edemsa.com` (HTTP 403 del proxy), así que **no fue posible validar el parser contra los PDF reales**. El JSON vigente (`data/reference/20261004134204_tarifas.json`) quedó con todos los campos en `baseline_manual`. Hay que correr `python -m etl.extractors.scrape_tarifas` desde una red con acceso y revisar `estado_campos` y `valores_detectados`. Si el formato de algún cuadro no matchea, ajustar `SECTION_PATTERNS_COMPRA` / `SECTION_PATTERNS_INYECCION`.
>
> Una búsqueda pública indica que el cargo variable de la Tarifa N.º 2 de EPEC era ≈ 54 ARS/kWh (cuadro aplicado el 01/09/2025, sin impuestos), mientras que el baseline usa **210 ARS/kWh**. No pude verificar si el baseline incluye impuestos u otros cargos, pero podría estar sobreestimando los montos hasta ~4×. Los montos en ARS deben considerarse ilustrativos hasta que se extraigan las tarifas reales.

### E2 — Filas replicadas en CBA por merge cartesiano

**Archivos**: `etl/extractors/scrape_bolsa_cereales_cba.py`, `etl/transformers/source_cleaning.py`

**Problema**. El extractor combina las hojas *Superficie*, *Rendimiento* y *Producción* con un `merge(how="outer")`. En algunas claves la hoja de producción trae dos variantes de "grano limpio y seco" y la de rendimiento otras dos: el merge genera **2 × 2 = 4 filas** con la misma superficie y producción. Luego `process_cba` descarta las columnas de grano limpio y seco y `group_and_standardize` hace `sum`, con lo que **la producción de esas claves quedaba cuadruplicada**. En el raw actual: 10 claves ×4 (30 filas espurias), p. ej. *Buenos Aires / 25 de Mayo / maní / 2022/23*.

**Corrección**.
- En el extractor: `drop_duplicates()` de cada hoja antes del merge y deduplicación posterior sobre clave + columnas núcleo (`SEMBRADAS`, `COSECHADAS`, `RENDIMIENTO`, `PRODUCCIÓN`).
- En la transformación (para proteger también los raw ya descargados): nueva función `dedupe_cba_merge_artifacts`, que elimina las filas replicadas y registra un warning con el conteo.
- Se reemplazó el `dropna()` global por `dropna(subset=["COSECHADAS", "PRODUCCIÓN"])`.

### E16 — Robustez de los extractores

- **CBA**: si el enlace de SharePoint vence, devuelve HTML con HTTP 200 y `pd.read_excel` fallaba con un error poco claro. Ahora se valida la firma ZIP del XLSX.
- **MAGYP**:
  - `validate_download_columns`: una página de error HTML interpretada como CSV se concatenaba al dataset. Ahora se exige el esquema esperado.
  - Si falla más del 5 % de los departamentos, la extracción lanza un error en lugar de guardar en silencio un dataset parcial (`MAX_FAIL_RATIO`).
  - Los catálogos de provincias/departamentos se cacheaban siempre en `./data/raw` aunque se pidiera otro `output_dir`.
  - Variable `csv_error` sin uso.

---

## 3. Transformación

### E7 — Faltantes convertidos en cero (MAGYP `SD`)

**Archivo**: `etl/transformers/source_cleaning.py`

`pd.to_numeric(errors="coerce")` convierte `SD` en `NaN`, pero `groupby().sum()` devuelve **0** para un grupo íntegramente `NaN`. Un dato faltante se convertía en "producción cero". Se usa `sum(min_count=1)` y el rendimiento queda `NaN` cuando la superficie cosechada es 0.

### E9 — Reconciliación no determinística

**Archivo**: `etl/transformers/reconciliation.py`

Con producciones iguales, el registro elegido dependía del orden de concatenación (el `sort_values` por defecto no es estable). Ahora el orden es: producción descendente (NaN al final), luego prioridad de fuente (MAGYP, oficial, primero), con `kind="mergesort"`. El dataset de descartados se construye directamente como "todo lo no seleccionado".

### E10 — Discrepancias CBA vs MAGYP vacías

El pipeline persistía `pd.DataFrame()` en `discrepancias_cba_vs_magyp.parquet` (el cálculo sólo existía en el notebook). Nueva función `compute_discrepancies`: por cada clave cubierta por ambas fuentes guarda superficie y producción de cada una y la diferencia relativa. Hoy: 3.243 claves.

### E11 — Validaciones

**Archivo**: `etl/transformers/validation.py`

- Se usaban `assert`, que se **desactivan** con `python -O`. Se reemplazaron por `raise AssertionError` explícito.
- El docstring decía validar el dominio de `fuente`, pero no lo hacía. Ahora sí.
- Con faltantes legítimos (`NaN`), `(prod >= 0).all()` fallaba. Se valida "no hay negativos" y la invariante de máximo trata `NaN == NaN`.

### E15 — Logging nunca configurado

**Archivo**: `etl/pipelines/run_etl.py`

`DEFAULT_LOGGING_PATH` apuntaba a `config/logging.yaml`, pero el archivo es `config/logging.yml`. Se usaba siempre `basicConfig` y no se escribía `logs/pipeline.log`. Se corrigió la ruta y se crea el directorio del handler de archivo.

### E17 — Taxonomía

`alfalfa` aparece en la fuente CBA. Hoy esas filas no tienen producción y se descartaban antes, pero si en una nueva extracción trajeran datos el pipeline abortaría por el fail-fast de `resolve_crops`. Se agregó como cultivo simple (sin IC, queda excluido por flag).

### Otros (carga IC)

`load_ic_table` confiaba en la columna `FR` persistida: si alguien editaba el `IC` a mano, `FR` quedaba desincronizado. Ahora `FR` se recalcula siempre desde `IC`, se avisa si difiere y se valida `0 < IC < 1`.

---

## 4. Errores metodológicos

### E5 — IC en base seca aplicado a producción húmeda

**Archivos**: `data/reference/ic_fr.csv`, `etl/reference/load_ic.py`, `etl/transformers/biomass.py`, notebook §3.11

El índice de cosecha se define como grano / biomasa aérea **en materia seca**. La producción de MAGYP/CBA está a humedad de comercialización (granos 8–15 %) o **en fresco** (papa ≈ 80 % de agua, ajo ≈ 65 %). `Residuo = Producción × FR` sobreestimaba el residuo seco.

**Corrección**: se agregó a la tabla IC la columna `MS` (fracción de materia seca del producto cosechado, con su fuente en `Fuente MS`) y el residuo pasa a ser

$$\text{Residuo (t MS)} = \text{Producción} \times MS \times \frac{1-IC}{IC}$$

Efecto medido en el notebook: **−16,2 %** sobre el residuo total; para papa el valor anterior era ~5× el correcto. Si la tabla no tiene `MS`, se asume 1 con un warning (compatibilidad hacia atrás).

### E6 — Se usaba el 100 % del rastrojo

Retirar todo el residuo del lote no es agronómicamente viable (erosión, pérdida de materia orgánica, especialmente en siembra directa). Se agregó `add_recoverable_residue` y la columna `Residuo Recuperable (Tn)` con `fraccion_recuperable_default = 0.5` (configurable en `parametros_pp30` del JSON de tarifas o con `--fraccion-recuperable`). La energía se calcula sobre el residuo recuperable.

### E3 — La humedad se descontaba dos veces

**Archivo**: `etl/transformers/energy_finance.py`

Antes: `masa_seca = Residuo × (1 − H)` y `kWh = masa_seca / CE`. Esto era doblemente incorrecto: (a) el residuo ya está en base seca y no hay que restarle humedad, y (b) el consumo específico del PP30 (≈ 1,1 kg/kWh) está expresado sobre biomasa **tal como se alimenta** (con su humedad operativa). La humedad terminaba descontándose dos veces y la energía quedaba subestimada ≈ 23 % (factor 0,88² ≈ 0,77).

Cadena corregida:

| Paso | Fórmula |
|---|---|
| Masa seca | `masa_seca_kg = Residuo Recuperable × 1000` |
| Masa alimentada | `masa_alimentada_kg = masa_seca_kg / (1 − H/100)` |
| Energía | `kwh_generados = masa_alimentada_kg / CE` |
| Horas | `horas = kWh / P_nom` |
| Equipos | `equipos_pp30_equivalentes = horas / (8760 × disponibilidad)` |

Rendimiento implícito: ≈ 1.033 kWh por t MS. Se agregaron validaciones de `P_nom > 0` y de la disponibilidad, y la nueva métrica `equipos_pp30_equivalentes` (con disponibilidad 0,8 ≈ 7.000 h/año), que da escala física al resultado.

### E4 — Suma de 57 campañas

**Archivos nuevos**: `etl/transformers/reference_period.py`; notebook §4.6; dashboard.

Los gráficos del notebook ("Residuo de biomasa total por provincia/cultivo", "Top 30") sumaban **todas** las campañas desde 1969/70: un número sin significado físico, que además favorecía a los departamentos con series más largas. El kWh y el dinero son **flujos anuales**. Además la campaña 2025/26 tiene 1.468 registros contra ~3.100 de las anteriores: está incompleta.

**Corrección**:
- `detect_incomplete_campaigns`: una campaña final es incompleta si tiene menos del 80 % de la mediana de registros de las 5 anteriores (hoy: 2025/26).
- `select_reference_campaigns`: últimas N (= 5) campañas completas → **2020/21 a 2024/25**.
- `annualize`: promedio anual = suma en el período / N. No se usa `mean` del `groupby` porque ignoraría los años sin siembra y sobrerrepresentaría a los cultivos esporádicos.
- El ETL genera un nuevo artefacto **`data/processed/potencial_energetico_anual.parquet`** (por provincia × departamento × cultivo, con energía y dinero anuales).
- Los KPIs del dashboard se muestran como promedio anual y las campañas por defecto excluyen la incompleta.

### E12 — Tarifa de Buenos Aires

`buenos aires → EDENOR_AMBA`: EDENOR sólo abastece al AMBA norte/oeste. Los departamentos agrícolas bonaerenses (que aportan ~34 % de la energía) los atienden EDEN, EDEA, EDES y cooperativas, con cuadros OCEBA distintos. Se marcó `es_proxy: true` y se propaga a la columna `tarifa_es_proxy` para no mezclar resultados aproximados con valores firmes. Las provincias sin distribuidora quedan con montos `NaN` (se informa en el log), sin imputar.

---

## 5. Notebook `notebooks/main.ipynb`

Se mantuvo la estructura narrativa (Exploración → Conclusiones → Desarrollo → Pruebas) y cada celda nueva o modificada tiene su texto explicativo.

**Correcciones en celdas existentes**:

| Celda / sección | Error | Corrección |
|---|---|---|
| Imports | `import geopandas` (no está en requirements) rompía la ejecución; `plotly` sin usar | Eliminados; se agrega la raíz del repo a `sys.path` para usar los módulos del ETL |
| 1.1 Ingesta | Rutas fijas `datos_*.csv`: ignoraba los raw timestamped más recientes | `find_latest_raw` |
| 1.5 (nueva) | — | Diagnóstico de filas replicadas en CBA, celdas `SD` y campañas |
| 1.6 Conclusiones | — | Nuevos hallazgos H8–H12 |
| Fase 2 | — | Nuevas acciones A9–A13 y criterio de desempate |
| 3.5 Limpieza CBA | `dropna` global y sin deduplicar | A9 + `dropna` por columnas requeridas |
| 3.9 Agrupación | `sum` convertía faltantes en 0; rendimiento `inf` | `sum(min_count=1)`; rendimiento `NaN` si superficie = 0 |
| 3.10 Reconciliación | Empate no determinístico | Orden estable con prioridad MAGYP |
| 3.11 Biomasa | Sin MS; `_valido_biomasa` no exigía IC ni superficie > 0 (distinto del ETL) | Residuo en base seca; flags idénticos al ETL |
| 4.1 Tests | — | Tests de deduplicación y `min_count` |
| 4.2 Invariantes | Fallaban con NaN legítimos | Comparación tolerante a NaN |
| 4.4 Impacto | Listaba como "excluidos" a todos los cultivos con *algún* registro inválido (maíz, soja, …) | Se separan los cultivos sin IC (17) de los registros con superficie/rendimiento inválido |
| 4.6 Gráficos | Sumaban 57 campañas | Promedio anual del período de referencia; eficiencia por ha ponderada por superficie |
| Persistencia | `cmp` con columnas MultiIndex (parquet falla con nombres no-str); pisaba los artefactos del ETL | Columnas aplanadas; archivos `*_notebook.parquet` para no sobrescribir los del pipeline |

**Fases nuevas**:

- **Fase 5 — Conversión de biomasa residual a energía**: parámetros PP30 leídos del JSON de referencia; cadena de cálculo explicada paso a paso; energía por provincia y cultivo; sensibilidad a fracción recuperable, humedad y consumo específico. Incluye una verificación (`assert`) de que el resultado es **idéntico** al del módulo `etl/transformers/energy_finance.py`.
- **Fase 6 — Valorización económica**: tabla de tarifas con su **origen** (`parsed_pdf` / `fallback_previous` / `baseline_manual`) y aviso si no están verificadas; asignación provincia → distribuidora; ahorro por autoconsumo + crédito por inyección (Ley 27.424); resumen por provincia (GWh, MM ARS, ARS/kWh, ARS/t residuo, equipos PP30); top 15 departamentos; sensibilidad al autoconsumo α; y alcance de los montos (beneficio bruto, sin CAPEX, O&M, flete ni impuestos). También verifica la igualdad con el módulo del ETL.

Resultados con los datos actuales (período 2020/21–2024/25, parámetros por defecto):

| Magnitud | Valor |
|---|---|
| Residuo total | 154,2 M t MS/año |
| Residuo recuperable (50 %) | 77,1 M t MS/año |
| Energía técnica | 79,6 TWh/año (≈ 455 mil equipos PP30) |
| Energía con tarifa asignada | 74,4 % (Córdoba, Santa Fe, Buenos Aires*) |
| Beneficio bruto | ≈ 6,0 billones ARS/año (**ilustrativo**: tarifas `baseline_manual`) |

\* Buenos Aires con tarifa aproximada (`es_proxy`).

El notebook se ejecutó de principio a fin con `nbclient` y se guardó con sus outputs.

---

## 6. Pipeline (`etl/pipelines/run_etl.py`)

- Nueva etapa de tarifas (no bloqueante: si falla, usa el JSON previo). Flags nuevos: `--skip-tarifas`, `--n-campanas`, `--fraccion-recuperable`; `--tarifas` pasa a ser opcional.
- El JSON de tarifas se carga una sola vez y se reutiliza.
- Orden: extracción → limpieza → reconciliación + discrepancias → biomasa (MS) → flags → residuo recuperable → energía/finanzas por campaña → **anualización** → validaciones → persistencia (`biomasa_validos`, `potencial_energetico_anual`, descartados, discrepancias).

---

## 7. Verificación

- `pytest`: **51 tests OK** (32 previos + 19 nuevos en `tests/test_etl_fixes.py` y `tests/test_energy_tarifas.py`).
- `python -m etl.pipelines.run_etl --skip-extract --skip-tarifas`: corre completo y elimina 30 filas replicadas de CBA. Período detectado 2020/21–2024/25.
- `notebooks/main.ipynb`: ejecutado completo sin errores; se verificó la igualdad de los cálculos con el ETL.
- Dashboard: las tres páginas se renderizan sin excepciones (`streamlit.testing.AppTest`).
- **No verificado**: la extracción online de CBA, MAGYP y tarifas (la red del entorno bloquea esos dominios).

---

## 8. Pendientes y recomendaciones

1. **Correr el scraper de tarifas con acceso a red** y revisar `estado_campos` / `valores_detectados` por distribuidora. Ajustar los patrones de sección si algún cuadro no se reconoce.
2. **Revisar el baseline de tarifas** (210 ARS/kWh en EPEC frente a ≈ 54 ARS/kWh publicado para T2 en sep-2025).
3. Incorporar cuadros de **EDEN/EDEA/EDES (OCEBA)** para Buenos Aires y de las provincias sin tarifa (Entre Ríos, La Pampa, Santiago del Estero, Salta, Chaco, …), que concentran ~26 % de la energía.
4. **Trigo candeal** queda excluido por no tener IC; podría usar el IC de trigo pan (0,35–0,40) documentando el supuesto.
5. Diferenciar la **fracción recuperable por cultivo y sistema de labranza** (p. ej. menor en soja, cuyo rastrojo es escaso y frágil).
6. Para la evaluación económica, incorporar costos de recolección/enfardado/flete, CAPEX y O&M del PP30, e impuestos.
7. `docs/` está en `.gitignore` aunque sus archivos están versionados: los documentos nuevos en esa carpeta requieren `git add -f`.

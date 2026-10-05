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
| — | Mejora | Tarifas | Sólo 4 distribuidoras; sin historial | 28 distribuidoras + historial (sección 9) |

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
3. ~~Incorporar el resto de las distribuidoras~~ → hecho (sección 9). Pendiente: cuadros de las cooperativas bonaerenses y pampeanas, y de Chubut.
4. **Trigo candeal** queda excluido por no tener IC; podría usar el IC de trigo pan (0,35–0,40) documentando el supuesto.
5. Diferenciar la **fracción recuperable por cultivo y sistema de labranza** (p. ej. menor en soja, cuyo rastrojo es escaso y frágil).
6. Para la evaluación económica, incorporar costos de recolección/enfardado/flete, CAPEX y O&M del PP30, e impuestos.
7. `docs/` está en `.gitignore` aunque sus archivos están versionados: los documentos nuevos en esa carpeta requieren `git add -f`.

---

## 9. Ampliación: todas las distribuidoras e historial de tarifas

### 9.1 Cobertura

El extractor pasó de 4 a **28 distribuidoras** (todas las jurisdicciones de la lista provista; las provincias con más de una distribuidora tienen una entrada por cada una). El registro vive en `etl/reference/distribuidoras.py` y es la única fuente de verdad: agregar o corregir una URL no requiere tocar código.

Para cada distribuidora hay dos tipos de fuente, que se prueban en este orden:

1. **Portal nacional de la Secretaría de Energía** (`argentina.gob.ar/.../cuadros-tarifarios-<slug>`). Publica los cuadros **mensuales de todas las distribuidoras desde 2025** en un formato uniforme, y los archivos tienen una URL predecible: `energia.gob.ar/.../cuadros_tarifarios_desde_2025/<DIR>/<AAAA>_<MM>_<DIR>.<pdf|xlsx|zip>`. Es la fuente preferida y la que permite reconstruir el historial.
2. **Fuente propia** de la distribuidora o de su ente regulador: páginas índice (OCEBA para EDEN/EDEA/EDES/EDELAP, EPRE Mendoza para EDEMSA/EDESTE, etc.), URLs directas (p. ej. EDESAL, EDESE, EDELAR) y plantillas mensuales (EDENOR, EDESA, EDEA).

Si ambas fuentes responden, se usa el cuadro de **vigencia más reciente**.

| Código | Jurisdicción | Portal nacional | Fuente propia |
|---|---|---|---|
| EDENOR | CABA (norte) y GBA norte/oeste | [`edenor`](https://www.argentina.gob.ar/economia/energia/energia-electrica/estadisticas/cuadros-tarifarios-edenor) | www.edenor.com |
| EDESUR | CABA (sur) y GBA sur | [`edesur`](https://www.argentina.gob.ar/economia/energia/energia-electrica/estadisticas/cuadros-tarifarios-edesur) | www.edesur.com.ar |
| EDELAP | Buenos Aires (Gran La Plata) | [`edelap`](https://www.argentina.gob.ar/economia/energia/energia-electrica/estadisticas/cuadros-tarifarios-edelap) | oceba.gba.gov.ar |
| EDEA | Buenos Aires (Costa Atlántica) | [`edea`](https://www.argentina.gob.ar/economia/energia/energia-electrica/estadisticas/cuadros-tarifarios-edea) | oceba.gba.gov.ar, www.edeaweb.com.ar |
| EDEN | Buenos Aires (norte y centro) | [`eden`](https://www.argentina.gob.ar/economia/energia/energia-electrica/estadisticas/cuadros-tarifarios-eden) | oceba.gba.gov.ar |
| EDES | Buenos Aires (sur) | [`edessa`](https://www.argentina.gob.ar/economia/energia/energia-electrica/estadisticas/cuadros-tarifarios-edessa) | oceba.gba.gov.ar |
| ECSAPEM | Catamarca | [`ecsapem`](https://www.argentina.gob.ar/economia/energia/energia-electrica/estadisticas/cuadros-tarifarios-ecsapem) | www.ecsapem.com.ar |
| SECHEEP | Chaco | [`secheep`](https://www.argentina.gob.ar/economia/energia/energia-electrica/estadisticas/cuadros-tarifarios-secheep) | www.secheep.gob.ar |
| EPEC | Córdoba | [`epec`](https://www.argentina.gob.ar/economia/energia/energia-electrica/estadisticas/cuadros-tarifarios-epec) | www.epec.com.ar |
| DPEC | Corrientes | [`dpec`](https://www.argentina.gob.ar/economia/energia/energia-electrica/estadisticas/cuadros-tarifarios-dpec) | www.dpec.com.ar |
| ENERSA | Entre Ríos | [`enersa`](https://www.argentina.gob.ar/economia/energia/energia-electrica/estadisticas/cuadros-tarifarios-enersa) | www.enersa.com.ar, epre.gov.ar |
| REFSA | Formosa | [`refsa`](https://www.argentina.gob.ar/economia/energia/energia-electrica/estadisticas/cuadros-tarifarios-refsa) | recursosyenergia.com.ar |
| EJESA | Jujuy | [`ejesa`](https://www.argentina.gob.ar/economia/energia/energia-electrica/estadisticas/cuadros-tarifarios-ejesa) | www.ejesa.com.ar, susepu.jujuy.gob.ar |
| APE | La Pampa | [`ape`](https://www.argentina.gob.ar/economia/energia/energia-electrica/estadisticas/cuadros-tarifarios-ape) | — |
| EDELAR | La Rioja | [`edelar`](https://www.argentina.gob.ar/economia/energia/energia-electrica/estadisticas/cuadros-tarifarios-edelar) | www.edelar.com.ar |
| EDEMSA | Mendoza (salvo zona este) | [`edemsa`](https://www.argentina.gob.ar/economia/energia/energia-electrica/estadisticas/cuadros-tarifarios-edemsa) | www.edemsa.com, epremendoza.gob.ar |
| EDESTE | Mendoza (zona este) | [`edeste`](https://www.argentina.gob.ar/economia/energia/energia-electrica/estadisticas/cuadros-tarifarios-edeste) | epremendoza.gob.ar |
| EMSA | Misiones | [`emsa`](https://www.argentina.gob.ar/economia/energia/energia-electrica/estadisticas/cuadros-tarifarios-emsa) | energia.misiones.gob.ar, www.energiademisiones.com.ar |
| EPEN | Neuquén | [`epen`](https://www.argentina.gob.ar/economia/energia/energia-electrica/estadisticas/cuadros-tarifarios-epen) | www.epen.gov.ar |
| EDERSA | Río Negro | [`edersa`](https://www.argentina.gob.ar/economia/energia/energia-electrica/estadisticas/cuadros-tarifarios-edersa) | www.edersa.com.ar, www.eprern.gov.ar |
| EDESA | Salta | [`edesa`](https://www.argentina.gob.ar/economia/energia/energia-electrica/estadisticas/cuadros-tarifarios-edesa) | www.edesa.com.ar |
| ESJ | San Juan | [`esj`](https://www.argentina.gob.ar/economia/energia/energia-electrica/estadisticas/cuadros-tarifarios-esj) | epresanjuan.gob.ar |
| EDESAL | San Luis | [`edesal-sa`](https://www.argentina.gob.ar/economia/energia/energia-electrica/estadisticas/cuadros-tarifarios-edesal-sa) | oficinavirtualedesal.com.ar |
| SPSE | Santa Cruz | [`spse`](https://www.argentina.gob.ar/economia/energia/energia-electrica/estadisticas/cuadros-tarifarios-spse) | spse.ar |
| EPE | Santa Fe | [`epe`](https://www.argentina.gob.ar/economia/energia/energia-electrica/estadisticas/cuadros-tarifarios-epe) | www.epe.santafe.gov.ar |
| EDESE | Santiago del Estero | [`edese`](https://www.argentina.gob.ar/economia/energia/energia-electrica/estadisticas/cuadros-tarifarios-edese) | www.edese.com.ar |
| DPE_TDF | Tierra del Fuego | [`dpe`](https://www.argentina.gob.ar/economia/energia/energia-electrica/estadisticas/cuadros-tarifarios-dpe) | www.dpe.com.ar |
| EDET | Tucumán | [`edet`](https://www.argentina.gob.ar/economia/energia/energia-electrica/estadisticas/cuadros-tarifarios-edet) | www.edetsa.com |


Los slugs nacionales `eden`, `refsa`, `ejesa` y `esj` no aparecieron en las búsquedas (sí figuran esas distribuidoras en el índice general del portal) y son la mejor estimación; si fallan, el extractor sigue con la fuente propia.

### 9.2 Formatos y parseo

- Nuevo módulo `etl/extractors/tariff_documents.py`: detecta el formato por firma binaria (PDF, XLSX, XLS, ZIP; un HTML de error con HTTP 200 se descarta) y convierte el documento a texto. En planillas, cuando la unidad (`$/kWh`, `$/mes`) está en el encabezado de la columna, se propaga a cada importe de esa columna para que el parser la reconozca igual que en un PDF. Un ZIP se procesa archivo por archivo.
- El parser ahora **empareja cada importe con su unidad** (`$/kWh 70,12` o `70,12 $/kWh`). Antes tomaba el último número de la línea y en una fila de planilla con cargo fijo y variable podía confundirlos.
- La sección de compra termina donde empieza la de usuario-generador, para no mezclar precios de compra e inyección.
- **Vigencia** de cada cuadro (AAAA-MM): se obtiene del nombre del archivo (`2026_04_DPEC.pdf`, `2026-01`, `Marzo_2026`, `…aplicacion-010925`) o del texto ("vigencia a partir del 1° de septiembre de 2026", "Periodo: OCTUBRE 2025").
- La validación ya **no rechaza un valor real por diferir de un baseline manual** (sólo compara contra valores extraídos antes).
- Si un host no responde (error de conexión), se omite el resto de sus URLs en esa corrida, para evitar cientos de timeouts.

### 9.3 Historial de cambios

Nuevo archivo `data/reference/tarifas_historial.csv` (módulo `etl/loaders/tariff_history.py`), append-only y versionado en git:

| Columna | Contenido |
|---|---|
| `distribuidora`, `vigencia` | Código y mes de vigencia del cuadro. |
| `tarifa_compra_kwh`, `tarifa_inyeccion_kwh`, `cargo_fijo_mensual` | Valores extraídos. |
| `seccion_compra`, `n_valores_*` | Sección usada y cantidad de importes detectados (auditoría del parseo). |
| `fuente_tipo`, `documento`, `sha256`, `fecha_extraccion` | Trazabilidad del documento. |

Cada documento se registra una sola vez (clave `distribuidora + sha256`), así que correr el extractor todos los días no duplica filas: sólo aparecen filas nuevas cuando se publica un cuadro nuevo. Para reconstruir la serie completa desde 2025:

```bash
python -m etl.extractors.scrape_tarifas --historial --desde 2025-01
python -m etl.extractors.scrape_tarifas --solo EPEC EDESAL    # sólo algunas
```

`load_history`, `latest_by_distribuidora` y `tariff_series` permiten consultarlo. El notebook muestra la evolución en la nueva sección 6.6. Además, cada corrida sigue dejando su JSON timestamped `AAAAMMDDHHMMSS_tarifas.json`.

### 9.4 Asignación de tarifas a los datos agrícolas

`TariffResolver` (en `energy_finance.py`, usado por el ETL y el notebook):

1. **Excepción por departamento**: zona este de Mendoza → EDESTE (San Martín, Junín, Rivadavia, Santa Rosa, La Paz); Gran La Plata → EDELAP (La Plata, Berisso, Ensenada, Brandsen, Magdalena, Punta Indio).
2. **Distribuidora de la provincia**. Interior bonaerense: promedio de EDEN, EDEA y EDES (marcado `tarifa_es_proxy`, ya que además hay unas 200 cooperativas). La Pampa (APE) también queda marcada como aproximada por el peso de las cooperativas.
3. **Chubut** no tiene distribuidora provincial (cooperativas): sin tarifa.

Nueva columna **`tarifa_origen`** en los datasets (`extraido`, `fallback_previous`, `baseline_manual` o `sin_dato`), para separar los montos basados en tarifas reales de los ilustrativos. En el notebook, `SOLO_TARIFAS_EXTRAIDAS = True` excluye los valores `baseline_manual`.

Se eliminó el mapeo anterior `buenos aires → EDENOR`: hoy Buenos Aires queda `sin_dato` hasta que se extraigan las tarifas de EDEN/EDEA/EDES, en lugar de usar una tarifa de otra área de concesión.

### 9.5 Estado actual y verificación

- Tests: **65 OK**. Incluyen tests de punta a punta con XLSX y ZIP reales generados en el test, backfill de historial con dos meses, deduplicación en una segunda corrida, selección de la vigencia más reciente, filtro de índices compartidos (OCEBA), resolver con promedio y excepción departamental, y el corte por host caído.
- También se probó a mano el recorrido real PDF → `pypdf` → parser con un PDF generado.
- **No se pudo descargar ningún cuadro real**: el proxy de este entorno responde 403 a todos los dominios de distribuidoras, entes y `argentina.gob.ar` / `energia.gob.ar`. El JSON vigente (`20261004143428_tarifas.json`) tiene 4 distribuidoras con `baseline_manual` (EPEC, EPE, EDEMSA, EDENOR) y 24 con `sin_dato`, y el historial está vacío. El primer paso al tener red es:

```bash
python -m etl.extractors.scrape_tarifas --historial --desde 2025-01
```

y luego revisar en el JSON `resumen_extraccion`, y por distribuidora `estado_campos`, `seccion_compra` y `valores_detectados`. Si algún formato real no matchea, ajustar `SECTION_PATTERNS_COMPRA` / `SECTION_PATTERNS_INYECCION` o la entrada del registro.

---

## 10. Validación contra las fuentes reales (con red habilitada)

Con la lista de dominios habilitada se ejecutaron todos los extractores contra los sitios reales. Aparecieron errores que no se veían con datos sintéticos.

### 10.1 Extractores agrícolas

| Fuente | Resultado | Error encontrado | Corrección |
|---|---|---|---|
| MAGyP (estimaciones) | ✅ 539/539 departamentos, 0 fallos, 162.297 filas | — | — |
| Bolsa de Cereales de Córdoba | ✅ 4.064 filas (= raw del repo sin las 30 duplicadas) | El Excel pasó a `.xls` y las tres hojas traen ahora 10 filas de título. El extractor (fila de encabezado fija y sin encabezado en dos hojas) fallaba con `KeyError: 'PROVINCIA'` | Se detecta la fila de encabezado buscando `PROVINCIA` en cada hoja; se aceptan `.xls` y `.xlsx`; columnas numéricas convertidas |
| Bolsa de Cereales de Bs. As. | ❌ HTTP 403 (desafío anti-bot de Cloudflare) | Bloqueo de IPs de datacenter | Sin cambios: no se evade un anti-bot y el dataset está descartado metodológicamente (zonas PAS) |
| Pipeline | — | Un extractor caído abortaba todo el ETL | `run_extract_stage` usa el raw más reciente en disco de esa fuente y lo registra en el log |

La descarga nueva de MAGyP pasa la limpieza sin cambios de esquema ni cultivos sin mapear. La campaña 2025/26 creció de 1.468 a 1.724 registros y sigue detectándose como incompleta.

### 10.2 Tarifas: problemas de las fuentes reales

- **`energia.gob.ar` corta el handshake TLS** desde redes fuera de Argentina, pero sirve los mismos archivos por **HTTP**. Ese host se normaliza a HTTP.
- El portal nacional antepone `blank:#` a algunos enlaces. Se quita.
- Las carpetas reales son por **código de distribuidora** (`EDESAL/2026_06_EDESAL.xlsx`). Los enlaces viejos por provincia (`cordoba/2025_07_EPEC.pdf`) dan 404.
- Algunas páginas del portal quedaron desactualizadas y existe una **versión nueva con sufijo `-0`** (EPEC, ESJ, SPSE). El registro admite varias páginas por distribuidora.
- El portal **enlaza archivos inexistentes** (p. ej. `EPEC/2026_06_EPEC.pdf` da 404) y **de otra distribuidora** (la página de EDET apuntaba a un cuadro de EDESE). Se descartan los enlaces cuyo nombre no corresponde al código.
- Para EDEN, EDEA, EDES y EDELAP el portal nacional **sólo publica componentes** (CTT, cargos de transporte), no el cuadro final. Se usa **OCEBA** y se descarta un PDF combinado "EDEA-EDEN-EDES" que se asignaba a las tres.
- OCEBA publica **varios anexos por mes** (pleno, con subsidio, por nivel de ingresos). Se procesan todos los del mes más reciente y se elige el de mejor categoría y mayor tarifa, es decir, el cuadro pleno.
- Los ZIP del portal mezclan el cuadro pleno con regímenes especiales ("Clubes de Barrio", "Subsidio del Estado Nacional") y con una hoja de **tarifas de inyección**. Los cuadros especiales se identifican por el título y se excluyen como compra; la hoja de inyección aporta el precio de inyección.
- El nombre del archivo puede indicar el mes de publicación y no el de vigencia (`2026_07_EDENOR 1.xlsx` con "vigencia a partir del 1° de junio de 2026"). Prevalece la **vigencia declarada en el texto**. Las carpetas de OCEBA `ctAAAAMM[DD]` también se interpretan.
- **Rate limiting y cortes**: un intervalo mínimo de 1 s por host, un reintento ante 403/429/503 o error de conexión, y los hosts con 403 o errores de conexión sostenidos se omiten en la corrida (EDENOR propio, `spse.ar`).
- `EPEC` (sitio propio) responde 403 desde fuera de Argentina, y su archivo del portal nacional está roto. Desde una red argentina debería funcionar la fuente propia.

### 10.3 Parser reescrito (`etl/extractors/tariff_parser.py`)

El parser por secciones "T2/T3" fallaba con los cuadros reales: cada distribuidora organiza filas, columnas (abastecimiento/VAD/total, con/sin subsidio) y unidades a su manera. Se reemplazó por un **puntaje de líneas candidatas**, validado contra 20+ cuadros reales:

- Candidatas: líneas con cargo en $/kWh, con la unidad en la línea, propagada desde el encabezado de la columna, o en la línea anterior para filas de banda horaria, cuyo contexto nombra medianas o grandes demandas, T2/T3 o baja tensión.
- Se prioriza la **banda "Resto"** (también `restantes`, `(R)` o `®` en PDFs).
- Se excluyen las líneas residenciales, sociales, subsidiadas, de VAD o costo de compra, peaje, alumbrado, media o alta tensión (incluidos 13,2/33/132 kV y "Vinculación superior") y las categorías de ≥ 300 kW, que no representan a un PP30 de 25 kW.
- Se exige un puntaje mínimo de medianas demandas: un PDF con la tabla desarmada (EDEMSA propio) ya no devuelve una tarifa residencial.
- **Formato numérico inglés** (`156.655`, `662,591.7` en EDESE) detectado por documento.
- Tablas lado a lado en la misma línea de PDF: se corta en la próxima etiqueta.
- Líneas sin etiqueta (`$/kWh 92,94`) toman el concepto de las líneas previas. Así, en EDELAR el precio de inyección no se confunde con la compra.
- Tablas cuyo encabezado es "Tarifa de inyección" (APE) no se usan como compra.
- Las líneas usadas quedan registradas (`lineas_compra`, `lineas_inyeccion`) para auditar.
- **Bloques de distribuidores municipales (OCEBA)**: en los cuadros de EDEN, EDEA y EDES, el bloque T3 BT trae primero la tarifa **mayorista** que la distribuidora cobra a las cooperativas ("DISTRIBUIDORES MUNICIPALES (...)") y después la de **usuarios finales**. El parser tomaba la mayorista: 114,98 $/kWh en lugar de 135,05 para EDEN en 2026-09, una subestimación de ~15 % en la provincia con más energía. Ahora se descarta toda línea cuyo encabezado de bloque más cercano es de distribuidores municipales, y "entre 50 y 300 kW" puntúa como grandes demandas en BT.
- **Columnas BT/MT en paralelo** (ECSAPEM): con encabezado "Baja Tensión | Media Tensión" se toma la mitad de baja tensión. Antes se promediaban ambas (101,45 en lugar de 106,29).
- **Filas de inyección**: una fila "Cargo variable por energía inyectada | $/kWh | …" marcaba como inyección las filas T2/T3 que la seguían. Ahora sólo cuentan como encabezado de tabla de inyección las líneas sin importes.
- **Importes partidos por el PDF** ("104,10 37", "9 ,0896") se reúnen; antes daban 104,10 y 896 $/kWh.
- **Cantidades de energía** ("hasta 800 kWh mes $/kWh", EDEMSA 2025-09) ya no se leen como precio (daba 800 $/kWh).
- **Fecha de carpetas OCEBA** `cuadros-tarifarios/AAAA/mes/`: no se reconocía, y el filtro `--desde` descargaba los cuadros de 2020–2024.

Cada corrección se verificó volviendo a parsear los ~1.800 documentos descargados y comparando antes/después: sólo cambiaron los de la distribuidora afectada.

### 10.4 Resultado final por distribuidora (corrida del 2026-10-04)

`data/reference/20261004214915_tarifas.json`. Tarifa de compra en ARS/kWh sin impuestos, categoría de medianas/grandes demandas en BT, banda "Resto".

| Distribuidora | Provincia | Compra | Inyección | Vigencia | Fuente | Estado |
|---|---|---:|---:|---|---|---|
| EDENOR | CABA / GBA | 108,37 | — | 2026-06 | Portal nacional (ZIP) | extraído |
| EDESUR | CABA / GBA | 107,91 | — | 2026-05 | Portal nacional (ZIP) | extraído |
| EDEN | Buenos Aires | 135,23 | — | 2026-09 | OCEBA | extraído |
| EDEA | Buenos Aires | 136,44 | — | 2026-09 | OCEBA | extraído |
| EDES | Buenos Aires | 137,18 | — | 2026-09 | OCEBA | extraído |
| EDELAP | Buenos Aires (Gran La Plata) | 148,72 | — | 2026-09 | OCEBA | extraído |
| ECSAPEM | Catamarca | 106,29 | rechazada¹ | 2026-05 | Portal nacional | extraído |
| SECHEEP | Chaco | 117,50 | 89,99 | 2026-06 | Portal nacional | extraído |
| DPEC | Corrientes | 109,20 | — | 2026-04 | Portal nacional | extraído |
| ENERSA | Entre Ríos | 130,84 | 93,55 | 2026-05 | Portal nacional | extraído |
| REFSA | Formosa | 135,28 | — | 2026-06 | Sitio propio | extraído |
| EJESA | Jujuy | 113,09 | — | 2025-10 | Portal nacional | valor anterior² |
| EDELAR | La Rioja | 104,67 | 78,67 | 2026-03 | Portal nacional | extraído |
| EDEMSA | Mendoza | 106,51 | — | 2026-05 | Portal nacional | extraído |
| EDESTE | Mendoza (este) | 106,51 | — | 2026-05 | Portal nacional | extraído |
| EPEN | Neuquén | 359,73 | — | 2026-08 | Sitio propio | extraído³ |
| EDERSA | Río Negro | 155,26 | rechazada¹ | 2026-09 | Sitio propio | extraído |
| EDESA | Salta | 266,81 | — | 2026-06 | Portal nacional | extraído³ |
| EDESAL | San Luis | 110,76 | — | 2026-06 | Portal nacional | extraído |
| EDESE | Santiago del Estero | 156,66 | — | 2026-09 | Sitio propio | extraído |
| EPEC | Córdoba | — | — | — | — | sin dato: sitio propio 403 desde fuera de Argentina; archivo del portal nacional roto (404) |
| EPE | Santa Fe | — | — | — | — | sin dato: los cuadros se bajan de `epe.santafe.gov.ar/institucional-api/` (dominio sin `www`), bloqueado por el proxy |
| APE | La Pampa | — | — | — | — | sin dato: publica sólo la composición del precio |
| EMSA | Misiones | — | — | — | — | sin dato: sólo cuadros de MT / ≥ 300 kW por bandas horarias |
| ESJ | San Juan | — | — | — | — | sin dato: las páginas del portal nacional (`-esj`, `-esj-0`) no enlazan archivos y el EPRE sólo publica un PDF de subsidios |
| SPSE | Santa Cruz | — | — | — | — | sin dato: el portal nacional no enlaza archivos y `spse.ar` no responde (host omitido por fallas sostenidas) |
| DPE_TDF | Tierra del Fuego | — | — | — | — | sin dato: el único documento es una resolución escaneada (Res. DPE 559/2025) cuyo texto OCR embebido es ilegible |
| EDET | Tucumán | — | — | — | — | sin dato: PDFs escaneados (imagen, sin texto) |

¹ La inyección detectada supera la tarifa de compra y la validación la descarta. En EDERSA es una mediana de categorías distintas (residencial 63, excedente 148, general 173); en ECSAPEM corresponde al régimen de generación distribuida (Res. D.P. 169-26), que remunera la energía inyectada por encima del precio T2. Asociar la inyección a la misma categoría que la compra queda pendiente.
² La página del portal nacional de EJESA (`cuadros-tarifarios-ejesa`) devolvía 404 el día de la corrida. Se conserva el último valor extraído (`fallback_previous`).
³ Valores altos verificados contra el documento: EPEN (T2 > 10 kW, cuadro de consumos de agosto) y EDESA (T3 > 50 kW).

**Cobertura**: con el período de referencia 2020/21–2024/25 (7,96·10¹⁰ kWh/año), el **53,7 %** de la energía tiene tarifa real y el 0,1 % (Jujuy) usa el valor anterior. Sin tarifa: Córdoba (26,1 %), Santa Fe (14,4 %), La Pampa (5,0 %), Tucumán (0,7 %) y Misiones (0,1 %).

### 10.5 Historial

`data/reference/tarifas_historial.csv` tiene 850 cuadros desde enero de 2025 (`--historial --desde 2025-01`). Las filas se recalcularon con el parser final a partir de los documentos descargados. La serie mensual de cuadros plenos (`tariff_series`) ya no muestra los saltos espurios de las versiones anteriores (EDEMSA 800 $/kWh en 2025-09; EDEN/EDEA/EDES ~33 $/kWh en 2025-09 por la tarifa mayorista).

### 10.6 Fuentes bloqueadas: dominios y carga manual

- **EPE (Santa Fe)**: la página `www.epe.santafe.gov.ar/institucional/grandes-usuarios/` (Astro) no tiene enlaces `<a>`. Los cuadros (`CUT_T2_Septiembre_2026.pdf`, …) vienen en las propiedades serializadas `fileName`/`fileHash` y se descargan con `GET https://epe.santafe.gov.ar/institucional-api/download/<uuid>` y la cabecera `x-api-key`. Esa clave es pública: está en el JavaScript del propio sitio y se puede reemplazar con la variable `EPE_API_KEY`. El extractor ya descubre los cuadros, pero para descargarlos hay que **habilitar `epe.santafe.gov.ar`** (sin `www`) en la lista de dominios.
- **Carga manual**: para fuentes que bloquean la descarga automática (EPEC, ESJ, SPSE, DPE), se puede dejar el cuadro descargado a mano en `data/reference/cuadros_manuales/<CÓDIGO>/` (PDF, XLSX o ZIP). El extractor lo procesa como cualquier otro documento (`fuente_tipo = "manual"`) y lo registra en el historial. Conviene incluir la fecha en el nombre (`cuadro_2026_09.pdf`) para que la vigencia se reconozca aunque el texto no la declare.

### 10.7 Otros errores encontrados

- `notebooks/main.ipynb` en `main` tenía **marcadores de conflicto de merge sin resolver** (`<<<<<<< HEAD` en un `execution_count`, del merge `f0c74a1`). El archivo no era JSON válido y Jupyter no lo abría. Se resolvió y el notebook se reejecutó completo sin errores.

---

## 11. Segunda ronda: tarifas restantes, dashboard y documentación (2026-10-05)

### 11.1 Tarifas

Con `epe.santafe.gov.ar` habilitado se probó de nuevo cada distribuidora sin dato.

| Distribuidora | Antes | Ahora | Qué se hizo |
|---|---|---|---|
| EPE (Santa Fe) | sin dato | **146,77 $/kWh** (2026-09) | Los cuadros `CUT_T2/T4/T6` se descargan por la API del sitio. La tensión sólo figura en el código de fila ("2 B1" = baja tensión, < 300 kW), así que la fila se fija en el registro (`fila_tarifa`), con la banda Resto de las columnas Pico/Resto/Valle. |
| APE (La Pampa) | sin dato | **169,40 $/kWh** (2025-12) | El cuadro separa costo de compra de energía y VAD. Un PP30 en autoconsumo es T2I (> 4000 kWh/mes, < 50 kW): compra 110,87 + VAD del excedente 58,53. `fila_tarifa` admite ahora un ancla de categoría y la suma de componentes. |
| EMSA (Misiones) | sin dato | **204,06 $/kWh** (2025-09) | No hay categoría por demanda en BT: se toma el cargo de energía de industrial 3.b (> 4000 kWh/mes) del "CT Pleno". El "Proyecto de cuadro … de referencia" del mismo ZIP se trata como documento no vigente. Vigencia "a partir del Período 09/2025" reconocida. |
| EPEC (Córdoba) | sin dato | sin dato | El sitio propio responde 403 y el portal nacional no tiene ningún archivo de EPEC (se probaron todos los meses de 2025–2026). El ente regulador (`ersep.cba.gov.ar`) está bloqueado por el proxy. Queda la carga manual. |
| ESJ (San Juan), SPSE (Santa Cruz) | sin dato | sin dato | El portal nacional enlaza `2026_06_ESJ.pdf` y `2026_06_SPSE.xlsx`, pero ambos dan 404. Los sitios propios (`energiasanjuan.com.ar`, `spse.gob.ar`) están bloqueados por el proxy. |
| EDET (Tucumán) | sin dato | sin dato | Tanto el portal nacional como el sitio propio publican PDF **escaneados** (sin capa de texto, 15–20 MB). Requeriría OCR, una dependencia pesada para el 0,8 % de la energía. |
| DPE (Tierra del Fuego) | sin dato | sin dato | Resolución escaneada con OCR ilegible. Sin producción agrícola relevante. |
| EJESA (Jujuy) | valor anterior | valor anterior | La página del portal nacional sigue en 404. El sitio propio publica el cuadro vigente (Res. 297/2026), pero el PDF tiene la tabla en columnas que el texto extraído desordena. Queda el último valor (113,09; 0,1 % de la energía). |

Resultado: **22 de 28** distribuidoras con tarifa extraída (antes 19), 1 con valor anterior y 5 sin dato. La energía con tarifa pasó del **53,7 % al 73,0 %**; sólo quedan Córdoba (26,2 %) y Tucumán (0,8 %).

### 11.2 Errores metodológicos encontrados

- **El dinero sólo se calculaba en 2 provincias.** `beneficio = ahorro + crédito por inyección`, y el crédito era NaN donde la distribuidora no publica precio de inyección (19 de 22). El beneficio de esas provincias quedaba en NaN y se sumaba como cero. Ahora la tarifa de inyección faltante se estima como compra × ratio mediano observado (0,752: SECHEEP, ENERSA, EDELAR) y se marca en `tarifa_inyeccion_estimada` (65,5 % de la energía). Beneficio bruto anual: 6,8·10¹¹ → **7,54·10¹² ARS**.
- **Doble conteo por nombres de departamento.** La Bolsa de Córdoba también cubre San Luis y Santiago del Estero, pero escribe "libertador san martin" y "juan felipe ibarra" donde MAGyP dice "libertador general san martin" y "juan f ibarra". La reconciliación no los cruzaba y sumaba ambas fuentes (p.ej. maíz 2020/21 en Juan F. Ibarra: 450.549 t + 441.084 t). Se agregaron los alias (ETL y notebook) y se revisó que no haya otros pares (sólo había esos dos). Energía anual: 7,964·10¹⁰ → 7,934·10¹⁰ kWh.
- **Cron del scheduler mal formado.** `config/schedule.ini` tenía `0 6 * * *`, pero la imagen `mcuadros/ofelia:latest` (0.3.x) exige el campo de segundos, así que ese horario no significaba "todos los días a las 06:00". Ahora es `0 0 6 * * *`, válido en 0.3.x y 0.4.x.

### 11.3 Dashboard

Errores encontrados:

- **Fuera de Docker ninguna página funcionaba**: `make dashboard` daba `ModuleNotFoundError: No module named 'dashboard'` en todas las páginas. Docker fija `PYTHONPATH=/app` y lo ocultaba. Además, con una carpeta `pages/` Streamlit usa el modo multipágina anterior, que ejecuta cada página sin pasar por `app.py`. Las páginas pasan a `dashboard/vistas/` y se registran con `st.navigation` en `app.py`, que agrega la raíz del proyecto al `sys.path`. El orden del menú queda fijo, con la auditoría al final.
- **Provincias invisibles en el mapa**: el coroplético sólo dibujaba los polígonos con dato, y las provincias sin registros (Patagonia, Cuyo, CABA) desaparecían. Ahora una capa base dibuja todas las provincias y departamentos con contorno, en gris neutro si no tienen dato.
- **Departamentos sin colorear**: 45 de 505 no cruzaban con GADM. Las causas eran números escritos en letras en GADM ("VeinticincodeMayo"), nombres abreviados o truncados ("General Angel V. Peñaloza", "Coronel de Marina L. Rosales"), departamentos renombrados (Dr. Manuel Belgrano → Capital; Juan Martín de Pueyrredón → La Capital) y San Fernando partido en dos polígonos. Ahora faltan 26: 21 son registros "sin definir" de la fuente y 5 son departamentos sin polígono en GADM 4.1 (Lezama, Punta Indio, 2 de Abril, San Salvador y 9 de Julio de San Juan). Representan el 0,83 % de la biomasa y sí cuentan en los totales y en el mapa provincial.
- Las provincias y cultivos se mostraban en minúsculas (como los normaliza el ETL); ahora se capitalizan para mostrar.

Contenido nuevo:

| Página | Contenido |
|---|---|
| Resumen | Selector **biomasa / energía / dinero** para KPIs, rankings y mapas por provincia y departamento. |
| Energía | Energía anual, equipos PP30 equivalentes, autoconsumo vs. inyección por provincia, energía por cultivo, mapas y parámetros del cálculo. |
| Dinero | Beneficio bruto (ahorro + inyección) por provincia, mapas, tabla de tarifas por distribuidora (vigencia, fuente, estado, documento) e historial de tarifas. |
| Exploración | Se suman energía y beneficio a los KPIs, la serie por campaña y la tabla. Una magnitud por gráfico: antes se mezclaban biomasa y producción en un mismo eje. |
| Auditoría de datos (última) | Descartados y discrepancias (con histograma), estado de cada tarifa, energía sin tarifa, peso de la inyección estimada y de las tarifas promediadas, departamentos sin polígono y campañas incompletas. |

**¿Tiene sentido la auditoría?** Sí. El dinero depende de tres pasos con huecos conocidos: la reconciliación entre fuentes (3.298 registros descartados), tarifas que faltan o se estiman (27 % de la energía sin tarifa, 65 % con inyección estimada) y el cruce con los mapas. Sin esa página, quien lee el Resumen no ve qué parte de cada número es firme. Se agregaron las pestañas de tarifas, cobertura de mapas y campañas, que no existían.

**Verificación**: se levantó Streamlit y se recorrieron todas las páginas con un navegador headless (Playwright). Se probaron el selector de métrica, las pestañas de mapas y las de auditoría, sin excepciones. Los mapas se verificaron aparte, con la cartografía base servida localmente, porque este entorno bloquea `cdn.plot.ly`.

### 11.4 Documentación

- `README.md` reescrito. Se quitaron las instrucciones de Shaper y `.dashboard.sql` (no existen en el proyecto), las marcas `[reference:N]` sueltas, el árbol de carpetas desactualizado y el enlace a un `LICENSE` inexistente. Se agregaron energía y dinero, tarifas, páginas del dashboard, formato del cron y la lista de dominios necesarios.
- `docs/`: los diagramas eran Mermaid sin bloque de código y GitHub no los renderizaba. Se actualizaron con tarifas, energía, dinero, scheduler y navegación del dashboard (arquitectura, despliegue, flujo detallado, ciclo de vida, modelo de datos y secuencia). `decision_log.md` estaba envuelto en un bloque de código; se corrigió y se agregaron las decisiones POL-GEO-001, POL-PERIOD-001, POL-ENERGY-001, POL-TARIFF-001 y POL-TARIFF-002. `data_sources.md` suma la sección de cuadros tarifarios.
- `pyproject.toml`: Streamlit en el extra `dev` (los tests del dashboard lo importan) y URLs reales del repositorio.

### 11.5 Tests

111 tests:
- Parser: filas fijadas por registro (EPE, APE, EMSA) y "proyecto de cuadro".
- Vigencia: "Período 09/2025".
- Dinero: estimación de la inyección faltante.
- Geografía: alias entre fuentes.
- Dashboard: claves GADM, partidos en dos polígonos y nombres legibles.

---

## 12. Reintentos en la extracción (2026-10-05)

**Problema**: al correr el ETL, la descarga de la Bolsa de Cereales de Córdoba falló con `503 Service Unavailable` aunque el archivo estaba disponible: SharePoint responde 503 cuando limita pedidos. El pipeline pasaba directo al raw en disco.

**Causa**: la política de reintentos (`request_with_retry`, backoff exponencial ante 429/5xx) existía sólo dentro del extractor de MAGyP. La descarga de CBA hacía un único `httpx.get` + `raise_for_status()` desde su primera versión. No se quitó en estos cambios: nunca la tuvo.

**Corrección**:

- `etl/extractors/http_retry.py`: la política pasa a un módulo compartido y se amplía. Reintenta ante 429, 500, 502, 503 y 504 y también ante cortes de red (conexión rechazada o cortada, timeouts). Usa backoff exponencial de 2, 4, 8… s (tope 60 s), hasta 6 intentos, y respeta `Retry-After`. MAGyP y CBA la usan.
- `run_extract_stage`: si una fuente falla igual, se sigue con las demás y al final se hace una **segunda pasada** (tras 60 s) sobre las que fallaron. Recién si vuelve a fallar se usa el raw más reciente en disco.
- Tests: 503 con `Retry-After`, corte de red, error no reintentable (404), intentos agotados, segunda pasada que recupera la fuente y fallback al raw.

---

## 13. Dashboard con datos viejos después de correr el ETL (2026-10-05)

**Síntoma**: Resumen y Exploración fallaban con `KeyError: 'kwh_generados'`. Energía y Dinero pedían ejecutar el ETL, aunque ya se había ejecutado.

**Causas**:

1. **La imagen de Docker no se reconstruía.** `Run-Etl.ps1` y `make docker-etl` corrían `docker compose run` sobre la imagen existente. El código del ETL se copia dentro de la imagen (no es un volumen), así que se ejecutaba la versión del último `build`. Si esa versión era anterior a la etapa de energía y dinero, `biomasa_validos.parquet` quedaba sin `kwh_generados` y no se generaba `potencial_energetico_anual.parquet`. El dashboard, en cambio, monta `./dashboard` en vivo y sí tenía el código nuevo.
2. **La caché del dashboard no miraba los archivos.** `st.cache_data` guardaba el DataFrame (o el "archivo inexistente") la primera vez y no lo volvía a leer. Si el dashboard estaba abierto mientras corría el ETL, seguía mostrando los datos viejos hasta reiniciarlo.

**Corrección**:

- `Run-Etl.ps1` y `make docker-etl` hacen `docker compose --profile etl build etl_pipeline` antes de correr el ETL. Docker reutiliza las capas sin cambios, así que si el código no cambió el paso tarda segundos.
- La caché del dashboard se indexa por ruta y fecha de modificación: cuando el ETL reescribe un archivo, se vuelve a leer sin reiniciar Streamlit.
- Si `biomasa_validos.parquet` o el potencial anual no tienen las columnas de energía y dinero, la página explica que fueron generados por una versión anterior del ETL. Muestra la ruta, la fecha y los comandos para reconstruir la imagen, en lugar del `KeyError`.
- Inicio → "Archivos de datos" muestra la fecha de cada artefacto.
- Verificación: se reprodujo el caso con un Parquet sin columnas de energía y sin el potencial anual; aparecen los mensajes nuevos. Al restaurar los archivos, el mismo servidor de Streamlit mostró los datos nuevos sin reiniciarse. Se agregó un test de la caché.

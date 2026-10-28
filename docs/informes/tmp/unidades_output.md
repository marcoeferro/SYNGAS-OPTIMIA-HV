# Unidades de los datos del proyecto

> Inventario de trabajo para estandarizar unidades. Relevado sobre los
> archivos en `data/` y el código de `etl/` y `dashboard/` (27/10/2026).
> Al final hay una lista de inconsistencias para decidir el estándar.

## Convenciones generales

| Magnitud | Unidad usada hoy | Notas |
|---|---|---|
| Superficie | ha | Superficie **cosechada** |
| Masa (producción y residuo) | t (escrito `Tn`) | En los pasos energéticos también kg |
| Rendimiento | t/ha | Calculado como producción / superficie |
| Energía | kWh | El dashboard la muestra en MWh, GWh o TWh |
| Potencia | kW | Potencia nominal del PP30 |
| Tiempo | h; año (8760 h) | |
| Dinero | ARS nominales | Sin impuestos y sin deflactar |
| Tarifas | ARS/kWh; cargo fijo en ARS/mes | Cada distribuidora con su propia vigencia (de 2026-03 a 2026-10) |
| Fracciones | 0–1 | Excepto la humedad, que va en % (0–100) |
| Período | Campaña (`AAAA/AA`) o año | Depende de la tabla |

## 1. Datos crudos (`data/raw/`)

Las unidades de origen no se usan directamente: el ETL recalcula el
rendimiento como producción / superficie.

### MAGyP — Estimaciones agrícolas (`datos_estimaciones.csv`)

| Columna | Unidad |
|---|---|
| `Sup. Sembrada`, `Sup. Cosechada` | ha |
| `Producción` | t |
| `Rendimiento` | **kg/ha** (por ejemplo, 3333 = 3,33 t/ha) |
| `Campaña` | `AAAA/AA` |

### Bolsa de Cereales de Córdoba (`datos_bolsa_granos_cba.csv`)

| Columna | Unidad |
|---|---|
| `SEMBRADAS`, `COSECHADAS` | ha |
| `PRODUCCIÓN`, `PRODUCCIÓN GRANO LIMPIO Y SECO` | t |
| `RENDIMIENTO`, `RENDIMIENTO GRANO LIMPIO Y SECO` | **qq/ha** (quintales: 22 = 2,2 t/ha) |

### Bolsa de Cereales de la Nación (`datos_bolsa_cereales_nacion.csv`)

El archivo es en realidad un **XLSX con extensión `.csv`**, y el pipeline
actual no lo usa.

## 2. Datos de referencia (`data/reference/`)

### Índice de cosecha (`ic_fr.csv`)

| Columna | Unidad |
|---|---|
| `IC` (índice de cosecha) | Fracción 0–1, sobre materia seca |
| `FR` (relación residuo/grano, `(1 − IC) / IC`) | Adimensional (t residuo / t grano) |
| `MS` (materia seca) | Fracción 0–1 de la producción comercial |

### Tarifas (`*_tarifas.json` y `tarifas_historial.csv`)

| Campo | Unidad |
|---|---|
| `tarifa_compra_kwh` | **ARS/kWh** sin impuestos |
| `tarifa_inyeccion_kwh` | **ARS/kWh** sin impuestos |
| `cargo_fijo_mensual` | ARS/mes |
| `vigencia` | `AAAA-MM` |
| `fecha_extraccion`, `generado_en` | ISO 8601 (`AAAA-MM-DDThh:mm:ss`) |
| `puntaje_compra`, `n_valores_*` | Adimensional (conteos y puntajes del parser) |

### Parámetros del PP30 (`parametros_pp30` en el JSON de tarifas)

| Parámetro | Valor | Unidad |
|---|---:|---|
| `humedad_pct_default` | 12 | **%** (0–100) |
| `consumo_especifico_seco_kg_kwh` | 1,0 | kg MS/kWh |
| `potencia_nominal_kw` | 22 | kW |
| `disponibilidad` | 0,8 | Fracción 0–1 |
| `factor_autoconsumo_default` | 0,6 | Fracción 0–1 |
| `fraccion_recuperable_default` | 0,5 | Fracción 0–1 |

Constantes en el código (`etl/transformers/energy_finance.py`):
`HOURS_PER_YEAR = 8760` h/año y `KG_PER_TON = 1000` kg/t.

## 3. Salidas procesadas (`data/processed/`)

### `biomasa_validos.parquet` — una fila por campaña, departamento y cultivo

| Columna | Unidad | Base |
|---|---|---|
| `Campaña` | `AAAA/AA` | |
| `Superficie (Ha)` | ha | Cosechada |
| `Produccion (Tn)` | t | Humedad comercial (granos) o fresco (papa, ajo) |
| `Rendimiento (Tn/Ha)` | t/ha | Humedad comercial |
| `Produccion (Tn/Ha)` | t/ha | **Duplica** a `Rendimiento (Tn/Ha)` |
| `FR` | Adimensional | |
| `MS` | Fracción 0–1 | |
| `Residuo de Biomasa (Tn)` | t | **Materia seca** (`Producción × MS × FR`) |
| `Residuo de Biomasa (Tn/Ha)` | t/ha | Materia seca |
| `Residuo Recuperable (Tn)` | t | Materia seca (× fracción recuperable) |
| `masa_seca_kg` | kg | Materia seca (= residuo recuperable × 1000) |
| `masa_alimentada_kg` | kg | Al 12 % de humedad (`masa_seca / (1 − H/100)`) |
| `kwh_generados` | kWh | Por campaña |
| `kwh_autoconsumo`, `kwh_inyectados` | kWh | Por campaña |
| `horas_operacion_estimadas` | h | Horas de un equipo PP30 |
| `equipos_pp30_equivalentes` | Equipos | Adimensional |
| `tarifa_compra_kwh`, `tarifa_inyeccion_kwh` | ARS/kWh | Sin impuestos |
| `ahorro_autoconsumo_ars` | ARS | Por campaña, nominales |
| `credito_inyeccion_ars` | ARS | Por campaña, nominales |
| `beneficio_total_ars` | ARS | Por campaña; beneficio **bruto** |
| `_tiene_ic`, `_valido_biomasa`, `tarifa_es_proxy`, `tarifa_inyeccion_estimada`, etc. | Booleanas | |

### `potencial_energetico_anual.parquet` — promedio anual del período de referencia

Tiene las mismas magnitudes, pero **por año**: es el promedio por
campaña de las últimas N campañas (`periodo_referencia`, por ejemplo
`2020/21–2024/25 (N=5)`). Las campañas sin dato cuentan como 0.

| Columna | Unidad |
|---|---|
| `Superficie (Ha)` | ha/año |
| `Produccion (Tn)` | t/año |
| `Residuo de Biomasa (Tn)`, `Residuo Recuperable (Tn)` | t MS/año |
| `masa_seca_kg`, `masa_alimentada_kg` | kg/año |
| `kwh_generados`, `kwh_autoconsumo`, `kwh_inyectados` | kWh/año |
| `horas_operacion_estimadas` | h/año |
| `ahorro_autoconsumo_ars`, `credito_inyeccion_ars`, `beneficio_total_ars` | ARS/año |
| `n_campanas_con_dato` | Campañas (conteo) |

### `database.sqlite`

No tiene tablas.

## 4. Auditoría (`data/audit/`)

| Archivo | Columnas con unidad |
|---|---|
| `discrepancias_cba_vs_magyp.parquet` | `superficie_*` en ha; `produccion_*` en t; `diff_rel_*` como fracción (4,23 = +423 %) |
| `descartados_reconciliacion.parquet` | Igual que `biomasa_validos` (ha, t, t/ha) |
| `alertas_calidad.parquet` | `valor_anterior` y `valor_actual` en la unidad del control (ARS/kWh en `salto_tarifa`); `variacion` y `umbral` como fracción (0,94 = +94 %) |
| `biomasa_validos.parquet` | Copia de la salida procesada |

## 5. Dashboard (cómo se muestra)

| Magnitud | Unidad mostrada |
|---|---|
| Energía | GWh/año (`kWh / 1e6`); en las tarjetas, MWh/GWh/TWh automático |
| Beneficio, ahorro, crédito | Millones de ARS/año (`/ 1e6`); en las tarjetas, `$ M` o `$ mil M` |
| Masa | t, k t, M t (automático); en la tabla de energía, t MS/año |
| Tarifas | $/kWh |

## Inconsistencias para estandarizar

1. **Nombres de columna con dos estilos:** con la unidad entre paréntesis y
   en mayúsculas (`Produccion (Tn)`, `Superficie (Ha)`) frente a snake_case
   con sufijo (`masa_seca_kg`, `beneficio_total_ars`).
2. **Símbolo de tonelada:** `Tn` en las columnas y `t` en el dashboard y la
   documentación. El símbolo SI es `t`.
3. **Base de humedad sin indicar:** `Produccion (Tn)` está a humedad
   comercial, pero `Residuo de Biomasa (Tn)` y `Residuo Recuperable (Tn)`
   están en **materia seca**, y el nombre no lo dice.
4. **Masa en dos unidades:** el residuo va en t y la masa del PP30 en kg
   (`masa_seca_kg` = `Residuo Recuperable (Tn)` × 1000).
5. **Nombres de tarifa engañosos:** `tarifa_compra_kwh` está en ARS/kWh,
   no en kWh.
6. **Porcentajes en dos formatos:** la humedad va en % (12), mientras que
   disponibilidad, factor de autoconsumo, MS, `variacion` y `diff_rel_*`
   van como fracción 0–1.
7. **Período implícito:** las mismas columnas significan "por campaña" en
   `biomasa_validos` y "por año" en `potencial_energetico_anual`, sin que el
   nombre lo indique.
8. **Columna duplicada:** `Produccion (Tn/Ha)` = `Rendimiento (Tn/Ha)`.
9. **Pesos sin fecha de referencia:** ARS nominales con tarifas de vigencias
   distintas (marzo a octubre de 2026), sin deflactar ni llevar a una fecha
   común.
10. **Fuentes crudas en unidades distintas:** el rendimiento viene en kg/ha
    (MAGyP) y en qq/ha (BCCBA). Hoy se evita porque se recalcula, pero
    conviene documentarlo si se usan esas columnas.
11. **Extensión incorrecta:** `datos_bolsa_cereales_nacion.csv` es un XLSX.

### Propuesta de estándar (para discutir)

- Símbolos SI en minúscula: `t`, `ha`, `kg`, `kWh`, `kW`, `h`.
- Nombres en snake_case con unidad y base al final, por ejemplo
  `produccion_t`, `residuo_recuperable_t_ms`, `rendimiento_t_ha`,
  `tarifa_compra_ars_kwh`, `energia_kwh_anio`.
- Una sola unidad de masa en las tablas (t), y kg sólo en cálculos
  internos.
- Fracciones siempre en 0–1, con el sufijo `_pct` sólo cuando el valor
  está en 0–100.
- Montos en ARS con mes de referencia explícito (por ejemplo,
  `ARS de oct-2026`).

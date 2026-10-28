# Tarifas faltantes de scrapear y cómo se estiman

> Estado a la última corrida del extractor (`data/reference/20261016221146_tarifas.json`,
> 16/10/2026). Documento de trabajo; la referencia estable es
> [`docs/03_datos/tarifas_electricas.md`](../../03_datos/tarifas_electricas.md).

## Resumen

De las **28 distribuidoras** mapeadas, el extractor obtiene la **tarifa de
compra en 25**. Lo que falta se reparte en tres grupos:

| Qué falta | Distribuidoras | Cómo se resuelve hoy |
|---|---:|---|
| Toda la tarifa (compra e inyección) | 3 (SPSE, DPE_TDF, EDET) | **No se estima**: la provincia queda sin valorización (finanzas en NaN) |
| Sólo la tarifa de inyección | 10 | Se estima como **compra × 0,913** (ratio mediano observado, 0,9126) |
| Cargo fijo mensual | 14 | No se estima; hoy no interviene en el cálculo financiero |
| Provincia sin distribuidora (Chubut) | — | Sin tarifa asignada (finanzas en NaN) |

## 1. Distribuidoras sin ninguna tarifa

| Código | Provincia | Motivo | Cómo completarla |
|---|---|---|---|
| `SPSE` | Santa Cruz | El portal nacional enlaza archivos inexistentes (404) y el sitio propio no responde | Carga manual |
| `DPE_TDF` | Tierra del Fuego | Sólo publica resoluciones escaneadas (sin texto) | Carga manual de una versión con texto o planilla |
| `EDET` | Tucumán | Cuadros en PDF escaneado (imágenes) | Carga manual de una versión con texto o planilla |

**Estimación: ninguna.** El extractor las deja con estado `sin_dato` y
`TariffResolver` (`etl/transformers/energy_finance.py`) no encuentra
distribuidora con valor, así que la tarifa de compra y la de inyección
quedan en NaN y esas provincias **no suman dinero**. Es una decisión
explícita: los valores cargados a mano en versiones viejas (`baseline_manual`)
no se heredan, para no mezclar números sin verificar con valores reales.

Impacto: menos del 1 % de la energía calculada, casi toda de Tucumán.

**Cómo completarlas:** dejar el cuadro oficial en
`data/reference/cuadros_manuales/<CÓDIGO>/` con `AAAA_MM` en el nombre y
correr:

```bash
python -m etl.extractors.scrape_tarifas --solo SPSE DPE_TDF EDET
```

Ver [`data/reference/cuadros_manuales/README.md`](../../../data/reference/cuadros_manuales/README.md).
Un PDF escaneado no sirve: hace falta texto seleccionable o una planilla.

### Chubut

No tiene distribuidora provincial única (el servicio lo prestan
cooperativas) y no figura en `provincia_a_distribuidora`. Sus registros
quedan sin distribuidora y con métricas financieras en NaN.

## 2. Tarifa de inyección faltante

Estas distribuidoras publican la tarifa de compra pero no un precio de
inyección (Ley 27.424) que el lector reconozca:

| Código | Provincia | Compra ($/kWh) | Inyección estimada ($/kWh) | Vigencia |
|---|---|---:|---:|---|
| ECSAPEM | Catamarca | 106,29 | 97,00 | 2026-05 |
| DPEC | Corrientes | 109,20 | 99,66 | 2026-04 |
| REFSA | Formosa | 135,28 | 123,47 | 2026-06 |
| EDEMSA | Mendoza | 106,51 | 97,20 | 2026-05 |
| EDESTE | Mendoza (zona este) | 106,51 | 97,20 | 2026-05 |
| EMSA | Misiones | 283,84 | 259,04 | 2026-09 |
| EPEN | Neuquén | 359,73 | 328,30 | 2026-08 |
| EDESAL | San Luis | 110,76 | 101,08 | 2026-06 |
| EPE | Santa Fe | 146,77 | 133,95 | 2026-09 |
| EDESE | Santiago del Estero | 156,66 | 142,97 | 2026-09 |

### Cómo se estima

En `compute_finance_metrics` (`etl/transformers/energy_finance.py`):

```
tarifa_inyeccion = tarifa_compra × ratio
ratio = mediana(inyección / compra) de las distribuidoras con ambos valores extraídos
```

- `injection_ratio` sólo usa distribuidoras con inyección en estado
  `extraido` y `0 < inyección ≤ compra`. Si no hubiera ninguna, usa
  `DEFAULT_RATIO_INYECCION = 0,75`.
- Cada registro estimado queda marcado con la columna
  `tarifa_inyeccion_estimada = True`, para poder filtrarlo en el análisis y
  en el dashboard.
- Fundamento: por la Ley 27.424 la inyección se paga al costo de compra de
  la energía en el mercado mayorista, sin valor agregado de distribución,
  así que es una fracción estable de la tarifa de compra. Ver
  [POL-TARIFF-002](../../02_metodologia/decisiones.md#pol-tariff-002--tarifa-de-inyección-faltante).

### Ratios observados (15 distribuidoras)

| Distribuidora | Inyección / compra |
|---|---:|
| EDERSA | 1,000 |
| ESJ | 1,000 |
| EPEC | 0,980 |
| EDESUR | 0,974 |
| EDENOR | 0,970 |
| EDELAP | 0,926 |
| EDEN | 0,917 |
| **EDEA (mediana)** | **0,913** |
| EDES | 0,904 |
| SECHEEP | 0,766 |
| EDELAR | 0,752 |
| ENERSA | 0,715 |
| EJESA | 0,634 |
| APE | 0,547 |
| EDESA | 0,120 |

La mediana es robusta a los extremos: EDESA (0,12, que paga la inyección de
origen biomasa muy por debajo de la compra) y los casos de cargo por
potencia (ESJ y EDERSA, ratio 1). Aun así, la dispersión es alta (0,12 a
1,0): la inyección estimada puede estar sobrevalorada en las provincias que
se comportan como Salta o La Pampa.

> La documentación de referencia todavía cita 0,917; con las 15
> distribuidoras actuales el ratio es **0,913**.

## 3. Cargo fijo mensual faltante

Sin cargo fijo extraído (`sin_dato`): EPEC, DPEC, REFSA, EJESA, APE, EMSA,
EPEN, EDERSA, ESJ, EDESAL, SPSE, EPE, EDESE y DPE_TDF.

**Estimación: ninguna**, y hoy no hace falta: el cálculo financiero valoriza
sólo kWh (ahorro por autoconsumo + crédito por inyección) y no usa el cargo
fijo. Pasaría a importar si se calcula una factura completa o un flujo de
caja con cargos fijos.

## 4. Casos aproximados (no faltantes, pero estimados)

- **Buenos Aires** tiene tres distribuidoras provinciales (EDEN, EDEA,
  EDES). Salvo los departamentos mapeados a una distribuidora concreta, se
  usa el **promedio simple** de las tres y el registro queda con
  `tarifa_es_proxy = True`.
- **APE (La Pampa)** está marcada como proxy: atiende sólo parte de la
  provincia y el resto lo cubren cooperativas.

## Próximos pasos sugeridos

1. Conseguir los cuadros de **EDET** (es casi todo el impacto), SPSE y DPE
   en un formato con texto y cargarlos a mano.
2. Evaluar un ratio de inyección **regional** en vez del nacional (por
   ejemplo, NOA con EJESA y EDESA), dada la dispersión observada.
3. Decidir si Chubut se modela con una tarifa de cooperativa
   representativa o queda fuera del análisis económico.
4. Actualizar el 0,917 de `docs/03_datos/tarifas_electricas.md` a 0,913.

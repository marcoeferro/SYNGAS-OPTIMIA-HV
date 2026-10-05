# Registro de decisiones metodológicas

> Por qué el sistema calcula como calcula. Cada decisión tiene un código
> (`POL-…`) que puede citarse en el código, en issues o en informes. El
> cálculo completo está en [metodología](metodologia.md).

| Código | Decisión | Desde |
|---|---|---|
| [POL-CROP-001](#pol-crop-001--total-vs-componentes-de-un-cultivo) | Si hay total y componentes de un cultivo, prevalece el total | versión inicial |
| [POL-SOURCE-001](#pol-source-001--reconciliación-por-mayor-producción) | Entre dos fuentes, prevalece la de mayor producción | versión inicial |
| [POL-MISSING-001](#pol-missing-001--valores-faltantes) | Los faltantes no se convierten en cero ni se borran en silencio | versión inicial |
| [POL-GEO-001](#pol-geo-001--alias-de-departamento-entre-fuentes) | Alias para nombres de departamento que difieren entre fuentes | 2026-10 |
| [POL-PERIOD-001](#pol-period-001--período-de-referencia-anual) | Resultados por año: promedio de las 5 últimas campañas completas | 2026-10 |
| [POL-ENERGY-001](#pol-energy-001--conversión-a-energía-apl-pp30) | Energía con el gasificador PP30 sobre el residuo recuperable | 2026-10 |
| [POL-TARIFF-001](#pol-tariff-001--tarifa-de-compra-representativa) | Tarifa de compra: medianas/grandes demandas, baja tensión, banda Resto | 2026-10 |
| [POL-TARIFF-002](#pol-tariff-002--tarifa-de-inyección-faltante) | Inyección faltante: compra × ratio observado | 2026-10 |
| [POL-QA-001](#pol-qa-001--tests-y-controles-de-calidad-de-datos) | Tests en CI; controles de datos y alertas en cada corrida | 2026-10 |

---

## POL-CROP-001 — Total vs. componentes de un cultivo

**Contexto**: algunas fuentes informan un cultivo desagregado ("soja 1ra",
"soja 2da") y también su total ("soja total").

**Regla**: para cada clave `(Campaña, Provincia, Departamento, cultivo
canónico)`, si coexisten el total y sus componentes, **prevalece el
total** y los componentes se descartan, para no contar dos veces. Si no hay
total, los componentes se suman.

**Excepciones**:
- `trigo candeal` (*Triticum durum*) y `trigo` (*Triticum aestivum*) son
  especies distintas y no se consolidan.
- Los nombres compuestos (`caña de azúcar`, `yerba mate`) no se colapsan.

**Código**: `etl/reference/crop_taxonomy.py`, `etl/transformers/crop_consolidation.py`.

---

## POL-SOURCE-001 — Reconciliación por mayor producción

**Contexto**: MAGyP y la Bolsa de Cereales de Córdoba informan muchos
departamentos en común, con cifras distintas.

**Regla**: cuando ambas fuentes informan la misma clave, se conserva **el
registro de mayor producción**. A igual producción, prevalece MAGyP (fuente
oficial); el desempate es determinístico.

**Fundamento**: la producción declarada ante AFIP en el SISA (Resolución
General Conjunta MAGyP–AFIP 5236) tiene carácter de declaración jurada.
Sin una validación de campo, conservar la mayor cifra declarada evita
subestimar el potencial.

**Consecuencia**: los registros descartados y la diferencia entre fuentes se
guardan en `data/audit/` y se ven en el dashboard (Auditoría).

**Código**: `etl/transformers/reconciliation.py`.

---

## POL-MISSING-001 — Valores faltantes

**Regla**:
- Un dato faltante en la fuente (p.ej. `SD`, "sin dato") queda como
  faltante: **no se convierte en cero**.
- No se borran filas en bloque (`dropna` global). Cada registro recibe
  marcas de validez: `_tiene_ic`, `_rendimiento_invalido`, `_valido_biomasa`.
- Al publicar, `biomasa_validos.parquet` incluye **sólo los registros
  válidos**: cultivo con coeficientes, superficie > 0 y biomasa calculable.
  Cuántos registros y cuánta producción quedan excluidos por cultivo se
  registra en el log de cada corrida.

**Código**: `etl/transformers/source_cleaning.py`, `etl/transformers/biomass.py`.

---

## POL-GEO-001 — Alias de departamento entre fuentes

**Contexto**: la reconciliación cruza fuentes por nombre de departamento.
Si las fuentes escriben distinto el mismo departamento, no se cruzan y se
suman las dos (doble conteo).

**Regla**: los nombres que difieren entre fuentes se unifican con un alias
explícito en `DEPT_ALIASES` (`etl/transformers/geography.py`). Casos
actuales: Juan Felipe Ibarra (Santiago del Estero), Libertador General San
Martín (San Luis), Juan B. Alberdi (Tucumán).

---

## POL-PERIOD-001 — Período de referencia anual

**Regla**: energía y dinero se expresan **por año**, como promedio de las 5
últimas campañas completas. La campaña en curso, con menos del 80 % de los
registros habituales, se excluye. Una campaña sin registro para una clave
cuenta como cero.

**Fundamento**: sumar todas las campañas desde 1969 no representa ninguna
magnitud física, y la campaña en curso subestimaría el resultado.

**Código**: `etl/transformers/reference_period.py`.

---

## POL-ENERGY-001 — Conversión a energía (APL PP30)

**Regla**: residuo recuperable (50 % del residuo) → masa a humedad
operativa (12 %) → energía con un consumo específico de 1,1 kg/kWh. La
humedad se aplica **una sola vez**: el residuo ya está en materia seca.

**Código**: `etl/transformers/energy_finance.py`.

---

## POL-TARIFF-001 — Tarifa de compra representativa

**Regla**: categoría de medianas o grandes demandas en **baja tensión**
(preferentemente < 300 kW), **banda horaria "Resto"**, **sin impuestos**,
del **cuadro pleno vigente** (sin subsidios ni regímenes especiales).

**Se excluyen**: media y alta tensión, peaje, alumbrado público,
categorías de 300 kW o más y la tarifa mayorista a distribuidores
municipales o cooperativas (OCEBA).

**Casos especiales**: cuando el cuadro no permite reconocer la categoría
por contexto, el registro de distribuidoras fija la fila (`fila_tarifa`):
- EPE: T2, fila "2 B1".
- APE: T2I, costo de compra + VAD del excedente.
- EMSA: industrial 3.b.
- EPEC: Tarifa 3, baja tensión, < 300 kW, apartado a.1.2 (no clubes de
  barrio), banda "Horas Restantes"; la inyección sale de la misma
  categoría en la sección de generación distribuida (`fila_inyeccion`).

**Código**: `etl/extractors/tariff_parser.py`, `etl/reference/distribuidoras.py`.
Detalle: [tarifas eléctricas](../03_datos/tarifas_electricas.md).

---

## POL-TARIFF-002 — Tarifa de inyección faltante

**Regla**: donde la distribuidora no publica precio de inyección (Ley
27.424), se estima como **tarifa de compra × ratio mediano
inyección/compra** de las distribuidoras que publican ambos (≈ 0,75 en
octubre de 2026). El registro queda marcado `tarifa_inyeccion_estimada`.

**Fundamento**: sin estimación, el beneficio de esas provincias quedaba
vacío y sólo dos provincias sumaban dinero.

---

## POL-QA-001 — Tests y controles de calidad de datos

**Regla**:
- Los **tests** verifican el código con casos fijos y corren en CI (cada PR
  y push a `main`). No se ejecutan dentro del ETL.
- Los **controles de datos** corren en cada ejecución del ETL:
  - las violaciones de invariantes cortan el pipeline;
  - los cambios sospechosos respecto de la corrida anterior generan
    alertas: salto de tarifa > 50 %, cambio del total > 20 %, de una
    provincia > 50 %;
  - con `--estricto`, las alertas también cortan el pipeline antes de
    publicar.

Detalle: [tests y controles](../06_calidad/tests_y_controles.md).

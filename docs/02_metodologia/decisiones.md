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
| [POL-ENERGY-001](#pol-energy-001--conversión-a-energía-apl-pp30) | Energía con la ficha del PP30: 1,0 kg MS/kWh, 22 kW a 50 Hz | 2026-10 |
| [POL-RECOVERY-001](#pol-recovery-001--fracción-de-rastrojo-retirada) | Se retira el 50 % del rastrojo (límite superior sostenible) | 2026-10 |
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

**Código**: `src/optimia_hv/biomasa/reference/crop_taxonomy.py`, `src/optimia_hv/biomasa/transformers/crop_consolidation.py`.

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

**Código**: `src/optimia_hv/biomasa/transformers/reconciliation.py`.

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

**Código**: `src/optimia_hv/biomasa/transformers/source_cleaning.py`, `src/optimia_hv/biomasa/transformers/biomass.py`.

---

## POL-GEO-001 — Alias de departamento entre fuentes

**Contexto**: la reconciliación cruza fuentes por nombre de departamento.
Si las fuentes escriben distinto el mismo departamento, no se cruzan y se
suman las dos (doble conteo).

**Regla**: los nombres que difieren entre fuentes se unifican con un alias
explícito en `DEPT_ALIASES` (`src/optimia_hv/biomasa/transformers/geography.py`). Casos
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

**Código**: `src/optimia_hv/biomasa/transformers/reference_period.py`.

---

## POL-ENERGY-001 — Conversión a energía (APL PP30)

**Regla**: residuo recuperable (t de materia seca) → energía con el
consumo específico de la **ficha técnica del fabricante: 1,0 kg de materia
seca por kWh**. La humedad operativa (12 %) sólo se usa para calcular la
masa que se carga al equipo; no cambia los kWh. Potencia de referencia
para los equipos equivalentes: **22 kW** (PP30 a 50 Hz conectado a red).

**Fundamento**: All Power Labs publica el consumo en base seca (1,0 kg/kWh)
y su ajuste por humedad (1,1 / 1,2 / 1,3 kg/kWh con 10 / 20 / 30 %). Como el
residuo del modelo ya está en materia seca, se usa el valor seco directo.

**Antes** (hasta 2026-10): 1,1 kg/kWh sobre material al 12 % (≈ 0,968 kg
MS/kWh) y 25 kW. El cambio bajó la energía un 3,2 %.

**Escenario**: el dashboard permite usar 1,1 kg MS/kWh (conservador).

**Código**: `src/optimia_hv/biomasa/transformers/energy_finance.py`. Detalle:
[metodología §3](metodologia.md#3-energía-gasificador-apl-pp30).

---

## POL-RECOVERY-001 — Fracción de rastrojo retirada

**Regla**: se retira el **50 %** del rastrojo (residuo recuperable); el
resto queda en el lote.

**Fundamento**: es un supuesto, elegido como límite superior de lo que la
bibliografía considera sostenible (Wilhelm et al. 2007: la materia
orgánica del suelo exige dejar más rastrojo que el control de erosión;
Agronomy Journal 2021: no más de 25–40 % en maíz con rendimientos altos).
Es optimista; 30–40 % es más prudente.

**Escenario**: el dashboard permite variarlo entre 20 % y 70 %; el ETL lo
acepta con `--fraccion-recuperable`.

**Código**: `src/optimia_hv/biomasa/transformers/biomass.py` (`add_recoverable_residue`).
Detalle: [metodología §2](metodologia.md#2-residuo-recuperable).

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

**Código**: `src/optimia_hv/biomasa/extractors/tariff_parser.py`, `src/optimia_hv/biomasa/reference/distribuidoras.py`.
Detalle: [tarifas eléctricas](../03_datos/tarifas_electricas.md).

---

## POL-TARIFF-002 — Tarifa de inyección faltante

**Contexto**: por la Ley 27.424 (generación distribuida) la distribuidora
reconoce cada kWh que el usuario-generador entrega a la red. Su
reglamentación fija ese precio en función del **costo de compra de la
energía por la distribuidora en el mercado mayorista** (precio estacional
más pérdidas reconocidas), sin el valor agregado de distribución. Así lo
dice, por ejemplo, el régimen de Tarifa 5 de Naturgy San Juan: "bonificación
por la energía inyectada a la red, valorizada según el precio de compra de
la energía por la distribuidora en cada banda horaria, incluyendo pérdidas
reconocidas".

**Regla**: donde el cuadro no publica el precio de inyección, se estima
como **tarifa de compra × ratio mediano inyección/compra** de las
distribuidoras que publican ambos valores (ver la tabla en
[tarifas eléctricas](../03_datos/tarifas_electricas.md)). El registro queda
marcado `tarifa_inyeccion_estimada`. El ratio se recalcula en cada corrida
con los valores reales disponibles.

**Fundamento**:

- Como la inyección se paga al precio de la energía y la compra incluye
  además la distribución, la inyección siempre es menor o igual que la
  compra. El ratio observado depende de cómo está armada la tarifa:
  - en categorías con cargo por potencia aparte (T3 de grandes demandas),
    el cargo de energía de compra ya es casi sólo energía: ratio entre
    0,9 y 1 (OCEBA, ENRE, EPEC, San Juan);
  - en categorías con cargo de energía único (medianas demandas), la
    compra incluye la distribución: ratio entre 0,6 y 0,8 (EJESA, ENERSA,
    SECHEEP, EDELAR).
- La mediana de los valores reales es un supuesto explícito, auditable y
  que se corrige solo a medida que se consiguen más cuadros.
- Sin estimación, el beneficio de esas provincias quedaba subvaluado (como
  si la energía inyectada no valiera nada).

**Cómo leerlo**: la inyección es el 40 % de la energía. Con el rango
observado de ratios (≈ 0,63 a 1) y un ratio central de ≈ 0,9, el
beneficio de una provincia con inyección estimada podría ser entre ≈ 12 %
menor y ≈ 4 % mayor que el calculado (beneficio ∝ 0,6 + 0,4 × ratio). En el dashboard las distribuidoras con inyección estimada están
marcadas como tales.

**Alternativa** (pendiente): estimar la inyección con el precio estacional
de la energía que publica la Secretaría de Energía, que es la base legal
del precio de inyección y es uniforme para todo el país.

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

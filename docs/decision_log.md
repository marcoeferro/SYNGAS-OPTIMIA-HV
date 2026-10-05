# Registro de decisiones metodológicas

## POL-CROP-001 — Consolidación de registros `X total` vs componentes

**Fecha**: 2026-XX-XX
**Autor**: Equipo de datos
**Alcance**: dataset integrado CBA + MAGYP en capa curada.

**Regla**: cuando para una clave `(Campaña, Provincia, Departamento,
cultivo_canónico)` coexistan registros agregados y componentes,
prevalece el agregado. Los componentes se descartan para esa clave por
riesgo de doble conteo. Si no existe agregado, se conservan los
componentes y se suman en la etapa de agregación.

**Cultivos biológicamente distintos**: `trigo candeal` (*Triticum durum*)
y `trigo` (*Triticum aestivum*) no se consolidan.

**Cultivos compuestos**: nombres de más de una palabra
(`caña de azúcar`, `yerba mate`) no se colapsan.

---

## POL-SOURCE-001 — Reconciliación multi-fuente por mayor producción

**Fecha**: 2026-XX-XX
**Autor**: Equipo de datos
**Alcance**: dataset integrado CBA + MAGYP.

**Regla**: en claves con cobertura múltiple, prevalece el registro con
mayor producción declarada.

**Fundamento**: la información productiva declarada ante AFIP en el
marco del SISA (Resolución General Conjunta MAGyP y AFIP 5236) tiene
carácter de declaración jurada y condiciona el tratamiento fiscal del
productor. En ausencia de validación contra ground truth, preservar la
mayor magnitud reportada minimiza subrepresentación del potencial de
biomasa residual.

**Registros descartados**: se persisten en `data/audit/` para permitir
reconstrucción de decisiones y análisis de discrepancias.

---

## POL-MISSING-001 — Gestión de valores faltantes

**Fecha**: 2026-XX-XX
**Autor**: Equipo de datos
**Alcance**: cálculo de biomasa residual.

**Regla**: prohibido `dropna(how="any")` sobre el dataset integrado.

**Clasificación de causas**:
- Dato faltante en fuente: la fuente no reportó el valor.
- Coeficiente no definido: falta entrada en la tabla IC.
- Valor derivado no calculable: NaN por propagación o div/0.

**Tratamiento**: los cultivos sin IC documentado se marcan con
`_valido_biomasa=False` y se reportan cuantitativamente. No se eliminan
filas del dataset curado.

---

## POL-GEO-001 — Alias de departamento entre fuentes

**Fecha**: 2026-10-05
**Alcance**: normalización geográfica previa a la reconciliación.

**Regla**: cuando MAGyP y la Bolsa de Córdoba nombran distinto el mismo
departamento, se agrega un alias en `DEPT_ALIASES`
(`etl/transformers/geography.py`). Sin alias, la reconciliación no cruza
los registros y suma ambas fuentes (doble conteo). Casos: Juan Felipe
Ibarra (Santiago del Estero) y Libertador General San Martín (San Luis).

---

## POL-PERIOD-001 — Período de referencia anual

**Regla**: energía y dinero se expresan por año, como promedio de las 5
últimas campañas completas. La campaña en curso (con registros
incompletos) se excluye. Una campaña sin registro para una clave cuenta
como cero.

---

## POL-ENERGY-001 — Conversión a energía (APL PP30)

**Regla**: residuo recuperable (50 % del residuo) → masa a humedad
operativa (12 %) → energía con un consumo específico de 1,1 kg/kWh. La
humedad se aplica una sola vez: el residuo ya está en materia seca.

---

## POL-TARIFF-001 — Tarifa de compra representativa

**Regla**: se toma la categoría de medianas o grandes demandas en baja
tensión, con preferencia por < 300 kW, banda horaria "Resto", sin
impuestos, del cuadro pleno vigente (sin subsidios ni regímenes
especiales). Se excluyen media y alta tensión, peaje, alumbrado y la
tarifa mayorista a distribuidores municipales (OCEBA). Cuando el cuadro
no permite reconocer la categoría por contexto, el registro de
distribuidoras fija la fila (`fila_tarifa`): EPE (T2 "2 B1"), APE (T2I:
costo de compra + VAD del excedente) y EMSA (industrial 3.b).

---

## POL-TARIFF-002 — Tarifa de inyección faltante

**Regla**: pocas distribuidoras publican el precio de inyección (Ley
27.424). Donde falta, se estima como tarifa de compra × ratio mediano
inyección/compra de las distribuidoras que publican ambos (0,75 en
octubre de 2026) y se marca `tarifa_inyeccion_estimada`. Antes el
beneficio quedaba en NaN y sólo dos provincias sumaban dinero.

---

## POL-QA-001 — Tests y controles de calidad de datos

**Fecha**: 2026-10-05

**Regla**: los tests verifican el código con casos fijos y corren en CI
(cada PR y push a `main`); no se ejecutan dentro del ETL. Los controles de
datos corren en cada ejecución del ETL. Las violaciones de invariantes
cortan el pipeline. Los cambios sospechosos respecto de la corrida
anterior (salto de tarifa > 50 %, cambio del total > 20 %, de una
provincia > 50 %) generan alertas; con `--estricto` también lo cortan
antes de publicar.


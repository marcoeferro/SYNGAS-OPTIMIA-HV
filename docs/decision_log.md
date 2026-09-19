
### `docs/decision_log.md`

```markdown
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
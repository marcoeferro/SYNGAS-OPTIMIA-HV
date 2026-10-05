# Flujo de datos detallado

Etapas de `etl/pipelines/run_etl.py`:

```mermaid
flowchart TD
    A1[1a. Extracción agrícola<br/>CBA + MAGyP → data/raw] --> B
    A2[1b. Extracción de tarifas<br/>→ data/reference/*_tarifas.json<br/>+ tarifas_historial.csv] --> G
    B[2. Carga y limpieza<br/>strings, geografía, alias de departamento,<br/>taxonomía de cultivos, 'SD' → NaN] --> C
    C[3. Agrupación por clave natural<br/>Provincia, Departamento, Campaña, Cultivo] --> D
    D[4. Reconciliación multi-fuente<br/>se conserva la mayor producción] --> E
    D -->|descartados y discrepancias| AUD[(data/audit)]
    E[5. Validación de invariantes] --> F
    F[6. Biomasa residual<br/>Producción × MS × FR;<br/>residuo recuperable] --> G
    G[7. Energía y dinero por campaña<br/>PP30 + tarifa por distribuidora] --> H
    H[8. Potencial anual<br/>promedio de las 5 últimas<br/>campañas completas] --> I
    I[9. Validación de biomasa] --> J
    J[10. Persistencia Parquet] --> OUT[(data/processed)]
```

## Energía y dinero

| Paso | Fórmula |
|------|---------|
| Residuo recuperable | residuo (t MS) × fracción recuperable (0,5) |
| Masa alimentada | residuo recuperable ÷ (1 − humedad operativa 12 %) |
| Energía | masa alimentada ÷ consumo específico (1,1 kg/kWh) |
| Equipos PP30 | energía ÷ (25 kW × 8760 h × disponibilidad 0,8) |
| Ahorro | energía × 0,6 (autoconsumo) × tarifa de compra |
| Inyección | energía × 0,4 × tarifa de inyección (si falta: compra × ratio observado) |

La tarifa se asigna por distribuidora: excepción por departamento (EDESTE,
EDELAP) → distribuidora de la provincia → promedio si la provincia tiene
varias (Buenos Aires: EDEN, EDEA, EDES).

-- =============================================================
-- init.sql — Configuración inicial de Shaper
-- =============================================================
-- Se ejecuta al arrancar el contenedor. Crea vistas sobre los
-- archivos Parquet generados por el pipeline ETL.
-- =============================================================

-- Vista principal de biomasa residual válida
CREATE OR REPLACE VIEW biomasa AS
SELECT *
FROM read_parquet('/data/processed/biomasa_validos.parquet');

-- Vista de registros descartados (auditoría)
CREATE OR REPLACE VIEW descartados AS
SELECT *
FROM read_parquet('/data/audit/descartados_reconciliacion.parquet');

-- Vista de discrepancias entre fuentes (auditoría)
CREATE OR REPLACE VIEW discrepancias AS
SELECT *
FROM read_parquet('/data/audit/discrepancias_cba_vs_magyp.parquet');
# =============================================================
# Dockerfile para el pipeline ETL y el dashboard Streamlit
# =============================================================
# Una sola imagen sirve para:
#   - etl_worker / etl_pipeline (CMD por defecto = ETL)
#   - dashboard   (command override en docker-compose)
# =============================================================

# --- Etapa 1: Builder ---
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /build/wheels -r requirements.txt

# --- Etapa 2: Runtime ---
FROM python:3.11-slim

WORKDIR /app

RUN useradd -m -u 1000 appuser \
    && mkdir -p /app/data /app/logs \
    && chown -R appuser:appuser /app

COPY --from=builder /build/wheels /wheels
COPY --from=builder /build/requirements.txt .
RUN pip install --no-cache /wheels/*

# Código del proyecto (paquete etl + dashboard)
COPY --chown=appuser:appuser . .

# Instalar el paquete local para que `import etl.*` funcione siempre
# (no depende solo del cwd / PYTHONPATH)
USER root
RUN pip install --no-cache-dir --no-deps .
USER appuser

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "etl.pipelines.run_etl", "--config", "config/paths.yaml"]

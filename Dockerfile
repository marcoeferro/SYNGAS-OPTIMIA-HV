# =============================================================
# Dockerfile para el pipeline ETL y el dashboard Streamlit
# =============================================================
# Una sola imagen sirve para:
#   - etl_worker / etl_pipeline (CMD por defecto = ETL)
#   - dashboard   (command override en docker-compose)
#
# Dependencias: solo pyproject.toml (PEP 621). No hay requirements.txt.
# =============================================================

# --- Etapa 1: Builder ---
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Metadatos + código mínimo para resolver deps del paquete
COPY pyproject.toml README.md ./
COPY etl/ etl/
COPY dashboard/ dashboard/

# Rueda el proyecto con el extra de dashboard (misma imagen para ETL y UI)
RUN pip wheel --no-cache-dir --wheel-dir /build/wheels ".[dashboard]"

# --- Etapa 2: Runtime ---
FROM python:3.11-slim

WORKDIR /app

RUN useradd -m -u 1000 appuser \
    && mkdir -p /app/data /app/logs \
    && chown -R appuser:appuser /app

COPY --from=builder /build/wheels /wheels
RUN pip install --no-cache /wheels/*

# Código del proyecto (paquete etl + dashboard)
COPY --chown=appuser:appuser . .

# Reinstalar el paquete local editable-like sin deps (ya están en /wheels)
# para que `import etl.*` y el entrypoint resuelvan siempre
USER root
RUN pip install --no-cache-dir --no-deps .
USER appuser

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "etl.pipelines.run_etl", "--config", "config/paths.yaml"]

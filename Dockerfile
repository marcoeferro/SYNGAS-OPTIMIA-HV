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

# Sólo pyproject.toml: esta capa (dependencias de terceros) se reutiliza
# mientras no cambien las dependencias. Antes se copiaba también el
# código, y cualquier cambio en etl/ o dashboard/ volvía a descargar y
# compilar pandas, pyarrow, streamlit, etc. Los paquetes vacíos alcanzan
# para resolver dependencias; el código real se instala en la etapa 2.
COPY pyproject.toml ./
RUN : > README.md \
    && mkdir -p etl dashboard \
    && touch etl/__init__.py dashboard/__init__.py \
    && pip wheel --no-cache-dir --wheel-dir /build/wheels ".[dashboard]"

# --- Etapa 2: Runtime ---
FROM python:3.11-slim

# Etiqueta para limpiar sólo las imágenes viejas de este proyecto
# (docker image prune --filter label=project=etl-biomasa).
LABEL project=etl-biomasa

WORKDIR /app

RUN useradd -m -u 1000 appuser \
    && mkdir -p /app/data /app/logs \
    && chown -R appuser:appuser /app

COPY --from=builder /build/wheels /wheels
RUN pip install --no-cache /wheels/*

# Código del proyecto (paquete etl + dashboard)
COPY --chown=appuser:appuser . .

# Reinstalar el paquete con el código real (en /wheels quedó el de
# paquetes vacíos), sin dependencias: ya están instaladas.
USER root
RUN pip install --no-cache-dir --no-deps --force-reinstall .
USER appuser

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "etl.pipelines.run_etl", "--config", "config/paths.yaml"]

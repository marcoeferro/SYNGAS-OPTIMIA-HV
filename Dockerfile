# =============================================================
# Dockerfile de OPTIMIA-HV: pipelines (biomasa, solar) y dashboard
# =============================================================
# Una sola imagen sirve para:
#   - cron         (supercronic + config/crontab: corre los extractores)
#   - etl_pipeline (CMD por defecto = ETL, corrida manual)
#   - dashboard    (command override en docker-compose)
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
# código, y cualquier cambio en src/ volvía a descargar y
# compilar pandas, pyarrow, streamlit, etc. Los paquetes vacíos alcanzan
# para resolver dependencias; el código real se instala en la etapa 2.
COPY pyproject.toml ./
RUN : > README.md \
    && mkdir -p src/optimia_hv \
    && touch src/optimia_hv/__init__.py \
    && pip wheel --no-cache-dir --wheel-dir /build/wheels ".[dashboard]"

# supercronic: cron pensado para contenedores (lee un crontab normal,
# pasa las variables de entorno a los jobs y loguea a stdout). Reemplaza
# a Ofelia, que necesitaba el socket de Docker y nombres de contenedor
# fijos (no sirve en Dokploy). Binario verificado por SHA1.
ARG SUPERCRONIC_VERSION=v0.2.49
ARG SUPERCRONIC_SHA1SUM=e63c11a9726b775a6a11801e81af4f3fb926aa68
RUN python -c "import urllib.request as u; u.urlretrieve('https://github.com/aptible/supercronic/releases/download/${SUPERCRONIC_VERSION}/supercronic-linux-amd64', '/build/supercronic')" \
    && echo "${SUPERCRONIC_SHA1SUM}  /build/supercronic" | sha1sum -c - \
    && chmod +x /build/supercronic

# --- Etapa 2: Runtime ---
FROM python:3.11-slim

# Etiqueta para limpiar sólo las imágenes viejas de este proyecto
# (docker image prune --filter label=project=optimia-hv).
LABEL project=optimia-hv

WORKDIR /app

RUN useradd -m -u 1000 appuser \
    && mkdir -p /app/data /app/logs \
    && chown -R appuser:appuser /app

# tzdata: el horario del cron y los logs usan TZ (America/Argentina/...).
RUN apt-get update && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /build/supercronic /usr/local/bin/supercronic
COPY --from=builder /build/wheels /wheels
RUN pip install --no-cache /wheels/* && rm -rf /wheels

# Código del proyecto (paquete optimia_hv en src/)
COPY --chown=appuser:appuser . .

# Reinstalar el paquete con el código real (en /wheels quedó el de
# paquetes vacíos), sin dependencias: ya están instaladas.
USER root
RUN pip install --no-cache-dir --no-deps --force-reinstall . \
    && sed -i 's/\r$//' deploy/cron-entrypoint.sh config/crontab
USER appuser

# El código se importa desde src/ (no desde site-packages) y data/ y
# config/ se buscan en /app.
ENV PYTHONPATH=/app/src
ENV OPTIMIA_ROOT=/app
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "optimia_hv.biomasa.pipelines.run_biomasa", "--config", "config/paths.yaml"]

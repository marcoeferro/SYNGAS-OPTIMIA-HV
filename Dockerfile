# =============================================================
# Dockerfile para el pipeline ETL de Biomasa Residual
# =============================================================
# Este Dockerfile construye únicamente la imagen del pipeline ETL.
# El dashboard (Shaper) usa la imagen oficial taleshape/shaper,
# definida en docker-compose.yml.
# =============================================================

# --- Etapa 1: Builder ---
FROM python:3.11-slim AS builder

WORKDIR /build

# Dependencias de compilación para wheels nativos
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements primero para aprovechar el cache de capas
COPY requirements.txt .

# Precompilar wheels para evitar compilar en runtime
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /build/wheels -r requirements.txt

# --- Etapa 2: Runtime ---
FROM python:3.11-slim

WORKDIR /app

# Usuario no-root por seguridad
RUN useradd -m -u 1000 appuser \
    && mkdir -p /app/data /app/logs \
    && chown -R appuser:appuser /app

# Instalar wheels precompilados
COPY --from=builder /build/wheels /wheels
COPY --from=builder /build/requirements.txt .
RUN pip install --no-cache /wheels/*

USER appuser

# Copiar código y configuración
COPY --chown=appuser:appuser . .

# Comando por defecto: ejecutar el pipeline ETL
CMD ["python", "-m", "etl.pipelines.run_etl", "--config", "config/paths.yaml"]
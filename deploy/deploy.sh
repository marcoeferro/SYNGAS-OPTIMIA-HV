#!/usr/bin/env bash
# Despliega (o actualiza) OPTIMIA-HV en el servidor.
#
# Lo llama .github/workflows/deploy.yml por SSH desde la carpeta de
# deploy (por defecto /opt/optimia), con OPTIMIA_IMAGE=<imagen:tag>.
# A mano: cd /opt/optimia && OPTIMIA_IMAGE=ghcr.io/marcoeferro/optimia:latest bash deploy/deploy.sh
set -euo pipefail

cd "$(dirname "$0")/.."
: "${OPTIMIA_IMAGE:?Falta OPTIMIA_IMAGE (p. ej. ghcr.io/marcoeferro/optimia:latest)}"
export OPTIMIA_IMAGE

COMPOSE=(docker compose -f deploy/docker-compose.prod.yml --project-directory .)

mkdir -p data logs

# El cron de desarrollo apunta al contenedor biomasa_etl_worker; en
# producción el worker se llama optimia_worker.
sed 's/^container = biomasa_etl_worker/container = optimia_worker/' \
    config/schedule.ini > schedule.prod.ini

# Imagen privada en GHCR: hace falta un token con read:packages en .env.
if [ -f .env ] && grep -q '^GHCR_TOKEN=' .env; then
    # shellcheck disable=SC1091
    source <(grep -E '^(GHCR_USER|GHCR_TOKEN)=' .env)
    echo "$GHCR_TOKEN" | docker login ghcr.io -u "${GHCR_USER:-marcoeferro}" --password-stdin
fi

echo "==> Imagen: $OPTIMIA_IMAGE"
"${COMPOSE[@]}" pull worker dashboard
"${COMPOSE[@]}" up -d --remove-orphans

echo "==> Esperando al dashboard..."
for _ in $(seq 1 30); do
    if curl -fsS http://127.0.0.1:8501/_stcore/health >/dev/null 2>&1; then
        echo "==> Dashboard OK"
        docker image prune -f >/dev/null
        exit 0
    fi
    sleep 5
done

echo "!! El dashboard no respondió en 150 s" >&2
"${COMPOSE[@]}" logs --tail 100 dashboard >&2
exit 1

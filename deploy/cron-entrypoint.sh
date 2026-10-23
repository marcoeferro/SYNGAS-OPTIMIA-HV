#!/bin/sh
# Arranque del servicio "cron": primera carga (si hace falta) + supercronic.
#
# ETL_AL_INICIAR controla la corrida inicial del ETL de biomasa:
#   auto (por defecto)  sólo si todavía no hay datos publicados (primer deploy)
#   si                  en cada arranque del contenedor
#   no                  nunca (sólo según config/crontab)
# La corrida inicial va en segundo plano: el cron arranca igual.
set -eu

modo="${ETL_AL_INICIAR:-auto}"
publicado="data/processed/potencial_energetico_anual.parquet"

if [ "$modo" = "si" ] || { [ "$modo" = "auto" ] && [ ! -f "$publicado" ]; }; then
    echo "==> Corrida inicial del ETL de biomasa (ETL_AL_INICIAR=$modo)"
    python -m optimia_hv.biomasa.pipelines.run_biomasa --config config/paths.yaml &
fi

exec supercronic config/crontab

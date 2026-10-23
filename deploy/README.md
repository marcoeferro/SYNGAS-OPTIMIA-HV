# Deploy en Dokploy (VPS)

Producción corre en un **VPS con [Dokploy](https://dokploy.com)**. Dokploy
clona el repo, construye la imagen y levanta `docker-compose.dokploy.yml`;
Traefik (incluido en Dokploy) pone el dominio y el HTTPS.

| Archivo | Para qué |
|---|---|
| `docker-compose.dokploy.yml` | `cron` (supercronic) + `dashboard`, con volúmenes con nombre |
| `cron-entrypoint.sh` | arranque del servicio `cron`: primera carga del ETL + supercronic |
| `../config/crontab` | horario de los extractores (cron estándar de 5 campos) |

## Requisitos del VPS

- Ubuntu 22.04/24.04, **amd64** (el binario de supercronic de la imagen es
  `linux-amd64`).
- **2 GB de RAM como mínimo** (Dokploy + build de la imagen + pandas);
  recomendado 4 GB. Con 2 GB conviene agregar 2 GB de swap.
- Puertos 80, 443 y 3000 (panel de Dokploy) abiertos.

## Preparar Dokploy (una sola vez)

1. Instalar Dokploy en el VPS: `curl -sSL https://dokploy.com/install.sh | sh`
   y entrar a `http://<ip>:3000`.
2. Conectar GitHub (Settings → Git → GitHub App) con acceso al repo.
3. **Create Service → Compose**:
   - Provider: GitHub, repo `marcoeferro/optimia`, rama `main`.
   - Compose Path: `./deploy/docker-compose.dokploy.yml`.
   - **Autodeploy: apagado** (el deploy lo dispara el CI verde, ver abajo).
4. **Environment**: pegar las variables de `.env.example` con los valores
   reales (Growatt, Telegram/webhook, etc.). Dokploy las guarda en `.env`
   junto al compose y `env_file` las pasa a los contenedores.
5. **Domains**: agregar el dominio → servicio `dashboard`, puerto `8501`,
   HTTPS con Let's Encrypt. El DNS del dominio tiene que apuntar a la IP.
6. **Deploy**. La primera vez el servicio `cron` corre el ETL de biomasa
   en segundo plano (`ETL_AL_INICIAR=auto`, unos minutos); el dashboard
   muestra datos cuando termina.
7. Carga histórica solar (una vez), desde la pestaña de terminal del
   contenedor `cron` o `docker exec`:
   `python -m optimia_hv.solar.pipelines.run_solar --historico`.

## Deploy automático tras el CI

`.github/workflows/deploy.yml` llama al webhook de Dokploy cuando el CI
termina verde en `main`. Cargar en GitHub (Settings → Secrets and
variables → Actions):

- `DOKPLOY_WEBHOOK_URL`: Dokploy → servicio → Deployments → Webhook URL.

## Datos y backups

- `optimia_data` (`/app/data`) y `optimia_logs` (`/app/logs`) son
  volúmenes con nombre: sobreviven a cada deploy. Un bind mount `./data`
  **no** sirve: Dokploy borra la carpeta del repo en cada deploy.
- La primera vez `optimia_data` se llena con `data/raw` y `data/reference`
  de la imagen. Después **no** se actualiza desde el repo: si se cambia un
  archivo de referencia versionado (p. ej. `ic_fr.csv`), copiarlo a mano
  (`docker cp`) o borrar el volumen para que se vuelva a sembrar.
- Backups: Dokploy → Volume Backups (sólo funciona con volúmenes con
  nombre) hacia un S3.

## Operación

| Tarea | Cómo |
|---|---|
| Ver si corrió el cron | Logs del servicio `cron` (cada job loguea inicio, salida y código) |
| Correr el ETL a mano | Terminal del contenedor `cron`: `python -m optimia_hv.biomasa.pipelines.run_biomasa` |
| Cambiar el horario | Editar `config/crontab`, push a `main` (redeploy) |
| Rollback | Dokploy → Deployments → redeploy de un deploy anterior |

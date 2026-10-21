# Deploy en DonWeb

Producción corre en un **Cloud Server (VPS) de DonWeb** con Docker. Un
hosting compartido (cPanel/PHP) no sirve: no puede mantener Streamlit ni
el cron de Ofelia corriendo.

| Archivo | Para qué |
|---|---|
| `docker-compose.prod.yml` | worker + scheduler (Ofelia) + dashboard, con la imagen de GHCR |
| `deploy.sh` | pull de la imagen, `up -d` y chequeo de salud; lo llama el workflow |
| `nginx/optimia.conf` | proxy inverso con HTTPS delante de Streamlit |

## Preparar el servidor (una sola vez)

1. Crear el Cloud Server (Ubuntu LTS) y apuntar el dominio a su IP.
2. Instalar Docker y Nginx:
   ```bash
   curl -fsSL https://get.docker.com | sh
   sudo apt install -y nginx certbot python3-certbot-nginx
   ```
3. Usuario de deploy con acceso a Docker y clave SSH:
   ```bash
   sudo adduser --disabled-password deploy
   sudo usermod -aG docker deploy
   sudo mkdir -p /opt/optimia && sudo chown deploy: /opt/optimia
   # en tu máquina: ssh-keygen -t ed25519 -f optimia_deploy
   # pegar optimia_deploy.pub en /home/deploy/.ssh/authorized_keys
   ```
4. Nginx + HTTPS: copiar `nginx/optimia.conf`, cambiar `server_name` y
   correr `sudo certbot --nginx -d <dominio>`.
5. Secretos de la app en `/opt/optimia/.env` (copiar de `.env.example`).
   Si la imagen de GHCR es privada, agregar `GHCR_USER` y `GHCR_TOKEN`
   (token clásico con `read:packages`).

## Secretos en GitHub

`Settings → Secrets and variables → Actions` del repo principal:

- `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY` (contenido de `optimia_deploy`)
- `DEPLOY_PATH` (opcional, por defecto `/opt/optimia`)

Sin `DEPLOY_HOST` el workflow publica la imagen pero no despliega.

## Deploy manual / rollback

```bash
cd /opt/optimia
OPTIMIA_IMAGE=ghcr.io/marcoeferro/optimia:<sha-anterior> bash deploy/deploy.sh
```

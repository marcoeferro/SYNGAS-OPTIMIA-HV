# Despliegue

> Cómo corre el sistema en una máquina (PC o servidor/VPS) con Docker:
> servicios, horario del ETL, recursos y conexiones necesarias. Los pasos
> de instalación están en [instalación](../05_uso/instalacion.md).

## Servicios (Docker Compose)

```mermaid
graph LR
    subgraph Host["Máquina con Docker"]
        SCH["scheduler<br/>(Ofelia)"]
        W["etl_worker<br/>(permanente)"]
        J["etl_pipeline<br/>(ejecución manual)"]
        DASH["dashboard<br/>Streamlit :8501"]
        V1[("./data")]
        V2[("./config")]
        V3[("./logs")]
    end
    U[Navegador] -->|HTTP 8501| DASH
    SCH -->|"ejecuta el ETL según<br/>config/schedule.ini"| W
    W -.lee y escribe.-> V1
    J -.lee y escribe.-> V1
    W -.lee.-> V2
    J -.lee.-> V2
    W -.escribe.-> V3
    DASH -.sólo lee.-> V1
```

| Servicio | Contenedor | Qué hace |
|---|---|---|
| `etl_worker` | `biomasa_etl_worker` | Queda encendido sin hacer nada; el scheduler ejecuta el ETL dentro de él. |
| `scheduler` | `biomasa_scheduler` | Ofelia: dispara el ETL según `config/schedule.ini`. |
| `dashboard` | `biomasa_dashboard` | Sirve el dashboard en el puerto 8501. Monta `./data` en sólo lectura. |
| `etl_pipeline` | `biomasa_etl` | Ejecución única del ETL a pedido (perfil `etl`): `docker compose --profile etl run --rm etl_pipeline`. |

- Una sola imagen (`etl-biomasa:latest`) sirve para el ETL y el dashboard.
- Las carpetas `data/`, `config/` y `logs/` del repositorio se montan en los
  contenedores: los datos sobreviven aunque se borren los contenedores.
- El código del ETL **está dentro de la imagen**: después de actualizar el
  código (`git pull`) hay que reconstruirla (`docker compose up -d --build`
  o `.\scripts\Run-Etl.ps1`, que la reconstruye solo). El código del
  dashboard se monta desde la carpeta, pero conviene reconstruir igual.

## Horario del ETL

Se configura en `config/schedule.ini`, línea `schedule`. El formato de
Ofelia tiene **seis campos, con los segundos primero**:

```ini
schedule = 0 0 6 * * *     ; todos los días a las 06:00
```

| Ejemplo | Significado |
|---|---|
| `0 0 6 * * *` | Todos los días a las 06:00 |
| `0 0 */12 * * *` | Cada 12 horas |
| `0 30 7 * * 1-5` | Lunes a viernes a las 07:30 |
| `0 0 0 1 * *` | El día 1 de cada mes a medianoche |

La hora es la de la variable `TZ` (por defecto Buenos Aires). Después de
cambiarlo: `docker compose restart scheduler`.

Las fuentes agrícolas se actualizan pocas veces por mes y las tarifas,
mensualmente: una corrida diaria alcanza de sobra; una semanal también.

## Variables de entorno

Se definen en un archivo `.env` junto a `docker-compose.yml` (opcional).

| Variable | Valor por defecto | Para qué |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Detalle de los logs (`DEBUG`, `INFO`, `WARNING`) |
| `DASHBOARD_PORT` | `8501` | Puerto del dashboard en la máquina |
| `TZ` | `America/Argentina/Buenos_Aires` | Zona horaria del horario del ETL |
| `EPE_API_KEY` | clave pública del sitio de EPE | Sólo si EPE cambia la clave de su API de descargas |
| `NOTIFY_WEBHOOK_URL` | (vacío) | Webhook para avisos (Slack, Discord, Teams, Google Chat). Ver [avisos](#avisos) |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | (vacío) | Avisos por un bot de Telegram |
| `NOTIFY_ON_SUCCESS` | (vacío) | `1` para avisar también las corridas sin problemas |
| `DATOS_VIEJOS_HORAS` | `48` | Horas sin datos nuevos a partir de las cuales el dashboard muestra un aviso |

## Avisos

El ETL avisa por mensaje cuando:

| Situación | Aviso |
|---|---|
| La corrida falla (fuente caída sin descarga previa, invariante rota, error de código) | 🔴 con la causa |
| Hay alertas de calidad (salto de tarifa, cambio grande de totales) | 🟠 con la lista de alertas; en modo `--estricto` aclara que no se publicaron los datos nuevos |
| Todo salió bien | 🟢 sólo si `NOTIFY_ON_SUCCESS=1` |

Canales (se puede usar uno, varios o ninguno), configurados en el archivo
`.env` junto a `docker-compose.yml`:

```ini
# Slack / Discord / Teams / Google Chat: URL del "webhook entrante" del canal
NOTIFY_WEBHOOK_URL=https://hooks.slack.com/services/...

# Telegram: crear un bot con @BotFather (da el token) y obtener el id del chat
TELEGRAM_BOT_TOKEN=123456:ABC...
TELEGRAM_CHAT_ID=123456789
```

Después de cambiar `.env`: `docker compose up -d` (recrea el worker con las
variables nuevas). Un aviso que no se puede enviar no hace fallar el ETL;
queda en el log. Las URL y tokens son secretos: no subir `.env` al
repositorio.

**Si el ETL directamente no corre** (scheduler detenido, servidor
apagado), no hay quién mande el aviso. Para eso, el dashboard muestra un
cartel en todas las páginas cuando los datos tienen más de
`DATOS_VIEJOS_HORAS` horas (48 por defecto: dos corridas diarias
perdidas). El código está en `etl/notifications.py` y `dashboard/app.py`.

## Recursos

Estimación con los datos de octubre de 2026 (orientativa):

| Recurso | Uso aproximado |
|---|---|
| Memoria | Dashboard: 300 a 600 MB. ETL: hasta ~1 GB durante la corrida. |
| CPU | Baja; el ETL tarda unos minutos, casi todo esperando las descargas (MAGyP hace ≈ 540 pedidos). |
| Disco | Imagen Docker ≈ 1 GB. Datos: unos 10 MB nuevos por día de descargas (ver [limpieza](ciclo_de_vida_de_los_datos.md#limpieza-del-disco)). |

Un VPS con **2 GB de RAM, 1 vCPU y 20 GB de disco** alcanza. Los scripts
`Run-Etl.ps1` y `make docker-etl` borran las imágenes viejas del
proyecto (etiqueta `project=etl-biomasa`) para que no se acumulen.

## Seguridad y acceso

- El dashboard **no tiene usuario ni contraseña**. En un servidor público,
  ponerlo detrás de un proxy con autenticación (Nginx, Caddy, Traefik) o de
  una VPN, y no exponer el puerto 8501 directamente.
- El `scheduler` monta el socket de Docker (`/var/run/docker.sock`) para
  ejecutar el ETL; es el mecanismo estándar de Ofelia, pero da control
  sobre Docker a ese contenedor.
- `etl_worker` y `etl_pipeline` corren como root dentro del contenedor
  porque en Windows/Docker Desktop las carpetas montadas no siempre son
  escribibles por otro usuario.

## Dominios necesarios

El ETL necesita salida a Internet (HTTPS) hacia estos sitios. Si el
servidor o la red filtran el tráfico, deben estar permitidos.

| Dominio | Uso |
|---|---|
| `datosestimaciones.magyp.gob.ar` | Estimaciones agrícolas (MAGyP) |
| `bccba.sharepoint.com`, `*.sharepoint.com` | Bolsa de Cereales de Córdoba |
| `www.argentina.gob.ar`, `www.energia.gob.ar` | Portal nacional de cuadros tarifarios |
| `oceba.gba.gov.ar` | EDEN, EDEA, EDES, EDELAP |
| `www.epe.santafe.gov.ar`, `epe.santafe.gov.ar` | EPE (página y API de descargas) |
| `www.edenor.com`, `www.edesur.com.ar`, `www.edeaweb.com.ar`, `www.ecsapem.com.ar`, `www.secheep.gob.ar`, `www.epec.com.ar`, `www.dpec.com.ar`, `www.enersa.com.ar`, `recursosyenergia.com.ar`, `www.ejesa.com.ar`, `susepu.jujuy.gob.ar`, `www.edelar.com.ar`, `www.edemsa.com`, `epremendoza.gob.ar`, `energia.misiones.gob.ar`, `www.energiademisiones.com.ar`, `www.epen.gov.ar`, `www.edersa.com.ar`, `www.eprern.gov.ar`, `www.edesa.com.ar`, `oficinavirtualedesal.com.ar`, `epresanjuan.gob.ar`, `spse.ar`, `www.edese.com.ar`, `www.dpe.com.ar`, `www.edetsa.com`, `epre.gov.ar` | Sitios propios de distribuidoras y entes reguladores |
| Opcionales: `ersep.cba.gov.ar`, `energiasanjuan.com.ar`, `spse.gob.ar` | Podrían cubrir ESJ y SPSE (hoy sin dato) |

Algunos sitios bloquean o limitan pedidos desde fuera de Argentina (EPEC
lo hizo durante un tiempo): un servidor en el país tiene mejores chances.

El **navegador** de quien abre el dashboard necesita acceso a
`cdn.plot.ly` (cartografía base de los mapas); sin él, los mapas quedan
en blanco.

## Migrar a la nube

La imagen es la misma para cualquier proveedor. Opciones:

- **VPS o máquina virtual** (lo más simple): igual que en una PC, con
  Docker Compose.
- **Servicios gestionados** (Cloud Run, Azure Container Apps, ECS): el
  dashboard como servicio web y el ETL como tarea programada (Cloud
  Scheduler, EventBridge) en lugar de Ofelia; `data/` en un disco o
  almacenamiento compartido entre ambos.

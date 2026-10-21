# Propuesta: estructura de carpetas para unificar los dos proyectos

> Estado: **fases 1, 2 y 4 aplicadas** (código de biomasa en `src/`,
> tests por tipo, CI, nightly, deploy). Falta la **fase 3**: incorporar
> el código solar en `src/optimia_hv/solar/` (esqueleto ya creado).

## Objetivo

Juntar en un solo repositorio (`marcoeferro/optimia`):

- **Biomasa** (Marco): ETL de rastrojo → energía → dinero, dashboard Streamlit.
- **Solar** (compañera): descarga de clima (NASA POWER, Open-Meteo) y de
  generación real (Growatt), estimación de energía cada 15 min, modelo viejo,
  validación del modelo.

Flujo de trabajo buscado:

1. Cada uno trabaja en **su fork** y abre un **pull request** al repo principal.
2. GitHub Actions corre **lint + tipos + varios tipos de tests + build Docker**.
3. Si todo pasa, el PR se **mergea** a `main`.
4. Cada push a `main` dispara el **deploy** al servidor de **DonWeb**.

---

## Estructura propuesta

```
optimia/
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                  # PR y push: lint, tipos, tests, build de imagen
│   │   ├── deploy.yml              # push a main (tras CI verde): publica imagen y despliega en DonWeb
│   │   └── nightly.yml             # programado: tests contra APIs reales + regresión del modelo
│   ├── CODEOWNERS                  # quién revisa qué carpeta
│   ├── pull_request_template.md    # checklist del PR
│   └── dependabot.yml              # actualiza dependencias y actions
│
├── src/
│   └── optimia_hv/                 # UN solo paquete Python instalable
│       ├── __init__.py
│       ├── comun/                  # código compartido por los dos dominios
│       │   ├── config.py           # lee config/*.yaml y variables de entorno
│       │   ├── logging.py
│       │   ├── http.py             # reintentos, timeouts, caché (ex http_retry.py)
│       │   ├── io.py               # leer/escribir CSV, Parquet, SQLite (ex io_utils.py)
│       │   └── notificaciones.py   # Telegram / webhook
│       │
│       ├── biomasa/                # ex carpeta etl/
│       │   ├── extractors/
│       │   ├── transformers/
│       │   ├── loaders/
│       │   ├── reference/
│       │   └── pipelines/run_biomasa.py
│       │
│       ├── solar/                  # trabajo de la compañera
│       │   ├── extractors/
│       │   │   ├── growatt.py      # histórico, diario, intradía, 15 min
│       │   │   ├── nasa_power.py   # histórico y diario
│       │   │   └── open_meteo.py   # histórico, diario, 15 min y pronóstico 5 días
│       │   ├── modelos/
│       │   │   ├── modelo_15min.py # energía estimada/pronosticada cada 15 min
│       │   │   └── modelo_viejo.py # modelo anterior (línea de base)
│       │   ├── validacion/
│       │   │   ├── metricas.py     # MAE, RMSE, sesgo, error de energía diaria
│       │   │   └── comparativas.py # modelo vs real, modelo nuevo vs viejo
│       │   ├── graficos.py         # funciones de gráficos reutilizables
│       │   └── pipelines/run_solar.py   # ex main_actualizaciones.py
│       │
│       └── dashboard/              # una sola app Streamlit con páginas por dominio
│           ├── app.py
│           ├── data_loader.py
│           ├── charts.py
│           ├── geo/
│           └── vistas/
│               ├── biomasa/        # inicio, resumen, energía, dinero, exploración, auditoría
│               └── solar/          # pronóstico, generación real, validación del modelo
│
├── tests/
│   ├── conftest.py                 # fixtures globales (rutas temporales, config de test)
│   ├── fixtures/                   # datos chicos y fijos para tests
│   │   ├── biomasa/                # CSV/JSON/PDF recortados
│   │   └── solar/                  # respuestas grabadas de Growatt / NASA / Open-Meteo
│   ├── unit/                       # funciones puras, sin red ni disco, < 1 s c/u
│   │   ├── comun/
│   │   ├── biomasa/
│   │   └── solar/
│   ├── integration/                # pipeline completo con fixtures, disco temporal, sin red
│   │   ├── test_pipeline_biomasa.py
│   │   └── test_pipeline_solar.py
│   ├── contract/                   # APIs externas reales: ¿siguen respondiendo con la misma forma?
│   │   ├── test_growatt_api.py
│   │   ├── test_nasa_power_api.py
│   │   └── test_open_meteo_api.py
│   ├── regression/                 # el modelo no empeora: métricas sobre dataset fijo vs umbral
│   │   └── test_modelo_solar_metricas.py
│   └── e2e/                        # humo de punta a punta: dashboard carga, imagen arranca
│       └── test_dashboard_smoke.py
│
├── analisis/                       # exploración y figuras para la tesis (no se despliega)
│   ├── biomasa/                    # notebooks actuales
│   └── solar/                      # ej. campana_2026-09-15.py, comparativas puntuales
│
├── config/
│   ├── paths.yaml                  # rutas, con secciones biomasa: y solar:
│   ├── solar.yaml                  # coordenadas, potencia instalada, IDs de planta, etc.
│   ├── schedule.ini                # cron de Ofelia: un job por dominio
│   └── logging.yml
│
├── data/                           # NO versionado (salvo reference/ chicos)
│   ├── raw/{biomasa,solar}/
│   ├── reference/{biomasa,solar}/
│   ├── interim/
│   ├── processed/
│   └── cache/                      # ex .cache.sqlite (caché HTTP de Open-Meteo)
│
├── outputs/                        # NO versionado: figuras y tablas generadas
│   └── figures/{biomasa,solar}/
│
├── deploy/                         # todo lo que vive en el servidor de DonWeb
│   ├── docker-compose.prod.yml     # usa la imagen publicada (no hace build)
│   ├── nginx/optimia.conf          # proxy inverso + HTTPS hacia Streamlit
│   ├── deploy.sh                   # pull de imagen + up -d + chequeo de salud
│   └── README.md                   # cómo preparar el servidor por primera vez
│
├── docs/                           # documentación (la actual + secciones solar)
│   ├── 02_metodologia/{biomasa,solar}/
│   ├── 04_arquitectura/diagramas/  # ex diagrama_flujo_proyecto / diagrama_flujo_tesis.png
│   └── informes/
│
├── scripts/                        # atajos locales (PowerShell / bash)
├── .env.example                    # nombres de variables secretas, SIN valores
├── .pre-commit-config.yaml         # ruff + formato antes de cada commit
├── CONTRIBUTING.md                 # flujo fork → PR, cómo sincronizar con upstream
├── Dockerfile
├── docker-compose.yml              # desarrollo local
├── Makefile
├── pyproject.toml                  # dependencias por grupo: biomasa, solar, dashboard, dev
└── README.md
```

---

## Para qué sirve cada cosa

### `src/optimia_hv/` — el código que se despliega

- **Layout `src/`**: obliga a instalar el paquete (`pip install -e .`) para
  importarlo. Así los tests prueban lo mismo que corre en el servidor y se
  evitan imports que "andan en mi máquina" porque el script está en la
  carpeta actual (por ejemplo `from growatt_diaria_15min import ...`).
- **Un solo paquete con subpaquetes por dominio** (`biomasa`, `solar`): cada
  uno es dueño de su carpeta, pero comparten config, logging, HTTP,
  notificaciones, Dockerfile, CI y dashboard.
- **`comun/`**: lo que hoy está duplicado o lo estaría (reintentos HTTP,
  lectura/escritura, avisos por Telegram). Regla: algo pasa a `comun/` cuando
  lo usan los dos dominios.
- **`extractors/` → `modelos/` → `validacion/` → `pipelines/`**: separa
  *traer datos*, *calcular* y *orquestar*. Las funciones de cálculo quedan
  puras (reciben un DataFrame, devuelven un DataFrame) y por eso son fáciles
  de testear sin red.
- **`pipelines/run_*.py`**: el punto de entrada que corre el cron. Se exponen
  como comandos en `pyproject.toml` (`optimia-biomasa`, `optimia-solar`).
- **`dashboard/`**: una sola app Streamlit; cada tesis agrega sus páginas en
  `vistas/<dominio>/`. Un solo servicio que desplegar y un solo dominio web.

### `tests/` — un tipo de test por carpeta

| Carpeta | Qué prueba | Red | Cuándo corre | Bloquea el merge |
|---|---|---|---|---|
| `unit/` | funciones sueltas (parseo, cálculo de energía, métricas) | no | cada PR | sí |
| `integration/` | pipeline completo con datos de `fixtures/` y disco temporal | no | cada PR | sí |
| `e2e/` | el dashboard levanta y cada página renderiza; la imagen Docker importa todo | no | cada PR | sí |
| `regression/` | el error del modelo solar sobre un dataset fijo no supera el umbral acordado | no | cada PR | sí |
| `contract/` | Growatt, NASA y Open-Meteo siguen respondiendo con las columnas/unidades esperadas | **sí** | nightly y manual | no (avisa) |

- **`fixtures/`**: respuestas de API grabadas una vez y guardadas recortadas.
  Así los tests de PR no dependen de internet, de credenciales de Growatt ni
  de límites de las APIs, y siempre dan el mismo resultado.
- Se seleccionan con **markers** de pytest (`unit`, `integration`, `e2e`,
  `regression`, `contract`). En `pyproject.toml` se excluye `contract` por
  defecto y el nightly lo corre con `pytest -m contract`.
- Los tests de `contract/` **no** van en el PR porque las APIs pueden caerse
  sin que el código esté mal; si fallaran en el PR bloquearían merges por
  algo ajeno.

### `analisis/` — exploración y figuras de tesis

Scripts y notebooks que generan gráficos puntuales (campana del 15/09,
comparativas de 5 días, mes, etc.). **Importan** funciones de
`src/optimia_hv/` en vez de copiarlas, no se despliegan y no son
obligatorios de testear. Las imágenes que salen de acá van a
`outputs/figures/` (ignorado por git); las que van a la tesis se copian a
`docs/informes/img/`.

### `config/` — parámetros sin tocar código

Rutas, coordenadas de la planta solar, potencia instalada, horarios del
cron. Cambiar un parámetro no requiere rebuild de la imagen.

### `data/` y `outputs/` — fuera de git

Los datos se regeneran desde las fuentes; versionarlos infla el repo y
genera conflictos en cada PR. Sólo se versionan referencias chicas y
estables (`data/reference/`). La caché HTTP (`.cache.sqlite`) pasa a
`data/cache/`.

### `.github/` — CI/CD y reglas de colaboración

- **`ci.yml`**: en cada PR (incluso desde forks) corre lint, mypy, tests
  `unit + integration + e2e + regression` y el build de la imagen. Sin
  secretos.
- **`deploy.yml`**: sólo en push a `main` del repo principal. Construye la
  imagen, la publica en GitHub Container Registry y entra por SSH al
  servidor de DonWeb a correr `deploy/deploy.sh`. Usa secretos
  (`DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`) que los forks no ven.
- **`nightly.yml`**: todas las noches corre `contract/` contra las APIs
  reales y avisa si algo cambió.
- **`CODEOWNERS`**: `src/optimia_hv/solar/` pide revisión de la compañera,
  `src/optimia_hv/biomasa/` de Marco, `comun/`, `dashboard/` y `.github/` de
  los dos.
- **`pull_request_template.md`**: checklist (tests agregados, docs
  actualizadas, no se subieron datos ni secretos).

### `deploy/` — lo que corre en DonWeb

Compose de producción (usa la imagen ya publicada, no compila en el
servidor), configuración de Nginx con HTTPS delante de Streamlit y el script
de deploy con chequeo de salud. Requiere un **Cloud Server (VPS)** con
Docker: un hosting compartido (cPanel/PHP) no puede mantener Streamlit ni el
cron de Ofelia corriendo.

### Archivos de raíz

- **`pyproject.toml`**: un solo archivo de dependencias, con grupos
  (`[biomasa]`, `[solar]`, `[dashboard]`, `[dev]`), configuración de pytest,
  ruff, mypy y coverage.
- **`.env.example`**: lista las variables secretas (usuario/clave de
  Growatt, token de Telegram) sin valores. El `.env` real nunca se sube.
- **`.pre-commit-config.yaml`**: corre ruff antes de cada commit para que el
  CI no falle por formato.
- **`CONTRIBUTING.md`**: cómo forkear, mantener el fork al día con
  `upstream` y abrir el PR.

---

## Dónde va cada archivo de la compañera

| Hoy | Propuesta |
|---|---|
| `datosHistoricos/growatt_historico.py`, `datosDiarios/growatt_diaria.py`, `EstimarEnergia/growatt_diaria_15min.py`, `ValidarModelo/growatt_intradia.py` | `src/optimia_hv/solar/extractors/growatt.py` (una función por granularidad, sin duplicar login/paginado) |
| `datosHistoricos/climaHistorico_NASA.py`, `datosDiarios/climaHistoricoNASA_diario.py` | `src/optimia_hv/solar/extractors/nasa_power.py` |
| `datosHistoricos/climaHistorico_openmeteo.py`, `datosDiarios/climaHistoricoOpenMeteo_diario.py`, `ValidarModelo/climaHistorico_OP_15min.py`, `datosDiarios/pronostico_diario_openMeteo.py`, `EstimarEnergia/pronostico_15min_5days.py` | `src/optimia_hv/solar/extractors/open_meteo.py` (histórico/pronóstico × diario/15 min como parámetros) |
| `EstimarEnergia/energia_pronosticada_15min.py`, `ValidarModelo/estimacionEnergia15min.py` | `src/optimia_hv/solar/modelos/modelo_15min.py` |
| `modeloViejo/calcularModeloViejo.py` | `src/optimia_hv/solar/modelos/modelo_viejo.py` |
| `EstimarEnergia/grafico.py`, `modeloViejo/grafico5dias.py`, `ValidarModelo/graficar_comparativa_5days.py` | funciones en `src/optimia_hv/solar/graficos.py`; la llamada puntual en `analisis/solar/` |
| `ValidarModelo/campana_15sept.py` | `analisis/solar/campana_2026-09-15.py` (y las métricas que calcule, a `solar/validacion/metricas.py`) |
| `main_actualizaciones.py` | `src/optimia_hv/solar/pipelines/run_solar.py` + job en `config/schedule.ini` |
| `*.png` de la raíz | `outputs/figures/solar/` (o `docs/informes/img/` si van a la tesis) |
| `diagrama_flujo_proyecto`, `diagrama_flujo_tesis.png` | `docs/04_arquitectura/diagramas/` |
| `.cache.sqlite` | `data/cache/` (ignorado por git) |
| `__pycache__/` | borrar e ignorar |

## Dónde va cada cosa de Marco

| Hoy | Propuesta |
|---|---|
| `etl/` | `src/optimia_hv/biomasa/` |
| `etl/extractors/http_retry.py`, `etl/extractors/io_utils.py`, `etl/notifications.py` | `src/optimia_hv/comun/` |
| `dashboard/` | `src/optimia_hv/dashboard/` (vistas actuales a `vistas/biomasa/`) |
| `tests/test_*.py` | `tests/unit/biomasa/` o `tests/integration/` según usen disco/pipeline completo; `test_dashboard.py` a `tests/e2e/` |
| `notebooks/` | `analisis/biomasa/` |

---

## Lista de cambios a realizar

Conviene hacerlo en PRs chicos, en este orden, para que el CI quede verde
en cada paso.

### Fase 0 — acuerdos (sin código)

1. Acordar esta estructura, nombres de carpetas e idioma (español, como hoy).
2. Definir los umbrales de error del modelo solar para `regression/`
   (ej. MAE diario máximo).
3. Confirmar el plan de DonWeb: tiene que ser un **Cloud Server/VPS** con
   acceso SSH y Docker.

### Fase 1 — configuración del repo principal

4. Proteger `main`: PR obligatorio, checks requeridos (`tests`, `imagen`),
   al menos 1 aprobación, sin push directo.
5. Activar **auto-merge nativo** de GitHub y cambiar el job `automerge` de
   `ci.yml`: hoy se saltea los PR desde forks
   (`head.repo.full_name == github.repository`) y en PR de forks el
   `GITHUB_TOKEN` es de sólo lectura. Con auto-merge nativo, quien abre el
   PR o el dueño lo habilita y GitHub mergea solo cuando los checks pasan.
   **No** usar `pull_request_target` para esto (ejecuta código del fork con
   permisos de escritura).
6. Agregar `.github/CODEOWNERS`, `.github/pull_request_template.md`,
   `.github/dependabot.yml`, `CONTRIBUTING.md`, `.pre-commit-config.yaml`,
   `.env.example`.
7. Ampliar `.gitignore`: `*.sqlite` fuera de `data/reference/`, `*.png` en
   la raíz, `data/cache/`, `.env`.

### Fase 2 — mover el código de Marco a `src/`

8. `git mv etl src/optimia_hv/biomasa` y `git mv dashboard src/optimia_hv/dashboard`
   (con `git mv` se conserva el historial).
9. Crear `src/optimia_hv/comun/` y mover `http_retry.py`, `io_utils.py`,
   `notifications.py`.
10. Reemplazar imports `etl.` → `optimia_hv.biomasa.` y `dashboard.` →
    `optimia_hv.dashboard.` (unos 40 imports internos).
11. `pyproject.toml`: renombrar el proyecto a `optimia-hv`,
    `packages.find` con `where = ["src"]`, entry points nuevos, grupos de
    dependencias `[biomasa]`, `[solar]`, coverage con
    `source = ["optimia_hv"]`, markers de pytest.
12. `Dockerfile`: `CMD` → `python -m optimia_hv.biomasa.pipelines.run_biomasa`.
13. `docker-compose.yml`: comando del dashboard →
    `streamlit run src/optimia_hv/dashboard/app.py`; el volumen
    `./dashboard` → `./src`.
14. `config/schedule.ini`: actualizar el comando del job `etl-biomasa`.
15. `config/paths.yaml`: rutas por dominio (`data/raw/biomasa`, …).
16. `Makefile`, `scripts/*.ps1`, `ci.yml` (rutas de `ruff check`), `README.md`,
    `llms.txt` y `docs/` con las rutas nuevas.
17. Reorganizar `tests/` en `unit/`, `integration/`, `e2e/` y mover los
    datos de prueba a `tests/fixtures/biomasa/`.

### Fase 3 — incorporar el trabajo de la compañera

18. Ella forkea el repo, crea una rama y copia sus archivos según la tabla
    de arriba.
19. Unificar los scripts duplicados en funciones (un `growatt.py`, un
    `open_meteo.py`, un `nasa_power.py`); sacar el código que corre al
    importar (todo dentro de funciones, y `if __name__ == "__main__":` sólo
    en los `pipelines/`).
20. Sacar credenciales de Growatt y coordenadas hardcodeadas a `.env` /
    `config/solar.yaml`.
21. Mover la caché de Open-Meteo a `data/cache/` (ruta desde config).
22. Agregar sus dependencias al grupo `[solar]` de `pyproject.toml`
    (las que usen hoy: cliente de Open-Meteo, `requests-cache`, cliente de
    Growatt, etc.).
23. Grabar respuestas reales de cada API en `tests/fixtures/solar/` y
    escribir tests `unit/solar/`, `integration/test_pipeline_solar.py`,
    `regression/` y `contract/`.
24. Agregar el job `optimia-solar` a `config/schedule.ini`.
25. Agregar páginas `vistas/solar/` al dashboard.
26. Mover PNG, diagramas y scripts de análisis a `outputs/`, `docs/` y
    `analisis/solar/`.

### Fase 4 — CI/CD completo

27. `ci.yml`: agregar `mypy`, separar pasos por marker
    (`pytest -m "unit or integration or e2e or regression"`), reporte de
    cobertura.
28. `nightly.yml`: `schedule` diario + `workflow_dispatch`, corre
    `pytest -m contract`; necesita los secretos de Growatt en el repo
    principal.
29. `deploy.yml`: en `push` a `main` → build y push de la imagen a
    `ghcr.io/marcoeferro/syngas-optimia-hv` → SSH al servidor → `deploy/deploy.sh`
    → chequeo de salud del dashboard; usar `environment: production` para
    poder pedir aprobación manual si se quiere.
30. Crear `deploy/` (compose de producción, Nginx, script) y preparar el
    servidor de DonWeb una sola vez: Docker, usuario de deploy con clave
    SSH, dominio apuntando al servidor, certificado HTTPS.
31. Cargar secretos en GitHub (`Settings → Secrets and variables → Actions`):
    `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, credenciales de Growatt,
    `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.

# Instalación

> Cómo poner el sistema a funcionar en una PC o servidor. Hay dos caminos:
> **con Docker** (recomendado para usarlo) o **con Python** (para
> desarrollar).

## Opción A — Con Docker (recomendado)

Docker empaqueta el programa con todo lo que necesita; no hay que instalar
Python ni librerías.

### Requisitos

- **Windows o Mac**: [Docker Desktop](https://www.docker.com/products/docker-desktop/).
- **Linux / servidor**: Docker Engine y el plugin Docker Compose.
- Git (para descargar el proyecto), o descargar el ZIP desde GitHub.
- Salida a Internet hacia las fuentes de datos (ver
  [dominios necesarios](../04_arquitectura/despliegue.md#dominios-necesarios)).

### Pasos

1. Descargar el proyecto:

   ```bash
   git clone https://github.com/marcoeferro/optimia.git
   cd optimia
   ```

2. Levantar todo (ETL programado + dashboard):

   - Windows (PowerShell): `.\scripts\Start-Stack.ps1`
   - Linux / Mac: `docker compose up -d --build` (o `make docker-up`)

   La primera vez tarda varios minutos porque construye la imagen.

3. Correr el ETL por primera vez, sin esperar al horario programado
   (tarda unos minutos):

   - Windows: `.\scripts\Run-Etl.ps1`
   - Linux / Mac: `make docker-etl` o
     `docker compose --profile etl run --rm etl_pipeline`

4. Abrir el dashboard en <http://localhost:8501>.

Desde entonces el ETL corre solo todos los días a las 06:00 (se cambia en
`config/schedule.ini`, ver [despliegue](../04_arquitectura/despliegue.md#horario-del-etl)).

### Actualizar a una versión nueva

```bash
git pull
docker compose up -d --build      # Windows: .\scripts\Start-Stack.ps1
```

El código del ETL está dentro de la imagen: sin `--build` se seguiría
usando la versión anterior.

### Detener

- Windows: `.\scripts\Stop-Stack.ps1`
- Linux / Mac: `docker compose down` (o `make docker-down`)

Los datos quedan en la carpeta `data/`.

## Opción B — Con Python (desarrollo)

### Requisitos

- Python 3.11 o superior.
- Git.

### Pasos

```bash
git clone https://github.com/marcoeferro/optimia.git
cd optimia

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate  (o .\activate.ps1)

pip install -e ".[dev]"            # o: make install-dev
```

Extras disponibles: `[dashboard]` (ETL + dashboard), `[dev]` (además
pytest, ruff, mypy). Sin extras se instala sólo el ETL.

Después:

```bash
python -m optimia_hv.biomasa.pipelines.run_biomasa          # o: make etl          → genera los datos
streamlit run src/optimia_hv/dashboard/app.py           # o: make dashboard    → abre el dashboard
pytest                                   # o: make test         → corre los tests
```

En Windows también: `.\scripts\Run-Etl.ps1 -Local` corre el ETL con el
Python del `.venv`.

## Siguiente paso

- Cómo correr el ETL y sus opciones: [ejecutar el ETL](ejecutar_etl.md).
- Cómo usar el dashboard: [guía del dashboard](dashboard.md).
- Si algo falla: [solución de problemas](solucion_de_problemas.md).

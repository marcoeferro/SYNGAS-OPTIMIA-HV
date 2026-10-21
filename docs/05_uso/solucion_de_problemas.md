# Solución de problemas

> Problemas que ya ocurrieron, su causa y cómo resolverlos.

## Dashboard

### Una página dice que hay que ejecutar el ETL, o aparece `KeyError: 'kwh_generados'`

**Causa**: el ETL nunca corrió, o corrió con una versión vieja del código
que no calculaba energía y dinero. En Docker, el código del ETL está
dentro de la imagen: si se actualizó el repositorio (`git pull`) pero no
se reconstruyó la imagen, el ETL sigue corriendo la versión anterior.

**Solución**: reconstruir y correr el ETL:

- Windows: `.\scripts\Run-Etl.ps1` (reconstruye la imagen solo).
- Linux/Mac: `make docker-etl`, o `docker compose up -d --build` y
  después `docker compose --profile etl run --rm etl_pipeline`.

Después recargar la página. En **Inicio → Archivos de datos** se ve si la
fecha de los archivos cambió.

### Los datos no se actualizan (o aparece "Los datos tienen N días")

- El cartel aparece cuando el ETL no publicó resultados en las últimas 48
  horas (`DATOS_VIEJOS_HORAS`).
- Ver la fecha en **Inicio → Archivos de datos**.
- Si es vieja, revisar que el scheduler esté corriendo
  (`docker compose ps`) y el log (`logs/pipeline.log`).
- Si el ETL corrió con `--estricto` y hubo alertas, no publica datos
  nuevos a propósito: revisar las alertas en el log.

### Los mapas aparecen en blanco

El navegador no puede descargar la cartografía de `cdn.plot.ly` (red
corporativa, bloqueador, sin Internet). Permitir ese dominio.

### Un departamento no aparece en el mapa

Algunos departamentos no tienen polígono en GADM o vienen como "sin
definir" en la fuente. Están listados en **Auditoría de datos → Cobertura
de mapas**; sus valores sí cuentan en los totales y tablas.

### Una provincia tiene energía pero no dinero

Su distribuidora no tiene tarifa (Santa Cruz, Tierra del Fuego,
Tucumán, Chubut). Ver [tarifas eléctricas](../03_datos/tarifas_electricas.md#distribuidoras-sin-dato)
y la carga manual de cuadros.

## ETL

### `503 Service Unavailable` u otros errores de descarga

Errores temporales del servidor (SharePoint de la Bolsa de Córdoba
responde 503 cuando limita pedidos). El ETL reintenta solo, hace una
segunda pasada y, si sigue fallando, usa la última descarga. No hace falta
hacer nada salvo que se repita varios días: en ese caso, verificar que el
sitio funcione en el navegador.

### El ETL se detiene con `Cultivos sin mapeo en CROP_TAXONOMY`

Una fuente agregó un cultivo que no está en la taxonomía. Agregarlo en
`src/optimia_hv/biomasa/reference/crop_taxonomy.py` (y, si corresponde, sus coeficientes en
`data/reference/ic_fr.csv`; ver [metodología](../02_metodologia/metodologia.md)).

### `Invariante rota: …`

Un control interno detectó un resultado imposible (registro repetido,
valores negativos, producción perdida). Es un error de código o de datos
de la fuente: no se publican resultados. Revisar el log y abrir un issue.

### Hay alertas de calidad

Ver [tests y controles](../06_calidad/tests_y_controles.md#qué-hacer-ante-una-alerta).

### Una distribuidora quedó como `fallback_previous` o `sin_dato`

Su sitio no respondió o cambió de formato. Ver
[tarifas eléctricas](../03_datos/tarifas_electricas.md); se puede cargar
el cuadro a mano.

## Docker y Windows

### `open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified`

Docker Desktop no está corriendo. Abrirlo y esperar a que diga "Engine
running". `Run-Etl.ps1` y `Start-Stack.ps1` intentan abrirlo solos y
esperan hasta 3 minutos. Alternativa: `.\scripts\Run-Etl.ps1 -Local`.

### PowerShell no deja ejecutar los scripts

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\Run-Etl.ps1
```

### El ETL programado no corre a la hora esperada

- El horario de Ofelia lleva **segundos al principio** (6 campos):
  `0 0 6 * * *` es 06:00. Con 5 campos (`0 6 * * *`) se interpreta mal.
- La hora es la de `TZ` (por defecto Buenos Aires).
- Después de editar `config/schedule.ini`: `docker compose restart scheduler`.

### El disco se llena

- Imágenes Docker viejas: `docker image prune -f --filter label=project=etl-biomasa`.
- Descargas viejas en `data/raw/`: ver
  [limpieza del disco](../04_arquitectura/ciclo_de_vida_de_los_datos.md#limpieza-del-disco).

### Errores de permisos al escribir en `data/` o `logs/`

En Windows, las carpetas montadas a veces no son escribibles por el
usuario del contenedor; por eso los servicios del ETL corren como root.
Si se cambió `user:` en `docker-compose.yml`, volver a `"0:0"`.

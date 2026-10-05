# Ejecuta el pipeline ETL una vez (sin esperar al cron).
#
# Uso (desde la raíz del repo, en PowerShell):
#   .\scripts\Run-Etl.ps1                    # en Docker (inicia Docker Desktop si hace falta)
#   .\scripts\Run-Etl.ps1 -Local             # sin Docker, con el Python del .venv
#   .\scripts\Run-Etl.ps1 -Local -SkipExtract -SkipTarifas
#
# Si la política de ejecución bloquea el script:
#   powershell -ExecutionPolicy Bypass -File .\scripts\Run-Etl.ps1 -Local

[CmdletBinding()]
param(
    [switch]$Local,         # Corre con Python local en lugar de Docker
    [switch]$SkipExtract,   # No descarga CBA/MAGyP; usa lo último en data/raw
    [switch]$SkipTarifas    # No descarga cuadros tarifarios
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root
. (Join-Path $PSScriptRoot "_Common.ps1")

$etlArgs = @("-m", "etl.pipelines.run_etl", "--config", "config/paths.yaml")
if ($SkipExtract) { $etlArgs += "--skip-extract" }
if ($SkipTarifas) { $etlArgs += "--skip-tarifas" }

if ($Local) {
    $python = Join-Path $Root ".venv\Scripts\python.exe"
    if (-not (Test-Path $python)) { $python = "python" }
    Write-Host "Ejecutando ETL local con $python ..." -ForegroundColor Cyan
    & $python @etlArgs
} else {
    Start-DockerDesktopIfNeeded
    # La imagen guarda el código del ETL (no se monta como volumen): sin
    # reconstruirla se ejecuta la versión del último build. Docker reutiliza
    # las capas sin cambios, así que si el código no cambió tarda segundos.
    Write-Host "Actualizando la imagen del ETL..." -ForegroundColor Cyan
    docker compose --profile etl build etl_pipeline
    if ($LASTEXITCODE -ne 0) { throw "docker compose build falló con código $LASTEXITCODE" }
    # Cada build que cambia el código deja la imagen anterior sin etiqueta
    # ("dangling"); se borran (sólo las de este proyecto) para no llenar el
    # disco del servidor.
    docker image prune -f --filter "label=project=etl-biomasa" | Out-Null
    Write-Host "Ejecutando ETL en Docker (one-shot)..." -ForegroundColor Cyan
    docker compose --profile etl run --rm etl_pipeline python @etlArgs
}
if ($LASTEXITCODE -ne 0) { throw "ETL falló con código $LASTEXITCODE" }
Write-Host "ETL finalizado." -ForegroundColor Green

# Arranca worker ETL + scheduler (cron) + dashboard.
# Requisito: Docker Desktop (se inicia automáticamente si está instalado).
# Uso (desde la raíz del repo, en PowerShell):
#   .\scripts\Start-Stack.ps1

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root
. (Join-Path $PSScriptRoot "_Common.ps1")

Start-DockerDesktopIfNeeded

Write-Host "Construyendo imagen y levantando servicios..." -ForegroundColor Cyan
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { throw "docker compose up falló con código $LASTEXITCODE" }

Write-Host ""
Write-Host "Stack en ejecución:" -ForegroundColor Green
Write-Host "  - Dashboard:  http://localhost:8501"
Write-Host "  - Scheduler:  lee config\schedule.ini (cron del ETL)"
Write-Host "  - Worker ETL: biomasa_etl_worker"
Write-Host ""
Write-Host "Para cambiar el horario del ETL, editá config\schedule.ini y ejecutá:"
Write-Host "  docker compose restart scheduler"
Write-Host ""
docker compose ps

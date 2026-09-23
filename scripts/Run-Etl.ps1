# Ejecuta el pipeline ETL una vez (sin esperar al cron).
# Uso (desde la raíz del repo, en PowerShell):
#   .\scripts\Run-Etl.ps1

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

Write-Host "Ejecutando ETL (one-shot)..." -ForegroundColor Cyan
docker compose --profile etl run --rm etl_pipeline
if ($LASTEXITCODE -ne 0) { throw "ETL falló con código $LASTEXITCODE" }
Write-Host "ETL finalizado." -ForegroundColor Green

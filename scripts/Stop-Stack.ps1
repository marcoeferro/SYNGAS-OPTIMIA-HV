# Detiene todos los servicios del compose.
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root
docker compose down
Write-Host "Stack detenido." -ForegroundColor Green

# Detiene todos los servicios del compose.
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root
. (Join-Path $PSScriptRoot "_Common.ps1")

if (-not (Test-DockerEngine)) {
    Write-Host "Docker no está corriendo: no hay servicios que detener." -ForegroundColor Yellow
    exit 0
}
docker compose down
if ($LASTEXITCODE -ne 0) { throw "docker compose down falló con código $LASTEXITCODE" }
Write-Host "Stack detenido." -ForegroundColor Green

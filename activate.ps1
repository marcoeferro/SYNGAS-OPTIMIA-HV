# activate-venv.ps1
# Script para activar el entorno virtual de Python en PowerShell

$venvPath = Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1"

if (Test-Path $venvPath) {
    Write-Host "Activando entorno virtual en $venvPath..."
    & $venvPath
} else {
    Write-Error "No se encontró el entorno virtual en: $venvPath"
}

# Funciones compartidas por los scripts de PowerShell del proyecto.
# Se cargan con:  . (Join-Path $PSScriptRoot "_Common.ps1")

function Test-DockerEngine {
    # True si el motor de Docker responde. "docker info" escribe en stderr
    # cuando el motor está apagado; se evalúa sólo el código de salida.
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & docker info *> $null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    } finally {
        $ErrorActionPreference = $prev
    }
}

function Start-DockerDesktopIfNeeded {
    param([int]$TimeoutSeconds = 180)

    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw ("No se encontró el comando 'docker'. Instalá Docker Desktop " +
               "(https://www.docker.com/products/docker-desktop/) o usá -Local " +
               "para correr el ETL con Python sin Docker.")
    }
    if (Test-DockerEngine) { return }

    $candidates = @()
    if ($env:ProgramFiles) { $candidates += Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe" }
    if ($env:LOCALAPPDATA) { $candidates += Join-Path $env:LOCALAPPDATA "Docker\Docker Desktop.exe" }
    $exe = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $exe) {
        throw ("El motor de Docker no está corriendo y no se encontró Docker Desktop " +
               "para iniciarlo. Abrilo a mano y reintentá, o usá -Local.")
    }

    Write-Host "Docker Desktop no está corriendo. Iniciándolo..." -ForegroundColor Yellow
    Start-Process -FilePath $exe | Out-Null
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 5
        if (Test-DockerEngine) {
            Write-Host "Docker Desktop listo." -ForegroundColor Green
            return
        }
        Write-Host "  esperando al motor de Docker..."
    }
    throw ("Docker Desktop no respondió en $TimeoutSeconds s. Verificá que haya " +
           "terminado de iniciar (ícono de la ballena en verde) y reintentá, o usá -Local.")
}

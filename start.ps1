# One-command dev startup for PlantPal: makes sure the mango-postgres
# container is running, then opens the backend (FastAPI/uvicorn) and frontend
# (static file server) each in their own PowerShell window.
#
# First-time setup (venv, pip install, schema, trained models, LRIS/CDSE keys
# in backend/.env) still has to be done once by hand - see backend/README.md.
# This script only automates the "start it up again" step.

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

$backendPort = 8001   # must match API_BASE in frontend/js/api.js
$frontendPort = 8000  # must match the root README's `http.server 8000`

# 1. Postgres container (create once by hand per backend/README.md; this just
#    starts it if it exists but is stopped).
$containerName = "mango-postgres"
$existing = docker ps -a --filter "name=$containerName" --format "{{.Names}}"
if (-not $existing) {
  Write-Host "No '$containerName' container found. Create it first, e.g.:" -ForegroundColor Yellow
  Write-Host "  docker run -d --name mango-postgres -e POSTGRES_USER=mango -e POSTGRES_PASSWORD=mango -e POSTGRES_DB=mango -p 5433:5432 postgres:16"
  Write-Host "then apply backend/sql/schema.sql. See backend/README.md#setup." -ForegroundColor Yellow
  exit 1
}
$running = docker ps --filter "name=$containerName" --format "{{.Names}}"
if (-not $running) {
  Write-Host "Starting $containerName..."
  docker start $containerName | Out-Null
  Start-Sleep -Seconds 2
} else {
  Write-Host "$containerName already running."
}

if (-not (Test-Path "$root\backend\.venv\Scripts\Activate.ps1")) {
  Write-Host "backend/.venv not found - run the one-time setup in backend/README.md first." -ForegroundColor Red
  exit 1
}
if (-not (Test-Path "$root\backend\.env")) {
  Write-Host "backend/.env not found - copy backend/.env.example to backend/.env and fill it in first." -ForegroundColor Red
  exit 1
}

function Test-PortOpen($port) {
  return [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}

# 2. Backend
if (Test-PortOpen $backendPort) {
  Write-Host "Port $backendPort is already in use - assuming the backend is already running, not starting another." -ForegroundColor Yellow
} else {
  Write-Host "Starting backend on http://127.0.0.1:$backendPort ..."
  Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$root\backend'; . .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --port $backendPort"
  )
}

# 3. Frontend (static file server - ES modules need real HTTP, not file://)
if (Test-PortOpen $frontendPort) {
  Write-Host "Port $frontendPort is already in use by something else." -ForegroundColor Red
  Write-Host "Free it (check with: Get-NetTCPConnection -LocalPort $frontendPort -State Listen) or edit `$frontendPort in this script." -ForegroundColor Red
} else {
  Write-Host "Starting frontend on http://127.0.0.1:$frontendPort ..."
  Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$root'; py -m http.server $frontendPort"
  )
}

Start-Sleep -Seconds 2
Write-Host ""
Write-Host "Backend docs:  http://127.0.0.1:$backendPort/docs"
Write-Host "Frontend:      http://127.0.0.1:$frontendPort"
Write-Host "(Each opened in its own window - close those windows, or Ctrl+C in them, to stop.)"
Start-Process "http://127.0.0.1:$frontendPort"

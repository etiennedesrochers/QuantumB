#Requires -Version 5.1
# Starts the FastAPI backend (:8000) in its own window, then the Express UI (:3000).
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

Start-Process -FilePath $python -ArgumentList "-m", "quantumb.api.main", "--port", "8000" -WorkingDirectory $root

Set-Location (Join-Path $root "node_app")
if (-not (Test-Path "node_modules")) { npm install --no-audit --no-fund }
$env:API_BASE = "http://127.0.0.1:8000"
npm start

# XNNOV Selection Tool - Web Server Startup (PowerShell)
# This script starts the Flask web server for the Selection Tool

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "XNNOV Selection Tool - Web Server" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Move to repo root (one level up from this scripts\ folder)
$APP_DIR = Split-Path -Parent $PSScriptRoot
Set-Location $APP_DIR

# Activate venv if it exists
if (Test-Path "venv\Scripts\Activate.ps1") {
    Write-Host "Activating virtual environment..." -ForegroundColor Green
    & "venv\Scripts\Activate.ps1"
    Write-Host ""
}

# Start the web server
Write-Host "Starting web server on http://localhost:5000" -ForegroundColor Green
Write-Host ""
Write-Host "Web Interface: http://localhost:5000" -ForegroundColor Yellow
Write-Host "API Endpoint:  http://localhost:5000/api/generate" -ForegroundColor Yellow
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

python src\web\web_server.py --host 127.0.0.1 --port 5000

# ============================================================
# QuantumB - Setup and Launch Script (PowerShell)
# For non-programmer users
# ============================================================

Write-Host ""
Write-Host "Starting QuantumB environment setup..." -ForegroundColor Green
Write-Host ""

# Check if Python is installed
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Found: $pythonVersion"
} catch {
    Write-Host "ERROR: Python is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install Python 3.9+ from https://www.python.org" -ForegroundColor Yellow
    Write-Host "Make sure to check 'Add Python to PATH' during installation"
    Read-Host "Press Enter to exit"
    exit 1
}

# Get the current directory
$APP_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$VENV_DIR = Join-Path $APP_DIR "venv"

# Create virtual environment if it doesn't exist
if (-not (Test-Path $VENV_DIR)) {
    Write-Host "Creating Python virtual environment..." -ForegroundColor Yellow
    python -m venv $VENV_DIR
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to create virtual environment" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& "$VENV_DIR\Scripts\Activate.ps1"

# Install/upgrade pip
Write-Host "Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip | Out-Null

# Install requirements
Write-Host "Installing required packages..." -ForegroundColor Yellow
Write-Host "(This may take a few minutes on first run)"
pip install -q -r "$APP_DIR\requirements.txt"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to install required packages" -ForegroundColor Red
    Write-Host "Please check your internet connection"
    Read-Host "Press Enter to exit"
    exit 1
}

# Change to app directory to ensure correct working directory for file paths
Set-Location $APP_DIR

# Run the application
Write-Host ""
Write-Host "Launching QuantumB..." -ForegroundColor Green
Write-Host ""
python app.py

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Application failed to start" -ForegroundColor Red
    Read-Host "Press Enter to exit"
}

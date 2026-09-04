@echo off
REM Starts the FastAPI backend (:8000) in its own window, then the Express UI (:3000).
cd /d "%~dp0.."
set "PYTHON=%CD%\.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

start "QuantumB API" "%PYTHON%" -m quantumb.api.main --port 8000

cd node_app
if not exist node_modules npm install --no-audit --no-fund
set API_BASE=http://127.0.0.1:8000
npm start

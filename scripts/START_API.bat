@echo off
REM Starts the new QuantumB FastAPI server (http://127.0.0.1:8000, docs at /docs).
cd /d "%~dp0.."
python -m quantumb.api.main --port 8000 %*
pause

@echo off
REM XNNOV Selection Tool - Web Server Startup
REM This script starts the Flask web server for the Selection Tool

echo.
echo ========================================
echo XNNOV Selection Tool - Web Server
echo ========================================
echo.

REM Move to repo root (one level up from this scripts\ folder)
cd /d "%~dp0.."

REM Activate venv if it exists
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
    echo Virtual environment activated
    echo.
)

REM Start the web server
echo Starting web server on http://localhost:5000
echo.
echo Web Interface: http://localhost:5000
echo API Endpoint: http://localhost:5000/api/generate
echo.
echo Press Ctrl+C to stop the server
echo.

python src\web\web_server.py --host 127.0.0.1 --port 5000

pause

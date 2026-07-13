@echo off
REM ============================================================
REM QuantumB - Setup and Launch Script
REM For non-programmer users
REM ============================================================

echo.
echo Starting QuantumB environment setup...
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.9+ from https://www.python.org
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

REM Get the current directory
set APP_DIR=%~dp0

REM Define virtual environment path
set VENV_DIR=%APP_DIR%venv

REM Create virtual environment if it doesn't exist
if not exist "%VENV_DIR%" (
    echo Creating Python virtual environment...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
)

REM Activate virtual environment
echo Activating virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)

REM Install/upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip >nul 2>&1

REM Install requirements
echo Installing required packages...
echo (This may take a few minutes on first run)
pip install -q -r "%APP_DIR%requirements.txt"
if errorlevel 1 (
    echo ERROR: Failed to install required packages
    echo Please check your internet connection
    pause
    exit /b 1
)

REM Change to app directory to ensure correct working directory for file paths
cd /d "%APP_DIR%"

REM Run the application
echo.
echo Launching QuantumB...
echo.
python app.py

REM Pause if there's an error
if errorlevel 1 (
    echo.
    echo ERROR: Application failed to start
    pause
)

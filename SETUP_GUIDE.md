# Starting QuantumB - Quick Setup Guide

Follow these simple steps to run the application:

## Prerequisites
- **Python 3.9 or later** must be installed on your computer
  - Download from: https://www.python.org/downloads/
  - **Important**: During installation, check the box "Add Python to PATH"

## Option 1: Simple Batch File (Recommended for Windows)

1. Find the file named **`START_APP.bat`** in the QuantumB folder
2. **Double-click** `START_APP.bat`
3. Wait for the setup to complete (first run takes 2-5 minutes)
4. The application will launch automatically

## Option 2: PowerShell Script (Windows)

1. Right-click the file **`START_APP.ps1`**
2. Select **"Run with PowerShell"**
3. Wait for the setup to complete
4. The application will launch automatically

**Note**: If you get an error about execution policy, follow the on-screen instructions

## Troubleshooting

### "Python is not installed or not in PATH"
- Install Python from https://www.python.org
- **Important**: Check "Add Python to PATH" during installation
- Restart your computer after installation
- Try again

### Script won't run / Permission denied
- Make sure the script file is not marked as read-only
- Try right-clicking the script and selecting "Run as Administrator"

### Application won't start
- Check your internet connection (first run downloads packages)
- Try deleting the `venv` folder and running the script again
- Check that you have at least 500MB of free disk space

## What the script does

1. ✓ Checks if Python is installed
2. ✓ Creates a virtual environment (isolated Python setup)
3. ✓ Installs all required packages
4. ✓ Launches the QuantumB application

The virtual environment is created only once. Subsequent runs will be much faster.

## Running the app again later

Just double-click `START_APP.bat` (or run `START_APP.ps1`) again - everything will already be set up!

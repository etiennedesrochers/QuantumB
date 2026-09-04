#Requires -Version 5.1
# Starts the new QuantumB FastAPI server (http://127.0.0.1:8000, docs at /docs).
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
python -m quantumb.api.main --port 8000 @args

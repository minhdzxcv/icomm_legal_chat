$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

if (-not (Test-Path '.venv')) {
    Write-Host "Virtual env not found. Running setup first..."
    .\setup.ps1
}

.\.venv\Scripts\Activate.ps1
uvicorn api:app --host 0.0.0.0 --port 8000

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

if (-not (Test-Path '.venv')) {
    python -m venv .venv
}

.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt

Write-Host "Setup complete."
Write-Host "Run API: .\\run_api.ps1"
Write-Host "Run CLI: python main.py --question \"Quy dinh bau cu dai bieu HĐND cap tinh\""

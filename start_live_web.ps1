$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    py -3 -m venv .venv
}
& .\.venv\Scripts\python.exe -m pip install --disable-pip-version-check -r requirements.txt
if (-not $env:PRICE_SERVER) { $env:PRICE_SERVER = "http://127.0.0.1:3333" }
if (-not $env:WEB_PORT) { $env:WEB_PORT = "3690" }
Start-Process "http://127.0.0.1:$env:WEB_PORT"
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port $env:WEB_PORT

# Create a local virtual environment on first use, then start the lab on http://127.0.0.1:8000
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
  python -m venv .venv
  & $python -m pip install --quiet -r requirements.txt
}
$port = if ($env:PORT) { $env:PORT } else { '8000' }
& $python -m uvicorn ethics_lab.app:app --host 127.0.0.1 --port $port

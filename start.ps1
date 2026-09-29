$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
conda run --no-capture-output -n gpu_env python -m uvicorn ethics_lab.app:app --host 127.0.0.1 --port 8000

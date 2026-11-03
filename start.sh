#!/usr/bin/env bash
# Create a local virtual environment on first use, then start the lab on http://127.0.0.1:8000
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
  .venv/bin/python -m pip install --quiet -r requirements.txt
fi
exec .venv/bin/python -m uvicorn ethics_lab.app:app --host 127.0.0.1 --port "${PORT:-8000}"

#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
  .venv/bin/python -m pip install -r requirements.lock.txt
fi
if [ ! -d node_modules ]; then
  npm ci
fi
npm run build
printf '\nOpen http://localhost:8008 in your browser. Stop with Control+C.\n\n'
exec .venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8008 --no-access-log

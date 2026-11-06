#!/bin/sh
set -eu
cd "$(dirname "$0")"

ngrok_bin=${NGROK_BIN:-ngrok}
if ! command -v "$ngrok_bin" >/dev/null 2>&1; then
  printf 'Install ngrok and connect your free account before running this script.\n'
  exit 1
fi
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
  .venv/bin/python -m pip install -r requirements.lock.txt
fi
if [ ! -d node_modules ]; then npm ci; fi
npm run build

# Do not stop or replace another application that is already using this port.
.venv/bin/python - <<'PY'
import socket
with socket.socket() as sock:
    try:
        sock.bind(('127.0.0.1', 8008))
    except OSError:
        raise SystemExit('Port 8008 is already in use. If the assignment is already running, use its current link; otherwise stop that server first.')
PY
review_url=$(.venv/bin/python - <<'PY'
from backend.main import Settings
cfg = Settings.read()
if cfg.missing() or not cfg.secure_cookies:
    raise SystemExit('Set a valid public HTTPS Salesforce callback in .env first.')
print(cfg.origin)
PY
)

app_pid=''
tunnel_pid=''
cleanup() {
  trap - EXIT INT TERM
  if [ -n "$tunnel_pid" ]; then kill "$tunnel_pid" 2>/dev/null || true; fi
  if [ -n "$app_pid" ]; then kill "$app_pid" 2>/dev/null || true; fi
}
trap cleanup EXIT INT TERM
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8008 --no-access-log &
app_pid=$!
.venv/bin/python - <<'PY'
import time
from urllib.request import urlopen
for attempt in range(40):
    try:
        with urlopen('http://localhost:8008/api/session', timeout=1) as response:
            if response.status == 200:
                break
    except OSError:
        time.sleep(.25)
else:
    raise SystemExit('The local server did not start.')
PY

printf '\nReview URL: %s\nKeep this window open and your Mac awake. Control+C stops both processes.\n\n' "$review_url"
if [ -n "${NGROK_CONFIG:-}" ]; then
  "$ngrok_bin" http 8008 --url "$review_url" --inspect=false --config "$NGROK_CONFIG" &
else
  "$ngrok_bin" http 8008 --url "$review_url" --inspect=false &
fi
tunnel_pid=$!
wait "$tunnel_pid"

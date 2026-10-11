#!/usr/bin/env bash
# Sprint 13 real-browser smoke (reference-viewer.html). From the repo root: bash verification/browser/run_smoke.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
WAQT_CORS_ORIGINS=http://localhost:8080 python -m uvicorn waqt.api:app --port 8000 --log-level warning & API=$!
(cd apps/web && python -m http.server 8080 --bind 127.0.0.1 >/dev/null 2>&1) & WEB=$!
trap 'kill $API $WEB 2>/dev/null || true' EXIT
for i in $(seq 1 40); do curl -sf localhost:8000/v1/health >/dev/null && break; sleep 0.5; done
(cd verification/browser && node run_smoke.mjs)

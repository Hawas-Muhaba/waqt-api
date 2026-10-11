#!/usr/bin/env bash
# Real-browser verification of apps/web (live-demo + Experience Lab). From the repo root:  bash verification/browser/run_web_option_b.sh
# Prereq: cd verification/browser && npm install
set -euo pipefail
cd "$(dirname "$0")/../.."
WAQT_CORS_ORIGINS=http://localhost:8080 python -m uvicorn waqt.api:app --port 8000 --log-level warning & API=$!
(cd apps/web && python -m http.server 8080 --bind 127.0.0.1 >/dev/null 2>&1) & WEB=$!
trap 'kill $API $WEB 2>/dev/null || true' EXIT
for i in $(seq 1 40); do curl -sf localhost:8000/v1/health >/dev/null && break; sleep 0.5; done
(cd verification/browser && node run_web_option_b.mjs)

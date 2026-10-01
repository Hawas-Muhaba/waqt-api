#!/usr/bin/env bash
# Sprint 14 real-browser verification. From the repo root:  bash verification/browser/run_sprint14.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
python verification/browser/fake_control.py > /tmp/fake.url & FAKE=$!
sleep 1.5; BASE=$(cat /tmp/fake.url)
WAQT_CORS_ORIGINS=http://localhost:8080 WAQT_ALADHAN_BASE_URL="$BASE" python -m uvicorn waqt.api:app --port 8000 --log-level warning & API=$!
(cd apps/web && python -m http.server 8080 --bind 127.0.0.1 >/dev/null 2>&1) & WEB=$!
trap 'kill $FAKE $API $WEB 2>/dev/null || true' EXIT
for i in $(seq 1 40); do curl -sf localhost:8000/v1/health >/dev/null && break; sleep 0.5; done
(cd verification/browser && node run_sprint14.mjs)

# verification/ — Sprint 13 real-stack checks

Nothing here is a stub: real uvicorn + FastAPI on real sockets, and a real (headless) Chrome.

| Script | What it proves | Run |
|---|---|---|
| `live_stack_check.py` | `/v1/version` + `/v1/health`; CORS off by default and on with `WAQT_CORS_ORIGINS` (incl. preflight, error responses); validation/error envelopes; live API == `sdk_conformance_vectors.json` (21 vectors); vector stamp == running engine. Writes `results/live_stack_check.json`. | `python verification/live_stack_check.py` |
| `browser/run_smoke.mjs` | `apps/web/index.html` in real Chrome against the real API: the `apps/web/tests/manual_smoke.md` checklist plus Maghrib/next-event boundary transitions, geolocation granted/denied, polar, errors, loading, narrow viewport, CORS positive **and negative** control. Writes `browser/results/browser_smoke_results.json`. | see below |

## Browser run

```bash
cd verification/browser && npm install puppeteer-core @sparticuz/chromium   # Chromium binary comes from the npm package
WAQT_CORS_ORIGINS=http://localhost:8080 python -m uvicorn waqt.api:app --port 8000 &   # from repo root
python -m http.server 8080 --directory apps/web &                                       # from repo root
node run_smoke.mjs
```

Notes
* `@sparticuz/chromium` launches with `--disable-web-security`; the harness strips it (and the
  site-isolation flags). Leaving it on makes every CORS check pass vacuously. Check `1d` is the
  negative control (a page on `127.0.0.1:8080` must NOT be able to read the API).
* Boundary tests shift the *page's* clock (`Date.now`/`new Date()`) and ask the API for the same
  shifted instant, so Maghrib can be reached in seconds. The page code is untouched; the real API answers.
* Geolocation "granted" uses Chrome's permission override + `setGeolocation`; "denied" is the default
  headless behaviour (no grant).

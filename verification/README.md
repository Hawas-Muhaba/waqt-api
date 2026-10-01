# verification/ — real-stack checks (Sprint 13, extended in Sprint 14)

Nothing here is a stub: real uvicorn + FastAPI on real sockets, and a real (headless) Chrome.

| Script | What it proves | Run |
|---|---|---|
| `live_stack_check.py` | `/v1/version` + `/v1/health`; CORS off by default and on with `WAQT_CORS_ORIGINS` (incl. preflight, error responses); validation/error envelopes; live API == `sdk_conformance_vectors.json` (21 vectors); vector stamp == running engine. Writes `results/live_stack_check.json`. | `python verification/live_stack_check.py` |
| `browser/run_smoke.mjs` | `apps/web/index.html` in real Chrome against the real API: the `apps/web/tests/manual_smoke.md` checklist plus Maghrib/next-event boundary transitions, geolocation granted/denied, polar, errors, loading, narrow viewport, CORS positive **and negative** control. Writes `browser/results/browser_smoke_results.json`. | see below |

| `fake_aladhan.py` | (Sprint 14) a local stand-in for AlAdhan `gToH` on a real TCP socket, with switchable failure modes (500, 429, garbage, 404, redirect, oversize, wrong echoed date, delay). Lets the API's *real* outbound HTTP path be exercised without the third-party service. Not evidence about the live service. | `python verification/fake_aladhan.py` |
| `vector_additivity_check.py` | (Sprint 14) proves an API change is additive: every value recorded in `sdk_conformance_vectors.json` must still be present and equal in the live app's response (only `api_version`/`generated_at` may move; the one list allowed to grow is the provider catalog). Run **before** regenerating vectors. | `python verification/vector_additivity_check.py` |
| `live_stack_check.py` (S14 section) | live Hijri provider, provenance, fallback, health/version, polar/high-latitude, invalid input, rate limit + CORS on 429, over real uvicorn + real HTTP to the fake. | as above |
| `browser/run_sprint14.sh` | (Sprint 14) real headless Chrome 153, CORS enforced: provider picker, live badge/provenance, fallback visible, `hijri:null` does not blank the page, markup in server text is escaped, real Maghrib day transition with the live provider, 429 backoff keeps the last view. Writes `browser/results/sprint14-browser-results.json`. | `bash verification/browser/run_sprint14.sh` (after `cd verification/browser && npm install`) |

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

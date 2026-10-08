# waqt-web

> **Site layout (Stitch implementation).** `apps/web` is a multi-page static site (no framework, `render.yaml` unchanged,
> no build step on the server). Design: the "Precision Astrometric Infrastructure" system from the Stitch export
> (Space Grotesk / Inter / JetBrains Mono, obsidian palette), compiled to `assets/css/stitch.css` with Tailwind and
> self-hosted fonts and inline-SVG icons — no CDN at runtime. Pages: `index`, `problem`, `how-it-works`, `live-demo`,
> `api`, `applications`, `lab`, `governance`, `community`, `resources`, plus `reference-viewer.html` (the original
> minimal API proof page, script unchanged). Shared JS is in `assets/js/`; **all external URLs are configuration** in
> `assets/js/config.js` (null until supplied).
>
> **Editing:** pages are generated so the shared header/footer cannot drift:
> `cd apps/web/tools && npm install && python3 build_pages.py && npm run build:css` (commit the generated files).
> Tests: `pytest apps/web/tests` and `cd apps/web/tests/js && npm install && npm test`. Details: `WAQT-WEB-REPORT.md`.

Reference web application for Waqt (Sprint 12, Goal A.2). A single static,
dependency-free `index.html` that **only** talks to the Waqt HTTP API
(`GET /v1/waqt`, `/v1/events`, `/v1/calendar`, `/v1/version`) — it computes
nothing. It is the browser counterpart to `apps/cli`: same rule
("consume Waqt, not reimplement it"), enforced here by construction (no
astronomy/calendar constants appear in the file at all — see
`tests/test_no_second_implementation.py`) rather than an import check,
since a static page has no import graph to inspect.

## Run it

The API needs CORS enabled for the origin serving this page (Sprint 12's
`WAQT_CORS_ORIGINS`, off by default):

```
WAQT_CORS_ORIGINS=http://localhost:8080 uvicorn waqt.api:app --port 8000
python -m http.server 8080 --directory apps/web
# open http://localhost:8080/live-demo.html (or index.html for the site), set the API base URL to http://localhost:8000 (default)
```

Same-origin also works with no CORS setup: serve `apps/web/index.html`
from the API's own static-file mount if you add one, or via a reverse proxy.

## What it shows

- **Location**: browser geolocation (`navigator.geolocation`), or manual
  lat/lon entry. The first view uses a clearly labeled Makkah demo location;
  it does not request geolocation without an explicit click.
- **Local Waqt day**: Maghrib-to-Maghrib boundary and length, from `/v1/waqt`.
- **Current Waqt clock**: the `HH:MM:SS` reading, live-ticking client-side
  between polls (interpolated from the last server reading + elapsed time —
  never recomputed from angles/instants in the browser).
- **Prayer/event timeline**: all six events with local time and Waqt reading,
  next event highlighted.
- **Gregorian / Hijri / Waqt representations** side by side.
- **Provider/method metadata**: Hijri provider, `computation.engine` +
  `.revision` + `.accuracy_level`, `waqt-core` version, API version — all
  read verbatim from the response, displayed in a collapsible panel, never
  hidden.

## API base URL

Stored in `localStorage` under `waqt:apiBase` (a per-browser UI preference,
not Waqt state — nothing about a computation is cached across sessions).
Localhost pages default to `http://localhost:8000`; public hosts default to
`https://waqt-api-r6e0.onrender.com`. The header remains editable, and `?api=`
can override the API base for a deployment or preview.

## Render deployment

The root `render.yaml` defines both the API and this static site. After the
first Blueprint deployment, copy the static site's actual HTTPS URL from Render
and set the API service's `WAQT_CORS_ORIGINS` to that exact origin in the Render
Dashboard, then redeploy the API. Add any custom web domains as additional,
comma-separated exact origins. CORS remains disabled until this is configured.
The client targets the supplied public API URL.

## Tests

`tests/test_no_second_implementation.py` (now pointed at `live-demo.html`; plain Python, no browser needed)
parses `index.html`'s inline `<script>` and fails if it defines any of the
astronomy/calendar constants `waqt-core` owns (a Fajr/Isha default angle,
the Hijri epoch JDN, a `waqt-noaa` string, ...), or if it computes a Waqt
reading from a raw instant instead of reading one out of a response.
`tests/manual_smoke.md` is a short checklist for exercising the page in an
actual browser against a running API, since this environment cannot run one.

# waqt-web

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
# open http://localhost:8080, set the API base URL to http://localhost:8000 (default)
```

Same-origin also works with no CORS setup: serve `apps/web/index.html`
from the API's own static-file mount if you add one, or via a reverse proxy.

## What it shows

- **Location**: browser geolocation (`navigator.geolocation`), or manual
  lat/lon entry — the app makes no claim about location without one of these.
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
Defaults to `http://localhost:8000`; editable in the header.

## Tests

`tests/test_no_second_implementation.py` (plain Python, no browser needed)
parses `index.html`'s inline `<script>` and fails if it defines any of the
astronomy/calendar constants `waqt-core` owns (a Fajr/Isha default angle,
the Hijri epoch JDN, a `waqt-noaa` string, ...), or if it computes a Waqt
reading from a raw instant instead of reading one out of a response.
`tests/manual_smoke.md` is a short checklist for exercising the page in an
actual browser against a running API, since this environment cannot run one.

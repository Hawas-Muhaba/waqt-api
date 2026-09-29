# apps/web manual smoke checklist

This environment could not run a browser or a live FastAPI server, so
`index.html` was verified structurally (`test_no_second_implementation.py`)
and by inspection against the real response shapes `waqt_local` produces
(same shapes `waqt.api` returns — see `waqt/api/waqt_endpoint.py`), not by
loading it. Run this checklist once in a real environment before treating
the page as done:

1. `WAQT_CORS_ORIGINS=http://localhost:8080 uvicorn waqt.api:app --port 8000`
   and `python -m http.server 8080 --directory apps/web`; open the page.
2. Enter a known location (e.g. `21.4225, 39.8262`, Makkah) and confirm the
   Waqt clock, Hijri date, and event table populate and the clock visibly
   ticks once a second without further network calls.
3. Click "Use my location"; accept/deny the browser permission prompt and
   confirm both paths behave (data loads, or a clear error is shown).
4. Switch the Hijri provider dropdown; confirm the Hijri date changes and
   the event *instants* do not.
5. Enter a polar-summer location/date pair known to be `UNDEFINED`
   (e.g. lat 78, any June instant) and confirm the page reports it plainly
   instead of showing stale or default data.
6. Point "API base" at a wrong port; confirm the CORS/unreachable error
   message is legible, not a silent blank page.
7. Resize to a narrow (< 400px) viewport; confirm the layout reflows and
   nothing is clipped.
8. Confirm the metadata panel shows `computation.engine`, `.revision`,
   `.accuracy_level`, the Hijri provider name+version, and (against an
   API >= 1.4.0) `waqt-core` and API versions from `GET /v1/version`.

# Waqt — reference implementation

Reference implementation of the **Waqt Core Time Model v0.1**, now with
Sprint 2's location/astronomy corrections: real timezone-based day
boundaries, elevation, and a named ΔT model.

```
waqt/
  solar.py             — solar event engine (sunrise, sunset, transit, Fajr, Asr, Isha)
  hijri.py              — calendar provider interface + one reference provider
  core.py                — the Core Time Model itself (day boundary, hour, events)
  timezone_provider.py  — Sprint 2: real IANA timezone -> local civil date
  timescale.py           — Sprint 2: DeltaT (TT-UT1) provider
  api.py                  — HTTP surface: GET /v1/waqt
tests/
  test_core.py — validates the claims in SCOPE.md and SPRINT-2-REPORT.md, across
                 a full geographic matrix (equator through polar, both hemispheres,
                 the International Date Line, multiple elevations)
SCOPE.md              — what's implemented, what isn't, and known limitations
SPRINT-2-REPORT.md    — what Sprint 2 added, including a real bug it caught
```

## Quickstart

```bash
pip install -r requirements.txt
uvicorn waqt.api:app --reload --port 8000
curl "http://localhost:8000/v1/waqt?lat=9.0192&lon=38.7525"
curl "http://localhost:8000/v1/waqt?lat=9.0192&lon=38.7525&elevation_m=2400"
```

Or open `http://localhost:8000/docs` for the interactive test UI.

## Verify

```bash
python3 -m pytest tests/ -v
```

32 tests, covering the full geographic matrix, elevation monotonicity,
the date-line fix, ΔT sanity, and the Core Time Model's own invariants
(Maghrib = 00:00, events-as-positions, weekday shift).

Read `SCOPE.md` and `SPRINT-2-REPORT.md` before using this for anything
beyond development and review.

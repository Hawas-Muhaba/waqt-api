# Waqt — reference implementation

Reference implementation of the **Waqt Core Time Model v0.1**, now at
Sprint 3: a pluggable calendar provider system on top of Sprint 2's
location/astronomy corrections (real timezone-based day boundaries,
elevation, ΔT).

```
waqt/
  solar.py               — solar event engine (sunrise, sunset, transit, Fajr, Asr, Isha)
  hijri.py               — HijriProvider interface + ArithmeticTabular + Declared providers
  core.py                — the Core Time Model itself (day boundary, hour, events)
  timezone_provider.py   — Sprint 2: real IANA timezone -> local civil date
  timescale.py           — Sprint 2: DeltaT (TT-UT1) provider
  api.py                 — HTTP surface: GET /v1/waqt
  calendar_providers/    — Sprint 3: pluggable calendar infrastructure
    umm_al_qura.py       — astronomical approximation of the real UAQ rule (via ephem)
    local_observation.py — moon-sighting reports as a Hijri calendar source
    registry.py          — name-based provider lookup + ExampleRegionalOffsetProvider
    __init__.py
tests/
  test_core.py             — 32 tests: geographic matrix, elevation, date-line, ΔT, invariants
  test_calendar_providers.py — 14 tests: all five provider categories, registry, pluggability
SCOPE.md              — what's implemented, what isn't, and known limitations
SPRINT-2-REPORT.md    — what Sprint 2 added, including a real bug it caught
SPRINT-3-REPORT.md    — what Sprint 3 added: five calendar providers, UAQ astronomy, bug fixes
```

## Quickstart

```bash
pip install -r requirements.txt
uvicorn waqt.api:app --reload --port 8000
curl "http://localhost:8000/v1/waqt?lat=9.0192&lon=38.7525"
curl "http://localhost:8000/v1/waqt?lat=21.4225&lon=39.8262&calendar_provider=umm-al-qura"
```

Or open `http://localhost:8000/docs` for the interactive test UI.

## Calendar Providers (Sprint 3)

The `calendar_provider` query parameter accepts any of:

| Value | Description |
|---|---|
| `arithmetic-tabular` | Classical 30-year arithmetic calendar (default) |
| `umm-al-qura` | Astronomical approximation of the real UAQ calculation rule |
| `declared` | Demo: empty override dict, falls back to arithmetic |
| `local-observation` | Demo: empty sightings dict, falls back to arithmetic |

Every response includes `hijri.provider` and `hijri.version` so callers always
know which algorithm produced the date.

## Verify

```bash
python3 -m pytest tests/ -v
```

46 tests covering the full geographic matrix, elevation monotonicity,
the date-line fix, ΔT sanity, all five calendar provider categories,
the registry, provider pluggability, UmmAlQura historical validation (4/4),
and a regression test for the recursion bug fix.

Read `SCOPE.md` and `SPRINT-3-REPORT.md` before using this for anything
beyond development and review.

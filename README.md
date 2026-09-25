# Waqt API v1

A Makkah-anchored, Maghrib-to-Maghrib civil time and Hijri calendar API — a stable, versioned, language-independent HTTP contract. You do not need to read any Python here to integrate it; start with [`docs/API.md`](docs/API.md).

```
waqt/
  solar.py                    — solar event engine (sunrise, sunset, transit, Fajr, Asr, Isha)
  hijri.py                     — HijriProvider interface + arithmetic-tabular + declared providers
  core.py                       — the Core Time Model (day boundary, hour, events) — untouched since Sprint 2
  semantics.py                   — Sprint 5: formal temporal vocabulary (WaqtDay, WaqtPosition, EventPosition,
                                    comparison rules, undefined-event handling) — built on core.py, doesn't touch it
  scheduling/                    — Sprint 6: windows, deadlines, event-relative rules, Maghrib-crossing spans,
                                    explicit undefined-event statuses (model.py, context.py, engine.py, ops.py)
  timezone_provider.py         — real IANA timezone -> local civil date
  timescale.py                  — DeltaT (TT-UT1) provider
  calendar_providers/           — pluggable calendar system
    umm_al_qura.py                — astronomical Umm al-Qura approximation (4/4 historical dates validated)
    local_observation.py           — moon-sighting reports
    registry.py                     — provider lookup + a worked "Custom provider" example
  api/                           — Waqt API v1
    common.py                       — shared envelope, error schema, unit/reading formatters
    providers.py                     — calendar_provider resolution + catalog
    waqt_endpoint.py, day_endpoint.py, events_endpoint.py, hijri_endpoint.py,
    calendar_endpoint.py, location_endpoint.py, conversions_endpoint.py
docs/
  API.md            — the full HTTP contract: endpoints, schemas, errors, versioning, units
  TIME-MODEL.md      — why the numbers look the way they do (Maghrib=00:00, variable day length, events-as-positions)
  ASTRONOMY.md        — solar engine, accuracy levels (measured, not assumed), elevation, DeltaT, edge cases
  CALENDARS.md         — every calendar provider's exact guarantees and limitations
  SEMANTICS.md          — Sprint 5: formal spec for instants, days, positions, comparison, undefined-event rules
tests/
  test_core.py               — astronomy, location, elevation, date-line, invariants
  test_calendar_providers.py — provider identification, UAQ historical validation, pluggability
  test_api.py                — the full v1 HTTP contract: envelope, every error code, all 7 endpoints
  test_semantics.py           — Sprint 5: boundary rule, comparison enforcement, undefined-event handling
  test_vectors.py              — loads tests/vectors/waqt_vectors.json, re-derives every value, asserts exact match
  vectors/
    scheduling_vectors.json      — Sprint 6: 116 vectors with embedded day tables (no astronomy needed to consume)
    generate_scheduling_vectors.py
    waqt_vectors.json            — 10 portable, language-independent conformance vectors
    generate_vectors.py           — regenerates the above from the reference implementation (never hand-edit the JSON)
consumers/js/                — Sprint 6: independent zero-dependency Node consumer of BOTH vector files (`cd consumers/js && npm test`)
SCOPE.md, SPRINT-6-REPORT.md, SPRINT-2-REPORT.md, SPRINT-3-REPORT.md, SPRINT-4-REPORT.md, SPRINT-5-REPORT.md — build history and honest limitations
```

## Quickstart

```bash
pip install -r requirements.txt
uvicorn waqt.api:app --reload --port 8000
curl "http://localhost:8000/v1/waqt?lat=9.0192&lon=38.7525"
```

Or open `http://localhost:8000/docs` for interactive testing (Swagger UI, generated automatically from the same code that serves requests).

## The seven endpoints

| Endpoint | What it returns |
|---|---|
| `GET /v1/waqt` | Everything — day boundary, clock reading, all six events, Hijri date |
| `GET /v1/day` | Day boundary only |
| `GET /v1/events` | The six prayer/solar events only (no calendar) |
| `GET /v1/hijri` | Calendar lookup only, **no location needed** — see `docs/API.md` §8 for the one gotcha |
| `GET /v1/calendar` | Discovery: what calendar providers exist |
| `GET /v1/location` | Timezone + local civil date resolution, standalone |
| `GET /v1/conversions` | Gregorian ↔ Hijri, either direction |

Full request/response schemas, every error code, units, and versioning policy: [`docs/API.md`](docs/API.md).

## Scheduling (Sprint 6)

| Endpoint | What it answers |
|---|---|
| `GET /v1/schedule/snapshot` | Day begin/end, next event, time until/since every event |
| `GET /v1/schedule/span` | Does `[start, end)` cross a Maghrib boundary? Civil midnight? |
| `POST /v1/schedule/resolve` | Any rule: windows, deadlines, "30 min before Maghrib", `between(Fajr, Sunrise)` … |

Waqt provides temporal facts, not religious rulings — see [`docs/SCHEDULING.md`](docs/SCHEDULING.md).

## Verify

```bash
python3 -m pytest tests/ -v
```

Sprint 6 adds 200+ tests (scheduling engine, HTTP, 116 portable vectors, and the independent JS consumer, run from pytest when Node is installed). Sprint 5's baseline was 106 tests: the full geographic matrix, elevation, the date-line fix, ΔT, all five calendar provider categories (including 4/4 historical Umm al-Qura dates), the complete v1 HTTP contract, and Sprint 5's formal temporal semantics — the exact-Maghrib boundary rule, same-day-only comparison enforcement, undefined-event handling, and 10 portable conformance vectors an independent implementation in another language could check itself against.

Read `SCOPE.md` and the `SPRINT-*-REPORT.md` files before using this for anything beyond development and review — especially before trusting any Hijri date for a religious purpose.

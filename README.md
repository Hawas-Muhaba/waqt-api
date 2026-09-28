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
  institutional/                 — Sprint 7: week, fiscal year, academic year, calendar profiles
                                    (rules.py, week.py, fiscal_year.py, academic_year.py, binding.py, profile.py)
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
    calendar_endpoint.py, location_endpoint.py, conversions_endpoint.py,
    schedule_endpoint.py, institutional_endpoint.py
docs/
  API.md            — the full HTTP contract: endpoints, schemas, errors, versioning, units
  TIME-MODEL.md      — why the numbers look the way they do (Maghrib=00:00, variable day length, events-as-positions)
  ASTRONOMY.md        — solar engine, accuracy levels (measured, not assumed), elevation, DeltaT, edge cases
  CALENDARS.md         — every calendar provider's exact guarantees and limitations
  SEMANTICS.md          — Sprint 5: formal spec for instants, days, positions, comparison, undefined-event rules
  SCHEDULING.md          — Sprint 6: windows, deadlines, event-relative rules, undefined-event statuses
  INSTITUTIONAL.md        — Sprint 7: week, fiscal year, academic year, calendar profiles
tests/
  test_core.py               — astronomy, location, elevation, date-line, invariants
  test_calendar_providers.py — provider identification, UAQ historical validation, pluggability
  test_api.py                — the full v1 HTTP contract: envelope, every error code, all 7 endpoints
  test_semantics.py           — Sprint 5: boundary rule, comparison enforcement, undefined-event handling
  test_vectors.py              — loads tests/vectors/waqt_vectors.json, re-derives every value, asserts exact match
  test_institutional.py         — Sprint 7: week, fiscal year, academic year, profile, architecture separation
  test_institutional_vectors.py  — Sprint 7: loads institutional_vectors.json, re-derives, invokes JS consumer
  test_institutional_api.py       — Sprint 7: /v1/institutional/* HTTP surface
  vectors/
    scheduling_vectors.json      — Sprint 6: 116 vectors with embedded day tables (no astronomy needed to consume)
    generate_scheduling_vectors.py
    institutional_vectors.json    — Sprint 7: 22 vectors with embedded Hijri calendar tables (no astronomy at all)
    generate_institutional_vectors.py
    waqt_vectors.json            — 10 portable, language-independent conformance vectors
    generate_vectors.py           — regenerates the above from the reference implementation (never hand-edit the JSON)
consumers/js/                — Sprint 6/7: independent zero-dependency Node consumer of all three vector files (`cd consumers/js && npm test`)
SCOPE.md, SPRINT-7-REPORT.md, SPRINT-6-REPORT.md, SPRINT-2-REPORT.md, SPRINT-3-REPORT.md, SPRINT-4-REPORT.md, SPRINT-5-REPORT.md — build history and honest limitations
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

## Institutional calendars (Sprint 7)

| Endpoint | What it answers |
|---|---|
| `GET /v1/institutional/week` | The Islamic week containing an instant — first day, Jumu'ah slot, all configurable |
| `GET`/`POST /v1/institutional/fiscal-year(/resolve)` | Muharram-1-to-Dhu-al-Hijjah by default, or any `start_rule`/`end_rule` you supply |
| `GET`/`POST /v1/institutional/academic-year(/resolve)` | First-Ahad-of-Muharram-to-last-Khamis-of-Sha'ban by default, or your own opening/closing/terms/holidays |
| `GET /v1/institutional/profile` | A demo `CalendarProfile` as pure JSON configuration |

No universal Islamic fiscal or school calendar is baked in — see [`docs/INSTITUTIONAL.md`](docs/INSTITUTIONAL.md).

## SDKs, local computation, and independent astronomy (Sprint 9-10)

- **Official SDKs** — `sdks/python/waqt_client` and `sdks/js/waqt-client`,
  remote HTTP clients with full read coverage plus typed request builders
  for every `POST` endpoint. See [`docs/SDK.md`](docs/SDK.md) and each
  package's `CHANGELOG.md`. Packaging/versioning/release procedure:
  [`docs/RELEASING.md`](docs/RELEASING.md).
- **Local computation library** — `local/waqt_local`, a no-HTTP, in-process
  Python package computing the same facts the server does, straight from
  `waqt.core`/`waqt.scheduling`/`waqt.institutional`. See
  [`docs/LOCAL.md`](docs/LOCAL.md).
- **Independent astronomy** — `independent-astronomy/independent_solar`
  (a from-scratch Level-B solar engine) and `independent-astronomy/level_a`
  (a VSOP87-based Level-A reference, Sprint 10, used to measure both
  Level-B engines). See [`docs/INDEPENDENT-ASTRONOMY.md`](docs/INDEPENDENT-ASTRONOMY.md)
  and [`docs/ASTRONOMY.md`](docs/ASTRONOMY.md)'s "Accuracy levels" section.

## Verify

```bash
python3 -m pytest tests/ -v
```

Sprint 7 adds 86 tests (institutional-layer unit tests, HTTP surface, 22 portable
calendar-table vectors, and the independent JS consumer, run from pytest when Node
is installed) on top of Sprint 6's 320. Sprint 6 added 200+ tests (scheduling
engine, HTTP, 116 portable vectors, and the independent JS consumer). Sprint 5's
baseline was 106 tests: the full geographic matrix, elevation, the date-line fix,
ΔT, all five calendar provider categories (including 4/4 historical Umm al-Qura
dates), the complete v1 HTTP contract, and Sprint 5's formal temporal semantics —
the exact-Maghrib boundary rule, same-day-only comparison enforcement,
undefined-event handling, and 10 portable conformance vectors an independent
implementation in another language could check itself against.

Read `SCOPE.md` and the `SPRINT-*-REPORT.md` files before using this for anything beyond development and review — especially before trusting any Hijri date for a religious purpose.

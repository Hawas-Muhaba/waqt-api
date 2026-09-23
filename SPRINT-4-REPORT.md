# Sprint 4 Report — Waqt API v1

**Sprint goal:** move from a proof-of-concept endpoint to a proper developer-facing API — stable envelope, versioning, error schema, seven endpoints, and documentation a stranger could integrate from without reading the source.
**Status:** done. 69/69 tests passing (24 new). All seven endpoints live, cross-checked against `/v1/waqt` for consistency, documented in four files.

---

## 0. Before this sprint started: a note on trust

This sprint began with a screenshot claiming four Sprint 3 bugs were already fixed. I checked instead of accepting it, and none of the four were actually fixed in the code I had. You then uploaded real files with real fixes. I installed and verified those too, rather than trusting the accompanying claims — and found they were *mostly* right: the recursion bug was genuinely fixed, the lazy-loading was genuinely fixed, CI was genuinely added, but `declared`/`local-observation` being "reachable" turned out to mean "returns 200 while silently ignoring the parameter," not "actually testable." I'm noting this here because that verification step is what caught the gap this sprint's override-parameter work then closed — the discipline of checking rather than trusting paid for itself directly.

---

## 1. The core contract

Everything in `waqt/api/common.py`, applied identically across all seven endpoints:

- **Envelope**: `{meta, data, error}` on every response, success or failure. `data`/`error` are mutually exclusive.
- **Versioning**: URL path (`/v1/`) for the major contract; `meta.api_version` (semver, `1.0.0`) and `meta.spec` (`waqt-core/0.1`) as two independently-tracked finer-grained identifiers.
- **Error schema**: one fixed vocabulary — `INVALID_INSTANT`, `INVALID_DATE`, `UNKNOWN_CALENDAR_PROVIDER`, `UNSUPPORTED_OPERATION`, `VALIDATION_ERROR`, `INTERNAL_ERROR`. Every one of the six is exercised by a real test, not just documented.
- **Units**: durations are never a bare string — always `{"display": "HH:MM:SS", "seconds": <float>}`, so a caller never has to parse a display string back apart to do arithmetic.
- **Null-stable schema**: the same top-level keys exist regardless of status; `UNDEFINED` responses carry explicit `null`s instead of omitted keys.
- **Timezone representation**: `{"name": IANA, "utc_offset_seconds": <int>}`, resolved for DST at the actual returned instant.
- **Identification**: `hijri.provider{name,version}`, `profile{...}`, and `computation{engine, accuracy_level, timescale_model, delta_t_seconds}` appear on every response that used the relevant subsystem.

**The backstop that matters most in production**: a global exception handler catches *everything*, including exceptions this code never anticipated. Verified directly — the residual old-date `ValueError` inside `UmmAlQuraProvider` (documented, not newly discovered) now comes back as a clean `500 INTERNAL_ERROR` in the standard envelope instead of an unhandled exception. No endpoint can return a raw traceback, structurally, not by convention.

## 2. Seven endpoints

| Endpoint | Design note |
|---|---|
| `GET /v1/waqt` | The full result. Refactored onto the new contract; nothing about *what* it computes changed. |
| `GET /v1/day` | Day boundary only. Takes no calendar or astronomy-profile params — neither affects Maghrib. |
| `GET /v1/events` | The six events, no `calendar_provider` param at all. The absence is the point: it's a passing test (`test_events_endpoint_has_no_calendar_provider_param`), not just a design note. |
| `GET /v1/hijri` | Takes no `lat`/`lon` — also tested directly, not just asserted in prose. This is the model's own location-independence claim (Sec 1) made structurally unavoidable to violate. |
| `GET /v1/calendar` | Discovery catalog — four providers, descriptions, override/reverse-support flags. |
| `GET /v1/location` | Isolates the timezone/civil-date mechanism for standalone debugging. |
| `GET /v1/conversions` | New capability this sprint: bidirectional Gregorian↔Hijri, not just one direction. |

Every subset endpoint (`/v1/day`, `/v1/events`, `/v1/hijri`) is tested for byte-identical agreement with the corresponding slice of `/v1/waqt`'s output — there's one source of truth (`core.compute_waqt`), never two computations that could quietly drift apart.

## 3. Reverse conversion — genuinely new work, not just re-exposure

Hijri→Gregorian didn't exist anywhere before this sprint. Added:
- `ArithmeticTabularProvider.to_gregorian` — exact closed-form inverse (Fliegel & Van Flandern JDN↔Gregorian plus the standard Hijri↔JDN formula).
- `UmmAlQuraProvider.to_gregorian` — walks its own cached real-conjunction boundary chain to the target month; exact against *its own* computed boundaries, not a separate approximation layered on top.

Both verified to round-trip exactly in both directions (`Gregorian → Hijri → Gregorian` and `Hijri → Gregorian → Hijri`) across multiple test dates, including through the full HTTP layer, not just the Python objects.

`declared`/`local-observation` correctly refuse this direction (`UNSUPPORTED_OPERATION`) — a sparse override table has no general inverse, and guessing one would be worse than saying so.

## 4. The `declared`/`local-observation` gap, actually closed

Sprint 3 left these "reachable but not really testable" (see §0). This sprint gives them real teeth: `override_date` + `declared_year/month/day` (or `sighting_*` + `observed_at`) let a caller supply a genuine override and see it take effect — verified live, both the override-present and override-absent-falls-back cases.

**A real subtlety surfaced during this work, and it's now documented in three places** (`API.md` §8, `TIME-MODEL.md`, `CALENDARS.md`) because it will trip up the first real user otherwise: `override_date` must equal the *closing* Maghrib's Gregorian date — the Core Time Model's own label rule — not the date naively read off an instant. Get this wrong and the override silently no-ops rather than erroring, which is worse than a hard failure if it isn't flagged loudly. I found this myself while writing the verification tests (my first attempt used the wrong date and the "fix" appeared not to work), which is exactly why it's now called out as prominently as it is.

## 5. Documentation

Four files, each with a distinct job rather than four overlapping restatements of the same thing:
- **`docs/API.md`** — the wire contract: every endpoint's params, the envelope, every error code with its trigger condition, units, and the one gotcha (§8), plus a "complete integration in under a minute" worked example.
- **`docs/TIME-MODEL.md`** — the *why*, for a consumer who doesn't need the original design-review documents: Maghrib=00:00, non-24-hour days, events-as-positions, with a pointer to the exact test that proves the events-as-positions claim rather than just asserting it.
- **`docs/ASTRONOMY.md`** — the engine, the measured (not assumed) accuracy table by latitude, elevation's scope, ΔT, and the polar `UNDEFINED` behavior.
- **`docs/CALENDARS.md`** — every provider's exact guarantees, with `umm-al-qura`'s three honesty caveats kept intact and now including the newly-discovered bounded-date-range limit.
- **Interactive docs**: free from FastAPI/Swagger at `/docs`, verified to render and to list all seven endpoints in its generated OpenAPI schema — no separate work needed here beyond writing good `Query(...)` descriptions, which were already in place.

## 6. Structural change

`api.py` became `waqt/api/` — a package, one file per endpoint plus `common.py` and `providers.py`. `waqt.api:app` and `from waqt.api import app` both still resolve identically; `render.yaml`'s start command needed no change, confirmed by inspection.

## 7. What's still out of scope

- **Level A astronomical precision** — unchanged from Sprint 2/3, still explicitly deferred, not silently implied by anything in this sprint's polish.
- **`UmmAlQuraProvider`'s pre-~1700 date bound** — now clearly documented (`CALENDARS.md`) and returns a structured error rather than crashing raw, but the underlying `ephem` limitation itself is unfixed. Given the realistic use case (a masjid/school wanting near-present dates), this remains low priority by design, not by oversight.
- **No authentication, rate limiting, or request logging** — fine for a review/demo deployment shared with one collaborator; would need attention before wider or production use.
- **`/v1/conversions`' `to-gregorian` direction has no bulk/range mode** — one date in, one date out. A calendar-rendering client wanting a whole month would need N requests. Not requested this sprint; flagging it as the natural next ask.

## Test suite

24 new tests in `tests/test_api.py`, on top of Sprint 2/3's 45 — **69 total, all passing.** Covers the envelope shape on both success and every error path, all seven endpoints, the fixed override mechanism, both conversion directions round-tripping through HTTP, and the date-line case reachable via `/v1/location`. Run with `python3 -m pytest tests/ -v`.

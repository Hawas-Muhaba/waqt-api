# Waqt Calendar Interoperability (Sprint 8)

The specification `waqt/calendar_interop.py` implements. It sits **beside** the layers Sprints 6-7 added, not above or below them — it is a secondary calendar view over the same primary model, not a new layer of temporal semantics:

```
Waqt Core             -> astronomical events -> Waqt dates -> temporal semantics    (Sprints 1-2)
Scheduling             -> windows, deadlines, event-relative rules                  (Sprint 6)
Institutional layer    -> week, fiscal year, academic year, terms, periods          (Sprint 7)
Calendar interop        -> Gregorian/solar calendar as a secondary, formal view      (Sprint 8, this document)
```

Sprint 8 adds no astronomy and changes none of `waqt/core.py`, `waqt/solar.py`, `waqt/semantics.py`, `waqt/hijri.py`, `waqt/scheduling/`, `waqt/institutional/`, or `waqt/calendar_providers/` (verified byte-for-byte in CI via md5sum, the same posture every prior sprint has taken). Everything in this document is either a documented statement of a rule the engine already enforced, or a thin, explicit interface onto something `waqt.core.compute_waqt` and `waqt.semantics` already compute.

## 0. The key principle

> The Gregorian date answers: **"Which civil-calendar date is this instant?"**
> Waqt answers: **"Which Waqt day and Waqt position does this instant belong to?"**

Those are two representations of the same instant, never two competing definitions of "today." Nothing in this module lets the Gregorian calendar redefine a Waqt day boundary, and nothing lets Waqt redefine what date the Gregorian calendar says it is. `waqt.calendar_interop.represent_instant` is the concrete proof: every value it returns is read off exactly one `instant` and, when a location is given, exactly one `compute_waqt` call.

## 1. Gregorian ↔ Waqt conversion

Two directions, two functions:

| Direction | Function | HTTP |
|---|---|---|
| instant → {Gregorian, Waqt} | `represent_instant(instant, location=None, ...)` | `GET /v1/calendar/convert?direction=instant-to-calendars` |
| Gregorian date + location → Waqt day | `waqt_day_for_gregorian_date(date, location, ...)` | `GET /v1/calendar/convert?direction=gregorian-date-to-waqt` |

`represent_instant` with no location returns only the UTC-Gregorian rendering (calendar-neutral: the same for every observer on Earth). With a location, it additionally returns the local civil-Gregorian date/time **and** the Waqt day/position at that place — all three read from the one instant.

`waqt_day_for_gregorian_date` is the documented, explicit form of a computation `core.compute_waqt` already performs internally every time it labels a Waqt day: a day is labeled with the Gregorian date its **closing** Maghrib falls on (see `TIME-MODEL.md` and the `declared` provider's override-date behavior in `CALENDARS.md`, which states this same relationship from the opposite direction). Given a civil date and a place, this function finds that day by probing local noon, in the place's own real IANA timezone, and bracketing Maghrib from there — safe everywhere Maghrib is actually defined, since Maghrib is never within a few hours of local noon at any non-polar location. This is a **documented approximation with a stated boundary**, matching the honesty posture `waqt/institutional/binding.py` already established for the identical need (it improves on that module's fixed-UTC-noon probe by using the location's actual civil timezone). If the noon probe lands on a Waqt day that does not, in fact, close on the requested date — possible only for an extreme mismatch between civil offset and geography — the function searches the immediate neighboring dates before giving up with `CivilDateUnresolvable(reason="civil_date_mismatch")`. A location with no defined Maghrib near the requested date (polar day/night) raises the same exception with `reason="undefined_near_date"`; the HTTP endpoint reports this as a normal `200` response with `waqt.status == "UNDEFINED"`, matching every other Waqt endpoint's NULL-STABLE convention — an undefined boundary is a legitimate astronomical answer, not a caller error.

## 2. Civil midnight vs Maghrib: a formal primitive

Sprint 6 already tracked these as two independent facts inside `SchedulingContext`/`SchedulingEngine.classify_span`. Sprint 8 does not re-derive that logic — it promotes the **same rule** into a standalone function that needs nothing from `waqt.scheduling`:

```python
classify_boundary_crossing(start, end, location, ...) -> BoundaryCrossing
```

Boundary rule (identical to `classify_span`'s, and tested against it directly in `tests/test_calendar_interop.py::test_boundary_crossing_agrees_with_scheduling_engine`): the half-open span `[start, end)` crosses a boundary B iff `start < B < end`, **strictly interior**.

- A span that **starts exactly at** B lies wholly within the day/date B opens — not a crossing.
- A span that **ends exactly at** B never reaches it, because a half-open span excludes its own end instant — not a crossing.

`crosses_maghrib` is computed by calling `waqt.semantics.crosses_maghrib` directly, not re-implemented; `maghrib_boundaries` (the actual list of Maghrib instants strictly inside the span, for display) is walked separately with `core._bracket_maghrib`, the same primitive `semantics.crosses_maghrib` itself is built on, so the boolean and the list can never disagree. `crosses_civil_midnight` compares the civil date of `start` against the civil date of `end` minus one microsecond (the span's own last included instant) — exactly `classify_span`'s own method.

The four combinations the Sprint 8 brief names — civil midnight only, Maghrib only, both, neither — plus the "starts/ends exactly at a boundary" edge cases, all have their own conformance vectors (§5).

## 3. Gregorian calendar semantics

Stated explicitly in `waqt.calendar_interop.GREGORIAN_CALENDAR_CONTRACT`, reproduced here:

| Aspect | Rule |
|---|---|
| Date representation | ISO 8601 proleptic Gregorian (year-month-day), no discontinuity at the 1582 calendar reform |
| Leap years | Divisible by 4, except centuries, except again every 400 — the standard Gregorian rule (`is_leap_year()`) |
| Month lengths | Standard Gregorian lengths (`days_in_month()`) |
| Weekday | Two renderings, never confused: `weekday_iso` (ISO 8601, Monday=1..Sunday=7) for a caller wanting the plain convention; `weekday_name_islamic` (Sunday-first, `waqt.hijri.weekday_name`) for every place a Waqt-day label is reported |
| Supported range | Python's `datetime.date`: 0001-01-01 through 9999-12-31 (proleptic Gregorian, matching ISO 8601's 4-digit-year convention) |
| Serialization | Date `YYYY-MM-DD`; instant `YYYY-MM-DDTHH:MM:SS[.ffffff]+00:00`, always UTC with explicit offset — identical to `waqt.api.common.iso()` |
| Implementation | Delegates to Python's standard library `datetime` module rather than reimplementing Gregorian arithmetic, per the Sprint 8 brief's own instruction not to duplicate it unnecessarily |

`is_leap_year()` and `days_in_month()` exist only to make this reliance explicit and tested (`tests/test_calendar_interop.py::test_days_in_month_matches_stdlib` cross-checks every month of several years against `calendar.monthrange`), not because Waqt distrusts the standard library.

## 4. Calendar-neutral instant representation

```
WaqtInstant (an ordinary UTC datetime)
   |
   +-- gregorian_of_instant(instant)            -> UTC-Gregorian (calendar-neutral)
   +-- gregorian_of_instant(instant, location)   -> local civil Gregorian
   +-- represent_instant(instant, location, ...) -> both of the above, PLUS
                                                     the Waqt day/position
```

`represent_instant` is the concrete form of the brief's own diagram (`WaqtInstant -> {Hijri, Gregorian}`). Neither calendar redefines `instant`: the Hijri date and Maghrib boundaries are computed exactly once, by `core.compute_waqt`, and both the Gregorian-civil and the Waqt renderings in the result are views over that one call — never two independently re-derived answers that could silently disagree.

## 5. API representation

```
GET /v1/calendar/convert?direction=instant-to-calendars
    &instant=2026-03-01T12:00:00Z
    &lat=9.0084&lon=38.7575
    &calendar_provider=arithmetic-tabular
```
```json
{
  "data": {
    "direction": "instant-to-calendars",
    "source": {"calendar": "instant", "instant": "2026-03-01T12:00:00+00:00"},
    "location": {"lat": 9.0084, "lon": 38.7575, "elevation_m": 0.0},
    "calendar_provider": {"name": "arithmetic-tabular", "version": "30-year-cycle-epoch-1948440"},
    "gregorian": {
      "utc":   {"date": "2026-03-01", "time_of_day": "12:00:00", "weekday_iso": 7, "weekday_name_islamic": "al-Ahad", "is_leap_year": false, "timezone_name": null, "utc_offset_seconds": 0},
      "civil": {"date": "2026-03-01", "time_of_day": "15:00:00", "weekday_iso": 7, "weekday_name_islamic": "al-Ahad", "is_leap_year": false, "timezone_name": "Africa/Addis_Ababa", "utc_offset_seconds": 10800}
    },
    "waqt": {"status": "OK", "undefined_reason": null, "day": {"hijri": {...}, "weekday": "al-Ahad", "day_open_maghrib": "...", "day_close_maghrib": "...", "position_seconds": 47828.5}},
    "caveat": "Waqt states calendar facts ..., not institutional or religious obligations."
  }
}
```

```
GET /v1/calendar/convert?direction=gregorian-date-to-waqt&date=2026-03-01&lat=9.0084&lon=38.7575
```
returns the `waqt.day` block (Hijri date, weekday, Maghrib open/close) for the Waqt day whose closing Maghrib falls on `2026-03-01` at that place, or, at a polar location with no defined Maghrib near that date, `{"waqt": {"status": "UNDEFINED", "undefined_reason": "..."}}` with HTTP `200`.

```
GET /v1/calendar/boundary-crossing?start=...&end=...&lat=...&lon=...
```
returns `{crosses_civil_midnight, crosses_maghrib, maghrib_boundaries, start_civil_date, end_civil_date}` for the half-open span `[start, end)`. `end <= start` is a caller error (`400 INVALID_SPAN`); an undefined boundary near the span is reported as `200` with `status: "UNDEFINED"`, per the same NULL-STABLE convention as everywhere else in the API.

See `waqt/api/calendar_convert_endpoint.py` for the full parameter list (astronomy-profile overrides, calendar-provider overrides, `timezone_override`) — every one of them is the same query parameter `/v1/waqt` and `/v1/institutional/*` already use, so a caller who already integrates with those endpoints needs to learn nothing new here.

## 6. Parallel Milestone A — Independent Astronomical Reference

The Sprint 7 report named the still-unbuilt independent astronomy implementation a separate, carried-forward milestone. Sprint 8 does not build it, by design — this sprint's brief explicitly says it need not block Sprint 8 — but per the brief, it is elevated here to a **named, tracked milestone**, not left to disappear under future feature sprints:

> **Parallel Milestone A — Independent Astronomical Reference.** The existing JavaScript consumers (`consumers/js/`) prove that Waqt's *semantic* layers — day tiling, scheduling, institutional rules, and now calendar interoperability — can be independently re-implemented from frozen data. None of them independently *calculates* a solar position: every one of them consumes Maghrib instants the Python `waqt.solar` engine already produced. The deepest numerical foundation of this entire project — the astronomy itself — has therefore never received the same independent cross-check its own outputs get. This milestone is: build a second, independent solar-position/Maghrib-bracketing implementation (in any language, sharing no astronomy code with `waqt/solar.py`) and cross-validate it against `waqt/solar.py`'s own output across a broad vector set. It is tracked here, explicitly, so it is picked up deliberately rather than by accident.

**Status: built in Sprint 9.** See `independent-astronomy/` (implementation) and `docs/INDEPENDENT-ASTRONOMY.md` (methodology, results, honest limitations) — a from-scratch solar engine using right-ascension/sidereal-time event-finding instead of the equation of time, agreeing with `waqt/solar.py` within documented per-latitude tolerances across a 60-row geographic/seasonal matrix, with one honestly-reported wider band at high latitude near the equinox. It runs alongside, and does not replace, `waqt/solar.py`.

## 7. Conformance vectors and independent consumer

`tests/vectors/calendar_interop_vectors.json` (generated by `tests/vectors/generate_calendar_interop_vectors.py`, never hand-typed) covers the Sprint 8 brief's minimum test matrix: ordinary conversion, exact Maghrib / one second before / one second after, exact civil midnight (both the "starts at" and "ends at" edges), civil-midnight-only, Maghrib-only, both boundaries, neither, a date-line location (Kiritimati, UTC+14), leap-year Gregorian dates (including the 1900/2000 century-leap-rule edge case), a Waqt date whose Gregorian representation differs from the intuitive civil date, a provider change that alters only the Hijri label, and a location (Dibrugarh, NE India) where the civil timezone and true solar time differ by roughly fifty minutes.

`consumers/js/src/calendar_interop.mjs` (zero dependencies, no code shared with the Python reference) reproduces every vector using only its own frozen `context` — it never recomputes Maghrib from coordinates, the same discipline every prior sprint's JS consumer has kept. Run with `npm test` inside `consumers/js/`, or via `pytest tests/test_calendar_interop_vectors.py::test_independent_javascript_consumer_validates_all_vectors`.

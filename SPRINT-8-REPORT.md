# Sprint 8 Report — Secondary / Solar Calendar Integration

## Summary

Sprint 8 adds `waqt/calendar_interop.py` — a formal, documented Gregorian/
solar calendar interoperability layer over the Waqt Core Time Model — plus
an HTTP surface (`GET /v1/calendar/convert`, `GET /v1/calendar/boundary-
crossing`), 22 portable conformance vectors covering the brief's full
minimum test matrix, and an independent zero-dependency JavaScript consumer
that validates all of them. `waqt/core.py`, `waqt/solar.py`,
`waqt/semantics.py`, `waqt/hijri.py`, `waqt/scheduling/`,
`waqt/institutional/`, and `waqt/calendar_providers/` are byte-for-byte
unchanged (`md5sum`-verified before and after). 472 Python tests pass (406
pre-existing + 66 new); 184 JavaScript tests pass (159 pre-existing + 25
new).

```
waqt/core.py       af88c5fdc13e99390597598586db9d73   (before == after)
waqt/solar.py      8002b2fb03de49ba0784528b766cb3f2   (before == after)
waqt/semantics.py  bf92e76e58c2e25b0b74e51c8a6d1b7c   (before == after)
waqt/hijri.py      6215cc141d6fb03234144246a441b761   (before == after)
```

## What was built

**`waqt/calendar_interop.py`** — the sprint's entire deliverable, organized
around the brief's own five numbered items:

1. **Gregorian ↔ Waqt conversion** — `represent_instant(instant, location=
   None, ...)` renders one instant as UTC-Gregorian always, and, given a
   location, additionally as local civil-Gregorian and a Waqt day/position
   — all three read off exactly one `core.compute_waqt` call, so they can
   never silently disagree. `waqt_day_for_gregorian_date(date, location,
   ...)` is the reverse: given a Gregorian civil date and a place, it finds
   the Waqt day whose *closing* Maghrib falls on that date — the existing
   day-labeling rule `core.compute_waqt` already applies internally, turned
   into an explicit, documented, standalone entry point, exactly as the
   brief asked. It probes local noon in the location's own real IANA
   timezone (an improvement on `institutional/binding.py`'s fixed-UTC-noon
   probe for the identical need), and, in the rare case that probe doesn't
   land on a day closing on the requested date, searches the immediate
   neighboring dates before raising `CivilDateUnresolvable` with a
   structured `.reason`.

2. **Civil midnight vs Maghrib** — `classify_boundary_crossing(start, end,
   location, ...)` promotes Sprint 6's `SchedulingContext`/`SchedulingEngine
   .classify_span` distinction into a standalone primitive needing nothing
   from `waqt.scheduling`. It reuses `waqt.semantics.crosses_maghrib`
   directly for the Maghrib half (never re-derived), and follows the exact
   same half-open interior rule (`start < B < end`) `classify_span` already
   documents — verified identical to the scheduling engine's own answer in
   `tests/test_calendar_interop.py::test_boundary_crossing_agrees_with_
   scheduling_engine`.

3. **Gregorian calendar semantics** — `GREGORIAN_CALENDAR_CONTRACT`, a
   plain dict stating exactly which rules this project relies on (date
   representation, leap years, month lengths, the two weekday conventions
   in use and where each applies, the proleptic supported range, ISO 8601
   serialization, and the explicit choice to delegate to Python's stdlib
   rather than reimplement Gregorian arithmetic). `is_leap_year()` and
   `days_in_month()` make that reliance testable
   (`test_days_in_month_matches_stdlib` cross-checks every month of several
   years against `calendar.monthrange`).

4. **Calendar-neutral instant representation** — `GregorianRepresentation`
   / `InstantRepresentation` are the concrete form of the brief's own
   diagram (`WaqtInstant -> {Hijri, Gregorian}`): neither calendar
   redefines the instant, because both are views over the one `instant`
   field and the one `compute_waqt` result.

5. **API representation** — `waqt/api/calendar_convert_endpoint.py`, below.

**`waqt/api/calendar_convert_endpoint.py`** — `GET /v1/calendar/convert`
(with `direction=instant-to-calendars` or `direction=gregorian-date-to-
waqt`, the same two-mode shape `/v1/conversions` already established in
Sprint 3) and `GET /v1/calendar/boundary-crossing`. Both are thin wrappers;
neither recomputes anything `calendar_interop.py` doesn't already provide.
Registered in `waqt/api/__init__.py`; API version bumped 1.2.0 → 1.3.0
(additive only). Two new error codes: `CALENDAR_DATE_UNRESOLVABLE` (422,
the rare civil-date-mismatch search-exhausted case) and `INVALID_SPAN` (400,
`end <= start`). A polar location with no defined Maghrib near the
requested date/span is a `200` with `status: "UNDEFINED"`, matching every
other Waqt endpoint's NULL-STABLE convention — not an error, since it's a
legitimate astronomical answer.

**`docs/CALENDAR-INTEROP.md`** — the prose contract: the key principle,
each of the five brief items, worked API examples, and §6, which names and
tracks **Parallel Milestone A — Independent Astronomical Reference** per
the brief's instruction to elevate it rather than let it disappear under
future sprints (see Design decisions).

**`tests/vectors/generate_calendar_interop_vectors.py`** →
**`tests/vectors/calendar_interop_vectors.json`** (22 vectors, three
groups: `instant_representation`, `gregorian_date_to_waqt_day`,
`boundary_crossing`) — every value computed once by the live Python engine,
never hand-typed, covering the brief's full minimum test matrix: ordinary
conversion, exact Maghrib / one second before / one second after, exact
civil midnight (both the "span starts at it" and "span ends at it" edges),
civil-midnight-only, Maghrib-only, both boundaries, neither, a date-line
location (Kiritimati, UTC+14), leap-year Gregorian dates (including the
1900-is-not-a-leap-year / 2000-is century-rule edge case), a Waqt date
whose Gregorian representation differs from the intuitive civil date
(shortly after local midnight, before Maghrib), a provider change that
alters only the Hijri label, and a location (Dibrugarh, NE India) where the
civil timezone and true solar time diverge by roughly fifty minutes.

**`consumers/js/src/calendar_interop.mjs`** + `consumers/js/test/
calendar_interop_vectors.test.mjs` — zero dependencies, no code shared with
the Python reference. It never recomputes Maghrib from coordinates; every
vector hands it the astronomy already produced, via `context`, and it
independently re-derives Gregorian civil dates, leap years, weekdays, and
the civil-midnight/Maghrib crossing rule itself from that frozen data.

**Python tests** (66 new, three files): `tests/test_calendar_interop.py`
(25 unit tests against the module directly, including the
scheduling-engine-agreement check), `tests/test_calendar_interop_vectors.py`
(25 tests: per-vector regression, minimum-test-matrix coverage, and the
subprocess-invoked JS-independence check), `tests/test_calendar_convert_api.py`
(16 tests against the HTTP surface).

## Design decisions and why

- **Reuse, never re-derive.** Every astronomy-dependent answer in this
  module — Maghrib boundaries, Hijri labels, civil-midnight-vs-Maghrib
  classification — is computed by calling `core.compute_waqt` or
  `semantics.crosses_maghrib`/`core._bracket_maghrib` directly, the same
  private-import convention `waqt/semantics.py` itself already uses. This
  is what makes the "never disagrees with `/v1/waqt`" and "never disagrees
  with the scheduling engine" guarantees structural rather than aspirational.
- **`waqt_day_for_gregorian_date` improves on, but doesn't replace,
  `institutional/binding.py`'s approximation.** Both probe local noon to
  find a Waqt day for a civil date; `binding.py` probes noon in UTC
  (documented as safe for non-extreme offsets), this module probes noon in
  the location's *own* real IANA timezone, which is strictly more accurate
  and still carries the same honest, stated boundary (never valid within a
  few hours of local noon — i.e., safe everywhere Maghrib is actually
  defined). `institutional/binding.py` itself is untouched; a future sprint
  could point it at this module instead, but that's not this sprint's job.
- **Two-mode `direction` query param, not two separate paths.** Matches the
  precedent `/v1/conversions` set in Sprint 3 for exactly this shape (one
  endpoint, a `direction` switch) rather than inventing a new convention.
- **Boundary-crossing is its own endpoint, not folded into `/convert`.**
  `/v1/schedule/span` already answers a related but broader question (which
  Waqt days a span touches, every crossing, in the context of a scheduling
  operation); `/v1/calendar/boundary-crossing` is deliberately narrower and
  needs no `SchedulingContext` at all — it's a pure calendar-interop primitive,
  matching the brief's framing of item 2 as a primitive in its own right.
- **Parallel Milestone A, elevated but not attempted.** The brief is
  explicit that Sprint 8 need not build the independent astronomy
  cross-check, but should stop letting it disappear under future feature
  sprints. `docs/CALENDAR-INTEROP.md` §6 names it, states exactly what it
  is and why it still matters (every JS consumer so far — including this
  sprint's — validates semantics from frozen astronomy, never recomputes a
  solar position), and tracks it explicitly rather than silently deferring
  it again.

## Test coverage

- 472 Python tests total (406 pre-existing, unchanged, all still passing;
  66 new for this sprint).
- 184 JavaScript tests total (159 pre-existing, unchanged, all still
  passing; 25 new for this sprint).
- `tests/test_calendar_interop_vectors.py::test_independent_javascript_
  consumer_validates_all_vectors` invokes the real `node --test` subprocess
  and asserts every vector passes there too — the same
  regression/coverage/independence three-part guarantee Sprints 6 and 7
  established.
- `md5sum` of `core.py`, `solar.py`, `semantics.py`, `hijri.py` unchanged;
  `waqt/scheduling/`, `waqt/institutional/`, `waqt/calendar_providers/`,
  `waqt/timezone_provider.py`, `waqt/timescale.py` also confirmed unchanged
  by the same check across the whole sprint.

## Definition of Done — checklist

- [x] Gregorian ↔ Waqt conversion, both directions, as an explicit,
      documented interoperability contract (`represent_instant`,
      `waqt_day_for_gregorian_date`)
- [x] Civil midnight vs Maghrib promoted to a formal, standalone
      calendar-interoperability primitive (`classify_boundary_crossing`),
      verified to agree with the scheduling engine it was extracted from
- [x] Gregorian calendar semantics specified explicitly
      (`GREGORIAN_CALENDAR_CONTRACT`, `is_leap_year`, `days_in_month`),
      delegating arithmetic to the standard library rather than duplicating it
- [x] Calendar-neutral instant representation
      (`InstantRepresentation`/`represent_instant`) where neither calendar
      redefines the underlying instant
- [x] API representation (`/v1/calendar/convert`,
      `/v1/calendar/boundary-crossing`), designed during the sprint per the
      brief's own instruction, following the existing `/v1/conversions`
      two-mode precedent
- [x] Portable conformance vectors covering the full minimum test matrix
      named in the brief (22 vectors), generated, never hand-typed
- [x] Independent JS consumer validating all vectors, sharing no code with
      the Python reference, never recomputing Maghrib
- [x] Core Time Model / solar engine unmodified (md5-verified); `semantics.py`,
      `hijri.py`, `waqt/scheduling/`, `waqt/institutional/`,
      `waqt/calendar_providers/` unmodified (md5-verified against the
      Sprint 7 delivery)
- [x] Secondary calendar never redefines the Waqt day boundary — every
      Waqt day boundary in this sprint's output is read from `core
      .compute_waqt`, never computed independently
- [x] Parallel Milestone A named and tracked (`docs/CALENDAR-INTEROP.md`
      §6), not attempted here, not silently dropped either

## Honest limitations

- **Parallel Milestone A (the independent astronomical reference
  implementation) is still not built.** As in the Sprint 7 report, and per
  this sprint's own brief, it remains explicitly out of scope and carried
  forward, now as a named, documented milestone rather than an implicit
  deferral.
- **`waqt_day_for_gregorian_date`'s local-noon probe is an approximation
  with a stated boundary**, not a general "instant for civil date g"
  solver — safe everywhere Maghrib is actually defined (never within a few
  hours of local noon at any non-polar location), and falls back to a
  small bounded neighbor search before giving up, but not proven for a
  contrived jurisdiction whose civil offset is wildly mismatched to its own
  geography. No such real jurisdiction is known to exist; Kiritimati
  (UTC+14, tested directly) is the most extreme real case in this project's
  own test matrix and resolves correctly on the very first probe.
- **`/v1/calendar/boundary-crossing`'s `maghrib_boundaries` list is bounded
  to 400 iterations** (matching `waqt.scheduling.engine`'s own
  `MAX_SPAN_DAYS` bound), so an absurdly long span (longer than roughly a
  year) would silently truncate that display list rather than error. The
  boolean `crosses_maghrib` itself has no such bound, since it's answered
  directly by `semantics.crosses_maghrib` rather than by walking the list.
- **The Gregorian calendar contract's "proleptic, no 1582 discontinuity"
  claim is a statement of what this project's arithmetic does, not a claim
  that dates before 1582 in the wild ever really used the Gregorian
  calendar.** This mirrors the same honesty posture `waqt/hijri.py` already
  takes about `ArithmeticTabularProvider` not being the real Umm al-Qura
  calendar.

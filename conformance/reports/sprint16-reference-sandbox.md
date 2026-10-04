> **SANDBOX RUN - read before trusting the numbers.** This report was produced in an offline sandbox where PyEphem,
> FastAPI and timezonefinder could not be installed. The reference was driven through a *verification-only fake
> FastAPI* and a stub `ephem`/`timezonefinder` (not shipped). The fake was validated first: on the untouched Sprint 15
> tree it reproduced all 28 known reference failures exactly. **Every one of the failures below is a vector that
> explicitly uses `umm-al-qura` or `aladhan` (which falls back to it)**, i.e. caused by the missing ephemeris, not by
> the code under test. Nothing here replaces a run in CI with the real dependencies (`conformance.yml`).
> The `uaq/range/*` failures are the provider being un-constructible in the sandbox; the range guard itself was tested
> directly (`core/tests/test_sprint16_contract_rules.py`, plus a sandbox probe recorded in SPRINT-16-REPORT.md).

# Waqt conformance report

Generated 2026-10-04 17:30 UTC by `harness/waqt_conform.py` · COP 1.1 · 733 vectors + 43 metamorphic checks.

Reproduce: `python3 conformance/harness/waqt_conform.py --adapter "python3 conformance/adapters/reference_adapter.py" --label reference --adapter "node conformance/independent/src/cli.mjs" --label independent`

## 0. Contract and unresolved questions

Contract **2.0.0** (DRAFT - not yet released/ratified) - sha256 `c6011d8bc7bc6c57` - manifest matches - COP 1.1.

**Unresolved specification questions: 12** of 28 (1 unresolved by design, 11 deferred; 16 resolved). A passing table below does not mean these are settled.

- `OQ-TIME-1` [deferred] Offset-less instant: reject or assume UTC
- `OQ-TIME-2` [deferred] ISO basic date accepted?
- `OQ-TIME-3` [deferred] Sub-second precision of output instants
- `OQ-TAB-2` [deferred] Gregorian dates before the tabular epoch convert to AH year <= 0
- `OQ-TAB-3` [deferred] Tabular variants (other leap patterns, astronomical epoch) are not provided
- `OQ-DT-1` [deferred] Delta-T model and decimal-year convention
- `OQ-UND-1` [deferred] Existence of grazing events
- `OQ-UAQ-2` [unresolved-by-design] Umm al-Qura computational conventions (limb, refraction, elevation, algorithms)
- `OQ-ERR-1` [deferred] Valid ranges of fajr_angle, isha_angle, asr_ratio (ERR-004 is MUST but its vectors are open)
- `OQ-PRV-1` [deferred] Does a short Retry-After shorten the 30 s cooldown
- `OQ-PRV-2` [deferred] Circuit-breaker: does the 3rd soft failure open it for the next call
- `OQ-PRV-3` [deferred] Outbound budget refill granularity

Declared MUST but not enforced by any normative vector: `ERR-004`.

## 1. Implementations

| label | implementation | language | shares code with reference | run time |
|---|---|---|---|---|
| reference | waqt-reference waqt-core 0.4.0 / waqt-api 0.4.0 | Python | n/a (this is the reference) | 2.81 s |

## 2. Results by tier

Normative tiers (`exact`, `tolerance`) and metamorphic checks decide conformance. `open` and `informative` vectors are reported but never counted as failures (see CONFORMANCE.md §4).

| tier | reference pass / fail / n.a. |
|---|---|
| exact | 433 / 43 / 3 |
| tolerance | 182 / 0 / 0 |
| open | 0 / 11 / 0 |
| informative | 8 / 53 / 0 |
| metamorphic | 31 / 12 / 0 |

## 3. Requirements

`PASS` = every normative vector for the requirement passes; `FAIL` = at least one fails; `OPEN-ONLY` = only open/informative vectors exist; `NO-DATA` = no vector yet.

| requirement | kind | reference | title |
|---|---|---|---|
| AST-001 | MUST | PASS (137/137) | The Asr target altitude uses the Sun's declination at the UPPER TRANSIT of the date (the noon shadow); the crossing instant is then solved with the Sun's position at the crossing |
| AST-002 | MUST | PASS (1/1) | Asr is undefined (omitted, UND-002) exactly when the Sun's geometric altitude at upper transit is <= 0 deg |
| CAL-001 | MUST | PASS (29/29) | arithmetic-tabular conversion Gregorian -> Hijri (epoch JDN 1948440) |
| CAL-002 | MUST | PASS (30/30) | arithmetic-tabular leap years are the positions 2,5,7,10,13,16,18,21,24,26,29 of the 30-year cycle ((11*y+14) mod 30 < 11); a different pattern is a different provider, never a substitution |
| CAL-003 | MUST | FAIL (23/31) | arithmetic-tabular reverse conversion is exact and round-trips |
| CAL-004 | MUST | PASS (10/10) | A Hijri date that does not exist is rejected, never normalised: year < 1, or a day beyond the month's length in that provider, is INVALID_HIJRI_DATE (out-of-range month/day numerals MAY be VALIDATION_ERROR) |
| CAL-005 | MUST | FAIL (0/9) | umm-al-qura reproduces the validated New Year dates (1438, 1440, 1441, 1447) |
| CAL-006 | MUST | FAIL (0/8) | umm-al-qura months have 29 or 30 days and Gregorian<->Hijri round-trips |
| CAL-007 | OPEN | OPEN-ONLY | umm-al-qura month boundaries away from the validated anchors: UNRESOLVED BY DESIGN (institutional convention; see OQ-UAQ-2) |
| CAL-008 | MUST | PASS (5/5) | declared / local-observation override applies only on the exact label date; otherwise tabular |
| CAL-009 | MUST | PASS (3/3) | Providers without a fixed rule reject reverse conversion (UNSUPPORTED_OPERATION) |
| CAL-010 | MUST | FAIL (3/10) | Swapping the calendar provider changes only the label, never an instant or position |
| CAL-011 | MUST | FAIL (0/4) | umm-al-qura is supported for 1700-01-01..2300-12-31 only; outside it the provider refuses with OUT_OF_RANGE |
| DAY-001 | MUST | PASS (152/152) | A Waqt day is the half-open interval [Maghrib(D), Maghrib(D+1)) |
| DAY-002 | MUST | PASS (8/8) | At the exact opening Maghrib the new day has begun (position 00:00:00) |
| DAY-003 | MUST | PASS (8/8) | One microsecond before a Maghrib belongs to the previous day; days tile without gap or overlap |
| DAY-004 | MUST | PASS (162/162) | The day label (Hijri date, weekday) is that of the civil date, in the location's IANA zone, on which the CLOSING Maghrib INSTANT falls |
| DAY-005 | MUST | PASS (151/151) | Position is elapsed SI time since the opening Maghrib and is not clamped at 24:00:00 |
| DAY-006 | MUST | PASS (137/137) | Day length is the real interval, not 86400 s |
| DAY-007 | MUST | PASS (293/293) | Civil dates use the location's IANA zone (date line, DST) — not UTC and not solar time |
| DAY-008 | MUST | PASS (8/8) | The Waqt day depends only on the instant: all instants inside a day give the same day and events |
| DAY-009 | MUST | PASS (2/2) | Labels follow DAY-004 even where it makes them non-injective: a civil date with NO closing Maghrib resolves to nothing (resolved=false), a civil date with TWO resolves to the day containing its local noon; labels never decrease |
| ERR-001 | MUST | PASS (4/4) | Out-of-range latitude/longitude is rejected |
| ERR-002 | MUST | PASS (2/2) | An unknown IANA time zone is rejected with UNKNOWN_TIMEZONE (a client error, never INTERNAL_ERROR) |
| ERR-003 | MUST | PASS (2/2) | Unknown calendar provider is rejected |
| ERR-004 | MUST | OPEN-ONLY | Non-physical astronomy profile parameters are rejected |
| EVT-001 | MUST | PASS (144/144) | Event definitions: Fajr/Isha angles, sunrise/Maghrib -0.8333 deg, Dhuhr transit, Asr shadow ratio (accuracy bands in CONFORMANCE 5) |
| EVT-002 | MUST | PASS (151/151) | An event's reading is its instant minus the day's opening Maghrib |
| EVT-003 | MUST | PASS (8/8) | The closing Maghrib is listed at the day length; Isha is listed beyond the day length |
| EVT-004 | MUST | PASS (6/6) | An event belongs to the Waqt day around its own upper transit, even after local midnight; the event listing never moves to the next civil date |
| EVT-005 | MUST | PASS (12/12) | Fajr/Isha angle and Asr ratio change only their own event, never the day boundary |
| EVT-006 | MUST | PASS (4/4) | Elevation (dip) shifts sunrise and Maghrib only |
| EVT-007 | MUST | PASS (1/1) | waqt.compute next_event is the next event by OCCURRENCE: the earliest event strictly after the instant, including the previous solar day's Isha (never only the listed events) |
| GREG-001 | MUST | PASS (12/12) | Proleptic Gregorian leap-year rule (4 / 100 / 400) |
| GREG-002 | MUST | PASS (12/12) | Weekday naming: ISO number and Sunday-first Islamic names |
| GREG-003 | MUST | PASS (12/12) | Days in month |
| INS-001 | MUST | FAIL (10/15) | Calendar rules: month_day, month_end, nth_weekday_of_month |
| INS-002 | MUST | PASS (4/4) | Islamic week: seven consecutive days from a configurable first day |
| INS-003 | MUST | FAIL (10/13) | Fiscal year resolves start/end rules; end before start is rejected |
| INS-004 | MUST | FAIL (2/3) | Academic year: opening, closing, terms, holidays |
| INS-005 | MUST | PASS (6/6) | Unresolvable rules fail with INVALID_CALENDAR_RULE |
| INT-001 | MUST | PASS (7/7) | Instant representation: UTC and civil Gregorian views of one instant, plus Waqt position |
| INT-002 | MUST | PASS (7/7) | Gregorian date + place -> the Waqt day whose closing Maghrib falls on that date |
| INT-003 | MUST | PASS (6/6) | Boundary crossing: civil midnight and Maghrib independent; strictly-interior rule |
| PRV-001 | MUST | FAIL (0/5) | Hard remote failures (timeout, network error, 429, 5xx) fall back to local umm-al-qura with the stable reason code |
| PRV-002 | MUST | FAIL (1/7) | Soft failures (4xx, malformed, date-mismatch, implausible) fall back with the stable reason code |
| PRV-003 | MUST | FAIL (0/4) | Dates outside 1900-01-01..2076-12-31 and a disabled provider never leave the process |
| PRV-004 | MUST | FAIL (3/4) | Cache hit within the TTL; stale-if-error up to 7 days, labelled remote-stale |
| PRV-005 | MUST | FAIL (0/2) | Circuit breaker after a hard failure; Retry-After honoured and capped |
| PRV-006 | MUST | FAIL (0/11) | The fallback result names the provider that actually produced it |
| PRV-007 | OPEN | OPEN-ONLY | Soft-failure counting and outbound budget details |
| SCH-001 | MUST | FAIL (34/37) | Point resolution: instant, anchor, event slots, next/prev occurrence, position, offset, fraction |
| SCH-002 | MUST | PASS (32/32) | Windows are half-open; unbounded ends; inside/before/after relation |
| SCH-003 | MUST | PASS (14/14) | Deadlines: pending / reached / passed with signed remaining seconds |
| SCH-004 | MUST | PASS (25/25) | Three undefined statuses; strict vs skip policy; evaluate reports unknown, not false |
| SCH-005 | MUST | PASS (15/15) | Span classification: strict-interior Maghrib crossing, civil midnight independent |
| SCH-006 | MUST | PASS (21/21) | event_position reports listed and containing positions; next_event/until/since |
| SCH-007 | MUST | PASS (3/3) | Derived instants use integer microseconds with half-up rounding |
| SCH-008 | MUST | PASS (16/16) | Scheduling over LIVE astronomy agrees with the table-driven result within astronomy tolerance |
| SCH-009 | MUST | PASS (3/3) | next_event/prev_event points carry `inclusive` (default true): at an instant exactly equal to an event, inclusive resolves to that event, exclusive to the next (prev: previous) one |
| SCH-010 | MUST | PASS (5/5) | event_position default slot: isha and maghrib resolve in the PREVIOUS listing, every other event in day 0; the result reports `listed` and `containing` positions |
| SCH-011 | MUST | PASS (5/5) | An empty or inverted window/span is status NO_VALID_WINDOW with duration_seconds null; WINDOW_UNDEFINED reports maghrib_boundaries as [] |
| SCH-012 | MUST | PASS (5/5) | A strict resolution (default) that meets an undefined event slot ends as EVENT_UNDEFINED / EVENT_UNDEFINED_ON_DAY naming it in undefined_ref; with on_undefined=skip the slot is listed in `skipped` and the scan continues over at most 8 day-slots, ending NO_OCCURRENCE_IN_RANGE if none is found |
| SCH-013 | MUST | PASS (2/2) | An event point at a day offset whose Waqt day, or a day stepped across to reach it, has an undefined bounding Maghrib is EVENT_UNDEFINED with cause DAY_UNDEFINED, even when the target lies outside the context's day table |
| TIME-001 | MUST | PASS (6/6) | Instants carry an explicit UTC offset; non-UTC offsets are normalised to UTC |
| TIME-002 | OPEN | OPEN-ONLY | Offset-less ('naive') instants: rejected, or assumed to be UTC |
| TIME-003 | MUST | PASS (14/14) | Malformed or non-existent instants/dates are rejected with INVALID_INSTANT / INVALID_DATE |
| UND-001 | MUST | PASS (14/14) | Polar day/night (no Maghrib): status UNDEFINED with a reason, never a guessed time; a day with exactly ONE undefined bounding Maghrib is wholly UNDEFINED |
| UND-002 | MUST | PASS (19/19) | An event that does not occur is omitted, never approximated; other events remain defined |
| UND-003 | MUST | PASS (26/26) | Both implementations must agree on WHICH events exist away from the transition latitude |
| UND-004 | OPEN | NO-DATA | Existence of GRAZING events (Sun within arc-minutes of a threshold): unresolved, scan strategy is implementation-defined |

## 4. Failing normative vectors — reference

- **uaq/new-year/1438** (exact; CAL-005)
  - `$` expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "An unexpected error occurred while computing the result."}`
- **uaq/new-year-forward/1438** (exact; CAL-005)
  - `$` expected `expected success` got `{"code": "UNKNOWN_CALENDAR_PROVIDER", "message": "ephem unavailable in this sandbox"}`
- **uaq/new-year/1440** (exact; CAL-005)
  - `$` expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "An unexpected error occurred while computing the result."}`
- **uaq/new-year-forward/1440** (exact; CAL-005)
  - `$` expected `expected success` got `{"code": "UNKNOWN_CALENDAR_PROVIDER", "message": "ephem unavailable in this sandbox"}`
- **uaq/new-year/1441** (exact; CAL-005)
  - `$` expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "An unexpected error occurred while computing the result."}`
- **uaq/new-year-forward/1441** (exact; CAL-005)
  - `$` expected `expected success` got `{"code": "UNKNOWN_CALENDAR_PROVIDER", "message": "ephem unavailable in this sandbox"}`
- **uaq/new-year/1447** (exact; CAL-005)
  - `$` expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "An unexpected error occurred while computing the result."}`
- **uaq/new-year-forward/1447** (exact; CAL-005)
  - `$` expected `expected success` got `{"code": "UNKNOWN_CALENDAR_PROVIDER", "message": "ephem unavailable in this sandbox"}`
- **uaq/day-before-new-year-1438** (exact; CAL-005)
  - `$` expected `expected success` got `{"code": "UNKNOWN_CALENDAR_PROVIDER", "message": "ephem unavailable in this sandbox"}`
- **uaq/range/1650-01-01** (exact; CAL-011)
  - `$.error.code` expected `["OUT_OF_RANGE"]` got `UNKNOWN_CALENDAR_PROVIDER`
- **uaq/range/1699-12-31** (exact; CAL-011)
  - `$.error.code` expected `["OUT_OF_RANGE"]` got `UNKNOWN_CALENDAR_PROVIDER`
- **uaq/range/2301-01-01** (exact; CAL-011)
  - `$.error.code` expected `["OUT_OF_RANGE"]` got `UNKNOWN_CALENDAR_PROVIDER`
- **uaq/range/2500-01-01** (exact; CAL-011)
  - `$.error.code` expected `["OUT_OF_RANGE"]` got `UNKNOWN_CALENDAR_PROVIDER`
- **ins/rule-month-day-muharram-1-umm-al-qura** (exact; INS-001)
  - `$` expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **ins/rule-month-end-dhul-hijjah-umm-al-qura** (exact; INS-001)
  - `$` expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **ins/rule-first-ahad-muharram-umm-al-qura** (exact; INS-001)
  - `$` expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **ins/rule-last-khamis-shaban-umm-al-qura** (exact; INS-001)
  - `$` expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **ins/rule-second-jumuah-muharram-umm-al-qura** (exact; INS-001)
  - `$` expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **ins/fiscal-year-default-umm-al-qura-1447** (exact; INS-003)
  - `$` expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **ins/fiscal-year-default-umm-al-qura-1448** (exact; INS-003)
  - `$` expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **ins/fiscal-year-custom-umm-al-qura** (exact; INS-003)
  - `$` expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **ins/academic-year-umm-al-qura** (exact; INS-004)
  - `$` expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **sch-table/calendar-umm-al-qura-window** (exact; CAL-010, SCH-001)
  - `$` expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **sch-table/calendar-umm-al-qura-span** (exact; CAL-010, SCH-001)
  - `$` expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **sch-table/calendar-umm-al-qura-day-bounds** (exact; CAL-010, SCH-001)
  - `$` expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **aladhan/single/timeout** (exact; PRV-001, PRV-006)
  - `$.steps[0].provider` expected `umm-al-qura` got `arithmetic-tabular`
- **aladhan/single/network-error** (exact; PRV-001, PRV-006)
  - `$.steps[0].provider` expected `umm-al-qura` got `arithmetic-tabular`
- **aladhan/single/http429** (exact; PRV-001, PRV-006)
  - `$.steps[0].provider` expected `umm-al-qura` got `arithmetic-tabular`
- **aladhan/single/http500** (exact; PRV-001, PRV-006)
  - `$.steps[0].provider` expected `umm-al-qura` got `arithmetic-tabular`
- **aladhan/single/http503** (exact; PRV-001, PRV-006)
  - `$.steps[0].provider` expected `umm-al-qura` got `arithmetic-tabular`
- **aladhan/single/http404** (exact; PRV-002, PRV-006)
  - `$.steps[0].provider` expected `umm-al-qura` got `arithmetic-tabular`
- **aladhan/single/http400** (exact; PRV-002, PRV-006)
  - `$.steps[0].provider` expected `umm-al-qura` got `arithmetic-tabular`
- **aladhan/single/malformed** (exact; PRV-002, PRV-006)
  - `$.steps[0].provider` expected `umm-al-qura` got `arithmetic-tabular`
- **aladhan/single/oversize** (exact; PRV-002, PRV-006)
  - `$.steps[0].provider` expected `umm-al-qura` got `arithmetic-tabular`
- **aladhan/single/echo-mismatch** (exact; PRV-002, PRV-006)
  - `$.steps[0].provider` expected `umm-al-qura` got `arithmetic-tabular`
- **aladhan/single/ok** (exact; PRV-002, PRV-006)
  - `$.steps[0].provider` expected `umm-al-qura` got `arithmetic-tabular`
- **aladhan/window-low** (exact; PRV-003)
  - `$.steps[0].provider` expected `umm-al-qura` got `arithmetic-tabular`
- **aladhan/window-high** (exact; PRV-003)
  - `$.steps[0].provider` expected `umm-al-qura` got `arithmetic-tabular`
- **aladhan/window-edge-low-inside** (exact; PRV-003)
  - `$.steps[0].provider` expected `umm-al-qura` got `arithmetic-tabular`
- **aladhan/disabled** (exact; PRV-003)
  - `$.steps[0].provider` expected `umm-al-qura` got `arithmetic-tabular`
- **aladhan/stale-expires-after-7-days** (exact; PRV-004)
  - `$.steps[1].provider` expected `umm-al-qura` got `arithmetic-tabular`
- **aladhan/circuit-open-after-hard-failure** (exact; PRV-005)
  - `$.steps[0].provider` expected `umm-al-qura` got `arithmetic-tabular`
  - `$.steps[1].provider` expected `umm-al-qura` got `arithmetic-tabular`
- **aladhan/retry-after-honoured-and-capped** (exact; PRV-005)
  - `$.steps[0].provider` expected `umm-al-qura` got `arithmetic-tabular`
  - `$.steps[1].provider` expected `umm-al-qura` got `arithmetic-tabular`
- **mm/calendar-consistency/umm-al-qura/1438** (metamorphic; CAL-006, CAL-003): {'code': 'INTERNAL_ERROR', 'message': 'NotImplementedError: ephem unavailable in this sandbox'}
- **mm/calendar-consistency/umm-al-qura/1440** (metamorphic; CAL-006, CAL-003): {'code': 'INTERNAL_ERROR', 'message': 'NotImplementedError: ephem unavailable in this sandbox'}
- **mm/calendar-consistency/umm-al-qura/1441** (metamorphic; CAL-006, CAL-003): {'code': 'INTERNAL_ERROR', 'message': 'NotImplementedError: ephem unavailable in this sandbox'}
- **mm/calendar-consistency/umm-al-qura/1445** (metamorphic; CAL-006, CAL-003): {'code': 'INTERNAL_ERROR', 'message': 'NotImplementedError: ephem unavailable in this sandbox'}
- **mm/calendar-consistency/umm-al-qura/1446** (metamorphic; CAL-006, CAL-003): {'code': 'INTERNAL_ERROR', 'message': 'NotImplementedError: ephem unavailable in this sandbox'}
- **mm/calendar-consistency/umm-al-qura/1447** (metamorphic; CAL-006, CAL-003): {'code': 'INTERNAL_ERROR', 'message': 'NotImplementedError: ephem unavailable in this sandbox'}
- **mm/calendar-consistency/umm-al-qura/1448** (metamorphic; CAL-006, CAL-003): {'code': 'INTERNAL_ERROR', 'message': 'NotImplementedError: ephem unavailable in this sandbox'}
- **mm/calendar-consistency/umm-al-qura/1450** (metamorphic; CAL-006, CAL-003): {'code': 'INTERNAL_ERROR', 'message': 'NotImplementedError: ephem unavailable in this sandbox'}
- **mm/provider-isolation/addis** (metamorphic; CAL-010): umm-al-qura: failed
- **mm/provider-isolation/london** (metamorphic; CAL-010): umm-al-qura: failed
- **mm/provider-isolation/kiritimati** (metamorphic; CAL-010): umm-al-qura: failed
- **mm/provider-isolation/makkah** (metamorphic; CAL-010): umm-al-qura: failed

## 5. Open-question and informative divergences — reference

- **uaq/year-table/1420** (informative; CAL-007, CAL-006): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **uaq/year-table/1421** (informative; CAL-007, CAL-006): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **uaq/year-table/1422** (informative; CAL-007, CAL-006): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **uaq/year-table/1423** (informative; CAL-007, CAL-006): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **uaq/year-table/1424** (informative; CAL-007, CAL-006): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **uaq/year-table/1425** (informative; CAL-007, CAL-006): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **uaq/year-table/1426** (informative; CAL-007, CAL-006): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **uaq/year-table/1427** (informative; CAL-007, CAL-006): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **uaq/year-table/1428** (informative; CAL-007, CAL-006): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **uaq/year-table/1429** (informative; CAL-007, CAL-006): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **uaq/year-table/1430** (informative; CAL-007, CAL-006): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **uaq/year-table/1431** (informative; CAL-007, CAL-006): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **uaq/year-table/1432** (informative; CAL-007, CAL-006): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **uaq/year-table/1433** (informative; CAL-007, CAL-006): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **uaq/year-table/1434** (informative; CAL-007, CAL-006): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **uaq/year-table/1435** (informative; CAL-007, CAL-006): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **uaq/year-table/1436** (informative; CAL-007, CAL-006): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **uaq/year-table/1437** (informative; CAL-007, CAL-006): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **uaq/year-table/1438** (informative; CAL-007, CAL-006): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **uaq/year-table/1439** (informative; CAL-007, CAL-006): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **uaq/year-table/1440** (informative; CAL-007, CAL-006): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **uaq/year-table/1441** (informative; CAL-007, CAL-006): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **uaq/year-table/1442** (informative; CAL-007, CAL-006): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **uaq/year-table/1443** (informative; CAL-007, CAL-006): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **uaq/year-table/1444** (informative; CAL-007, CAL-006): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **uaq/year-table/1445** (informative; CAL-007, CAL-006): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **uaq/year-table/1446** (informative; CAL-007, CAL-006): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **uaq/year-table/1447** (informative; CAL-007, CAL-006): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **uaq/year-table/1448** (informative; CAL-007, CAL-006): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **uaq/year-table/1449** (informative; CAL-007, CAL-006): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **uaq/year-table/1450** (informative; CAL-007, CAL-006): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **uaq/year-table/1451** (informative; CAL-007, CAL-006): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **uaq/year-table/1452** (informative; CAL-007, CAL-006): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **uaq/year-table/1453** (informative; CAL-007, CAL-006): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **uaq/year-table/1454** (informative; CAL-007, CAL-006): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **uaq/year-table/1455** (informative; CAL-007, CAL-006): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **uaq/year-table/1456** (informative; CAL-007, CAL-006): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **uaq/year-table/1457** (informative; CAL-007, CAL-006): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **uaq/year-table/1458** (informative; CAL-007, CAL-006): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **uaq/year-table/1459** (informative; CAL-007, CAL-006): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **uaq/year-table/1460** (informative; CAL-007, CAL-006): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **uaq/range/1700-01-01** (informative; CAL-011): $ expected `expected success` got `{"code": "UNKNOWN_CALENDAR_PROVIDER", "message": "ephem unavailable in this sandbox"}`
- **uaq/range/2300-12-31** (informative; CAL-011): $ expected `expected success` got `{"code": "UNKNOWN_CALENDAR_PROVIDER", "message": "ephem unavailable in this sandbox"}`
- **err/profile/fajr-95** (open; ERR-004): $ expected `expected error ['VALIDATION_ERROR']` got `succeeded: {"status": "OK", "undefined_reason": null, "instant": "2026-09-19T15:42:00+00:00", "timezone": "UTC", "profile": {"fajr_angle_deg": 95.0, "isha_angle_deg": 17....`
- **err/profile/fajr-negative** (open; ERR-004): $ expected `expected error ['VALIDATION_ERROR']` got `succeeded: {"status": "OK", "undefined_reason": null, "instant": "2026-09-19T15:42:00+00:00", "timezone": "UTC", "profile": {"fajr_angle_deg": -5.0, "isha_angle_deg": 17....`
- **err/profile/isha-zero** (open; ERR-004): $ expected `expected error ['VALIDATION_ERROR']` got `succeeded: {"status": "OK", "undefined_reason": null, "instant": "2026-09-19T15:42:00+00:00", "timezone": "UTC", "profile": {"fajr_angle_deg": 18.0, "isha_angle_deg": 0.0...`
- **err/profile/asr-zero** (open; ERR-004): $ expected `expected error ['VALIDATION_ERROR']` got `succeeded: {"status": "OK", "undefined_reason": null, "instant": "2026-09-19T15:42:00+00:00", "timezone": "UTC", "profile": {"fajr_angle_deg": 18.0, "isha_angle_deg": 17....`
- **err/profile/asr-negative** (open; ERR-004): $ expected `expected error ['VALIDATION_ERROR']` got `succeeded: {"status": "OK", "undefined_reason": null, "instant": "2026-09-19T15:42:00+00:00", "timezone": "UTC", "profile": {"fajr_angle_deg": 18.0, "isha_angle_deg": 17....`
- **ins/rule-month-day-muharram-1-umm-al-qura/computed** (informative; INS-001, CAL-007): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **ins/rule-month-end-dhul-hijjah-umm-al-qura/computed** (informative; INS-001, CAL-007): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **ins/rule-first-ahad-muharram-umm-al-qura/computed** (informative; INS-001, CAL-007): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **ins/rule-last-khamis-shaban-umm-al-qura/computed** (informative; INS-001, CAL-007): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **ins/rule-second-jumuah-muharram-umm-al-qura/computed** (informative; INS-001, CAL-007): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **ins/fiscal-year-default-umm-al-qura-1447/computed** (informative; INS-003, CAL-007): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **ins/fiscal-year-default-umm-al-qura-1448/computed** (informative; INS-003, CAL-007): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **ins/fiscal-year-custom-umm-al-qura/computed** (informative; INS-003, CAL-007): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **ins/academic-year-umm-al-qura/computed** (informative; INS-004, CAL-007): $ expected `expected success` got `{"code": "INTERNAL_ERROR", "message": "NotImplementedError: ephem unavailable in this sandbox"}`
- **date/basic-format-20260101** (open; TIME-003): $ expected `expected error ['INVALID_DATE', 'VALIDATION_ERROR']` got `succeeded: {"weekday_iso": 4, "weekday_name_islamic": "al-Khamis", "is_leap_year": false, "days_in_month": 31}`
- **instant/fraction-echo** (open; TIME-001): $.instant expected `2026-09-19T15:42:00.123456+00:00` got `2026-09-19T15:42:00+00:00`
- **instant/naive** (open; TIME-002): $ expected `expected error ['INVALID_INSTANT', 'VALIDATION_ERROR']` got `succeeded: {"instant": "2026-09-19T15:42:00+00:00"}`
- **aladhan/retry-after-short** (open; PRV-005): $.steps[0].provider expected `umm-al-qura` got `arithmetic-tabular`
- **aladhan/three-soft-failures-open-circuit** (open; PRV-007): $.steps[0].provider expected `umm-al-qura` got `arithmetic-tabular`
- **aladhan/outbound-budget** (open; PRV-007): $.steps[2].provider expected `umm-al-qura` got `arithmetic-tabular`
- **live/15-kiritimati-day_bounds** (informative; SCH-006, SCH-008): $.hijri_label expected `1448-04-06` got `1448-04-07`

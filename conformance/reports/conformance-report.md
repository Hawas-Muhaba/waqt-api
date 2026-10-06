# Waqt conformance report

Generated 2026-10-06 03:47 UTC by `harness/waqt_conform.py` · COP 1.1 · 733 vectors + 43 metamorphic checks.

Reproduce: `python3 conformance/harness/waqt_conform.py --adapter "python3 conformance/adapters/reference_adapter.py" --label reference --adapter "node conformance/independent/src/cli.mjs" --label independent`

## 0. Contract and unresolved questions

Contract **2.0.0** (DRAFT - not yet released/ratified) - sha256 `c2ed8ff1c7f9a757` - manifest matches - COP 1.1.

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
| independent | waqt-independent 0.1.0 | JavaScript (Node.js, zero dependencies) | False | 31.44 s |
| reference | waqt-reference waqt-core 0.4.0 / waqt-api 0.4.0 | Python | n/a (this is the reference) | 15.54 s |

## 2. Results by tier

Normative tiers (`exact`, `tolerance`) and metamorphic checks decide conformance. `open` and `informative` vectors are reported but never counted as failures (see CONFORMANCE.md §4).

| tier | independent pass / fail / n.a. | reference pass / fail / n.a. |
|---|---|---|
| exact | 479 / 0 / 0 | 476 / 0 / 3 |
| tolerance | 182 / 0 / 0 | 182 / 0 / 0 |
| open | 11 / 0 / 0 | 2 / 9 / 0 |
| informative | 55 / 6 / 0 | 60 / 1 / 0 |
| metamorphic | 43 / 0 / 0 | 43 / 0 / 0 |

## 3. Requirements

`PASS` = every normative vector for the requirement passes; `FAIL` = at least one fails; `OPEN-ONLY` = only open/informative vectors exist; `NO-DATA` = no vector yet.

| requirement | kind | independent | reference | title |
|---|---|---|---|---|
| AST-001 | MUST | PASS (137/137) | PASS (137/137) | The Asr target altitude uses the Sun's declination at the UPPER TRANSIT of the date (the noon shadow); the crossing instant is then solved with the Sun's position at the crossing |
| AST-002 | MUST | PASS (1/1) | PASS (1/1) | Asr is undefined (omitted, UND-002) exactly when the Sun's geometric altitude at upper transit is <= 0 deg |
| CAL-001 | MUST | PASS (29/29) | PASS (29/29) | arithmetic-tabular conversion Gregorian -> Hijri (epoch JDN 1948440) |
| CAL-002 | MUST | PASS (30/30) | PASS (30/30) | arithmetic-tabular leap years are the positions 2,5,7,10,13,16,18,21,24,26,29 of the 30-year cycle ((11*y+14) mod 30 < 11); a different pattern is a different provider, never a substitution |
| CAL-003 | MUST | PASS (31/31) | PASS (31/31) | arithmetic-tabular reverse conversion is exact and round-trips |
| CAL-004 | MUST | PASS (10/10) | PASS (10/10) | A Hijri date that does not exist is rejected, never normalised: year < 1, or a day beyond the month's length in that provider, is INVALID_HIJRI_DATE (out-of-range month/day numerals MAY be VALIDATION_ERROR) |
| CAL-005 | MUST | PASS (9/9) | PASS (9/9) | umm-al-qura reproduces the validated New Year dates (1438, 1440, 1441, 1447) |
| CAL-006 | MUST | PASS (8/8) | PASS (8/8) | umm-al-qura months have 29 or 30 days and Gregorian<->Hijri round-trips |
| CAL-007 | OPEN | OPEN-ONLY | OPEN-ONLY | umm-al-qura month boundaries away from the validated anchors: UNRESOLVED BY DESIGN (institutional convention; see OQ-UAQ-2) |
| CAL-008 | MUST | PASS (5/5) | PASS (5/5) | declared / local-observation override applies only on the exact label date; otherwise tabular |
| CAL-009 | MUST | PASS (3/3) | PASS (3/3) | Providers without a fixed rule reject reverse conversion (UNSUPPORTED_OPERATION) |
| CAL-010 | MUST | PASS (13/13) | PASS (10/10) | Swapping the calendar provider changes only the label, never an instant or position |
| CAL-011 | MUST | PASS (4/4) | PASS (4/4) | umm-al-qura is supported for 1700-01-01..2300-12-31 only; outside it the provider refuses with OUT_OF_RANGE |
| DAY-001 | MUST | PASS (152/152) | PASS (152/152) | A Waqt day is the half-open interval [Maghrib(D), Maghrib(D+1)) |
| DAY-002 | MUST | PASS (8/8) | PASS (8/8) | At the exact opening Maghrib the new day has begun (position 00:00:00) |
| DAY-003 | MUST | PASS (8/8) | PASS (8/8) | One microsecond before a Maghrib belongs to the previous day; days tile without gap or overlap |
| DAY-004 | MUST | PASS (162/162) | PASS (162/162) | The day label (Hijri date, weekday) is that of the civil date, in the location's IANA zone, on which the CLOSING Maghrib INSTANT falls |
| DAY-005 | MUST | PASS (151/151) | PASS (151/151) | Position is elapsed SI time since the opening Maghrib and is not clamped at 24:00:00 |
| DAY-006 | MUST | PASS (137/137) | PASS (137/137) | Day length is the real interval, not 86400 s |
| DAY-007 | MUST | PASS (293/293) | PASS (293/293) | Civil dates use the location's IANA zone (date line, DST) — not UTC and not solar time |
| DAY-008 | MUST | PASS (8/8) | PASS (8/8) | The Waqt day depends only on the instant: all instants inside a day give the same day and events |
| DAY-009 | MUST | PASS (2/2) | PASS (2/2) | Labels follow DAY-004 even where it makes them non-injective: a civil date with NO closing Maghrib resolves to nothing (resolved=false), a civil date with TWO resolves to the day containing its local noon; labels never decrease |
| ERR-001 | MUST | PASS (4/4) | PASS (4/4) | Out-of-range latitude/longitude is rejected |
| ERR-002 | MUST | PASS (2/2) | PASS (2/2) | An unknown IANA time zone is rejected with UNKNOWN_TIMEZONE (a client error, never INTERNAL_ERROR) |
| ERR-003 | MUST | PASS (2/2) | PASS (2/2) | Unknown calendar provider is rejected |
| ERR-004 | MUST | OPEN-ONLY | OPEN-ONLY | Non-physical astronomy profile parameters are rejected |
| EVT-001 | MUST | PASS (144/144) | PASS (144/144) | Event definitions: Fajr/Isha angles, sunrise/Maghrib -0.8333 deg, Dhuhr transit, Asr shadow ratio (accuracy bands in CONFORMANCE 5) |
| EVT-002 | MUST | PASS (151/151) | PASS (151/151) | An event's reading is its instant minus the day's opening Maghrib |
| EVT-003 | MUST | PASS (8/8) | PASS (8/8) | The closing Maghrib is listed at the day length; Isha is listed beyond the day length |
| EVT-004 | MUST | PASS (6/6) | PASS (6/6) | An event belongs to the Waqt day around its own upper transit, even after local midnight; the event listing never moves to the next civil date |
| EVT-005 | MUST | PASS (12/12) | PASS (12/12) | Fajr/Isha angle and Asr ratio change only their own event, never the day boundary |
| EVT-006 | MUST | PASS (4/4) | PASS (4/4) | Elevation (dip) shifts sunrise and Maghrib only |
| EVT-007 | MUST | PASS (1/1) | PASS (1/1) | waqt.compute next_event is the next event by OCCURRENCE: the earliest event strictly after the instant, including the previous solar day's Isha (never only the listed events) |
| GREG-001 | MUST | PASS (12/12) | PASS (12/12) | Proleptic Gregorian leap-year rule (4 / 100 / 400) |
| GREG-002 | MUST | PASS (12/12) | PASS (12/12) | Weekday naming: ISO number and Sunday-first Islamic names |
| GREG-003 | MUST | PASS (12/12) | PASS (12/12) | Days in month |
| INS-001 | MUST | PASS (15/15) | PASS (15/15) | Calendar rules: month_day, month_end, nth_weekday_of_month |
| INS-002 | MUST | PASS (4/4) | PASS (4/4) | Islamic week: seven consecutive days from a configurable first day |
| INS-003 | MUST | PASS (13/13) | PASS (13/13) | Fiscal year resolves start/end rules; end before start is rejected |
| INS-004 | MUST | PASS (3/3) | PASS (3/3) | Academic year: opening, closing, terms, holidays |
| INS-005 | MUST | PASS (6/6) | PASS (6/6) | Unresolvable rules fail with INVALID_CALENDAR_RULE |
| INT-001 | MUST | PASS (7/7) | PASS (7/7) | Instant representation: UTC and civil Gregorian views of one instant, plus Waqt position |
| INT-002 | MUST | PASS (7/7) | PASS (7/7) | Gregorian date + place -> the Waqt day whose closing Maghrib falls on that date |
| INT-003 | MUST | PASS (6/6) | PASS (6/6) | Boundary crossing: civil midnight and Maghrib independent; strictly-interior rule |
| PRV-001 | MUST | PASS (5/5) | PASS (5/5) | Hard remote failures (timeout, network error, 429, 5xx) fall back to local umm-al-qura with the stable reason code |
| PRV-002 | MUST | PASS (7/7) | PASS (7/7) | Soft failures (4xx, malformed, date-mismatch, implausible) fall back with the stable reason code |
| PRV-003 | MUST | PASS (4/4) | PASS (4/4) | Dates outside 1900-01-01..2076-12-31 and a disabled provider never leave the process |
| PRV-004 | MUST | PASS (4/4) | PASS (4/4) | Cache hit within the TTL; stale-if-error up to 7 days, labelled remote-stale |
| PRV-005 | MUST | PASS (2/2) | PASS (2/2) | Circuit breaker after a hard failure; Retry-After honoured and capped |
| PRV-006 | MUST | PASS (11/11) | PASS (11/11) | The fallback result names the provider that actually produced it |
| PRV-007 | OPEN | OPEN-ONLY | OPEN-ONLY | Soft-failure counting and outbound budget details |
| SCH-001 | MUST | PASS (40/40) | PASS (37/37) | Point resolution: instant, anchor, event slots, next/prev occurrence, position, offset, fraction |
| SCH-002 | MUST | PASS (32/32) | PASS (32/32) | Windows are half-open; unbounded ends; inside/before/after relation |
| SCH-003 | MUST | PASS (14/14) | PASS (14/14) | Deadlines: pending / reached / passed with signed remaining seconds |
| SCH-004 | MUST | PASS (25/25) | PASS (25/25) | Three undefined statuses; strict vs skip policy; evaluate reports unknown, not false |
| SCH-005 | MUST | PASS (15/15) | PASS (15/15) | Span classification: strict-interior Maghrib crossing, civil midnight independent |
| SCH-006 | MUST | PASS (21/21) | PASS (21/21) | event_position reports listed and containing positions; next_event/until/since |
| SCH-007 | MUST | PASS (3/3) | PASS (3/3) | Derived instants use integer microseconds with half-up rounding |
| SCH-008 | MUST | PASS (16/16) | PASS (16/16) | Scheduling over LIVE astronomy agrees with the table-driven result within astronomy tolerance |
| SCH-009 | MUST | PASS (3/3) | PASS (3/3) | next_event/prev_event points carry `inclusive` (default true): at an instant exactly equal to an event, inclusive resolves to that event, exclusive to the next (prev: previous) one |
| SCH-010 | MUST | PASS (5/5) | PASS (5/5) | event_position default slot: isha and maghrib resolve in the PREVIOUS listing, every other event in day 0; the result reports `listed` and `containing` positions |
| SCH-011 | MUST | PASS (5/5) | PASS (5/5) | An empty or inverted window/span is status NO_VALID_WINDOW with duration_seconds null; WINDOW_UNDEFINED reports maghrib_boundaries as [] |
| SCH-012 | MUST | PASS (5/5) | PASS (5/5) | A strict resolution (default) that meets an undefined event slot ends as EVENT_UNDEFINED / EVENT_UNDEFINED_ON_DAY naming it in undefined_ref; with on_undefined=skip the slot is listed in `skipped` and the scan continues over at most 8 day-slots, ending NO_OCCURRENCE_IN_RANGE if none is found |
| SCH-013 | MUST | PASS (2/2) | PASS (2/2) | An event point at a day offset whose Waqt day, or a day stepped across to reach it, has an undefined bounding Maghrib is EVENT_UNDEFINED with cause DAY_UNDEFINED, even when the target lies outside the context's day table |
| TIME-001 | MUST | PASS (6/6) | PASS (6/6) | Instants carry an explicit UTC offset; non-UTC offsets are normalised to UTC |
| TIME-002 | OPEN | OPEN-ONLY | OPEN-ONLY | Offset-less ('naive') instants: rejected, or assumed to be UTC |
| TIME-003 | MUST | PASS (14/14) | PASS (14/14) | Malformed or non-existent instants/dates are rejected with INVALID_INSTANT / INVALID_DATE |
| UND-001 | MUST | PASS (14/14) | PASS (14/14) | Polar day/night (no Maghrib): status UNDEFINED with a reason, never a guessed time; a day with exactly ONE undefined bounding Maghrib is wholly UNDEFINED |
| UND-002 | MUST | PASS (19/19) | PASS (19/19) | An event that does not occur is omitted, never approximated; other events remain defined |
| UND-003 | MUST | PASS (26/26) | PASS (26/26) | Both implementations must agree on WHICH events exist away from the transition latitude |
| UND-004 | OPEN | NO-DATA | NO-DATA | Existence of GRAZING events (Sun within arc-minutes of a threshold): unresolved, scan strategy is implementation-defined |

## 4. Failing normative vectors — independent

None.


## 4. Failing normative vectors — reference

None.


## 5. Open-question and informative divergences — independent

- **uaq/year-table/1420** (informative; CAL-007, CAL-006): $.months[9].length expected `29` got `30`
- **uaq/year-table/1446** (informative; CAL-007, CAL-006): $.months[4].length expected `29` got `30`
- **interop/instant/one-second-before-maghrib** (informative; INT-001, DAY-007): $.waqt_position_seconds expected `86401.137` got `0.240126`
- **interop/boundary/ends-exactly-at-maghrib** (informative; INT-003): $.crosses_maghrib expected `false` got `true`
- **waqt/london-long-day-near-24h-boundary** (informative; DAY-001, EVT-001, DAY-004, DAY-005, EVT-002): $.day.open expected `2026-02-14T17:13:44.159299+00:00` got `2026-02-14T17:13:40.639907+00:00`
- **live/15-kiritimati-day_bounds** (informative; SCH-006, SCH-008): $.hijri_label expected `1448-04-06` got `1448-04-07`

## 5. Open-question and informative divergences — reference

- **err/profile/fajr-95** (open; ERR-004): $ expected `expected error ['VALIDATION_ERROR']` got `succeeded: {"status": "OK", "undefined_reason": null, "instant": "2026-09-19T15:42:00+00:00", "timezone": "UTC", "profile": {"fajr_angle_deg": 95.0, "isha_angle_deg": 17....`
- **err/profile/fajr-negative** (open; ERR-004): $ expected `expected error ['VALIDATION_ERROR']` got `succeeded: {"status": "OK", "undefined_reason": null, "instant": "2026-09-19T15:42:00+00:00", "timezone": "UTC", "profile": {"fajr_angle_deg": -5.0, "isha_angle_deg": 17....`
- **err/profile/isha-zero** (open; ERR-004): $ expected `expected error ['VALIDATION_ERROR']` got `succeeded: {"status": "OK", "undefined_reason": null, "instant": "2026-09-19T15:42:00+00:00", "timezone": "UTC", "profile": {"fajr_angle_deg": 18.0, "isha_angle_deg": 0.0...`
- **err/profile/asr-zero** (open; ERR-004): $ expected `expected error ['VALIDATION_ERROR']` got `succeeded: {"status": "OK", "undefined_reason": null, "instant": "2026-09-19T15:42:00+00:00", "timezone": "UTC", "profile": {"fajr_angle_deg": 18.0, "isha_angle_deg": 17....`
- **err/profile/asr-negative** (open; ERR-004): $ expected `expected error ['VALIDATION_ERROR']` got `succeeded: {"status": "OK", "undefined_reason": null, "instant": "2026-09-19T15:42:00+00:00", "timezone": "UTC", "profile": {"fajr_angle_deg": 18.0, "isha_angle_deg": 17....`
- **date/basic-format-20260101** (open; TIME-003): $ expected `expected error ['INVALID_DATE', 'VALIDATION_ERROR']` got `succeeded: {"weekday_iso": 4, "weekday_name_islamic": "al-Khamis", "is_leap_year": false, "days_in_month": 31}`
- **instant/fraction-echo** (open; TIME-001): $.instant expected `2026-09-19T15:42:00.123456+00:00` got `2026-09-19T15:42:00+00:00`
- **instant/naive** (open; TIME-002): $ expected `expected error ['INVALID_INSTANT', 'VALIDATION_ERROR']` got `succeeded: {"instant": "2026-09-19T15:42:00+00:00"}`
- **aladhan/retry-after-short** (open; PRV-005): $.steps[2].provider expected `aladhan` got `umm-al-qura`
- **live/15-kiritimati-day_bounds** (informative; SCH-006, SCH-008): $.hijri_label expected `1448-04-06` got `1448-04-07`

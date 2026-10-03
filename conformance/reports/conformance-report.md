# Waqt conformance report

Generated 2026-10-03 08:32 UTC by `harness/waqt_conform.py` · COP 1.0 · 726 vectors + 43 metamorphic checks.

Reproduce: `python3 conformance/harness/waqt_conform.py --adapter "python3 conformance/adapters/reference_adapter.py" --label reference --adapter "node conformance/independent/src/cli.mjs" --label independent`

## 1. Implementations

| label | implementation | language | shares code with reference | run time |
|---|---|---|---|---|
| reference | waqt-reference waqt-core 0.3.0 / waqt-api 0.3.0 | Python | n/a (this is the reference) | 10.0 s |
| independent | waqt-independent 0.1.0 | JavaScript (Node.js, zero dependencies) | False | 11.24 s |

## 2. Results by tier

Normative tiers (`exact`, `tolerance`) and metamorphic checks decide conformance. `open` and `informative` vectors are reported but never counted as failures (see CONFORMANCE.md §4).

| tier | reference pass / fail / n.a. | independent pass / fail / n.a. |
|---|---|---|
| exact | 409 / 28 / 3 | 440 / 0 / 0 |
| tolerance | 180 / 0 / 0 | 180 / 0 / 0 |
| open | 37 / 10 / 0 | 43 / 4 / 0 |
| informative | 59 / 0 / 0 | 53 / 6 / 0 |
| metamorphic | 43 / 0 / 0 | 43 / 0 / 0 |

## 3. Requirements

`PASS` = every normative vector for the requirement passes; `FAIL` = at least one fails; `OPEN-ONLY` = only open/informative vectors exist; `NO-DATA` = no vector yet.

| requirement | kind | reference | independent | title |
|---|---|---|---|---|
| CAL-001 | MUST | PASS (29/29) | PASS (29/29) | arithmetic-tabular conversion Gregorian -> Hijri (epoch JDN 1948440) |
| CAL-002 | OPEN | OPEN-ONLY | OPEN-ONLY | arithmetic-tabular leap-year pattern within the 30-year cycle |
| CAL-003 | MUST | PASS (31/31) | PASS (31/31) | arithmetic-tabular reverse conversion is exact and round-trips |
| CAL-004 | MUST | FAIL (6/8) | PASS (8/8) | Non-existent Hijri dates are rejected (INVALID_HIJRI_DATE), never silently normalised |
| CAL-005 | MUST | PASS (9/9) | PASS (9/9) | umm-al-qura reproduces the validated New Year dates (1438, 1440, 1441, 1447) |
| CAL-006 | MUST | PASS (8/8) | PASS (8/8) | umm-al-qura months have 29 or 30 days and Gregorian<->Hijri round-trips |
| CAL-007 | OPEN | OPEN-ONLY | OPEN-ONLY | umm-al-qura month boundaries away from the validated anchors (threshold-sensitive months) |
| CAL-008 | MUST | PASS (5/5) | PASS (5/5) | declared / local-observation override applies only on the exact label date; otherwise tabular |
| CAL-009 | MUST | PASS (3/3) | PASS (3/3) | Providers without a fixed rule reject reverse conversion (UNSUPPORTED_OPERATION) |
| CAL-010 | MUST | PASS (10/10) | PASS (13/13) | Swapping the calendar provider changes only the label, never an instant or position |
| CAL-011 | OPEN | OPEN-ONLY | OPEN-ONLY | umm-al-qura supported range and the error returned outside it |
| DAY-001 | MUST | PASS (152/152) | PASS (152/152) | A Waqt day is the half-open interval [Maghrib(D), Maghrib(D+1)) |
| DAY-002 | MUST | PASS (8/8) | PASS (8/8) | At the exact opening Maghrib the new day has begun (position 00:00:00) |
| DAY-003 | MUST | PASS (8/8) | PASS (8/8) | One microsecond before a Maghrib belongs to the previous day; days tile without gap or overlap |
| DAY-004 | MUST | FAIL (135/160) | PASS (160/160) | The day label (Hijri date, weekday) is that of the civil date on which the CLOSING Maghrib falls |
| DAY-005 | MUST | PASS (151/151) | PASS (151/151) | Position is elapsed SI time since the opening Maghrib and is not clamped at 24:00:00 |
| DAY-006 | MUST | PASS (137/137) | PASS (137/137) | Day length is the real interval, not 86400 s |
| DAY-007 | MUST | FAIL (269/293) | PASS (293/293) | Civil dates use the location's IANA zone (date line, DST) — not UTC and not solar time |
| DAY-008 | MUST | PASS (8/8) | PASS (8/8) | The Waqt day depends only on the instant: all instants inside a day give the same day and events |
| ERR-001 | MUST | PASS (4/4) | PASS (4/4) | Out-of-range latitude/longitude is rejected |
| ERR-002 | MUST | FAIL (0/1) | PASS (1/1) | Unknown IANA time zone is rejected |
| ERR-003 | MUST | PASS (2/2) | PASS (2/2) | Unknown calendar provider is rejected |
| ERR-004 | MUST | OPEN-ONLY | OPEN-ONLY | Non-physical astronomy profile parameters are rejected |
| EVT-001 | MUST | PASS (144/144) | PASS (144/144) | Event definitions: Fajr/Isha angles, sunrise/Maghrib -0.8333 deg, Dhuhr transit, Asr shadow ratio (accuracy bands in CONFORMANCE 5) |
| EVT-002 | MUST | PASS (151/151) | PASS (151/151) | An event's reading is its instant minus the day's opening Maghrib |
| EVT-003 | MUST | PASS (8/8) | PASS (8/8) | The closing Maghrib is listed at the day length; Isha is listed beyond the day length |
| EVT-004 | MUST | PASS (6/6) | PASS (6/6) | Events after local midnight stay in the day of their transit (never move to the next civil date) |
| EVT-005 | MUST | PASS (12/12) | PASS (12/12) | Fajr/Isha angle and Asr ratio change only their own event, never the day boundary |
| EVT-006 | MUST | PASS (4/4) | PASS (4/4) | Elevation (dip) shifts sunrise and Maghrib only |
| EVT-007 | OPEN | OPEN-ONLY | OPEN-ONLY | waqt.compute next_event: by OCCURRENCE (includes tonight's Isha) or only among the listed events |
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
| SCH-001 | MUST | PASS (37/37) | PASS (40/40) | Point resolution: instant, anchor, event slots, next/prev occurrence, position, offset, fraction |
| SCH-002 | MUST | PASS (32/32) | PASS (32/32) | Windows are half-open; unbounded ends; inside/before/after relation |
| SCH-003 | MUST | PASS (14/14) | PASS (14/14) | Deadlines: pending / reached / passed with signed remaining seconds |
| SCH-004 | MUST | PASS (25/25) | PASS (25/25) | Three undefined statuses; strict vs skip policy; evaluate reports unknown, not false |
| SCH-005 | MUST | PASS (15/15) | PASS (15/15) | Span classification: strict-interior Maghrib crossing, civil midnight independent |
| SCH-006 | MUST | PASS (21/21) | PASS (21/21) | event_position reports listed and containing positions; next_event/until/since |
| SCH-007 | MUST | PASS (3/3) | PASS (3/3) | Derived instants use integer microseconds with half-up rounding |
| SCH-008 | MUST | PASS (16/16) | PASS (16/16) | Scheduling over LIVE astronomy agrees with the table-driven result within astronomy tolerance |
| TIME-001 | MUST | PASS (6/6) | PASS (6/6) | Instants carry an explicit UTC offset; non-UTC offsets are normalised to UTC |
| TIME-002 | OPEN | OPEN-ONLY | OPEN-ONLY | Offset-less ('naive') instants: rejected, or assumed to be UTC |
| TIME-003 | MUST | PASS (14/14) | PASS (14/14) | Malformed or non-existent instants/dates are rejected with INVALID_INSTANT / INVALID_DATE |
| UND-001 | MUST | PASS (14/14) | PASS (14/14) | Polar day/night (no Maghrib): status UNDEFINED with a reason, never a guessed time |
| UND-002 | MUST | PASS (19/19) | PASS (19/19) | An event that does not occur is omitted, never approximated; other events remain defined |
| UND-003 | MUST | PASS (26/26) | PASS (26/26) | Both implementations must agree on WHICH events exist away from the transition latitude |
| UND-004 | OPEN | OPEN-ONLY | OPEN-ONLY | Existence of grazing events within a few arc-minutes of their threshold |

## 4. Failing normative vectors — reference

- **tab/invalid/1448-2-30** (exact; CAL-004)
  - `$` expected `expected error ['INVALID_HIJRI_DATE', 'VALIDATION_ERROR', 'INVALID_DATE']` got `succeeded: {"date": "2026-08-15"}`
- **tab/invalid/0-1-1** (exact; CAL-004)
  - `$` expected `expected error ['INVALID_HIJRI_DATE', 'VALIDATION_ERROR', 'INVALID_DATE']` got `succeeded: {"date": "0621-07-30"}`
- **label/reykjavik/2026-06-21/after-midnight** (exact; DAY-004, DAY-007)
  - `$.hijri.date` expected `1448-01-06` got `1448-01-05`
  - `$.weekday` expected `al-Ithnayn` got `al-Ahad`
- **label/reykjavik/2026-06-21/midday** (exact; DAY-004, DAY-007)
  - `$.hijri.date` expected `1448-01-06` got `1448-01-05`
  - `$.weekday` expected `al-Ithnayn` got `al-Ahad`
- **label/reykjavik/2026-06-21/late-evening** (exact; DAY-004, DAY-007)
  - `$.hijri.date` expected `1448-01-06` got `1448-01-05`
  - `$.weekday` expected `al-Ithnayn` got `al-Ahad`
- **label/kiritimati/2026-09-19/after-midnight** (exact; DAY-004, DAY-007)
  - `$.hijri.date` expected `1448-04-06` got `1448-04-05`
  - `$.weekday` expected `as-Sabt` got `al-Jumuah`
- **label/kiritimati/2026-09-19/midday** (exact; DAY-004, DAY-007)
  - `$.hijri.date` expected `1448-04-06` got `1448-04-05`
  - `$.weekday` expected `as-Sabt` got `al-Jumuah`
- **label/kiritimati/2026-09-19/late-evening** (exact; DAY-004, DAY-007)
  - `$.hijri.date` expected `1448-04-07` got `1448-04-06`
  - `$.weekday` expected `al-Ahad` got `as-Sabt`
- **label/kiritimati/2026-06-21/after-midnight** (exact; DAY-004, DAY-007)
  - `$.hijri.date` expected `1448-01-05` got `1448-01-04`
  - `$.weekday` expected `al-Ahad` got `as-Sabt`
- **label/kiritimati/2026-06-21/midday** (exact; DAY-004, DAY-007)
  - `$.hijri.date` expected `1448-01-05` got `1448-01-04`
  - `$.weekday` expected `al-Ahad` got `as-Sabt`
- **label/kiritimati/2026-06-21/late-evening** (exact; DAY-004, DAY-007)
  - `$.hijri.date` expected `1448-01-06` got `1448-01-05`
  - `$.weekday` expected `al-Ithnayn` got `al-Ahad`
- **label/apia/2026-03-20/after-midnight** (exact; DAY-004, DAY-007)
  - `$.hijri.date` expected `1447-10-01` got `1447-09-30`
  - `$.weekday` expected `al-Jumuah` got `al-Khamis`
- **label/apia/2026-03-20/midday** (exact; DAY-004, DAY-007)
  - `$.hijri.date` expected `1447-10-01` got `1447-09-30`
  - `$.weekday` expected `al-Jumuah` got `al-Khamis`
- **label/apia/2026-03-20/late-evening** (exact; DAY-004, DAY-007)
  - `$.hijri.date` expected `1447-10-02` got `1447-10-01`
  - `$.weekday` expected `as-Sabt` got `al-Jumuah`
- **label/apia/2026-12-30/after-midnight** (exact; DAY-004, DAY-007)
  - `$.hijri.date` expected `1448-07-20` got `1448-07-19`
  - `$.weekday` expected `al-Arbiaa` got `ath-Thulatha`
- **label/apia/2026-12-30/midday** (exact; DAY-004, DAY-007)
  - `$.hijri.date` expected `1448-07-20` got `1448-07-19`
  - `$.weekday` expected `al-Arbiaa` got `ath-Thulatha`
- **label/apia/2026-12-30/late-evening** (exact; DAY-004, DAY-007)
  - `$.hijri.date` expected `1448-07-21` got `1448-07-20`
  - `$.weekday` expected `al-Khamis` got `al-Arbiaa`
- **label/chatham/2026-09-27/after-midnight** (exact; DAY-004, DAY-007)
  - `$.hijri.date` expected `1448-04-14` got `1448-04-13`
  - `$.weekday` expected `al-Ahad` got `as-Sabt`
- **label/chatham/2026-09-27/midday** (exact; DAY-004, DAY-007)
  - `$.hijri.date` expected `1448-04-14` got `1448-04-13`
  - `$.weekday` expected `al-Ahad` got `as-Sabt`
- **label/chatham/2026-09-27/late-evening** (exact; DAY-004, DAY-007)
  - `$.hijri.date` expected `1448-04-15` got `1448-04-14`
  - `$.weekday` expected `al-Ithnayn` got `al-Ahad`
- **label/date-to-waqt-day/kiritimati/2026-09-20** (exact; DAY-004, DAY-007)
  - `$.hijri_date` expected `1448-04-07` got `1448-04-06`
  - `$.weekday` expected `al-Ahad` got `as-Sabt`
- **label/compute-midday/kiritimati/2026-09-20** (exact; DAY-004, DAY-007)
  - `$.hijri.date` expected `1448-04-07` got `1448-04-06`
  - `$.weekday` expected `al-Ahad` got `as-Sabt`
- **label/date-to-waqt-day/kiritimati/2026-06-15** (exact; DAY-004, DAY-007)
  - `$.hijri_date` expected `1447-12-29` got `1447-12-28`
  - `$.weekday` expected `al-Ithnayn` got `al-Ahad`
- **label/compute-midday/kiritimati/2026-06-15** (exact; DAY-004, DAY-007)
  - `$.hijri.date` expected `1447-12-29` got `1447-12-28`
  - `$.weekday` expected `al-Ithnayn` got `al-Ahad`
- **label/date-to-waqt-day/apia/2026-03-21** (exact; DAY-004, DAY-007)
  - `$.hijri_date` expected `1447-10-02` got `1447-10-01`
  - `$.weekday` expected `as-Sabt` got `al-Jumuah`
- **label/compute-midday/apia/2026-03-21** (exact; DAY-004, DAY-007)
  - `$.hijri.date` expected `1447-10-02` got `1447-10-01`
  - `$.weekday` expected `as-Sabt` got `al-Jumuah`
- **label/after-midnight-maghrib/reykjavik** (exact; DAY-004)
  - `$.hijri.date` expected `1448-01-06` got `1448-01-05`
  - `$.weekday` expected `al-Ithnayn` got `al-Ahad`
- **err/tz-unknown** (exact; ERR-002)
  - `$.error.code` expected `["VALIDATION_ERROR", "UNKNOWN_TIMEZONE", "INVALID_TIMEZONE"]` got `INTERNAL_ERROR`

## 4. Failing normative vectors — independent

None.


## 5. Open-question and informative divergences — reference

- **err/profile/fajr-95** (open; ERR-004): $ expected `expected error ['VALIDATION_ERROR']` got `succeeded: {"status": "OK", "undefined_reason": null, "instant": "2026-09-19T15:42:00+00:00", "timezone": "UTC", "profile": {"fajr_angle_deg": 95.0, "isha_angle_deg": 17....`
- **err/profile/fajr-negative** (open; ERR-004): $ expected `expected error ['VALIDATION_ERROR']` got `succeeded: {"status": "OK", "undefined_reason": null, "instant": "2026-09-19T15:42:00+00:00", "timezone": "UTC", "profile": {"fajr_angle_deg": -5.0, "isha_angle_deg": 17....`
- **err/profile/isha-zero** (open; ERR-004): $ expected `expected error ['VALIDATION_ERROR']` got `succeeded: {"status": "OK", "undefined_reason": null, "instant": "2026-09-19T15:42:00+00:00", "timezone": "UTC", "profile": {"fajr_angle_deg": 18.0, "isha_angle_deg": 0.0...`
- **err/profile/asr-zero** (open; ERR-004): $ expected `expected error ['VALIDATION_ERROR']` got `succeeded: {"status": "OK", "undefined_reason": null, "instant": "2026-09-19T15:42:00+00:00", "timezone": "UTC", "profile": {"fajr_angle_deg": 18.0, "isha_angle_deg": 17....`
- **err/profile/asr-negative** (open; ERR-004): $ expected `expected error ['VALIDATION_ERROR']` got `succeeded: {"status": "OK", "undefined_reason": null, "instant": "2026-09-19T15:42:00+00:00", "timezone": "UTC", "profile": {"fajr_angle_deg": 18.0, "isha_angle_deg": 17....`
- **date/basic-format-20260101** (open; TIME-003): $ expected `expected error ['INVALID_DATE', 'VALIDATION_ERROR']` got `succeeded: {"weekday_iso": 4, "weekday_name_islamic": "al-Khamis", "is_leap_year": false, "days_in_month": 31}`
- **instant/fraction-echo** (open; TIME-001): $.instant expected `2026-09-19T15:42:00.123456+00:00` got `2026-09-19T15:42:00+00:00`
- **instant/naive** (open; TIME-002): $ expected `expected error ['INVALID_INSTANT', 'VALIDATION_ERROR']` got `succeeded: {"instant": "2026-09-19T15:42:00+00:00"}`
- **next-event/tonights-isha** (open; EVT-007): $.next_event.name expected `isha` got `fajr`
- **aladhan/retry-after-short** (open; PRV-005): $.steps[2].provider expected `aladhan` got `umm-al-qura`

## 5. Open-question and informative divergences — independent

- **uaq/year-table/1420** (informative; CAL-007, CAL-006): $.months[9].length expected `29` got `30`
- **uaq/year-table/1446** (informative; CAL-007, CAL-006): $.months[4].length expected `29` got `30`
- **interop/instant/one-second-before-maghrib** (informative; INT-001, DAY-007): $.waqt_position_seconds expected `86401.137` got `0.240126`
- **interop/boundary/ends-exactly-at-maghrib** (informative; INT-003): $.crosses_maghrib expected `false` got `true`
- **waqt/london-long-day-near-24h-boundary** (informative; DAY-001, EVT-001, DAY-004, DAY-005, EVT-002): $.day.open expected `2026-02-14T17:13:44.159299+00:00` got `2026-02-14T17:13:40.639907+00:00`
- **uaq/range/1650-01-01** (open; CAL-011): $ expected `expected success` got `{"code": "OUT_OF_RANGE", "message": "umm-al-qura is supported for 1700-01-01..2300-12-31 only"}`
- **uaq/range/1699-12-31** (open; CAL-011): $ expected `expected success` got `{"code": "OUT_OF_RANGE", "message": "umm-al-qura is supported for 1700-01-01..2300-12-31 only"}`
- **uaq/range/2301-01-01** (open; CAL-011): $ expected `expected success` got `{"code": "OUT_OF_RANGE", "message": "umm-al-qura is supported for 1700-01-01..2300-12-31 only"}`
- **uaq/range/2500-01-01** (open; CAL-011): $ expected `expected success` got `{"code": "OUT_OF_RANGE", "message": "umm-al-qura is supported for 1700-01-01..2300-12-31 only"}`
- **live/15-kiritimati-day_bounds** (informative; SCH-006, SCH-008): $.hijri_label expected `1448-04-06` got `1448-04-07`

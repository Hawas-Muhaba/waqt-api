# Changelog — waqt-core

All notable changes to the `waqt-core` distribution are documented here.

## 0.7.0 — AT/BT display

**Added:** `waqt_core.display.at_bt` — an experimental, optional 12-hour
friendly display convention (After Twelve / After Twelve).  Exports
`format_at_bt(value)`, `parse_at_bt(value)` → `AtBtTime`, and the
`AtBtTime` dataclass.  Canonical Waqt times, instants, prayer events,
schedules, and day boundaries are unchanged.  The feature is not included
in Conformance Contract 2.0.0 and is not a normative Waqt standard
(governance decision pending).  See
`core/waqt_core/display/at_bt/SPEC.md` for the full specification.

## 0.6.0 — API 1.8.0 / conformance 2.0.0

**Changed (behaviour change, DR-0011/DR-0014):** ERR-004 profile fields accept finite numeric values only; nulls, booleans and numeric strings are rejected instead of coerced or treated as omitted. **Added:** `calendar_error_code()` provides the stable CAL-013 machine code for adapters. The independent implementation's upper instant limit remains disclosed; no full-range instant-conformance claim is made.

## 0.5.0 — Option B (default calendar provider)

**Changed (behaviour change)**: when a caller passes no Hijri provider, `waqt-core` now uses **`umm-al-qura`**
(was `arithmetic-tabular`). The default is defined once, in `waqt_core.calendar_providers.default`
(`DEFAULT_CALENDAR_PROVIDER`, `default_calendar_provider()`), and is the same value as the HTTP API default (API 1.7.0),
`waqt-local` and the `waqt` CLI. It affects `calendar_interop` (`represent_instant`, `waqt_day_for_gregorian_date`,
`classify_boundary_crossing`) and `SchedulingContext`. It labels days only: no Waqt instant, position or countdown changes.
Callers that need the previous results pass `ArithmeticTabularProvider()` explicitly. `umm-al-qura` supports
1700-01-01..2300-12-31 (CAL-011); outside it the Hijri label is empty (see Fixed).

**Fixed**: `InstantRepresentation.to_dict()` (and so `/v1/calendar/convert`, which returned HTTP 500) raised
`AttributeError: 'NoneType' object has no attribute 'iso_like'` when the provider could not label the day. A calendar failure
now leaves `hijri` empty and reports why in the new additive `WaqtDay.calendar_error` / `waqt.calendar_error`, never failing the
Waqt computation (same policy as `/v1/waqt`). This was already reachable with an explicit `umm-al-qura`; the new default made it common.

**Contract**: conformance contract 2.0.0 (draft) states the same default as requirement CAL-012 (DR-0010, ratification pending).
Engine revision unchanged (`"2"`); no vector expected value changed.

## 0.4.0 — Sprint 16

**Fixed (behaviour change)**: the Waqt-day label (`hijri_date`, `weekday`) is now that of the *civil* date, in the
location's IANA zone, on which the closing Maghrib instant falls (DIS-001; requirement DAY-004). It was derived
from the solar-date key given to the solver, which is a day off at Kiritimati, Apia and for after-midnight
Maghribs. Added `WaqtResult.label_date`.
**Fixed (behaviour change)**: `next_event` is the next event by occurrence, including the previous solar day's
Isha (EVT-007). It used to skip tonight's Isha after Maghrib and relied on list order.
**Added**: `InvalidHijriDate` (code `INVALID_HIJRI_DATE`), `checked_to_gregorian`, `tabular_is_leap_year`,
`tabular_month_length`; `ArithmeticTabularProvider.to_gregorian` rejects non-existent dates instead of
normalising them (DIS-002; CAL-004).
**Added**: `UnknownTimezoneError` (code `UNKNOWN_TIMEZONE`); `ManualTimezoneProvider` validates its zone at
construction (DIS-003; ERR-002).
**Added**: `CalendarOutOfRange` (code `OUT_OF_RANGE`); `UmmAlQuraProvider` supports 1700-01-01..2300-12-31 only (CAL-011).
**Packaging**: declare `tzdata` on Windows so `zoneinfo` can resolve IANA zones in clean installations.
**Vector set 1.1 → 2.0** (MAJOR: expected values changed). Engine revision unchanged (`2`).

## 0.3.0 — Sprint 14

**Added**: `waqt_core.calendar_providers.AlAdhanHijriProvider` — a live Gregorian→Hijri source behind
the existing `HijriProvider` protocol (12-hour cache, stale-if-error, circuit breaker, outbound rate
limit, bounded LRU, response validation, local `umm-al-qura` fallback, injectable transport). It never
raises and is never an input to astronomical computation.
**Added**: `HijriDate.source` (`local` | `declared` | `observation` | `remote` | `remote-stale` |
`local-fallback`) and `HijriDate.provenance` (`HijriProvenance`); `DeclaredProvider` /
`LocalObservationProvider` now stamp their own `source`. Both fields have defaults, so existing
constructors and equality keep working.
**Changed (behaviour)**: `compute_waqt` now contains calendar-provider failures. If
`calendar_provider.from_gregorian` raises, the events are still computed, `hijri_date` is `None` and
the new `WaqtResult.calendar_error` says why. Previously the exception propagated and the whole result
was lost (e.g. `umm-al-qura` outside its ephemeris range).
**Unchanged**: `solar.py`, `timescale.py`, `versioning.py` (engine revision `"2"`, vector set `"1.1"`).

## 0.2.1 — Sprint 13

**Changed**: `VECTOR_SET_VERSION` `"1.0"` → `"1.1"` (`waqt_core.versioning`; reported by
`version_report()` and therefore by `GET /v1/version` and `waqt_local.version()`).
The vector set moved because Sprint 13's first real regeneration (with `ephem`,
`timezonefinder` and FastAPI present) found that the calendar-interop case
`non-leap-century-1900` was not reproducible across environments: it used Addis Ababa, whose
1900 civil offset is a local-mean-time value that differs between tz database releases
(`9320 s` in tzdata 2026a, `8836 s` in the release the Sprint 12 vector was captured under).
The case now uses London (offset 0 in 1900), which does not depend on the tz database version.
No expected value changed for an input that is still present, so this is a MINOR vector-set
bump; no vector for any solar-engine output changed.

**Not changed**: `solar.py`, `timescale.py`, the engine revision (`"2"`, fingerprint unchanged),
the accuracy level (`"B"`), and every public function signature. Sprint 13's astronomy work
(`independent-astronomy/`) is evidence only; it altered no engine behaviour.

## 0.2.0 — Sprint 12

**Added**: `waqt_core.versioning` — the single source of the computation identity
(`ENGINE_NAME`, `ENGINE_REVISION`, `ACCURACY_LEVEL`, `computation_identity()`), the revision
history (`ENGINE_REVISIONS`), the reproducibility pin (`engine_fingerprint()`, enforced by
`core/tests/test_engine_revision.py`), `VECTOR_SET_VERSION` and `version_report()`.
`ENGINE_NAME`, `ENGINE_REVISION`, `ACCURACY_LEVEL`, `VECTOR_SET_VERSION`,
`computation_identity` are re-exported from the package root.

**Not changed**: any computed value. Engine revision stayed `"2"` (Sprint 11's).

## 0.1.0 — Sprint 11

Initial release. Extracted, unchanged, from what had been the
computation portion of the combined `waqt/` package: `core`, `solar`,
`hijri`, `calendar_providers`, `semantics`, `calendar_interop`,
`scheduling`, `institutional`, `timescale`, `timezone_provider`. See
`SPRINT-11-REPORT.md` §1 for the byte-for-byte extraction verification.

Three deliberate behavior changes to `solar.py`, made and measured
separately from the extraction (details, before/after tables and
reproduction: `docs/ASTRONOMY-ENGINE-EVALUATION.md`):

1. **Refinement epoch (`_event_time`)** — Julian Day of the refinement loop
   was 12 h off (`_jdn` is JD at *noon*; the `- 0.5` was missing). Dominant
   cause of the "high-latitude discrepancy" (432 s → ~50 s on its own).
2. **Transit/Asr sampling** — declination and equation of time were sampled
   at UT noon rather than at the transit instant (up to 12 h off at extreme
   longitudes). Dhuhr 15.5 s → 0.9 s, Asr 190 s → 1.3 s.
3. **Polar-threshold existence** — whether a marginal sunrise/sunset/twilight
   exists is now decided from the transit (and nadir) epoch and re-verified at
   the returned instant. Matches brute-force physical truth on 8/8 horizon
   disagreements with the independent references (which are wrong on all 8).

Net vs Level A (VSOP87), max |diff|: equator/tropics/mid-lat 0.9–1.0 s
(was 20–48 s), high latitude 3.6 s (was 432 s). **Computed times change**:
up to ~7 min at high latitude near an equinox, typically seconds elsewhere.
Public vectors were regenerated; the API's `accuracy_level` label ("B") was
deliberately left unchanged (see the evaluation doc, §5).

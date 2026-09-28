# Changelog — waqt-core

All notable changes to the `waqt-core` distribution are documented here.

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

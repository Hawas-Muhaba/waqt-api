# Accuracy-level review (Sprint 12 Goal C)

`waqt_core.versioning.ACCURACY_LEVEL` is currently `"B"`. This document is
the explicit review point Sprint 12's brief asked for: the criteria that
would justify moving it to `"A"`, what evidence exists for and against that
move today, and why Sprint 12 did not make it.

**This value is a public contract.** Every `computation` block the API,
`waqt-local`, and both SDKs return carries it. Changing it changes what a
caller is told to expect from every number Waqt produces. It must never
change as a side effect of an unrelated commit — `core/tests/test_engine_revision.py::test_accuracy_level_is_still_B_pending_the_documented_review`
pins the value; changing it requires editing that test in the same commit,
which is the mechanism that makes the change visible and reviewed rather
than silent.

## 1. What Level A/B/production mean here

| Label | Engine | Method |
|---|---|---|
| Level A | `independent-astronomy/level_a/` | full VSOP87 via `pymeeus`, apparent sidereal time |
| Level B | `independent-astronomy/independent_solar/` | Meeus low-accuracy position, explicit nutation, RA/sidereal-time |
| Production | `core/waqt_core/solar.py` | NOAA/Meeus low-precision series, equation-of-time event solving |

`ACCURACY_LEVEL` describes the **production** engine, i.e. what `waqt-core`
actually ships. Level A and Level B are reference/measurement tools, never
production — see `docs/ASTRONOMY-ENGINE-EVALUATION.md`.

## 2. Promotion criteria

Move `ACCURACY_LEVEL` from `"B"` to `"A"` only when **all** of the following
hold, and record the decision here when it happens:

1. **Multi-year agreement with Level A**, not a single epoch. Production vs
   Level A must stay within the Sprint 11 tolerances
   (`independent-astronomy/compare_sprint11.py`'s
   `TOLERANCE_SECONDS_WAQT_VS_LEVEL_A`) across several years spanning
   different equinox/solstice dates, not just the year the tolerances were
   set against.
2. **A second, genuinely independent reference agrees**, not just Level A
   and Level B (which already share the Meeus low-accuracy lineage for
   nutation/sidereal time — see `docs/ASTRONOMY-ENGINE-EVALUATION.md` §"what
   this is NOT"). A second source — a JPL-ephemeris-backed library
   (`skyfield` + a DE44x kernel, or `astropy.coordinates` + `jplephem`), or a
   published almanac's numeric tables — must independently corroborate Level
   A's numbers before "Level A" can be said to mean "verified accurate"
   rather than "agrees with one particular VSOP87 implementation".
3. **The polar/high-latitude case is covered**, not just excluded. All three
   sprints' comparisons already agree on *when* an event is undefined; the
   promotion decision needs the same tolerance discipline applied to defined
   high-latitude events across years, not only near one equinox.
4. **The decision is made in a dedicated review**, recorded in this file,
   not inferred from a comparison script's exit code. A script can supply
   evidence; it should not be the thing that flips the label.

## 3. Evidence as of Sprint 12

| Criterion | Status |
|---|---|
| 1. Multi-year vs Level A | **Evaluated.** Multi-year run (`vectors/multi_year_comparison_sprint12.json`, 560 rows, 7 years × Sprint 11's full geographic matrix) evaluated against Level A (`pymeeus`). Non-polar bands stay tightly bound under 3.4 s (equator: 2.923 s, tropics: 3.215 s, mid-lat-N: 3.349 s, mid-lat-S: 3.387 s). However, the high-latitude band reaches **9.427 s** (Tromso Fajr on 2019-09-19) compared to Sprint 11's single-epoch 3.6 s. |
| 1b. Tolerance calibration | **Stale baseline flagged.** `TOLERANCE_SECONDS_WAQT_VS_LEVEL_A["high-lat"]` is currently set to 450 s (a legacy artifact from Sprint 10's pre-fix 432 s error). This masked the 9.427 s high-lat divergence from triggering a script failure, indicating tolerances need deliberate recalibration. |
| 2. Independent second reference | **Not delivered.** Attempted; not practical in this environment (no network, no additional astronomy package available). See `compare_sprint12.py`'s docstring. |
| 3. Polar/high-latitude coverage | **Evaluated.** Polar row (Svalbard, `polar` band) showed 0 agreement failures across all 7 years × 5 dates. Defined high-latitude cases demonstrated the ~9.4 s equinox-drift variance described above. |
| 4. Dedicated review | This document, Sprint 12. Decision: **do not promote**. |

## 4. Decision record

| Sprint | Decision | Basis |
|---|---|---|
| 10 | Stay at B; do not swap engines on a comparison alone | Initial Level A comparison found up to 432 s error at high latitude, attributed at the time to "a real geometric effect" |
| 11 | Stay at B, engine corrected | Found and fixed two real bugs (epoch alignment, transit/Asr sampling instant); post-fix max |diff| vs Level A dropped to 0.9–3.6 s. This was *strong single-epoch evidence* (2026 only), not multi-year, and Level A/B share lineage (criterion 2 above), so Sprint 11 explicitly left the label unchanged pending further review — see `docs/ASTRONOMY-ENGINE-EVALUATION.md` §5. |
| **12** | **Stay at B** | Extended the evidence to 7 years with real Level A execution. While non-polar bands perform exceptionally well (< 3.4 s), the multi-year run revealed that equinox drift across leap-year cycles causes high-latitude difference vs Level A to expand to **9.427 s** (nearly 3× Sprint 11's 3.6 s single-year figure). This provides a concrete geometric finding against promoting `ACCURACY_LEVEL` to `"A"`, and highlights that the high-latitude tolerance threshold requires dedicated resizing in a future sprint alongside a second independent ephemeris reference. |

## 5. What would change if promoted

- `ACCURACY_LEVEL` in `core/waqt_core/versioning.py` → `"A"`.
- `core/tests/test_engine_revision.py`'s pinning test updated in the same
  commit (see file header).
- `ENGINE_REVISION` does **not** necessarily bump — promotion is a claim
  about accuracy given the current, unchanged engine behavior, not a
  behavioral change. If the promotion work also changes `solar.py` (e.g. to
  close a gap the new evidence reveals), that *does* need a revision bump,
  in the normal way (`core/waqt_core/versioning.py`'s module docstring).
- `docs/ASTRONOMY.md` and `docs/ASTRONOMY-ENGINE-EVALUATION.md` updated to
  reflect the new status and cite this document's decision record.

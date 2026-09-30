# Accuracy-level review (Sprint 12 Goal C; updated with Sprint 13 evidence)

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
| 2. Independent second reference | **Not delivered in Sprint 12** (no network / no package then). **Delivered in Sprint 13** — see §6. |
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

## 6. Sprint 13 evidence (verification sprint; no behaviour changed)

Full write-up, tables and reproduction commands: [`ASTRONOMY-SPRINT13.md`](ASTRONOMY-SPRINT13.md).
Engine under test: `waqt-noaa-low-precision` revision `2`, accuracy level `B` (unchanged).

| Criterion | Sprint 13 status |
|---|---|
| 1. Multi-year vs Level A | **Re-run, identical to Sprint 12** (560 rows, 0 of 16,170 fields differ). Non-polar max ≤ 3.39 s; high-lat max 9.427 s (Tromsø Fajr 2019-09-19). Mean \|diff\| 1.40 s, median 1.38 s, mean signed **+0.84 s** (Waqt is systematically late; cause not yet diagnosed). |
| 1b. Tolerance calibration | **Still open.** `TOLERANCE_SECONDS_WAQT_VS_LEVEL_A["high-lat"]` is still the stale 450 s. Not changed here (would silently alter what "agreement" means); a recalibration proposal is in `ASTRONOMY-SPRINT13.md` §7. |
| 2. Independent second reference | **Delivered.** JPL DE421 + Skyfield (own apparent place, IAU 2006/2000A sidereal time, own timescale, own root finder; the package imports nothing from waqt, Level A or Level B — enforced by test). **Level A agrees with it to ≤ 0.26 s** on the 560-row matrix, so Level A is genuinely corroborated. Waqt vs JPL: max 9.34 s (matrix), same conclusion as vs Level A. |
| 3. Polar / high-latitude coverage | **Covered, and it changes the picture.** Polar row: 210 event-instances, all four engines agree on existence in every one. Dense daily scans (every day of a year) at Tromsø 2019 and 2026, Reykjavik 2019, Longyearbyen 2026 show Waqt-vs-JPL max **22.0 s, 24.6 s, 9.5 s and 43.5 s**. These are not larger *angular* errors — every worst case corresponds to at most ~17 arcsec of Sun-position error (most 3–12″) — but a shallow altitude curve (0.18–0.5 arcsec per second) turns that into tens of seconds. |
| 4. Dedicated review | This section. **Decision: do not promote.** |

Two event-existence disagreements were found and adjudicated against the JPL altitude curve:
Tromsø 2026-09-17 Fajr (physical margin 0.55″ above threshold; Waqt and Level B say undefined,
Level A and JPL say defined) and Tromsø 2019-11-23 Asr (margin 0.06″; Waqt, Level A and Level B
say undefined, JPL says defined). Both are knife-edge days far below every engine's model error;
Waqt errs on the fail-closed side (UNDEFINED rather than an invented time).

### Decision record (addition)

| Sprint | Decision | Basis |
|---|---|---|
| **13** | **Stay at B** | Criterion 2 is now met and it *confirms* the reference chain (Level A ≈ JPL to 0.26 s). But the literal Level-A definition in `ASTRONOMY.md` — "sub-10-second agreement … across the full geographic matrix" — is met only on the 5-dates-per-year matrix (9.34–9.43 s, with 0.6 s of headroom) and **fails under dense high-latitude sampling** (up to 43.5 s at 78°N). Tolerances (1b) remain uncalibrated. Promotion would be a claim the evidence does not support. |

`ACCURACY_LEVEL` is unchanged and `core/tests/test_engine_revision.py` still pins it.
`independent-astronomy/tests/test_skyfield_reference.py::test_accuracy_promotion_criterion_is_not_met_by_committed_evidence`
records the reason; if the engine is later improved so that dense-scan error falls under 10 s,
that test fails and forces this review to be reopened rather than silently passing.

### What would justify reopening

1. Diagnose the +0.84 s mean bias (UT1/ΔT handling vs the low-precision series) and either fix it (which is an engine revision bump) or document it as the model's floor.
2. Define the Level-A claim as an **angular** tolerance (Sun position, arcsec) plus a stated latitude limit, rather than a time tolerance that geometry can amplify without bound, then recalibrate criterion 1b.
3. Decide whether Level A is claimed poleward of ~64°, or only equatorward, and document the boundary.

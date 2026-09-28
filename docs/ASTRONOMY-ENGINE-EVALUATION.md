# Astronomical engine evaluation (Sprint 11)

Three engines, one question: which one should the production computation
layer (`waqt-core`) run, and how good is it really?

| Engine | Where | Method | Role |
|---|---|---|---|
| **Production** ("NOAA lineage") | `core/waqt_core/solar.py` | NOAA/Meeus low-precision solar position, equation-of-time event solving | what `waqt-core`, `waqt.api`, `waqt_local` run |
| **Level B** (independent) | `independent-astronomy/independent_solar/` | Meeus low-accuracy position + explicit nutation, RA/sidereal-time event solving | cross-check, not production |
| **Level A** (reference) | `independent-astronomy/level_a/` | full VSOP87 via `pymeeus`, apparent sidereal time | ground-truth reference, not production (~60 ms/day) |

**Decision (recorded for review): keep the production engine, corrected. Do not
swap to Level B. Do not relabel it Level A yet.** Reasoning in §5.

## 1. What Sprint 10 left us with

Sprint 10 measured production vs Level A and found up to ~432 s error at high
latitude (≈20–48 s elsewhere) against ~1.7–4.3 s for Level B, and described the
high-latitude number as "a real geometric effect". It correctly declined to swap
engines on the strength of a comparison alone.

## 2. Findings

### 2.1 The "geometric effect" was mostly a bug (Bug 1)

`_event_time` refines an event by re-evaluating the sun at each estimate. It
built the Julian Day as `_jdn(d) + (estimate − midnight)/86400`. `_jdn(d)` is
the JD at **noon** UT (2000‑01‑01 → 2451545, which *is* noon), so the fraction
must be added to `_jdn(d) − 0.5`. Without the `− 0.5` the sun was sampled
**12 hours away** from the instant being solved for. Verified directly:
`julian_day(2000‑01‑01 04:14Z)` = 2451544.676…; the old expression gave
2451545.176….

Why it hid: 12 hours of declination drift is negligible near the equator or a
solstice. Where it isn't negligible (declination moving ~0.4°/day near an
equinox) *and* the hour angle is hypersensitive to declination (high latitude),
it dominates. Measured at Tromsø (69.6°N), 19 Sep 2026: declination at the event
instant differed from Level A by **694″** (Level B: 4.4″), and the hour-angle
sensitivity to declination there is ~865× that at the equator, which turns 694″
into minutes. Both effects are real; the bug supplied the input error the
geometry amplified.

### 2.2 Transit and Asr sampled the wrong instant (Bug 2)

After Bug 1 the residual maxima were Dhuhr 15.5 s and Asr 52.5 s. `transit()`
and `asr()` evaluated declination/equation of time at **UT noon of the date**,
but transit is at 12:00 − lon/15 h UT — up to 12 h away at extreme longitudes
(worst rows: Suva lon +178, Kiritimati lon −157, Anchorage lon −150), and the
equation of time moves up to ~30 s/day. Fixed by evaluating at the transit
instant (two fixed-point iterations, converged to <1 ms).

### 2.3 What I predicted wrong

I first expected the pre-fix error to peak exactly at the equinox and fall off
either side. The equinox‑proximity sweep says otherwise: at Tromsø it was a
~116 s plateau across roughly ±30 days of the equinox, and *grew* toward the
seasonal extremes (up to ~254 s at +60 days) as the day approached the
polar‑night boundary, where the hour-angle sensitivity keeps rising even though
declination is changing more slowly. Both sweeps are committed
(`independent-astronomy/vectors/level_a_comparison_sprint11_before.json`).

### 2.4 Defined vs undefined near the polar threshold (Bug 3)

The engine decided "does this sunrise/sunset/twilight exist today?" from the
declination at UT noon. Near polar-day onset the sun's trough altitude is within
~0.03° of the horizon threshold, so a 12 h sampling error flips the answer.
Fix: start the search at the actual transit instant, probe the nadir epoch
(where a marginal crossing occurs) before giving up, and verify the event exists
at the instant returned.

To check this properly I could not use Level A/B as the oracle: their
solving loops are transit‑anchored and give up the first time the hour angle is
undefined, so comparing to them just compares loops. `threshold_truth.py`
instead scans the sun's *true altitude* (VSOP87 + apparent sidereal time)
across the half‑day and asks whether it crosses the threshold.

**Scan** (`threshold_scan.py`): 19,125 event‑days, latitudes 60–85°, four
lon/season configurations (18.96°E and 150°W May–Jul, 100°E Nov–Jan, southern
70°W Nov–Jan). Result on the final code:

| | count |
|---|---|
| Sunrise/Maghrib disagreements among the three engines | 8 |
| …where the **production engine matches physical truth** | **8 / 8** |
| …where Level A **and** Level B are both wrong | 8 / 8 |
| Asr disagreements (engine defined; A and B undefined) | 6 |
| …ill‑conditioned tangency (sun's peak within 0.0001–0.0023° of the Asr altitude) | 6 / 6 |

The Asr rows are not "wrong" in any checkable sense: at those inputs the sun
barely clears the horizon, the Asr altitude is essentially the noon peak, and
the answer depends on a few arcseconds — below the accuracy of every engine
here. The production engine returns an Asr 0.7–3.2 min after transit, which is
the sensible limit. Before this fix the same scan showed 23 disagreements in the
100°E configuration alone, including one Maghrib the engine wrongly called
undefined; a wider class of misses was closed by starting at transit rather
than UT noon.

The scan is **not** a proof of zero remaining threshold errors — it's a dense
sample of one latitude range in one year. Fajr/Isha threshold days were compared
between engines but have no single‑threshold truth scan (§6).

## 3. Results: before and after

Production vs Level A on the same 80‑row named matrix (16 locations × 5 dates,
incl. Reykjavik, Anchorage, Punta Arenas, Ushuaia, Suva, Kiritimati, Svalbard),
max |diff| in seconds:

| Band | Before | After Bug 1 only | After all | Level B (unchanged) |
|---|---|---|---|---|
| equator | 19.8 | 10.6 | **0.9** | 1.7 |
| tropics | 31.7 | 20.1 | **1.0** | 1.7 |
| mid‑lat N | 40.1 | 12.5 | **1.0** | 1.8 |
| mid‑lat S | 47.8 | 2.3 | **1.0** | 1.9 |
| high‑lat | 432.1 | 52.5 | **3.6** | 4.3 |

By event (before → after): Fajr 432→3.6, Sunrise 138→1.8, Dhuhr 15.5→0.9,
Asr 190→1.3, Maghrib 135→1.6, Isha 288→2.7.

Dense latitude sweep (0–80° every 5°, 19 Sep, sunrise): max 260.9 s → **0.95 s**.
Equinox‑proximity sweep (Tromsø, ±60 days): max 253.9 s → **3.05 s**.

Polar UNDEFINED agreement in the matrix: no disagreements.

## 4. Trade‑offs

| | Production (corrected) | Level B | Level A |
|---|---|---|---|
| Max error vs Level A (matrix) | 0.9–1.0 s; 3.6 s high‑lat | 1.7–1.9 s; 4.3 s high‑lat | — |
| Sunrise/Maghrib threshold days | matches physics 8/8 | wrong 8/8 | wrong 8/8 |
| Cost per day‑of‑events | 0.12 ms | 0.26 ms | ~60 ms |
| Runtime deps | none | none | `pymeeus` |
| Code | 1 file, ~380 lines | 7 modules, ~890 lines | wrapper over `pymeeus` |
| Already wired into API/local/vectors | yes | no | no |

Swapping to Level B would cost regenerating every vector and API expectation a
second time, buy *no* accuracy (production is now equal or better on every
band), and import the threshold‑day errors. Adopting Level A would add a
dependency and a ~500× runtime cost for no additional accuracy at prayer‑time
scale.

**Independence caveat.** Production and Level B use the *same* mean‑element
orbital series (mean longitude/anomaly, eccentricity, equation of centre); they
differ in nutation/aberration handling and event solving. Their agreement with
Level A therefore says less about the series than their two‑way agreement
suggested, and Level A (VSOP87) is the only genuinely independent check on the
position model. This does not affect the results above, but it limits what
"three engines agree" can mean.

## 5. Decision and what was deliberately not changed

- **Production engine: `waqt_core.solar`, corrected (three fixes).** Not
  replaced.
- **API label unchanged:** responses still report `waqt-noaa-low-precision` /
  accuracy level `B`. The measured 1–3.6 s agreement meets the *numeric*
  definition of Level A (sub‑10 s against a high‑precision ephemeris) on the
  tested matrix — but relabelling is a public contract change to every
  response, the evidence covers essentially one year (2026, plus early 2027 in
  the scan) and one ΔT model, and the reference is VSOP87 via `pymeeus`, not a
  JPL ephemeris. **Open decision for you:** promote to Level A now, or first
  extend the matrix to other years / a JPL reference.
- **Recommended next sprint:** add an engine **revision** field to the API
  `computation` block. Output times changed by up to minutes under an unchanged
  engine string; a client that cached results has no way to tell.

## 6. Limitations

- One reference (VSOP87/`pymeeus`) and mostly one year. Not yet checked against
  JPL DE or across decades; ΔT is the project's own provider.
- Residual ~1 s floor against Level A appears in *both* Level B and production.
  I did not investigate its source (reference conventions, refraction model,
  ΔT) — it is well below prayer‑time relevance but is unexplained.
- Fajr/Isha threshold days: engines compared, no independent truth scan.
- The older `astral` comparison table in `docs/ASTRONOMY.md` was **not**
  re‑measured; `tests/test_core.py` still passes against its (looser)
  tolerances, so it stands as an upper bound.
- Bugs 1–3 shipped in every prior sprint. Values computed and vectors published
  before Sprint 11 differ from current ones (up to ~7 min at high latitude near
  the equinox; typically seconds elsewhere).

## 7. Reproduce

```bash
cd independent-astronomy
python3 compare_sprint11.py --label after      # matrix + both sweeps
python3 compare_level_a.py && python3 compare.py
python3 threshold_scan.py                       # ~5 min
python3 asr_threshold_classify.py
pytest tests/                                   # incl. test_sprint11_matrix, test_threshold_truth
cd .. && pytest core/tests/test_solar_epoch_regression.py   # revert any of the 3 fixes → fails
```

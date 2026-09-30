# Astronomy evidence — Sprint 13

Engine under test: `waqt-noaa-low-precision` revision `2`, accuracy level `B`. Nothing in the
engine changed. Everything below is reproducible from committed scripts and artifacts.

| Script | Artifact | What it is |
|---|---|---|
| `independent-astronomy/compare_sprint13.py` | `vectors/multi_year_comparison_sprint13.json` | Sprint 12's 560-row study re-run unchanged (same 7 years, same `NAMED_LOCATIONS`, same 5 dates, same 6 events) + statistics + row-by-row diff against Sprint 12 |
| `independent-astronomy/compare_skyfield_sprint13.py` | `vectors/skyfield_reference_sprint13.json` | Waqt, Level B, Level A vs the independent JPL reference: 560-row matrix, parallax sensitivity, polar four-way existence, four dense one-year daily scans |
| `independent-astronomy/analyze_worst_cases_sprint13.py` | `vectors/worst_case_analysis_sprint13.json` | Converts worst time errors to arcseconds; adjudicates existence disagreements |

Run: `cd independent-astronomy && python compare_sprint13.py && python compare_skyfield_sprint13.py && python analyze_worst_cases_sprint13.py`
(the second takes roughly 15–20 minutes; `--quick` runs a small subset and writes a separate file).

## 1. The independent reference

`independent-astronomy/skyfield_reference/`: Sun and Earth from **JPL DE421** (the `de421` PyPI
package — JPL's numbers in jplephem's legacy Chebyshev format; NAIF's `.bsp` host was not
reachable, and the numbers are the same), apparent place / aberration / light-time / IAU 2006/2000A
sidereal time and UT1/TT from **Skyfield**, and an own grid-refinement root finder.
It shares with Waqt only the event **definitions** in `docs/ASTRONOMY.md` (18°/17°, −0.8333° +
dip, Asr formula, day-selection rule) — those are the question being asked, not a method.
`tests/test_skyfield_reference.py` checks structurally that the package imports none of
`waqt*`, `independent_solar`, `level_a`, `pymeeus`, `ephem`, `astral`.

Limits: DE421 covers 1900–2050 (all study years are inside). The geocentric-altitude convention is
used because the −0.8333° constant already absorbs refraction and semidiameter for a geocentric
Sun centre; the topocentric (parallax) variant is reported as a sensitivity.

## 2. Waqt vs Level B, Level A and JPL — 560 rows, 3,045 defined event-instances (seconds)

| Comparison | max \|diff\| | mean \|diff\| | median | mean signed |
|---|---|---|---|---|
| Waqt − Level B | 1.710 | 1.083 | 1.342 | +0.252 |
| Waqt − Level A (VSOP87) | 9.427 | 1.401 | 1.375 | +0.835 |
| Level B − Level A | 7.915 | 0.768 | 0.705 | +0.582 |
| **Waqt − JPL (independent)** | **9.343** | 1.436 | 1.396 | +0.862 |
| Level B − JPL | 7.831 | 0.800 | 0.769 | +0.610 |
| **Level A − JPL** | **0.259** | 0.081 | 0.096 | +0.027 |

Sprint 12's Waqt−Level B result (≈1.67–1.71 s) is reproduced exactly; the whole Sprint 13 row set
equals Sprint 12's (0 of 16,170 compared fields differ).

### Per latitude band — Waqt vs Level A (max / mean / median), and vs JPL (max)

| Band | n | Waqt−A max | mean | median | Waqt−JPL max | Level A−JPL max |
|---|---|---|---|---|---|---|
| equator | 210 | 2.923 | 1.355 | 1.374 | 2.776 | 0.169 |
| tropics | 1260 | 3.215 | 1.373 | 1.374 | 3.070 | 0.170 |
| mid-lat N | 420 | 3.349 | 1.369 | 1.375 | 3.206 | 0.170 |
| mid-lat S | 210 | 3.387 | 1.385 | 1.377 | 3.245 | 0.170 |
| high-lat | 945 | 9.427 | 1.468 | 1.377 | 9.343 | 0.259 |

High-latitude locations, Waqt−A max: Tromsø 9.427, Reykjavik 4.891, Anchorage 4.494,
Ushuaia 3.992, Punta Arenas 3.914.

### Per event — Waqt vs Level A (max / mean), vs JPL (max)

| Event | max | mean | Waqt−JPL max |
|---|---|---|---|
| Fajr | 9.427 | 1.540 | 9.343 |
| Sunrise | 4.733 | 1.441 | 4.603 |
| Dhuhr | 2.941 | 1.369 | 2.794 |
| Asr | 3.535 | 1.350 | 3.394 |
| Maghrib | 3.840 | 1.351 | 3.702 |
| Isha | 3.992 | 1.363 | 3.870 |

Every one of the top-5 worst matrix rows is Tromsø Fajr near the September equinox
(2019-09-19 9.43 s, 2030-09-19 7.46 s, 2019-09-23 6.98 s, 2027-09-19 6.46 s, 2030-09-23 5.03 s).

## 3. Polar boundary (Longyearbyen, 78.2°N)

35 rows × 6 events = 210 event-instances. All four engines (Waqt, Level B, Level A, JPL) agree
on whether the event exists in **all 210** (119 defined, 91 undefined). The Sprint 12 finding
(0 polar-agreement failures) is therefore confirmed by a fourth, independent engine.

## 4. Dense daily scans (what the 5-date matrix cannot see)

Every calendar day of one year, all six events, Waqt vs JPL:

| Site (year) | defined event-instances | max \|diff\| | mean | p95 | worst day |
|---|---|---|---|---|---|
| Reykjavik 64.1°N (2019) | 1905 | 9.48 | 1.19 | 2.88 | 2019-08-30 Isha |
| Tromsø 69.6°N (2019) | 1555 | 22.02 | 1.36 | 3.41 | 2019-01-19 Asr |
| Tromsø 69.6°N (2026) | 1557 | 24.58 | 1.69 | 3.87 | 2026-05-17 Maghrib |
| Longyearbyen 78.2°N (2026) | 1163 | **43.50** | 1.87 | 5.01 | 2026-02-15 Maghrib (and Sunrise, −38.6) |

The bulk is fine (p95 ≤ 5 s); the tail sits on days when the Sun grazes the horizon
(the first/last days of polar day/night at those sites).

## 5. Why the tail is large: time error is angle ÷ slope

`analyze_worst_cases_sprint13.py` evaluates the JPL altitude at the instant Waqt reported.

| Case | time diff | Sun altitude rate | angular error |
|---|---|---|---|
| Longyearbyen 2026-02-15 Maghrib | +43.5 s | 0.183″/s | 8.2″ |
| Longyearbyen 2026-02-15 Sunrise | −38.6 s | 0.183″/s | 7.2″ |
| Tromsø 2026-05-17 Maghrib | +24.6 s | 0.245″/s | 5.9″ |
| Longyearbyen 2026-03-06 Isha | +22.6 s | 0.499″/s | 11.2″ |
| Tromsø 2019-01-19 Asr | −22.0 s | 0.009″/s | 0.11″ |
| Tromsø 2019-09-19 Fajr (matrix worst) | +9.3 s | 1.353″/s | 12.7″ |

The Sun-position error is about 0.1–17″ everywhere — consistent with a low-precision series — and
the time error is that divided by how fast the altitude changes. This is a property of the
*question* (event time near a grazing geometry) as much as of the engine, which is exactly why a
fixed-seconds tolerance is the wrong shape for a high-latitude accuracy claim (see §7).

## 6. Existence disagreements (2 of 8,760 scanned event-days)

| Day | JPL | Level A | Level B | Waqt | physical margin |
|---|---|---|---|---|---|
| Tromsø 2026-09-17 Fajr | occurs (22:40:25.9 UTC on the 16th) | occurs (+7.6 s from JPL) | undefined | undefined | 0.55″ |
| Tromsø 2019-11-23 Asr | occurs | undefined | undefined | undefined | 0.06″ |

Both are sub-arcsecond knife-edges. The 7.6 s JPL/Level-A spread on the first shows how
ill-conditioned the *time* is even between the two best engines. Waqt fails closed.

## 7. Observations and open items (not acted on)

* **Systematic bias:** mean signed Waqt−JPL is **+0.86 s** for every event including Dhuhr
  (Level A−JPL is +0.03 s). A ~constant offset points at time-scale handling (UT1 vs UTC, ΔT) or the
  series' equation-of-time term, not at geometry. Not diagnosed this sprint; changing it would be an
  engine revision bump and was out of scope.
* **Year dependence:** Addis Ababa Waqt−JPL is ≈ +2.8 s on 2019-09-19 but ≈ +0.9 s on 2026-09-19,
  i.e. the low-precision series drifts with distance from J2000 (or with ΔT model error).
* **Parallax:** topocentric vs geocentric altitude changes event times by ≤ 1.02 s outside
  the high-latitude band and up to 16.2 s at high latitude (mean 1.4 s). Any future Level-A
  claim must state which convention it uses.
* **Tolerance recalibration proposal (not applied):** replace the 450 s high-lat time tolerance with
  (a) an angular bound on Sun position (e.g. ≤ 20″ vs JPL, all bands) and (b) a per-event time bound of
  `angular_bound / |d altitude / dt|`, with an explicit statement that events with slope below
  ~0.1″/s are reported as ill-conditioned rather than pass/fail.

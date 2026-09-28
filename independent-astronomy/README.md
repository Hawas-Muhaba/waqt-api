# Parallel Milestone A — Independent Astronomical Reference

Sprint 9 deliverable, run alongside the Sprint 9 SDK work per the sprint
brief. See `docs/INDEPENDENT-ASTRONOMY.md` (main repo) for the full
write-up; this is the short version.

**What it is.** `independent_solar/` is a second, from-scratch solar
event engine — sunrise, sunset, Fajr, Dhuhr, Asr, Isha — that shares no
astronomy code with `waqt/solar.py` and imports nothing from `waqt`.
Where `waqt/solar.py` follows NOAA's low-precision polynomial series and
finds event times via the equation of time, this package follows Meeus's
apparent-position route (explicit nutation, aberration, right ascension)
and finds event times via Greenwich Apparent Sidereal Time + the sun's own
right ascension — no equation of time appears anywhere in this package.
See `independent_solar/__init__.py` for the full side-by-side.

**What it found.** `compare.py` runs both engines across 12 locations
(the equator through both poles' high latitudes, the date line, and a
civil-timezone/solar-time divergence case) and 5 dates (both equinoxes,
both solstices, one ordinary date) — 60 location/date rows, 6 events each.
In Sprint 9 every event agreed within a (deliberately wide) tolerance band, with
one exception reported honestly: high-latitude events near the equinox
disagreed by up to ~7 minutes. Sprint 9 described that as a real geometric
effect. **Sprint 11 found it was mostly a bug in `waqt/solar.py`'s event solver
(sampling the sun 12 h off), amplified by geometry** — fixed, and the
tolerances re-tightened to a few seconds; see
`docs/ASTRONOMY-ENGINE-EVALUATION.md`. No case of one engine calling an event `UNDEFINED` (polar day/night)
while the other found a numeric answer.

**Commands:**

```bash
cd independent-astronomy
python3 compare.py                 # regenerate vectors/independent_astronomy_comparison.json
python3 -m pytest -q tests/        # 15 tests: standalone sanity + comparison-agreement
```

**What this milestone is NOT.** It does not replace `waqt/solar.py`, and
nothing in `waqt/` was touched to build it (verified by
`test_no_import_of_waqt_package` and the repo-wide md5 check in
`SPRINT-9-REPORT.md`). Per the Sprint 9 brief: "It should not silently
replace the existing engine. ... It should first prove
agreement/disagreement transparently." That's what this is.

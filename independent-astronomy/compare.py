#!/usr/bin/env python3
"""
independent-astronomy/compare.py — Parallel Milestone A comparison run.

Computes all six solar events, at every (location, date) pair in the test
matrix below, with BOTH:
  - waqt/solar.py               (the existing reference implementation)
  - independent_solar           (this milestone's independent implementation)

and writes every result plus the signed difference (independent - waqt,
in seconds) to vectors/independent_astronomy_comparison.json. Nothing here
is hand-typed: every "waqt" value comes from a live call into
waqt.solar.compute_day_events, and every "independent" value comes from a
live call into independent_solar.compute_day_events.

This script is the ONLY file in this milestone that imports from `waqt`
(for comparison purposes only) -- `independent_solar/` itself never does.

Usage:  python3 compare.py
"""

from __future__ import annotations

import json
import sys
from datetime import date, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent
sys.path.insert(0, str(_REPO_ROOT))      # for `import waqt.solar`
sys.path.insert(0, str(_HERE))            # for `import independent_solar`

from independent_solar import compute_day_events as independent_events  # noqa: E402
from waqt import solar as waqt_solar  # noqa: E402

# Same geographic test matrix `tests/test_core.py` uses, for continuity
# with the project's own documented accuracy tiers (docs/ASTRONOMY.md),
# plus Dibrugarh (civil-tz/solar-time divergence case from Sprint 8) and
# a second Addis elevation.
LOCATIONS = [
    # (name, lat, lon, elevation_m, latitude_band)
    ("Quito (equator)", -0.1807, -78.4678, 0.0, "equator"),
    ("Nairobi (tropics, S)", -1.2921, 36.8219, 0.0, "tropics"),
    ("Addis Ababa (tropics, N)", 9.0192, 38.7525, 0.0, "tropics"),
    ("Addis Ababa @ 2400m", 9.0192, 38.7525, 2400.0, "tropics"),
    ("Makkah (tropics, N)", 21.4225, 39.8262, 0.0, "tropics"),
    ("Dibrugarh, NE India", 27.4728, 94.9120, 0.0, "mid-lat-N"),
    ("Cairo (mid-lat, N)", 30.0444, 31.2357, 0.0, "mid-lat-N"),
    ("Cape Town (mid-lat, S)", -33.9249, 18.4241, 0.0, "mid-lat-S"),
    ("Tromso (high-lat, N)", 69.6492, 18.9553, 0.0, "high-lat"),
    ("Punta Arenas (high-lat, S)", -53.1638, -70.9171, 0.0, "high-lat"),
    ("Suva, Fiji", -18.1416, 178.4419, 0.0, "tropics"),
    ("Kiritimati (UTC+14)", 1.8721, -157.4278, 0.0, "tropics"),
]

# Spread across the year (equinoxes, both solstices, and two ordinary
# dates) so seasonal declination swing is exercised, not just one date.
DATES = [
    date(2026, 3, 20),   # March equinox
    date(2026, 6, 21),   # June solstice
    date(2026, 9, 19),   # ordinary (matches Sprint 5's own primary vector date)
    date(2026, 9, 23),   # September equinox
    date(2026, 12, 21),  # December solstice
]

# Base tiers echo docs/ASTRONOMY.md's own Level-B-vs-astral numbers, WIDENED
# for high-lat specifically. Two genuinely independent algorithms (this
# milestone's sidereal-time/right-ascension solver vs the reference's
# equation-of-time solver) diverge more than either does from `astral`
# alone once you're near the equinox at high latitude: docs/ASTRONOMY.md
# already explains why ("near high latitude the sun's path is shallow, so
# the same angle disagreement amplifies") -- this run empirically confirms
# it rather than assuming it. 500s is set from the actually observed
# max at Tromso/equinox (see max_abs_diff_seconds_by_band_observed below
# and docs/INDEPENDENT-ASTRONOMY.md for the full discussion), not tuned to
# force a pass.
TOLERANCE_SECONDS = {
    # Sprint 11 re-tightened these (was 30/40/80/80/500) after fixing a
    # half-day epoch-alignment bug in solar.py's event-time refinement
    # that had been the dominant error source, especially at high
    # latitude -- see SPRINT-11-REPORT.md Sec 2. Same "measure, then set
    # the tolerance from what's observed" discipline as before.
    # Second tightening after the transit/Asr fix; observed max ~1.7 s
    # everywhere (this is the waqt-vs-independent_solar comparison, whose
    # residual is now dominated by independent_solar's own ~1.7 s offset
    # from Level A, not by waqt).
    "equator": 4,
    "tropics": 4,
    "mid-lat-N": 4,
    "mid-lat-S": 4,
    "high-lat": 8,
}

EVENT_NAMES = ["fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha"]


def _diff_seconds(a, b):
    if a is None or b is None:
        return None
    return round((a - b).total_seconds(), 3)


def run() -> dict:
    vectors = []
    max_abs_diff_by_band = {}
    undefined_agreement_failures = []

    for name, lat, lon, elevation_m, band in LOCATIONS:
        for d in DATES:
            waqt_day = waqt_solar.compute_day_events(
                d, lat, lon, elevation_m=elevation_m
            )
            indep_day = independent_events(d, lat, lon, elevation_m=elevation_m)

            events = {}
            for ev_name in EVENT_NAMES:
                w = getattr(waqt_day, ev_name)
                i = getattr(indep_day, ev_name)
                if (w is None) != (i is None):
                    undefined_agreement_failures.append(
                        {"location": name, "date": d.isoformat(), "event": ev_name,
                         "waqt_defined": w is not None, "independent_defined": i is not None}
                    )
                diff = _diff_seconds(i, w)
                events[ev_name] = {
                    "waqt": w.astimezone(timezone.utc).isoformat() if w else None,
                    "independent": i.astimezone(timezone.utc).isoformat() if i else None,
                    "diff_seconds": diff,
                    "within_tolerance": (
                        None if diff is None else abs(diff) <= TOLERANCE_SECONDS[band]
                    ),
                }
                if diff is not None:
                    cur = max_abs_diff_by_band.get(band, 0.0)
                    max_abs_diff_by_band[band] = max(cur, abs(diff))

            vectors.append({
                "location": name,
                "lat": lat,
                "lon": lon,
                "elevation_m": elevation_m,
                "latitude_band": band,
                "date": d.isoformat(),
                "tolerance_seconds": TOLERANCE_SECONDS[band],
                "events": events,
            })

    report = {
        "milestone": "Parallel Milestone A - Independent Astronomical Reference",
        "note": (
            "Every value below was computed live by calling waqt.solar.compute_day_events "
            "(existing reference) and independent_solar.compute_day_events (this milestone's "
            "independent implementation) at comparison time. Nothing here is hand-typed. "
            "independent_solar shares no astronomy code with waqt/solar.py -- see "
            "independent_solar/__init__.py for the two implementations' differing methods."
        ),
        "tolerance_seconds_by_latitude_band": TOLERANCE_SECONDS,
        "max_abs_diff_seconds_by_band_observed": {
            k: round(v, 3) for k, v in max_abs_diff_by_band.items()
        },
        "undefined_agreement_failures": undefined_agreement_failures,
        "vectors": vectors,
    }
    return report


def main():
    report = run()
    out_path = _HERE / "vectors" / "independent_astronomy_comparison.json"
    out_path.write_text(json.dumps(report, indent=2) + "\n")

    print(f"Wrote {len(report['vectors'])} comparison rows to {out_path}")
    print("Max |diff| observed, by latitude band:")
    for band, tol in TOLERANCE_SECONDS.items():
        observed = report["max_abs_diff_seconds_by_band_observed"].get(band)
        status = "OK" if (observed is None or observed <= tol) else "OVER TOLERANCE"
        print(f"  {band:12s} tolerance={tol:4d}s  observed_max={observed}  [{status}]")
    if report["undefined_agreement_failures"]:
        print(f"UNDEFINED-status disagreements: {len(report['undefined_agreement_failures'])}")
        for f in report["undefined_agreement_failures"]:
            print(f"  {f}")
    else:
        print("No UNDEFINED-status disagreements (polar day/night agreement: OK).")


if __name__ == "__main__":
    main()

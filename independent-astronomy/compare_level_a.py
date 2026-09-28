#!/usr/bin/env python3
"""
independent-astronomy/compare_level_a.py — Sprint 10's Level-A comparison.

Computes all six solar events, at every (location, date) pair in the
same test matrix `compare.py` (Sprint 9) uses plus one explicit
Svalbard polar-night/day row, with THREE independently-sourced
implementations:

  - waqt/solar.py           (production; NOAA low-precision formulas)
  - independent_solar/      (Sprint 9's Level-B independent reference;
                              Meeus low-accuracy solar-coordinates method)
  - level_a/                (this sprint's reference; full VSOP87 via
                              the published, independently-tested
                              `pymeeus` library -- see level_a/sun.py)

and writes every result plus both signed differences (against Level A,
in seconds) to vectors/level_a_comparison.json.

This is explicitly a MEASUREMENT, not a decision: nothing here changes
`waqt/solar.py`, and the tolerances below were set AFTER running this
script and reading off the actually observed maxima (see the `_observed`
suffix in the printed table and docs/independent-astronomy/LEVEL-A.md),
the same honesty discipline compare.py's own comment already documents
for its waqt-vs-independent_solar tolerances.

Usage:  python3 compare_level_a.py
"""

from __future__ import annotations

import json
import sys
from datetime import date, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_HERE))

from independent_solar import compute_day_events as level_b_events  # noqa: E402
from level_a.events import compute_day_events as level_a_events  # noqa: E402
from waqt import solar as waqt_solar  # noqa: E402

LOCATIONS = [
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
    # Explicit "undefined polar conditions" row for this sprint's DoD --
    # well inside the Arctic Circle, exercised at both solstices below.
    ("Longyearbyen, Svalbard (polar)", 78.2232, 15.6469, 0.0, "polar"),
]

DATES = [
    date(2026, 3, 20),
    date(2026, 6, 21),
    date(2026, 9, 19),
    date(2026, 9, 23),
    date(2026, 12, 21),
]

EVENT_NAMES = ["fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha"]

# Set AFTER running this script once and reading off the actually
# observed maxima below (not tuned in advance to force a pass -- see
# module docstring). waqt/solar.py (NOAA low-precision) and
# independent_solar (Meeus low-accuracy) are different accuracy classes
# in practice, which is itself one of this comparison's findings (see
# docs/independent-astronomy/LEVEL-A.md) -- each therefore gets its own
# tolerance table rather than one shared number. "polar" has no numeric
# tolerance: agreement there is checked as "all three engines call it
# undefined together", not a diff-in-seconds number.
TOLERANCE_SECONDS_WAQT_VS_LEVEL_A = {
    # Sprint 11 re-tightened these after fixing the half-day epoch-
    # alignment bug in solar.py's event-time refinement (see
    # SPRINT-11-REPORT.md Sec 2) -- the same "measure, then set the
    # tolerance from what's observed" discipline as the original values,
    # applied again now that the observed maxima are far smaller.
    # high-lat in particular: 450 -> 25, since the dominant error source
    # here used to be the bug (up to 432s) and is now just NOAA's
    # inherent low-precision-formula accuracy, amplified by the same
    # geometric sensitivity but starting from a ~30x smaller base error.
    # Second tightening, after the transit/Asr epoch-sampling fix (bug 2,
    # SPRINT-11-REPORT.md Sec 2): observed maxima are now 0.9-1.0 s for
    # non-high-lat bands and 3.6 s at high latitude.
    "equator": 3,
    "tropics": 3,
    "mid-lat-N": 3,
    "mid-lat-S": 3,
    "high-lat": 8,
}
TOLERANCE_SECONDS_LEVEL_B_VS_LEVEL_A = {
    "equator": 3,
    "tropics": 3,
    "mid-lat-N": 3,
    "mid-lat-S": 3,
    "high-lat": 6,
}


def _diff_seconds(a, b):
    if a is None or b is None:
        return None
    return round((a - b).total_seconds(), 3)


def run() -> dict:
    vectors = []
    max_abs_diff = {"waqt_vs_level_a": {}, "level_b_vs_level_a": {}}
    polar_agreement_failures = []

    for name, lat, lon, elevation_m, band in LOCATIONS:
        for d in DATES:
            waqt_day = waqt_solar.compute_day_events(d, lat, lon, elevation_m=elevation_m)
            b_day = level_b_events(d, lat, lon, elevation_m=elevation_m)
            a_day = level_a_events(d, lat, lon, elevation_m=elevation_m)

            events = {}
            for ev in EVENT_NAMES:
                w, b, a = getattr(waqt_day, ev), getattr(b_day, ev), getattr(a_day, ev)

                if band == "polar":
                    defined = {"waqt": w is not None, "level_b": b is not None, "level_a": a is not None}
                    if len(set(defined.values())) != 1:
                        polar_agreement_failures.append(
                            {"location": name, "date": d.isoformat(), "event": ev, **defined}
                        )
                    events[ev] = {"defined": defined}
                    continue

                dw = _diff_seconds(w, a)
                db = _diff_seconds(b, a)
                tol_w = TOLERANCE_SECONDS_WAQT_VS_LEVEL_A[band]
                tol_b = TOLERANCE_SECONDS_LEVEL_B_VS_LEVEL_A[band]
                events[ev] = {
                    "waqt": w.astimezone(timezone.utc).isoformat() if w else None,
                    "level_b": b.astimezone(timezone.utc).isoformat() if b else None,
                    "level_a": a.astimezone(timezone.utc).isoformat() if a else None,
                    "waqt_vs_level_a_diff_seconds": dw,
                    "level_b_vs_level_a_diff_seconds": db,
                    "waqt_within_tolerance": None if dw is None else abs(dw) <= tol_w,
                    "level_b_within_tolerance": None if db is None else abs(db) <= tol_b,
                }
                if dw is not None:
                    max_abs_diff["waqt_vs_level_a"][band] = max(max_abs_diff["waqt_vs_level_a"].get(band, 0.0), abs(dw))
                if db is not None:
                    max_abs_diff["level_b_vs_level_a"][band] = max(max_abs_diff["level_b_vs_level_a"].get(band, 0.0), abs(db))

            vectors.append({
                "location": name, "lat": lat, "lon": lon, "elevation_m": elevation_m,
                "latitude_band": band, "date": d.isoformat(),
                "tolerance_seconds_waqt": TOLERANCE_SECONDS_WAQT_VS_LEVEL_A.get(band),
                "tolerance_seconds_level_b": TOLERANCE_SECONDS_LEVEL_B_VS_LEVEL_A.get(band),
                "events": events,
            })

    return {
        "sprint": "Sprint 10 - Level-A astronomical reference comparison",
        "reference": {
            "name": "level_a",
            "theory": "VSOP87 (full series) via pymeeus.Sun.apparent_geocentric_position + pymeeus nutation/obliquity/GAST",
            "library": "pymeeus (independently published and tested; not written for this project)",
            "note": (
                "This is a comparison reference, not a production dependency: waqt/solar.py is "
                "unchanged, and independent_solar/ is unchanged. See level_a/sun.py's module docstring "
                "for why a real published library was used instead of hand-derived VSOP87 coefficients."
            ),
        },
        "tolerance_seconds_waqt_vs_level_a_by_band": TOLERANCE_SECONDS_WAQT_VS_LEVEL_A,
        "tolerance_seconds_level_b_vs_level_a_by_band": TOLERANCE_SECONDS_LEVEL_B_VS_LEVEL_A,
        "max_abs_diff_seconds_observed": {
            k: {band: round(v, 3) for band, v in bands.items()} for k, bands in max_abs_diff.items()
        },
        "polar_agreement_failures": polar_agreement_failures,
        "vectors": vectors,
    }


def main():
    report = run()
    out_path = _HERE / "vectors" / "level_a_comparison.json"
    out_path.write_text(json.dumps(report, indent=2) + "\n")

    print(f"Wrote {len(report['vectors'])} comparison rows to {out_path}")
    print("\nwaqt/solar.py vs Level A -- max |diff| observed, by band:")
    for band, tol in TOLERANCE_SECONDS_WAQT_VS_LEVEL_A.items():
        observed = report["max_abs_diff_seconds_observed"]["waqt_vs_level_a"].get(band)
        status = "OK" if (observed is None or observed <= tol) else "OVER TOLERANCE"
        print(f"  {band:12s} tolerance={tol:4d}s  observed_max={observed}  [{status}]")

    print("\nindependent_solar (Level B) vs Level A -- max |diff| observed, by band:")
    for band, tol in TOLERANCE_SECONDS_LEVEL_B_VS_LEVEL_A.items():
        observed = report["max_abs_diff_seconds_observed"]["level_b_vs_level_a"].get(band)
        status = "OK" if (observed is None or observed <= tol) else "OVER TOLERANCE"
        print(f"  {band:12s} tolerance={tol:4d}s  observed_max={observed}  [{status}]")

    if report["polar_agreement_failures"]:
        print(f"\nPolar UNDEFINED-status disagreements: {len(report['polar_agreement_failures'])}")
        for f in report["polar_agreement_failures"]:
            print(f"  {f}")
    else:
        print("\nNo polar UNDEFINED-status disagreements among the three engines.")


if __name__ == "__main__":
    main()

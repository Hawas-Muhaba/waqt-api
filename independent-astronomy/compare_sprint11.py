#!/usr/bin/env python3
"""
independent-astronomy/compare_sprint11.py — Sprint 11's astronomy
evaluation (Goal B).

Builds on Sprint 10's compare_level_a.py in three ways:

1. WIDER GEOGRAPHIC MATRIX. Sprint 10's matrix had one row per latitude
   band; this adds a dense latitude sweep (every 5 degrees from the
   equator to 80 degrees N, fixed longitude) so the error can be
   plotted as a continuous function of latitude, not just sampled at a
   handful of named cities.

2. WIDER SEASONAL MATRIX. Sprint 10 used 5 fixed dates (solstices,
   equinoxes, one arbitrary day). This adds a dedicated "days from
   equinox" sweep at a fixed high-latitude location, in both
   directions, because Sprint 10's own numbers (and this sprint's root-
   cause finding -- see docs/independent-astronomy/LEVEL-A.md Sec on
   the half-day bug) point at declination RATE OF CHANGE, which peaks
   at the equinoxes, as the driver of the high-latitude error -- so the
   matrix needs to resolve *how the error grows as the equinox is
   approached*, not just its value exactly at the equinox.

3. BEFORE/AFTER. This script is run twice per SPRINT-11-REPORT.md: once
   against the solar.py inherited unchanged from Sprint 10 (the
   half-day epoch-alignment bug present), and once after the one-line
   fix documented there. Pass --label to tag the output file
   (vectors/level_a_comparison_sprint11_<label>.json) so both runs are
   preserved side by side.

Usage:  python3 compare_sprint11.py --label before
        python3 compare_sprint11.py --label after
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_HERE))

from independent_solar import compute_day_events as level_b_events  # noqa: E402
from level_a.events import compute_day_events as level_a_events  # noqa: E402
from waqt_core import solar as waqt_solar  # noqa: E402

EVENT_NAMES = ["fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha"]

# --- 1. Named-city matrix (Sprint 10's, plus more high-latitude rows) ---
NAMED_LOCATIONS = [
    ("Quito (equator)", -0.1807, -78.4678, 0.0, "equator"),
    ("Nairobi (tropics, S)", -1.2921, 36.8219, 0.0, "tropics"),
    ("Addis Ababa (tropics, N)", 9.0192, 38.7525, 0.0, "tropics"),
    ("Addis Ababa @ 2400m", 9.0192, 38.7525, 2400.0, "tropics"),
    ("Makkah (tropics, N)", 21.4225, 39.8262, 0.0, "tropics"),
    ("Dibrugarh, NE India", 27.4728, 94.9120, 0.0, "mid-lat-N"),
    ("Cairo (mid-lat, N)", 30.0444, 31.2357, 0.0, "mid-lat-N"),
    ("Cape Town (mid-lat, S)", -33.9249, 18.4241, 0.0, "mid-lat-S"),
    ("Reykjavik (high-lat, N)", 64.1466, -21.9426, 0.0, "high-lat"),
    ("Anchorage (high-lat, N)", 61.2181, -149.9003, 0.0, "high-lat"),
    ("Tromso (high-lat, N)", 69.6492, 18.9553, 0.0, "high-lat"),
    ("Punta Arenas (high-lat, S)", -53.1638, -70.9171, 0.0, "high-lat"),
    ("Ushuaia (high-lat, S)", -54.8019, -68.3030, 0.0, "high-lat"),
    ("Suva, Fiji", -18.1416, 178.4419, 0.0, "tropics"),
    ("Kiritimati (UTC+14)", 1.8721, -157.4278, 0.0, "tropics"),
    ("Longyearbyen, Svalbard (polar)", 78.2232, 15.6469, 0.0, "polar"),
]

DATES = [
    date(2026, 3, 20),
    date(2026, 6, 21),
    date(2026, 9, 19),
    date(2026, 9, 23),
    date(2026, 12, 21),
]

# --- 2. Latitude sweep: every 5 deg 0..80N, fixed lon, near equinox ---
LATITUDE_SWEEP_LON = 18.9553  # Tromso's longitude, held fixed
LATITUDE_SWEEP_DATE = date(2026, 9, 19)  # 4 days before the Sep equinox
LATITUDE_SWEEP = [round(lat, 1) for lat in [i * 5.0 for i in range(0, 17)]]  # 0, 5, ..., 80

# --- 3. Equinox-proximity sweep: fixed high-lat location, days from equinox ---
EQUINOX_SWEEP_LOCATION = ("Tromso (high-lat, N)", 69.6492, 18.9553, 0.0)
SEPTEMBER_EQUINOX_2026 = date(2026, 9, 23)
EQUINOX_OFFSETS_DAYS = [-60, -30, -14, -7, -3, -1, 0, 1, 3, 7, 14, 30, 60]

TOLERANCE_SECONDS_WAQT_VS_LEVEL_A = {
    "equator": 25, "tropics": 35, "mid-lat-N": 45, "mid-lat-S": 55, "high-lat": 450,
}
TOLERANCE_SECONDS_LEVEL_B_VS_LEVEL_A = {
    "equator": 3, "tropics": 3, "mid-lat-N": 3, "mid-lat-S": 3, "high-lat": 6,
}


def _diff_seconds(a, b):
    if a is None or b is None:
        return None
    return round((a - b).total_seconds(), 3)


def _row(lat, lon, elevation_m, d):
    waqt_day = waqt_solar.compute_day_events(d, lat, lon, elevation_m=elevation_m)
    b_day = level_b_events(d, lat, lon, elevation_m=elevation_m)
    a_day = level_a_events(d, lat, lon, elevation_m=elevation_m)

    events = {}
    for ev in EVENT_NAMES:
        w, b, a = getattr(waqt_day, ev), getattr(b_day, ev), getattr(a_day, ev)
        events[ev] = {
            "waqt_vs_level_a_diff_seconds": _diff_seconds(w, a),
            "level_b_vs_level_a_diff_seconds": _diff_seconds(b, a),
            "all_defined": None not in (w, b, a),
            "all_undefined": w is None and b is None and a is None,
        }
    return events


def run_named_matrix():
    vectors, max_abs_diff, polar_agreement_failures = [], {"waqt_vs_level_a": {}, "level_b_vs_level_a": {}}, []
    for name, lat, lon, elevation_m, band in NAMED_LOCATIONS:
        for d in DATES:
            events_raw = _row(lat, lon, elevation_m, d)
            events = {}
            for ev, e in events_raw.items():
                if band == "polar":
                    events[ev] = {"all_defined": e["all_defined"], "all_undefined": e["all_undefined"]}
                    if not (e["all_defined"] or e["all_undefined"]):
                        polar_agreement_failures.append({"location": name, "date": d.isoformat(), "event": ev})
                    continue
                dw, db = e["waqt_vs_level_a_diff_seconds"], e["level_b_vs_level_a_diff_seconds"]
                tol_w = TOLERANCE_SECONDS_WAQT_VS_LEVEL_A[band]
                tol_b = TOLERANCE_SECONDS_LEVEL_B_VS_LEVEL_A[band]
                events[ev] = {
                    "waqt_vs_level_a_diff_seconds": dw, "level_b_vs_level_a_diff_seconds": db,
                    "waqt_within_tolerance": None if dw is None else abs(dw) <= tol_w,
                    "level_b_within_tolerance": None if db is None else abs(db) <= tol_b,
                }
                if dw is not None:
                    max_abs_diff["waqt_vs_level_a"][band] = max(max_abs_diff["waqt_vs_level_a"].get(band, 0.0), abs(dw))
                if db is not None:
                    max_abs_diff["level_b_vs_level_a"][band] = max(max_abs_diff["level_b_vs_level_a"].get(band, 0.0), abs(db))
            vectors.append({"location": name, "lat": lat, "lon": lon, "elevation_m": elevation_m,
                             "latitude_band": band, "date": d.isoformat(), "events": events})
    return vectors, max_abs_diff, polar_agreement_failures


def run_latitude_sweep():
    rows = []
    for lat in LATITUDE_SWEEP:
        events = _row(lat, LATITUDE_SWEEP_LON, 0.0, LATITUDE_SWEEP_DATE)
        # sunrise is the event most sensitive to the bug (largest hour angle offset from noon)
        rows.append({
            "lat": lat, "date": LATITUDE_SWEEP_DATE.isoformat(),
            "sunrise_waqt_vs_level_a_diff_seconds": events["sunrise"]["waqt_vs_level_a_diff_seconds"],
            "sunrise_level_b_vs_level_a_diff_seconds": events["sunrise"]["level_b_vs_level_a_diff_seconds"],
            "sunset_waqt_vs_level_a_diff_seconds": events["maghrib"]["waqt_vs_level_a_diff_seconds"],
            "sunset_level_b_vs_level_a_diff_seconds": events["maghrib"]["level_b_vs_level_a_diff_seconds"],
        })
    return rows


def run_equinox_sweep():
    name, lat, lon, elevation_m = EQUINOX_SWEEP_LOCATION
    rows = []
    for offset in EQUINOX_OFFSETS_DAYS:
        d = SEPTEMBER_EQUINOX_2026 + timedelta(days=offset)
        events = _row(lat, lon, elevation_m, d)
        rows.append({
            "days_from_equinox": offset, "date": d.isoformat(),
            "sunrise_waqt_vs_level_a_diff_seconds": events["sunrise"]["waqt_vs_level_a_diff_seconds"],
            "sunrise_level_b_vs_level_a_diff_seconds": events["sunrise"]["level_b_vs_level_a_diff_seconds"],
        })
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True, help="e.g. 'before' or 'after' -- tags the output filename")
    args = parser.parse_args()

    named_vectors, max_abs_diff, polar_failures = run_named_matrix()
    lat_sweep = run_latitude_sweep()
    equinox_sweep = run_equinox_sweep()

    report = {
        "sprint": "Sprint 11 - expanded geographic/seasonal Level-A comparison",
        "label": args.label,
        "tolerance_seconds_waqt_vs_level_a_by_band": TOLERANCE_SECONDS_WAQT_VS_LEVEL_A,
        "tolerance_seconds_level_b_vs_level_a_by_band": TOLERANCE_SECONDS_LEVEL_B_VS_LEVEL_A,
        "max_abs_diff_seconds_observed": {k: {b: round(v, 3) for b, v in bands.items()} for k, bands in max_abs_diff.items()},
        "polar_agreement_failures": polar_failures,
        "named_matrix": named_vectors,
        "latitude_sweep": {"lon": LATITUDE_SWEEP_LON, "date": LATITUDE_SWEEP_DATE.isoformat(), "rows": lat_sweep},
        "equinox_proximity_sweep": {"location": EQUINOX_SWEEP_LOCATION, "equinox": SEPTEMBER_EQUINOX_2026.isoformat(), "rows": equinox_sweep},
    }

    out_path = _HERE / "vectors" / f"level_a_comparison_sprint11_{args.label}.json"
    out_path.write_text(json.dumps(report, indent=2) + "\n")
    print(f"[{args.label}] wrote {len(named_vectors)} named-matrix rows, {len(lat_sweep)} latitude-sweep rows, "
          f"{len(equinox_sweep)} equinox-sweep rows -> {out_path}")

    print(f"\n[{args.label}] waqt vs Level A -- max |diff| by band:")
    for band, v in report["max_abs_diff_seconds_observed"]["waqt_vs_level_a"].items():
        print(f"  {band:12s} {v:10.3f}s")
    print(f"\n[{args.label}] Level B vs Level A -- max |diff| by band:")
    for band, v in report["max_abs_diff_seconds_observed"]["level_b_vs_level_a"].items():
        print(f"  {band:12s} {v:10.3f}s")

    print(f"\n[{args.label}] latitude sweep (sunrise, waqt vs Level A), lon={LATITUDE_SWEEP_LON}, date={LATITUDE_SWEEP_DATE}:")
    for row in lat_sweep:
        print(f"  lat={row['lat']:5.1f}  waqt_diff={row['sunrise_waqt_vs_level_a_diff_seconds']!s:>10}  level_b_diff={row['sunrise_level_b_vs_level_a_diff_seconds']!s:>8}")

    print(f"\n[{args.label}] equinox-proximity sweep (sunrise, Tromso, waqt vs Level A):")
    for row in equinox_sweep:
        print(f"  days_from_equinox={row['days_from_equinox']:+4d}  waqt_diff={row['sunrise_waqt_vs_level_a_diff_seconds']!s:>10}  level_b_diff={row['sunrise_level_b_vs_level_a_diff_seconds']!s:>8}")


if __name__ == "__main__":
    main()

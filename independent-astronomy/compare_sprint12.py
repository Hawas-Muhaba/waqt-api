#!/usr/bin/env python3
"""
independent-astronomy/compare_sprint12.py — Sprint 12 Goal C: astronomy
evidence expansion.

Deliberately smaller than Sprint 11 (which found and fixed a real bug).
This script does three things:

1. ADDITIONAL YEARS. Sprint 11's compare_sprint11.py ran one calendar year
   (2026). Equinox/solstice dates drift by about six hours a year and reset
   with the leap-year cycle, so a single year cannot show whether an
   agreement/disagreement is a property of the *geometry* (latitude, season)
   or an artifact of 2026's specific dates. This script repeats Sprint 11's
   named-location matrix at seven years spanning a full leap-year cycle
   before and after 2026: 2019, 2022, 2023, 2026, 2027, 2030, 2033.

2. GEOGRAPHIC MATRIX RETAINED, UNCHANGED. `NAMED_LOCATIONS` and
   `TOLERANCE_SECONDS_*` are imported from compare_sprint11.py, not
   redefined — a location or tolerance drifting between scripts would
   quietly change what "agreement" means. NOTE: TOLERANCE_SECONDS_WAQT_VS_LEVEL_A["high-lat"]
   is currently imported at its stale Sprint 10 value (450 s, set before the
   Sprint 11 epoch bugfix); it needs deliberate recalibration down to a post-fix
   bound in a future sprint. The dense latitude/equinox sweeps are NOT
   repeated here: they characterise the error as a function of latitude and
   season at a fixed epoch, which Sprint 11 already answered; repeating them at
   seven years would multiply the run without adding a new question. Sprint 11's
   numbers are cited as-is (Section "carried over" below) rather than re-run for
   no reason.

3. INDEPENDENT REFERENCE DIRECTION: attempted, not delivered. A genuinely
   different reference (an ephemeris-backed library other than pymeeus, or
   a published almanac's numeric tables) was the goal. This sandbox has no
   network access and no additional astronomy package beyond `pymeeus`
   itself (already Level A) and the hand-rolled Level B here, so nothing
   independent of {waqt-core, pymeeus, this repo's own Meeus implementation}
   was available to try. See docs/ACCURACY-LEVEL-REVIEW.md Sec "Sprint 12"
   for what a real attempt would need (`skyfield` + a JPL DE44x kernel, or
   `astropy.coordinates` + `jplephem`, both requiring a package index and a
   multi-MB ephemeris download this environment cannot reach).

Level A (pymeeus/VSOP87) is used WHEN AVAILABLE and the run notes plainly
when it was not, rather than silently reporting Level-B-only numbers as if
they were the full three-way comparison. `ACCURACY_LEVEL` is not touched by
this script; core/tests/test_engine_revision.py pins it and Goal C's brief
explicitly asks for the label decision to stay an explicit review point.

Usage:  python3 compare_sprint12.py
Output: vectors/multi_year_comparison_sprint12.json
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "core"))
sys.path.insert(0, str(_HERE))

from compare_sprint11 import (  # noqa: E402  (matrix + tolerances: reused; note TOLERANCE_SECONDS_WAQT_VS_LEVEL_A['high-lat'] is stale 450s legacy)
    EVENT_NAMES,
    NAMED_LOCATIONS,
    TOLERANCE_SECONDS_LEVEL_B_VS_LEVEL_A,
    TOLERANCE_SECONDS_WAQT_VS_LEVEL_A,
)
from independent_solar import compute_day_events as level_b_events  # noqa: E402
from waqt_core import solar as waqt_solar  # noqa: E402
from waqt_core.versioning import computation_identity  # noqa: E402

_LEVEL_A_IMPORT_ERROR = None
try:
    from level_a.events import compute_day_events as level_a_events  # noqa: E402

    # `level_a/` imports `pymeeus` unconditionally, so a stub package that lets
    # the import succeed but raises on real use (as this sandbox's does; see
    # /tmp/stubs/pymeeus in SPRINT-12-REPORT.md) would otherwise look
    # "available" here. Prove it can actually compute before trusting it.
    level_a_events(date(2026, 3, 20), 9.0192, 38.7525)
    LEVEL_A_AVAILABLE = True
except Exception as e:  # ImportError (no level_a/pymeeus at all) or a stub's RuntimeError
    LEVEL_A_AVAILABLE = False
    _LEVEL_A_IMPORT_ERROR = f"{type(e).__name__}: {e}"

    def level_a_events(*a, **k):  # pragma: no cover - only called if LEVEL_A_AVAILABLE
        raise RuntimeError("level_a unavailable")


# Years spanning a full 4-year leap cycle either side of the reference year,
# not chosen to flatter any particular result.
YEARS = [2019, 2022, 2023, 2026, 2027, 2030, 2033]

# Sprint 11's five fixed dates, expressed as (month, day) and re-anchored to
# each year in YEARS below. September 23 (not a fixed equinox date -- the
# September equinox itself moves between the 22nd and 23rd) is kept as a
# literal date, same as Sprint 11, rather than "corrected" per year: this
# script is testing the engines at approximately-equinox/solstice dates, not
# computing the equinox instant itself (a separate, harder problem outside
# this scope).
MONTH_DAYS = [(3, 20), (6, 21), (9, 19), (9, 23), (12, 21)]


def _diff_seconds(a, b):
    if a is None or b is None:
        return None
    return round((a - b).total_seconds(), 3)


def _row(lat, lon, elevation_m, d):
    waqt_day = waqt_solar.compute_day_events(d, lat, lon, elevation_m=elevation_m)
    b_day = level_b_events(d, lat, lon, elevation_m=elevation_m)
    a_day = level_a_events(d, lat, lon, elevation_m=elevation_m) if LEVEL_A_AVAILABLE else None

    events = {}
    for ev in EVENT_NAMES:
        w, b = getattr(waqt_day, ev), getattr(b_day, ev)
        a = getattr(a_day, ev) if a_day is not None else None
        events[ev] = {
            "waqt_vs_level_a_diff_seconds": _diff_seconds(w, a) if LEVEL_A_AVAILABLE else None,
            "level_b_vs_level_a_diff_seconds": _diff_seconds(b, a) if LEVEL_A_AVAILABLE else None,
            "waqt_vs_level_b_diff_seconds": _diff_seconds(w, b),
            "all_defined": None not in (w, b, (a if LEVEL_A_AVAILABLE else w)),
            "all_undefined": w is None and b is None and (a is None if LEVEL_A_AVAILABLE else True),
        }
    return events


def run():
    vectors = []
    max_abs_diff = {"waqt_vs_level_a": {}, "level_b_vs_level_a": {}, "waqt_vs_level_b": {}}
    polar_agreement_failures = []
    within_tolerance_failures = []

    for name, lat, lon, elevation_m, band in NAMED_LOCATIONS:
        for year in YEARS:
            for month, day in MONTH_DAYS:
                d = date(year, month, day)
                events_raw = _row(lat, lon, elevation_m, d)
                events = {}
                for ev, e in events_raw.items():
                    if band == "polar":
                        events[ev] = {"all_defined": e["all_defined"], "all_undefined": e["all_undefined"]}
                        if not (e["all_defined"] or e["all_undefined"]):
                            polar_agreement_failures.append(
                                {"location": name, "date": d.isoformat(), "event": ev}
                            )
                        continue
                    dw, db, dwb = (
                        e["waqt_vs_level_a_diff_seconds"],
                        e["level_b_vs_level_a_diff_seconds"],
                        e["waqt_vs_level_b_diff_seconds"],
                    )
                    entry = {
                        "waqt_vs_level_a_diff_seconds": dw,
                        "level_b_vs_level_a_diff_seconds": db,
                        "waqt_vs_level_b_diff_seconds": dwb,
                    }
                    if LEVEL_A_AVAILABLE:
                        tol_w, tol_b = TOLERANCE_SECONDS_WAQT_VS_LEVEL_A[band], TOLERANCE_SECONDS_LEVEL_B_VS_LEVEL_A[band]
                        entry["waqt_within_tolerance"] = None if dw is None else abs(dw) <= tol_w
                        entry["level_b_within_tolerance"] = None if db is None else abs(db) <= tol_b
                        if dw is not None:
                            max_abs_diff["waqt_vs_level_a"][band] = max(max_abs_diff["waqt_vs_level_a"].get(band, 0.0), abs(dw))
                            if abs(dw) > tol_w:
                                within_tolerance_failures.append(
                                    {"location": name, "date": d.isoformat(), "event": ev, "diff_seconds": dw, "tolerance": tol_w}
                                )
                        if db is not None:
                            max_abs_diff["level_b_vs_level_a"][band] = max(max_abs_diff["level_b_vs_level_a"].get(band, 0.0), abs(db))
                    if dwb is not None:
                        max_abs_diff["waqt_vs_level_b"][band] = max(max_abs_diff["waqt_vs_level_b"].get(band, 0.0), abs(dwb))
                    events[ev] = entry
                vectors.append(
                    {"location": name, "lat": lat, "lon": lon, "elevation_m": elevation_m,
                     "latitude_band": band, "year": year, "date": d.isoformat(), "events": events}
                )

    return {
        "sprint": 12,
        "goal": "C — astronomy evidence expansion",
        "years_covered": YEARS,
        "geographic_matrix": "unchanged from Sprint 11 (compare_sprint11.NAMED_LOCATIONS)",
        "level_a_available": LEVEL_A_AVAILABLE,
        "level_a_unavailable_reason": None if LEVEL_A_AVAILABLE else _LEVEL_A_IMPORT_ERROR,
        "independent_reference_direction_attempted": True,
        "independent_reference_direction_delivered": False,
        "independent_reference_direction_note": (
            "No network access and no astronomy package beyond pymeeus (already Level A) and this "
            "repo's own Meeus implementation (Level B) was available in this environment; see "
            "docs/ACCURACY-LEVEL-REVIEW.md."
        ),
        "accuracy_level_changed_this_sprint": False,
        "computation_identity_under_test": computation_identity(),
        "max_abs_diff_seconds": max_abs_diff,
        "polar_agreement_failures": polar_agreement_failures,
        "within_tolerance_failures": within_tolerance_failures,
        "row_count": len(vectors),
        "vectors": vectors,
    }


def main():
    result = run()
    out_path = _HERE / "vectors" / "multi_year_comparison_sprint12.json"
    out_path.write_text(json.dumps(result, indent=1, default=str) + "\n")

    print(f"Level A available: {result['level_a_available']}")
    if not result["level_a_available"]:
        print(f"  ({result['level_a_unavailable_reason']})")
    print(f"Years: {result['years_covered']}")
    print(f"Rows: {result['row_count']}")
    print("Max |diff| (waqt vs level_b), seconds, by band:")
    for band, v in sorted(result["max_abs_diff_seconds"]["waqt_vs_level_b"].items()):
        print(f"  {band:<12} {v:.3f}")
    if result["level_a_available"]:
        print("Max |diff| (waqt vs level_a), seconds, by band:")
        for band, v in sorted(result["max_abs_diff_seconds"]["waqt_vs_level_a"].items()):
            print(f"  {band:<12} {v:.3f}")
        if result["within_tolerance_failures"]:
            print(f"TOLERANCE FAILURES: {len(result['within_tolerance_failures'])} — see output file")
    if result["polar_agreement_failures"]:
        print(f"POLAR AGREEMENT FAILURES: {len(result['polar_agreement_failures'])} — see output file")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()

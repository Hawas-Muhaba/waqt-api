#!/usr/bin/env python3
"""
independent-astronomy/compare_skyfield_sprint13.py -- Sprint 13 Goal D.

Compares Waqt (production), Level B, Level A (VSOP87/pymeeus) against the
INDEPENDENT reference in skyfield_reference/ (JPL DE421 + Skyfield IAU2006/2000A).

Part 1  Matrix: exactly Sprint 12's 7 years x NAMED_LOCATIONS x 5 dates x 6 events (560 rows).
Part 2  Parallax sensitivity: same matrix, topocentric altitudes (differences vs geocentric).
Part 3  Dense scans (every day of a year) at boundary/high-latitude sites:
        Tromso 2019 & 2026, Reykjavik 2019, Longyearbyen 2026 (event existence + error).
Part 4  Polar existence agreement across all four engines.

Does not modify tolerances or ACCURACY_LEVEL.  Usage: python compare_skyfield_sprint13.py [--quick]
Output: vectors/skyfield_reference_sprint13.json
"""
from __future__ import annotations
import json, statistics, sys
from datetime import date, timedelta
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(_HERE), str(_HERE.parent), str(_HERE.parent / "core")]
from compare_sprint11 import EVENT_NAMES, NAMED_LOCATIONS  # noqa: E402  (matrix reused, never redefined)
from compare_sprint12 import YEARS, MONTH_DAYS  # noqa: E402
from independent_solar import compute_day_events as level_b  # noqa: E402
from level_a.events import compute_day_events as level_a  # noqa: E402
from waqt_core import solar as waqt_solar  # noqa: E402
from waqt_core.versioning import computation_identity  # noqa: E402
from skyfield_reference import compute_day_events as sky  # noqa: E402

QUICK = "--quick" in sys.argv

def dsec(a, b):
    return None if a is None or b is None else round((a - b).total_seconds(), 3)

def stats(xs):
    if not xs: return None
    a = sorted(abs(x) for x in xs)
    return {"n": len(xs), "max_abs": round(a[-1], 3), "mean_abs": round(statistics.mean(a), 3),
            "median_abs": round(statistics.median(a), 3), "p95_abs": round(a[int(0.95 * (len(a) - 1))], 3),
            "mean_signed": round(statistics.mean(xs), 3)}

ENGINES = {"waqt": lambda d, la, lo, el: waqt_solar.compute_day_events(d, la, lo, elevation_m=el),
           "level_b": lambda d, la, lo, el: level_b(d, la, lo, elevation_m=el),
           "level_a": lambda d, la, lo, el: level_a(d, la, lo, elevation_m=el)}

def matrix():
    rows, per = [], {e: {} for e in ENGINES}          # per[engine][band][event] -> diffs
    topo_delta = {}                                   # band -> |topo - geo| seconds (sky)
    polar = {"instances": 0, "all_four_agree_defined": 0, "all_four_agree_undefined": 0, "disagree": []}
    years = YEARS[:2] if QUICK else YEARS
    for name, lat, lon, el, band in NAMED_LOCATIONS:
        for y in years:
            for m, dd in MONTH_DAYS:
                d = date(y, m, dd)
                ref = sky(d, lat, lon, el)
                ref_t = sky(d, lat, lon, el, mode="topocentric")
                eng = {k: f(d, lat, lon, el) for k, f in ENGINES.items()}
                row = {"location": name, "band": band, "date": d.isoformat(), "events": {}}
                for ev in EVENT_NAMES:
                    r = getattr(ref, ev)
                    if band == "polar":
                        defs = [getattr(eng[k], ev) is not None for k in ENGINES] + [r is not None]
                        polar["instances"] += 1
                        if all(defs): polar["all_four_agree_defined"] += 1
                        elif not any(defs): polar["all_four_agree_undefined"] += 1
                        else: polar["disagree"].append({"date": d.isoformat(), "event": ev, "defined": dict(zip([*ENGINES, "skyfield"], defs))})
                        row["events"][ev] = {"defined": defs}
                        continue
                    e = {"skyfield": r.isoformat() if r else None}
                    for k in ENGINES:
                        x = dsec(getattr(eng[k], ev), r); e[f"{k}_minus_skyfield_s"] = x
                        if x is not None: per[k].setdefault(band, {}).setdefault(ev, []).append(x)
                    tt = getattr(ref_t, ev)
                    e["topocentric_minus_geocentric_s"] = dsec(tt, r)
                    if e["topocentric_minus_geocentric_s"] is not None:
                        topo_delta.setdefault(band, []).append(e["topocentric_minus_geocentric_s"])
                    row["events"][ev] = e
                rows.append(row)
    return rows, per, topo_delta, polar

def agg(per):
    out = {}
    for k, bands in per.items():
        out[k] = {"per_band": {b: stats([x for v in evs.values() for x in v]) for b, evs in bands.items()},
                  "per_event": {ev: stats([x for evs in bands.values() for x in evs.get(ev, [])]) for ev in EVENT_NAMES},
                  "per_band_x_event": {b: {ev: stats(v) for ev, v in evs.items()} for b, evs in bands.items()},
                  "overall": stats([x for evs in bands.values() for v in evs.values() for x in v])}
    return out

def dense(name, lat, lon, year, el=0.0):
    out = {"location": name, "lat": lat, "lon": lon, "year": year, "days": 0, "existence_disagreements": [],
           "per_event_defined_days": {ev: {"skyfield": 0, "waqt": 0} for ev in EVENT_NAMES}, "diffs": {ev: [] for ev in EVENT_NAMES}, "worst": []}
    d = date(year, 1, 1)
    step = 5 if QUICK else 1
    while d.year == year:
        r = sky(d, lat, lon, el); w = waqt_solar.compute_day_events(d, lat, lon, elevation_m=el)
        out["days"] += 1
        for ev in EVENT_NAMES:
            a, b = getattr(w, ev), getattr(r, ev)
            out["per_event_defined_days"][ev]["skyfield"] += b is not None
            out["per_event_defined_days"][ev]["waqt"] += a is not None
            if (a is None) != (b is None):
                out["existence_disagreements"].append({"date": d.isoformat(), "event": ev, "waqt_defined": a is not None, "skyfield_defined": b is not None})
            elif a is not None:
                x = dsec(a, b); out["diffs"][ev].append(x); out["worst"].append((abs(x), d.isoformat(), ev, x))
        d += timedelta(days=step)
    out["worst"] = [dict(zip(("abs", "date", "event", "waqt_minus_skyfield_s"), w)) for w in sorted(out["worst"], reverse=True)[:8]]
    out["stats_per_event"] = {ev: stats(v) for ev, v in out["diffs"].items()}
    out["stats_all"] = stats([x for v in out["diffs"].values() for x in v])
    del out["diffs"]
    return out

def main():
    rows, per, topo, polar = matrix()
    result = {"sprint": 13, "goal": "D -- independent reference (JPL DE421 + Skyfield)", "quick": QUICK,
              "computation_identity_under_test": computation_identity(),
              "reference": {"ephemeris": "JPL DE421 (de421 PyPI package, jplephem legacy format)", "library": "skyfield",
                            "apparent_place": "light-time + aberration (+ deflection) via Skyfield", "sidereal_time": "Skyfield GAST (IAU 2006/2000A)",
                            "timescale": "Skyfield builtin UT1/TT tables (NOT Espenak-Meeus)", "root_finder": "own grid refinement, skyfield_reference/events.py",
                            "shared_with_waqt": "event DEFINITIONS only (18/17 deg, -0.8333 deg, dip formula, Asr formula, day-selection rule)"},
              "years": YEARS[:2] if QUICK else YEARS, "row_count": len(rows),
              "matrix_stats": agg(per),
              "parallax_sensitivity_topocentric_minus_geocentric_s": {b: stats(v) for b, v in topo.items()},
              "polar_existence_four_way": polar, "rows": rows}
    result["dense_scans"] = [dense("Tromso", 69.6492, 18.9553, 2019), dense("Tromso", 69.6492, 18.9553, 2026),
                             dense("Reykjavik", 64.1466, -21.9426, 2019), dense("Longyearbyen (Svalbard)", 78.2232, 15.6469, 2026)]
    out = _HERE / "vectors" / ("skyfield_reference_sprint13_quick.json" if QUICK else "skyfield_reference_sprint13.json")
    out.write_text(json.dumps(result, indent=1, default=str) + "\n")
    for k in ENGINES:
        print(f"\n{k} - skyfield (s):  band n max mean median")
        for b, s in sorted(result["matrix_stats"][k]["per_band"].items()): print(f"  {b:10s}{s['n']:5d} {s['max_abs']:7.3f} {s['mean_abs']:7.3f} {s['median_abs']:7.3f}")
    print("\npolar four-way:", {k: v for k, v in polar.items() if k != "disagree"}, "disagree:", len(polar["disagree"]))
    print("parallax sensitivity max:", {b: s["max_abs"] for b, s in result["parallax_sensitivity_topocentric_minus_geocentric_s"].items()})
    for ds in result["dense_scans"]:
        print(f"\ndense {ds['location']} {ds['year']}: days={ds['days']} existence disagreements={len(ds['existence_disagreements'])} all={ds['stats_all']}")
        print("  worst:", ds["worst"][:3])
    print("wrote", out)

if __name__ == "__main__":
    main()

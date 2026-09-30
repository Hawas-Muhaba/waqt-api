#!/usr/bin/env python3
"""
independent-astronomy/compare_sprint13.py -- Sprint 13 Goal C.

Re-runs Sprint 12's multi-year study UNCHANGED (it calls compare_sprint12.run():
same 7 years, same NAMED_LOCATIONS matrix, same 5 dates/year, same 6 events,
same methodology) with real pymeeus, then adds what Sprint 12 did not report:
mean / median / max per band, per event, per band x event; the worst rows; the
high-latitude and polar breakdown; and a row-by-row comparison with the committed
Sprint 12 output (reproducibility check).

It does NOT change tolerances and does NOT touch ACCURACY_LEVEL.
Usage: python compare_sprint13.py     Output: vectors/multi_year_comparison_sprint13.json
"""
from __future__ import annotations
import json, statistics, sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import compare_sprint12 as s12  # noqa: E402
from compare_sprint11 import EVENT_NAMES  # noqa: E402

PAIRS = ("waqt_vs_level_a", "level_b_vs_level_a", "waqt_vs_level_b")
KEY = {p: p + "_diff_seconds" for p in PAIRS}

def _stats(xs):
    if not xs: return None
    a = [abs(x) for x in xs]
    return {"n": len(xs), "max_abs": round(max(a), 3), "mean_abs": round(statistics.mean(a), 3),
            "median_abs": round(statistics.median(a), 3), "mean_signed": round(statistics.mean(xs), 3),
            "p95_abs": round(sorted(a)[int(0.95 * (len(a) - 1))], 3)}

def analyse(result):
    rows = result["vectors"]
    by_band, by_event, by_be, worst = {}, {}, {}, []
    high_by_loc, polar = {}, {"rows": 0, "dates": 0, "all_defined_events": 0, "all_undefined_events": 0, "disagreements": 0, "per_date": []}
    for r in rows:
        band = r["latitude_band"]
        if band == "polar":
            polar["rows"] += 1
            st = {ev: ("defined" if e["all_defined"] else "undefined" if e["all_undefined"] else "DISAGREE") for ev, e in r["events"].items()}
            polar["per_date"].append({"date": r["date"], "status": st})
            for v in st.values():
                polar["all_defined_events" if v == "defined" else "all_undefined_events" if v == "undefined" else "disagreements"] += 1
            continue
        for ev, e in r["events"].items():
            for p in PAIRS:
                v = e.get(KEY[p])
                if v is None: continue
                by_band.setdefault(p, {}).setdefault(band, []).append(v)
                by_event.setdefault(p, {}).setdefault(ev, []).append(v)
                by_be.setdefault(p, {}).setdefault(band, {}).setdefault(ev, []).append(v)
                if band == "high-lat":
                    high_by_loc.setdefault(p, {}).setdefault(r["location"], []).append(v)
                if p == "waqt_vs_level_a":
                    worst.append({"location": r["location"], "band": band, "date": r["date"], "event": ev, "diff_seconds": v})
    worst.sort(key=lambda x: -abs(x["diff_seconds"]))
    undefined_nonpolar = sum(1 for r in rows if r["latitude_band"] != "polar" for e in r["events"].values() if e.get(KEY["waqt_vs_level_b"]) is None)
    return {
        "per_band": {p: {b: _stats(v) for b, v in d.items()} for p, d in by_band.items()},
        "per_event": {p: {ev: _stats(by_event[p].get(ev, [])) for ev in EVENT_NAMES} for p in by_event},
        "per_band_x_event": {p: {b: {ev: _stats(v) for ev, v in evs.items()} for b, evs in d.items()} for p, d in by_be.items()},
        "overall": {p: _stats([x for v in d.values() for x in v]) for p, d in by_band.items()},
        "high_latitude_by_location": {p: {loc: _stats(v) for loc, v in d.items()} for p, d in high_by_loc.items()},
        "worst_10_waqt_vs_level_a": worst[:10],
        "non_polar_event_instances_undefined_in_some_engine": undefined_nonpolar,
        "polar": polar,
    }

def reproducibility_vs_sprint12(new):
    old_path = _HERE / "vectors" / "multi_year_comparison_sprint12.json"
    old = json.loads(old_path.read_text())
    n_cmp = n_diff = 0; diffs = []
    for ro, rn in zip(old["vectors"], new["vectors"]):
        assert (ro["location"], ro["date"]) == (rn["location"], rn["date"])
        for ev in rn["events"]:
            for k, v in rn["events"][ev].items():
                n_cmp += 1
                if ro["events"][ev].get(k) != v:
                    n_diff += 1; diffs.append({"location": rn["location"], "date": rn["date"], "event": ev, "field": k,
                                               "sprint12": ro["events"][ev].get(k), "sprint13": v})
    return {"rows_sprint12": len(old["vectors"]), "rows_sprint13": len(new["vectors"]), "fields_compared": n_cmp,
            "fields_differing": n_diff, "differences": diffs[:50],
            "sprint12_max_abs_diff_seconds": old["max_abs_diff_seconds"]}

def main():
    if not s12.LEVEL_A_AVAILABLE:
        sys.exit(f"Level A (pymeeus) unavailable: {s12._LEVEL_A_IMPORT_ERROR}")
    result = s12.run()
    result["sprint"] = 13
    result["goal"] = "C -- multi-year Level-A/Level-B study (re-run of Sprint 12 methodology)"
    result.pop("independent_reference_direction_attempted", None); result.pop("independent_reference_direction_delivered", None)
    result.pop("independent_reference_direction_note", None)
    result["independent_reference"] = "see independent-astronomy/vectors/skyfield_reference_sprint13.json (compare_skyfield_sprint13.py)"
    result["tolerances_used_unchanged"] = {"waqt_vs_level_a": s12.TOLERANCE_SECONDS_WAQT_VS_LEVEL_A,
                                            "level_b_vs_level_a": s12.TOLERANCE_SECONDS_LEVEL_B_VS_LEVEL_A}
    result["analysis"] = analyse(result)
    result["reproducibility_vs_sprint12"] = reproducibility_vs_sprint12(result)
    out = _HERE / "vectors" / "multi_year_comparison_sprint13.json"
    out.write_text(json.dumps(result, indent=1, default=str) + "\n")
    a = result["analysis"]
    print(f"rows={result['row_count']} years={result['years_covered']} identity={result['computation_identity_under_test']}")
    for p in PAIRS:
        print(f"\n{p}: band  n  max  mean  median")
        for b, s in sorted(a["per_band"][p].items()): print(f"  {b:10s} {s['n']:4d} {s['max_abs']:7.3f} {s['mean_abs']:7.3f} {s['median_abs']:7.3f}")
    print("\nworst 5 waqt_vs_level_a:", *a["worst_10_waqt_vs_level_a"][:5], sep="\n  ")
    print("polar:", {k: v for k, v in a["polar"].items() if k != "per_date"})
    rp = result["reproducibility_vs_sprint12"]; print(f"vs Sprint 12: {rp['fields_differing']}/{rp['fields_compared']} fields differ")
    print("tolerance failures (legacy tolerances):", len(result["within_tolerance_failures"]))

if __name__ == "__main__":
    main()

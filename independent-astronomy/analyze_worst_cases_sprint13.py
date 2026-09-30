#!/usr/bin/env python3
"""Sprint 13: turn Waqt-vs-JPL TIME differences into ANGLES, and adjudicate event-existence disagreements.

For each worst-case (date, event): evaluate the JPL/Skyfield geocentric altitude at the instant Waqt reported.
  angular_error = altitude(t_waqt) - target_altitude          (arcseconds)
  slope         = d altitude / dt at the event                 (arcsec per second)
so time_error ~= angular_error / slope, showing whether a large time error is a large angle (bad) or a
tiny angle over a nearly-flat altitude curve (geometry).  For existence disagreements: the JPL altitude
extremum vs the threshold (margin in arcseconds).
Output: vectors/worst_case_analysis_sprint13.json
"""
from __future__ import annotations
import json, math, sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import numpy as np
_HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(_HERE), str(_HERE.parent), str(_HERE.parent / "core")]
from skyfield_reference import compute_day_events as sky
from skyfield_reference.events import _altitude_fn, SUN_HORIZON_DEG  # geocentric altitude of the Sun's centre
from waqt_core import solar as W

LOC = {"Tromso": (69.6492, 18.9553), "Reykjavik": (64.1466, -21.9426), "Longyearbyen (Svalbard)": (78.2232, 15.6469)}
TARGET = {"fajr": -18.0, "isha": -17.0, "sunrise": SUN_HORIZON_DEG, "maghrib": SUN_HORIZON_DEG}

def alt_at(lat, lon, d, dt):
    day0 = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    f = _altitude_fn(lat, lon, "geocentric", day0)
    return lambda t: float(f(np.array([(t - day0).total_seconds()]))[0])

def target_for(ev, lat, lon, d):
    if ev in TARGET: return TARGET[ev]
    r = sky(d, lat, lon)                           # asr target from JPL declination at transit (spec formula)
    from skyfield_reference.events import sun_geocentric_apparent, _times
    day0 = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    _, dec, _ = sun_geocentric_apparent(_times(day0, [(r.dhuhr - day0).total_seconds()]))
    z = abs(lat - float(dec[0])); return math.degrees(math.atan(1.0 / (1.0 + math.tan(math.radians(z)))))

def case(name, d, ev):
    lat, lon = LOC[name]; d = date.fromisoformat(d)
    w = getattr(W.compute_day_events(d, lat, lon), ev); s = getattr(sky(d, lat, lon), ev)
    tgt = target_for(ev, lat, lon, d); f = alt_at(lat, lon, d, s)
    a_w = f(w); slope = (f(s + timedelta(seconds=1)) - f(s - timedelta(seconds=1))) / 2.0   # deg/s
    return {"location": name, "date": d.isoformat(), "event": ev, "time_diff_waqt_minus_jpl_s": round((w - s).total_seconds(), 3),
            "jpl_altitude_slope_arcsec_per_s": round(slope * 3600, 3), "angular_error_at_waqt_time_arcsec": round((a_w - tgt) * 3600, 3),
            "implied_time_error_s": round((a_w - tgt) / slope, 3) if slope else None}

def existence(name, d, ev):
    """Adjudicate a day on which Waqt and the JPL reference disagree about whether `ev` occurs.
    Reports what each engine (Waqt, Level A, Level B, JPL) said and the physical margin in arcseconds."""
    from level_a.events import compute_day_events as LA
    from independent_solar import compute_day_events as LB
    from skyfield_reference.events import sun_geocentric_apparent, _times
    lat, lon = LOC[name]; d = date.fromisoformat(d)
    day0 = datetime(d.year, d.month, d.day, tzinfo=timezone.utc); f = _altitude_fn(lat, lon, "geocentric", day0)
    s0 = sky(d, lat, lon); tr = (s0.dhuhr - day0).total_seconds()
    said = {"jpl_skyfield": getattr(s0, ev), "waqt": getattr(W.compute_day_events(d, lat, lon), ev),
            "level_a": getattr(LA(d, lat, lon), ev), "level_b": getattr(LB(d, lat, lon), ev)}
    said = {k: (v.isoformat() if v else None) for k, v in said.items()}
    if ev in ("fajr", "isha"):
        tgt = TARGET[ev]; sec = tr + np.arange(-13 * 3600, 0, 5.0) if ev == "fajr" else tr + np.arange(0, 13 * 3600, 5.0)
        ext = float(f(sec).min()); margin = (tgt - ext) * 3600
        what = f"JPL minimum altitude on the twilight side of transit = {ext:.5f} deg vs threshold {tgt} deg"
    else:   # asr exists iff the sun's noon altitude reaches the Asr target altitude (spec formula)
        _, dec, _ = sun_geocentric_apparent(_times(day0, [tr])); z = abs(lat - float(dec[0]))
        noon_alt = 90.0 - z; tgt = math.degrees(math.atan(1.0 / (1.0 + math.tan(math.radians(z)))))
        margin = (noon_alt - tgt) * 3600; ext = noon_alt
        what = f"JPL geometric noon altitude {noon_alt:.5f} deg vs Asr target altitude {tgt:.5f} deg"
    return {"location": name, "date": d.isoformat(), "event": ev, "engines_said": said, "physical_margin_arcsec": round(margin, 2),
            "detail": what, "reading": "margin > 0 means the event physically occurs per JPL; |margin| of a few arcsec is inside every engine's model error"}

def main():
    dense = json.loads((_HERE / "vectors/skyfield_reference_sprint13.json").read_text())["dense_scans"]
    cases = []
    for ds in dense:
        for w in ds["worst"][:4]: cases.append(case(ds["location"].split(" (")[0] if ds["location"].startswith("Tromso") or ds["location"].startswith("Rey") else ds["location"], w["date"], w["event"]))
    m = json.loads((_HERE / "vectors/multi_year_comparison_sprint13.json").read_text())["analysis"]["worst_10_waqt_vs_level_a"]
    matrix_cases = [case("Tromso", w["date"], w["event"]) for w in m[:5] if w["location"].startswith("Tromso")]
    ex = [existence("Tromso", e["date"], e["event"]) for ds in dense for e in ds["existence_disagreements"] if ds["location"] == "Tromso"]
    out = {"dense_worst_cases": cases, "matrix_worst_cases": matrix_cases, "existence_adjudication": ex}
    (_HERE / "vectors/worst_case_analysis_sprint13.json").write_text(json.dumps(out, indent=1) + "\n")
    for k, v in out.items():
        print("\n" + k)
        for c in v: print(" ", c)

if __name__ == "__main__":
    main()

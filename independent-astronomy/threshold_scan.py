#!/usr/bin/env python3
"""
independent-astronomy/threshold_scan.py — Sprint 11 threshold-band scan.

For a dense latitude x date grid across the polar-day/night onset windows,
compares defined-vs-undefined status of fajr/sunrise/asr/maghrib/isha among
the production engine, Level B and Level A, and classifies every
disagreement against physical truth (threshold_truth.py, sunrise/sunset
only -- twilight/asr have no single-threshold truth scan here and are
reported as "unclassified").

Writes vectors/threshold_scan_sprint11.json. Slow (~minutes: Level A is
~60 ms per day); not part of the unit-test suite -- tests/test_threshold_truth.py
covers the pinned cases and a small grid.
"""
from __future__ import annotations
import json, sys
from datetime import date, timedelta
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent)); sys.path.insert(0, str(_HERE))

from independent_solar import compute_day_events as B  # noqa: E402
from level_a.events import compute_day_events as A  # noqa: E402
from threshold_truth import crossing_exists  # noqa: E402
from waqt_core import solar  # noqa: E402

EVS = ["fajr", "sunrise", "asr", "maghrib", "isha"]
CONFIGS = [
    ("N lat, lon 18.96E, May-Jul", 18.9553, 1, date(2026, 5, 1), 3),
    ("N lat, lon 150W, May-Jul", -150.0, 1, date(2026, 5, 1), 6),
    ("N lat, lon 100E, Nov-Jan", 100.0, 1, date(2026, 11, 10), 6),
    ("S lat, lon 70W, Nov-Jan", -70.0, -1, date(2026, 11, 10), 6),
]

def main():
    out = {"configs": {}}
    for label, lon, sign, base, step in CONFIGS:
        tot = 0; dis = []
        for lat in [x / 2 for x in range(120, 171)]:
            la = sign * lat
            for k in range(0, 90, step):
                d = base + timedelta(days=k)
                w, b, a = solar.compute_day_events(d, la, lon), B(d, la, lon), A(d, la, lon)
                for e in EVS:
                    tot += 1
                    st = (getattr(w, e) is None, getattr(b, e) is None, getattr(a, e) is None)
                    if len(set(st)) == 1:
                        continue
                    rec = {"lat": la, "date": d.isoformat(), "event": e,
                           "undefined": {"waqt": st[0], "level_b": st[1], "level_a": st[2]}}
                    if e in ("sunrise", "maghrib"):
                        truth = crossing_exists(d, la, lon, e == "sunrise", solar.transit(d, la, lon))
                        rec["physical_crossing_exists"] = truth
                        rec["waqt_correct"] = (not st[0]) == truth
                        rec["references_correct"] = (not st[1]) == truth and (not st[2]) == truth
                    dis.append(rec)
        out["configs"][label] = {"lon": lon, "checked": tot, "disagreements": dis}
        (_HERE / "vectors" / "threshold_scan_sprint11.json").write_text(json.dumps(out, indent=1) + "\n")
        print(label, tot, len(dis), flush=True)

if __name__ == "__main__":
    main()

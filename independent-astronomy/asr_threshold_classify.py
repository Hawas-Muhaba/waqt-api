#!/usr/bin/env python3
"""Sprint 11: classify the Asr defined-vs-undefined disagreements found by
threshold_scan.py. Asr has no fixed horizon threshold: its target altitude
is atan(1/(shadow_ratio + tan|lat - decl|)) with decl at transit, which near
the polar threshold is nearly identical to the sun's midday PEAK altitude,
so the 'crossing' is a near-tangency. Reports margin = peak - asr_altitude
(degrees): margins below ~0.003 deg (~10 arcsec) are below the accuracy of
every engine here and the existence question is ill-conditioned."""
import json, math, sys
from datetime import date, timedelta
from pathlib import Path
_H = Path(__file__).resolve().parent
sys.path.insert(0, str(_H.parent)); sys.path.insert(0, str(_H))
from level_a.sun import apparent_position
from independent_solar.julian import julian_day
from independent_solar.deltat import delta_t_seconds
from threshold_truth import solar_altitude_deg
from waqt_core import solar

scan = json.loads((_H / "vectors" / "threshold_scan_sprint11.json").read_text())
rows = []
for label, cfg in scan["configs"].items():
    for r in cfg["disagreements"]:
        if r["event"] != "asr":
            continue
        lat, lon, d = r["lat"], cfg["lon"], date.fromisoformat(r["date"])
        tr = solar.transit(d, lat, lon)
        jd = julian_day(tr)
        dec = apparent_position(jd + delta_t_seconds(d) / 86400).declination_deg
        asr_alt = math.degrees(math.atan(1 / (1 + math.tan(math.radians(abs(lat - dec))))))
        peak = max(solar_altitude_deg(tr + timedelta(minutes=m), lat, lon) for m in range(-30, 31))
        w = solar.asr(d, lat, lon, 1.0)
        rows.append({"lat": lat, "date": r["date"], "lon": lon,
                     "asr_altitude_deg": round(asr_alt, 4), "peak_altitude_deg": round(peak, 4),
                     "margin_deg": round(peak - asr_alt, 4),
                     "ill_conditioned": abs(peak - asr_alt) < 0.003,
                     "waqt_asr_minus_transit_min": round((w - tr).total_seconds() / 60, 1) if w else None})
out = {"note": __doc__.strip(), "rows": rows}
(_H / "vectors" / "asr_threshold_classification_sprint11.json").write_text(json.dumps(out, indent=1) + "\n")
for x in rows: print(x)

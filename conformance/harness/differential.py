#!/usr/bin/env python3
"""Seeded differential run: random (place, date, instant) cases evaluated by two adapters and by the
JPL DE421 oracle, plus a high-latitude event-existence sweep.  Reproducible: --seed.

    python3 harness/differential.py --n 500 --seed 15

Outputs reports/differential-report.{md,json}.  Nothing here is a pass/fail gate; it is the search for
disagreements that the fixed vectors did not anticipate.
"""
import argparse, datetime as dt, json, os, random, subprocess, sys, warnings
from collections import Counter, defaultdict
from zoneinfo import ZoneInfo

warnings.filterwarnings("ignore")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "..", "independent-astronomy"))
# pyrefly: ignore [missing-import]
from skyfield_reference.events import compute_day_events  # noqa: E402

UTC = dt.timezone.utc
EV = ["fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha"]
PLACES = {
    "addis": (9.0192, 38.7525, "Africa/Addis_Ababa"), "makkah": (21.4225, 39.8262, "Asia/Riyadh"), "cairo": (30.0444, 31.2357, "Africa/Cairo"),
    "jakarta": (-6.2088, 106.8456, "Asia/Jakarta"), "quito": (-0.1807, -78.4678, "America/Guayaquil"), "london": (51.5074, -0.1278, "Europe/London"),
    "newyork": (40.7128, -74.0060, "America/New_York"), "sydney": (-33.8688, 151.2093, "Australia/Sydney"), "capetown": (-33.9249, 18.4241, "Africa/Johannesburg"),
    "punta-arenas": (-53.1638, -70.9171, "America/Punta_Arenas"), "reykjavik": (64.1466, -21.9426, "Atlantic/Reykjavik"), "oslo": (59.9139, 10.7522, "Europe/Oslo"),
    "kiritimati": (1.8721, -157.4278, "Pacific/Kiritimati"), "apia": (-13.8333, -171.7667, "Pacific/Apia"), "urumqi": (43.8256, 87.6168, "Asia/Urumqi"),
    "kathmandu": (27.7172, 85.3240, "Asia/Kathmandu"), "anchorage": (61.2181, -149.9003, "America/Anchorage"), "chatham": (-43.95, -176.55, "Pacific/Chatham"),
    "auckland": (-36.8485, 174.7633, "Pacific/Auckland"), "mumbai": (19.0760, 72.8777, "Asia/Kolkata"), "moscow": (55.7558, 37.6173, "Europe/Moscow"),
    "madrid": (40.4168, -3.7038, "Europe/Madrid"), "lagos": (6.5244, 3.3792, "Africa/Lagos"), "dhaka": (23.8103, 90.4125, "Asia/Dhaka"),
}


def run(cmd, cases):
    p = subprocess.run(cmd, input=json.dumps({"cases": cases}), capture_output=True, text=True, shell=True, cwd=ROOT, encoding="utf-8")
    return {r["id"]: r for r in json.loads(p.stdout)["results"]}


_c = {}


def listing(pid, k):
    if (pid, k) in _c:
        return _c[(pid, k)]
    lat, lon, tz = PLACES[pid]
    zi = ZoneInfo(tz)
    res = None
    for d in (k - dt.timedelta(days=1), k, k + dt.timedelta(days=1)):
        ev = compute_day_events(d, lat, lon, 0.0)
        if ev.dhuhr.astimezone(zi).date() == k:
            res = ev; break
    _c[(pid, k)] = res
    return res


def oracle(pid, t):
    zi = ZoneInfo(PLACES[pid][2])
    X = t.astimezone(zi).date()
    j = None
    for kk in range(1, -3, -1):
        k = X + dt.timedelta(days=kk)
        ev = listing(pid, k)
        if ev and ev.maghrib and ev.maghrib <= t:
            j = k; break
    if j is None:
        return None
    k = j + dt.timedelta(days=1)
    a, b = listing(pid, j), listing(pid, k)
    if not (a and b and a.maghrib and b.maghrib):
        return None
    return {"open": a.maghrib, "close": b.maghrib, "events": {n: getattr(b, n) for n in EV}, "label": b.maghrib.astimezone(zi).date()}


def iso(d):
    return d.astimezone(UTC).isoformat()


def p(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--seed", type=int, default=15)
    ap.add_argument("--ref", default="python3 adapters/reference_adapter.py")
    ap.add_argument("--ind", default="node independent/src/cli.mjs")
    a = ap.parse_args()
    rnd = random.Random(a.seed)
    cases, meta = [], {}
    for i in range(a.n):
        pid = rnd.choice(list(PLACES))
        lat, lon, tz = PLACES[pid]
        d = dt.date(2025, 1, 1) + dt.timedelta(days=rnd.randrange(0, 365 * 3))
        t = dt.datetime.combine(d, dt.time(0), tzinfo=UTC) + dt.timedelta(seconds=rnd.randrange(0, 86400))
        cid = f"r{i:04d}"
        cases.append({"id": cid, "op": "waqt.compute", "input": {"location": {"lat": lat, "lon": lon, "elevation_m": 0.0}, "instant": iso(t), "timezone": tz,
                                                                  "profile": {"fajr_angle_deg": 18.0, "isha_angle_deg": 17.0, "asr_shadow_ratio": 1.0}, "calendar": {"provider": "arithmetic-tabular"}}})
        meta[cid] = (pid, t)
    R, I = run(a.ref, cases), run(a.ind, cases)
    cats = defaultdict(list)
    err = {"reference": [], "independent": []}
    stats = {"reference": [], "independent": []}
    for c in cases:
        cid = c["id"]; pid, t = meta[cid]
        O = oracle(pid, t)
        for lab, res in (("reference", R[cid]), ("independent", I[cid])):
            if not res["ok"]:
                err[lab].append((cid, pid, res["error"]["code"])); continue
            o = res["output"]
            if O is None:
                if o["status"] == "OK":
                    cats[f"{lab}: day defined but oracle says undefined"].append((cid, pid, iso(t)))
                continue
            if o["status"] != "OK":
                cats[f"{lab}: UNDEFINED but oracle has a day"].append((cid, pid, iso(t))); continue
            e_open = abs((p(o["day"]["open"]) - O["open"]).total_seconds())
            e_close = abs((p(o["day"]["close"]) - O["close"]).total_seconds())
            stats[lab].append(max(e_open, e_close))
            if max(e_open, e_close) > 5:
                cats[f"{lab}: day boundary off by >5 s from DE421"].append((cid, pid, f"{max(e_open, e_close):.1f}s"))
            got = {e["name"]: p(e["instant"]) for e in o["events"]}
            for n in EV:
                want = O["events"][n]
                if (want is None) != (n not in got):
                    cats[f"{lab}: event existence differs from oracle ({n})"].append((cid, pid, f"oracle={'none' if want is None else 'yes'}"))
                elif want is not None:
                    lim = 5 if n in ("dhuhr", "asr", "sunrise", "maghrib") else 30
                    if abs((got[n] - want).total_seconds()) > lim:
                        cats[f"{lab}: {n} off by more than {lim} s"].append((cid, pid, f"{(got[n] - want).total_seconds():+.1f}s"))
            # label = civil date of closing Maghrib instant
            y = O["label"]
            import calendar as _c2
            want_wd = ["al-Ithnayn", "ath-Thulatha", "al-Arbiaa", "al-Khamis", "al-Jumuah", "as-Sabt", "al-Ahad"][y.weekday()]
            if o["weekday"] != want_wd:
                cats[f"{lab}: weekday label differs from civil date of closing Maghrib"].append((cid, pid, f"got {o['weekday']} want {want_wd}"))
    # ---- high-latitude existence sweep
    sweep = []
    for date in (dt.date(2026, 6, 21), dt.date(2026, 12, 21), dt.date(2026, 3, 20)):
        for lat in [x / 2 for x in range(90, 137)]:      # 45.0 .. 68.0
            sweep.append((date, lat))
    scases = []
    for date, lat in sweep:
        scases.append({"id": f"s{date}-{lat}", "op": "waqt.compute", "input": {"location": {"lat": lat, "lon": 0.0}, "instant": iso(dt.datetime.combine(date, dt.time(12), tzinfo=UTC)), "timezone": "UTC",
                       "profile": {"fajr_angle_deg": 18.0, "isha_angle_deg": 17.0, "asr_shadow_ratio": 1.0}, "calendar": {"provider": "arithmetic-tabular"}}})
    SR, SI = run(a.ref, scases), run(a.ind, scases)
    swdiff = []
    first_missing = {}
    for (date, lat), c in zip(sweep, scases):
        t = dt.datetime.combine(date, dt.time(12), tzinfo=UTC)
        lat_, lon_, tz = 0, 0, "UTC"
        PLACES["_sweep"] = (lat, 0.0, "UTC"); _c.clear()
        O = oracle("_sweep", t)
        want = None if O is None else frozenset(n for n in EV if O["events"][n] is not None)
        row = {"date": str(date), "lat": lat, "oracle": None if want is None else sorted(want)}
        for lab, S in (("reference", SR), ("independent", SI)):
            r = S[c["id"]]
            if not r["ok"]:
                row[lab] = "error"; continue
            o = r["output"]
            row[lab] = None if o["status"] != "OK" else sorted(e["name"] for e in o["events"])
        row["agree"] = {k: (row[k] == row["oracle"]) for k in ("reference", "independent")}
        sweep_row = row
        swdiff.append(row)
    bad = [r for r in swdiff if not all(r["agree"].values())]

    def pct(xs, q):
        xs = sorted(xs); return xs[int(q * (len(xs) - 1))] if xs else None
    out = {"seed": a.seed, "n": a.n, "errors": err, "categories": {k: v for k, v in cats.items()},
           "boundary_error_seconds": {lab: {"n": len(v), "median": pct(v, .5), "p95": pct(v, .95), "max": max(v) if v else None} for lab, v in stats.items()},
           "sweep_total": len(swdiff), "sweep_disagreements": bad}
    json.dump(out, open(os.path.join(ROOT, "reports", "differential-report.json"), "w", encoding="utf-8"), indent=1)
    L = [f"# Differential run (seed {a.seed}, {a.n} random cases + {len(swdiff)}-point latitude sweep)\n",
         "Truth source: JPL DE421 via Skyfield. Cases drawn uniformly from 24 places x 3 years x all times of day.\n",
         "## Day-boundary error vs DE421 (|open|,|close| worst of the two, seconds)\n", "| implementation | n | median | p95 | max |", "|---|---|---|---|---|"]
    for lab, v in out["boundary_error_seconds"].items():
        L.append(f"| {lab} | {v['n']} | {v['median']:.2f} | {v['p95']:.2f} | {v['max']:.2f} |")
    L.append("\n## Disagreements with the oracle\n")
    if not cats:
        L.append("None.\n")
    for k, v in sorted(cats.items()):
        L.append(f"- **{k}**: {len(v)} case(s); e.g. " + "; ".join(f"{x[0]} {x[1]} {x[2]}" for x in v[:3]))
    for lab, v in err.items():
        if v:
            L.append(f"- **{lab} returned errors** on {len(v)} case(s): " + ", ".join(sorted({x[2] for x in v})))
    L.append(f"\n## High-latitude existence sweep (lon 0, 3 dates, 45.0-68.0 deg N, step 0.5): {len(bad)} of {len(swdiff)} points where at least one implementation's set of defined events differs from the oracle\n")
    L.append("| date | lat | oracle events | reference | independent |")
    L.append("|---|---|---|---|---|")
    for r in bad:
        f = lambda x: "UNDEFINED day" if x is None else ",".join(x) if x != "error" else "error"
        L.append(f"| {r['date']} | {r['lat']} | {f(r['oracle'])} | {f(r['reference'])}{'' if r['agree']['reference'] else ' ✗'} | {f(r['independent'])}{'' if r['agree']['independent'] else ' ✗'} |")
    open(os.path.join(ROOT, "reports", "differential-report.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L[:30]))


if __name__ == "__main__":
    main()

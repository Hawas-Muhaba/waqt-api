#!/usr/bin/env python3
"""Adopt the Sprint 5-8 vector files into the portable COP vector format.
Expected values are the legacy ones, unchanged; only the envelope is new."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "..", "tests", "vectors")
OUT = os.path.join(HERE, "..", "vectors")

ZONES = [((9.0, 38.7), "Africa/Addis_Ababa"), ((21.4, 39.8), "Asia/Riyadh"), ((51.5, -0.13), "Europe/London"),
         ((69.6, 18.9), "Europe/Oslo"), ((1.87, -157.4), "Pacific/Kiritimati"), ((27.5, 95.0), "Asia/Kolkata")]


def zone_of(loc):
    for (la, lo), z in ZONES:
        if abs(loc["lat"] - la) < 0.6 and abs(loc["lon"] - lo) < 0.6:
            return z
    raise KeyError(loc)


def load(n):
    return json.load(open(os.path.join(SRC, n)))


def save(name, tier, desc, vectors, mm=None):
    d = {"suite": name, "tier": tier, "description": desc, "vectors": vectors}
    if mm:
        d["metamorphic"] = mm
    json.dump(d, open(os.path.join(OUT, name + ".json"), "w"), indent=1)
    print(f"{name}: {len(vectors)} vectors")


SCH_REQ = {"points": ["SCH-001"], "windows": ["SCH-002"], "evaluate": ["SCH-002"], "deadlines": ["SCH-003"], "undefined": ["SCH-004"],
           "spans": ["SCH-005"], "positions": ["SCH-006"], "until-since": ["SCH-006", "SCH-003"], "profile-asr": ["SCH-001", "EVT-005"],
           "calendar-substitution": ["CAL-010", "SCH-001"]}


def scheduling():
    vs = []
    for v in load("scheduling_vectors.json")["vectors"]:
        reqs = list(SCH_REQ[v["group"]])
        if "microsecond" in v["id"] or "fractional" in v["id"] or "rounding" in v["id"]:
            reqs.append("SCH-007")
        vs.append({"id": "sch-table/" + v["id"], "requirements": reqs, "op": "schedule.run", "tier": "exact",
                   "input": {"context": v["context"], "anchor": v["anchor"], "operation": v["operation"]},
                   "expect": {"output": v["expected"]}, "ignore": ["description", "reason"], "note": v["description"]})
    save("legacy-scheduling", "exact", "Sprint 6 scheduling vectors (frozen day tables), adopted verbatim.", vs)


def institutional():
    vs = []
    GR = {"rules": "INS-001", "week": "INS-002", "fiscal_year": "INS-003", "academic_year": "INS-004"}
    for v in load("institutional_vectors.json")["vectors"]:
        r = [GR[v["group"]]]
        vs.append({"id": "ins/" + v["id"], "requirements": r, "op": "institutional.run", "tier": "exact",
                   "input": {"operation": v["operation"], "context": v["context"]}, "expect": {"output": v["expected"]}, "note": v["description"]})
        prov = v["context"].get("calendar_provider")
        if prov:   # same vector, but the implementation must compute the calendar itself
            ctx = {k: x for k, x in v["context"].items() if k != "month_table"}
            vs.append({"id": "ins/" + v["id"] + "/computed", "requirements": r + ["CAL-001" if prov == "arithmetic-tabular" else "CAL-007"],
                       "op": "institutional.run", "tier": "exact" if prov == "arithmetic-tabular" else "informative",
                       "input": {"operation": v["operation"], "context": ctx}, "expect": {"output": v["expected"]},
                       "note": "no month_table supplied: the implementation computes its own calendar. " + v["description"]})
    save("legacy-institutional", "exact", "Sprint 7 institutional vectors; each is run with a frozen month table and again with the calendar computed.", vs)


def waqt():
    d = load("waqt_vectors.json")
    BOUNDARY = {"addis-exact-maghrib-boundary", "addis-one-second-before-maghrib", "london-long-day-near-24h-boundary"}
    vs = []
    for v in d["vectors"]:
        i, e = v["input"], v["expected"]
        inp = {"location": i["location"], "instant": i["instant"], "timezone": zone_of(i["location"]),
               "profile": i["astronomy_profile"], "calendar": {"provider": i["calendar_provider"]}}
        out = {"status": e["status"]}
        reqs = ["DAY-001", "EVT-001"]
        if e["status"] == "OK":
            out.update({"hijri": {"date": e["hijri_date"]}, "weekday": e["weekday"],
                        "day": {"open": e["day"]["maghrib_open"], "close": e["day"]["maghrib_close"], "length_seconds": e["day"]["length_si_seconds"]},
                        "position": {"seconds": e["waqt_position"]["total_seconds"]},
                        "events": [{"name": n, "instant": x["instant"], "reading_seconds": x["position_total_seconds"]} for n, x in e["events"].items()]})
            reqs += ["DAY-004", "DAY-005", "EVT-002"]
        else:
            reqs += ["UND-001"]
        tol = {"default": {"instant_s": 3, "abs": 3}}
        tier = "tolerance"
        if v["id"] == "kiritimati-date-line":   # the frozen label (04-06 / as-Sabt) is the disputed one; see day-model label/* vectors
            out.pop("hijri", None); out.pop("weekday", None)
            v = dict(v, description=v["description"] + " [label fields removed: disputed, see DIS-001 and the label/* vectors]")
        note = v["description"]
        if v["id"] in BOUNDARY:
            tier = "informative"
            note += " [boundary-sensitive: instants placed at the REFERENCE's Maghrib cannot be compared across engines; see metamorphic DAY-002/003 instead]"
        vs.append({"id": "waqt/" + v["id"], "requirements": reqs, "op": "waqt.compute", "tier": tier, "input": inp,
                   "expect": {"output": out}, "tolerance": tol, "ignore": ["display"], "note": note})
    save("legacy-waqt", "tolerance", "Sprint 5 vectors as live computations (tolerance 3 s: the reference is ~1 s from DE421).", vs)


def interop():
    d = load("calendar_interop_vectors.json")
    vs = []
    SENS = {"exact-maghrib", "one-second-before-maghrib", "one-second-after-maghrib", "starts-exactly-at-maghrib", "ends-exactly-at-maghrib"}
    for v in d["instant_representation"]:
        c = v["context"]
        if "timezone_name" not in c:
            continue   # the provider-swap vector is covered by metamorphic CAL-010
        e = v["expected"]
        exp = {k: e[k] for k in ("gregorian_utc", "gregorian_civil", "waqt_status") if k in e}
        if "waqt_position_seconds" in e:
            exp["waqt_position_seconds"] = e["waqt_position_seconds"]
        sens = v["id"] in SENS
        vs.append({"id": "interop/instant/" + v["id"], "requirements": ["INT-001", "DAY-007"], "op": "calendar.represent_instant",
                   "tier": "informative" if sens else "tolerance",
                   "input": {"instant": v["instant"], "location": c["location"], "timezone": c["timezone_name"]},
                   "expect": {"output": exp}, "tolerance": {"default": {"instant_s": 3, "abs": 3}},
                   "note": v["description"] + (" [boundary-sensitive]" if sens else "")})
    for v in d["gregorian_date_to_waqt_day"]:
        c = v["context"]
        vs.append({"id": "interop/date/" + v["id"], "requirements": ["INT-002"], "op": "calendar.gregorian_date_to_waqt_day", "tier": "exact",
                   "input": {"date": v["date"], "location": c["location"], "timezone": zone_of(c["location"])},
                   "expect": {"output": {"resolved": v["expected"]["resolved"], "close_civil_date": v["expected"]["close_civil_date"]}}, "note": v["description"]})
    for v in d["boundary_crossing"]:
        c = v["context"]
        sens = v["id"] in SENS
        vs.append({"id": "interop/boundary/" + v["id"], "requirements": ["INT-003"], "op": "calendar.boundary_crossing",
                   "tier": "informative" if sens else "exact",
                   "input": {"start": v["start"], "end": v["end"], "location": c["location"], "timezone": zone_of(c["location"])},
                   "expect": {"output": {k: v["expected"][k] for k in ("crosses_civil_midnight", "crosses_maghrib", "start_civil_date", "end_civil_date")}},
                   "note": v["description"] + (" [boundary-sensitive]" if sens else "")})
    save("legacy-interop", "exact", "Sprint 8 calendar-interop vectors recomputed from coordinates.", vs)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    scheduling(); institutional(); waqt(); interop()

#!/usr/bin/env python3
"""Sprint 16 -- migrate the conformance contract from 1.0.0 (Sprint 15) to 2.0.0.

WHY A SCRIPT: `build_vectors.py` regenerates vectors from the reference adapter, which needs FastAPI and
PyEphem. Editing vector JSON by hand leaves no audit trail. This script IS the audit trail: every change to a
requirement, vector or tier made for contract 2.0.0 is written here, with the decision record (conformance/
decisions/DR-*.md) that justifies it. It is idempotent -- running it twice changes nothing the second time.

After this release `requirements.json` and `vectors/*.json` are edited only through the change process in
GOVERNANCE.md, and every edit is recorded in CHANGELOG.md. This script is not re-run in future sprints.

    python3 tools/migrate_contract_2_0.py            # apply
    python3 tools/migrate_contract_2_0.py --check    # exit 1 if anything would still change
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

CONF = Path(__file__).resolve().parent.parent
V = CONF / "vectors"
CONTRACT = "2.0.0"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def save(p, obj):
    Path(p).write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def vec(d, vid):
    return next(v for v in d["vectors"] if v["id"] == vid)


def main(check: bool) -> int:
    before = {p.name: p.read_bytes() for p in list(V.glob("*.json")) + [CONF / "spec" / "requirements.json", CONF / "baselines" / "known-failures.json"]}

    # ------------------------------------------------------------------ requirements
    rp = CONF / "spec" / "requirements.json"
    req = load(rp)
    req["cop_version"] = "1.1"
    req["contract_version"] = CONTRACT
    by = {r["id"]: r for r in req["requirements"]}
    for r in req["requirements"]:
        r.setdefault("since", "1.0.0")
        r["status"] = "normative" if r["kind"] == "MUST" else "open"

    def promote(rid, title, decision, section=None):
        r = by[rid]
        r.update(kind="MUST", status="normative", title=title, decision=decision, changed="2.0.0")
        if section:
            r["section"] = section

    promote("EVT-007", "waqt.compute next_event is the next event by OCCURRENCE: the earliest event strictly after the instant, "
            "including the previous solar day's Isha (never only the listed events)", "DR-0003", "SCHEDULING 5; API")
    promote("CAL-002", "arithmetic-tabular leap years are the positions 2,5,7,10,13,16,18,21,24,26,29 of the 30-year cycle "
            "((11*y+14) mod 30 < 11); a different pattern is a different provider, never a substitution", "DR-0005", "CALENDARS 2")
    promote("CAL-004", "A Hijri date that does not exist is rejected, never normalised: year < 1, or a day beyond the month's length in that "
            "provider, is INVALID_HIJRI_DATE (out-of-range month/day numerals MAY be VALIDATION_ERROR)", "DR-0006", "CALENDARS 2; API errors")
    promote("CAL-011", "umm-al-qura is supported for 1700-01-01..2300-12-31 only; outside it the provider refuses with OUT_OF_RANGE", "DR-0007", "CALENDARS 3")
    promote("ERR-002", "An unknown IANA time zone is rejected with UNKNOWN_TIMEZONE (a client error, never INTERNAL_ERROR)", "DR-0006", "API errors")
    by["DAY-004"].update(
        title="The day label (Hijri date, weekday) is that of the civil date, in the location's IANA zone, on which the CLOSING Maghrib INSTANT falls",
        decision="DR-0001", changed="2.0.0", section="SEMANTICS 3; TIME-MODEL")
    by["EVT-004"].update(
        title="An event belongs to the Waqt day around its own upper transit, even after local midnight; the event listing never moves to the next civil date",
        decision="DR-0002", changed="2.0.0")
    by["DAY-007"]["decision"] = "DR-0001"
    by["UND-001"]["decision"] = "DR-0002"
    by["UND-001"]["title"] = ("Polar day/night (no Maghrib): status UNDEFINED with a reason, never a guessed time; a day with exactly ONE "
                              "undefined bounding Maghrib is wholly UNDEFINED")
    by["UND-001"]["changed"] = "2.0.0"
    by["UND-004"].update(
        title="Existence of GRAZING events (Sun within arc-minutes of a threshold): unresolved, scan strategy is implementation-defined",
        decision="OQ-UND-1")
    by["CAL-007"].update(
        title="umm-al-qura month boundaries away from the validated anchors: UNRESOLVED BY DESIGN (institutional convention; see OQ-UAQ-2)",
        decision="OQ-UAQ-2")
    by["PRV-007"]["decision"] = "OQ-PRV-1..3"
    by["TIME-002"]["decision"] = "OQ-TIME-1"

    def add(rid, title, section, decision):
        r = by.get(rid)
        if r is None:
            r = {"id": rid, "kind": "MUST", "since": "2.0.0"}
            req["requirements"].append(r)
            by[rid] = r
        r.update(title=title, section=section, status="normative", decision=decision)

    add("AST-001", "The Asr target altitude uses the Sun's declination at the UPPER TRANSIT of the date (the noon shadow); the crossing instant is then solved "
        "with the Sun's position at the crossing", "ASTRONOMY (Asr)", "DR-0004")
    add("AST-002", "Asr is undefined (omitted, UND-002) exactly when the Sun's geometric altitude at upper transit is <= 0 deg", "ASTRONOMY (Asr)", "DR-0004")
    add("DAY-009", "Labels follow DAY-004 even where it makes them non-injective: a civil date with NO closing Maghrib resolves to nothing "
        "(resolved=false), a civil date with TWO resolves to the day containing its local noon; labels never decrease", "SEMANTICS 3 (consequences)", "DR-0001")
    add("SCH-009", 'next_event/prev_event points carry `inclusive` (default true): at an instant exactly equal to an event, inclusive resolves to that event, exclusive to the next (prev: previous) one', "SCHEDULING 3", "DR-0008")
    add("SCH-010", 'event_position default slot: isha and maghrib resolve in the PREVIOUS listing, every other event in day 0; the result reports `listed` and `containing` positions', "SCHEDULING 3", "DR-0008")
    add("SCH-011", 'An empty or inverted window/span is status NO_VALID_WINDOW with duration_seconds null; WINDOW_UNDEFINED reports maghrib_boundaries as []', "SCHEDULING 4, 7", "DR-0008")
    add("SCH-012", 'A strict resolution (default) that meets an undefined event slot ends as EVENT_UNDEFINED / EVENT_UNDEFINED_ON_DAY naming it in undefined_ref; with on_undefined=skip the slot is listed in `skipped` and the scan continues over at most 8 day-slots, ending NO_OCCURRENCE_IN_RANGE if none is found', "SCHEDULING 6", "DR-0008")
    add("SCH-013", "An event point at a day offset whose Waqt day, or a day stepped across to reach it, has an undefined bounding Maghrib is EVENT_UNDEFINED with cause DAY_UNDEFINED, even when the target lies outside the context's day table", "SCHEDULING 6", "DR-0008")
    req["requirements"].sort(key=lambda r: (r["id"].split("-")[0], int(r["id"].split("-")[1])))
    save(rp, req)

    # ------------------------------------------------------------------ calendar-core
    cp = V / "calendar-core.json"
    cc = load(cp)
    for v in cc["vectors"]:
        if v["id"].startswith("tab/month12-length/"):
            v["tier"] = "exact"
            v["note"] = ("Normative since contract 2.0.0 (DR-0005): leap years are positions 2,5,7,10,13,16,18,21,24,26,29 of the 30-year cycle. "
                         "A different published pattern is a different provider.")
    for vid in ("tab/invalid/1448-2-30", "tab/invalid/0-1-1"):
        vec(cc, vid)["expect"] = {"error": {"code": ["INVALID_HIJRI_DATE"]}}
    for vid in ("tab/invalid/1448-13-1", "tab/invalid/1448-0-1", "tab/invalid/1448-1-31", "tab/invalid/1448-1-0", "tab/invalid/1448-4-0"):
        vec(cc, vid)["expect"] = {"error": {"code": ["INVALID_HIJRI_DATE", "VALIDATION_ERROR"]}}
        sentence = " Out-of-range numerals MAY be rejected earlier as VALIDATION_ERROR (CAL-004)."
        base = (vec(cc, vid).get("note") or "").replace(sentence, "").strip()
        vec(cc, vid)["note"] = base + sentence
    tmpl = vec(cc, "tab/invalid/1448-2-30")
    have = {v["id"] for v in cc["vectors"]}
    for vid, y, m, dd, why in (
        ("tab/invalid/1448-12-30", 1448, 12, 30, "1448 is not a leap year, so Dhu al-Hijjah has 29 days (DR-0005)."),
        ("tab/invalid/-1-1-1", -1, 1, 1, "There is no year zero and no negative year: the tabular domain starts at 1 AH (DR-0006)."),
    ):
        if vid not in have:
            n = json.loads(json.dumps(tmpl))
            n.update(id=vid, note=why)
            n["input"] = {"year": y, "month": m, "day": dd, "provider": "arithmetic-tabular"}
            cc["vectors"].append(n)
    save(cp, cc)

    # ------------------------------------------------------------------ errors
    ep = V / "errors.json"
    ee = load(ep)
    vec(ee, "err/tz-unknown")["expect"] = {"error": {"code": ["UNKNOWN_TIMEZONE"]}}
    vec(ee, "err/tz-unknown")["note"] = "Contract 2.0.0 (DR-0006): UNKNOWN_TIMEZONE only. Before 2.0.0 VALIDATION_ERROR was also accepted."
    if "err/tz-malformed" not in {v["id"] for v in ee["vectors"]}:
        n = json.loads(json.dumps(vec(ee, "err/tz-unknown")))
        n["id"] = "err/tz-malformed"
        n["input"]["timezone"] = "../etc/passwd"
        n["note"] = "A path-like zone name is an unknown zone, not a file lookup and not a server fault."
        ee["vectors"].append(n)
    save(ep, ee)

    # ------------------------------------------------------------------ open-questions -> resolved suites
    op_ = V / "open-questions.json"
    oq = load(op_)
    moved = {"next-event/tonights-isha": ("day-model", ["EVT-007"]), "asr/degenerate-67N-solstice": ("day-model", ["AST-002"])}
    for rid in ("uaq/range/1650-01-01", "uaq/range/1699-12-31", "uaq/range/2301-01-01", "uaq/range/2500-01-01"):
        moved[rid] = ("calendar-uaq", ["CAL-011"])
    targets = {"day-model": load(V / "day-model.json"), "calendar-uaq": load(V / "calendar-uaq.json")}
    for vid, (suite, reqs) in moved.items():
        src = [v for v in oq["vectors"] if v["id"] == vid]
        if not src:
            continue
        v = src[0]
        oq["vectors"].remove(v)
        v["tier"] = "exact" if not vid.startswith("next-event") else "tolerance"
        v["requirements"] = reqs
        v["basis"] = "spec"
        v["note"] = (v.get("note") or "").replace("PROPOSED:", "RULED (contract 2.0.0):") + " Promoted from open-questions in contract 2.0.0."
        if vid.startswith("uaq/range"):
            v["expect"] = {"error": {"code": ["OUT_OF_RANGE"]}}
            v["note"] = "umm-al-qura is supported for 1700-01-01..2300-12-31 only (DR-0007). Before 2.0.0 the reference answered for 1650..2300."
        targets[suite]["vectors"].append(v)
    if "uaq/range/1700-01-01" not in {v["id"] for v in targets["calendar-uaq"]["vectors"]}:
        tpl = [v for v in targets["calendar-uaq"]["vectors"] if v["id"] == "uaq/range/1650-01-01"][0]
        for vid, dt, hij in (("uaq/range/1700-01-01", "1700-01-01", "1111-07-11"), ("uaq/range/2300-12-31", "2300-12-31", "1730-12-19")):
            n = json.loads(json.dumps(tpl))
            n.update(id=vid, tier="informative", basis="recorded")
            n["input"]["date"] = dt
            n["expect"] = {"output": {"date": hij}}
            n["note"] = "Boundary of the supported range (DR-0007): must answer. Value recorded from the independent implementation; informative because month starts away from anchors are CAL-007 (unresolved)."
            targets["calendar-uaq"]["vectors"].append(n)
    for k, t in targets.items():
        save(V / f"{k}.json", t)
    save(op_, oq)

    # ------------------------------------------------------------------ day-model: DAY-009 + AST-001 tags
    dm = load(V / "day-model.json")
    for v in dm["vectors"]:
        if v["op"] == "waqt.compute" and any(e.get("name") == "asr" for e in v.get("expect", {}).get("output", {}).get("events", [])):
            if "AST-001" not in v["requirements"]:
                v["requirements"].append("AST-001")
    have = {v["id"] for v in dm["vectors"]}
    loc = {"lat": 64.1466, "lon": -21.9426}
    if "label/skip/reykjavik/2026-06-15" not in have:
        dm["vectors"].append({
            "id": "label/skip/reykjavik/2026-06-15", "requirements": ["DAY-004", "DAY-009"], "op": "calendar.gregorian_date_to_waqt_day",
            "tier": "exact", "basis": "spec", "input": {"date": "2026-06-15", "location": loc, "timezone": "Atlantic/Reykjavik"},
            "expect": {"output": {"resolved": False}},
            "note": "Maghrib closes the previous day at 23:58:53 on 14 June and the next at 00:00:09 on 16 June: NO Waqt day closes on civil date 2026-06-15, "
                    "so that date resolves to nothing (DR-0001). The `reason` text is not normative."})
    if "label/repeat/reykjavik/2026-06-29" not in have:
        dm["vectors"].append({
            "id": "label/repeat/reykjavik/2026-06-29", "requirements": ["DAY-004", "DAY-009"], "op": "calendar.gregorian_date_to_waqt_day",
            "tier": "tolerance", "basis": "spec", "input": {"date": "2026-06-29", "location": loc, "timezone": "Atlantic/Reykjavik"},
            "expect": {"output": {"resolved": True, "close_civil_date": "2026-06-29", "hijri_date": "1448-01-13", "weekday": "al-Ithnayn",
                                  "open": "2026-06-29T00:00:16+00:00", "close": "2026-06-29T23:59:04+00:00"}},
            "tolerance": {"default": {"instant_s": 5, "abs": 5}},
            "note": "TWO Waqt days close on 2026-06-29 (00:00:16 and 23:59:04). The date resolves to the one containing the date's local noon, the later (DR-0001)."})
    save(V / "day-model.json", dm)

    # ------------------------------------------------------------------ scheduling requirement tags (rules that lived only in vectors)
    ls = load(V / "legacy-scheduling.json")
    tags = {
        "SCH-009": ["sch-table/point-next-maghrib-at-exact-maghrib-inclusive", "sch-table/point-next-maghrib-at-exact-maghrib-exclusive", "sch-table/point-prev-maghrib-at-exact-maghrib-inclusive"],
        "SCH-010": ["sch-table/event-position-isha-next", "sch-table/event-position-isha-listed-day-0", "sch-table/event-position-fajr", "sch-table/event-position-maghrib", "sch-table/undef-london-event-position-fajr"],
        "SCH-011": ["sch-table/window-inverted-is-no-valid-window", "sch-table/window-empty-half-open-is-no-valid-window", "sch-table/span-inverted-no-valid-window", "sch-table/span-empty-half-open-no-valid-window", "sch-table/undef-tromso-span-into-undefined-day"],
        "SCH-012": ["sch-table/undef-london-strict-until-fajr", "sch-table/undef-london-skip-until-fajr-finds-nothing", "sch-table/undef-london-strict-until-fajr-late-july", "sch-table/undef-london-skip-until-fajr-late-july", "sch-table/undef-london-next-event-lists-undefined"],
        "SCH-013": ["sch-table/undef-tromso-step-into-undefined-day", "sch-table/undef-tromso-step-across-undefined-day"],
    }
    ids = {v["id"] for v in ls["vectors"]}
    for rid, vids in tags.items():
        for vid in vids:
            if vid in ids and rid not in vec(ls, vid)["requirements"]:
                vec(ls, vid)["requirements"].append(rid)
    # DIS-001 resolved: restore the label fields that Sprint 15 had to remove from the frozen Kiritimati vector.
    k = vec(load(V / "legacy-waqt.json"), "waqt/kiritimati-date-line")
    lw = load(V / "legacy-waqt.json")
    k = vec(lw, "waqt/kiritimati-date-line")
    k["expect"]["output"]["hijri"] = {"date": "1448-04-07"}
    k["expect"]["output"]["weekday"] = "al-Ahad"
    k["note"] = ("Kiritimati, Kiribati: civil offset UTC+14 is ~24.5h from natural solar time -- the hardest real-world date-line case. "
                 "Label restored in contract 2.0.0 (DIS-001 resolved, DR-0001): the day closes on civil 2026-09-20, an al-Ahad, 1448-04-07. "
                 "The frozen Sprint 5 value (1448-04-06 / as-Sabt) was the defect.")
    save(V / "legacy-waqt.json", lw)
    save(V / "legacy-scheduling.json", ls)

    # ------------------------------------------------------------------ baselines
    kp = CONF / "baselines" / "known-failures.json"
    kf = load(kp)
    kf["cop_version"] = "1.1"
    kf["contract_version"] = CONTRACT
    kf["description"] = ("Normative conformance failures of the REFERENCE. Empty at contract 2.0.0: DIS-001, DIS-002 and DIS-003 were resolved in Sprint 16. "
                         "Every future entry must be explained in DISAGREEMENTS.md and carry a decision record (GOVERNANCE.md 5).")
    kf["reference"] = {"vectors": [], "metamorphic": []}
    kf["independent"] = []
    save(kp, kf)

    after = {p.name: p.read_bytes() for p in list(V.glob("*.json")) + [rp, kp]}
    changed = sorted(k for k in after if before.get(k) != after[k])
    print("changed:", changed if changed else "nothing (already migrated)")
    if check:
        return 1 if changed else 0
    return 0


if __name__ == "__main__":
    sys.exit(main("--check" in sys.argv))

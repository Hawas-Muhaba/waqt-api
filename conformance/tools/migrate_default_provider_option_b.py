#!/usr/bin/env python3
"""Audit trail for contract 2.0.0 (draft) amendment CCP-0001 / DR-0010: the default Hijri provider is `umm-al-qura`.

    python3 tools/migrate_default_provider_option_b.py        (idempotent; run from conformance/)

1. spec/requirements.json: adds CAL-012 (MUST): an omitted provider means umm-al-qura; an explicit provider is honoured.
2. vectors/day-model.json: the three NORMATIVE label vectors that omitted the provider only asserted a provider-independent rule
   (DAY-004: the label is the provider's date of the closing civil date). Their EXPECTED VALUES are arithmetic-tabular's and are
   NOT changed; the provider they always meant is now stated in the input. No expected value of any vector changes.
3. spec/COP.md: states the rule; spec/open-questions.json + vectors/open-questions.json: OQ-CAL-1 (what the other operations do for an
   omitted provider outside umm-al-qura's range: the two implementations DISAGREE and the contract does not decide).
4. vectors/calendar-default.json (new suite): CAL-012 vectors. Every expected value is copied from an existing normative
   Umm al-Qura vector (official new-year dates) with the provider OMITTED, plus two label vectors on 1 Muharram 1447.
"""
import json
from pathlib import Path

CONF = Path(__file__).resolve().parent.parent
PIN = {"label/date-to-waqt-day/kiritimati/2026-09-20", "label/date-to-waqt-day/addis/2026-09-20", "label/repeat/reykjavik/2026-06-29"}


def load(p):
    return json.loads(p.read_text(encoding="utf-8"))


def save(p, o):
    p.write_text(json.dumps(o, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


COP_RULE = """### Default calendar provider (CAL-012)
Every `provider` (or `calendar.provider`, `calendar_provider`) input is **optional**. When it is omitted the provider is **`umm-al-qura`**; an explicitly named provider is always honoured, and an unknown name is still `UNKNOWN_CALENDAR_PROVIDER`. The default labels days only: it never changes a Waqt day, an event instant, a position or a countdown. It is a deliberate project default (DR-0010), not a claim that every community follows one calendar convention, which is why every other provider stays selectable. (Before contract 2.0.0 the COP left the default unspecified and both adapters used `arithmetic-tabular`.) Vectors that assert a Hijri value under a provider other than the default must name it.
Outside `umm-al-qura`'s 1700-01-01..2300-12-31 (CAL-011), `hijri.*` operations that omit the provider return `OUT_OF_RANGE`. What the *other* operations (`waqt.compute`, `calendar.*`) must do there is **not yet specified** (open question OQ-CAL-1): the reference returns the Waqt day with an empty Hijri label, the independent implementation returns `OUT_OF_RANGE`.

"""


def cop():
    p = CONF / "spec" / "COP.md"; s = p.read_text(encoding="utf-8")
    if "### Default calendar provider (CAL-012)" in s:
        return
    a = "### `hijri.from_gregorian`"
    assert s.count(a) == 1
    s = s.replace(a, COP_RULE + a, 1)
    for old, new in (("`{date, provider, params?}`", "`{date, provider?, params?}`"), ("`{year, month, day, provider}`", "`{year, month, day, provider?}`"),
                     ("`{year, month, provider}`", "`{year, month, provider?}`"), ("`{year, provider}`", "`{year, provider?}`")):
        s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")


def oq():
    p = CONF / "spec" / "open-questions.json"; q = load(p)
    if not any(x["id"] == "OQ-CAL-1" for x in q["questions"]):
        q["questions"].append({"id": "OQ-CAL-1", "topic": "Omitted provider (umm-al-qura) outside 1700..2300: must waqt.compute / calendar.* refuse with OUT_OF_RANGE, or return the Waqt day with an empty Hijri label?",
                               "status": "deferred", "requirement": "CAL-012", "decision": None})
        save(p, q)
    vp = CONF / "vectors" / "open-questions.json"; v = load(vp)
    loc, tz = {"lat": 9.0192, "lon": 38.7525}, "Africa/Addis_Ababa"
    prof = {"fajr_angle_deg": 18.0, "isha_angle_deg": 17.0, "asr_shadow_ratio": 1.0}
    new = [{"id": "default/out-of-range/date-to-waqt-day/addis/1699-09-19", "requirements": ["CAL-012"], "op": "calendar.gregorian_date_to_waqt_day", "tier": "open", "basis": "spec",
            "input": {"date": "1699-09-19", "location": loc, "timezone": tz}, "expect": {"output": {"resolved": True, "hijri_date": None}},
            "note": "PROPOSED: the Waqt day is returned with an empty Hijri label (a calendar failure never fails a Waqt computation; API 1.5.0 calendar_error). The reference does this; the independent implementation returns OUT_OF_RANGE. OQ-CAL-1."},
           {"id": "default/out-of-range/compute/addis/1699-09-19", "requirements": ["CAL-012"], "op": "waqt.compute", "tier": "open", "basis": "spec",
            "input": {"location": loc, "instant": "1699-09-19T15:42:00+00:00", "timezone": tz, "profile": prof}, "expect": {"output": {"status": "OK"}},
            "note": "PROPOSED: status OK with an empty Hijri label. The reference does this; the independent implementation returns OUT_OF_RANGE. OQ-CAL-1."}]
    have = {x["id"] for x in v["vectors"]}
    v["vectors"] += [x for x in new if x["id"] not in have]
    save(vp, v)


def main():
    cop(); oq()
    # 1. requirement
    rp = CONF / "spec" / "requirements.json"; r = load(rp)
    if not any(x["id"] == "CAL-012" for x in r["requirements"]):
        i = next(k for k, x in enumerate(r["requirements"]) if x["id"] == "CAL-011")
        r["requirements"].insert(i + 1, {"id": "CAL-012", "kind": "MUST",
            "title": "When a request names no calendar provider, the provider is umm-al-qura; an explicitly named provider is always honoured (the default changes Hijri labels only, never a Waqt instant)",
            "section": "COP 4; API 1.7.0", "since": "2.0.0", "status": "normative", "decision": "DR-0010", "changed": "2.0.0"})
        save(rp, r)
    # 2. pin
    dp = CONF / "vectors" / "day-model.json"; d = load(dp); n = 0
    for v in d["vectors"]:
        if v["id"] in PIN and "calendar" not in v["input"] and "provider" not in v["input"]:
            v["input"]["calendar"] = {"provider": "arithmetic-tabular"}
            v["note"] = v.get("note", "") + " [Provider pinned to arithmetic-tabular (CCP-0001): the rule is provider-independent and the expected label is arithmetic-tabular's; the default is now umm-al-qura, CAL-012.]"
            n += 1
    save(dp, d)
    # 3. new suite
    up = load(CONF / "vectors" / "calendar-uaq.json")["vectors"]; by = {v["id"]: v for v in up}
    out = []
    for src in ("uaq/new-year/1438", "uaq/new-year-forward/1438", "uaq/new-year/1447", "uaq/new-year-forward/1447", "uaq/day-before-new-year-1438"):
        v = json.loads(json.dumps(by[src])); inp = {k: x for k, x in v["input"].items() if k != "provider"}
        out.append({"id": "default/" + src.removeprefix("uaq/"), "requirements": ["CAL-012"] + [q for q in v["requirements"] if q != "CAL-012"], "op": v["op"],
                    "tier": "exact", "basis": "spec", "input": inp, "expect": v["expect"],
                    "note": f"Copy of normative vector {src} with the provider OMITTED: the answer must be umm-al-qura's (CAL-012)."})
    loc, tz = {"lat": 9.0192, "lon": 38.7525}, "Africa/Addis_Ababa"
    prof = {"fajr_angle_deg": 18.0, "isha_angle_deg": 17.0, "asr_shadow_ratio": 1.0}
    why = "2025-06-26 is 1 Muharram 1447 in umm-al-qura (normative vector uaq/new-year-forward/1447); DAY-004 gives the day closing on that civil date that label; no calendar is named, so the default applies."
    out.append({"id": "default/label/date-to-waqt-day/addis/2025-06-26", "requirements": ["CAL-012", "DAY-004"], "op": "calendar.gregorian_date_to_waqt_day", "tier": "exact", "basis": "spec",
                "input": {"date": "2025-06-26", "location": loc, "timezone": tz}, "expect": {"output": {"resolved": True, "hijri_date": "1447-01-01", "weekday": "al-Khamis"}}, "note": why})
    out.append({"id": "default/label/compute-midday/addis/2025-06-26", "requirements": ["CAL-012", "DAY-004"], "op": "waqt.compute", "tier": "exact", "basis": "spec",
                "input": {"location": loc, "instant": "2025-06-26T09:00:00+00:00", "timezone": tz, "profile": prof},
                "expect": {"output": {"status": "OK", "hijri": {"date": "1447-01-01"}, "weekday": "al-Khamis"}}, "note": why})
    save(CONF / "vectors" / "calendar-default.json", {"suite": "calendar-default", "tier": "exact", "vectors": out})
    print(f"OQ-CAL-1 registered; CAL-012 present; {n} vector(s) pinned; calendar-default.json: {len(out)} vectors")


main()

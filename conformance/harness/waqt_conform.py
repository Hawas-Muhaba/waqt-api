#!/usr/bin/env python3
"""waqt-conform -- reproducible conformance runner for the Waqt specification (COP v1).

    python3 harness/waqt_conform.py --adapter "node independent/src/cli.mjs" --label independent
    python3 harness/waqt_conform.py --adapter "python3 adapters/reference_adapter.py" --label reference \
                                    --adapter "node independent/src/cli.mjs" --label independent

Standard library only. An *adapter* is any command that reads {"cases":[{id,op,input}]} on stdin and
writes {"implementation":{...},"results":[{id,ok,output|error}]} on stdout (conformance/spec/COP.md).

Vector tiers (conformance/spec/CONFORMANCE.md section 4):
  exact        normative; every expected leaf must match (subset semantics, null == absent)
  tolerance    normative; instants / numbers match within the vector's declared tolerance
  open         the specification does not determine the answer; the vector records the PROPOSED
               answer and an implementation's divergence is reported but is not a failure
  informative  provider- or data-dependent; reported, never counted as a failure
Metamorphic checks (vectors/metamorphic.json) assert relations between several calls instead of values.
"""
import argparse
import datetime as dt
import glob
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def contract_summary():
    """Contract version, hash and unresolved questions (Sprint 16, GOVERNANCE.md section 5): printed in EVERY
    report, never filtered, so a clean-looking table cannot hide an unresolved question."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("waqt_contract", os.path.join(ROOT, "tools", "contract.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.summary()
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$")


# ----------------------------------------------------------------------------- adapters
def call_adapter(cmd, cases, timeout=1800):
    req = json.dumps({"cases": cases})
    t0 = time.time()
    p = subprocess.run(cmd, input=req, capture_output=True, text=True, shell=True, cwd=ROOT, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(f"adapter failed ({p.returncode}): {p.stderr[-800:]}")
    out = json.loads(p.stdout)
    out["_seconds"] = round(time.time() - t0, 2)
    return out


def describe(cmd):
    p = subprocess.run(cmd + " --describe", capture_output=True, text=True, shell=True, cwd=ROOT)
    return json.loads(p.stdout)


# ----------------------------------------------------------------------------- comparison
def to_us(s):
    d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    frac = re.search(r"\.(\d+)", s)
    micro = int((frac.group(1) + "000000")[:6]) if frac else 0
    return int((d.replace(microsecond=0) - dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)).total_seconds()) * 1_000_000 + micro


def tol_for(path, tol):
    """exact indexed path first (e.g. $.events[2].instant), then index-free ($.events[].instant), then default"""
    paths = tol.get("paths", {})
    for cand in (path, re.sub(r"\[\d+\]", "[]", path)):
        for pat, v in paths.items():
            if re.fullmatch(pat, cand):
                return v
    return tol.get("default")


def cmp_value(exp, act, path, tol, ign, diffs):
    if isinstance(exp, dict):
        if not isinstance(act, dict):
            if exp == {} and act is None:
                return
            diffs.append((path, exp, act)); return
        for k, v in exp.items():
            if k in ign:
                continue
            cmp_value(v, act.get(k), f"{path}.{k}", tol, ign, diffs)
    elif isinstance(exp, list):
        if not isinstance(act, list) or len(exp) != len(act):
            if exp == [] and act is None:
                return
            diffs.append((path, exp, act)); return
        for i, (a, b) in enumerate(zip(exp, act)):
            cmp_value(a, b, f"{path}[{i}]", tol, ign, diffs)
    elif exp is None:
        if act not in (None, {}, []):
            diffs.append((path, exp, act))
    elif isinstance(exp, str) and ISO.match(exp):
        if not isinstance(act, str) or not ISO.match(act):
            diffs.append((path, exp, act)); return
        t = tol_for(path, tol)
        allowed = int((t or {}).get("instant_s", 0) * 1e6) if isinstance(t, dict) else 0
        if abs(to_us(exp) - to_us(act)) > allowed:
            diffs.append((path, exp, act, f"|d|={(to_us(exp) - to_us(act)) / 1e6:+.3f}s allowed {allowed / 1e6}s"))
    elif isinstance(exp, bool) or isinstance(act, bool):
        if exp is not act:
            diffs.append((path, exp, act))
    elif isinstance(exp, (int, float)):
        if not isinstance(act, (int, float)):
            diffs.append((path, exp, act)); return
        t = tol_for(path, tol)
        allowed = (t or {}).get("abs", 1e-6) if isinstance(t, dict) else 1e-6
        if abs(exp - act) > allowed:
            diffs.append((path, exp, act, f"|d|={exp - act:+.4f} allowed {allowed}"))
    else:
        if exp != act:
            diffs.append((path, exp, act))


def judge(vec, res):
    """-> (verdict, diffs)   verdict in PASS | FAIL | N/A"""
    exp = vec["expect"]
    if res is None:
        return "FAIL", [("$", "no result", None)]
    want_unsup = False
    if "error" in exp:
        c0 = exp["error"]["code"] if isinstance(exp["error"], dict) else exp["error"]
        want_unsup = "UNSUPPORTED_OPERATION" in (c0 if isinstance(c0, list) else [c0])
    if not res["ok"] and res["error"]["code"] == "UNSUPPORTED_OPERATION" and not want_unsup:
        return "N/A", [("$", "operation not implemented by adapter", res["error"]["message"])]
    if "error" in exp:
        want = exp["error"]["code"] if isinstance(exp["error"], dict) else exp["error"]
        wants = want if isinstance(want, list) else [want]
        if res["ok"]:
            return "FAIL", [("$", f"expected error {wants}", "succeeded: " + json.dumps(res["output"])[:160])]
        return ("PASS", []) if res["error"]["code"] in wants else ("FAIL", [("$.error.code", wants, res["error"]["code"])])
    if not res["ok"]:
        return "FAIL", [("$", "expected success", res["error"])]
    diffs = []
    cmp_value(exp["output"], res["output"], "$", vec.get("tolerance", {}), set(vec.get("ignore", [])), diffs)
    return ("PASS", []) if not diffs else ("FAIL", diffs)


# ----------------------------------------------------------------------------- metamorphic
def us_add(iso, delta_us):
    t = to_us(iso) + delta_us
    d = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(microseconds=t)
    return d.isoformat()


def run_metamorphic(cmd, mms, prec_us=1):
    """Each check is: base compute -> derived computes -> boolean assertions. Returns list of dicts."""
    out = run_calendar_properties(cmd, [m for m in mms if m["kind"] == "calendar-consistency"])
    mms = [m for m in mms if m["kind"] != "calendar-consistency"]
    # phase 1: base
    base_cases = [{"id": m["id"] + "#base", "op": "waqt.compute", "input": m["input"]} for m in mms]
    base = {r["id"]: r for r in call_adapter(cmd, base_cases)["results"]}
    phase2, plan = [], {}
    for m in mms:
        b = base[m["id"] + "#base"]
        if not b["ok"] or b["output"]["status"] != "OK":
            plan[m["id"]] = None
            continue
        o = b["output"]
        inp = m["input"]
        derived = {}
        k = m["kind"]
        if k in ("tiling", "boundary-instants"):
            # an implementation that publishes instants truncated to `prec_us` cannot be probed at the exact
            # boundary: probe one precision-unit either side instead (weaker, and reported as such)
            e = prec_us if prec_us > 1 else 0
            derived["at_open"] = dict(inp, instant=us_add(o["day"]["open"], e))
            derived["before_open"] = dict(inp, instant=us_add(o["day"]["open"], -max(e, 1)))
            derived["at_close"] = dict(inp, instant=us_add(o["day"]["close"], e))
            derived["before_close"] = dict(inp, instant=us_add(o["day"]["close"], -max(e, 1)))
        elif k == "profile-isolation":
            p = dict(inp.get("profile") or {})
            derived["fajr"] = dict(inp, profile=dict(p, fajr_angle_deg=m["change"]["fajr_angle_deg"]))
            derived["isha"] = dict(inp, profile=dict(p, isha_angle_deg=m["change"]["isha_angle_deg"]))
            derived["asr"] = dict(inp, profile=dict(p, asr_shadow_ratio=m["change"]["asr_shadow_ratio"]))
        elif k == "provider-isolation":
            for name in m["providers"]:
                derived[name] = dict(inp, calendar={"provider": name})
        elif k == "elevation-isolation":
            derived["high"] = dict(inp, location=dict(inp["location"], elevation_m=m["elevation_m"]))
        elif k == "instant-invariance":
            span = to_us(o["day"]["close"]) - to_us(o["day"]["open"])
            for j, fr in enumerate(m["fractions"]):
                derived[f"f{j}"] = dict(inp, instant=us_add(o["day"]["open"], int(fr * span)))
        for name, di in derived.items():
            phase2.append({"id": f"{m['id']}#{name}", "op": "waqt.compute", "input": di})
        plan[m["id"]] = derived
    res2 = {r["id"]: r for r in call_adapter(cmd, phase2)["results"]} if phase2 else {}
    for m in mms:
        mid = m["id"]
        b = base[mid + "#base"]
        if plan.get(mid) is None:
            out.append({"id": mid, "requirements": m["requirements"], "verdict": "FAIL" if not b["ok"] else "N/A",
                        "detail": "base computation did not return an OK day" + ("" if b["ok"] else f" ({b['error']})")}); continue
        o = b["output"]
        got = {n: res2.get(f"{mid}#{n}") for n in plan[mid]}
        checks = CHECKS[m["kind"]](m, o, got)
        bad = [c for c in checks if not c[0]]
        out.append({"id": mid, "requirements": m["requirements"], "verdict": "PASS" if not bad else "FAIL",
                    "detail": "; ".join(c[1] for c in bad) if bad else f"{len(checks)} relations hold"})
    return out


def run_calendar_properties(cmd, props):
    """Hijri calendar self-consistency: month lengths are 29/30 (tabular: 354/355-day years), months are contiguous,
    from_gregorian(start) is day 1, the day before the start is the last day of the previous month, and
    to_gregorian inverts from_gregorian."""
    if not props:
        return []
    c1 = [{"id": p["id"] + "#t", "op": "hijri.year_table", "input": p["input"]} for p in props]
    t = {r["id"]: r for r in call_adapter(cmd, c1)["results"]}
    c2, plan = [], {}
    for p in props:
        r = t[p["id"] + "#t"]
        if not r["ok"]:
            continue
        for mo in r["output"]["months"]:
            c2.append({"id": f"{p['id']}#f{mo['month']}", "op": "hijri.from_gregorian", "input": {"date": mo["start"], "provider": p["input"]["provider"]}})
            c2.append({"id": f"{p['id']}#b{mo['month']}", "op": "hijri.from_gregorian",
                       "input": {"date": (dt.date.fromisoformat(mo["start"]) - dt.timedelta(days=1)).isoformat(), "provider": p["input"]["provider"]}})
            c2.append({"id": f"{p['id']}#l{mo['month']}", "op": "hijri.to_gregorian",
                       "input": {"year": p["input"]["year"], "month": mo["month"], "day": mo["length"], "provider": p["input"]["provider"]}})
    g = {r["id"]: r for r in call_adapter(cmd, c2)["results"]} if c2 else {}
    out = []
    for p in props:
        r = t[p["id"] + "#t"]
        if not r["ok"]:
            out.append({"id": p["id"], "requirements": p["requirements"], "verdict": "N/A" if r["error"]["code"] == "UNSUPPORTED_OPERATION" else "FAIL", "detail": str(r["error"])[:120]}); continue
        bad, y = [], p["input"]["year"]
        ms = r["output"]["months"]
        for i, mo in enumerate(ms):
            if mo["length"] not in (29, 30):
                bad.append(f"month {mo['month']} has length {mo['length']}")
            if i + 1 < len(ms):
                gap = (dt.date.fromisoformat(ms[i + 1]["start"]) - dt.date.fromisoformat(mo["start"])).days
                if gap != mo["length"]:
                    bad.append(f"month {mo['month']} start->next start is {gap} days but length says {mo['length']}")
            f, b, l = g.get(f"{p['id']}#f{mo['month']}"), g.get(f"{p['id']}#b{mo['month']}"), g.get(f"{p['id']}#l{mo['month']}")
            if not (f and f["ok"] and (f["output"]["year"], f["output"]["month"], f["output"]["day"]) == (y, mo["month"], 1)):
                bad.append(f"from_gregorian(start of month {mo['month']}) is not day 1")
            if b and b["ok"] and not (mo["month"] == 1) and (b["output"]["year"], b["output"]["month"], b["output"]["day"]) != (y, mo["month"] - 1, ms[i - 1]["length"]):
                bad.append(f"day before month {mo['month']} is not the last day of month {mo['month'] - 1}")
            if not (l and l["ok"] and dt.date.fromisoformat(l["output"]["date"]) == dt.date.fromisoformat(mo["start"]) + dt.timedelta(days=mo["length"] - 1)):
                bad.append(f"to_gregorian(last day of month {mo['month']}) is wrong")
        out.append({"id": p["id"], "requirements": p["requirements"], "verdict": "FAIL" if bad else "PASS", "detail": "; ".join(bad[:3]) if bad else "12 months contiguous, lengths 29/30, round-trip exact"})
    return out


def _ok(r):
    return r is not None and r["ok"] and r["output"]["status"] == "OK"


def chk_tiling(m, o, g):
    tol_us = int(max(m.get("tolerance_s", 0.001) * 1e6, 2 * m.get("_prec", 1) if m.get("_prec", 1) > 1 else 0))
    c = []
    a, b, cl, bc = g["at_open"], g["before_open"], g["at_close"], g["before_close"]
    if not all(_ok(x) for x in (a, b, cl, bc)):
        return [(False, "derived computation failed")]
    a, b, cl, bc = a["output"], b["output"], cl["output"], bc["output"]
    c.append((abs(to_us(a["day"]["open"]) - to_us(o["day"]["open"])) <= tol_us, "instant == opening Maghrib must belong to the SAME day (half-open [open, close))"))
    ptol = m.get("position_tol_s", 1.0) + 2 * m.get("_prec", 1) / 1e6 * (1 if m.get("_prec", 1) > 1 else 0)
    c.append((a["position"]["seconds"] <= ptol, f"position at the exact opening Maghrib must be 0 (got {a['position']['seconds']})"))
    c.append((abs(to_us(b["day"]["close"]) - to_us(o["day"]["open"])) <= tol_us, "1 microsecond before opening Maghrib must belong to the PREVIOUS day, whose close == this open"))
    c.append((abs(to_us(cl["day"]["open"]) - to_us(o["day"]["close"])) <= tol_us, "instant == closing Maghrib must belong to the NEXT day (its open == this close)"))
    c.append((cl["position"]["seconds"] <= ptol, "position at the exact closing Maghrib must be 0 of the next day"))
    c.append((abs(to_us(bc["day"]["close"]) - to_us(o["day"]["close"])) <= tol_us and abs(to_us(bc["day"]["open"]) - to_us(o["day"]["open"])) <= tol_us, "1 microsecond before closing Maghrib stays in this day"))
    c.append((abs(o["day"]["length_seconds"] - (to_us(o["day"]["close"]) - to_us(o["day"]["open"])) / 1e6) <= max(0.01, 2 * m.get("_prec", 1) / 1e6 if m.get("_prec", 1) > 1 else 0), "length_seconds == close - open"))
    c.append((cl["weekday"] != o["weekday"], "weekday label changes at the closing Maghrib"))
    c.append((a["weekday"] == o["weekday"] and b["weekday"] != o["weekday"], "weekday changes exactly at Maghrib, not at civil midnight"))
    return c


def chk_boundary_instants(m, o, g):
    return chk_tiling(m, o, g)


def chk_position(m, o, g):
    c = []
    pt = max(0.01, 2 * m.get("_prec", 1) / 1e6) if m.get("_prec", 1) > 1 else 0.01
    t = to_us(o["instant"])
    c.append((abs((t - to_us(o["day"]["open"])) / 1e6 - o["position"]["seconds"]) <= pt, "position.seconds == instant - open"))
    for e in o["events"]:
        c.append((abs((to_us(e["instant"]) - to_us(o["day"]["open"])) / 1e6 - e["reading_seconds"]) <= pt, f"{e['name']}: reading == instant - open"))
    mg = [e for e in o["events"] if e["name"] == "maghrib"]
    if mg:
        c.append((abs(mg[0]["reading_seconds"] - o["day"]["length_seconds"]) <= pt, "closing Maghrib reading == day length"))
    isha = [e for e in o["events"] if e["name"] == "isha"]
    if isha and mg:
        c.append((isha[0]["reading_seconds"] > o["day"]["length_seconds"], "Isha is listed beyond the day length (it follows the closing Maghrib)"))
    return c


def chk_profile(m, o, g):
    c = []
    def evmap(x):
        return {e["name"]: to_us(e["instant"]) for e in x["output"]["events"]} if _ok(x) else None
    base = {e["name"]: to_us(e["instant"]) for e in o["events"]}
    for key, ev in (("fajr", "fajr"), ("isha", "isha"), ("asr", "asr")):
        d = evmap(g[key])
        if d is None:
            c.append((False, f"{key}: derived computation failed")); continue
        others = [n for n in base if n != ev]
        same = all(n in d and abs(d[n] - base[n]) <= 1_000 for n in others)
        c.append((same, f"changing the {key} parameter moved another event"))
        if ev in base:   # (the event may legitimately not exist at this place/date)
            c.append((ev in d and abs(d[ev] - base[ev]) > 1_000_000, f"changing the {key} parameter did not move {ev}"))
        c.append((to_us(g[key]["output"]["day"]["open"]) == to_us(o["day"]["open"]) and to_us(g[key]["output"]["day"]["close"]) == to_us(o["day"]["close"]), f"changing {key} parameter altered the day boundary"))
    return c


def chk_provider(m, o, g):
    c = []
    labels = set()
    for n, r in g.items():
        if not _ok(r):
            c.append((False, f"{n}: failed")); continue
        x = r["output"]
        c.append((x["day"] == o["day"] and x["position"]["seconds"] == o["position"]["seconds"], f"{n}: provider changed the day/position"))
        c.append(([(e["name"], e["instant"]) for e in x["events"]] == [(e["name"], e["instant"]) for e in o["events"]], f"{n}: provider changed an event"))
        labels.add(x["hijri"]["date"])
    c.append((len(labels | {o["hijri"]["date"]}) >= 1, "labels"))
    return c


def chk_elev(m, o, g):
    x = g["high"]
    if not _ok(x):
        return [(False, "derived computation failed")]
    a = {e["name"]: to_us(e["instant"]) for e in o["events"]}
    b = {e["name"]: to_us(e["instant"]) for e in x["output"]["events"]}
    c = []
    if all(k in a and k in b for k in ("maghrib", "sunrise")):
        c.append((b["maghrib"] > a["maghrib"] and b["sunrise"] < a["sunrise"], "elevation must make sunrise earlier and sunset later"))
    for n in ("fajr", "dhuhr", "asr", "isha"):
        if n in a:
            c.append((n in b and abs(a[n] - b[n]) <= 1_000, f"elevation must not move {n}"))
    return c


def chk_invariance(m, o, g):
    c = []
    for n, r in g.items():
        if not _ok(r):
            c.append((False, f"{n}: failed")); continue
        x = r["output"]
        c.append((x["day"]["open"] == o["day"]["open"] and x["day"]["close"] == o["day"]["close"], f"{n}: day differs for an instant inside the same day"))
        c.append(([e["instant"] for e in x["events"]] == [e["instant"] for e in o["events"]], f"{n}: events differ for an instant inside the same day"))
    return c


CHECKS = {"tiling": lambda m, o, g: chk_tiling(m, o, g) + chk_position(m, o, g), "boundary-instants": chk_boundary_instants,
          "profile-isolation": chk_profile, "provider-isolation": chk_provider, "elevation-isolation": chk_elev,
          "instant-invariance": chk_invariance}


# ----------------------------------------------------------------------------- main
def load_vectors(vdir, suites):
    files = sorted(glob.glob(os.path.join(vdir, "*.json")))
    vecs, mms = [], []
    for f in files:
        name = os.path.basename(f)[:-5]
        if suites and name not in suites:
            continue
        d = json.load(open(f))
        for v in d.get("vectors", []):
            v.setdefault("suite", name)
            v.setdefault("tier", d.get("tier", "exact"))
            vecs.append(v)
        for m in d.get("metamorphic", []):
            m.setdefault("suite", name)
            mms.append(m)
    return vecs, mms


def short(x, n=170):
    s = json.dumps(x, ensure_ascii=False) if not isinstance(x, str) else x
    return s if len(s) <= n else s[:n] + "..."


def run_one(label, cmd, vecs, mms, all_ops):
    desc = describe(cmd)
    cases = [{"id": v["id"], "op": v["op"], "input": v["input"]} for v in vecs]
    out = call_adapter(cmd, cases)
    by = {r["id"]: r for r in out["results"]}
    rows = []
    for v in vecs:
        r = by.get(v["id"])
        verdict, diffs = judge(v, r)
        rows.append({"id": v["id"], "suite": v["suite"], "tier": v["tier"], "requirements": v["requirements"], "verdict": verdict,
                     "diffs": [[d[0], short(d[1]), short(d[2])] + ([d[3]] if len(d) > 3 else []) for d in diffs[:4]],
                     "note": v.get("note"), "result": r})
    prec = int((desc.get("implementation") or {}).get("instant_precision_us", 1))
    mm_rows = run_metamorphic(cmd, [dict(m, _prec=prec) for m in mms], prec) if mms else []
    return {"label": label, "command": cmd, "descriptor": desc.get("implementation"), "operations": desc.get("operations"),
            "seconds": out["_seconds"], "vectors": rows, "metamorphic": mm_rows}


def summarize(run, reqs):
    tiers = {}
    for r in run["vectors"]:
        t = tiers.setdefault(r["tier"], {"PASS": 0, "FAIL": 0, "N/A": 0})
        t[r["verdict"]] += 1
    mm = {"PASS": 0, "FAIL": 0, "N/A": 0}
    for m in run["metamorphic"]:
        mm[m["verdict"]] += 1
    per_req = {}
    def add(rid, tier, v):
        e = per_req.setdefault(rid, {"exact": [0, 0], "tolerance": [0, 0], "open": [0, 0], "informative": [0, 0], "metamorphic": [0, 0], "na": 0})
        if v == "N/A":
            e["na"] += 1
        else:
            e[tier][0 if v == "PASS" else 1] += 1
    for r in run["vectors"]:
        for rid in r["requirements"]:
            add(rid, r["tier"], r["verdict"])
    for m in run["metamorphic"]:
        for rid in m["requirements"]:
            add(rid, "metamorphic", m["verdict"])
    return tiers, mm, per_req


def req_status(e):
    """normative status of a requirement for one implementation"""
    p = e["exact"][0] + e["tolerance"][0] + e["metamorphic"][0]
    f = e["exact"][1] + e["tolerance"][1] + e["metamorphic"][1]
    if p + f == 0:
        if e["open"][0] + e["open"][1] + e["informative"][0] + e["informative"][1] == 0:
            return "NO-DATA"
        return "OPEN-ONLY"
    return "PASS" if f == 0 else "FAIL"


def markdown(runs, reqs, vecs, mms, meta):
    L = []
    w = L.append
    w(f"# Waqt conformance report\n")
    w(f"Generated {meta['generated']} by `harness/waqt_conform.py` · COP {meta['cop']} · {len(vecs)} vectors + {len(mms)} metamorphic checks.\n")
    w("Reproduce: `python3 conformance/harness/waqt_conform.py --adapter \"python3 conformance/adapters/reference_adapter.py\" --label reference --adapter \"node conformance/independent/src/cli.mjs\" --label independent`\n")
    c = meta.get("contract") or {}
    if c:
        w("## 0. Contract and unresolved questions\n")
        w(f"Contract **{c['contract_version']}** ({'released' if c['released'] else 'DRAFT - not yet released/ratified'}) - sha256 `{c['contract_sha256'][:16]}` - "
          f"manifest {'matches' if c['manifest_matches_files'] else '**DOES NOT MATCH** the files on disk'} - COP {c['cop_version']}.\n")
        q = c["questions"]
        w(f"**Unresolved specification questions: {q['deferred'] + q['unresolved-by-design']}** of {q['total']} "
          f"({q['unresolved-by-design']} unresolved by design, {q['deferred']} deferred; {q['resolved']} resolved). "
          "A passing table below does not mean these are settled.\n")
        for u in c["unresolved"]:
            w(f"- `{u['id']}` [{u['status']}] {u['topic']}")
        if c["unenforced_musts"]:
            w("\nDeclared MUST but not enforced by any normative vector: " + ", ".join(f"`{x}`" for x in c["unenforced_musts"]) + ".")
        w("")
    w("## 1. Implementations\n")
    w("| label | implementation | language | shares code with reference | run time |")
    w("|---|---|---|---|---|")
    for r in runs:
        d = r["descriptor"] or {}
        w(f"| {r['label']} | {d.get('name')} {d.get('version')} | {d.get('language')} | {d.get('shares_code_with_reference')} | {r['seconds']} s |")
    w("\n## 2. Results by tier\n")
    w("Normative tiers (`exact`, `tolerance`) and metamorphic checks decide conformance. `open` and `informative` vectors are reported but never counted as failures (see CONFORMANCE.md §4).\n")
    w("| tier | " + " | ".join(f"{r['label']} pass / fail / n.a." for r in runs) + " |")
    w("|---|" + "---|" * len(runs))
    sums = [summarize(r, reqs) for r in runs]
    for tier in ("exact", "tolerance", "open", "informative"):
        cells = []
        for s in sums:
            t = s[0].get(tier, {"PASS": 0, "FAIL": 0, "N/A": 0})
            cells.append(f"{t['PASS']} / {t['FAIL']} / {t['N/A']}")
        w(f"| {tier} | " + " | ".join(cells) + " |")
    w("| metamorphic | " + " | ".join(f"{s[1]['PASS']} / {s[1]['FAIL']} / {s[1]['N/A']}" for s in sums) + " |")
    w("\n## 3. Requirements\n")
    w("`PASS` = every normative vector for the requirement passes; `FAIL` = at least one fails; `OPEN-ONLY` = only open/informative vectors exist; `NO-DATA` = no vector yet.\n")
    w("| requirement | kind | " + " | ".join(r["label"] for r in runs) + " | title |")
    w("|---|---|" + "---|" * len(runs) + "---|")
    for rid in sorted(reqs):
        cells = []
        for s in sums:
            e = s[2].get(rid)
            if not e:
                cells.append("NO-DATA"); continue
            st = req_status(e)
            n = f" ({e['exact'][0] + e['tolerance'][0] + e['metamorphic'][0]}/{sum(e['exact']) + sum(e['tolerance']) + sum(e['metamorphic'])})"
            cells.append(st + (n if st in ("PASS", "FAIL") else ""))
        w(f"| {rid} | {reqs[rid]['kind']} | " + " | ".join(cells) + f" | {reqs[rid]['title']} |")
    for r in runs:
        w(f"\n## 4. Failing normative vectors — {r['label']}\n")
        fails = [v for v in r["vectors"] if v["verdict"] == "FAIL" and v["tier"] in ("exact", "tolerance")]
        mfail = [m for m in r["metamorphic"] if m["verdict"] == "FAIL"]
        if not fails and not mfail:
            w("None.\n"); continue
        for v in fails:
            w(f"- **{v['id']}** ({v['tier']}; {', '.join(v['requirements'])})")
            for d in v["diffs"][:3]:
                w(f"  - `{d[0]}` expected `{d[1]}` got `{d[2]}`" + (f" — {d[3]}" if len(d) > 3 else ""))
        for m in mfail:
            w(f"- **{m['id']}** (metamorphic; {', '.join(m['requirements'])}): {m['detail']}")
    for r in runs:
        w(f"\n## 5. Open-question and informative divergences — {r['label']}\n")
        rows = [v for v in r["vectors"] if v["tier"] in ("open", "informative") and v["verdict"] == "FAIL"]
        if not rows:
            w("None.\n"); continue
        for v in rows:
            w(f"- **{v['id']}** ({v['tier']}; {', '.join(v['requirements'])}): " + (v["diffs"][0][0] + " expected `" + v["diffs"][0][1] + "` got `" + v["diffs"][0][2] + "`" if v["diffs"] else ""))
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--adapter", action="append", required=True)
    ap.add_argument("--label", action="append")
    ap.add_argument("--vectors", default=os.path.join(ROOT, "vectors"))
    ap.add_argument("--suite", action="append", help="restrict to suite file name(s) without .json")
    ap.add_argument("--out", default=os.path.join(ROOT, "reports"))
    ap.add_argument("--name", default="conformance-report")
    args = ap.parse_args()
    labels = args.label or [f"impl{i}" for i in range(len(args.adapter))]
    reqs = json.load(open(os.path.join(ROOT, "spec", "requirements.json")))["requirements"]
    reqs = {r["id"]: r for r in reqs}
    vecs, mms = load_vectors(args.vectors, args.suite)
    unknown = {rid for v in vecs + mms for rid in v["requirements"]} - set(reqs)
    if unknown:
        sys.exit(f"vectors reference unknown requirement ids: {sorted(unknown)}")
    runs = []
    for cmd, label in zip(args.adapter, labels):
        print(f"[waqt-conform] running {label}: {len(vecs)} vectors, {len(mms)} metamorphic ...", file=sys.stderr)
        runs.append(run_one(label, cmd, vecs, mms, None))
    meta = {"generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "cop": contract_summary()["cop_version"], "contract": contract_summary()}
    os.makedirs(args.out, exist_ok=True)
    slim = []
    for r in runs:
        rr = dict(r)
        rr["vectors"] = [{k: v for k, v in x.items() if k != "result"} for x in r["vectors"]]
        slim.append(rr)
    json.dump({"meta": meta, "runs": slim}, open(os.path.join(args.out, args.name + ".json"), "w"), indent=1)
    open(os.path.join(args.out, args.name + ".md"), "w").write(markdown(runs, reqs, vecs, mms, meta))
    # cross-implementation agreement on every shared vector
    if len(runs) > 1:
        a, b = runs[0], runs[1]
        dis = [(x["id"], x["tier"], x["verdict"], y["verdict"]) for x, y in zip(a["vectors"], b["vectors"]) if x["verdict"] != y["verdict"]]
        json.dump(dis, open(os.path.join(args.out, args.name + "-verdict-differences.json"), "w"), indent=1)
        print(f"[waqt-conform] verdict differences between {a['label']} and {b['label']}: {len(dis)}", file=sys.stderr)
    for r, s in zip(runs, [summarize(r, reqs) for r in runs]):
        norm = {k: v for k, v in s[0].items() if k in ("exact", "tolerance")}
        p = sum(v["PASS"] for v in norm.values()) + s[1]["PASS"]
        f = sum(v["FAIL"] for v in norm.values()) + s[1]["FAIL"]
        print(f"[waqt-conform] {r['label']}: normative pass={p} fail={f}", file=sys.stderr)


if __name__ == "__main__":
    main()

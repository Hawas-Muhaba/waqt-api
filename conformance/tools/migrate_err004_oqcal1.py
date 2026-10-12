#!/usr/bin/env python3
"""Audit trail for the contract 2.0.0 (draft) amendments of DR-0011 and DR-0012.

    python3 tools/migrate_err004_oqcal1.py            # apply (idempotent; run from conformance/)
    python3 tools/migrate_err004_oqcal1.py --check    # STRICTLY READ-ONLY: exit 1 if anything would still change

DR-0011  ERR-004 becomes a normative requirement with explicit ranges:
         fajr_angle_deg, isha_angle_deg: finite, 0 < x <= 90;  asr_shadow_ratio: finite, x > 0.
         Anything else (zero, negative, above range, NaN, +/-Infinity, a non-number) is rejected with VALIDATION_ERROR.
         The five `open` vectors err/profile/* are PROMOTED in place (same ids) and extended.
DR-0012  OQ-CAL-1 is resolved by adopting the API policy as the contract rule CAL-013: an operation that returns a
         Waqt day never fails because the calendar provider cannot label the date; hijri.* operations still refuse
         (CAL-011). The two `open` vectors of OQ-CAL-1 are PROMOTED (moved to calendar-default.json, same ids).

No recorded value of any pre-existing vector changes: only tiers (open -> exact) and, for promoted vectors, the
expectation that was already PROPOSED in them. Standard library only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

CONF = Path(__file__).resolve().parent.parent
PLANNED: dict[Path, str] = {}


def rd(p: Path) -> str:
    return PLANNED.get(p) if p in PLANNED else p.read_text(encoding="utf-8")


def load(p: Path):
    return json.loads(rd(p))


def put(p: Path, text: str) -> None:
    PLANNED[p] = text


def save(p: Path, obj) -> None:
    put(p, json.dumps(obj, indent=1, ensure_ascii=False) + "\n")


# ----------------------------------------------------------------------------------------------- requirements
ERR004_TITLE = ("Astronomy profile parameters are validated: fajr_angle_deg and isha_angle_deg must be finite numbers with 0 < value <= 90, "
                "asr_shadow_ratio a finite number with value > 0; zero, negatives, values above range, NaN, +/-Infinity and non-numbers are "
                "rejected with VALIDATION_ERROR (HTTP 422); nothing is clamped or coerced")
CAL013_TITLE = ("An operation that returns a Waqt day (waqt.compute, calendar.*) never fails because the calendar provider cannot label the date: "
                "the Waqt day and every instant are unchanged, the Hijri label is empty and calendar_error {code: OUT_OF_RANGE} says why; "
                "hijri.* operations still refuse with OUT_OF_RANGE (CAL-011)")


def requirements():
    p = CONF / "spec" / "requirements.json"
    r = load(p)
    for q in r["requirements"]:
        if q["id"] == "ERR-004":
            q["title"], q["decision"], q["changed"] = ERR004_TITLE, "DR-0011", "2.0.0"
            q["status"] = "normative"
    if not any(q["id"] == "CAL-013" for q in r["requirements"]):
        r["requirements"].append({"id": "CAL-013", "kind": "MUST", "title": CAL013_TITLE, "section": "COP 5; API 1.8.0",
                                  "since": "2.0.0", "status": "normative", "decision": "DR-0012"})
    r["requirements"].sort(key=lambda x: (x["id"].split("-")[0], int(x["id"].split("-")[1])))
    save(p, r)


# --------------------------------------------------------------------------------------------------- vectors
NF = lambda t: {"$nonfinite": t}  # noqa: E731  (COP wire convention, spec/COP.md section 2)
BASE_PROFILE = {"fajr_angle_deg": 18.0, "isha_angle_deg": 17.0, "asr_shadow_ratio": 1.0}
ZERO_LOC = {"lat": 0, "lon": 0}
ADDIS = {"lat": 9.0192, "lon": 38.7525}
TZ = "Africa/Addis_Ababa"
NOTE_INVALID = "DR-0011 / ERR-004: rejected with VALIDATION_ERROR; never clamped, never defaulted."
NOTE_VALID = "DR-0011 / ERR-004: an inclusive boundary of the valid range is accepted and echoed unchanged."


def vec(vid, reqs, op, inp, expect, tier="exact", note=None, tolerance=None, basis="spec"):
    v = {"id": vid, "requirements": reqs, "op": op, "tier": tier, "basis": basis, "input": inp, "expect": expect}
    if note:
        v["note"] = note
    if tolerance:
        v["tolerance"] = tolerance
    return v


def compute_input(prof):
    return {"location": ZERO_LOC, "instant": "2026-09-19T15:42:00+00:00", "timezone": "UTC", "profile": {**BASE_PROFILE, **prof}}


VALIDATION = {"error": {"code": ["VALIDATION_ERROR"]}}

INVALID = [
    ("fajr-95", {"fajr_angle_deg": 95}), ("fajr-90.0001", {"fajr_angle_deg": 90.0001}), ("fajr-zero", {"fajr_angle_deg": 0}),
    ("fajr-negative", {"fajr_angle_deg": -5}), ("fajr-nan", {"fajr_angle_deg": NF("NaN")}), ("fajr-infinity", {"fajr_angle_deg": NF("Infinity")}),
    ("fajr-neg-infinity", {"fajr_angle_deg": NF("-Infinity")}), ("fajr-non-numeric-string", {"fajr_angle_deg": "abc"}), ("fajr-boolean", {"fajr_angle_deg": True}),
    ("isha-zero", {"isha_angle_deg": 0}), ("isha-90.0001", {"isha_angle_deg": 90.0001}), ("isha-negative", {"isha_angle_deg": -1}),
    ("isha-nan", {"isha_angle_deg": NF("NaN")}), ("isha-infinity", {"isha_angle_deg": NF("Infinity")}),
    ("isha-non-numeric-string", {"isha_angle_deg": "abc"}), ("isha-boolean", {"isha_angle_deg": False}),
    ("asr-zero", {"asr_shadow_ratio": 0}), ("asr-negative", {"asr_shadow_ratio": -1}), ("asr-nan", {"asr_shadow_ratio": NF("NaN")}),
    ("asr-infinity", {"asr_shadow_ratio": NF("Infinity")}), ("asr-neg-infinity", {"asr_shadow_ratio": NF("-Infinity")}),
    ("asr-non-numeric-string", {"asr_shadow_ratio": "abc"}), ("asr-boolean", {"asr_shadow_ratio": True}),
]
VALID = [("fajr-90", {"fajr_angle_deg": 90}), ("fajr-0.0001", {"fajr_angle_deg": 0.0001}), ("isha-90", {"isha_angle_deg": 90}),
         ("isha-0.0001", {"isha_angle_deg": 0.0001}), ("asr-0.0001", {"asr_shadow_ratio": 0.0001}), ("asr-100", {"asr_shadow_ratio": 100})]
SCHED_CTX = {"location": {**ADDIS, "elevation_m": 0.0}, "timezone": TZ, "calendar": {"provider": "arithmetic-tabular"}}
SCHED_OP = {"anchor": "2026-09-19T15:42:00+00:00", "operation": {"op": "resolve_point", "point": {"type": "event", "name": "fajr", "day": 0}}}


def errors_vectors():
    p = CONF / "vectors" / "errors.json"
    d = load(p)
    keep = [v for v in d["vectors"] if not v["id"].startswith(("err/profile/", "err/profile-"))]
    new = []
    for tag, prof in INVALID:
        new.append(vec(f"err/profile/{tag}", ["ERR-004"], "waqt.compute", compute_input(prof), VALIDATION, note=NOTE_INVALID))
    for tag, prof in VALID:
        new.append(vec(f"err/profile-valid/{tag}", ["ERR-004"], "waqt.compute", compute_input(prof),
                       {"output": {"status": "OK", "profile": {**BASE_PROFILE, **prof}}}, note=NOTE_VALID))
    # other public entry points: the same rule, the same code
    for tag, prof in [("fajr-95", {"fajr_angle_deg": 95}), ("isha-nan", {"isha_angle_deg": NF("NaN")}), ("asr-zero", {"asr_shadow_ratio": 0})]:
        ctx = {**SCHED_CTX, "profile": {**BASE_PROFILE, **prof}}
        new.append(vec(f"err/profile-schedule/{tag}", ["ERR-004"], "schedule.run", {"context": ctx, **SCHED_OP}, VALIDATION, note=NOTE_INVALID))
    for tag, prof in [("fajr-zero", {"fajr_angle_deg": 0}), ("asr-nan", {"asr_shadow_ratio": NF("NaN")})]:
        new.append(vec(f"err/profile-date-to-waqt/{tag}", ["ERR-004"], "calendar.gregorian_date_to_waqt_day",
                       {"date": "2026-09-19", "location": ADDIS, "timezone": TZ, "profile": {**BASE_PROFILE, **prof}}, VALIDATION, note=NOTE_INVALID))
    d["vectors"] = keep + new
    save(p, d)


OOR = {"code": "OUT_OF_RANGE"}
NOTE13 = "DR-0012 / CAL-013: the Waqt day is returned, the Hijri label is empty, calendar_error says OUT_OF_RANGE; no failure."


def default_vectors():
    p = CONF / "vectors" / "calendar-default.json"
    d = load(p)
    have = {v["id"] for v in d["vectors"]}
    mp = CONF / "vectors" / "open-questions.json"
    oq = load(mp)
    moved = [v for v in oq["vectors"] if v["id"].startswith("default/out-of-range/")]
    oq["vectors"] = [v for v in oq["vectors"] if not v["id"].startswith("default/out-of-range/")]
    save(mp, oq)
    for v in moved:
        if v["id"] in have:
            continue
        v = dict(v)
        v["tier"], v["requirements"] = "exact", ["CAL-012", "CAL-013"]
        v["note"] = NOTE13 + " (promoted from OQ-CAL-1; the expectation is unchanged)"
        if v["op"] == "waqt.compute":
            v["expect"] = {"output": {"status": "OK", "hijri": None, "calendar_error": OOR}}
        else:
            v["expect"] = {"output": {"resolved": True, "hijri_date": None, "calendar_error": OOR}}
        d["vectors"].append(v)
        have.add(v["id"])
    new = []
    for date, expect in [("1699-12-31", {"resolved": True, "hijri_date": None, "calendar_error": OOR}),
                         ("2301-01-01", {"resolved": True, "hijri_date": None, "calendar_error": OOR}),
                         ("1700-01-01", {"resolved": True, "hijri_date": "1111-07-11", "calendar_error": None}),
                         ("2300-12-31", {"resolved": True, "hijri_date": "1730-12-19", "calendar_error": None})]:
        new.append(vec(f"cal13/date-to-waqt-day/addis/{date}", ["CAL-012", "CAL-013"], "calendar.gregorian_date_to_waqt_day",
                       {"date": date, "location": ADDIS, "timezone": TZ}, {"output": expect}, note=NOTE13 if expect["hijri_date"] is None else
                       "DR-0012: the first / last supported day behaves exactly as before; expected value is that of the normative uaq/range vector."))
    for date in ("1699-12-31", "2301-01-01"):
        new.append(vec(f"cal13/date-to-waqt-day-explicit/addis/{date}", ["CAL-013"], "calendar.gregorian_date_to_waqt_day",
                       {"date": date, "location": ADDIS, "timezone": TZ, "calendar": {"provider": "umm-al-qura"}},
                       {"output": {"resolved": True, "hijri_date": None, "calendar_error": OOR}}, note=NOTE13 + " Same rule for an explicitly named provider."))
        new.append(vec(f"cal13/hijri-refuses/{date}", ["CAL-011", "CAL-012"], "hijri.from_gregorian", {"date": date},
                       {"error": {"code": ["OUT_OF_RANGE"]}}, note="CAL-011 is unchanged: hijri.* operations refuse outside the range, with the default provider omitted."))
    tol = {"default": {"instant_s": 5, "abs": 5}}
    new.append(vec("cal13/compute/addis/1699-12-31T12:00Z", ["CAL-013"], "waqt.compute",
                   {"location": ADDIS, "instant": "1699-12-31T12:00:00+00:00", "timezone": TZ, "profile": BASE_PROFILE},
                   {"output": {"status": "OK", "hijri": None, "calendar_error": OOR, "day": {"open": "1699-12-30T15:16:36+00:00", "close": "1699-12-31T15:17:08+00:00"}}},
                   tier="tolerance", basis="recorded", tolerance=tol,
                   note=NOTE13 + " The day boundaries are recorded from the reference (the independent implementation agrees to < 1 s); the Waqt day is unchanged by the missing label."))
    new.append(vec("cal13/compute/addis/1700-01-01T12:00Z", ["CAL-013"], "waqt.compute",
                   {"location": ADDIS, "instant": "1700-01-01T12:00:00+00:00", "timezone": TZ, "profile": BASE_PROFILE},
                   {"output": {"status": "OK", "hijri": {"date": "1111-07-11"}, "calendar_error": None, "day": {"open": "1699-12-31T15:17:08+00:00", "close": "1700-01-01T15:17:40+00:00"}}},
                   tier="tolerance", basis="recorded", tolerance=tol,
                   note="DR-0012: the first supported day, inside the range, behaves exactly as before. (An upper-end waqt.compute vector is not possible: the independent implementation's microsecond-integer clock stops near 2255, RANGE_ERROR; the upper end is covered by calendar.gregorian_date_to_waqt_day.)"))
    for v in new:
        if v["id"] not in have:
            d["vectors"].append(v)
            have.add(v["id"])
    save(p, d)


def open_question():
    p = CONF / "spec" / "open-questions.json"
    q = load(p)
    for x in q["questions"]:
        if x["id"] == "OQ-CAL-1":
            x["status"], x["requirement"], x["decision"] = "resolved", "CAL-013", "DR-0012"
        if x["id"] == "OQ-ERR-1":
            x["status"], x["requirement"], x["decision"] = "resolved", "ERR-004", "DR-0011"
    save(p, q)


# -------------------------------------------------------------------------------------------- documentation
def cop():
    p = CONF / "spec" / "COP.md"
    s = rd(p)
    if "$nonfinite" not in s:
        row = "| Time zone |"
        add = ("| Non-finite numbers | JSON has no NaN or Infinity. A vector writes one as `{\"$nonfinite\": \"NaN\"}`, `{\"$nonfinite\": \"Infinity\"}` or "
               "`{\"$nonfinite\": \"-Infinity\"}` (nothing else); an adapter decodes it to a real non-finite number before calling the implementation (DR-0011). |\n")
        assert s.count(row) == 1
        s = s.replace(row, add + row, 1)
    if "### Astronomy profile validation (ERR-004)" not in s:
        anchor = "### `waqt.compute`"
        block = (
            "### Astronomy profile validation (ERR-004)\n"
            "Every operation that accepts an astronomy profile (`waqt.compute`, `schedule.run`, `calendar.gregorian_date_to_waqt_day`, ...) validates it, and so does every HTTP "
            "endpoint, `waqt-local` and the CLI:\n\n"
            "| parameter | valid values |\n|---|---|\n| `fajr_angle_deg` | a finite number, `0 < x <= 90` |\n| `isha_angle_deg` | a finite number, `0 < x <= 90` |\n"
            "| `asr_shadow_ratio` | a finite number, `x > 0` |\n\n"
            "Zero, negatives, values above range, NaN, +/-Infinity, booleans and non-numeric text are rejected with `VALIDATION_ERROR` (HTTP 422 on the API). Nothing is clamped, "
            "coerced or replaced by a default. A parameter that is *omitted* takes its default (18, 17, 1); a JSON `null` is treated as omitted by both reference adapters and is "
            "**not specified** by the contract (flagged in DR-0011). The numeric *text* `\"18\"` is accepted by the HTTP GET API (every query parameter is text) and is therefore "
            "also not specified for JSON inputs.\n\n")
        assert s.count(anchor) == 1
        s = s.replace(anchor, block + anchor, 1)
    old = ("Outside `umm-al-qura`'s 1700-01-01..2300-12-31 (CAL-011), `hijri.*` operations that omit the provider return `OUT_OF_RANGE`. What the *other* operations "
           "(`waqt.compute`, `calendar.*`) must do there is **not yet specified** (open question OQ-CAL-1): the reference returns the Waqt day with an empty Hijri label, "
           "the independent implementation returns `OUT_OF_RANGE`.")
    new = ("Outside `umm-al-qura`'s 1700-01-01..2300-12-31 (CAL-011), `hijri.*` operations return `OUT_OF_RANGE`. Operations that return a Waqt day (`waqt.compute`, "
           "`calendar.*`) do **not** fail (CAL-013, DR-0012, closing OQ-CAL-1): they return the Waqt day and every instant unchanged, an empty Hijri label (`hijri` / "
           "`hijri_date` null) and `calendar_error: {code: \"OUT_OF_RANGE\"}`. This holds for the default provider and for an explicitly named `umm-al-qura` alike; the free-text "
           "message is not normative and is not part of the COP output.")
    if old in s:
        s = s.replace(old, new, 1)
    put(p, s)


DR11 = """# DR-0011: ERR-004 -- astronomy profile parameters are validated, with explicit ranges

| | |
|---|---|
| **Status** | DECIDED by the project owner's written instruction of 2026-10-11 (pre-release review owner decisions). **Ratification by a named maintainer: PENDING.** Independent review: NOT performed. Signed ratification artifact: NONE held. This record does not claim ratification; see GOVERNANCE.md section 3 and the CCP-0001 / DR-0010 open items. |
| **Contract** | 2.0.0 (draft, unreleased): amended in place; no released manifest is altered |
| **Date** | 2026-10-11 |
| **Questions** | closes OQ-ERR-1 (valid ranges of fajr_angle, isha_angle, asr_ratio) |
| **Requirements** | ERR-004 (MUST, now with explicit ranges and normative vectors) |

## Context
ERR-004 ("non-physical astronomy parameters are rejected") was declared MUST but had only `open` vectors, because the specification gave units but no range. The reference
accepted fajr_angle=95, fajr_angle=-5, isha_angle=0 and asr_ratio=0 with HTTP 200. The independent implementation already rejected them, but with an exclusive upper bound of 90.

## Decision
`fajr_angle_deg` and `isha_angle_deg`: finite number, 0 < x <= 90. `asr_shadow_ratio`: finite number, x > 0. Everything else -- zero, negatives, values above range, NaN,
+/-Infinity, booleans, non-numeric text -- is rejected with `VALIDATION_ERROR` (HTTP 422). No clamping, no coercion, no change of defaults (18, 17, 1). One validator in
`waqt_core.profile_validation`, applied when an `AstronomyProfile` is constructed, so the API (GET and POST), `waqt-local`, the CLI, `waqt-core` and the reference adapter share it.
The independent implementation changed its upper bound from exclusive to inclusive (90 is valid).

## Evidence
Reference and independent agree on every new vector (see the regenerated conformance report). Reproduce: `python3 tools/migrate_err004_oqcal1.py --check`, `sh run.sh`.

## Consequences
Behaviour change (tightening): a client that sent an out-of-range profile previously received a result and now receives HTTP 422. This is part of API 1.8.0 (DR-0013).
Vectors: the five `open` err/profile/* vectors are promoted in place (same ids); 18 invalid and 6 valid-boundary `waqt.compute` vectors, 3 `schedule.run` and 2
`calendar.gregorian_date_to_waqt_day` vectors are added. NaN/Infinity are written with the `$nonfinite` wire convention (COP section 2).

## Alternatives considered
Clamp to the range (rejected by the owner: never silently clamp). Exclusive upper bound at 90 (rejected by the owner; the independent implementation was changed to match).

## Configurability (religious / regional conventions)
Any angle in the range is accepted, so every established convention (for example 15, 18, 19.5 degrees; Shafi'i/Hanafi Asr) stays selectable. The contract does not say which
angle is right for a place.

## Dissent and unresolved points
Not specified, deliberately left unspecified rather than invented: (1) a JSON `null` is treated as "omitted" by both adapters; (2) numeric text such as "18" is accepted by the
HTTP GET API because query parameters are text; (3) whether 90 degrees is *meaningful* astronomically (the event is simply undefined at most latitudes) is outside this record.

## Reopen when
A domain ruling narrows a range, a third implementation disagrees, or null / numeric-text handling is specified.

## Vectors affected
`errors.json` (5 promoted, rest added). Audit trail: `tools/migrate_err004_oqcal1.py`.
"""

DR12 = """# DR-0012: Out-of-range calendar dates never fail a Waqt computation (CAL-013); OQ-CAL-1 resolved

| | |
|---|---|
| **Status** | DECIDED by the project owner's written instruction of 2026-10-11, adopting the existing API 1.5.0+ policy. **Ratification by a named maintainer: PENDING.** Independent review: NOT performed. Signed ratification artifact: NONE held. This record does not claim ratification. |
| **Contract** | 2.0.0 (draft, unreleased): amended in place |
| **Date** | 2026-10-11 |
| **Questions** | closes OQ-CAL-1 |
| **Requirements** | CAL-013 (new, MUST); CAL-011 and CAL-012 unchanged |

## Context
DR-0010 recorded that outside Umm al-Qura's 1700-01-01..2300-12-31 the reference returned the Waqt day with an empty Hijri label and a `calendar_error`, while the independent
implementation returned `OUT_OF_RANGE`. Two `open` vectors recorded the proposed answer.

## Decision
The API policy is the contract rule: an operation that returns a Waqt day returns it unchanged (every instant, position and countdown), with an empty Hijri label and
`calendar_error` whose machine code is `OUT_OF_RANGE` and whose message says the date is outside the provider's supported range. No HTTP 500, no failure of the whole request.
`hijri.*` operations still refuse with `OUT_OF_RANGE` (CAL-011). The rule holds for the default provider and for an explicitly named `umm-al-qura`. Implemented in `waqt-core` (as
before), the API, `waqt-local`, the CLI (which crashed with a TypeError; it now prints the Waqt day and the notice), the reference adapter and the independent adapter.

## Evidence
Both implementations pass the promoted and the new vectors (see the regenerated report). The in-range first and last days (1700-01-01, 2300-12-31) are unchanged.

## Consequences
Independent implementation: now returns the Waqt day instead of `OUT_OF_RANGE`. COP gains an output field `calendar_error: {code}` (additive; a missing key equals null).
The two `open` vectors are moved from `open-questions.json` to `calendar-default.json` with the same ids and promoted to `exact`.

## Alternatives considered
Refuse with OUT_OF_RANGE everywhere: rejected by the owner (a calendar failure must not fail a Waqt computation).

## Configurability (religious / regional conventions)
An explicitly named provider with a wider range (for example `arithmetic-tabular`) is always available and labels these dates.

## Dissent and unresolved points
(1) The HTTP shape of `calendar_error` is not uniform: `/v1/waqt` returns an object `{provider, message}`, `/v1/calendar/convert` returns a string. This record does not change either shape
(that would be a further breaking change); the COP normalises both to `{code}`. (2) The independent implementation cannot compute *instants* after about the year 2255 (RANGE_ERROR),
so the upper boundary is covered through dates, not instants.

## Reopen when
A provider with a different range becomes the default, or the HTTP shape of `calendar_error` is unified.

## Vectors affected
`calendar-default.json` (2 moved and promoted, +14 new), `open-questions.json` (-2). Audit trail: `tools/migrate_err004_oqcal1.py`.
"""


def tracking_docs():
    p = CONF / "spec" / "OPEN-QUESTIONS.md"
    t = rd(p)
    t = t.replace("**16 resolved** (decision records", "**18 resolved** (decision records").replace("**12 deferred**,", "**10 deferred**,")
    t = t.replace("OQ-ERR-2, OQ-ERR-3, OQ-SCH-1..5 |", "OQ-ERR-2, OQ-ERR-3, OQ-SCH-1..5, **OQ-ERR-1** (DR-0011), **OQ-CAL-1** (DR-0012) |")
    t = t.replace("OQ-UND-1, OQ-ERR-1, OQ-PRV-1..3, **OQ-CAL-1** |", "OQ-UND-1, OQ-PRV-1..3 |")
    t = t.replace("| 95° or −5° silently yield garbage | add ranges to API.md |", "| 95° or −5° silently yield garbage | **RESOLVED by DR-0011**: 0 < angle <= 90, ratio > 0, else VALIDATION_ERROR; vectors now exact |")
    t = t.replace("tier open) | return th", "tier open) | **RESOLVED by DR-0012 (CAL-013)**: the vectors are now exact. Original proposal: return th")
    put(p, t)
    p = CONF / "DISAGREEMENTS.md"
    t = rd(p)
    t = t.replace("independent rejects with `VALIDATION_ERROR`. Five `open` vectors. | OQ-ERR-1 |", "independent rejects with `VALIDATION_ERROR`. Five `open` vectors. **RESOLVED (DR-0011, 2026-10-11): both reject with `VALIDATION_ERROR`; ranges 0 < angle <= 90, ratio > 0; vectors exact.** | OQ-ERR-1 |")
    put(p, t)


def decisions():
    for name, text in (("DR-0011.md", DR11), ("DR-0012.md", DR12)):
        p = CONF / "decisions" / name
        if not p.exists() or p.read_text(encoding="utf-8") != text:
            put(p, text)
    p = CONF / "decisions" / "README.md"
    s = rd(p)
    if "DR-0011" not in s:
        s = s.rstrip("\n") + (
            "\n| [DR-0011](DR-0011.md) | ERR-004: astronomy profile parameters are validated, with explicit ranges | ERR-004 (decided by owner instruction; ratification evidence NOT held) |\n"
            "| [DR-0012](DR-0012.md) | Out-of-range calendar dates never fail a Waqt computation (CAL-013) | OQ-CAL-1 (resolved; ratification evidence NOT held) |\n")
        put(p, s)


def changelog():
    p = CONF / "CHANGELOG.md"
    s = rd(p)
    if "DR-0011" in s:
        put(p, s.replace("Totals: 72 -> 73 requirements, 13 -> 12 unresolved questions.", "Closes OQ-ERR-1 and OQ-CAL-1. Totals: 72 -> 73 requirements, 13 -> 11 unresolved questions."))
        return
    marker = "**Amendment to the 2.0.0 draft (CCP-0001 / DR-0010"
    assert s.count(marker) == 1
    entry = ("**Amendment to the 2.0.0 draft (DR-0011, DR-0012; owner decisions of 2026-10-11, NOT independently reviewed, no signed ratification held):** "
             "ERR-004 is now normative with explicit ranges (fajr/isha 0 < x <= 90, asr > 0; NaN, infinity, non-numbers rejected with VALIDATION_ERROR) and has normative vectors; "
             "new MUST **CAL-013**: operations that return a Waqt day never fail because the Hijri provider cannot label the date (empty label + `calendar_error`), closing **OQ-CAL-1**. "
             "COP gains the `$nonfinite` wire convention and a `calendar_error: {code}` output. Closes OQ-ERR-1 and OQ-CAL-1. Totals: 72 -> 73 requirements, 13 -> 11 unresolved questions. "
             "Promoted in place (same ids, no recorded value changed): 5 `err/profile/*` and 2 OQ-CAL-1 vectors. Audit trail: `tools/migrate_err004_oqcal1.py`.\n\n")
    put(p, s.replace(marker, entry + marker, 1))


def main(check: bool) -> int:
    requirements(); errors_vectors(); default_vectors(); open_question(); cop(); tracking_docs(); decisions(); changelog()
    changed = []
    for p, text in PLANNED.items():
        if not p.exists() or p.read_text(encoding="utf-8") != text:
            changed.append(p.relative_to(CONF).as_posix())
            if not check:
                p.write_text(text, encoding="utf-8")
    print("changed:", sorted(changed) if changed else "nothing (already migrated)")
    return 1 if (check and changed) else 0


if __name__ == "__main__":
    sys.exit(main("--check" in sys.argv))

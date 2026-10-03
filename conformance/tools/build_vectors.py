#!/usr/bin/env python3
"""Build the Sprint 15 conformance vectors.

Where an expected value comes from (recorded per vector in `basis`):
  spec        derived by hand from the written specification
  closed-form computed here by an independent closed-form formula (JDN arithmetic), no waqt code
  oracle      JPL DE421 + Skyfield (independent-astronomy/skyfield_reference) -- a third party to BOTH implementations
  recorded    the reference implementation's own answer (only for `informative` / `open` vectors)

    python3 tools/build_vectors.py          (needs the repo's independent-astronomy oracle; run from conformance/)
"""
import datetime as dt
import json
import math
import os
import sys
import warnings
from zoneinfo import ZoneInfo

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
REPO = os.path.join(ROOT, "..")
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "independent-astronomy"))
sys.path.insert(0, os.path.join(ROOT, "adapters"))
OUT = os.path.join(ROOT, "vectors")
UTC = dt.timezone.utc

from requirements_catalog import R  # noqa: E402

REQ_IDS = {r["id"] for r in R}
SUITES = {}


def add(suite, vid, reqs, op, inp, expect, tier="exact", basis="spec", note=None, tolerance=None, ignore=None):
    assert all(r in REQ_IDS for r in reqs), reqs
    v = {"id": vid, "requirements": reqs, "op": op, "tier": tier, "basis": basis, "input": inp, "expect": expect}
    if note:
        v["note"] = note
    if tolerance:
        v["tolerance"] = tolerance
    if ignore:
        v["ignore"] = ignore
    SUITES.setdefault(suite, {"vectors": [], "metamorphic": []})["vectors"].append(v)


def addmm(suite, mid, reqs, kind, inp, **kw):
    assert all(r in REQ_IDS for r in reqs)
    SUITES.setdefault(suite, {"vectors": [], "metamorphic": []})["metamorphic"].append({"id": mid, "requirements": reqs, "kind": kind, "input": inp, **kw})


def ok(**o):
    return {"output": o}


def err(*codes):
    return {"error": {"code": list(codes)}}


# =============================================================== 1. Gregorian / time / errors
_IS = ["al-Ithnayn", "ath-Thulatha", "al-Arbiaa", "al-Khamis", "al-Jumuah", "as-Sabt", "al-Ahad"]
import calendar as _cal  # noqa: E402
for d, _w, _n, _l, _dim in [
    ("1970-01-01", 4, "al-Khamis", False, 31), ("2000-01-01", 6, "as-Sabt", True, 31), ("2024-02-29", 4, "al-Khamis", True, 29),
    ("1900-02-28", 3, "al-Arbiaa", False, 28), ("2100-02-28", 7, "al-Ahad", False, 28), ("2000-02-29", 2, "al-Ithnayn", True, 29),
    ("2026-09-20", 7, "al-Ahad", False, 30), ("0001-01-01", 1, "al-Ithnayn", False, 31), ("9999-12-31", 5, "al-Jumuah", False, 31),
    ("2026-02-28", 6, "as-Sabt", False, 28), ("1600-02-29", 2, "al-Ithnayn", True, 29), ("2026-06-19", 5, "al-Jumuah", False, 30)]:
    _d = dt.date.fromisoformat(d)
    wiso, wname, leap, dim = _d.isoweekday(), _IS[_d.weekday()], _cal.isleap(_d.year), _cal.monthrange(_d.year, _d.month)[1]
    add("gregorian-time", f"greg/{d}", ["GREG-001", "GREG-002", "GREG-003"], "gregorian.weekday", {"date": d},
        ok(weekday_iso=wiso, weekday_name_islamic=wname, is_leap_year=leap, days_in_month=dim), basis="spec")
for d in ["2026-02-30", "2026-13-01", "2026-00-10", "2026-1-1", "not-a-date", "2100-02-29", "1900-02-29"]:
    add("gregorian-time", f"greg/invalid/{d}", ["TIME-003"], "gregorian.weekday", {"date": d}, err("INVALID_DATE", "VALIDATION_ERROR"))
add("open-questions", "date/basic-format-20260101", ["TIME-003"], "gregorian.weekday", {"date": "20260101"}, err("INVALID_DATE", "VALIDATION_ERROR"), tier="open",
    note="PROPOSED: reject. The wire format is stated as YYYY-MM-DD; whether ISO-8601 basic format is tolerated is not stated. The reference accepts it (Python fromisoformat).")
add("open-questions", "instant/fraction-echo", ["TIME-001"], "instant.parse", {"value": "2026-09-19T15:42:00.123456Z"}, ok(instant="2026-09-19T15:42:00.123456+00:00"), tier="open",
    note="PROPOSED: sub-second input is preserved. The reference /v1/waqt response echoes the instant truncated to whole seconds.")
for v in ["2026-09-19T25:00:00Z", "2026-02-30T00:00:00Z", "yesterday", "", "2026-09-19T15:42:61Z", "2026-9-19T15:42:00Z"]:
    add("gregorian-time", f"instant/invalid/{v or 'empty'}", ["TIME-003"], "instant.parse", {"value": v}, err("INVALID_INSTANT", "VALIDATION_ERROR"))
for v, e in [("2026-09-19T15:42:00Z", "2026-09-19T15:42:00+00:00"), ("2026-09-19T15:42:00+00:00", "2026-09-19T15:42:00+00:00"),
             ("2026-09-19T18:42:00+03:00", "2026-09-19T15:42:00+00:00"), ("2026-09-19T05:42:00-10:00", "2026-09-19T15:42:00+00:00"),
             ("2026-12-31T23:59:59-05:00", "2027-01-01T04:59:59+00:00"),
             ("2026-09-20T05:12:00+13:30", "2026-09-19T15:42:00+00:00")]:
    add("gregorian-time", f"instant/offset/{v}", ["TIME-001"], "instant.parse", {"value": v}, ok(instant=e))
add("open-questions", "instant/naive", ["TIME-002"], "instant.parse", {"value": "2026-09-19T15:42:00"}, err("INVALID_INSTANT", "VALIDATION_ERROR"), tier="open",
    note="PROPOSED: reject. API.md says instant is 'ISO 8601 UTC' but never says whether an offset-less string is rejected or assumed UTC. The reference assumes UTC.")

# =============================================================== 2. Calendars (closed-form oracle for tabular)
def jdn(y, m, d):
    a = (14 - m) // 12; yy = y + 4800 - a; mm = m + 12 * a - 3
    return d + (153 * mm + 2) // 5 + 365 * yy + yy // 4 - yy // 100 + yy // 400 - 32045


def tab_to_jdn(y, m, d):   # Kuwaiti-algorithm civil tabular calendar (leap years 2,5,7,10,13,16,18,21,24,26,29)
    return d + math.ceil(29.5 * (m - 1)) + (y - 1) * 354 + (3 + 11 * y) // 30 + 1948440 - 1


def tab_from_date(date):
    j = jdn(date.year, date.month, date.day)
    y = (30 * (j - 1948440) + 10646) // 10631
    m = min(12, math.ceil((j - (29 + tab_to_jdn(y, 1, 1))) / 29.5) + 1)
    return y, m, j - tab_to_jdn(y, m, 1) + 1


def ordinal_to_date(j):
    return dt.date.fromordinal(j - 1721425)


MN = ["Muharram", "Safar", "Rabi al-Awwal", "Rabi al-Thani", "Jumada al-Awwal", "Jumada al-Thani", "Rajab", "Shaban", "Ramadan", "Shawwal", "Dhu al-Qadah", "Dhu al-Hijjah"]
for ds in ["2026-09-20", "2026-06-17", "2026-06-16", "2027-06-05", "2000-01-01", "1970-01-01", "1900-01-01", "2100-12-31", "2024-03-11", "2025-03-01", "0622-07-19",
           "2026-02-28", "2026-03-01", "2029-12-31", "1999-12-31", "2050-07-04"]:
    d = dt.date.fromisoformat(ds)
    y, m, dd = tab_from_date(d)
    add("calendar-core", f"tab/from/{ds}", ["CAL-001"], "hijri.from_gregorian", {"date": ds, "provider": "arithmetic-tabular"},
        ok(year=y, month=m, day=dd, date=f"{y:04d}-{m:02d}-{dd:02d}", month_name=MN[m - 1], provider="arithmetic-tabular"), basis="closed-form")
    add("calendar-core", f"tab/roundtrip/{ds}", ["CAL-003"], "hijri.to_gregorian", {"year": y, "month": m, "day": dd, "provider": "arithmetic-tabular"},
        ok(date=ds), basis="closed-form")
# leap pattern probe: lengths of Dhu al-Hijjah across a full 30-year cycle
for y in range(1, 31):
    L = 355 if y in (2, 5, 7, 10, 13, 16, 18, 21, 24, 26, 29) else 354
    add("calendar-core", f"tab/month12-length/{y}", ["CAL-002"], "hijri.month_length", {"year": y, "month": 12, "provider": "arithmetic-tabular"},
        ok(days=30 if L == 355 else 29), tier="open", basis="closed-form",
        note="PROPOSED leap pattern 2,5,7,10,13,16,18,21,24,26,29. CALENDARS.md says only 'classical 30-year-cycle'; several patterns exist.")
for y, m, d in [(1448, 2, 30), (1448, 13, 1), (1448, 0, 1), (1448, 1, 31), (1448, 1, 0), (0, 1, 1), (1448, 4, 0)]:
    add("calendar-core", f"tab/invalid/{y}-{m}-{d}", ["CAL-004"], "hijri.to_gregorian", {"year": y, "month": m, "day": d, "provider": "arithmetic-tabular"},
        err("INVALID_HIJRI_DATE", "VALIDATION_ERROR", "INVALID_DATE"),
        note="(1448,2,30): Safar 1448 has 29 days; the day must be rejected, not normalised into Rabi al-Awwal." if (m, d) == (2, 30) else None)
for prov in ("declared", "local-observation"):
    add("calendar-providers", f"reverse-unsupported/{prov}", ["CAL-009"], "hijri.to_gregorian", {"year": 1448, "month": 4, "day": 7, "provider": prov}, err("UNSUPPORTED_OPERATION"))
add("calendar-providers", "reverse-unsupported/aladhan", ["CAL-009"], "hijri.to_gregorian", {"year": 1448, "month": 4, "day": 7, "provider": "aladhan"}, err("UNSUPPORTED_OPERATION"))
add("calendar-providers", "unknown-provider", ["ERR-003"], "hijri.from_gregorian", {"date": "2026-09-20", "provider": "nope"}, err("UNKNOWN_CALENDAR_PROVIDER"))
# overrides
decl = {"override_date": "2026-09-20", "declared": {"year": 1448, "month": 4, "day": 10}}
add("calendar-providers", "declared/fires-on-exact-date", ["CAL-008"], "hijri.from_gregorian", {"date": "2026-09-20", "provider": "declared", "params": decl},
    ok(date="1448-04-10", provider="declared"))
add("calendar-providers", "declared/other-date-falls-back", ["CAL-008"], "hijri.from_gregorian", {"date": "2026-09-21", "provider": "declared", "params": decl},
    ok(date="1448-04-08", provider="arithmetic-tabular"), note="override applies to ONE date only; every other date is tabular")
add("calendar-providers", "declared/no-override-falls-back", ["CAL-008"], "hijri.from_gregorian", {"date": "2026-09-20", "provider": "declared"},
    ok(date="1448-04-07", provider="arithmetic-tabular"))
sight = {"override_date": "2026-09-20", "sighting": {"year": 1448, "month": 4, "day": 9}, "observed_at": "Addis Ababa"}
add("calendar-providers", "local-observation/fires-on-exact-date", ["CAL-008"], "hijri.from_gregorian", {"date": "2026-09-20", "provider": "local-observation", "params": sight},
    ok(date="1448-04-09", provider="local-observation"))
add("calendar-providers", "local-observation/other-date-falls-back", ["CAL-008"], "hijri.from_gregorian", {"date": "2026-09-19", "provider": "local-observation", "params": sight},
    ok(date="1448-04-06", provider="arithmetic-tabular"))
# UAQ validated anchors (documented in CALENDARS.md)
for (y, ds) in [(1438, "2016-10-02"), (1440, "2018-09-11"), (1441, "2019-08-31"), (1447, "2025-06-26")]:
    add("calendar-uaq", f"uaq/new-year/{y}", ["CAL-005"], "hijri.to_gregorian", {"year": y, "month": 1, "day": 1, "provider": "umm-al-qura"}, ok(date=ds))
    add("calendar-uaq", f"uaq/new-year-forward/{y}", ["CAL-005"], "hijri.from_gregorian", {"date": ds, "provider": "umm-al-qura"}, ok(year=y, month=1, day=1, provider="umm-al-qura"))
add("calendar-uaq", "uaq/day-before-new-year-1438", ["CAL-005"], "hijri.from_gregorian", {"date": "2016-10-01", "provider": "umm-al-qura"}, ok(year=1437, month=12, provider="umm-al-qura"))
for y in range(1430, 1461):
    for m in range(1, 13):
        pass
# round-trip + length invariants are generated as `year_table` sweeps (recorded, informative)
import reference_adapter as RA  # noqa: E402  (only used to RECORD informative sweeps)
for y in range(1420, 1461):
    r = RA.op_year_table({"year": y, "provider": "umm-al-qura"})
    add("calendar-uaq", f"uaq/year-table/{y}", ["CAL-007", "CAL-006"], "hijri.year_table", {"year": y, "provider": "umm-al-qura"}, ok(months=r["months"]),
        tier="informative", basis="recorded", note="reference-recorded: month starts and lengths. Disagreement is expected only in threshold-sensitive months (CALENDARS.md 'What this is not' 2).")
for ds in ["1650-01-01", "1699-12-31", "2301-01-01", "2500-01-01"]:
    try:
        r = RA.op_h_from({"date": ds, "provider": "umm-al-qura"}); e = ok(date=r["date"])
    except Exception as ex:
        e = err(getattr(ex, "code", "ERROR"))
    add("open-questions", f"uaq/range/{ds}", ["CAL-011"], "hijri.from_gregorian", {"date": ds, "provider": "umm-al-qura"}, e, tier="open", basis="recorded",
        note="Supported range of umm-al-qura is stated only as 'reliable roughly 1900-2100'; what happens outside is unspecified.")

# =============================================================== 3. Provider failure (LIVE-INTEGRATIONS.md)
def step(at, date, remote):
    return {"at_seconds": at, "date": date, "remote": remote}


OKH = lambda y, m, d: {"kind": "ok", "hijri": {"year": y, "month": m, "day": d}}
D0 = "2026-09-20"          # tabular 1448-04-07; UAQ 1448-04-09
FB = lambda date, reason: {"date": date, "provider": "umm-al-qura", "source": "local-fallback", "fallback_reason": reason}
for kind, reason, reqs in [({"kind": "timeout"}, "timeout", "PRV-001"), ({"kind": "network-error"}, "network-error", "PRV-001"),
                            ({"kind": "http", "status": 429}, "upstream-rate-limited", "PRV-001"), ({"kind": "http", "status": 500}, "upstream-server-error", "PRV-001"),
                            ({"kind": "http", "status": 503}, "upstream-server-error", "PRV-001"), ({"kind": "http", "status": 404}, "upstream-rejected", "PRV-002"),
                            ({"kind": "http", "status": 400}, "upstream-rejected", "PRV-002"), ({"kind": "malformed"}, "malformed-response", "PRV-002"),
                            ({"kind": "oversize"}, "malformed-response", "PRV-002"), ({"kind": "echo-mismatch", "hijri": {"year": 1448, "month": 4, "day": 9}}, "date-mismatch", "PRV-002"),
                            (OKH(1448, 4, 20), "implausible-response", "PRV-002")]:
    tag = kind["kind"] + (str(kind.get("status", "")) if kind["kind"] == "http" else "")
    add("provider-failure", f"aladhan/single/{tag}", [reqs, "PRV-006"], "hijri.provider_scenario", {"steps": [step(0, D0, kind)]}, ok(steps=[FB(D0, reason)]))
add("provider-failure", "aladhan/ok", ["PRV-004"], "hijri.provider_scenario", {"steps": [step(0, D0, OKH(1448, 4, 9))]},
    ok(steps=[{"date": D0, "provider": "aladhan", "source": "remote", "fallback_reason": None}]))
add("provider-failure", "aladhan/ok-within-3-days-is-plausible", ["PRV-002"], "hijri.provider_scenario", {"steps": [step(0, D0, OKH(1448, 4, 10))]},
    ok(steps=[{"date": D0, "provider": "aladhan", "source": "remote", "fallback_reason": None}]), note="remote 1448-04-10 is +3 days from tabular 1448-04-07: the limit is inclusive")
add("provider-failure", "aladhan/window-low", ["PRV-003"], "hijri.provider_scenario", {"steps": [step(0, "1899-12-31", OKH(1317, 8, 28))]}, ok(steps=[FB("1899-12-31", "date-outside-remote-window")]))
add("provider-failure", "aladhan/window-high", ["PRV-003"], "hijri.provider_scenario", {"steps": [step(0, "2077-01-01", OKH(1498, 6, 1))]}, ok(steps=[FB("2077-01-01", "date-outside-remote-window")]))
add("provider-failure", "aladhan/window-edge-low-inside", ["PRV-003"], "hijri.provider_scenario", {"steps": [step(0, "1900-01-01", {"kind": "timeout"})]}, ok(steps=[FB("1900-01-01", "timeout")]),
    note="1900-01-01 is inside the window, so a remote call is attempted (and fails)")
add("provider-failure", "aladhan/disabled", ["PRV-003"], "hijri.provider_scenario", {"config": {"enabled": False}, "steps": [step(0, D0, OKH(1448, 4, 9))]}, ok(steps=[FB(D0, "disabled")]))
add("provider-failure", "aladhan/cache-hit-within-ttl", ["PRV-004"], "hijri.provider_scenario",
    {"steps": [step(0, D0, OKH(1448, 4, 9)), step(3600, D0, {"kind": "timeout"})]},
    ok(steps=[{"date": D0, "provider": "aladhan", "source": "remote", "fallback_reason": None}, {"date": D0, "provider": "aladhan", "source": "remote", "fallback_reason": None}]))
add("provider-failure", "aladhan/stale-if-error", ["PRV-004"], "hijri.provider_scenario",
    {"steps": [step(0, D0, OKH(1448, 4, 9)), step(13 * 3600, D0, {"kind": "timeout"})]},
    ok(steps=[{"date": D0, "provider": "aladhan", "source": "remote", "fallback_reason": None}, {"date": D0, "provider": "aladhan", "source": "remote-stale", "fallback_reason": "timeout"}]))
add("provider-failure", "aladhan/stale-expires-after-7-days", ["PRV-004"], "hijri.provider_scenario",
    {"steps": [step(0, D0, OKH(1448, 4, 9)), step(8 * 86400, D0, {"kind": "timeout"})]},
    ok(steps=[{"date": D0, "provider": "aladhan", "source": "remote", "fallback_reason": None}, FB(D0, "timeout")]))
add("provider-failure", "aladhan/circuit-open-after-hard-failure", ["PRV-005"], "hijri.provider_scenario",
    {"steps": [step(0, D0, {"kind": "timeout"}), step(10, "2026-09-21", OKH(1448, 4, 10)), step(31, "2026-09-21", OKH(1448, 4, 10))]},
    ok(steps=[FB(D0, "timeout"), FB("2026-09-21", "circuit-open"), {"date": "2026-09-21", "provider": "aladhan", "source": "remote", "fallback_reason": None}]))
add("provider-failure", "aladhan/retry-after-honoured-and-capped", ["PRV-005"], "hijri.provider_scenario",
    {"steps": [step(0, D0, {"kind": "http", "status": 429, "retry_after": 3600}), step(599, "2026-09-21", OKH(1448, 4, 10)), step(601, "2026-09-21", OKH(1448, 4, 10))]},
    ok(steps=[FB(D0, "upstream-rate-limited"), FB("2026-09-21", "circuit-open"), {"date": "2026-09-21", "provider": "aladhan", "source": "remote", "fallback_reason": None}]),
    note="Retry-After 3600 s is capped at 600 s")
add("provider-failure", "aladhan/retry-after-short", ["PRV-005"], "hijri.provider_scenario",
    {"steps": [step(0, D0, {"kind": "http", "status": 429, "retry_after": 5}), step(4, "2026-09-21", OKH(1448, 4, 10)), step(6, "2026-09-21", OKH(1448, 4, 10))]},
    ok(steps=[FB(D0, "upstream-rate-limited"), FB("2026-09-21", "circuit-open"), {"date": "2026-09-21", "provider": "aladhan", "source": "remote", "fallback_reason": None}]),
    tier="open", note="LIVE-INTEGRATIONS says 'no request for 30 s (or AlAdhan's Retry-After, capped at 10 min)'. Whether a SHORT Retry-After shortens the 30 s cooldown is not stated. Proposed: Retry-After replaces it.")
add("provider-failure", "aladhan/three-soft-failures-open-circuit", ["PRV-007"], "hijri.provider_scenario",
    {"steps": [step(0, "2026-09-20", {"kind": "http", "status": 404}), step(1, "2026-09-21", {"kind": "http", "status": 404}), step(2, "2026-09-22", {"kind": "http", "status": 404}),
               step(3, "2026-09-23", OKH(1448, 4, 12))]},
    ok(steps=[FB("2026-09-20", "upstream-rejected"), FB("2026-09-21", "upstream-rejected"), FB("2026-09-22", "upstream-rejected"), FB("2026-09-23", "circuit-open")]), tier="open",
    note="Spec: 'three consecutive soft failures also open it'. Whether the third failure itself opens it for the NEXT call (proposed) is implied but not exact.")
add("provider-failure", "aladhan/outbound-budget", ["PRV-007"], "hijri.provider_scenario",
    {"config": {"requests_per_minute": 2}, "steps": [step(0, "2026-09-20", OKH(1448, 4, 9)), step(1, "2026-09-21", OKH(1448, 4, 10)), step(2, "2026-09-22", OKH(1448, 4, 11))]},
    ok(steps=[{"date": "2026-09-20", "provider": "aladhan", "source": "remote", "fallback_reason": None}, {"date": "2026-09-21", "provider": "aladhan", "source": "remote", "fallback_reason": None}, FB("2026-09-22", "outbound-rate-limited")]),
    tier="open", note="token-bucket details (refill granularity) are not specified")

# =============================================================== 4. Day model: DE421 oracle vectors
from skyfield_reference.events import compute_day_events  # noqa: E402

EV = ["fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha"]
PLACES = {  # id: (lat, lon, elev, tz)
    "addis": (9.0192, 38.7525, 0, "Africa/Addis_Ababa"), "makkah": (21.4225, 39.8262, 0, "Asia/Riyadh"), "cairo": (30.0444, 31.2357, 0, "Africa/Cairo"),
    "jakarta": (-6.2088, 106.8456, 0, "Asia/Jakarta"), "quito": (-0.1807, -78.4678, 0, "America/Guayaquil"), "london": (51.5074, -0.1278, 0, "Europe/London"),
    "newyork": (40.7128, -74.0060, 0, "America/New_York"), "sydney": (-33.8688, 151.2093, 0, "Australia/Sydney"), "capetown": (-33.9249, 18.4241, 0, "Africa/Johannesburg"),
    "punta-arenas": (-53.1638, -70.9171, 0, "America/Punta_Arenas"), "reykjavik": (64.1466, -21.9426, 0, "Atlantic/Reykjavik"), "tromso": (69.6492, 18.9553, 0, "Europe/Oslo"),
    "kiritimati": (1.8721, -157.4278, 0, "Pacific/Kiritimati"), "apia": (-13.8333, -171.7667, 0, "Pacific/Apia"), "urumqi": (43.8256, 87.6168, 0, "Asia/Urumqi"),
    "kathmandu": (27.7172, 85.3240, 0, "Asia/Kathmandu"), "anchorage": (61.2181, -149.9003, 0, "America/Anchorage"), "chatham": (-43.95, -176.55, 0, "Pacific/Chatham"),
    "auckland": (-36.8485, 174.7633, 0, "Pacific/Auckland"), "mumbai": (19.0760, 72.8777, 0, "Asia/Kolkata"), "bogota-high": (4.711, -74.0721, 2640, "America/Bogota"),
}
PLAN = [  # (place, date) : equinox / solstice / DST / edge dates
    ("addis", "2026-03-20"), ("addis", "2026-09-19"), ("makkah", "2026-06-21"), ("makkah", "2026-12-21"), ("cairo", "2026-06-21"), ("jakarta", "2026-12-21"),
    ("quito", "2026-09-23"), ("london", "2026-03-29"), ("london", "2026-06-21"), ("london", "2026-10-25"), ("london", "2026-12-21"),
    ("newyork", "2026-03-08"), ("newyork", "2026-11-01"), ("sydney", "2026-04-05"), ("sydney", "2026-10-04"), ("capetown", "2026-06-21"),
    ("punta-arenas", "2026-12-21"), ("reykjavik", "2026-06-21"), ("reykjavik", "2026-03-20"), ("tromso", "2026-06-21"), ("tromso", "2026-12-21"), ("tromso", "2026-03-20"),
    ("kiritimati", "2026-09-19"), ("kiritimati", "2026-06-21"), ("apia", "2026-03-20"), ("apia", "2026-12-30"), ("urumqi", "2026-06-21"), ("kathmandu", "2026-03-20"),
    ("anchorage", "2026-06-21"), ("anchorage", "2026-12-21"), ("chatham", "2026-09-27"), ("auckland", "2026-09-27"), ("mumbai", "2026-06-21"), ("bogota-high", "2026-03-20"),
]
PROFILE = {"fajr_angle_deg": 18.0, "isha_angle_deg": 17.0, "asr_shadow_ratio": 1.0}
_lcache = {}


def listing(pid, k, prof=None):
    prof = prof or PROFILE
    """oracle events of the transit-anchored solar day whose transit has local civil date k (a datetime.date)"""
    key = (pid, k, prof['fajr_angle_deg'], prof['isha_angle_deg'], prof['asr_shadow_ratio'])
    if key in _lcache:
        return _lcache[key]
    lat, lon, el, tz = PLACES[pid]
    zi = ZoneInfo(tz)
    res = None
    for d in (k - dt.timedelta(days=1), k, k + dt.timedelta(days=1)):
        ev = compute_day_events(d, lat, lon, float(el), prof['fajr_angle_deg'], prof['isha_angle_deg'], prof['asr_shadow_ratio'])
        if ev.dhuhr.astimezone(zi).date() == k:
            res = ev; break
    _lcache[key] = res
    return res


def maghrib(pid, k, prof=None):
    ev = listing(pid, k, prof)
    return ev.maghrib if ev else None


def oracle_day(pid, t, prof=None):
    """-> dict(open, close, idx, events{name: dt|None}) or None when undefined"""
    zi = ZoneInfo(PLACES[pid][3])
    X = t.astimezone(zi).date()
    j = None
    for kk in range(1, -3, -1):
        k = X + dt.timedelta(days=kk)
        m = maghrib(pid, k, prof)
        if m is not None and m <= t:
            j = k; break
    if j is None:
        return None
    k = j + dt.timedelta(days=1)
    o, c = maghrib(pid, j, prof), maghrib(pid, k, prof)
    if o is None or c is None:
        return None
    ev = listing(pid, k, prof)
    return {"open": o, "close": c, "idx": k, "events": {n: getattr(ev, n) for n in EV}, "label": c.astimezone(zi).date()}


def iso(d):
    return d.astimezone(UTC).isoformat()


WD = ["al-Ithnayn", "ath-Thulatha", "al-Arbiaa", "al-Khamis", "al-Jumuah", "as-Sabt", "al-Ahad"]


def band(ev, lat):
    a = abs(lat)
    if ev in ("dhuhr", "asr", "sunrise", "maghrib"):
        return 5 if a <= 60 else 20
    return 10 if a <= 45 else 30 if a <= 55 else 120


def day_vector(pid, date, local_hhmm, tag, prof=None):
    prof = prof or PROFILE
    lat, lon, el, tz = PLACES[pid]
    zi = ZoneInfo(tz)
    h, m = map(int, local_hhmm.split(":"))
    t = dt.datetime.combine(dt.date.fromisoformat(date), dt.time(h, m), tzinfo=zi).astimezone(UTC)
    d = oracle_day(pid, t, prof)
    inp = {"location": {"lat": lat, "lon": lon, "elevation_m": float(el)}, "instant": iso(t), "timezone": tz, "profile": prof, "calendar": {"provider": "arithmetic-tabular"}}
    vid = f"day/{pid}/{date}/{tag}"
    if d is None:
        add("day-model", vid, ["UND-001"], "waqt.compute", inp, ok(status="UNDEFINED", events=[]), tier="tolerance", basis="oracle",
            note="no Maghrib bounds this instant (polar day or night) -> UNDEFINED, with no substituted time")
        return
    y, mo, dd = tab_from_date(d["label"])
    paths = {r"\$\.day\.(open|close)": {"instant_s": band("maghrib", lat)}, r"\$\.day\.length_seconds": {"abs": 2 * band("maghrib", lat)},
             r"\$\.position\.seconds": {"abs": 2 * band("maghrib", lat)}}
    evs, und = [], []
    for i_, n in enumerate(EV):
        e = d["events"][n]
        if e is None:
            und.append({"name": n}); continue
        i = len(evs)
        evs.append({"name": n, "instant": iso(e), "reading_seconds": (e - d["open"]).total_seconds(), "local_date": e.astimezone(zi).date().isoformat()})
        paths[rf"\$\.events\[{i}\]\.instant"] = {"instant_s": band(n, lat)}
        paths[rf"\$\.events\[{i}\]\.reading_seconds"] = {"abs": band(n, lat) + band("maghrib", lat)}
    reqs = ["DAY-001", "DAY-004", "DAY-005", "DAY-006", "DAY-007", "EVT-001", "EVT-002"]
    if und:
        reqs.append("UND-002")
    if pid.startswith("sweep"):
        reqs.append("UND-003")
    if any(e["local_date"] != d["label"].isoformat() for e in evs if e["name"] not in ("maghrib",)) or pid in ("reykjavik",):
        reqs.append("EVT-004")
    out = {"status": "OK", "day": {"open": iso(d["open"]), "close": iso(d["close"]), "length_seconds": (d["close"] - d["open"]).total_seconds()},
           "position": {"seconds": (t - d["open"]).total_seconds()}, "events": evs, "undefined_events": und}
    reqs = [r for r in reqs if r not in ("DAY-004",)]
    add("day-model", "label/" + vid[4:], ["DAY-004", "DAY-007"], "waqt.compute", inp,
        ok(status="OK", hijri={"date": f"{y:04d}-{mo:02d}-{dd:02d}"}, weekday=WD[d["label"].weekday()]), tier="exact", basis="closed-form",
        note="label = Hijri date and weekday of the civil date (in the location's IANA zone) of the CLOSING Maghrib instant; the date comes from the DE421 closing Maghrib and Python's zoneinfo")
    add("day-model", vid, reqs, "waqt.compute", inp, {"output": out}, tier="tolerance", basis="oracle",
        tolerance={"paths": paths, "default": {"instant_s": 5, "abs": 1e-6}}, ignore=["reading_display", "display"],
        note=f"local {local_hhmm} on {date}; DE421 oracle; bands: horizon/transit events {band('dhuhr', lat)} s, twilight {band('fajr', lat)} s")


for pid, date in PLAN:
    for hhmm, tag in (("00:30", "after-midnight"), ("13:00", "midday"), ("23:30", "late-evening")):
        day_vector(pid, date, hhmm, tag)
# event-existence at the edge of the habitable latitudes: lon 0, UTC, local noon; truth = DE421
for lat in (50.0, 54.0, 57.0, 60.0, 62.0, 64.0, 65.5, 66.5, 67.5, 68.5, 70.0):
    PLACES[f"sweep{lat}"] = (lat, 0.0, 0, "UTC")
    for date in ("2026-06-21", "2026-12-21", "2026-03-20"):
        day_vector(f"sweep{lat}", date, "12:00", "noon")

PROFILES = {"hanafi-asr": {"fajr_angle_deg": 18.0, "isha_angle_deg": 17.0, "asr_shadow_ratio": 2.0},
            "isna-15": {"fajr_angle_deg": 15.0, "isha_angle_deg": 15.0, "asr_shadow_ratio": 1.0},
            "egyptian-19.5": {"fajr_angle_deg": 19.5, "isha_angle_deg": 17.5, "asr_shadow_ratio": 1.0}}
for pname, prof in PROFILES.items():
    for pid, date in (("addis", "2026-09-19"), ("makkah", "2026-12-21"), ("london", "2026-03-20"), ("newyork", "2026-06-21"), ("sydney", "2026-12-21")):
        day_vector(pid, date, "13:00", "profile-" + pname, prof)

# =============================================================== 5. Label semantics at the date line / after-midnight sunsets
for pid, date, why in [("kiritimati", "2026-09-20", "UTC+14: civil date and longitude-based solar date differ by one day"),
                       ("kiritimati", "2026-06-15", "same, northern summer"), ("apia", "2026-03-21", "UTC+13/+14 zone east of the date line"),
                       ("addis", "2026-09-20", "control: civil and solar date agree")]:
    d0 = dt.date.fromisoformat(date)
    lat, lon, el, tz = PLACES[pid]
    d = oracle_day(pid, dt.datetime.combine(d0, dt.time(12, 0), tzinfo=ZoneInfo(tz)).astimezone(UTC))
    y, mo, dd = tab_from_date(d0)
    add("day-model", f"interop/date-to-waqt-day/{pid}/{date}", ["INT-002", "DAY-007"], "calendar.gregorian_date_to_waqt_day",
        {"date": date, "location": {"lat": lat, "lon": lon}, "timezone": tz},
        ok(resolved=True, close_civil_date=date), basis="spec",
        note="the Waqt day resolved for civil date " + date + " must close on that civil date. " + why)
    add("day-model", f"label/date-to-waqt-day/{pid}/{date}", ["DAY-004", "DAY-007"], "calendar.gregorian_date_to_waqt_day",
        {"date": date, "location": {"lat": lat, "lon": lon}, "timezone": tz},
        ok(resolved=True, hijri_date=f"{y:04d}-{mo:02d}-{dd:02d}", weekday=WD[d0.weekday()]), basis="spec",
        note="The Waqt day whose closing Maghrib falls on civil date " + date + " must carry THAT date's Hijri label and weekday. " + why)
    t = dt.datetime.combine(d0, dt.time(12, 0), tzinfo=ZoneInfo(tz)).astimezone(UTC)
    add("day-model", f"label/compute-midday/{pid}/{date}", ["DAY-004", "DAY-007"], "waqt.compute",
        {"location": {"lat": lat, "lon": lon}, "instant": iso(t), "timezone": tz, "profile": PROFILE, "calendar": {"provider": "arithmetic-tabular"}},
        ok(status="OK", hijri={"date": f"{y:04d}-{mo:02d}-{dd:02d}"}, weekday=WD[d0.weekday()]), basis="spec",
        note="local noon of civil date " + date + " lies inside the day that closes that evening, so its label is this civil date's. " + why)
# Maghrib after local midnight (Reykjavik, June): the closing Maghrib INSTANT's civil date is the label
d_r = oracle_day("reykjavik", dt.datetime(2026, 6, 21, 12, 0, tzinfo=UTC))
y, mo, dd = tab_from_date(d_r["label"])
add("day-model", "label/after-midnight-maghrib/reykjavik", ["DAY-004"], "waqt.compute",
    {"location": {"lat": 64.1466, "lon": -21.9426}, "instant": "2026-06-21T12:00:00+00:00", "timezone": "Atlantic/Reykjavik", "profile": PROFILE, "calendar": {"provider": "arithmetic-tabular"}},
    ok(status="OK", hijri={"date": f"{y:04d}-{mo:02d}-{dd:02d}"}, weekday=WD[d_r["label"].weekday()]), tier="exact", basis="oracle", note=f"Maghrib {iso(d_r['close'])} is AFTER local midnight; the label is the civil date of that instant ({d_r['label']}), not the date of the day's transit")

# =============================================================== 6. Open question: next_event semantics
add("open-questions", "next-event/tonights-isha", ["EVT-007"], "waqt.compute",
    {"location": {"lat": 9.0192, "lon": 38.7525}, "instant": "2026-09-19T15:42:00+00:00", "timezone": "Africa/Addis_Ababa", "profile": PROFILE, "calendar": {"provider": "arithmetic-tabular"}},
    ok(next_event={"name": "isha", "instant": "2026-09-19T16:28:28+00:00"}), tier="open", tolerance={"default": {"instant_s": 3, "abs": 3}},
    note="Right after Maghrib the next event by OCCURRENCE is tonight's Isha (SCHEDULING.md 5 says exactly this for the scheduling layer). The waqt.compute response lists only the new day's events, so a listing-based next_event skips it and returns tomorrow's Fajr.")

add("open-questions", "asr/degenerate-67N-solstice", ["UND-004"], "waqt.compute",
    {"location": {"lat": 67.0, "lon": 0.0}, "instant": "2026-12-21T12:00:00+00:00", "timezone": "UTC", "profile": PROFILE, "calendar": {"provider": "arithmetic-tabular"}},
    ok(status="OK", undefined_events=[{"name": "asr"}]), tier="open", basis="oracle",
    note="Sun's noon altitude is -0.44 deg, equal to the (degenerate, negative) Asr target. PROPOSED: Asr is undefined when the Sun is not above the geometric horizon at transit. The independent implementation first returned an Asr here and was changed AFTER the latitude sweep exposed it.")

# =============================================================== 7. Errors
for tag, inp, codes, req in [
    ("lat-91", {"location": {"lat": 91, "lon": 0}}, ("VALIDATION_ERROR",), "ERR-001"), ("lat--91", {"location": {"lat": -91, "lon": 0}}, ("VALIDATION_ERROR",), "ERR-001"),
    ("lon-181", {"location": {"lat": 0, "lon": 181}}, ("VALIDATION_ERROR",), "ERR-001"), ("lon--181", {"location": {"lat": 0, "lon": -181}}, ("VALIDATION_ERROR",), "ERR-001"),
    ("tz-unknown", {"location": {"lat": 0, "lon": 0}, "timezone": "Mars/Base"}, ("VALIDATION_ERROR", "UNKNOWN_TIMEZONE", "INVALID_TIMEZONE"), "ERR-002"),
    ("provider-unknown", {"location": {"lat": 0, "lon": 0}, "calendar": {"provider": "nope"}}, ("UNKNOWN_CALENDAR_PROVIDER",), "ERR-003"),
    ("instant-garbage", {"location": {"lat": 0, "lon": 0}, "instant": "garbage"}, ("INVALID_INSTANT",), "TIME-003")]:
    base = {"location": {"lat": 0, "lon": 0}, "instant": "2026-09-19T15:42:00+00:00", "timezone": "UTC", "profile": PROFILE, "calendar": {"provider": "arithmetic-tabular"}}
    add("errors", f"err/{tag}", [req], "waqt.compute", {**base, **inp}, err(*codes),
        note="a bad time zone must be a client error, not INTERNAL_ERROR" if tag == "tz-unknown" else None)
for tag, prof in [("fajr-95", {"fajr_angle_deg": 95}), ("fajr-negative", {"fajr_angle_deg": -5}), ("isha-zero", {"isha_angle_deg": 0}), ("asr-zero", {"asr_shadow_ratio": 0}), ("asr-negative", {"asr_shadow_ratio": -1})]:
    add("errors", f"err/profile/{tag}", ["ERR-004"], "waqt.compute", {"location": {"lat": 0, "lon": 0}, "instant": "2026-09-19T15:42:00+00:00", "timezone": "UTC", "profile": {**PROFILE, **prof}},
        err("VALIDATION_ERROR"), tier="open", note="PROPOSED: reject non-physical parameters. The specification gives the units but no valid range; the reference accepts all of these silently.")

# =============================================================== 8. Metamorphic
NOW = {"addis": "2026-09-19T15:42:00+00:00", "london-long": "2026-06-21T12:00:00+00:00", "kiritimati": "2026-09-19T23:00:00+00:00", "reykjavik": "2026-06-21T12:00:00+00:00",
       "newyork-dst": "2026-03-08T12:00:00+00:00", "makkah": "2026-12-21T12:00:00+00:00", "sydney": "2026-04-05T02:00:00+00:00"}
for tag, pid, inst in [("addis", "addis", NOW["addis"]), ("london", "london", NOW["london-long"]), ("kiritimati", "kiritimati", NOW["kiritimati"]), ("reykjavik", "reykjavik", NOW["reykjavik"]),
                       ("newyork-dst", "newyork", NOW["newyork-dst"]), ("makkah", "makkah", NOW["makkah"]), ("sydney-dst", "sydney", NOW["sydney"]), ("punta-arenas", "punta-arenas", "2026-12-21T12:00:00+00:00")]:
    lat, lon, el, tz = PLACES[pid]
    inp = {"location": {"lat": lat, "lon": lon, "elevation_m": float(el)}, "instant": inst, "timezone": tz, "profile": PROFILE, "calendar": {"provider": "arithmetic-tabular"}}
    addmm("metamorphic", f"mm/tiling/{tag}", ["DAY-001", "DAY-002", "DAY-003", "DAY-004", "DAY-005", "EVT-002", "EVT-003"], "tiling", inp, tolerance_s=0.001, position_tol_s=0.001)
    addmm("metamorphic", f"mm/invariance/{tag}", ["DAY-008"], "instant-invariance", inp, fractions=[0.0005, 0.3, 0.6, 0.9995])
    if tag in ("addis", "london", "kiritimati", "makkah"):
        addmm("metamorphic", f"mm/profile-isolation/{tag}", ["EVT-005"], "profile-isolation", inp, change={"fajr_angle_deg": 15.0, "isha_angle_deg": 15.0, "asr_shadow_ratio": 2.0})
        addmm("metamorphic", f"mm/provider-isolation/{tag}", ["CAL-010"], "provider-isolation", inp, providers=["umm-al-qura", "declared", "local-observation"])
        addmm("metamorphic", f"mm/elevation/{tag}", ["EVT-006"], "elevation-isolation", inp, elevation_m=2400.0)

for prov, years in (("umm-al-qura", [1438, 1440, 1441, 1445, 1446, 1447, 1448, 1450]), ("arithmetic-tabular", [1, 2, 29, 30, 1400, 1448, 1500])):
    for y in years:
        addmm("metamorphic", f"mm/calendar-consistency/{prov}/{y}", ["CAL-006", "CAL-003"] if prov == "umm-al-qura" else ["CAL-003"], "calendar-consistency", {"year": y, "provider": prov})

# =============================================================== 9. Scheduling over live astronomy (reference-recorded, tolerance)
from datetime import datetime  # noqa: E402

def live_ctx(pid, prov="arithmetic-tabular"):
    lat, lon, el, tz = PLACES[pid]
    return {"location": {"lat": lat, "lon": lon, "elevation_m": float(el)}, "timezone": tz, "profile": PROFILE, "calendar": {"provider": prov}}


ev = lambda n, d=0: {"type": "event", "name": n, "day": d}
LIVE = [
    ("addis", "2026-09-19T15:42:00+00:00", {"op": "resolve_point", "point": ev("fajr")}, "SCH-001"),
    ("addis", "2026-09-19T15:42:00+00:00", {"op": "resolve_point", "point": {"type": "offset", "base": {"type": "next_event", "name": "maghrib"}, "minutes": -30}}, "SCH-001"),
    ("addis", "2026-09-19T15:42:00+00:00", {"op": "resolve_interval", "interval": {"type": "interval", "start": ev("fajr"), "end": ev("sunrise"), "start_inclusive": True, "end_inclusive": False}}, "SCH-002"),
    ("addis", "2026-09-19T15:42:00+00:00", {"op": "event_position", "name": "isha"}, "SCH-006"),
    ("addis", "2026-09-19T15:42:00+00:00", {"op": "day_bounds"}, "SCH-006"),
    ("addis", "2026-09-19T15:42:00+00:00", {"op": "next_event"}, "SCH-006"),
    ("addis", "2026-09-20T20:00:00+00:00", {"op": "until", "name": "fajr"}, "SCH-006"),
    ("addis", "2026-09-20T20:00:00+00:00", {"op": "since", "name": "isha"}, "SCH-006"),
    ("addis", "2026-09-19T15:42:00+00:00", {"op": "classify_span", "start": "2026-09-19T14:00:00+00:00", "end": "2026-09-19T17:00:00+00:00"}, "SCH-005"),
    ("addis", "2026-09-19T15:42:00+00:00", {"op": "classify_span", "start": "2026-09-19T20:30:00+00:00", "end": "2026-09-19T22:30:00+00:00"}, "SCH-005"),
    ("addis", "2026-09-19T15:42:00+00:00", {"op": "classify_span", "start": "2026-09-19T20:30:00+00:00", "end": "2026-09-20T01:00:00+00:00"}, "SCH-005"),
    ("london", "2026-06-21T12:00:00+00:00", {"op": "resolve_point", "point": ev("fajr")}, "SCH-004"),
    ("london", "2026-06-21T12:00:00+00:00", {"op": "until", "name": "fajr", "on_undefined": "skip"}, "SCH-004"),
    ("tromso", "2026-06-21T12:00:00+00:00", {"op": "day_bounds"}, "SCH-004"),
    ("london", "2026-06-21T12:00:00+00:00", {"op": "next_event"}, "SCH-004"),
    ("kiritimati", "2026-09-19T23:00:00+00:00", {"op": "day_bounds"}, "SCH-006"),
    ("reykjavik", "2026-06-21T12:00:00+00:00", {"op": "next_event"}, "SCH-006"),
]
for i, (pid, anchor, op, rq) in enumerate(LIVE):
    c = live_ctx(pid)
    rec = RA.op_schedule({"context": c, "anchor": anchor, "operation": op})
    add("scheduling-live", f"live/{i:02d}-{pid}-{op['op']}", [rq, "SCH-008"], "schedule.run", {"context": c, "anchor": anchor, "operation": op}, {"output": rec},
        tier="informative" if pid == "kiritimati" else "tolerance", basis="recorded", tolerance={"default": {"instant_s": 5, "abs": 5}}, ignore=["description", "reason", "display"],
        note="recorded from the reference (tolerance 5 s absorbs the ~1 s reference/DE421 offset)")

_leg = json.load(open(os.path.join(REPO, "tests", "vectors", "scheduling_vectors.json")))["vectors"][0]
_ctx, _anc = _leg["context"], _leg["anchor"]
_iv = lambda a, b, **k: {"type": "interval", "start": {"type": "instant", "value": a}, "end": {"type": "instant", "value": b}, **k}
_A, _B = "2026-09-19T16:00:00+00:00", "2026-09-19T17:00:00+00:00"
for tag, inst, rel, inside in [("at-start", _A, "inside", True), ("just-before-start", "2026-09-19T15:59:59.999999+00:00", "before_window", False),
                               ("at-end", _B, "after_window", False), ("just-before-end", "2026-09-19T16:59:59.999999+00:00", "inside", True)]:
    add("scheduling-defaults", f"sch-default/interval-half-open/{tag}", ["SCH-002"], "schedule.run",
        {"context": _ctx, "anchor": _anc, "operation": {"op": "evaluate", "interval": _iv(_A, _B), "instant": inst}},
        ok(status="OK", inside=inside, relation=rel), note="no start_inclusive/end_inclusive given: SCHEDULING.md 4 'defaults to half-open [start, end)'")
add("scheduling-defaults", "sch-default/zero-length-is-empty", ["SCH-002"], "schedule.run",
    {"context": _ctx, "anchor": _anc, "operation": {"op": "resolve_interval", "interval": _iv(_A, _A)}}, ok(status="NO_VALID_WINDOW"))
add("scheduling-defaults", "sch-default/closed-zero-length-is-valid", ["SCH-002"], "schedule.run",
    {"context": _ctx, "anchor": _anc, "operation": {"op": "resolve_interval", "interval": _iv(_A, _A, start_inclusive=True, end_inclusive=True)}}, ok(status="OK", duration_seconds=0))
add("scheduling-defaults", "sch-default/classify-span-end-exclusive", ["SCH-005"], "schedule.run",
    {"context": _ctx, "anchor": _anc, "operation": {"op": "classify_span", "start": (dt.datetime.fromisoformat(_ctx["days"][_ctx["anchor_index"]]["open"]) + dt.timedelta(hours=1)).isoformat(), "end": _ctx["days"][_ctx["anchor_index"]]["close"]}},
    ok(status="OK", crosses_maghrib=False), note="a span that ends exactly at the closing Maghrib never reaches the next day (half-open)")

# provider swap for the Hijri label of a day, via institutional rules computed WITHOUT tables: checks CAL-001/CAL-007 interplay
for y in (1446, 1447, 1448, 1449):
    last = tab_to_jdn(y + 1, 1, 1) - 1
    ly, lm, ld = tab_from_date(dt.date.fromordinal(last - 1721425))
    assert (ly, lm) == (y, 12)
    add("calendar-core", f"inst/fiscal/tabular/{y}", ["INS-003", "CAL-001"], "institutional.run",
        {"operation": {"op": "fiscal_year", "start_rule": {"type": "month_day", "month": 1, "day": 1}, "end_rule": {"type": "month_end", "month": 12}, "year": y},
         "context": {"calendar_provider": "arithmetic-tabular", "hijri_year": y}},
        ok(start={"hijri": f"{y:04d}-01-01", "gregorian": dt.date.fromordinal(tab_to_jdn(y, 1, 1) - 1721425).isoformat()},
           end={"hijri": f"{y:04d}-12-{ld:02d}", "gregorian": dt.date.fromordinal(last - 1721425).isoformat()}), basis="closed-form")
for tag, op in [("end-before-start", {"op": "fiscal_year", "start_rule": {"type": "month_end", "month": 12}, "end_rule": {"type": "month_day", "month": 1, "day": 1}, "year": 1448}),
                ("day-30-in-29-day-month", {"op": "month_day", "month": 2, "day": 30, "year": 1448}), ("no-fifth-weekday", {"op": "nth_weekday_of_month", "weekday": "al-Ahad", "n": 6, "month": 1, "year": 1448}),
                ("n-zero", {"op": "nth_weekday_of_month", "weekday": "al-Ahad", "n": 0, "month": 1, "year": 1448}), ("bad-weekday", {"op": "nth_weekday_of_month", "weekday": "Sunday", "n": 1, "month": 1, "year": 1448}),
                ("bad-month", {"op": "month_end", "month": 13, "year": 1448})]:
    add("calendar-core", f"inst/error/{tag}", ["INS-005", "CAL-004"] if tag == "day-30-in-29-day-month" else ["INS-005"], "institutional.run",
        {"operation": op, "context": {"calendar_provider": "arithmetic-tabular", "hijri_year": 1448}}, err("INVALID_CALENDAR_RULE"))

# =============================================================== write
if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for name, d in SUITES.items():
        tiers = sorted({v["tier"] for v in d["vectors"]})
        doc = {"suite": name, "tier": tiers[0] if len(tiers) == 1 else "mixed", "vectors": d["vectors"]}
        if d["metamorphic"]:
            doc["metamorphic"] = d["metamorphic"]
        json.dump(doc, open(os.path.join(OUT, name + ".json"), "w"), indent=1)
        print(f"{name}: {len(d['vectors'])} vectors, {len(d['metamorphic'])} metamorphic")

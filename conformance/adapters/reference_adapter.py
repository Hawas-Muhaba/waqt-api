#!/usr/bin/env python3
"""COP adapter for the Python reference implementation (waqt-core / waqt-api).

Same stdin/stdout protocol as the independent implementation (see conformance/spec/COP.md).
This file is the ONLY place the conformance suite touches reference internals; it maps the
reference's native shapes onto the portable COP output schema.
"""
import json
import math
import sys
import warnings
from datetime import date, datetime, timedelta, timezone

warnings.filterwarnings("ignore")
from fastapi.testclient import TestClient  # noqa: E402
from waqt.api import app  # noqa: E402
from waqt.api.providers import resolve_calendar_provider  # noqa: E402
from waqt_core.calendar_providers import DEFAULT_CALENDAR_PROVIDER as DEFAULT_PROVIDER  # noqa: E402  (CAL-012: omitted provider = the default)
from waqt_core.hijri import weekday_name, calendar_error_code  # noqa: E402
from waqt_core._version import __version__ as _CORE_VERSION  # noqa: E402
from waqt_core.core import AstronomyProfile, Location  # noqa: E402
from waqt_core.scheduling import SchedulingContext, SchedulingEngine, run_operation  # noqa: E402
from waqt_core.institutional.rules import MonthDay, MonthEnd, NthWeekdayOfMonth, month_days  # noqa: E402
from waqt_core.institutional.week import WeekDefinition, week_dates  # noqa: E402
from waqt_core.institutional.fiscal_year import FiscalCalendar  # noqa: E402
from waqt_core.institutional.academic_year import AcademicCalendar, TermDefinition  # noqa: E402
from waqt_core.calendar_providers.aladhan import (  # noqa: E402
    AlAdhanHijriProvider, TransportResponse, TransportTimeout, TransportError)

client = TestClient(app, raise_server_exceptions=False)
UTC = timezone.utc


class CopError(Exception):
    def __init__(self, code, message=""):
        super().__init__(message)
        self.code, self.message = code, message


def http(path, params):
    r = client.get(path, params={k: v for k, v in params.items() if v is not None})
    j = r.json()
    if r.status_code >= 400 or j.get("error"):
        e = j.get("error") or {"code": f"HTTP_{r.status_code}", "message": str(j)[:200]}
        raise CopError(e.get("code", "ERROR"), e.get("message", ""))
    return j["data"]


def iso(dt):
    return dt.astimezone(UTC).isoformat()


def parse_date(s):
    try:
        return date.fromisoformat(s)
    except Exception:
        raise CopError("INVALID_DATE", str(s))


def provider_from(name, params=None):
    if str(name).startswith("example-"):
        raise CopError("UNSUPPORTED_OPERATION", "example provider is not registered in the reference API")
    p = params or {}
    d, s = p.get("declared") or {}, p.get("sighting") or {}
    return resolve_calendar_provider(
        name, p.get("override_date"), d.get("year"), d.get("month"), d.get("day"),
        s.get("year"), s.get("month"), s.get("day"), p.get("observed_at"))


def hijri_out(hd):
    prov = getattr(hd, "provenance", None)
    return {
        "year": hd.year, "month": hd.month, "day": hd.day,
        "date": f"{hd.year:04d}-{hd.month:02d}-{hd.day:02d}", "month_name": hd.month_name, "display": str(hd),
        "provider": hd.provider, "source": getattr(hd, "source", "local") or "local",
        "fallback_reason": getattr(prov, "fallback_reason", None) if prov else None,
    }


def op_weekday(i):
    import calendar
    d = parse_date(i["date"])
    return {"weekday_iso": d.isoweekday(), "weekday_name_islamic": weekday_name(d),
            "is_leap_year": calendar.isleap(d.year), "days_in_month": calendar.monthrange(d.year, d.month)[1]}


def op_h_from(i):
    d = parse_date(i["date"])
    try:
        prov = provider_from(i.get("provider", DEFAULT_PROVIDER), i.get("params"))
    except Exception as e:
        raise CopError(getattr(e, "code", None) or "UNKNOWN_CALENDAR_PROVIDER", str(e))
    try:
        hd = prov.from_gregorian(d)
    except Exception as e:
        raise CopError(getattr(e, "code", None) or "OUT_OF_RANGE", f"{type(e).__name__}: {e}")
    return hijri_out(hd)


def op_h_to(i):
    data = http("/v1/conversions", dict(direction="to-gregorian", year=i["year"], month=i["month"], day=i["day"],
                                         calendar_provider=i.get("provider", DEFAULT_PROVIDER)))
    return {"date": data["output"]["gregorian_date"]}


def op_year_table(i):
    prov = provider_from(i.get("provider", DEFAULT_PROVIDER))
    months = []
    for m in range(1, 13):
        months.append({"month": m, "start": prov.to_gregorian(i["year"], m, 1).isoformat(), "length": len(month_days(prov, i["year"], m))})
    return {"months": months}


def op_month_len(i):
    prov = provider_from(i.get("provider", DEFAULT_PROVIDER))
    try:
        return {"days": len(month_days(prov, i["year"], i["month"]))}
    except Exception as e:
        raise CopError("INVALID_HIJRI_DATE", str(e))


def _ok_body(d, h, echo=None):
    e = echo or d
    return {"code": 200, "data": {"hijri": {"year": str(h["year"]), "month": {"number": h["month"]}, "day": str(h["day"])},
                                  "gregorian": {"date": e.strftime("%d-%m-%Y")}}}


def op_scenario(i):
    cfg = i.get("config") or {}
    clock, cur = {"t": 0.0}, {}

    def transport(url, timeout, max_bytes):
        r, k = cur["remote"], cur["remote"].get("kind")
        if k == "timeout":
            raise TransportTimeout()
        if k in ("network-error", "unreachable"):
            raise TransportError("simulated")
        if k == "http":
            hdr = {"Retry-After": str(r["retry_after"])} if r.get("retry_after") is not None else {}
            body = json.dumps(_ok_body(cur["date"], r.get("hijri"))).encode() if r["status"] == 200 and r.get("hijri") else b"{}"
            return TransportResponse(r["status"], body, hdr)
        if k == "malformed":
            return TransportResponse(200, b"<html>nope</html>")
        if k == "oversize":
            return TransportResponse(200, b"x" * (max_bytes + 1))
        if k == "echo-mismatch":
            return TransportResponse(200, json.dumps(_ok_body(cur["date"], r["hijri"], echo=cur["date"] + timedelta(days=1))).encode())
        return TransportResponse(200, json.dumps(_ok_body(cur["date"], r["hijri"])).encode())

    kw = dict(transport=transport, clock=lambda: clock["t"],
              wall_clock=lambda: datetime(2026, 10, 1, tzinfo=UTC) + timedelta(seconds=clock["t"]))
    m = {"enabled": "enabled", "ttl_seconds": "cache_ttl_seconds", "max_stale_seconds": "max_stale_seconds",
         "cooldown_seconds": "failure_cooldown_seconds", "max_retry_after_seconds": "max_retry_after_seconds",
         "max_plausible_delta_days": "max_plausible_delta_days", "requests_per_minute": "max_requests_per_minute"}
    for a, b in m.items():
        if a in cfg:
            kw[b] = cfg[a]
    prov = AlAdhanHijriProvider(cross_check=False, **kw)
    out = []
    for st in i["steps"]:
        clock["t"] = float(st["at_seconds"])
        cur["remote"], cur["date"] = st.get("remote") or {"kind": "network-error"}, parse_date(st["date"])
        o = hijri_out(prov.from_gregorian(cur["date"]))
        out.append({"date": st["date"], "provider": o["provider"], "source": o["source"], "fallback_reason": o["fallback_reason"]})
    return {"steps": out}


def common_params(i):
    loc, prof, cal = i.get("location") or {}, _profile(i), i.get("calendar") or {}
    p = cal.get("params") or {}
    d, s = p.get("declared") or {}, p.get("sighting") or {}
    return dict(lat=loc.get("lat"), lon=loc.get("lon"), elevation_m=loc.get("elevation_m", 0.0), timezone_override=i.get("timezone"),
                fajr_angle=prof.get("fajr_angle_deg", 18.0), isha_angle=prof.get("isha_angle_deg", 17.0),
                asr_ratio=prof.get("asr_shadow_ratio", 1.0), calendar_provider=cal.get("provider", DEFAULT_PROVIDER),
                override_date=p.get("override_date"), declared_year=d.get("year"), declared_month=d.get("month"), declared_day=d.get("day"),
                sighting_year=s.get("year"), sighting_month=s.get("month"), sighting_day=s.get("day"), observed_at=p.get("observed_at"))


def _profile(i):
    prof = i["profile"] if "profile" in i else i.get("astronomy_profile", {})
    if not isinstance(prof, dict):
        raise CopError("VALIDATION_ERROR", "profile must be a JSON object")
    for key in ("fajr_angle_deg", "isha_angle_deg", "asr_shadow_ratio"):
        if key not in prof:
            continue
        value = prof[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise CopError("VALIDATION_ERROR", f"{key} must be a finite JSON number")
    return prof


def op_compute(i):
    d = http("/v1/waqt", dict(common_params(i), instant=i.get("instant")))
    tz = d.get("timezone")
    base = {"instant": d["instant"], "timezone": tz.get("name") if isinstance(tz, dict) else tz,
            "profile": {k: d["profile"][k] for k in ("fajr_angle_deg", "isha_angle_deg", "asr_shadow_ratio")}}
    if d["status"] != "OK":
        return {"status": "UNDEFINED", "undefined_reason": d.get("undefined_reason"), **base, "day": None, "position": None,
                "hijri": None, "weekday": None, "events": [], "undefined_events": [], "next_event": None}
    reps = {r["name"]: r for r in d.get("event_representations", [])}
    evs = []
    for e in d["events"]:
        if e.get("instant") is None:
            continue
        evs.append({"name": e["name"], "instant": e["instant"], "reading_seconds": e["reading"]["seconds"],
                    "reading_display": e["reading"]["display"], "local_date": (reps.get(e["name"]) or {}).get("gregorian", {}).get("local_date")})
    have = {e["name"] for e in evs}
    und = [{"name": n, "reason": None} for n in ["fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha"] if n not in have]
    h, ne = d["hijri"] or {}, d.get("next_event")
    prov = h.get("provenance") or {}
    return {"status": "OK", "undefined_reason": None, **base,
            "day": {"open": d["day"]["maghrib_open"], "close": d["day"]["maghrib_close"], "length_seconds": d["day"]["length_si_seconds"]},
            "position": {"seconds": d["waqt"]["reading"]["seconds"], "display": d["waqt"]["reading"]["display"]},
            # CAL-013: no label (the provider could not label the date) is `null`, not an object of nulls.
            "hijri": ({"date": h.get("date"), "year": h.get("year"), "month": h.get("month"), "day": h.get("day"), "month_name": h.get("month_name"),
                       "provider": (h.get("provider") or {}).get("name"), "source": h.get("source"), "fallback_reason": prov.get("fallback_reason")}
                      if h.get("date") else None),
            "calendar_error": calendar_error_out(d.get("calendar_error"), d.get("calendar_error_code")),
            "weekday": d["weekday"], "events": evs, "undefined_events": und,
            "next_event": {"name": ne["name"], "instant": ne["instant"], "seconds_until": ne["countdown"]["seconds"]} if ne else None}


def op_represent(i):
    loc = i.get("location") or {}
    d = http("/v1/calendar/convert", dict(direction="instant-to-calendars", instant=i["instant"], lat=loc.get("lat"),
                                           lon=loc.get("lon"), elevation_m=loc.get("elevation_m"), timezone_override=i.get("timezone")))
    out = {"gregorian_utc": d["gregorian"]["utc"]}
    if d["gregorian"].get("civil"):
        out["gregorian_civil"] = d["gregorian"]["civil"]
    if d.get("waqt"):
        out["waqt_status"] = d["waqt"]["status"]
        out["waqt_position_seconds"] = (d["waqt"].get("day") or {}).get("position_seconds")
    return out


def op_date_to_waqt(i):
    p = common_params(i)
    try:
        d = http("/v1/calendar/convert", dict(p, direction="gregorian-date-to-waqt", date=i["date"]))
    except CopError as e:
        # Sprint 16 (DAY-009): the HTTP API reports a civil date on which no Waqt day closes as HTTP 422
        # CALENDAR_DATE_UNRESOLVABLE; the COP models that as a successful answer with resolved=false.
        if getattr(e, "code", None) == "CALENDAR_DATE_UNRESOLVABLE":
            return {"resolved": False, "close_civil_date": None, "open": None, "close": None, "reason": str(e)[:200]}
        raise
    w = d["waqt"]
    if w.get("status") != "OK" or not w.get("day"):
        return {"resolved": False, "close_civil_date": None, "open": None, "close": None, "reason": w.get("undefined_reason")}
    from zoneinfo import ZoneInfo
    close = datetime.fromisoformat(w["day"]["maghrib_close"])
    return {"resolved": True, "close_civil_date": close.astimezone(ZoneInfo(d["timezone"]["name"])).date().isoformat(),
            "open": w["day"]["maghrib_open"], "close": w["day"]["maghrib_close"],
            "hijri_date": (w.get("hijri") or {}).get("date"),
            "calendar_error": calendar_error_out(w.get("calendar_error"), w.get("calendar_error_code")),
            "weekday": w.get("weekday"), "reason": None}


def _ctx(c):
    from waqt_core.timezone_provider import DEFAULT_TIMEZONE_PROVIDER, ManualTimezoneProvider
    loc = c["location"]
    prof = _profile(c)
    p = AstronomyProfile(name="custom", fajr_angle_deg=prof.get("fajr_angle_deg", 18.0), isha_angle_deg=prof.get("isha_angle_deg", 17.0),
                         asr_shadow_ratio=prof.get("asr_shadow_ratio", 1.0))
    cal = c.get("calendar") or {"provider": c.get("calendar_provider", DEFAULT_PROVIDER)}
    tz = ManualTimezoneProvider(c["timezone"]) if c.get("timezone") else DEFAULT_TIMEZONE_PROVIDER
    return SchedulingContext(Location(loc["lat"], loc["lon"], loc.get("elevation_m", 0.0)), p, provider_from(cal["provider"], cal.get("params")), tz_provider=tz)


def op_boundary(i):
    from waqt_core.calendar_interop import classify_boundary_crossing
    ctx = _ctx(i)
    s = datetime.fromisoformat(i["start"].replace("Z", "+00:00"))
    e = datetime.fromisoformat(i["end"].replace("Z", "+00:00"))
    r = classify_boundary_crossing(s, e, ctx.location, ctx.calendar_provider, tz_provider=ctx.tz_provider)
    return {"status": "OK", "crosses_civil_midnight": r.crosses_civil_midnight, "crosses_maghrib": r.crosses_maghrib,
            "maghrib_boundaries": [iso(x) for x in r.maghrib_boundaries], "start_civil_date": r.start_civil_date.isoformat(),
            "end_civil_date": r.end_civil_date.isoformat()}


def op_schedule(i):
    c = i["context"]
    if "days" in c:   # frozen day table: the reference cannot ingest tables; it re-derives the same days live
        c = dict(c, timezone=c.get("timezone") or ZONE_BY_LOC.get((c["location"]["lat"], c["location"]["lon"])))
    return run_operation(SchedulingEngine(_ctx(c)), datetime.fromisoformat(i["anchor"]), i["operation"])


ZONE_BY_LOC = {(9.0192, 38.7525): "Africa/Addis_Ababa", (51.5074, -0.1278): "Europe/London", (69.6492, 18.9553): "Europe/Oslo"}


def _rule(r):
    t = r["type"]
    if t == "month_day":
        return MonthDay(r["month"], r["day"])
    if t == "month_end":
        return MonthEnd(r["month"])
    return NthWeekdayOfMonth(r["weekday"], r["n"], r["month"])


def op_inst(i):
    from waqt_core.institutional import rules as R
    op, c = i["operation"], i.get("context") or {}
    prov = provider_from(c.get("calendar_provider", DEFAULT_PROVIDER))
    year = op.get("year", c.get("hijri_year"))
    hs = lambda hd: f"{hd.year:04d}-{hd.month:02d}-{hd.day:02d}"
    pack = lambda hd: {"hijri": hs(hd), "gregorian": prov.to_gregorian(hd.year, hd.month, hd.day).isoformat()}
    try:
        k = op["op"]
        if k in ("month_day", "month_end", "nth_weekday_of_month"):
            return pack(_rule({**op, "type": k}).resolve(year, prov))
        if k == "week_dates":
            defn = WeekDefinition(first_day=op.get("first_day", "al-Ahad"))
            wd = week_dates(date.fromisoformat(op["date"]), defn)
            return {"week_dates": [x.isoformat() for x in wd], "weekdays": [defn.ordered_days()[j] for j in range(7)]}
        if k == "fiscal_year":
            fy = FiscalCalendar(start_rule=_rule(op["start_rule"]), end_rule=_rule(op["end_rule"]), label="x", calendar_provider=prov).year(year)
            return {"start": {"hijri": hs(fy.start_hijri), "gregorian": fy.start_gregorian.isoformat()},
                    "end": {"hijri": hs(fy.end_hijri), "gregorian": fy.end_gregorian.isoformat()}}
        if k == "academic_year":
            terms = tuple(TermDefinition(t["label"], _rule(t["start_rule"]), _rule(t["end_rule"])) for t in op.get("term_rules", []))
            ay = AcademicCalendar(opening_rule=_rule(op["opening_rule"]), closing_rule=_rule(op["closing_rule"]), term_rules=terms,
                                  holidays=(), calendar_provider=prov).year(year)
            return {"opening": {"hijri": hs(ay.opening_hijri), "gregorian": ay.opening_gregorian.isoformat()},
                    "closing": {"hijri": hs(ay.closing_hijri), "gregorian": ay.closing_gregorian.isoformat()},
                    "terms": [{"label": t.label, "start": {"hijri": hs(t.start_hijri), "gregorian": t.start_gregorian.isoformat()},
                               "end": {"hijri": hs(t.end_hijri), "gregorian": t.end_gregorian.isoformat()}} for t in ay.terms]}
    except R.RuleError as e:
        raise CopError("INVALID_CALENDAR_RULE", str(e))
    raise CopError("INVALID_CALENDAR_RULE", f"unknown op {op}")


def op_instant_parse(i):
    return {"instant": http("/v1/waqt", dict(lat=0, lon=0, timezone_override="UTC", instant=i["value"]))["instant"]}


OPS = {"gregorian.weekday": op_weekday, "hijri.from_gregorian": op_h_from, "hijri.to_gregorian": op_h_to,
       "hijri.month_length": op_month_len, "hijri.year_table": op_year_table, "hijri.provider_scenario": op_scenario, "waqt.compute": op_compute,
       "calendar.represent_instant": op_represent, "calendar.gregorian_date_to_waqt_day": op_date_to_waqt,
       "calendar.boundary_crossing": op_boundary, "schedule.run": op_schedule, "institutional.run": op_inst,
       "instant.parse": op_instant_parse}

def _pkg_api_version():
    """waqt-api package version from source pyproject.toml, falling back to installed metadata."""
    import re
    from pathlib import Path
    try:
        pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
        if pyproject.exists():
            m = re.search(r'^version\s*=\s*"([^"]+)"', pyproject.read_text(encoding="utf-8"), re.M)
            if m:
                return m.group(1)
    except Exception:
        pass
    try:
        from importlib.metadata import version
        return version("waqt-api")
    except Exception:
        return "unknown"


_PKG_API_VERSION = _pkg_api_version()

DESCRIPTOR = {"name": "waqt-reference", "version": f"waqt-core {_CORE_VERSION} / waqt-api {_PKG_API_VERSION}", "language": "Python", "cop_version": "1.1", "instant_precision_us": 1000000,
              "astronomy": {"sun": "NOAA low-precision", "moon": "PyEphem (umm-al-qura)"},
              "timezone_source": "IANA via Python zoneinfo + timezonefinder", "shares_code_with_reference": "n/a (this is the reference)"}


def decode_nonfinite(v):
    """COP wire convention (spec/COP.md section 2): {"$nonfinite": "NaN"|"Infinity"|"-Infinity"} -> a real float."""
    if isinstance(v, list):
        return [decode_nonfinite(x) for x in v]
    if isinstance(v, dict):
        if set(v) == {"$nonfinite"} and v["$nonfinite"] in ("NaN", "Infinity", "-Infinity"):
            return float(v["$nonfinite"].replace("Infinity", "inf"))
        return {k: decode_nonfinite(x) for k, x in v.items()}
    return v


def calendar_error_out(err, code=None):
    """COP `calendar_error` (CAL-013): {code} only; the free-text message is not normative. None when there is no error."""
    if not err:
        return None
    if code:
        return {"code": code}
    msg = err.get("message") if isinstance(err, dict) else str(err)
    return {"code": calendar_error_code(msg)}


def run_case(c):
    fn = OPS.get(c["op"])
    if not fn:
        return {"id": c["id"], "ok": False, "error": {"code": "UNSUPPORTED_OPERATION", "message": c["op"]}}
    try:
        return {"id": c["id"], "ok": True, "output": fn(decode_nonfinite(c.get("input") or {}))}
    except CopError as e:
        return {"id": c["id"], "ok": False, "error": {"code": e.code, "message": e.message}}
    except Exception as e:  # noqa
        if getattr(e, "code", None):
            return {"id": c["id"], "ok": False, "error": {"code": e.code, "message": str(e)[:300]}}
        return {"id": c["id"], "ok": False, "error": {"code": "INTERNAL_ERROR", "message": f"{type(e).__name__}: {e}"[:300]}}


if __name__ == "__main__":
    if "--describe" in sys.argv:
        print(json.dumps({"implementation": DESCRIPTOR, "operations": sorted(OPS)}))
    else:
        req = json.load(sys.stdin)
        print(json.dumps({"implementation": DESCRIPTOR, "results": [run_case(c) for c in req["cases"]]}))

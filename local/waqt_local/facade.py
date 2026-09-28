"""
waqt_local.facade — the local, embeddable Waqt computation surface.

Every function here does exactly what the matching `/v1/*` HTTP
endpoint does (waqt.api.*_endpoint), computed in-process, no server, no
network, no `httpx`. Each one:

  * calls the SAME underlying computation waqt.core / waqt.solar /
    waqt.semantics / waqt.hijri / waqt.scheduling / waqt.institutional /
    waqt.calendar_interop already provide — nothing here re-derives a
    Maghrib instant, a Hijri date, or a scheduling result by a second
    route;
  * shapes its result into the SAME dict shape the matching endpoint's
    `data` field has (see docs/API.md, docs/SCHEDULING.md,
    docs/INSTITUTIONAL.md, docs/CALENDAR-INTEROP.md) — this is what
    `tests/test_local_vs_server_equivalence.py` verifies automatically,
    field by field, rather than by inspection;
  * raises a `waqt_local.errors.WaqtLocalError` subclass for a caller
    mistake (never for "astronomy is undefined at this place/time",
    which is a normal `status` value, exactly as on the HTTP side).

None of this is a second implementation of Waqt's temporal or
astronomical rules — see the module docstring in `formatting.py` for
why the small amount of duplicated *presentation* code (units, null
behavior) is not that.
"""

from __future__ import annotations

from datetime import date as _date
from datetime import datetime
from typing import Any, Optional

from waqt import calendar_interop as ci
from waqt.core import AstronomyProfile, Location, compute_waqt
from waqt.hijri import ArithmeticTabularProvider, weekday_name
from waqt.institutional import (
    AcademicCalendar,
    FiscalCalendar,
    HolidayDefinition,
    RuleError as InstitutionalRuleError,
    TermDefinition,
    WeekDefinition,
    default_islamic_academic_calendar,
    default_islamic_fiscal_calendar,
    default_profile,
    rule_from_dict,
    week_containing,
)
from waqt.scheduling import RuleError as SchedulingRuleError, SchedulingContext, SchedulingEngine, run_operation
from waqt.semantics import waqt_day_from_result
from waqt.timescale import DEFAULT_TIMESCALE_PROVIDER
from waqt.timezone_provider import DEFAULT_TIMEZONE_PROVIDER, ManualTimezoneProvider

from .errors import (
    CalendarDateUnresolvableError,
    InvalidCalendarRuleError,
    InvalidRuleError,
    InvalidSpanError,
    ValidationError,
    validation_error,
)
from .formatting import computation_block, hijri_block, iso, parse_date, parse_instant, profile_block, reading, timezone_block
from .providers import PROVIDER_CATALOG, resolve_calendar_provider

_UNUSED_PROVIDER = ArithmeticTabularProvider()

CAVEAT_SCHEDULING = (
    "Waqt returns temporal facts derived from an astronomical profile. "
    "It does not decide religious rulings: whether and how an event, offset or window applies to any obligation "
    "is the caller's (or their scholar's) determination."
)
CAVEAT_INSTITUTIONAL = (
    "Waqt states calendar facts derived from a Hijri calendar provider and an institutional convention "
    "(which day starts the week, which rule opens a fiscal or academic year). It does not decide whether "
    "an institution should adopt any particular convention."
)
CAVEAT_INTEROP = (
    "Waqt states calendar facts (which civil date, which Hijri date, which "
    "Waqt day/position), not institutional or religious obligations."
)


def _location(lat: float, lon: float, elevation_m: float = 0.0) -> Location:
    if not (-90 <= lat <= 90 and -180 <= lon <= 180 and elevation_m >= 0):
        raise validation_error("location out of range (|lat|<=90, |lon|<=180, elevation_m>=0)")
    return Location(lat=lat, lon=lon, elevation_m=elevation_m)


def _tz_provider(timezone_override: Optional[str]):
    return ManualTimezoneProvider(timezone_override) if timezone_override else DEFAULT_TIMEZONE_PROVIDER


def _profile(fajr_angle: float = 18.0, isha_angle: float = 17.0, asr_ratio: float = 1.0) -> AstronomyProfile:
    return AstronomyProfile(name="custom", fajr_angle_deg=fajr_angle, isha_angle_deg=isha_angle, asr_shadow_ratio=asr_ratio)


# ---------------------------------------------------------------------------
# Core time model: waqt / day / events / location
# ---------------------------------------------------------------------------


def waqt(
    lat: float,
    lon: float,
    elevation_m: float = 0.0,
    instant: Any = None,
    timezone_override: Optional[str] = None,
    fajr_angle: float = 18.0,
    isha_angle: float = 17.0,
    asr_ratio: float = 1.0,
    calendar_provider: str = "arithmetic-tabular",
    **provider_overrides: Any,
) -> dict:
    """Equivalent of `GET /v1/waqt`."""
    t = parse_instant(instant)
    provider = resolve_calendar_provider(calendar_provider, **provider_overrides)
    location = _location(lat, lon, elevation_m)
    profile = _profile(fajr_angle, isha_angle, asr_ratio)
    tz_provider = _tz_provider(timezone_override)

    r = compute_waqt(t, location, provider, profile, tz_provider=tz_provider, timescale=DEFAULT_TIMESCALE_PROVIDER)

    waqt_field = None
    if r.hour_reading is not None and r.day_start_maghrib is not None:
        waqt_field = {"display": f"Waqt {r.hour_reading}", "reading": reading(r.instant - r.day_start_maghrib)}

    events_field = [
        {
            "name": e.name,
            "instant": iso(e.instant),
            "reading": reading(e.instant - r.day_start_maghrib) if (e.instant and r.day_start_maghrib) else None,
        }
        for e in r.events
    ]

    next_event_field = None
    if r.next_event is not None:
        next_event_field = {
            "name": r.next_event.name,
            "instant": iso(r.next_event.instant),
            "countdown": reading(r.next_event.instant - r.instant) if r.next_event.instant else None,
        }

    return {
        "status": r.status,
        "instant": iso(r.instant),
        "location": {"lat": r.location_lat, "lon": r.location_lon, "elevation_m": r.location_elevation_m},
        "timezone": timezone_block(r.timezone_name, r.instant),
        "undefined_reason": r.undefined_reason,
        "day": {
            "maghrib_open": iso(r.day_start_maghrib),
            "maghrib_close": iso(r.day_end_maghrib),
            "length_si_seconds": round(r.day_length_si_seconds, 3) if r.day_length_si_seconds is not None else None,
            "note": r.hour_length_note,
        },
        "hijri": hijri_block(r.hijri_date),
        "weekday": r.weekday,
        "waqt": waqt_field,
        "events": events_field,
        "next_event": next_event_field,
        "profile": profile_block(r.profile),
        "computation": computation_block(r.timescale_model, r.delta_t_seconds),
    }


def day(lat: float, lon: float, elevation_m: float = 0.0, instant: Any = None, timezone_override: Optional[str] = None) -> dict:
    """Equivalent of `GET /v1/day`."""
    t = parse_instant(instant)
    location = _location(lat, lon, elevation_m)
    tz_provider = _tz_provider(timezone_override)
    r = compute_waqt(t, location, _UNUSED_PROVIDER, AstronomyProfile(), tz_provider=tz_provider, timescale=DEFAULT_TIMESCALE_PROVIDER)
    return {
        "status": r.status,
        "instant": iso(r.instant),
        "location": {"lat": r.location_lat, "lon": r.location_lon, "elevation_m": r.location_elevation_m},
        "timezone": timezone_block(r.timezone_name, r.instant),
        "undefined_reason": r.undefined_reason,
        "day": {
            "maghrib_open": iso(r.day_start_maghrib),
            "maghrib_close": iso(r.day_end_maghrib),
            "length_si_seconds": round(r.day_length_si_seconds, 3) if r.day_length_si_seconds is not None else None,
            "note": r.hour_length_note,
        },
        "computation": computation_block(r.timescale_model, r.delta_t_seconds),
    }


def events(
    lat: float,
    lon: float,
    elevation_m: float = 0.0,
    instant: Any = None,
    timezone_override: Optional[str] = None,
    fajr_angle: float = 18.0,
    isha_angle: float = 17.0,
    asr_ratio: float = 1.0,
) -> dict:
    """Equivalent of `GET /v1/events`."""
    t = parse_instant(instant)
    location = _location(lat, lon, elevation_m)
    profile = _profile(fajr_angle, isha_angle, asr_ratio)
    tz_provider = _tz_provider(timezone_override)
    r = compute_waqt(t, location, _UNUSED_PROVIDER, profile, tz_provider=tz_provider, timescale=DEFAULT_TIMESCALE_PROVIDER)

    events_field = [
        {
            "name": e.name,
            "instant": iso(e.instant),
            "reading": reading(e.instant - r.day_start_maghrib) if (e.instant and r.day_start_maghrib) else None,
        }
        for e in r.events
    ] if r.events else []

    next_event_field = None
    if r.next_event is not None:
        next_event_field = {
            "name": r.next_event.name,
            "instant": iso(r.next_event.instant),
            "countdown": reading(r.next_event.instant - r.instant) if r.next_event.instant else None,
        }

    return {
        "status": r.status,
        "instant": iso(r.instant),
        "location": {"lat": r.location_lat, "lon": r.location_lon, "elevation_m": r.location_elevation_m},
        "timezone": timezone_block(r.timezone_name, r.instant),
        "undefined_reason": r.undefined_reason,
        "day_start_maghrib": iso(r.day_start_maghrib),
        "events": events_field,
        "next_event": next_event_field,
        "profile": profile_block(r.profile),
        "computation": computation_block(r.timescale_model, r.delta_t_seconds),
    }


def location_info(lat: float, lon: float, instant: Any = None, timezone_override: Optional[str] = None) -> dict:
    """Equivalent of `GET /v1/location`."""
    t = parse_instant(instant)
    tz_provider = _tz_provider(timezone_override)
    tz_name = tz_provider.timezone_name_for(lat, lon)
    local_date = tz_provider.local_date(t, lat, lon)
    return {
        "location": {"lat": lat, "lon": lon},
        "instant": iso(t),
        "timezone": timezone_block(tz_name, t),
        "local_civil_date": local_date.isoformat(),
    }


# ---------------------------------------------------------------------------
# Calendars
# ---------------------------------------------------------------------------


def hijri(date: Any = None, calendar_provider: str = "arithmetic-tabular", **provider_overrides: Any) -> dict:
    """Equivalent of `GET /v1/hijri`."""
    d = parse_date(date)
    provider = resolve_calendar_provider(calendar_provider, **provider_overrides)
    hd = provider.from_gregorian(d)
    return {"gregorian_date": d.isoformat(), "weekday": weekday_name(d), "hijri": hijri_block(hd)}


def list_calendar_providers() -> dict:
    """Equivalent of `GET /v1/calendar`."""
    return {
        "providers": [
            {
                "name": name,
                "description": entry["description"],
                "requires_override": entry["requires_override"],
                "supports_reverse_conversion": entry["supports_reverse"],
            }
            for name, entry in PROVIDER_CATALOG.items()
        ]
    }


def convert(
    direction: str,
    calendar_provider: str = "arithmetic-tabular",
    date: Any = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    day: Optional[int] = None,
) -> dict:
    """Equivalent of `GET /v1/conversions`."""
    if direction not in ("to-hijri", "to-gregorian"):
        raise validation_error(f"direction must be 'to-hijri' or 'to-gregorian', got {direction!r}.", received=direction)

    provider = resolve_calendar_provider(calendar_provider)

    if direction == "to-hijri":
        g = parse_date(date)
        hd = provider.from_gregorian(g)
        return {"direction": "to-hijri", "input": {"gregorian_date": g.isoformat()}, "output": {"hijri": hijri_block(hd)}}

    if year is None or month is None or day is None:
        raise validation_error("direction=to-gregorian requires year, month, and day.", received={"year": year, "month": month, "day": day})
    if not hasattr(provider, "to_gregorian"):
        from .errors import UnsupportedOperationError

        raise UnsupportedOperationError(
            f"calendar_provider={calendar_provider!r} cannot convert Hijri -> Gregorian.",
            {"calendar_provider": calendar_provider},
        )
    g = provider.to_gregorian(year, month, day)
    return {
        "direction": "to-gregorian",
        "input": {"hijri": {"year": year, "month": month, "day": day}},
        "output": {"gregorian_date": g.isoformat(), "weekday": weekday_name(g)},
    }


def _location_or_none(lat: Optional[float], lon: Optional[float], elevation_m: float) -> Optional[Location]:
    if lat is None and lon is None:
        return None
    if lat is None or lon is None:
        raise validation_error("lat and lon must both be supplied, or both omitted.", received={"lat": lat, "lon": lon})
    return Location(lat=lat, lon=lon, elevation_m=elevation_m)


def represent_instant(
    instant: Any = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    elevation_m: float = 0.0,
    timezone_override: Optional[str] = None,
    fajr_angle: float = 18.0,
    isha_angle: float = 17.0,
    asr_ratio: float = 1.0,
    calendar_provider: str = "arithmetic-tabular",
    **provider_overrides: Any,
) -> dict:
    """Equivalent of `GET /v1/calendar/convert?direction=instant-to-calendars`."""
    t = parse_instant(instant)
    location = _location_or_none(lat, lon, elevation_m)
    provider = resolve_calendar_provider(calendar_provider, **provider_overrides)
    profile = _profile(fajr_angle, isha_angle, asr_ratio)
    tz_provider = _tz_provider(timezone_override)

    rep = ci.represent_instant(t, location, provider, profile, tz_provider=tz_provider, timescale=DEFAULT_TIMESCALE_PROVIDER)
    body = rep.to_dict()
    return {
        "direction": "instant-to-calendars",
        "source": {"calendar": "instant", "instant": body["instant"]},
        "location": {"lat": location.lat, "lon": location.lon, "elevation_m": location.elevation_m} if location else None,
        "calendar_provider": {"name": provider.name, "version": provider.version} if location else None,
        "gregorian": {"utc": body["gregorian_utc"], "civil": body["gregorian_civil"]},
        "waqt": (
            {"status": body["waqt_status"], "undefined_reason": body["undefined_reason"], **({"day": body["waqt"]} if body["waqt"] else {})}
            if location else None
        ),
        "profile": profile_block(profile) if location else None,
        "computation": computation_block(DEFAULT_TIMESCALE_PROVIDER.name, DEFAULT_TIMESCALE_PROVIDER.delta_t_seconds(rep.gregorian_utc.date)) if location else None,
        "caveat": CAVEAT_INTEROP,
    }


def waqt_day_for_gregorian_date(
    date: Any,
    lat: float,
    lon: float,
    elevation_m: float = 0.0,
    timezone_override: Optional[str] = None,
    fajr_angle: float = 18.0,
    isha_angle: float = 17.0,
    asr_ratio: float = 1.0,
    calendar_provider: str = "arithmetic-tabular",
    **provider_overrides: Any,
) -> dict:
    """Equivalent of `GET /v1/calendar/convert?direction=gregorian-date-to-waqt`."""
    location = _location(lat, lon, elevation_m)
    provider = resolve_calendar_provider(calendar_provider, **provider_overrides)
    profile = _profile(fajr_angle, isha_angle, asr_ratio)
    tz_provider = _tz_provider(timezone_override)
    g = parse_date(date)

    try:
        d = ci.waqt_day_for_gregorian_date(g, location, provider, profile, tz_provider=tz_provider, timescale=DEFAULT_TIMESCALE_PROVIDER)
    except ci.CivilDateUnresolvable as exc:
        if exc.reason == "undefined_near_date":
            return {
                "direction": "gregorian-date-to-waqt",
                "source": {"calendar": "gregorian", "date": g.isoformat()},
                "location": {"lat": location.lat, "lon": location.lon, "elevation_m": location.elevation_m},
                "calendar_provider": {"name": provider.name, "version": provider.version},
                "waqt": {"status": "UNDEFINED", "undefined_reason": str(exc)},
                "caveat": CAVEAT_INTEROP,
            }
        raise CalendarDateUnresolvableError(str(exc), {"reason": exc.reason})

    return {
        "direction": "gregorian-date-to-waqt",
        "source": {"calendar": "gregorian", "date": g.isoformat()},
        "location": {"lat": location.lat, "lon": location.lon, "elevation_m": location.elevation_m},
        "timezone": timezone_block(tz_provider.timezone_name_for(location.lat, location.lon), d.open),
        "calendar_provider": {"name": provider.name, "version": provider.version},
        "waqt": {
            "status": "OK",
            "hijri": hijri_block(d.hijri_date),
            "weekday": d.weekday,
            "day": {
                "maghrib_open": iso(d.open),
                "maghrib_close": iso(d.close),
                "length_si_seconds": round(d.length_seconds, 3) if d.length_seconds is not None else None,
            },
        },
        "caveat": CAVEAT_INTEROP,
    }


def boundary_crossing(
    start: Any,
    end: Any,
    lat: float,
    lon: float,
    elevation_m: float = 0.0,
    timezone_override: Optional[str] = None,
) -> dict:
    """Equivalent of `GET /v1/calendar/boundary-crossing`."""
    s = parse_instant(start)
    e = parse_instant(end)
    tz_provider = _tz_provider(timezone_override)
    if e <= s:
        raise InvalidSpanError(
            "end must be strictly after start (a half-open span cannot be empty or reversed).",
            {"start": iso(s), "end": iso(e)},
        )
    location = _location(lat, lon, elevation_m)
    try:
        crossing = ci.classify_boundary_crossing(s, e, location, tz_provider=tz_provider, timescale=DEFAULT_TIMESCALE_PROVIDER)
    except ci.CivilDateUnresolvable as exc:
        return {
            "start": iso(s), "end": iso(e),
            "location": {"lat": lat, "lon": lon, "elevation_m": elevation_m},
            "status": "UNDEFINED", "undefined_reason": str(exc), "caveat": CAVEAT_INTEROP,
        }
    return {**crossing.to_dict(), "status": "OK", "location": {"lat": lat, "lon": lon, "elevation_m": elevation_m}, "caveat": CAVEAT_INTEROP}


# ---------------------------------------------------------------------------
# Scheduling (Sprint 6)
# ---------------------------------------------------------------------------


def _scheduling_context(lat, lon, elevation_m, profile, calendar_provider, timezone_override) -> SchedulingContext:
    provider = resolve_calendar_provider(calendar_provider)
    tz = _tz_provider(timezone_override)
    return SchedulingContext(_location(lat, lon, elevation_m), profile, provider, tz_provider=tz)


def _schedule_context_block(ctx: SchedulingContext, anchor: datetime) -> dict:
    return {
        "location": {"lat": ctx.location.lat, "lon": ctx.location.lon, "elevation_m": ctx.location.elevation_m},
        "profile": profile_block(ctx.profile),
        "calendar_provider": {"name": ctx.calendar_provider.name, "version": ctx.calendar_provider.version,
                               "used_for": "display labels only — never an input to any scheduling result"},
        "computation": computation_block(ctx.timescale.name, ctx.timescale.delta_t_seconds(anchor.date())),
    }


def schedule_snapshot(
    lat: float, lon: float, elevation_m: float = 0.0, instant: Any = None, timezone_override: Optional[str] = None,
    fajr_angle: float = 18.0, isha_angle: float = 17.0, asr_ratio: float = 1.0,
    calendar_provider: str = "arithmetic-tabular", precision: str = "second",
) -> dict:
    """Equivalent of `GET /v1/schedule/snapshot`."""
    rs = _check_precision(precision)
    t = parse_instant(instant)
    profile = _profile(fajr_angle, isha_angle, asr_ratio)
    ctx = _scheduling_context(lat, lon, elevation_m, profile, calendar_provider, timezone_override)
    eng = SchedulingEngine(ctx)
    snap = SchedulingEngine.snapshot_to_dict(eng.snapshot(t), rs)
    tz = ctx.tz_provider.timezone_name_for(lat, lon)
    return {**snap, "timezone": timezone_block(tz, t), **_schedule_context_block(ctx, t), "caveat": CAVEAT_SCHEDULING}


def schedule_span(
    lat: float, lon: float, start: Any, end: Any, end_inclusive: bool = False, elevation_m: float = 0.0,
    timezone_override: Optional[str] = None, calendar_provider: str = "arithmetic-tabular", precision: str = "second",
) -> dict:
    """Equivalent of `GET /v1/schedule/span`."""
    rs = _check_precision(precision)
    s, e = parse_instant(start), parse_instant(end)
    ctx = _scheduling_context(lat, lon, elevation_m, AstronomyProfile(), calendar_provider, timezone_override)
    eng = SchedulingEngine(ctx)
    result = eng.classify_span(s, e, end_inclusive).to_dict(rs)
    return {**result, **_schedule_context_block(ctx, s), "caveat": CAVEAT_SCHEDULING}


def _check_precision(precision: str) -> bool:
    if precision not in ("second", "microsecond"):
        raise validation_error(f"precision must be one of ['second', 'microsecond']", received=precision)
    return precision == "second"


def schedule_resolve(request: Any) -> dict:
    """Equivalent of `POST /v1/schedule/resolve`.

    `request` is either a plain dict in the same JSON shape
    docs/SCHEDULING.md documents (identical to the HTTP body), or a
    `waqt_local.requests.ScheduleResolveRequest` built with this
    library's typed request builders (the same ones the Python SDK's
    `waqt_client.requests` module provides, kept in sync — see
    docs/SDK.md).
    """
    body = request.to_json() if hasattr(request, "to_json") else request
    if not isinstance(body, dict):
        raise InvalidRuleError("Request body must be a JSON object")
    loc = body.get("location")
    if not isinstance(loc, dict) or "lat" not in loc or "lon" not in loc:
        raise validation_error("`location` must be an object with `lat` and `lon`")
    lat, lon, elev = float(loc["lat"]), float(loc["lon"]), float(loc.get("elevation_m", 0.0))
    location = _location(lat, lon, elev)

    pr = body.get("profile") or {}
    profile = _profile(pr.get("fajr_angle_deg", 18.0), pr.get("isha_angle_deg", 17.0), pr.get("asr_shadow_ratio", 1.0))
    rs = _check_precision(body.get("precision", "second"))

    from waqt.scheduling.model import parse_instant as parse_rule_instant

    try:
        anchor = parse_rule_instant(body["anchor"]) if body.get("anchor") is not None else parse_instant(None)
    except SchedulingRuleError as e:
        from .errors import InvalidInstantError

        raise InvalidInstantError(str(e), {"received": body.get("anchor")})

    provider = resolve_calendar_provider(body.get("calendar_provider", "arithmetic-tabular"))
    tz = _tz_provider(body.get("timezone_override"))
    ctx = SchedulingContext(location, profile, provider, tz_provider=tz)
    eng = SchedulingEngine(ctx)
    op = body.get("operation")
    try:
        result = run_operation(eng, anchor, op, rs)
    except SchedulingRuleError as e:
        raise InvalidRuleError(str(e), {"operation": op if isinstance(op, dict) else None})

    return {
        "anchor": iso(anchor) if rs else anchor.isoformat(),
        "operation": op["op"],
        "result": result,
        **_schedule_context_block(ctx, anchor),
        "caveat": CAVEAT_SCHEDULING,
    }


# ---------------------------------------------------------------------------
# Institutional calendars (Sprint 7)
# ---------------------------------------------------------------------------


def _hijri_year_for_instant(instant: Any, provider) -> int:
    t = parse_instant(instant)
    return provider.from_gregorian(t.date()).year


def _resolve_and_wrap(build, label: str) -> dict:
    try:
        return build()
    except InstitutionalRuleError as e:
        raise InvalidCalendarRuleError(f"{label}: {e}")


def institutional_week(
    lat: float, lon: float, elevation_m: float = 0.0, instant: Any = None,
    first_day: str = "al-Ahad", jumuah_day: str = "al-Jumuah", calendar_provider: str = "arithmetic-tabular",
) -> dict:
    """Equivalent of `GET /v1/institutional/week`."""
    t = parse_instant(instant)
    try:
        defn = WeekDefinition(first_day=first_day, jumuah_day=jumuah_day)
    except InstitutionalRuleError as e:
        raise InvalidCalendarRuleError(str(e))
    provider = resolve_calendar_provider(calendar_provider)
    ctx = SchedulingContext(_location(lat, lon, elevation_m), calendar_provider=provider)
    week = _resolve_and_wrap(lambda: week_containing(ctx, t, defn), "week")
    return {**week.to_dict(ctx), "caveat": CAVEAT_INSTITUTIONAL}


def institutional_fiscal_year(
    hijri_year: Optional[int] = None, instant: Any = None, lat: Optional[float] = None, lon: Optional[float] = None,
    elevation_m: float = 0.0, calendar_provider: str = "arithmetic-tabular",
) -> dict:
    """Equivalent of `GET /v1/institutional/fiscal-year`."""
    provider = resolve_calendar_provider(calendar_provider)
    year = hijri_year if hijri_year is not None else _hijri_year_for_instant(instant, provider)
    ctx = SchedulingContext(_location(lat, lon, elevation_m), calendar_provider=provider) if (lat is not None and lon is not None) else None
    fc = default_islamic_fiscal_calendar(provider)
    fy = _resolve_and_wrap(lambda: fc.year(year, ctx=ctx), "fiscal-year")
    return {**fy.to_dict(), "definition": fc.to_dict(), "caveat": CAVEAT_INSTITUTIONAL}


def institutional_fiscal_year_resolve(request: Any) -> dict:
    """Equivalent of `POST /v1/institutional/fiscal-year/resolve`."""
    body = request.to_json() if hasattr(request, "to_json") else request
    if not isinstance(body, dict):
        raise InvalidCalendarRuleError("Request body must be a JSON object")
    if "hijri_year" not in body:
        raise validation_error("`hijri_year` is required")
    provider = resolve_calendar_provider(body.get("calendar_provider", "arithmetic-tabular"))
    loc = _location_or_none(body.get("location", {}).get("lat") if body.get("location") else None,
                             body.get("location", {}).get("lon") if body.get("location") else None,
                             body.get("location", {}).get("elevation_m", 0.0) if body.get("location") else 0.0)
    ctx = SchedulingContext(loc, calendar_provider=provider) if loc is not None else None

    def build():
        fc = FiscalCalendar(
            start_rule=rule_from_dict(body["start_rule"]), end_rule=rule_from_dict(body["end_rule"]),
            label=body.get("label", "Fiscal Year"), calendar_provider=provider,
        )
        return fc, fc.year(int(body["hijri_year"]), ctx=ctx)

    fc, fy = _resolve_and_wrap(build, "fiscal-year")
    return {**fy.to_dict(), "definition": fc.to_dict(), "caveat": CAVEAT_INSTITUTIONAL}


def institutional_academic_year(
    hijri_year: Optional[int] = None, instant: Any = None, lat: Optional[float] = None, lon: Optional[float] = None,
    elevation_m: float = 0.0, calendar_provider: str = "arithmetic-tabular",
) -> dict:
    """Equivalent of `GET /v1/institutional/academic-year`."""
    provider = resolve_calendar_provider(calendar_provider)
    year = hijri_year if hijri_year is not None else _hijri_year_for_instant(instant, provider)
    ctx = SchedulingContext(_location(lat, lon, elevation_m), calendar_provider=provider) if (lat is not None and lon is not None) else None
    ac = default_islamic_academic_calendar(provider)
    ay = _resolve_and_wrap(lambda: ac.year(year, ctx=ctx), "academic-year")
    return {**ay.to_dict(), "definition": ac.to_dict(), "caveat": CAVEAT_INSTITUTIONAL}


def _term_defs(raw: list) -> tuple:
    return tuple(
        TermDefinition(t["label"], rule_from_dict(t["start_rule"]), rule_from_dict(t["end_rule"]), t.get("year_offset", 0))
        for t in raw
    )


def _holiday_defs(raw: list) -> tuple:
    return tuple(HolidayDefinition(h["label"], rule_from_dict(h["rule"]), h.get("year_offset", 0)) for h in raw)


def institutional_academic_year_resolve(request: Any) -> dict:
    """Equivalent of `POST /v1/institutional/academic-year/resolve`."""
    body = request.to_json() if hasattr(request, "to_json") else request
    if not isinstance(body, dict):
        raise InvalidCalendarRuleError("Request body must be a JSON object")
    if "hijri_year" not in body:
        raise validation_error("`hijri_year` is required")
    provider = resolve_calendar_provider(body.get("calendar_provider", "arithmetic-tabular"))
    loc = _location_or_none(body.get("location", {}).get("lat") if body.get("location") else None,
                             body.get("location", {}).get("lon") if body.get("location") else None,
                             body.get("location", {}).get("elevation_m", 0.0) if body.get("location") else 0.0)
    ctx = SchedulingContext(loc, calendar_provider=provider) if loc is not None else None

    def build():
        ac = AcademicCalendar(
            opening_rule=rule_from_dict(body["opening_rule"]), closing_rule=rule_from_dict(body["closing_rule"]),
            term_rules=_term_defs(body.get("term_rules", [])), holidays=_holiday_defs(body.get("holidays", [])),
            label=body.get("label", "Academic Year"), calendar_provider=provider,
        )
        return ac, ac.year(int(body["hijri_year"]), ctx=ctx)

    ac, ay = _resolve_and_wrap(build, "academic-year")
    return {**ay.to_dict(), "definition": ac.to_dict(), "caveat": CAVEAT_INSTITUTIONAL}


def institutional_default_profile(calendar_provider: str = "arithmetic-tabular") -> dict:
    """Equivalent of `GET /v1/institutional/profile`."""
    provider = resolve_calendar_provider(calendar_provider)
    profile = default_profile(name=f"demo-{calendar_provider}", calendar_provider=provider)
    return {"profile": profile.to_dict(), "caveat": CAVEAT_INSTITUTIONAL}

"""
waqt.api.calendar_convert_endpoint — Sprint 8's HTTP surface:

    GET /v1/calendar/convert            — instant <-> Gregorian <-> Waqt
    GET /v1/calendar/boundary-crossing  — civil midnight vs Maghrib, for a span

Both are thin HTTP wrappers over waqt.calendar_interop; neither
recomputes anything that module doesn't already provide. See
docs/CALENDAR-INTEROP.md for the prose contract.

`/v1/calendar/convert` takes a `direction`, the same shape
`/v1/conversions` (Sprint 3) already established for a two-mode
endpoint:

  direction=instant-to-calendars (default) — given an instant (and,
    optionally, a location), render it as UTC-Gregorian always, and
    as local-civil-Gregorian and a Waqt day/position if a location was
    supplied. This is `calendar_interop.represent_instant`.

  direction=gregorian-date-to-waqt — given a Gregorian civil DATE and
    a location, find the Waqt day whose closing Maghrib falls on that
    date. This is `calendar_interop.waqt_day_for_gregorian_date`, the
    Sprint 8 brief's "Gregorian date + location -> Waqt day" item.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from .. import calendar_interop as ci
from ..core import AstronomyProfile, Location
from ..timescale import DEFAULT_TIMESCALE_PROVIDER
from ..timezone_provider import DEFAULT_TIMEZONE_PROVIDER, ManualTimezoneProvider
from .common import (
    ApiError,
    ErrorCode,
    computation_block,
    hijri_block,
    iso,
    parse_date,
    parse_instant,
    profile_block,
    success,
    timezone_block,
)
from .providers import PROVIDER_CATALOG, resolve_calendar_provider

router = APIRouter()

CAVEAT = (
    "Waqt states calendar facts (which civil date, which Hijri date, which "
    "Waqt day/position), not institutional or religious obligations."
)


def _location_or_none(lat: Optional[float], lon: Optional[float], elevation_m: float) -> Optional[Location]:
    if lat is None and lon is None:
        return None
    if lat is None or lon is None:
        raise ApiError(
            400, ErrorCode.VALIDATION_ERROR,
            "lat and lon must both be supplied, or both omitted.",
            {"received": {"lat": lat, "lon": lon}},
        )
    return Location(lat=lat, lon=lon, elevation_m=elevation_m)


@router.get("/v1/calendar/convert")
def convert_calendar(
    direction: str = Query(
        "instant-to-calendars",
        description="'instant-to-calendars' or 'gregorian-date-to-waqt'",
    ),
    instant: Optional[str] = Query(None, description="ISO 8601 UTC instant (instant-to-calendars only)"),
    date: Optional[str] = Query(None, description="Gregorian civil date YYYY-MM-DD (gregorian-date-to-waqt only)"),
    lat: Optional[float] = Query(None, ge=-90, le=90, description="Required for gregorian-date-to-waqt; optional otherwise"),
    lon: Optional[float] = Query(None, ge=-180, le=180),
    elevation_m: float = Query(0.0, ge=0),
    timezone_override: Optional[str] = Query(None, description="IANA zone to force, skipping lookup"),
    fajr_angle: float = Query(18.0, description="Fajr depression angle, degrees"),
    isha_angle: float = Query(17.0, description="Isha depression angle, degrees"),
    asr_ratio: float = Query(1.0, description="Asr shadow ratio: 1.0 = standard, 2.0 = Hanafi"),
    calendar_provider: str = Query(
        "arithmetic-tabular", description=f"One of: {', '.join(PROVIDER_CATALOG)}. See GET /v1/calendar."
    ),
    override_date: Optional[str] = Query(None),
    declared_year: Optional[int] = Query(None),
    declared_month: Optional[int] = Query(None, ge=1, le=12),
    declared_day: Optional[int] = Query(None, ge=1, le=30),
    sighting_year: Optional[int] = Query(None),
    sighting_month: Optional[int] = Query(None, ge=1, le=12),
    sighting_day: Optional[int] = Query(None, ge=1, le=30),
    observed_at: Optional[str] = Query(None),
):
    if direction not in ("instant-to-calendars", "gregorian-date-to-waqt"):
        raise ApiError(
            400, ErrorCode.VALIDATION_ERROR,
            f"direction must be 'instant-to-calendars' or 'gregorian-date-to-waqt', got {direction!r}.",
            {"received": direction},
        )

    provider = resolve_calendar_provider(
        calendar_provider, override_date,
        declared_year, declared_month, declared_day,
        sighting_year, sighting_month, sighting_day, observed_at,
    )
    profile = AstronomyProfile(
        name="custom", fajr_angle_deg=fajr_angle, isha_angle_deg=isha_angle, asr_shadow_ratio=asr_ratio
    )
    tz_provider = ManualTimezoneProvider(timezone_override) if timezone_override else DEFAULT_TIMEZONE_PROVIDER

    if direction == "gregorian-date-to-waqt":
        if date is None:
            raise ApiError(
                400, ErrorCode.VALIDATION_ERROR,
                "direction=gregorian-date-to-waqt requires 'date'.",
                {},
            )
        location = _location_or_none(lat, lon, elevation_m)
        if location is None:
            raise ApiError(
                400, ErrorCode.VALIDATION_ERROR,
                "direction=gregorian-date-to-waqt requires lat and lon.",
                {},
            )
        g = parse_date(date)

        try:
            day = ci.waqt_day_for_gregorian_date(
                g, location, provider, profile, tz_provider=tz_provider, timescale=DEFAULT_TIMESCALE_PROVIDER
            )
        except ci.CivilDateUnresolvable as exc:
            if exc.reason == "undefined_near_date":
                data = {
                    "direction": direction,
                    "source": {"calendar": "gregorian", "date": g.isoformat()},
                    "location": {"lat": location.lat, "lon": location.lon, "elevation_m": location.elevation_m},
                    "calendar_provider": {"name": provider.name, "version": provider.version},
                    "waqt": {"status": "UNDEFINED", "undefined_reason": str(exc)},
                    "caveat": CAVEAT,
                }
                return success(data)
            raise ApiError(
                422, ErrorCode.CALENDAR_DATE_UNRESOLVABLE, str(exc), {"reason": exc.reason},
            )

        data = {
            "direction": direction,
            "source": {"calendar": "gregorian", "date": g.isoformat()},
            "location": {"lat": location.lat, "lon": location.lon, "elevation_m": location.elevation_m},
            "timezone": timezone_block(tz_provider.timezone_name_for(location.lat, location.lon), day.open),
            "calendar_provider": {"name": provider.name, "version": provider.version},
            "waqt": {
                "status": "OK",
                "hijri": hijri_block(day.hijri_date),
                "weekday": day.weekday,
                "day": {
                    "maghrib_open": iso(day.open),
                    "maghrib_close": iso(day.close),
                    "length_si_seconds": round(day.length_seconds, 3) if day.length_seconds is not None else None,
                },
            },
            "caveat": CAVEAT,
        }
        return success(data)

    # direction == "instant-to-calendars"
    t = parse_instant(instant)
    location = _location_or_none(lat, lon, elevation_m)
    rep = ci.represent_instant(
        t, location, provider, profile, tz_provider=tz_provider, timescale=DEFAULT_TIMESCALE_PROVIDER
    )

    body = rep.to_dict()
    data = {
        "direction": direction,
        "source": {"calendar": "instant", "instant": body["instant"]},
        "location": {"lat": location.lat, "lon": location.lon, "elevation_m": location.elevation_m} if location else None,
        "calendar_provider": {"name": provider.name, "version": provider.version} if location else None,
        "gregorian": {"utc": body["gregorian_utc"], "civil": body["gregorian_civil"]},
        "waqt": {"status": body["waqt_status"], "undefined_reason": body["undefined_reason"], **({"day": body["waqt"]} if body["waqt"] else {})}
        if location else None,
        "profile": profile_block(profile) if location else None,
        "computation": computation_block(DEFAULT_TIMESCALE_PROVIDER.name, DEFAULT_TIMESCALE_PROVIDER.delta_t_seconds(rep.gregorian_utc.date)) if location else None,
        "caveat": CAVEAT,
    }
    return success(data)


@router.get("/v1/calendar/boundary-crossing")
def boundary_crossing(
    start: str = Query(..., description="ISO 8601 UTC instant: span start"),
    end: str = Query(..., description="ISO 8601 UTC instant: span end (exclusive)"),
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    elevation_m: float = Query(0.0, ge=0),
    timezone_override: Optional[str] = Query(None, description="IANA zone to force, skipping lookup"),
):
    """Does the half-open span [start, end) cross civil midnight, a
    Maghrib boundary, both, or neither at this location — reported as
    two independent facts (module docstring §4 of calendar_interop.py;
    see also docs/CALENDAR-INTEROP.md and Sprint 6's
    SpanClassification.crosses_civil_midnight/.crosses_maghrib, which
    this endpoint deliberately agrees with)."""
    s = parse_instant(start)
    e = parse_instant(end)
    location = Location(lat=lat, lon=lon, elevation_m=elevation_m)
    tz_provider = ManualTimezoneProvider(timezone_override) if timezone_override else DEFAULT_TIMEZONE_PROVIDER

    if e <= s:
        raise ApiError(
            400, ErrorCode.INVALID_SPAN,
            "end must be strictly after start (a half-open span cannot be empty or reversed).",
            {"start": iso(s), "end": iso(e)},
        )

    try:
        crossing = ci.classify_boundary_crossing(
            s, e, location, tz_provider=tz_provider, timescale=DEFAULT_TIMESCALE_PROVIDER
        )
    except ci.CivilDateUnresolvable as exc:
        data = {
            "start": iso(s), "end": iso(e),
            "location": {"lat": lat, "lon": lon, "elevation_m": elevation_m},
            "status": "UNDEFINED",
            "undefined_reason": str(exc),
            "caveat": CAVEAT,
        }
        return success(data)

    data = {**crossing.to_dict(), "status": "OK",
            "location": {"lat": lat, "lon": lon, "elevation_m": elevation_m}, "caveat": CAVEAT}
    return success(data)

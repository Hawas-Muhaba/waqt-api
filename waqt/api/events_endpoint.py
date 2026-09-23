"""
waqt.api.events_endpoint — GET /v1/events

Just the six solar/prayer events for the Waqt day containing `instant`,
with their positions on that day's hour grid. Independent of any
calendar_provider — the calendar has no way to influence solar
astronomy, and this endpoint's shape proves it by not accepting a
calendar_provider parameter at all.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from ..core import AstronomyProfile, Location, compute_waqt
from ..hijri import ArithmeticTabularProvider
from ..timescale import DEFAULT_TIMESCALE_PROVIDER
from ..timezone_provider import DEFAULT_TIMEZONE_PROVIDER, ManualTimezoneProvider
from .common import computation_block, iso, parse_instant, profile_block, reading, success, timezone_block

router = APIRouter()

_UNUSED_PROVIDER = ArithmeticTabularProvider()  # events don't depend on the calendar; see module docstring


@router.get("/v1/events")
def get_events(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    elevation_m: float = Query(0.0, ge=0),
    instant: Optional[str] = Query(None, description="ISO 8601 UTC instant; defaults to now"),
    timezone_override: Optional[str] = Query(None, description="IANA zone to force, skipping lookup"),
    fajr_angle: float = Query(18.0, description="Fajr depression angle, degrees"),
    isha_angle: float = Query(17.0, description="Isha depression angle, degrees"),
    asr_ratio: float = Query(1.0, description="Asr shadow ratio: 1.0 = standard, 2.0 = Hanafi"),
):
    t = parse_instant(instant)
    location = Location(lat=lat, lon=lon, elevation_m=elevation_m)
    profile = AstronomyProfile(name="custom", fajr_angle_deg=fajr_angle, isha_angle_deg=isha_angle, asr_shadow_ratio=asr_ratio)
    tz_provider = ManualTimezoneProvider(timezone_override) if timezone_override else DEFAULT_TIMEZONE_PROVIDER

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

    data = {
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
    return success(data)

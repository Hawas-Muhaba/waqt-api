"""
waqt.api.day_endpoint — GET /v1/day

The Core Time Model's Sec 2-3 skeleton, on its own: just the day
boundary and its length. No calendar (the Hijri date is irrelevant to
where Maghrib falls) and no events (those need an astronomy profile
this endpoint deliberately doesn't ask for). For a caller who only
needs "when does today start and end here" — a scheduling system,
say — this is cheaper to reason about than parsing it out of the full
/v1/waqt response.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from ..core import AstronomyProfile, Location, compute_waqt
from ..hijri import ArithmeticTabularProvider
from ..timescale import DEFAULT_TIMESCALE_PROVIDER
from ..timezone_provider import DEFAULT_TIMEZONE_PROVIDER, ManualTimezoneProvider
from .common import computation_block, iso, parse_instant, success, timezone_block

router = APIRouter()

# Day boundary computation needs SOME calendar provider parameter internally
# (compute_waqt's signature requires one) even though this endpoint never
# returns a Hijri date. Using the cheapest, dependency-free one avoids
# paying for ephem/umm-al-qura's setup for a question that doesn't need it.
_UNUSED_PROVIDER = ArithmeticTabularProvider()


@router.get("/v1/day")
def get_day(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    elevation_m: float = Query(0.0, ge=0),
    instant: Optional[str] = Query(None, description="ISO 8601 UTC instant; defaults to now"),
    timezone_override: Optional[str] = Query(None, description="IANA zone to force, skipping lookup"),
):
    t = parse_instant(instant)
    location = Location(lat=lat, lon=lon, elevation_m=elevation_m)
    tz_provider = ManualTimezoneProvider(timezone_override) if timezone_override else DEFAULT_TIMEZONE_PROVIDER

    r = compute_waqt(
        t, location, _UNUSED_PROVIDER, AstronomyProfile(),
        tz_provider=tz_provider, timescale=DEFAULT_TIMESCALE_PROVIDER,
    )

    data = {
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
    return success(data)

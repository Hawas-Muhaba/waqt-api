"""
waqt.api.location_endpoint — GET /v1/location

Exposes Sprint 2's timezone_provider mechanism directly: given
coordinates (and optionally an instant), what IANA timezone is this,
and what civil calendar date is it there right now. Useful on its own
for debugging a date that looks wrong elsewhere in the API — it isolates
"what date did Waqt think it was here" from all the astronomy.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from ..timezone_provider import DEFAULT_TIMEZONE_PROVIDER, ManualTimezoneProvider
from .common import iso, parse_instant, success, timezone_block

router = APIRouter()


@router.get("/v1/location")
def get_location(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    instant: Optional[str] = Query(None, description="ISO 8601 UTC instant; defaults to now"),
    timezone_override: Optional[str] = Query(None, description="IANA zone to force, skipping lookup"),
):
    t = parse_instant(instant)
    tz_provider = ManualTimezoneProvider(timezone_override) if timezone_override else DEFAULT_TIMEZONE_PROVIDER

    tz_name = tz_provider.timezone_name_for(lat, lon)
    local_date = tz_provider.local_date(t, lat, lon)

    data = {
        "location": {"lat": lat, "lon": lon},
        "instant": iso(t),
        "timezone": timezone_block(tz_name, t),
        "local_civil_date": local_date.isoformat(),
    }
    return success(data)

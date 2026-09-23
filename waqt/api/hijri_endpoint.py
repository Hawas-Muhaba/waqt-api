"""
waqt.api.hijri_endpoint — GET /v1/hijri

Deliberately takes NO lat/lon. Per the Core Time Model Sec 1, the
Gregorian-to-Hijri mapping is location-independent — Makkah computes
the date once, for everyone. This endpoint's own shape is the
demonstration of that principle: it only accepts a plain Gregorian
`date`, a calendar_provider, and (for declared/local-observation) the
override parameters.

IMPORTANT — this is the piece most likely to confuse a first-time
caller, so it's worth saying plainly here too (see docs/CALENDARS.md
for the full explanation): the `date` you pass here must be the
Gregorian date that a Waqt day's Maghrib CLOSES on (Sec 2's label
rule), not the date you started your evening on. If you don't already
know that date for your location/instant, get it first from
GET /v1/day (its `day.maghrib_close` instant's calendar date) or from
GET /v1/waqt directly.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from ..hijri import weekday_name
from .common import hijri_block, parse_date, success
from .providers import PROVIDER_CATALOG, resolve_calendar_provider

router = APIRouter()


@router.get("/v1/hijri")
def get_hijri(
    date: Optional[str] = Query(None, description="Gregorian date, YYYY-MM-DD; defaults to today (UTC)"),
    calendar_provider: str = Query("arithmetic-tabular", description=f"One of: {', '.join(PROVIDER_CATALOG)}"),
    override_date: Optional[str] = Query(None, description="declared/local-observation: must equal `date` above to take effect"),
    declared_year: Optional[int] = Query(None),
    declared_month: Optional[int] = Query(None, ge=1, le=12),
    declared_day: Optional[int] = Query(None, ge=1, le=30),
    sighting_year: Optional[int] = Query(None),
    sighting_month: Optional[int] = Query(None, ge=1, le=12),
    sighting_day: Optional[int] = Query(None, ge=1, le=30),
    observed_at: Optional[str] = Query(None),
):
    d = parse_date(date)
    provider = resolve_calendar_provider(
        calendar_provider, override_date,
        declared_year, declared_month, declared_day,
        sighting_year, sighting_month, sighting_day, observed_at,
    )

    hd = provider.from_gregorian(d)

    data = {
        "gregorian_date": d.isoformat(),
        "weekday": weekday_name(d),
        "hijri": hijri_block(hd),
    }
    return success(data)

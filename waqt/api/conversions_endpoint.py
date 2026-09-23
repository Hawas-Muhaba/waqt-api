"""
waqt.api.conversions_endpoint — GET /v1/conversions

Bidirectional Gregorian <-> Hijri conversion, independent of any
instant/location/astronomy — a pure calendar utility. Only providers
that implement `to_gregorian` support the hijri-to-gregorian direction
(currently arithmetic-tabular and umm-al-qura; declared and
local-observation cannot invert a sparse override table, and say so
via UNSUPPORTED_OPERATION rather than guessing).
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from .common import ApiError, ErrorCode, hijri_block, parse_date, success
from .providers import PROVIDER_CATALOG, resolve_calendar_provider
from ..hijri import weekday_name

router = APIRouter()


@router.get("/v1/conversions")
def convert(
    direction: str = Query(..., description="'to-hijri' or 'to-gregorian'"),
    calendar_provider: str = Query("arithmetic-tabular", description=f"One of: {', '.join(PROVIDER_CATALOG)}"),
    date: Optional[str] = Query(None, description="to-hijri: the Gregorian date, YYYY-MM-DD"),
    year: Optional[int] = Query(None, description="to-gregorian: Hijri year"),
    month: Optional[int] = Query(None, ge=1, le=12, description="to-gregorian: Hijri month (1-12)"),
    day: Optional[int] = Query(None, ge=1, le=30, description="to-gregorian: Hijri day (1-30)"),
):
    if direction not in ("to-hijri", "to-gregorian"):
        raise ApiError(
            400, ErrorCode.VALIDATION_ERROR,
            f"direction must be 'to-hijri' or 'to-gregorian', got {direction!r}.",
            {"received": direction},
        )

    provider = resolve_calendar_provider(calendar_provider)

    if direction == "to-hijri":
        g = parse_date(date)
        hd = provider.from_gregorian(g)
        return success({
            "direction": "to-hijri",
            "input": {"gregorian_date": g.isoformat()},
            "output": {"hijri": hijri_block(hd)},
        })

    # to-gregorian
    if year is None or month is None or day is None:
        raise ApiError(
            400, ErrorCode.VALIDATION_ERROR,
            "direction=to-gregorian requires year, month, and day.",
            {"received": {"year": year, "month": month, "day": day}},
        )
    if not hasattr(provider, "to_gregorian"):
        raise ApiError(
            400, ErrorCode.UNSUPPORTED_OPERATION,
            f"calendar_provider={calendar_provider!r} cannot convert Hijri -> Gregorian "
            f"(it has no fixed rule to invert — see GET /v1/calendar).",
            {"calendar_provider": calendar_provider},
        )
    g = provider.to_gregorian(year, month, day)
    return success({
        "direction": "to-gregorian",
        "input": {"hijri": {"year": year, "month": month, "day": day}},
        "output": {"gregorian_date": g.isoformat(), "weekday": weekday_name(g)},
    })

"""
waqt_client._requests — pure query-parameter builders, one per endpoint.

Kept separate from client.py/async_client.py so the sync and async
clients can share the exact same request-building logic (no I/O here at
all) instead of maintaining two copies. Each function's keyword names
mirror the FastAPI `Query(...)` parameter names in `waqt/api/*_endpoint.py`
exactly, so a caller reading docs/API.md never has to translate a name.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional


def _fmt_instant(v: Optional[Any]) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    return v


def _fmt_date(v: Optional[Any]) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, date):
        return v.isoformat()
    return v


def _drop_none(params: dict) -> dict:
    return {k: v for k, v in params.items() if v is not None}


def body_json(body: Any) -> dict:
    """Accepts either a plain `dict` (the Sprint 9 wire-format contract,
    unchanged) or any object exposing `.to_json()` -- what every class in
    `waqt_client.requests` (Sprint 10's typed request builders) provides.
    Never requires the typed classes; always accepts them."""
    return body.to_json() if hasattr(body, "to_json") else body


def waqt_params(
    lat: float, lon: float, *, elevation_m: float = 0.0, instant=None,
    timezone_override: Optional[str] = None, fajr_angle: Optional[float] = None,
    isha_angle: Optional[float] = None, asr_ratio: Optional[float] = None,
    calendar_provider: Optional[str] = None, override_date=None,
    declared_year: Optional[int] = None, declared_month: Optional[int] = None,
    declared_day: Optional[int] = None, sighting_year: Optional[int] = None,
    sighting_month: Optional[int] = None, sighting_day: Optional[int] = None,
    observed_at: Optional[str] = None,
) -> dict:
    return _drop_none({
        "lat": lat, "lon": lon, "elevation_m": elevation_m,
        "instant": _fmt_instant(instant), "timezone_override": timezone_override,
        "fajr_angle": fajr_angle, "isha_angle": isha_angle, "asr_ratio": asr_ratio,
        "calendar_provider": calendar_provider, "override_date": _fmt_date(override_date),
        "declared_year": declared_year, "declared_month": declared_month, "declared_day": declared_day,
        "sighting_year": sighting_year, "sighting_month": sighting_month, "sighting_day": sighting_day,
        "observed_at": observed_at,
    })


def day_params(lat, lon, *, elevation_m=0.0, instant=None, timezone_override=None) -> dict:
    return _drop_none({
        "lat": lat, "lon": lon, "elevation_m": elevation_m,
        "instant": _fmt_instant(instant), "timezone_override": timezone_override,
    })


def events_params(
    lat, lon, *, elevation_m=0.0, instant=None, timezone_override=None,
    fajr_angle=None, isha_angle=None, asr_ratio=None,
) -> dict:
    return _drop_none({
        "lat": lat, "lon": lon, "elevation_m": elevation_m,
        "instant": _fmt_instant(instant), "timezone_override": timezone_override,
        "fajr_angle": fajr_angle, "isha_angle": isha_angle, "asr_ratio": asr_ratio,
    })


def hijri_params(
    *, date=None, calendar_provider=None, override_date=None,
    declared_year=None, declared_month=None, declared_day=None,
    sighting_year=None, sighting_month=None, sighting_day=None, observed_at=None,
) -> dict:
    return _drop_none({
        "date": _fmt_date(date), "calendar_provider": calendar_provider,
        "override_date": _fmt_date(override_date),
        "declared_year": declared_year, "declared_month": declared_month, "declared_day": declared_day,
        "sighting_year": sighting_year, "sighting_month": sighting_month, "sighting_day": sighting_day,
        "observed_at": observed_at,
    })


def location_params(lat, lon, *, instant=None, timezone_override=None) -> dict:
    return _drop_none({
        "lat": lat, "lon": lon, "instant": _fmt_instant(instant), "timezone_override": timezone_override,
    })


def conversions_params(
    direction: str, *, calendar_provider=None, date=None, year=None, month=None, day=None,
) -> dict:
    return _drop_none({
        "direction": direction, "calendar_provider": calendar_provider,
        "date": _fmt_date(date), "year": year, "month": month, "day": day,
    })


def calendar_convert_params(
    *, direction="instant-to-calendars", instant=None, date=None, lat=None, lon=None,
    elevation_m=0.0, timezone_override=None, fajr_angle=None, isha_angle=None, asr_ratio=None,
    calendar_provider=None, override_date=None, declared_year=None, declared_month=None,
    declared_day=None, sighting_year=None, sighting_month=None, sighting_day=None, observed_at=None,
) -> dict:
    return _drop_none({
        "direction": direction, "instant": _fmt_instant(instant), "date": _fmt_date(date),
        "lat": lat, "lon": lon, "elevation_m": elevation_m, "timezone_override": timezone_override,
        "fajr_angle": fajr_angle, "isha_angle": isha_angle, "asr_ratio": asr_ratio,
        "calendar_provider": calendar_provider, "override_date": _fmt_date(override_date),
        "declared_year": declared_year, "declared_month": declared_month, "declared_day": declared_day,
        "sighting_year": sighting_year, "sighting_month": sighting_month, "sighting_day": sighting_day,
        "observed_at": observed_at,
    })


def boundary_crossing_params(start, end, lat, lon, *, elevation_m=0.0, timezone_override=None) -> dict:
    return _drop_none({
        "start": _fmt_instant(start), "end": _fmt_instant(end), "lat": lat, "lon": lon,
        "elevation_m": elevation_m, "timezone_override": timezone_override,
    })


def snapshot_params(
    lat, lon, *, elevation_m=0.0, instant=None, timezone_override=None,
    fajr_angle=None, isha_angle=None, asr_ratio=None, calendar_provider=None,
    precision=None,
) -> dict:
    return _drop_none({
        "lat": lat, "lon": lon, "elevation_m": elevation_m, "instant": _fmt_instant(instant),
        "timezone_override": timezone_override, "fajr_angle": fajr_angle, "isha_angle": isha_angle,
        "asr_ratio": asr_ratio, "calendar_provider": calendar_provider, "precision": precision,
    })


def span_params(
    lat, lon, start, end, *, end_inclusive=None, elevation_m=0.0, timezone_override=None,
    calendar_provider=None, precision=None,
) -> dict:
    return _drop_none({
        "lat": lat, "lon": lon, "start": _fmt_instant(start), "end": _fmt_instant(end),
        "end_inclusive": end_inclusive, "elevation_m": elevation_m,
        "timezone_override": timezone_override, "calendar_provider": calendar_provider,
        "precision": precision,
    })


def institutional_week_params(
    lat, lon, *, elevation_m=0.0, instant=None, first_day=None, jumuah_day=None,
    calendar_provider=None,
) -> dict:
    return _drop_none({
        "lat": lat, "lon": lon, "elevation_m": elevation_m, "instant": _fmt_instant(instant),
        "first_day": first_day, "jumuah_day": jumuah_day, "calendar_provider": calendar_provider,
    })


def institutional_profile_params(*, calendar_provider=None) -> dict:
    return _drop_none({"calendar_provider": calendar_provider})

"""
waqt.api.institutional_endpoint — Sprint 7: the institutional calendar
layer over HTTP.

  GET  /v1/institutional/week                the Islamic week containing an instant
  GET  /v1/institutional/fiscal-year         the brief's default fiscal year (Muharram 1 -> end Dhu al-Hijjah)
  POST /v1/institutional/fiscal-year/resolve a custom FiscalCalendar (caller-supplied start/end rules)
  GET  /v1/institutional/academic-year       the brief's default academic year (first Ahad Muharram -> last Khamis Sha'ban)
  POST /v1/institutional/academic-year/resolve a custom AcademicCalendar (terms, holidays)
  GET  /v1/institutional/profile             a demo CalendarProfile as pure data (see waqt.institutional.profile)

Conventions inherited from the rest of v1: the standard meta/data/error
envelope; a malformed rule is 400 INVALID_CALENDAR_RULE (a caller
mistake); a well-formed rule that cannot be resolved for astronomical
reasons (a boundary falling on an undefined Waqt day) is also reported
through INVALID_CALENDAR_RULE with a 200-adjacent posture is NOT used
here — unlike scheduling, a fiscal/academic-year boundary that cannot
be resolved has no partial "here's the calendar fact, astronomy is
undefined" answer to fall back to (the whole point was the Waqt-day
binding), so it is a 422 UNPROCESSABLE with details, not a 200.
Every response carries the same `caveat` field the scheduling endpoint
does: Waqt states calendar facts, not the institution's obligations.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Callable, Optional, TypeVar

from fastapi import APIRouter, Body, Query

from waqt_core.core import Location
from waqt_core.hijri import HijriDate
from waqt_core.institutional import (
    AcademicCalendar,
    CalendarProfile,
    FiscalCalendar,
    HolidayDefinition,
    RuleError,
    TermDefinition,
    WeekDefinition,
    default_islamic_academic_calendar,
    default_islamic_fiscal_calendar,
    default_profile,
    rule_from_dict,
    week_containing,
)
from waqt_core.scheduling import SchedulingContext
from .common import ApiError, ErrorCode, hijri_block, iso, reject_null_fields, success
from .providers import DEFAULT_CALENDAR_PROVIDER, PROVIDER_CATALOG, provider_identity, resolve_calendar_provider

router = APIRouter()

CAVEAT = (
    "Waqt states calendar facts derived from a Hijri calendar provider and an institutional convention "
    "(which day starts the week, which rule opens a fiscal or academic year). It does not decide whether "
    "an institution should adopt any particular convention."
)


def _provider(name: str):
    return resolve_calendar_provider(name, batch=True)


def _optional_location(loc: Optional[dict]) -> Optional[Location]:
    if loc is None:
        return None
    if not isinstance(loc, dict) or "lat" not in loc or "lon" not in loc:
        raise ApiError(422, ErrorCode.VALIDATION_ERROR, "`location` must be an object with `lat` and `lon`", {})
    lat, lon, elev = loc["lat"], loc["lon"], loc.get("elevation_m", 0.0)
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in (lat, lon, elev)):
        raise ApiError(422, ErrorCode.VALIDATION_ERROR, "location coordinates and elevation must be JSON numbers", {})
    if any(isinstance(value, float) and not math.isfinite(value) for value in (lat, lon, elev)):
        raise ApiError(422, ErrorCode.VALIDATION_ERROR, "location coordinates and elevation must be finite", {})
    if not (-90 <= lat <= 90 and -180 <= lon <= 180 and elev >= 0):
        raise ApiError(422, ErrorCode.VALIDATION_ERROR, "location out of range (|lat|<=90, |lon|<=180, elevation_m>=0)", {})
    return Location(lat, lon, elev)


def _body_integer(body: dict, field: str) -> int:
    value = body.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ApiError(422, ErrorCode.VALIDATION_ERROR, f"`{field}` must be a positive JSON integer", {"received": value})
    return value


def _body_string(body: dict, field: str, default: str) -> str:
    value = body.get(field, default)
    if not isinstance(value, str):
        raise ApiError(422, ErrorCode.VALIDATION_ERROR, f"`{field}` must be a string", {"received": value})
    return value


def _body_list(body: dict, field: str) -> list:
    value = body.get(field, [])
    if not isinstance(value, list):
        raise ApiError(422, ErrorCode.VALIDATION_ERROR, f"`{field}` must be a JSON array", {"received": value})
    return value


def _hijri_year_for_instant(instant: Optional[str], provider) -> int:
    from .common import parse_instant

    t = parse_instant(instant)
    return provider.from_gregorian(t.astimezone(timezone.utc).date()).year


_T = TypeVar("_T")


def _resolve_and_wrap(build: Callable[[], _T], label: str) -> _T:
    try:
        return build()
    except RuleError as e:
        raise ApiError(422, ErrorCode.INVALID_CALENDAR_RULE, f"{label}: {e}", {})


# ---------------------------------------------------------------------------
# Week
# ---------------------------------------------------------------------------


@router.get("/v1/institutional/week")
def get_week(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    elevation_m: float = Query(0.0, ge=0),
    instant: Optional[str] = Query(None, description="ISO 8601 UTC instant; defaults to now"),
    first_day: str = Query("al-Ahad", description="Islamic weekday name that starts the week"),
    jumuah_day: str = Query("al-Jumuah"),
    calendar_provider: str = Query(DEFAULT_CALENDAR_PROVIDER),
):
    from .common import parse_instant

    t = parse_instant(instant)
    try:
        defn = WeekDefinition(first_day=first_day, jumuah_day=jumuah_day)
    except RuleError as e:
        raise ApiError(400, ErrorCode.INVALID_CALENDAR_RULE, str(e), {})
    provider = _provider(calendar_provider)
    ctx = SchedulingContext(Location(lat, lon, elevation_m), calendar_provider=provider)
    week = _resolve_and_wrap(lambda: week_containing(ctx, t, defn), "week")
    return success({**week.to_dict(ctx), "calendar_provider": provider_identity(provider), "caveat": CAVEAT})


# ---------------------------------------------------------------------------
# Fiscal year
# ---------------------------------------------------------------------------


@router.get("/v1/institutional/fiscal-year")
def get_fiscal_year(
    hijri_year: Optional[int] = Query(None),
    instant: Optional[str] = Query(None, description="Used to infer hijri_year if hijri_year is omitted"),
    lat: Optional[float] = Query(None, ge=-90, le=90),
    lon: Optional[float] = Query(None, ge=-180, le=180),
    elevation_m: float = Query(0.0, ge=0),
    calendar_provider: str = Query(DEFAULT_CALENDAR_PROVIDER),
):
    provider = _provider(calendar_provider)
    year = hijri_year if hijri_year is not None else _hijri_year_for_instant(instant, provider)
    ctx = None
    if lat is not None and lon is not None:
        ctx = SchedulingContext(Location(lat, lon, elevation_m), calendar_provider=provider)
    fc = default_islamic_fiscal_calendar(provider)
    fy = _resolve_and_wrap(lambda: fc.year(year, ctx=ctx), "fiscal-year")
    return success({**fy.to_dict(), "definition": fc.to_dict(), "calendar_provider": provider_identity(provider), "caveat": CAVEAT})


@router.post("/v1/institutional/fiscal-year/resolve")
def post_fiscal_year_resolve(
    body: dict[str, Any] = Body(
        ...,
        examples=[{
            "hijri_year": 1448,
            "start_rule": {"type": "month_day", "month": 1, "day": 1},
            "end_rule": {"type": "month_end", "month": 12},
            "label": "Custom Fiscal Year",
        }],
    ),
):
    if not isinstance(body, dict):
        raise ApiError(400, ErrorCode.INVALID_CALENDAR_RULE, "Request body must be a JSON object", {})
    reject_null_fields(body, ("calendar_provider", "location", "label"))
    if "hijri_year" not in body:
        raise ApiError(422, ErrorCode.VALIDATION_ERROR, "`hijri_year` is required", {})
    hijri_year = _body_integer(body, "hijri_year")
    provider = _provider(_body_string(body, "calendar_provider", DEFAULT_CALENDAR_PROVIDER))
    loc = _optional_location(body.get("location"))
    ctx = SchedulingContext(loc, calendar_provider=provider) if loc is not None else None
    if not isinstance(body.get("start_rule"), dict) or not isinstance(body.get("end_rule"), dict):
        raise ApiError(422, ErrorCode.VALIDATION_ERROR, "`start_rule` and `end_rule` must be JSON objects", {})
    label = _body_string(body, "label", "Fiscal Year")

    def build():
        fc = FiscalCalendar(
            start_rule=rule_from_dict(body["start_rule"]), end_rule=rule_from_dict(body["end_rule"]),
            label=label, calendar_provider=provider,
        )
        return fc, fc.year(hijri_year, ctx=ctx)

    fc, fy = _resolve_and_wrap(build, "fiscal-year")
    return success({**fy.to_dict(), "definition": fc.to_dict(), "calendar_provider": provider_identity(provider), "caveat": CAVEAT})


# ---------------------------------------------------------------------------
# Academic year
# ---------------------------------------------------------------------------


@router.get("/v1/institutional/academic-year")
def get_academic_year(
    hijri_year: Optional[int] = Query(None),
    instant: Optional[str] = Query(None, description="Used to infer hijri_year if hijri_year is omitted"),
    lat: Optional[float] = Query(None, ge=-90, le=90),
    lon: Optional[float] = Query(None, ge=-180, le=180),
    elevation_m: float = Query(0.0, ge=0),
    calendar_provider: str = Query(DEFAULT_CALENDAR_PROVIDER),
):
    provider = _provider(calendar_provider)
    year = hijri_year if hijri_year is not None else _hijri_year_for_instant(instant, provider)
    ctx = None
    if lat is not None and lon is not None:
        ctx = SchedulingContext(Location(lat, lon, elevation_m), calendar_provider=provider)
    ac = default_islamic_academic_calendar(provider)
    ay = _resolve_and_wrap(lambda: ac.year(year, ctx=ctx), "academic-year")
    return success({**ay.to_dict(), "definition": ac.to_dict(), "calendar_provider": provider_identity(provider), "caveat": CAVEAT})


def _term_defs(raw: list) -> tuple:
    if any(not isinstance(t, dict) for t in raw):
        raise ApiError(422, ErrorCode.VALIDATION_ERROR, "`term_rules` entries must be JSON objects", {})
    for term in raw:
        missing = [key for key in ("label", "start_rule", "end_rule") if key not in term]
        if missing:
            raise ApiError(422, ErrorCode.VALIDATION_ERROR, f"term missing required field(s): {', '.join(missing)}", {})
        offset = term.get("year_offset", 0)
        if not isinstance(offset, int) or isinstance(offset, bool):
            raise ApiError(422, ErrorCode.VALIDATION_ERROR, "term `year_offset` must be an integer", {"received": offset})
        if not isinstance(term.get("label"), str):
            raise ApiError(422, ErrorCode.VALIDATION_ERROR, "term `label` must be a string", {"received": term.get("label")})
    try:
        return tuple(
            TermDefinition(
                t["label"], rule_from_dict(t["start_rule"]), rule_from_dict(t["end_rule"]), t.get("year_offset", 0)
            )
            for t in raw
        )
    except RuleError as exc:
        raise ApiError(422, ErrorCode.INVALID_CALENDAR_RULE, f"academic-year term: {exc}", {}) from exc


def _holiday_defs(raw: list) -> tuple:
    if any(not isinstance(h, dict) for h in raw):
        raise ApiError(422, ErrorCode.VALIDATION_ERROR, "`holidays` entries must be JSON objects", {})
    for holiday in raw:
        missing = [key for key in ("label", "rule") if key not in holiday]
        if missing:
            raise ApiError(422, ErrorCode.VALIDATION_ERROR, f"holiday missing required field(s): {', '.join(missing)}", {})
        offset = holiday.get("year_offset", 0)
        if not isinstance(offset, int) or isinstance(offset, bool):
            raise ApiError(422, ErrorCode.VALIDATION_ERROR, "holiday `year_offset` must be an integer", {"received": offset})
        if not isinstance(holiday.get("label"), str):
            raise ApiError(422, ErrorCode.VALIDATION_ERROR, "holiday `label` must be a string", {"received": holiday.get("label")})
    try:
        return tuple(HolidayDefinition(h["label"], rule_from_dict(h["rule"]), h.get("year_offset", 0)) for h in raw)
    except RuleError as exc:
        raise ApiError(422, ErrorCode.INVALID_CALENDAR_RULE, f"academic-year holiday: {exc}", {}) from exc


@router.post("/v1/institutional/academic-year/resolve")
def post_academic_year_resolve(
    body: dict[str, Any] = Body(
        ...,
        examples=[{
            "hijri_year": 1448,
            "opening_rule": {"type": "nth_weekday_of_month", "weekday": "al-Ahad", "n": 1, "month": 1},
            "closing_rule": {"type": "nth_weekday_of_month", "weekday": "al-Khamis", "n": -1, "month": 8},
            "term_rules": [],
            "holidays": [],
        }],
    ),
):
    if not isinstance(body, dict):
        raise ApiError(400, ErrorCode.INVALID_CALENDAR_RULE, "Request body must be a JSON object", {})
    reject_null_fields(body, ("calendar_provider", "location", "label", "term_rules", "holidays"))
    if "hijri_year" not in body:
        raise ApiError(422, ErrorCode.VALIDATION_ERROR, "`hijri_year` is required", {})
    hijri_year = _body_integer(body, "hijri_year")
    provider = _provider(_body_string(body, "calendar_provider", DEFAULT_CALENDAR_PROVIDER))
    loc = _optional_location(body.get("location"))
    ctx = SchedulingContext(loc, calendar_provider=provider) if loc is not None else None
    if not isinstance(body.get("opening_rule"), dict) or not isinstance(body.get("closing_rule"), dict):
        raise ApiError(422, ErrorCode.VALIDATION_ERROR, "`opening_rule` and `closing_rule` must be JSON objects", {})
    term_rules = _term_defs(_body_list(body, "term_rules"))
    holidays = _holiday_defs(_body_list(body, "holidays"))
    label = _body_string(body, "label", "Academic Year")

    def build():
        ac = AcademicCalendar(
            opening_rule=rule_from_dict(body["opening_rule"]), closing_rule=rule_from_dict(body["closing_rule"]),
            term_rules=term_rules, holidays=holidays, label=label,
            calendar_provider=provider,
        )
        return ac, ac.year(hijri_year, ctx=ctx)

    ac, ay = _resolve_and_wrap(build, "academic-year")
    return success({**ay.to_dict(), "definition": ac.to_dict(), "calendar_provider": provider_identity(provider), "caveat": CAVEAT})


# ---------------------------------------------------------------------------
# Profile (discovery / demo)
# ---------------------------------------------------------------------------


@router.get("/v1/institutional/profile")
def get_default_profile(calendar_provider: str = Query(DEFAULT_CALENDAR_PROVIDER)):
    """A demo CalendarProfile as pure data — see waqt.institutional.profile.
    Not a claim that this is THE profile; it demonstrates the shape."""
    provider = _provider(calendar_provider)
    profile = default_profile(name=f"demo-{calendar_provider}", calendar_provider=provider)
    return success({"profile": profile.to_dict(), "caveat": CAVEAT})

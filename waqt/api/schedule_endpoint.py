"""
waqt.api.schedule_endpoint — Sprint 6: the Islamic scheduling layer over HTTP.

  GET  /v1/schedule/snapshot   the standard questions, answered for one moment
  GET  /v1/schedule/span       does [start, end) cross a Maghrib boundary?
  POST /v1/schedule/resolve    any rule: points, windows, deadlines, ...

The POST body's `operation` is exactly the JSON operation format the
conformance vectors use (waqt.scheduling.ops), so a caller can take a
rule from a vector, or from docs/SCHEDULING.md, and send it unchanged.

Conventions inherited from the rest of the v1 contract:
  * every response is the standard meta/data/error envelope;
  * undefined astronomy is a 200 with a structured `status`, never an
    error — EVENT_UNDEFINED / WINDOW_UNDEFINED / NO_VALID_WINDOW are
    normal answers at high latitude;
  * a malformed rule is a 400 INVALID_RULE (a caller mistake), which is
    a different thing from a well-formed rule whose astronomy is undefined;
  * instants are rounded to whole seconds at this boundary unless
    `precision=microsecond` is requested (exact boundary tests need it).
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Body, Query

from ..core import AstronomyProfile, Location
from ..scheduling import RuleError, SchedulingContext, SchedulingEngine, run_operation
from ..scheduling.model import parse_instant as parse_rule_instant
from ..timescale import DEFAULT_TIMESCALE_PROVIDER
from ..timezone_provider import DEFAULT_TIMEZONE_PROVIDER, ManualTimezoneProvider
from .common import ApiError, ErrorCode, computation_block, iso, parse_instant, profile_block, success, timezone_block
from .providers import PROVIDER_CATALOG, resolve_calendar_provider

router = APIRouter()

PRECISIONS = ("second", "microsecond")

CAVEAT = (
    "Waqt returns temporal facts derived from an astronomical profile. "
    "It does not decide religious rulings: whether and how an event, offset or window applies to any obligation "
    "is the caller's (or their scholar's) determination."
)


def _check_precision(precision: str) -> bool:
    if precision not in PRECISIONS:
        raise ApiError(400, ErrorCode.VALIDATION_ERROR, f"precision must be one of {list(PRECISIONS)}", {"received": precision})
    return precision == "second"


def _engine(lat, lon, elevation_m, profile, calendar_provider, timezone_override, batch=False):
    # batch=True only for /resolve (recurrences can touch many dates); snapshot/span resolve
    # a bounded handful of labels and may use a single-date live provider.
    provider = resolve_calendar_provider(calendar_provider, batch=batch)
    tz = ManualTimezoneProvider(timezone_override) if timezone_override else DEFAULT_TIMEZONE_PROVIDER
    ctx = SchedulingContext(Location(lat, lon, elevation_m), profile, provider, tz_provider=tz)
    return ctx, SchedulingEngine(ctx)


def _context_block(ctx: SchedulingContext, anchor) -> dict:
    return {
        "location": {"lat": ctx.location.lat, "lon": ctx.location.lon, "elevation_m": ctx.location.elevation_m},
        "profile": profile_block(ctx.profile),
        "calendar_provider": {"name": ctx.calendar_provider.name, "version": ctx.calendar_provider.version,
                              "used_for": "display labels only — never an input to any scheduling result"},
        "computation": computation_block(ctx.timescale.name, ctx.timescale.delta_t_seconds(anchor.date())),
    }


@router.get("/v1/schedule/snapshot")
def get_snapshot(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    elevation_m: float = Query(0.0, ge=0),
    instant: Optional[str] = Query(None, description="ISO 8601 UTC instant; defaults to now"),
    timezone_override: Optional[str] = Query(None),
    fajr_angle: float = Query(18.0),
    isha_angle: float = Query(17.0),
    asr_ratio: float = Query(1.0, description="1.0 standard, 2.0 Hanafi"),
    calendar_provider: str = Query("arithmetic-tabular", description=f"One of: {', '.join(PROVIDER_CATALOG)}. Affects labels only."),
    precision: str = Query("second", description="second | microsecond"),
):
    rs = _check_precision(precision)
    t = parse_instant(instant)
    profile = AstronomyProfile(name="custom", fajr_angle_deg=fajr_angle, isha_angle_deg=isha_angle, asr_shadow_ratio=asr_ratio)
    ctx, eng = _engine(lat, lon, elevation_m, profile, calendar_provider, timezone_override)
    snap = SchedulingEngine.snapshot_to_dict(eng.snapshot(t), rs)
    tz = ctx.tz_provider.timezone_name_for(lat, lon)
    return success({**snap, "timezone": timezone_block(tz, t), **_context_block(ctx, t), "caveat": CAVEAT})


@router.get("/v1/schedule/span")
def get_span(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    start: str = Query(..., description="ISO 8601 UTC instant"),
    end: str = Query(..., description="ISO 8601 UTC instant"),
    end_inclusive: bool = Query(False, description="false: half-open [start, end). true: the instant-pair reading, end included."),
    elevation_m: float = Query(0.0, ge=0),
    timezone_override: Optional[str] = Query(None),
    calendar_provider: str = Query("arithmetic-tabular"),
    precision: str = Query("second"),
):
    rs = _check_precision(precision)
    s, e = parse_instant(start), parse_instant(end)
    ctx, eng = _engine(lat, lon, elevation_m, AstronomyProfile(), calendar_provider, timezone_override)
    result = eng.classify_span(s, e, end_inclusive).to_dict(rs)
    return success({**result, **_context_block(ctx, s), "caveat": CAVEAT})


def _bad_body(message: str, **details) -> ApiError:
    return ApiError(400, ErrorCode.INVALID_RULE, message, details)


def _num(d: dict, key: str, default: Optional[float] = None) -> float:
    v = d.get(key, default)
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ApiError(422, ErrorCode.VALIDATION_ERROR, f"`{key}` must be a number", {"received": v})
    return float(v)


@router.post("/v1/schedule/resolve")
def post_resolve(
    body: dict[str, Any] = Body(
        ...,
        examples=[{
            "location": {"lat": 9.0192, "lon": 38.7525},
            "anchor": "2026-09-19T15:42:00Z",
            "operation": {"op": "resolve_interval", "interval": {
                "type": "interval",
                "start": {"type": "event", "name": "maghrib", "day": 0},
                "end": {"type": "event", "name": "isha", "day": 0}}},
        }],
    ),
):
    """Resolve any scheduling rule. Body:

    `location` {lat, lon, elevation_m?} · `anchor` ISO instant (default now) · `operation` (see docs/SCHEDULING.md §8)
    · optional `profile` {fajr_angle_deg, isha_angle_deg, asr_shadow_ratio}, `calendar_provider`, `timezone_override`, `precision`.
    """
    if not isinstance(body, dict):
        raise _bad_body("Request body must be a JSON object")
    loc = body.get("location")
    if not isinstance(loc, dict) or "lat" not in loc or "lon" not in loc:
        raise ApiError(422, ErrorCode.VALIDATION_ERROR, "`location` must be an object with `lat` and `lon`", {})
    lat, lon, elev = _num(loc, "lat"), _num(loc, "lon"), _num(loc, "elevation_m", 0.0)
    if not (-90 <= lat <= 90 and -180 <= lon <= 180 and elev >= 0):
        raise ApiError(422, ErrorCode.VALIDATION_ERROR, "location out of range (|lat|<=90, |lon|<=180, elevation_m>=0)", {})

    pr = body.get("profile") or {}
    if not isinstance(pr, dict):
        raise ApiError(422, ErrorCode.VALIDATION_ERROR, "`profile` must be an object", {})
    profile = AstronomyProfile(
        name="custom", fajr_angle_deg=_num(pr, "fajr_angle_deg", 18.0), isha_angle_deg=_num(pr, "isha_angle_deg", 17.0),
        asr_shadow_ratio=_num(pr, "asr_shadow_ratio", 1.0),
    )
    rs = _check_precision(body.get("precision", "second"))

    try:
        anchor = parse_rule_instant(body["anchor"]) if body.get("anchor") is not None else parse_instant(None)
    except RuleError as e:
        raise ApiError(400, ErrorCode.INVALID_INSTANT, str(e), {"received": body.get("anchor")})

    ctx, eng = _engine(lat, lon, elev, profile, body.get("calendar_provider", "arithmetic-tabular"), body.get("timezone_override"), batch=True)
    op = body.get("operation")
    try:
        result = run_operation(eng, anchor, op, rs)
    except RuleError as e:
        raise _bad_body(str(e), operation=op if isinstance(op, dict) else None)

    return success({
        "anchor": iso(anchor) if rs else anchor.isoformat(),
        "operation": op["op"],
        "result": result,
        **_context_block(ctx, anchor),
        "caveat": CAVEAT,
    })

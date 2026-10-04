"""
waqt.api.common — the shared contract every v1 endpoint is built on.

This module is the actual answer to "what does the Waqt API v1 promise
a caller who has never read the Python source": one response envelope,
one error shape, one way of representing a duration, one way of
identifying which algorithm produced a number. Every endpoint module
imports from here rather than inventing its own shapes — that
consistency IS the API design, not a formatting nicety.

See docs/API.md for the prose version of everything below, written
for a caller who will never open this file.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import HTTPException
from zoneinfo import ZoneInfo

API_VERSION = "1.6.0"          # this HTTP contract's own version (1.6.0: additive INVALID_HIJRI_DATE / UNKNOWN_TIMEZONE / OUT_OF_RANGE errors; behaviour corrections DIS-001 and OQ-EVT-1, see conformance/CHANGELOG.md; 1.1.0: additive /v1/schedule/*; 1.2.0: additive /v1/institutional/*; 1.3.0: additive /v1/calendar/convert + /v1/calendar/boundary-crossing; 1.4.0: additive computation.engine/revision + /v1/version; 1.5.0: additive hijri.source/provenance, calendar_provider=aladhan, data.calendar_error, per-event representations, integrations in /v1/health + /v1/version, 429 RATE_LIMITED)
CORE_SPEC_VERSION = "waqt-core/0.1"   # the Core Time Model version it implements
# Sprint 12: computation identity is owned by waqt-core (one definition for the
# API, waqt-local, the SDK vectors and the reference apps). These two names are
# kept as read-only aliases for anything that imported them from here.
from waqt_core.versioning import ACCURACY_LEVEL, ENGINE_NAME, ENGINE_REVISION, computation_identity  # noqa: E402
ASTRONOMY_ENGINE_NAME = ENGINE_NAME


# ---------------------------------------------------------------------------
# Error codes — the fixed, documented vocabulary. New codes get added to
# this list and to docs/API.md; endpoints never invent a code inline.
# ---------------------------------------------------------------------------

class ErrorCode:
    INVALID_INSTANT = "INVALID_INSTANT"
    INVALID_DATE = "INVALID_DATE"
    UNKNOWN_CALENDAR_PROVIDER = "UNKNOWN_CALENDAR_PROVIDER"
    UNSUPPORTED_OPERATION = "UNSUPPORTED_OPERATION"
    INVALID_RULE = "INVALID_RULE"              # Sprint 6: a scheduling rule/operation is malformed (a caller mistake, not undefined astronomy)
    INVALID_CALENDAR_RULE = "INVALID_CALENDAR_RULE"  # Sprint 7: a week/fiscal-year/academic-year rule is malformed or unresolvable
    CALENDAR_DATE_UNRESOLVABLE = "CALENDAR_DATE_UNRESOLVABLE"  # Sprint 8: a Gregorian civil date could not be matched to a Waqt day (extreme-offset search exhausted)
    INVALID_SPAN = "INVALID_SPAN"               # Sprint 8: a boundary-crossing span's end is not strictly after its start
    INVALID_HIJRI_DATE = "INVALID_HIJRI_DATE"  # Sprint 16: a (year, month, day) that does not exist in the requested calendar (DIS-002)
    OUT_OF_RANGE = "OUT_OF_RANGE"              # Sprint 16: a date outside a calendar provider's supported range (CAL-011)
    UNKNOWN_TIMEZONE = "UNKNOWN_TIMEZONE"      # Sprint 16: timezone_override is not an IANA zone name (DIS-003)
    VALIDATION_ERROR = "VALIDATION_ERROR"      # request shape/range errors (lat/lon etc.)
    RATE_LIMITED = "RATE_LIMITED"              # Sprint 14: inbound rate limit exceeded (HTTP 429, Retry-After set)
    INTERNAL_ERROR = "INTERNAL_ERROR"          # anything unexpected — always caught, never a raw 500


class ApiError(HTTPException):
    """Raise this (not bare HTTPException) from any endpoint. The
    registered exception handler in waqt.api turns it into the
    standard error envelope automatically."""

    def __init__(self, status_code: int, code: str, message: str, details: Optional[dict] = None):
        super().__init__(status_code=status_code, detail=message)
        self.code = code
        self.message = message
        self.details = details or {}


# ---------------------------------------------------------------------------
# Envelope
# ---------------------------------------------------------------------------

def meta_block(extra: Optional[dict] = None) -> dict:
    m = {
        "api_version": API_VERSION,
        "spec": CORE_SPEC_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    if extra:
        m.update(extra)
    return m


def success(data: dict, meta_extra: Optional[dict] = None) -> dict:
    return {"meta": meta_block(meta_extra), "data": data, "error": None}


def error_body(code: str, message: str, details: Optional[dict] = None) -> dict:
    return {
        "meta": meta_block(),
        "data": None,
        "error": {"code": code, "message": message, "details": details or {}},
    }


# ---------------------------------------------------------------------------
# Shared value formatters — the "units, precision, null behavior" part
# of the contract.
# ---------------------------------------------------------------------------

def iso(dt: Optional[datetime]) -> Optional[str]:
    """UTC instant, ISO 8601, always with an explicit offset. Rounded
    to whole seconds at this presentation boundary only — internal
    computation stays full-precision; this is where it gets cut."""
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def reading(delta: Optional[timedelta]) -> Optional[dict]:
    """A duration/position on the Waqt hour grid. Always both a display
    string AND a machine-parseable seconds value — v1 never returns a
    bare 'HH:MM:SS' string as the whole answer, specifically so a
    caller never has to parse it back apart to do math with it.

    Can exceed 24:00:00 (Core Time Model Sec 3) and the seconds value
    reflects that directly (e.g. 90000.0 for a day that ran long).
    """
    if delta is None:
        return None
    total = delta.total_seconds()
    sign = "-" if total < 0 else ""
    t = abs(total)
    h, rem = divmod(int(t), 3600)
    m, s = divmod(rem, 60)
    return {"display": f"{sign}{h:02d}:{m:02d}:{s:02d}", "seconds": round(total, 3)}


def timezone_block(tz_name: Optional[str], at_instant: Optional[datetime]) -> Optional[dict]:
    """IANA name plus the UTC offset actually in effect at this instant
    (so a caller doesn't have to know DST rules to render local time)."""
    if tz_name is None:
        return None
    offset_seconds = None
    if at_instant is not None:
        try:
            offset = at_instant.astimezone(ZoneInfo(tz_name)).utcoffset()
            offset_seconds = int(offset.total_seconds()) if offset is not None else None
        except Exception:
            offset_seconds = None
    return {"name": tz_name, "utc_offset_seconds": offset_seconds}


def provenance_block(hd) -> Optional[dict]:
    """Sprint 14: extra provenance for providers that consult something outside the
    process. None for purely local providers (their `source` says everything)."""
    p = getattr(hd, "provenance", None)
    if p is None:
        return None
    return {
        "requested_provider": p.requested_provider,
        "cache": p.cache,
        "fetched_at": p.fetched_at,
        "age_seconds": p.age_seconds,
        "ttl_seconds": p.ttl_seconds,
        "upstream_method": p.upstream_method,
        "fallback_reason": p.fallback_reason,
        "fallback_detail": p.fallback_detail,
        "cross_check": p.cross_check,
    }


def hijri_block(hd) -> Optional[dict]:
    if hd is None:
        return None
    return {
        "date": hd.iso_like(),
        "display": str(hd),
        "year": hd.year,
        "month": hd.month,
        "month_name": hd.month_name,
        "day": hd.day,
        "provider": {"name": hd.provider, "version": hd.version},
        "source_note": hd.source_note,
        # Sprint 14 (additive): where this value came from. See waqt_core.hijri.HIJRI_SOURCES.
        "source": hd.source,
        "provenance": provenance_block(hd),
    }


def computation_block(timescale_model: Optional[str], delta_t_seconds: Optional[float]) -> dict:
    """Astronomical-engine identification. Every response that used the solar
    engine says exactly which engine, at which revision, at what accuracy
    level, with what DeltaT.

    Sprint 12 (API 1.4.0, additive): `engine` and `revision` join
    `accuracy_level` as the reproducibility triple (see docs/VERSIONING.md).
    `astronomy_engine` is retained, with the same value as `engine`, so no
    v1 client breaks; new code should read `engine`."""
    ident = computation_identity()
    return {
        "engine": ident["engine"],
        "revision": ident["revision"],
        "accuracy_level": ident["accuracy_level"],
        "astronomy_engine": ident["engine"],   # deprecated alias of `engine`
        "timescale_model": timescale_model,
        "delta_t_seconds": round(delta_t_seconds, 3) if delta_t_seconds is not None else None,
    }


def profile_block(profile) -> dict:
    return {
        "name": profile.name,
        "fajr_angle_deg": profile.fajr_angle_deg,
        "isha_angle_deg": profile.isha_angle_deg,
        "asr_shadow_ratio": profile.asr_shadow_ratio,
    }


# ---------------------------------------------------------------------------
# Shared parsing — every endpoint that takes `instant` or `date` parses
# it exactly the same way and raises exactly the same error on failure.
# ---------------------------------------------------------------------------

def parse_instant(instant: Optional[str]) -> datetime:
    if instant is None:
        return datetime.now(timezone.utc)
    try:
        dt = datetime.fromisoformat(instant.replace("Z", "+00:00"))
    except ValueError:
        raise ApiError(
            400, ErrorCode.INVALID_INSTANT,
            f"Could not parse instant {instant!r} as ISO 8601.",
            {"received": instant, "expected_format": "YYYY-MM-DDTHH:MM:SSZ"},
        )
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def parse_date(date_str: Optional[str], param_name: str = "date") -> date:
    if date_str is None:
        return datetime.now(timezone.utc).date()
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        raise ApiError(
            400, ErrorCode.INVALID_DATE,
            f"Could not parse {param_name} {date_str!r} as YYYY-MM-DD.",
            {"received": date_str, "expected_format": "YYYY-MM-DD"},
        )

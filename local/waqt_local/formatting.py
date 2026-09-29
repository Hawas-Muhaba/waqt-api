"""
waqt_local.formatting — value presentation, independent of waqt.api.

The HTTP server's `waqt.api.common` module defines what a duration, a
timezone block, a Hijri block, or an astronomy-engine identification
"look like" over the wire (docs/API.md). The local library deliberately
does **not** import `waqt.api` (it has no reason to require FastAPI to
be installed, and the architecture in the Sprint 10 brief draws "Local
computation" and "HTTP API" as siblings under the Waqt Specification,
not one depending on the other). Instead this module re-expresses the
same small set of formatting rules directly against `waqt.core` /
`waqt.hijri` value objects.

This is presentation-shaping (units, null behavior, display strings),
not a temporal or astronomical rule — the actual computation these
functions format always comes straight from `waqt.core`, `waqt.solar`,
`waqt.semantics`, `waqt.scheduling`, `waqt.institutional`, and
`waqt.calendar_interop`. See docs/LOCAL.md for the full architecture
note, including where the two presentation layers were deliberately
kept in exact agreement (`tests/test_local_vs_server_equivalence.py`,
in this package's own test suite, checks that agreement automatically
rather than by inspection).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

# Sprint 12: computation identity is owned by waqt-core; waqt-local reports
# exactly what the engine it calls reports (never a second copy of the strings).
from waqt_core.versioning import ACCURACY_LEVEL, ENGINE_NAME, ENGINE_REVISION, computation_identity  # noqa: E402
ASTRONOMY_ENGINE_NAME = ENGINE_NAME
CORE_SPEC_VERSION = "waqt-core/0.1"


def iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def reading(delta: Optional[timedelta]) -> Optional[dict]:
    if delta is None:
        return None
    total = delta.total_seconds()
    sign = "-" if total < 0 else ""
    t = abs(total)
    h, rem = divmod(int(t), 3600)
    m, s = divmod(rem, 60)
    return {"display": f"{sign}{h:02d}:{m:02d}:{s:02d}", "seconds": round(total, 3)}


def timezone_block(tz_name: Optional[str], at_instant: Optional[datetime]) -> Optional[dict]:
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
    }


def computation_block(timescale_model: Optional[str], delta_t_seconds: Optional[float]) -> dict:
    ident = computation_identity()
    return {
        "engine": ident["engine"],
        "revision": ident["revision"],
        "accuracy_level": ident["accuracy_level"],
        "astronomy_engine": ident["engine"],   # deprecated alias of `engine` (kept identical to the API)
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


def parse_instant(value):
    from .errors import InvalidInstantError

    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            raise InvalidInstantError(
                f"Could not parse instant {value!r} as ISO 8601.",
                {"received": value, "expected_format": "YYYY-MM-DDTHH:MM:SSZ"},
            )
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_date(value, param_name: str = "date"):
    from datetime import date as _date

    from .errors import InvalidDateError

    if value is None:
        return datetime.now(timezone.utc).date()
    if isinstance(value, _date):
        return value
    try:
        return _date.fromisoformat(str(value))
    except ValueError:
        raise InvalidDateError(
            f"Could not parse {param_name} {value!r} as YYYY-MM-DD.",
            {"received": value, "expected_format": "YYYY-MM-DD"},
        )

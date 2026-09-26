"""
independent_solar.julian — UTC instant -> Julian Day, independently coded.

Uses the standard Meeus (Astronomical Algorithms, Ch. 7) calendar-to-JD
algorithm directly on a fractional day-of-month, rather than the
JDN-plus-time-of-day split `waqt/solar.py` uses. Both converge on the same
Julian Day for the same instant (they have to — it's the same well-defined
quantity), but the arithmetic path here is written from scratch.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone


def julian_day(dt: datetime) -> float:
    """Fractional Julian Day (UT1/UTC scale) for an aware UTC datetime."""
    if dt.tzinfo is None:
        raise ValueError("julian_day requires a timezone-aware datetime")
    dt = dt.astimezone(timezone.utc)

    year, month = dt.year, dt.month
    day = (
        dt.day
        + dt.hour / 24.0
        + dt.minute / 1440.0
        + (dt.second + dt.microsecond / 1_000_000.0) / 86400.0
    )

    if month <= 2:
        year -= 1
        month += 12

    a = math.floor(year / 100.0)
    # Gregorian calendar throughout (proleptic where needed) — matches this
    # project's own GREGORIAN_CALENDAR_CONTRACT (docs/CALENDAR-INTEROP.md).
    b = 2 - a + math.floor(a / 4.0)

    jd = (
        math.floor(365.25 * (year + 4716))
        + math.floor(30.6001 * (month + 1))
        + day
        + b
        - 1524.5
    )
    return jd


def julian_century(jd: float) -> float:
    """Julian centuries since J2000.0 (JD 2451545.0), TT or UT — caller's choice."""
    return (jd - 2451545.0) / 36525.0

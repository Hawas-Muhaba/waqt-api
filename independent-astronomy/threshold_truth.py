"""
independent-astronomy/threshold_truth.py — Sprint 11.

Physical ground truth for "does this sunrise/sunset exist on this date?",
independent of any engine's event-solving loop: scan the Sun's true
altitude (Level A / VSOP87 positions + GAST, the same reference
positions level_a/ uses) across the half-day window on the relevant side
of transit and ask whether it actually crosses the horizon threshold.

Why this exists: Sprint 11's threshold-day scan (SPRINT-11-REPORT.md Sec
2.4) found that Level A and Level B -- which share a transit-anchored
solving loop that gives up the first time the hour angle is undefined --
are NOT a trustworthy oracle for defined-vs-undefined on the handful of
days around the polar-day threshold. Comparing engines to each other
there just compares their solving loops. This compares them to the
geometry.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone

from independent_solar.deltat import delta_t_seconds
from independent_solar.julian import julian_day
from level_a.sun import apparent_position, apparent_sidereal_time_deg

THRESHOLD_ALTITUDE_DEG = -0.8333


def solar_altitude_deg(t: datetime, lat: float, lon: float) -> float:
    jd_ut = julian_day(t)
    jd_tt = jd_ut + delta_t_seconds(t.date()) / 86400.0
    p = apparent_position(jd_tt)
    h = math.radians(apparent_sidereal_time_deg(jd_tt, jd_ut) + lon - p.right_ascension_deg)
    la, de = math.radians(lat), math.radians(p.declination_deg)
    return math.degrees(math.asin(math.sin(la) * math.sin(de) + math.cos(la) * math.cos(de) * math.cos(h)))


def crossing_exists(d: date, lat: float, lon: float, morning: bool, transit: datetime, step_min: int = 10) -> bool:
    """True iff the Sun crosses THRESHOLD_ALTITUDE_DEG upward (morning) or
    downward (evening) in the 14 h before/after `transit`."""
    minutes = range(-14 * 60, 1, step_min) if morning else range(0, 14 * 60 + 1, step_min)
    alts = [solar_altitude_deg(transit + timedelta(minutes=m), lat, lon) for m in minutes]
    th = THRESHOLD_ALTITUDE_DEG
    if morning:
        return any(alts[i] < th <= alts[i + 1] for i in range(len(alts) - 1))
    return any(alts[i] >= th > alts[i + 1] for i in range(len(alts) - 1))

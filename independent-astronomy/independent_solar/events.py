"""
independent_solar.events — the six solar events, solved via local hour
angle (Greenwich Apparent Sidereal Time + right ascension), never via an
equation of time.

For a target instant t: the sun's local hour angle is
    H(t) = GAST(t) + longitude - RightAscension(t)      [degrees, -180..180]
Transit is where H(t) = 0. A rise/set-type event at target altitude `alt`
is where H(t) = -H0 (morning) or +H0 (evening), with
    H0 = acos( (sin(alt) - sin(lat)sin(dec)) / (cos(lat)cos(dec)) )
the same spherical-triangle altitude formula every sun-position
implementation uses (it is basic spherical astronomy, not
`waqt/solar.py`'s own code -- see the package docstring).

Each target is solved by a small Newton-style loop: H(t) drifts at very
close to the sidereal rate (~360.98565 deg/day = ~15.0410 deg/hour)
because the sun's right ascension itself only creeps ~1 deg/day, so one
correction step lands within a fraction of a second and a handful more
squeeze out any remaining drift from right ascension/declination/H0
themselves changing through the day. This mirrors the general shape of
`waqt/solar.py`'s own two-pass refinement (iterate because the quantities
drift slightly across a day) without sharing its formulas.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from .deltat import delta_t_seconds
from .julian import julian_day
from .sidereal import greenwich_apparent_sidereal_time_deg
from .sun import apparent_position

SIDEREAL_RATE_DEG_PER_HOUR = 360.98564736629 / 24.0  # ~15.0410686...
SUNRISE_SUNSET_ALTITUDE_DEG = -0.8333  # geometric horizon - refraction - solar radius
MAX_ITER = 10
TOL_DEG = 1e-7


def _wrap_pm180(x: float) -> float:
    x = x % 360.0
    if x > 180.0:
        x -= 360.0
    return x


def _dip_of_horizon_deg(elevation_m: float) -> float:
    if elevation_m <= 0:
        return 0.0
    return 1.76 * math.sqrt(elevation_m) / 60.0


def _hour_angle_for_altitude(lat: float, dec: float, altitude_deg: float) -> float | None:
    lat_r, dec_r, alt_r = map(math.radians, (lat, dec, altitude_deg))
    denom = math.cos(lat_r) * math.cos(dec_r)
    if denom == 0:
        return None
    cos_h0 = (math.sin(alt_r) - math.sin(lat_r) * math.sin(dec_r)) / denom
    if cos_h0 < -1.0 or cos_h0 > 1.0:
        return None
    return math.degrees(math.acos(cos_h0))


def _local_hour_angle(dt_utc: datetime, lat: float, lon: float):
    jd_ut = julian_day(dt_utc)
    dtsec = delta_t_seconds(dt_utc.date())
    jd_tt = jd_ut + dtsec / 86400.0
    pos = apparent_position(jd_tt)
    gast = greenwich_apparent_sidereal_time_deg(jd_ut)
    h = _wrap_pm180(gast + lon - pos.right_ascension_deg)
    return h, pos


def _solve(
    d: date, lat: float, lon: float, mode: str, altitude_deg: float | None = None
) -> datetime | None:
    """mode: 'transit', 'morning' (target = -H0), or 'evening' (target = +H0)."""
    t = datetime(d.year, d.month, d.day, 12, 0, 0, tzinfo=timezone.utc) - timedelta(
        hours=lon / 15.0
    )

    for _ in range(MAX_ITER):
        h, pos = _local_hour_angle(t, lat, lon)
        if mode == "transit":
            target = 0.0
        else:
            h0 = _hour_angle_for_altitude(lat, pos.declination_deg, altitude_deg)
            if h0 is None:
                return None
            target = -h0 if mode == "morning" else h0
        diff = _wrap_pm180(h - target)
        if abs(diff) < TOL_DEG:
            return t
        t = t - timedelta(hours=diff / SIDEREAL_RATE_DEG_PER_HOUR)
    return t


def transit(d: date, lat: float, lon: float) -> datetime:
    result = _solve(d, lat, lon, "transit")
    assert result is not None  # transit (H=0) always has a solution
    return result


def sunrise(d: date, lat: float, lon: float, elevation_m: float = 0.0) -> datetime | None:
    alt = SUNRISE_SUNSET_ALTITUDE_DEG - _dip_of_horizon_deg(elevation_m)
    return _solve(d, lat, lon, "morning", alt)


def sunset(d: date, lat: float, lon: float, elevation_m: float = 0.0) -> datetime | None:
    alt = SUNRISE_SUNSET_ALTITUDE_DEG - _dip_of_horizon_deg(elevation_m)
    return _solve(d, lat, lon, "evening", alt)


def fajr(d: date, lat: float, lon: float, angle_deg: float) -> datetime | None:
    return _solve(d, lat, lon, "morning", -angle_deg)


def isha(d: date, lat: float, lon: float, angle_deg: float) -> datetime | None:
    return _solve(d, lat, lon, "evening", -angle_deg)


def asr(d: date, lat: float, lon: float, shadow_ratio: float) -> datetime | None:
    """Shar'i Asr: the instant a vertical gnomon's shadow equals
    shadow_ratio * height plus its own noon shadow length. Declination
    used for the noon-altitude calculation is read at the day's solar
    transit -- the same "compute once near noon" approach
    `waqt/solar.py::asr` takes, arrived at independently."""
    t_noon = transit(d, lat, lon)
    jd_tt = julian_day(t_noon) + delta_t_seconds(d) / 86400.0
    pos_noon = apparent_position(jd_tt)
    dec = pos_noon.declination_deg

    noon_altitude = 90.0 - abs(lat - dec)
    if noon_altitude <= 0:
        return None
    target_altitude = math.degrees(
        math.atan(1.0 / (shadow_ratio + math.tan(math.radians(90.0 - noon_altitude))))
    )
    return _solve(d, lat, lon, "evening", target_altitude)


@dataclass
class IndependentDayEvents:
    date: date
    fajr: datetime | None
    sunrise: datetime | None
    dhuhr: datetime
    asr: datetime | None
    maghrib: datetime | None
    isha: datetime | None


def compute_day_events(
    d: date,
    lat: float,
    lon: float,
    elevation_m: float = 0.0,
    fajr_angle_deg: float = 18.0,
    isha_angle_deg: float = 17.0,
    asr_shadow_ratio: float = 1.0,
) -> IndependentDayEvents:
    return IndependentDayEvents(
        date=d,
        fajr=fajr(d, lat, lon, fajr_angle_deg),
        sunrise=sunrise(d, lat, lon, elevation_m),
        dhuhr=transit(d, lat, lon),
        asr=asr(d, lat, lon, asr_shadow_ratio),
        maghrib=sunset(d, lat, lon, elevation_m),
        isha=isha(d, lat, lon, isha_angle_deg),
    )

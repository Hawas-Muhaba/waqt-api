"""
independent-astronomy/level_a/events — the same six solar events
`independent_solar/events.py` computes, solved the same general way
(local hour angle against Greenwich Apparent Sidereal Time -- ordinary
spherical astronomy, not a Waqt-specific rule), but sourcing the Sun's
position from `level_a/sun.py`'s VSOP87 reference instead of
`independent_solar/sun.py`'s Meeus low-accuracy series.

This file is a small, deliberate duplicate of `independent_solar/
events.py`'s solving loop rather than a shared import, for the same
reason `independent_solar` itself is not built on `waqt/solar.py`: the
point of a comparison reference is that it not share a bug with the
thing it is checking. See `docs/independent-astronomy/LEVEL-A.md`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from independent_solar.deltat import delta_t_seconds
from independent_solar.julian import julian_day

from .sun import apparent_position, apparent_sidereal_time_deg

SIDEREAL_RATE_DEG_PER_HOUR = 360.98564736629 / 24.0
SUNRISE_SUNSET_ALTITUDE_DEG = -0.8333
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


def _hour_angle_for_altitude(lat: float, dec: float, altitude_deg: float):
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
    gast = apparent_sidereal_time_deg(jd_tt, jd_ut)
    h = _wrap_pm180(gast + lon - pos.right_ascension_deg)
    return h, pos


def _solve(d: date, lat: float, lon: float, mode: str, altitude_deg=None):
    t = datetime(d.year, d.month, d.day, 12, 0, 0, tzinfo=timezone.utc) - timedelta(hours=lon / 15.0)

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
    assert result is not None
    return result


def sunrise(d: date, lat: float, lon: float, elevation_m: float = 0.0):
    alt = SUNRISE_SUNSET_ALTITUDE_DEG - _dip_of_horizon_deg(elevation_m)
    return _solve(d, lat, lon, "morning", alt)


def sunset(d: date, lat: float, lon: float, elevation_m: float = 0.0):
    alt = SUNRISE_SUNSET_ALTITUDE_DEG - _dip_of_horizon_deg(elevation_m)
    return _solve(d, lat, lon, "evening", alt)


def fajr(d: date, lat: float, lon: float, angle_deg: float):
    return _solve(d, lat, lon, "morning", -angle_deg)


def isha(d: date, lat: float, lon: float, angle_deg: float):
    return _solve(d, lat, lon, "evening", -angle_deg)


def asr(d: date, lat: float, lon: float, shadow_ratio: float):
    t_noon = transit(d, lat, lon)
    jd_tt = julian_day(t_noon) + delta_t_seconds(d) / 86400.0
    pos_noon = apparent_position(jd_tt)
    dec = pos_noon.declination_deg

    noon_altitude = 90.0 - abs(lat - dec)
    if noon_altitude <= 0:
        return None
    target_altitude = math.degrees(math.atan(1.0 / (shadow_ratio + math.tan(math.radians(90.0 - noon_altitude)))))
    return _solve(d, lat, lon, "evening", target_altitude)


@dataclass
class LevelADayEvents:
    date: date
    fajr: "datetime | None"
    sunrise: "datetime | None"
    dhuhr: datetime
    asr: "datetime | None"
    maghrib: "datetime | None"
    isha: "datetime | None"


def compute_day_events(
    d: date, lat: float, lon: float, elevation_m: float = 0.0,
    fajr_angle_deg: float = 18.0, isha_angle_deg: float = 17.0, asr_shadow_ratio: float = 1.0,
) -> LevelADayEvents:
    return LevelADayEvents(
        date=d,
        fajr=fajr(d, lat, lon, fajr_angle_deg),
        sunrise=sunrise(d, lat, lon, elevation_m),
        dhuhr=transit(d, lat, lon),
        asr=asr(d, lat, lon, asr_shadow_ratio),
        maghrib=sunset(d, lat, lon, elevation_m),
        isha=isha(d, lat, lon, isha_angle_deg),
    )

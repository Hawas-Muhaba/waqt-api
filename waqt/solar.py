"""
waqt.solar — Solar event engine.

Implements the NOAA low-precision solar position algorithm (the same
formulas behind NOAA's public Solar Calculator spreadsheet), generalized
to accept an arbitrary depression angle. This lets one routine compute
sunrise/sunset (0.833 deg depression), Fajr/Isha (any configured angle),
and, via a separate altitude formula, Asr (shadow-ratio based).

Accuracy: ~30-60 seconds versus high-precision ephemerides in most cases
(refined here with a two-pass iteration on the hour angle, which removes
most of the single-pass error). This meets the "Level B" conformance
tolerance (+/-30 SI seconds on anchors) defined in the Waqt proposal.
It has NOT been validated against a Level A (high-precision) reference,
and elevation/atmospheric refraction beyond the standard 34' term are
not modeled. See SCOPE.md.

All inputs/outputs are UTC. No timezone handling is performed here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone


def _jdn(d: date) -> int:
    """Gregorian calendar date -> Julian Day Number (integer, noon-based)."""
    y, m, day = d.year, d.month, d.day
    a = (14 - m) // 12
    y2 = y + 4800 - a
    m2 = m + 12 * a - 3
    return (
        day
        + (153 * m2 + 2) // 5
        + 365 * y2
        + y2 // 4
        - y2 // 100
        + y2 // 400
        - 32045
    )


def _julian_century(jd: float) -> float:
    return (jd - 2451545.0) / 36525.0


@dataclass
class SunParams:
    """Solar position parameters for one instant (as a fraction of a UTC day)."""

    declination_deg: float
    equation_of_time_min: float  # minutes


def _sun_params(jd: float) -> SunParams:
    t = _julian_century(jd)

    geom_mean_long = (280.46646 + t * (36000.76983 + t * 0.0003032)) % 360.0
    geom_mean_anom = 357.52911 + t * (35999.05029 - 0.0001537 * t)
    eccent = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)

    m_rad = math.radians(geom_mean_anom)
    sun_eq_ctr = (
        math.sin(m_rad) * (1.914602 - t * (0.004817 + 0.000014 * t))
        + math.sin(2 * m_rad) * (0.019993 - 0.000101 * t)
        + math.sin(3 * m_rad) * 0.000289
    )

    sun_true_long = geom_mean_long + sun_eq_ctr
    sun_app_long = sun_true_long - 0.00569 - 0.00478 * math.sin(
        math.radians(125.04 - 1934.136 * t)
    )

    mean_obliq = (
        23
        + (26 + (21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))) / 60) / 60
    )
    obliq_corr = mean_obliq + 0.00256 * math.cos(math.radians(125.04 - 1934.136 * t))

    declin = math.degrees(
        math.asin(
            math.sin(math.radians(obliq_corr)) * math.sin(math.radians(sun_app_long))
        )
    )

    y = math.tan(math.radians(obliq_corr / 2)) ** 2
    eq_time = 4 * math.degrees(
        y * math.sin(2 * math.radians(geom_mean_long))
        - 2 * eccent * math.sin(m_rad)
        + 4 * eccent * y * math.sin(m_rad) * math.cos(2 * math.radians(geom_mean_long))
        - 0.5 * y * y * math.sin(4 * math.radians(geom_mean_long))
        - 1.25 * eccent * eccent * math.sin(2 * m_rad)
    )

    return SunParams(declination_deg=declin, equation_of_time_min=eq_time)


def _solar_noon_utc(d: date, lon: float, params: SunParams) -> datetime:
    """UTC instant of solar transit (Dhuhr) for the given date/longitude."""
    minutes_from_utc_midnight = 720.0 - 4.0 * lon - params.equation_of_time_min
    base = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    return base + timedelta(minutes=minutes_from_utc_midnight)


def _hour_angle_for_altitude(lat: float, declin: float, altitude_deg: float) -> float | None:
    """Hour angle (degrees) at which the sun reaches `altitude_deg`.

    Returns None if the sun never reaches that altitude on this day at
    this latitude (permanent day/night at that angle).
    """
    lat_r, decl_r, alt_r = map(math.radians, (lat, declin, altitude_deg))
    cos_ha = (math.sin(alt_r) - math.sin(lat_r) * math.sin(decl_r)) / (
        math.cos(lat_r) * math.cos(decl_r)
    )
    if cos_ha < -1.0 or cos_ha > 1.0:
        return None
    return math.degrees(math.acos(cos_ha))


def _event_time(
    d: date, lat: float, lon: float, altitude_deg: float, morning: bool
) -> datetime | None:
    """Instant the sun crosses `altitude_deg` on date `d` (morning=ascending)."""
    jd = _jdn(d)
    params = _sun_params(jd)
    noon = _solar_noon_utc(d, lon, params)

    ha = _hour_angle_for_altitude(lat, params.declination_deg, altitude_deg)
    if ha is None:
        return None

    offset_min = ha * 4.0
    approx = noon - timedelta(minutes=offset_min) if morning else noon + timedelta(
        minutes=offset_min
    )

    # Iterative refinement: recompute solar params (declination/EoT drift
    # through the day) at each successive estimate. Two passes are enough
    # to bring agreement with a reference ephemeris under ~30 SI seconds
    # in the cases tested; see tests/test_core.py.
    day_start = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    for _ in range(2):
        jd_i = jd + (approx - day_start).total_seconds() / 86400.0
        params_i = _sun_params(jd_i)
        noon_i = _solar_noon_utc(d, lon, params_i)
        ha_i = _hour_angle_for_altitude(lat, params_i.declination_deg, altitude_deg)
        if ha_i is None:
            return approx
        offset_min_i = ha_i * 4.0
        approx = noon_i - timedelta(minutes=offset_min_i) if morning else noon_i + timedelta(
            minutes=offset_min_i
        )
    return approx


# Standard sunrise/sunset altitude: geometric horizon (0 deg) minus the sun's
# angular radius (~16') minus standard atmospheric refraction (~34').
SUNRISE_SUNSET_ALTITUDE_DEG = -0.8333


def transit(d: date, lat: float, lon: float) -> datetime:
    """Solar transit (Dhuhr) — always exists."""
    jd = _jdn(d)
    params = _sun_params(jd)
    return _solar_noon_utc(d, lon, params)


def sunrise(d: date, lat: float, lon: float) -> datetime | None:
    return _event_time(d, lat, lon, SUNRISE_SUNSET_ALTITUDE_DEG, morning=True)


def sunset(d: date, lat: float, lon: float) -> datetime | None:
    return _event_time(d, lat, lon, SUNRISE_SUNSET_ALTITUDE_DEG, morning=False)


def fajr(d: date, lat: float, lon: float, angle_deg: float) -> datetime | None:
    """Fajr — sun at `angle_deg` below the horizon, pre-dawn."""
    return _event_time(d, lat, lon, -angle_deg, morning=True)


def isha(d: date, lat: float, lon: float, angle_deg: float) -> datetime | None:
    """Isha — sun at `angle_deg` below the horizon, post-dusk."""
    return _event_time(d, lat, lon, -angle_deg, morning=False)


def asr(d: date, lat: float, lon: float, shadow_ratio: float) -> datetime | None:
    """Asr — instant a vertical object's shadow equals shadow_ratio * height
    plus its noon shadow length (the standard shar'i definition).

    shadow_ratio = 1 -> Shafi'i/Maliki/Hanbali convention
    shadow_ratio = 2 -> Hanafi convention
    """
    jd = _jdn(d)
    params = _sun_params(jd)
    declin = params.declination_deg
    noon_altitude = 90.0 - abs(lat - declin)
    if noon_altitude <= 0:
        return None  # sun never rises high enough (polar edge case)

    target_altitude = math.degrees(
        math.atan(1.0 / (shadow_ratio + math.tan(math.radians(90.0 - noon_altitude))))
    )
    return _event_time(d, lat, lon, target_altitude, morning=False)


@dataclass
class DayEvents:
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
    fajr_angle_deg: float = 18.0,
    isha_angle_deg: float = 17.0,
    asr_shadow_ratio: float = 1.0,
) -> DayEvents:
    return DayEvents(
        date=d,
        fajr=fajr(d, lat, lon, fajr_angle_deg),
        sunrise=sunrise(d, lat, lon),
        dhuhr=transit(d, lat, lon),
        asr=asr(d, lat, lon, asr_shadow_ratio),
        maghrib=sunset(d, lat, lon),
        isha=isha(d, lat, lon, isha_angle_deg),
    )

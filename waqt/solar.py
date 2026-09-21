"""
waqt.solar — Solar event engine.

Implements the NOAA low-precision solar position algorithm (the same
formulas behind NOAA's public Solar Calculator spreadsheet), generalized
to accept an arbitrary depression angle. This lets one routine compute
sunrise/sunset (0.833 deg depression), Fajr/Isha (any configured angle),
and, via a separate altitude formula, Asr (shadow-ratio based).

Sprint 2 additions over Stage 1:
  - Elevation correction (dip of the horizon), applied to sunrise/sunset
    only — see the note above `_dip_of_horizon_deg` for why.
  - A pluggable TimeScaleProvider (waqt.timescale) supplies DeltaT
    instead of silently treating UTC as Terrestrial Time.

Accuracy: see SCOPE.md and tests/test_core.py for measured numbers.
It is latitude-dependent (tighter near the equator, looser at high
latitude) and has NOT been validated against a Level A / sub-second
ephemeris. All inputs/outputs are UTC; timezone handling lives in
waqt.timezone_provider, not here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from .timescale import DEFAULT_TIMESCALE_PROVIDER, TimeScaleProvider


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
    declination_deg: float
    equation_of_time_min: float  # minutes


def _sun_params(jd_tt: float) -> SunParams:
    """NOTE: `jd_tt` must already be in Terrestrial Time (i.e. UT1's JD
    plus DeltaT/86400) — callers apply the DeltaT shift before calling
    this."""
    t = _julian_century(jd_tt)

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


def _jd_tt(jd_utc: float, d: date, timescale: TimeScaleProvider) -> float:
    return jd_utc + timescale.delta_t_seconds(d) / 86400.0


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
    d: date,
    lat: float,
    lon: float,
    altitude_deg: float,
    morning: bool,
    timescale: TimeScaleProvider = DEFAULT_TIMESCALE_PROVIDER,
) -> datetime | None:
    """Instant the sun crosses `altitude_deg` on date `d` (morning=ascending)."""
    jd = _jdn(d)
    params = _sun_params(_jd_tt(jd, d, timescale))
    noon = _solar_noon_utc(d, lon, params)

    ha = _hour_angle_for_altitude(lat, params.declination_deg, altitude_deg)
    if ha is None:
        return None

    offset_min = ha * 4.0
    approx = noon - timedelta(minutes=offset_min) if morning else noon + timedelta(
        minutes=offset_min
    )

    # Iterative refinement: recompute solar params (declination/EoT drift
    # through the day) at each successive estimate. See tests/test_core.py
    # for measured agreement with an independent reference.
    day_start = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    for _ in range(2):
        jd_i = jd + (approx - day_start).total_seconds() / 86400.0
        params_i = _sun_params(_jd_tt(jd_i, d, timescale))
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


def _dip_of_horizon_deg(elevation_m: float) -> float:
    """Standard dip-of-horizon approximation: dip (arcmin) = 1.76 * sqrt(h).

    Positive elevation makes the effective altitude threshold MORE
    negative (the sun can be lower and still be "up" from the observer's
    higher vantage point) -> later sunset, earlier sunrise.

    Applied to sunrise/sunset only, not Fajr/Isha/Asr. Rationale:
    elevation changes WHERE the physical horizon sits relative to an
    observer (a taller observer sees over the true horizon), and
    sunrise/sunset are defined relative to that physical horizon. Fajr
    and Isha are defined by the sun's depression below the horizontal
    astronomical plane (twilight geometry), which elevation does not
    meaningfully change for civil purposes, and no mainstream
    prayer-time convention applies an elevation correction to them.
    This mirrors the decision recorded in the Core Time Model's D-02.
    """
    if elevation_m <= 0:
        return 0.0
    return 1.76 * math.sqrt(elevation_m) / 60.0


def transit(
    d: date, lat: float, lon: float, timescale: TimeScaleProvider = DEFAULT_TIMESCALE_PROVIDER
) -> datetime:
    """Solar transit (Dhuhr) — always exists."""
    jd = _jdn(d)
    params = _sun_params(_jd_tt(jd, d, timescale))
    return _solar_noon_utc(d, lon, params)


def sunrise(
    d: date,
    lat: float,
    lon: float,
    elevation_m: float = 0.0,
    timescale: TimeScaleProvider = DEFAULT_TIMESCALE_PROVIDER,
) -> datetime | None:
    altitude = SUNRISE_SUNSET_ALTITUDE_DEG - _dip_of_horizon_deg(elevation_m)
    return _event_time(d, lat, lon, altitude, morning=True, timescale=timescale)


def sunset(
    d: date,
    lat: float,
    lon: float,
    elevation_m: float = 0.0,
    timescale: TimeScaleProvider = DEFAULT_TIMESCALE_PROVIDER,
) -> datetime | None:
    altitude = SUNRISE_SUNSET_ALTITUDE_DEG - _dip_of_horizon_deg(elevation_m)
    return _event_time(d, lat, lon, altitude, morning=False, timescale=timescale)


def fajr(
    d: date,
    lat: float,
    lon: float,
    angle_deg: float,
    timescale: TimeScaleProvider = DEFAULT_TIMESCALE_PROVIDER,
) -> datetime | None:
    """Fajr — sun at `angle_deg` below the horizon, pre-dawn. No elevation
    correction — see the note above `_dip_of_horizon_deg`."""
    return _event_time(d, lat, lon, -angle_deg, morning=True, timescale=timescale)


def isha(
    d: date,
    lat: float,
    lon: float,
    angle_deg: float,
    timescale: TimeScaleProvider = DEFAULT_TIMESCALE_PROVIDER,
) -> datetime | None:
    """Isha — sun at `angle_deg` below the horizon, post-dusk. No elevation
    correction — see the note above `_dip_of_horizon_deg`."""
    return _event_time(d, lat, lon, -angle_deg, morning=False, timescale=timescale)


def asr(
    d: date,
    lat: float,
    lon: float,
    shadow_ratio: float,
    timescale: TimeScaleProvider = DEFAULT_TIMESCALE_PROVIDER,
) -> datetime | None:
    """Asr — instant a vertical object's shadow equals shadow_ratio * height
    plus its noon shadow length (the standard shar'i definition).

    shadow_ratio = 1 -> Shafi'i/Maliki/Hanbali convention
    shadow_ratio = 2 -> Hanafi convention
    """
    jd = _jdn(d)
    params = _sun_params(_jd_tt(jd, d, timescale))
    declin = params.declination_deg
    noon_altitude = 90.0 - abs(lat - declin)
    if noon_altitude <= 0:
        return None  # sun never rises high enough (polar edge case)

    target_altitude = math.degrees(
        math.atan(1.0 / (shadow_ratio + math.tan(math.radians(90.0 - noon_altitude))))
    )
    return _event_time(d, lat, lon, target_altitude, morning=False, timescale=timescale)


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
    elevation_m: float = 0.0,
    fajr_angle_deg: float = 18.0,
    isha_angle_deg: float = 17.0,
    asr_shadow_ratio: float = 1.0,
    timescale: TimeScaleProvider = DEFAULT_TIMESCALE_PROVIDER,
) -> DayEvents:
    return DayEvents(
        date=d,
        fajr=fajr(d, lat, lon, fajr_angle_deg, timescale=timescale),
        sunrise=sunrise(d, lat, lon, elevation_m, timescale=timescale),
        dhuhr=transit(d, lat, lon, timescale=timescale),
        asr=asr(d, lat, lon, asr_shadow_ratio, timescale=timescale),
        maghrib=sunset(d, lat, lon, elevation_m, timescale=timescale),
        isha=isha(d, lat, lon, isha_angle_deg, timescale=timescale),
    )

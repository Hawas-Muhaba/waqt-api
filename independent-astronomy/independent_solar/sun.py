"""
independent_solar.sun — Sun's apparent equatorial position (RA, Dec).

This is the module that makes this reference genuinely independent of
`waqt/solar.py`'s route:

  waqt/solar.py never computes right ascension. It works entirely in
  ecliptic longitude, folds nutation and aberration into ONE combined
  shortcut term applied to true longitude, and gets declination straight
  from apparent longitude + a lightly-corrected obliquity. It never needs
  RA because it finds event times via the equation of time.

  This module computes nutation in longitude and aberration as TWO
  separate, explicit corrections (`nutation.py` for the first, the
  standard -20.4898"/R term for the second, `R` being the true Earth-Sun
  distance from Kepler's equation of center), then converts apparent
  ecliptic longitude + true obliquity into right ascension AND
  declination via the standard equatorial transform. `events.py` uses the
  right ascension together with Greenwich Apparent Sidereal Time to find
  event instants directly -- no equation of time is computed anywhere in
  this package.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .julian import julian_century
from .nutation import nutation_and_obliquity


def _deg360(x: float) -> float:
    return x % 360.0


@dataclass
class SunPosition:
    right_ascension_deg: float
    declination_deg: float
    apparent_longitude_deg: float
    true_obliquity_deg: float
    nutation_in_longitude_deg: float
    earth_sun_distance_au: float


def apparent_position(jd_tt: float) -> SunPosition:
    """`jd_tt` is the Julian Day already expressed in Terrestrial Time
    (i.e. JD(UT) + deltaT/86400 -- callers apply that shift, same
    division of responsibility `waqt/solar.py` uses for its own jd_tt)."""
    t = julian_century(jd_tt)

    mean_long = _deg360(280.46646 + t * (36000.76983 + 0.0003032 * t))
    mean_anom_deg = 357.52911 + t * (35999.05029 - 0.0001537 * t)
    eccentricity = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)

    m = math.radians(mean_anom_deg)
    equation_of_center = (
        (1.914602 - t * (0.004817 + 0.000014 * t)) * math.sin(m)
        + (0.019993 - 0.000101 * t) * math.sin(2 * m)
        + 0.000289 * math.sin(3 * m)
    )

    true_longitude = mean_long + equation_of_center
    true_anomaly_deg = mean_anom_deg + equation_of_center

    earth_sun_distance_au = (
        1.000001018
        * (1 - eccentricity**2)
        / (1 + eccentricity * math.cos(math.radians(true_anomaly_deg)))
    )

    nut = nutation_and_obliquity(t)

    # Annual aberration (Meeus eq. 25.10's constant, applied as its own
    # term -- NOT folded together with nutation into one shortcut).
    aberration_deg = -20.4898 / 3600.0 / earth_sun_distance_au

    apparent_longitude = true_longitude + nut.delta_psi_deg + aberration_deg

    lam_r = math.radians(apparent_longitude)
    eps_r = math.radians(nut.true_obliquity_deg)

    right_ascension = math.degrees(
        math.atan2(math.cos(eps_r) * math.sin(lam_r), math.cos(lam_r))
    ) % 360.0
    declination = math.degrees(math.asin(math.sin(eps_r) * math.sin(lam_r)))

    return SunPosition(
        right_ascension_deg=right_ascension,
        declination_deg=declination,
        apparent_longitude_deg=apparent_longitude % 360.0,
        true_obliquity_deg=nut.true_obliquity_deg,
        nutation_in_longitude_deg=nut.delta_psi_deg,
        earth_sun_distance_au=earth_sun_distance_au,
    )

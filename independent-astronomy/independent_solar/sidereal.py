"""
independent_solar.sidereal — Greenwich Apparent Sidereal Time (GAST).

This is the other half of what makes `events.py` independent of
`waqt/solar.py`: event instants here are found by solving for the local
hour angle of the sun (GAST + longitude - right ascension) rather than by
offsetting solar noon by the equation of time. Standard Meeus formula
(Ch. 12), independently coded; takes UT-scale JD (not TT) because
sidereal time is defined relative to the Earth's actual rotation.
"""

from __future__ import annotations

import math

from .julian import julian_century
from .nutation import nutation_and_obliquity


def greenwich_mean_sidereal_time_deg(jd_ut: float) -> float:
    t = julian_century(jd_ut)
    theta0 = (
        280.46061837
        + 360.98564736629 * (jd_ut - 2451545.0)
        + 0.000387933 * t * t
        - (t ** 3) / 38710000.0
    )
    return theta0 % 360.0


def greenwich_apparent_sidereal_time_deg(jd_ut: float) -> float:
    """GMST plus the equation of the equinoxes (nutation's effect on
    sidereal time): Delta_psi * cos(true obliquity)."""
    gmst = greenwich_mean_sidereal_time_deg(jd_ut)
    t = julian_century(jd_ut)
    nut = nutation_and_obliquity(t)
    eq_equinoxes = nut.delta_psi_deg * math.cos(math.radians(nut.true_obliquity_deg))
    return (gmst + eq_equinoxes) % 360.0

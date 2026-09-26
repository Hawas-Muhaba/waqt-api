"""
independent_solar.nutation — nutation in longitude/obliquity, mean obliquity.

Meeus's abbreviated four-term nutation series (Astronomical Algorithms,
Ch. 22 low-precision formulas), independently coded. `waqt/solar.py` never
computes nutation in obliquity at all, and only uses a single term of this
(Omega, folded into its apparent-longitude shortcut) -- this module keeps
nutation in longitude and obliquity as two explicit, separate quantities
used downstream by `sun.py`'s right-ascension/declination path.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


def _deg(x: float) -> float:
    return x % 360.0


@dataclass
class Nutation:
    delta_psi_deg: float   # nutation in longitude
    delta_eps_deg: float   # nutation in obliquity
    mean_obliquity_deg: float
    true_obliquity_deg: float


def nutation_and_obliquity(t: float) -> Nutation:
    """`t` is Julian centuries from J2000.0 (dynamical/TT time)."""
    omega = _deg(125.04452 - 1934.136261 * t)
    mean_long_sun = _deg(280.4665 + 36000.7698 * t)
    mean_long_moon = _deg(218.3165 + 481267.8813 * t)

    omega_r = math.radians(omega)
    two_l_r = math.radians(2 * mean_long_sun)
    two_lp_r = math.radians(2 * mean_long_moon)
    two_omega_r = math.radians(2 * omega)

    delta_psi_arcsec = (
        -17.20 * math.sin(omega_r)
        - 1.32 * math.sin(two_l_r)
        - 0.23 * math.sin(two_lp_r)
        + 0.21 * math.sin(two_omega_r)
    )
    delta_eps_arcsec = (
        9.20 * math.cos(omega_r)
        + 0.57 * math.cos(two_l_r)
        + 0.10 * math.cos(two_lp_r)
        - 0.09 * math.cos(two_omega_r)
    )

    # Mean obliquity of the ecliptic (IAU 1980 polynomial, arcseconds).
    mean_obliq_arcsec = (
        23.0 * 3600 + 26.0 * 60 + 21.448
        - 46.8150 * t
        - 0.00059 * t**2
        + 0.001813 * t**3
    )
    mean_obliq_deg = mean_obliq_arcsec / 3600.0
    true_obliq_deg = mean_obliq_deg + delta_eps_arcsec / 3600.0

    return Nutation(
        delta_psi_deg=delta_psi_arcsec / 3600.0,
        delta_eps_deg=delta_eps_arcsec / 3600.0,
        mean_obliquity_deg=mean_obliq_deg,
        true_obliquity_deg=true_obliq_deg,
    )

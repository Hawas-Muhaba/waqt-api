"""
independent-astronomy/level_a — a Level-A-grade reference for the Sun's
apparent geocentric position, used ONLY to measure how far the two
existing Level-B engines (`waqt/solar.py` and `independent-astronomy/
independent_solar/`) sit from a higher-precision reference. It is not
wired into Waqt's production computation anywhere, and this sprint's
Definition of Done explicitly forbids that
("without silently changing the production astronomical engine").

Why this is Level A and not another Level B:

`waqt/solar.py` uses the NOAA low-precision solar position formulas.
`independent_solar/sun.py` independently codes Meeus's *low-accuracy*
solar-coordinates method (Ch. 25's short series -- explicitly labelled
"more than sufficient for this project's purposes" there, ~0.01 degree,
i.e. tens of arcseconds). Both are legitimate, but both are the same
accuracy class, so comparing them to each other (Sprint 9's
`compare.py`) can show they agree without showing whether either is
actually *right*.

This module instead calls the full VSOP87 planetary theory (thousands
of periodic terms for Earth's heliocentric position, arcsecond-class
accuracy) via `pymeeus` -- a published, independently-tested, pure-
Python implementation of Meeus's *Astronomical Algorithms*, not code
written for this project. Sprint 9's own report was explicit that hand
-deriving a VSOP87-class series from memory would be irresponsible
("the current independent implementation does not prove sub-second
absolute accuracy against Level A" was named as a real, open gap, not
one to paper over with unverifiable coefficients); using a real,
externally-maintained library closes that gap honestly instead of
guessing at ephemeris coefficients. See docs/ASTRONOMY.md and this
sprint's report for the accuracy claims this justifies, and does not.
"""

from __future__ import annotations

from dataclasses import dataclass

from pymeeus.Coordinates import ecliptical2equatorial, true_obliquity
from pymeeus.Epoch import Epoch
from pymeeus.Sun import Sun

PYMEEUS_THEORY = "VSOP87 (full series, via pymeeus.Sun.apparent_geocentric_position)"


@dataclass(frozen=True)
class Position:
    right_ascension_deg: float
    declination_deg: float


def apparent_position(jd_tt: float) -> Position:
    """The Sun's apparent geocentric right ascension/declination (degrees,
    true equinox of date) at a Terrestrial-Time Julian Day, via full
    VSOP87 + nutation + aberration (pymeeus's `apparent_geocentric_position`,
    which already applies both -- see its docstring/source)."""
    epoch = Epoch(jd_tt)
    lon, lat, _r = Sun.apparent_geocentric_position(epoch)
    eps = true_obliquity(epoch)
    ra, dec = ecliptical2equatorial(lon, lat, eps)
    return Position(right_ascension_deg=float(ra), declination_deg=float(dec))


def apparent_sidereal_time_deg(jd_tt: float, jd_ut: float) -> float:
    """Greenwich Apparent Sidereal Time (degrees), via pymeeus, for the
    same instant `apparent_position` was evaluated at. Takes both time
    scales because GAST is a function of UT (Earth's actual rotation)
    while the nutation/obliquity terms feeding the equation of the
    equinoxes are most naturally evaluated at TT; pymeeus's own
    `apparent_sidereal_time` takes obliquity/nutation directly rather
    than an epoch, so this wraps it explicitly for clarity."""
    from pymeeus.Coordinates import nutation_longitude

    tt_epoch = Epoch(jd_tt)
    ut_epoch = Epoch(jd_ut)
    eps = true_obliquity(tt_epoch)
    dpsi = nutation_longitude(tt_epoch)
    fraction_of_day = ut_epoch.apparent_sidereal_time(eps, dpsi)  # pymeeus returns this in DAYS, not hours
    return (fraction_of_day * 360.0) % 360.0

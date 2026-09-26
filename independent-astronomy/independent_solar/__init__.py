"""
independent_solar — Parallel Milestone A: Independent Astronomical Reference.

A second, standalone solar-position / Maghrib-bracketing implementation,
built to the brief in the Sprint 9 roadmap:

    "Independently calculate the solar events required by Waqt from the
    documented astronomical specification and compare the results against
    the current reference implementation across the established
    geographic/test matrix."

This package imports NOTHING from `waqt` (no `waqt.solar`, no
`waqt.timescale`, no shared helper of any kind) and shares no code with
`waqt/solar.py`. It takes a genuinely different computational route to the
same six events:

  waqt/solar.py (existing reference)          independent_solar (this package)
  ----------------------------------          --------------------------------
  Low-order NOAA polynomial series for        Meeus-style apparent solar
  apparent solar longitude; equation of       position (mean longitude, mean
  time computed via the closed-form           anomaly, eccentricity, equation
  "y = tan^2(eps/2)" trigonometric             of center, full nutation-in-
  identity (NOAA Solar Calculator shortcut).   longitude series, aberration)
                                                with explicit right ascension
                                                and declination.

  Event times found by estimating solar        Event times found via Greenwich
  noon from the equation of time, then          Apparent Sidereal Time and the
  offsetting by the hour angle for the           sun's own right ascension: the
  target altitude, iterated twice.               local hour angle is computed
                                                  directly (H = GAST + lon - RA)
                                                  and solved for zero (transit)
                                                  or +-H0 (rise/set-type events)
                                                  by Newton-style iteration on
                                                  the ~360.9856 deg/day sidereal
                                                  rate. No equation of time is
                                                  ever computed here.

Both implementations are independent expressions of standard, published
solar-position astronomy (the kind of formulas found in Jean Meeus,
*Astronomical Algorithms*, and NOAA's public Solar Calculator
documentation) — using the same spherical-trigonometry altitude formula
that essentially every sunrise/sunset calculator in existence uses, since
that formula is basic spherical astronomy, not `waqt/solar.py`'s own
invention. What is independent here is the derivation of the sun's
apparent position and the method of turning that position into a UTC
instant, which is a completely different code path.

See `../REPORT.md` and `docs/INDEPENDENT-ASTRONOMY.md` (in the main repo)
for the comparison methodology, results and honest limitations.
"""

from .events import IndependentDayEvents, compute_day_events, transit, fajr, isha, asr, sunrise, sunset

__all__ = [
    "IndependentDayEvents",
    "compute_day_events",
    "transit",
    "fajr",
    "isha",
    "asr",
    "sunrise",
    "sunset",
]

"""Sprint 13 Goal D: a genuinely independent solar-event reference.

Sun and Earth positions: JPL DE421 (via the `de421` package / `jplephem`).
Apparent place, aberration, light-time, precession-nutation, apparent sidereal
time, UT1/TT: Skyfield (IAU 2006/2000A). Root finding: this package's own
grid-refinement. Nothing here imports waqt_core, independent_solar or level_a --
tests/test_skyfield_reference_independence.py enforces that structurally.
"""
from .events import compute_day_events, SkyfieldDayEvents, sun_geocentric_apparent  # noqa: F401

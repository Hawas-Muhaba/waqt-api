"""
waqt.timescale — Sprint 2, item 4.

Solar position formulas (declination, equation of time) are properly
functions of Terrestrial Time (TT), not UTC. The difference, DeltaT =
TT - UT1, is not a constant: it drifts (currently ~69s and slowly
increasing) and its FUTURE value is a prediction, not a fact, because
it depends on the (irregular) slowing of Earth's rotation.

Stage 1 ignored this entirely (treated UTC as if it were TT), which is
fine for near-present dates (the error is under a second) but was
flagged as formally missing. This module makes it an explicit,
swappable, versioned choice instead of a silent assumption, per the
sprint brief's `TimeScaleProvider` request.
"""

from __future__ import annotations

from datetime import date
from typing import Protocol


class TimeScaleProvider(Protocol):
    name: str

    def delta_t_seconds(self, d: date) -> float:
        """TT - UT1, in seconds, for the given (Gregorian) date."""
        ...


class EspenakMeeusDeltaT:
    """Polynomial approximations published by Espenak & Meeus (2006),
    NASA's standard reference for DeltaT estimation. Valid with
    documented accuracy across roughly 1900-2150; degrades gracefully
    (via the long-term parabola) outside that but should not be
    trusted far from it.

    This is the "named, versioned model" the Core Time Model's
    F-17/D-07 review item asked for.
    """

    name = "espenak-meeus-2006"

    def delta_t_seconds(self, d: date) -> float:
        y = d.year + (d.month - 0.5) / 12.0

        if 2005 <= y < 2050:
            t = y - 2000
            return 62.92 + 0.32217 * t + 0.005589 * t * t
        if 1986 <= y < 2005:
            t = y - 2000
            return (
                63.86
                + 0.3345 * t
                - 0.060374 * t**2
                + 0.0017275 * t**3
                + 0.000651814 * t**4
                + 0.00002373599 * t**5
            )
        if 2050 <= y <= 2150:
            return -20 + 32 * ((y - 1820) / 100) ** 2 - 0.5628 * (2150 - y)
        # Long-term parabola (Espenak & Meeus), for anything further out.
        u = (y - 1820) / 100.0
        return -20 + 32 * u * u


DEFAULT_TIMESCALE_PROVIDER = EspenakMeeusDeltaT()

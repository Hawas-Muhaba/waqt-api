"""
independent_solar.deltat — Terrestrial Time - UT1, independently coded.

Deliberately uses the SAME published NASA/Espenak-Meeus polynomial family
`waqt/timescale.py` uses (rather than a different empirical model), and
says so plainly: ΔT is a measured astronomical quantity, not a matter of
algorithmic taste, and this milestone exists to isolate and measure
disagreement in the *solar-position* algorithm specifically. Mixing in a
second, different ΔT model would blur that signal with a second, unrelated
source of disagreement. The code below is written from scratch against the
public formula (it imports nothing from `waqt`), and only the choice of
which published model to follow is shared.

Valid range: roughly 1900-2150 (Espenak & Meeus 2006), matching the
current-era-only scope of this whole milestone.
"""

from __future__ import annotations

from datetime import date


def delta_t_seconds(d: date) -> float:
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
    if 1961 <= y < 1986:
        t = y - 1975
        return 45.45 + 1.067 * t - t**2 / 260.0 - t**3 / 718.0
    if 1900 <= y < 1961:
        t = y - 1900
        return (
            -2.79
            + 1.494119 * t
            - 0.0598939 * t**2
            + 0.0061966 * t**3
            - 0.000197 * t**4
        )
    if 2050 <= y <= 2150:
        # Long-term extrapolation, same as waqt/timescale.py's own
        # documented fallback for this band.
        return -20.0 + 32.0 * ((y - 1820) / 100.0) ** 2 - 0.5628 * (2150 - y)
    # Outside the documented range: this milestone doesn't claim validity
    # there (matches the "current era only" scope of the whole project).
    t = (y - 1820) / 100.0
    return -20.0 + 32.0 * t * t

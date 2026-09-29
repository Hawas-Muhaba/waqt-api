"""
waqt-core — the independently distributable computation layer of the
Waqt Islamic Civil Time and Calendar Standard.

    Waqt Specification
           |
    +-------------+-------------+
    |                           |
waqt-core (this package) <------+
    |                           |
    +-------------+-------------+
                  used by
           +-------+-------+
           |               |
      waqt.api        waqt_local
   (HTTP server)   (embeddable, no-server)

Sprint 11 extracted this package out of what had, since Stage 1, been a
single `waqt/` package mixing computation (astronomy, Hijri calendars,
scheduling, institutional calendars) with the HTTP/FastAPI application
layer. `waqt-core` is that computation layer, moved out unchanged (see
`SPRINT-11-REPORT.md` §1 for the byte-for-byte verification) so it can
be installed and versioned on its own, with zero dependency on FastAPI,
`waqt.api`, or `waqt_local`.

Modules:
  - `core`                — the Waqt time model: Location, AstronomyProfile,
                             compute_waqt, day-boundary/Maghrib logic.
  - `solar`                — NOAA low-precision solar event engine.
  - `hijri`                — Hijri date arithmetic and calendar providers'
                             shared protocol/base types.
  - `calendar_providers`   — pluggable HijriProvider implementations
                             (Umm al-Qura, Declared, LocalObservation, ...).
  - `semantics`            — Waqt time/calendar vocabulary (instants, days,
                             positions, comparisons).
  - `calendar_interop`     — Hijri <-> Gregorian <-> Waqt-day conversions.
  - `scheduling`           — the scheduling engine (points, intervals,
                             the 10 resolve/classify operations).
  - `institutional`        — fiscal year / academic year / week calendars
                             built on top of scheduling + calendar rules.
  - `timescale`, `timezone_provider` — DeltaT and timezone lookup providers.
  - `versioning`           — Sprint 12: engine identity + revision, the behavioural
                             fingerprint that keeps the revision honest, and the
                             machine-readable form of docs/VERSIONING.md.

`waqt.core`, `waqt.hijri`, `waqt.semantics`, `waqt.solar`,
`waqt.timescale`, `waqt.timezone_provider`, `waqt.calendar_interop`,
`waqt.calendar_providers`, `waqt.institutional`, and `waqt.scheduling`
remain importable (see `waqt/__init__.py`) as the *exact same module
objects* as their counterparts here — not copies — so existing code
that imports from `waqt.*` (including deep imports like
`waqt.scheduling.model`) keeps working without modification.
"""

from __future__ import annotations

from ._version import __version__
from .versioning import (
    ACCURACY_LEVEL,
    ENGINE_NAME,
    ENGINE_REVISION,
    VECTOR_SET_VERSION,
    computation_identity,
)

__all__ = [
    "__version__",
    "ENGINE_NAME", "ENGINE_REVISION", "ACCURACY_LEVEL", "VECTOR_SET_VERSION",
    "computation_identity",
]

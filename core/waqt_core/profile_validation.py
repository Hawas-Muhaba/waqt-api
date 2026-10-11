"""ERR-004 -- validation of the astronomy-profile parameters.

One definition, used by every public entry point that builds an ``AstronomyProfile``
(waqt-core, the HTTP API, the local facade, the CLI and the conformance adapters).

Normative constraints (conformance contract ERR-004, DR-0011):

  fajr_angle_deg    finite real number, 0 < x <= 90
  isha_angle_deg    finite real number, 0 < x <= 90
  asr_shadow_ratio  finite real number, x > 0

NaN, +/-infinity, booleans, strings and every other non-number are rejected, as is any value
outside those ranges. Nothing is clamped or coerced. The error code is ``VALIDATION_ERROR``
(HTTP 422 on the API).
"""
from __future__ import annotations

import math
from numbers import Real
from typing import Any

#: parameter -> (inclusive upper bound or None); the lower bound is always exclusive 0.
PROFILE_CONSTRAINTS = {
    "fajr_angle_deg": 90.0,
    "isha_angle_deg": 90.0,
    "asr_shadow_ratio": None,
}


class InvalidProfileError(ValueError):
    """A profile parameter is non-numeric, non-finite or outside its normative range (ERR-004)."""

    code = "VALIDATION_ERROR"

    def __init__(self, parameter: str, received: Any, expected: str):
        self.parameter, self.received, self.expected = parameter, received, expected
        super().__init__(f"{parameter} must be {expected}; got {received!r}.")

    @property
    def received_json(self) -> Any:
        """``received`` in a form every JSON encoder accepts (NaN/Infinity and other non-JSON values become text)."""
        r = self.received
        if isinstance(r, (int, float)) and not isinstance(r, bool) and math.isfinite(r):
            return r
        return r if isinstance(r, (str, bool)) or r is None else repr(r)


def _expected(upper: float | None) -> str:
    return "a finite number with 0 < value <= 90" if upper is not None else "a finite number with value > 0"


def validate_profile_value(parameter: str, value: Any) -> float:
    """Return ``value`` as a float if it satisfies the constraint for ``parameter``; raise otherwise."""
    upper = PROFILE_CONSTRAINTS[parameter]
    expected = _expected(upper)
    if isinstance(value, bool) or not isinstance(value, Real):
        raise InvalidProfileError(parameter, value, expected)
    v = float(value)
    if not math.isfinite(v) or v <= 0 or (upper is not None and v > upper):
        raise InvalidProfileError(parameter, value, expected)
    return v


def validate_profile(fajr_angle_deg: Any, isha_angle_deg: Any, asr_shadow_ratio: Any) -> None:
    """Validate all three parameters (fajr, isha, asr order); raises InvalidProfileError on the first bad one."""
    validate_profile_value("fajr_angle_deg", fajr_angle_deg)
    validate_profile_value("isha_angle_deg", isha_angle_deg)
    validate_profile_value("asr_shadow_ratio", asr_shadow_ratio)

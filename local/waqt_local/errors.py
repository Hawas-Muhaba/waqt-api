"""
waqt_local.errors — the local library's error vocabulary.

Deliberately mirrors the *names* of `waqt.api.common.ErrorCode` (so a
caller who knows the HTTP API's error codes recognizes these
immediately) without importing anything from `waqt.api` — the local
library does not depend on the HTTP layer at all, in either direction.
Each code is its own exception class rather than one exception with a
`.code` string, which is the more idiomatic shape for a Python library
that never serializes to a JSON error envelope.
"""

from __future__ import annotations

from typing import Any, Optional


class WaqtLocalError(Exception):
    """Base class for every error this library raises."""

    code = "INTERNAL_ERROR"

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class InvalidInstantError(WaqtLocalError):
    code = "INVALID_INSTANT"


class InvalidDateError(WaqtLocalError):
    code = "INVALID_DATE"


class UnknownCalendarProviderError(WaqtLocalError):
    code = "UNKNOWN_CALENDAR_PROVIDER"


class InvalidHijriDateError(WaqtLocalError):
    """Sprint 16 (DIS-002): the Hijri (year, month, day) does not exist."""
    code = "INVALID_HIJRI_DATE"


class UnknownTimezoneError(WaqtLocalError):
    """Sprint 16 (DIS-003): timezone_override is not an IANA zone name."""
    code = "UNKNOWN_TIMEZONE"


class UnsupportedOperationError(WaqtLocalError):
    code = "UNSUPPORTED_OPERATION"


class InvalidRuleError(WaqtLocalError):
    code = "INVALID_RULE"


class InvalidCalendarRuleError(WaqtLocalError):
    code = "INVALID_CALENDAR_RULE"


class CalendarDateUnresolvableError(WaqtLocalError):
    code = "CALENDAR_DATE_UNRESOLVABLE"


class InvalidSpanError(WaqtLocalError):
    code = "INVALID_SPAN"


class ValidationError(WaqtLocalError):
    code = "VALIDATION_ERROR"


def validation_error(message: str, **details: Any) -> ValidationError:
    return ValidationError(message, details)


class OutOfRangeError(WaqtLocalError):
    """Sprint 16 (CAL-011): the date is outside the calendar provider's supported range."""
    code = "OUT_OF_RANGE"

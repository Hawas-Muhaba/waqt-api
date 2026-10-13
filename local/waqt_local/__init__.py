"""
waqt-local — the embeddable, no-server Waqt computation library.

    Waqt Specification
           |
    +-------------+-------------+
    |                           |
 Local computation           HTTP API
    |                           |
 waqt_local (this package)   Waqt Server (waqt.api)
                                 |
                       +---------+---------+
                       |                   |
                  Python SDK          JS/TS SDK
                (waqt_client, remote)  (waqt-client, remote)

This package computes Waqt facts in-process: no HTTP, no `httpx`, no
running server. It is deliberately NOT `waqt_client` (the remote API
client from Sprint 9) — that package's every returned value comes from
a live HTTP response; every value this package returns comes from a
direct, in-process call into `waqt.core` / `waqt.solar` /
`waqt.semantics` / `waqt.hijri` / `waqt.scheduling` /
`waqt.institutional` / `waqt.calendar_interop` — the same computation
the HTTP server itself is built on, reused rather than reimplemented.

    >>> import waqt_local
    >>> result = waqt_local.waqt(lat=9.0192, lon=38.7525)
    >>> result["status"]
    'OK'

Every function returns a plain dict with the same shape the matching
`/v1/*` HTTP endpoint's `data` field has (no `meta`/`error` envelope —
there is no transport to report an envelope about; a caller-side
mistake raises a `waqt_local.errors.WaqtLocalError` instead of a
malformed `dict`). See docs/LOCAL.md.
"""

from ._version import __version__
from .providers import DEFAULT_CALENDAR_PROVIDER
from . import facade
from .errors import (
    CalendarDateUnresolvableError,
    InvalidCalendarRuleError,
    InvalidDateError,
    InvalidHijriDateError,
    InvalidInstantError,
    InvalidRuleError,
    InvalidSpanError,
    OutOfRangeError,
    UnknownCalendarProviderError,
    UnknownTimezoneError,
    UnsupportedOperationError,
    ValidationError,
    WaqtLocalError,
)
from .facade import (
    boundary_crossing,
    convert,
    day,
    events,
    hijri,
    institutional_academic_year,
    institutional_academic_year_resolve,
    institutional_default_profile,
    institutional_fiscal_year,
    institutional_fiscal_year_resolve,
    institutional_week,
    list_calendar_providers,
    location_info,
    represent_instant,
    schedule_resolve,
    schedule_snapshot,
    schedule_span,
    version,
    waqt,
    waqt_day_for_gregorian_date,
)
from waqt_core.display.at_bt import AtBtTime, format_at_bt, parse_at_bt

__all__ = [
    "__version__",
    "DEFAULT_CALENDAR_PROVIDER",
    "facade",
    "waqt", "version", "day", "events", "location_info", "hijri", "list_calendar_providers",
    "convert", "represent_instant", "waqt_day_for_gregorian_date", "boundary_crossing",
    "schedule_snapshot", "schedule_span", "schedule_resolve",
    "institutional_week", "institutional_fiscal_year", "institutional_fiscal_year_resolve",
    "institutional_academic_year", "institutional_academic_year_resolve", "institutional_default_profile",
    "AtBtTime", "format_at_bt", "parse_at_bt",
    "WaqtLocalError", "ValidationError", "InvalidInstantError", "InvalidDateError",
    "UnknownCalendarProviderError", "UnknownTimezoneError", "InvalidHijriDateError", "UnsupportedOperationError", "InvalidRuleError",
    "InvalidCalendarRuleError", "CalendarDateUnresolvableError", "InvalidSpanError", "OutOfRangeError",
]

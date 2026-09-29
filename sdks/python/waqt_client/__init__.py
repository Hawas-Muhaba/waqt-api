"""
waqt-client — the official thin Python SDK for the Waqt API.

    Waqt Specification
           |
       HTTP / JSON
           |
     waqt_client (this package)   <-- ergonomic types + functions,
           |                          the wire contract preserved
     Your application

This package is a REMOTE API CLIENT, not a local reimplementation of
Waqt's astronomical/calendar rules. Every number it returns came from a
live (or replayed, in tests) `/v1/*` HTTP response — nothing here
computes a Maghrib instant, a Hijri date, or a scheduling result on its
own. If you need Waqt computation without a server round-trip, see the
sibling `waqt-local` package (Sprint 10) — a distinct, in-process
library, not this one wearing a different hat (docs/SDK.md's "Local vs
server computation" section, docs/LOCAL.md).

Sprint 10 also added `waqt_client.requests`: typed, `.to_json()`-able
request builders for the three endpoints that used to take only a raw
`dict` (`POST /v1/schedule/resolve` and the two institutional
`.../resolve` endpoints). Passing a plain `dict` still works exactly as
it did in Sprint 9 — the typed builders are opt-in convenience.

    >>> from waqt_client import WaqtClient
    >>> with WaqtClient(base_url="http://localhost:8000") as client:
    ...     resp = client.get_waqt(lat=9.0192, lon=38.7525)
    ...     print(resp.hijri.display, resp.waqt.display)

    >>> from waqt_client import AsyncWaqtClient
    >>> async with AsyncWaqtClient(base_url="http://localhost:8000") as client:
    ...     resp = await client.get_waqt(lat=9.0192, lon=38.7525)
"""

from . import requests
from ._version import __version__
from .async_client import AsyncWaqtClient
from .client import WaqtClient
from .config import WaqtClientConfig
from .errors import WaqtApiError, WaqtError, WaqtTransportError, WaqtVersionMismatch
from .types import (
    AstronomicalEvent,
    AstronomyProfile,
    BoundaryCrossingResult,
    CalendarProviderInfo,
    ComputationInfo,
    VersionInfo,
    ConversionResult,
    DayBoundary,
    GregorianRepresentation,
    HijriDate,
    InstantRepresentation,
    InstitutionalCalendarResult,
    Location,
    LocationInfo,
    Reading,
    SchedulingResult,
    TimezoneInfo,
    WaqtPosition,
    WaqtResponse,
)

__all__ = [
    "__version__",
    "requests",
    "WaqtClient",
    "AsyncWaqtClient",
    "WaqtClientConfig",
    "WaqtError",
    "WaqtApiError",
    "WaqtTransportError",
    "WaqtVersionMismatch",
    "WaqtResponse",
    "AstronomicalEvent",
    "AstronomyProfile",
    "BoundaryCrossingResult",
    "CalendarProviderInfo",
    "ComputationInfo",
    "VersionInfo",
    "ConversionResult",
    "DayBoundary",
    "GregorianRepresentation",
    "HijriDate",
    "InstantRepresentation",
    "InstitutionalCalendarResult",
    "Location",
    "LocationInfo",
    "Reading",
    "SchedulingResult",
    "TimezoneInfo",
    "WaqtPosition",
]

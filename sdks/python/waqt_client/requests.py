"""
waqt_client.requests — typed request bodies for the three POST
endpoints Sprint 9 left as raw `dict` (`POST /v1/schedule/resolve`,
`POST /v1/institutional/fiscal-year/resolve`,
`POST /v1/institutional/academic-year/resolve`).

Every class here mirrors, field-for-field, the wire JSON format
`waqt.scheduling.model` and `waqt.institutional.rules` already define
server-side (docs/SCHEDULING.md §8, docs/INSTITUTIONAL.md) — but is a
clean, independent re-expression of that format, not an import of the
server's own dataclasses: this package's only dependency is `httpx`
(see `pyproject.toml`), and a client SDK constructing the shape of a
request it sends is a normal, expected duplication (every SDK
construct request bodies independently of server-side model code; a
Python SDK importing internal server dataclasses would also defeat the
point of it being usable against ANY server that speaks the same wire
protocol, not just one that happens to be this exact checkout).

Passing a raw `dict` to `WaqtClient.schedule_resolve` etc. keeps
working exactly as it did in Sprint 9 — these classes are opt-in
convenience, not a breaking change. Every class exposes `.to_json()`;
`WaqtClient`/`AsyncWaqtClient` accept either a `dict` or any object
with a `.to_json()` method (see client.py `_body_json`).

    >>> from waqt_client.requests import ScheduleResolveRequest, ResolveInterval, Interval, Event
    >>> req = ScheduleResolveRequest(
    ...     lat=9.0192, lon=38.7525,
    ...     anchor="2026-09-19T15:42:00Z",
    ...     operation=ResolveInterval(Interval(Event("maghrib", 0), Event("isha", 0))),
    ... )
    >>> client.schedule_resolve(req)                       # doctest: +SKIP
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional, Union

EVENT_NAMES = ("fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha")
REF_NAMES = EVENT_NAMES + ("day_start", "day_end")


def _fmt_instant(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    return v


def _fmt_date(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, date):
        return v.isoformat()
    return v


class RequestValidationError(ValueError):
    """A typed request was built with an invalid value. Raised client-side,
    before any network call — never for something the server itself would
    reject only for being semantically impossible (e.g. undefined
    astronomy), which is a normal response, not a construction error."""


# ---------------------------------------------------------------------------
# Scheduling points (waqt.scheduling.model's wire format, §8 of docs/SCHEDULING.md)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Instant:
    value: Any  # str (ISO 8601) or datetime

    def to_json(self) -> dict:
        return {"type": "instant", "value": _fmt_instant(self.value)}


@dataclass(frozen=True)
class Anchor:
    def to_json(self) -> dict:
        return {"type": "anchor"}


@dataclass(frozen=True)
class Event:
    name: str
    day: int = 0

    def __post_init__(self):
        if self.name not in REF_NAMES:
            raise RequestValidationError(f"Unknown event {self.name!r}. Known: {list(REF_NAMES)}")

    def to_json(self) -> dict:
        return {"type": "event", "name": self.name, "day": self.day}


@dataclass(frozen=True)
class NextEvent:
    name: str
    inclusive: bool = True
    on_undefined: str = "strict"

    def to_json(self) -> dict:
        return {"type": "next_event", "name": self.name, "inclusive": self.inclusive, "on_undefined": self.on_undefined}


@dataclass(frozen=True)
class PrevEvent:
    name: str
    inclusive: bool = True
    on_undefined: str = "strict"

    def to_json(self) -> dict:
        return {"type": "prev_event", "name": self.name, "inclusive": self.inclusive, "on_undefined": self.on_undefined}


@dataclass(frozen=True)
class Position:
    seconds: float
    day: int = 0

    def to_json(self) -> dict:
        return {"type": "position", "seconds": self.seconds, "day": self.day}


@dataclass(frozen=True)
class Offset:
    base: "Point"
    seconds: float

    def to_json(self) -> dict:
        return {"type": "offset", "base": self.base.to_json(), "seconds": self.seconds}


@dataclass(frozen=True)
class Fraction:
    start: "Point"
    end: "Point"
    fraction: float

    def to_json(self) -> dict:
        return {"type": "fraction", "start": self.start.to_json(), "end": self.end.to_json(), "fraction": self.fraction}


Point = Union[Instant, Anchor, Event, NextEvent, PrevEvent, Position, Offset, Fraction]


@dataclass(frozen=True)
class Interval:
    start: Optional[Point] = None
    end: Optional[Point] = None
    start_inclusive: bool = True
    end_inclusive: bool = False

    def __post_init__(self):
        if self.start is None and self.end is None:
            raise RequestValidationError("An interval needs at least one bound")

    def to_json(self) -> dict:
        return {
            "type": "interval",
            "start": self.start.to_json() if self.start is not None else None,
            "end": self.end.to_json() if self.end is not None else None,
            "start_inclusive": self.start_inclusive,
            "end_inclusive": self.end_inclusive,
        }


# ---- Generic interval constructors, mirroring waqt.scheduling.model's ----

def before(p: Point, inclusive: bool = False) -> Interval:
    return Interval(None, p, end_inclusive=inclusive)


def after(p: Point, inclusive: bool = True) -> Interval:
    return Interval(p, None, start_inclusive=inclusive)


def between(a: Point, b: Point) -> Interval:
    return Interval(a, b)


def within(p: Point, seconds: float) -> Interval:
    if seconds <= 0:
        raise RequestValidationError("within() needs a positive duration")
    return Interval(p, Offset(p, seconds))


def within_day(day: int = 0) -> Interval:
    return Interval(Event("day_start", day), Event("day_end", day))


# ---------------------------------------------------------------------------
# Scheduling operations (waqt.scheduling.ops's wire format)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResolvePoint:
    point: Point

    def to_json(self) -> dict:
        return {"op": "resolve_point", "point": self.point.to_json()}


@dataclass(frozen=True)
class ResolveInterval:
    interval: Interval

    def to_json(self) -> dict:
        return {"op": "resolve_interval", "interval": self.interval.to_json()}


@dataclass(frozen=True)
class Evaluate:
    interval: Interval
    instant: Any

    def to_json(self) -> dict:
        return {"op": "evaluate", "interval": self.interval.to_json(), "instant": _fmt_instant(self.instant)}


@dataclass(frozen=True)
class CheckDeadline:
    point: Point
    now: Any = None

    def to_json(self) -> dict:
        body = {"op": "check_deadline", "point": self.point.to_json()}
        if self.now is not None:
            body["now"] = _fmt_instant(self.now)
        return body


@dataclass(frozen=True)
class Until:
    name: str
    on_undefined: str = "strict"
    instant: Any = None

    def to_json(self) -> dict:
        body = {"op": "until", "name": self.name, "on_undefined": self.on_undefined}
        if self.instant is not None:
            body["instant"] = _fmt_instant(self.instant)
        return body


@dataclass(frozen=True)
class Since:
    name: str
    on_undefined: str = "strict"
    instant: Any = None

    def to_json(self) -> dict:
        body = {"op": "since", "name": self.name, "on_undefined": self.on_undefined}
        if self.instant is not None:
            body["instant"] = _fmt_instant(self.instant)
        return body


@dataclass(frozen=True)
class NextEventOp:
    instant: Any = None

    def to_json(self) -> dict:
        body = {"op": "next_event"}
        if self.instant is not None:
            body["instant"] = _fmt_instant(self.instant)
        return body


@dataclass(frozen=True)
class EventPosition:
    name: str
    day: Optional[int] = None

    def to_json(self) -> dict:
        return {"op": "event_position", "name": self.name, "day": self.day}


@dataclass(frozen=True)
class DayBounds:
    instant: Any = None

    def to_json(self) -> dict:
        body = {"op": "day_bounds"}
        if self.instant is not None:
            body["instant"] = _fmt_instant(self.instant)
        return body


@dataclass(frozen=True)
class ClassifySpan:
    start: Any
    end: Any
    end_inclusive: bool = False

    def to_json(self) -> dict:
        return {
            "op": "classify_span", "start": _fmt_instant(self.start), "end": _fmt_instant(self.end),
            "end_inclusive": self.end_inclusive,
        }


Operation = Union[
    ResolvePoint, ResolveInterval, Evaluate, CheckDeadline, Until, Since, NextEventOp, EventPosition,
    DayBounds, ClassifySpan,
]


@dataclass(frozen=True)
class Profile:
    fajr_angle_deg: float = 18.0
    isha_angle_deg: float = 17.0
    asr_shadow_ratio: float = 1.0

    def to_json(self) -> dict:
        return {"fajr_angle_deg": self.fajr_angle_deg, "isha_angle_deg": self.isha_angle_deg, "asr_shadow_ratio": self.asr_shadow_ratio}


@dataclass(frozen=True)
class ScheduleResolveRequest:
    """`POST /v1/schedule/resolve` body. See docs/SCHEDULING.md §8."""

    lat: float
    lon: float
    operation: Operation
    elevation_m: float = 0.0
    anchor: Any = None
    profile: Optional[Profile] = None
    calendar_provider: Optional[str] = None
    timezone_override: Optional[str] = None
    precision: Optional[str] = None

    def to_json(self) -> dict:
        body: dict = {
            "location": {"lat": self.lat, "lon": self.lon, "elevation_m": self.elevation_m},
            "operation": self.operation.to_json(),
        }
        if self.anchor is not None:
            body["anchor"] = _fmt_instant(self.anchor)
        if self.profile is not None:
            body["profile"] = self.profile.to_json()
        if self.calendar_provider is not None:
            body["calendar_provider"] = self.calendar_provider
        if self.timezone_override is not None:
            body["timezone_override"] = self.timezone_override
        if self.precision is not None:
            body["precision"] = self.precision
        return body


# ---------------------------------------------------------------------------
# Institutional calendar rules (waqt.institutional.rules's wire format)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MonthDay:
    month: int
    day: int = 1

    def to_json(self) -> dict:
        return {"type": "month_day", "month": self.month, "day": self.day}


@dataclass(frozen=True)
class MonthEnd:
    month: int

    def to_json(self) -> dict:
        return {"type": "month_end", "month": self.month}


@dataclass(frozen=True)
class NthWeekdayOfMonth:
    weekday: str
    n: int
    month: int

    def to_json(self) -> dict:
        return {"type": "nth_weekday_of_month", "weekday": self.weekday, "n": self.n, "month": self.month}


CalendarRule = Union[MonthDay, MonthEnd, NthWeekdayOfMonth]


@dataclass(frozen=True)
class Location:
    lat: float
    lon: float
    elevation_m: float = 0.0

    def to_json(self) -> dict:
        return {"lat": self.lat, "lon": self.lon, "elevation_m": self.elevation_m}


@dataclass(frozen=True)
class FiscalYearResolveRequest:
    """`POST /v1/institutional/fiscal-year/resolve` body. See docs/INSTITUTIONAL.md."""

    hijri_year: int
    start_rule: CalendarRule
    end_rule: CalendarRule
    label: Optional[str] = None
    calendar_provider: Optional[str] = None
    location: Optional[Location] = None

    def to_json(self) -> dict:
        body: dict = {
            "hijri_year": self.hijri_year,
            "start_rule": self.start_rule.to_json(),
            "end_rule": self.end_rule.to_json(),
        }
        if self.label is not None:
            body["label"] = self.label
        if self.calendar_provider is not None:
            body["calendar_provider"] = self.calendar_provider
        if self.location is not None:
            body["location"] = self.location.to_json()
        return body


@dataclass(frozen=True)
class TermRule:
    label: str
    start_rule: CalendarRule
    end_rule: CalendarRule
    year_offset: int = 0

    def to_json(self) -> dict:
        return {
            "label": self.label, "start_rule": self.start_rule.to_json(), "end_rule": self.end_rule.to_json(),
            "year_offset": self.year_offset,
        }


@dataclass(frozen=True)
class HolidayRule:
    label: str
    rule: CalendarRule
    year_offset: int = 0

    def to_json(self) -> dict:
        return {"label": self.label, "rule": self.rule.to_json(), "year_offset": self.year_offset}


@dataclass(frozen=True)
class AcademicYearResolveRequest:
    """`POST /v1/institutional/academic-year/resolve` body. See docs/INSTITUTIONAL.md."""

    hijri_year: int
    opening_rule: CalendarRule
    closing_rule: CalendarRule
    term_rules: tuple = ()
    holidays: tuple = ()
    label: Optional[str] = None
    calendar_provider: Optional[str] = None
    location: Optional[Location] = None

    def to_json(self) -> dict:
        body: dict = {
            "hijri_year": self.hijri_year,
            "opening_rule": self.opening_rule.to_json(),
            "closing_rule": self.closing_rule.to_json(),
            "term_rules": [t.to_json() for t in self.term_rules],
            "holidays": [h.to_json() for h in self.holidays],
        }
        if self.label is not None:
            body["label"] = self.label
        if self.calendar_provider is not None:
            body["calendar_provider"] = self.calendar_provider
        if self.location is not None:
            body["location"] = self.location.to_json()
        return body

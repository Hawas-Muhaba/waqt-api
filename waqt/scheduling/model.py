"""
waqt.scheduling.model — the declarative vocabulary of Waqt scheduling.

Nothing in this file computes anything. It only DESCRIBES temporal
rules — points in time and intervals between them — as plain immutable
values that can be built in Python, serialized to JSON, shipped to
another language, and resolved there. Resolution lives in engine.py.

======================================================================
THE FOUR KINDS OF POINT (the brief's central distinction)
======================================================================
A rule's endpoints are not all the same kind of thing, and the result
of resolving one always says which kind it was (`basis`):

  absolute_instant   -- Instant, Anchor. A UTC instant supplied by the
                        caller. No astronomy, no Waqt day involved.
  astronomical_event -- Event, NextEvent, PrevEvent. An instant the
                        solar engine produced (Fajr, Maghrib, ...).
  waqt_position      -- Position. "N seconds after this Waqt day's
                        opening Maghrib". Meaningless without a day.
  rule_derived       -- Offset, Fraction. Computed FROM other points by
                        an arithmetic rule. Carries `depends_on`, the
                        set of bases it was built from.

WHAT THIS LAYER DOES NOT CLAIM
------------------------------
Every primitive here is temporal arithmetic over astronomical facts.
None of them is a religious ruling. "Fajr" means: the instant at which
the configured astronomy profile's depression angle is reached — not a
determination that fasting, prayer, or any obligation begins then.
Whether a given application should use `Event("fajr")` or Fajr minus
ten minutes of caution, whether a "night" runs Maghrib-to-Fajr or
Maghrib-to-sunrise, and what a "third of the night" is, are questions a
scholar or an institution answers; this layer only lets them WRITE the
answer down precisely and evaluate it reproducibly. That is why there
are no presets like `suhoor()` or `iftar()` here.

EVENT SLOT NAMING (matches waqt.semantics exactly — nothing new)
----------------------------------------------------------------
`Event(name, day=k)` refers to the event as LISTED on the k-th Waqt
day relative to the anchor's day (k=0: the day containing the anchor;
-1 previous; +1 next). Listing follows `WaqtDay.event()`:

  fajr, sunrise, dhuhr, asr            occur INSIDE their listed day
  maghrib                              is the listed day's CLOSING
                                       Maghrib — by the half-open rule
                                       the first instant (00:00:00) of
                                       the NEXT Waqt day
  isha                                 occurs in the NEXT Waqt day
                                       (it follows that closing Maghrib)
  day_start, day_end                   the listed day's opening and
                                       closing Maghrib. `day_end` and
                                       `maghrib` are the same instant.

The Maghrib/Isha facts are not quirks of this layer: Sprint 5's own
vectors list Maghrib at 23:59:23 and Isha at 25:04:53 on a day that is
23:59:23 long. Both are properties of "Waqt day = Maghrib to Maghrib". It is a property of
"Waqt day = Maghrib to Maghrib", and the scheduler is where it becomes
visible, because a window like [Maghrib, Isha) straddles the boundary.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Union

EVENT_NAMES = ("fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha")
BOUNDARY_NAMES = ("day_start", "day_end")
REF_NAMES = EVENT_NAMES + BOUNDARY_NAMES

# Events whose instant lies in the Waqt day AFTER the one that lists them
# (containment under the half-open rule [open, close)). Maghrib is here
# because the closing Maghrib is the first instant of the next day;
# Isha because it follows it. Verified across a year of dates at twelve
# places, including Kiritimati, in tests/test_scheduling.py.
DAY_SHIFT = {"maghrib": 1, "isha": 1}


class Status:
    """Result statuses. Deliberately distinct — see docs/SCHEDULING.md §6."""

    OK = "OK"
    # A single referenced point does not exist (event never occurs that
    # day, or the whole Waqt day is undefined — polar day/night).
    EVENT_UNDEFINED = "EVENT_UNDEFINED"
    # An interval could not be built because >=1 of its endpoints is
    # EVENT_UNDEFINED. The endpoint results are attached as `causes`.
    WINDOW_UNDEFINED = "WINDOW_UNDEFINED"
    # Both endpoints exist, but they do not bound a non-empty window
    # (end before start, or empty under the inclusivity flags).
    NO_VALID_WINDOW = "NO_VALID_WINDOW"


class UndefinedPolicy:
    """What a Next/Prev occurrence search does when it meets a day on
    which the event does not occur."""

    STRICT = "strict"  # default: report EVENT_UNDEFINED. Never invent a time.
    SKIP = "skip"      # explicit opt-in: continue to the next day the event does occur, and REPORT what was skipped.


class RuleError(ValueError):
    """A rule spec (dict/JSON) is malformed. Never raised for valid-but-
    undefined astronomy — that is a Status, not an error."""


# ---------------------------------------------------------------------------
# Microsecond arithmetic, shared bit-for-bit with the JS consumer:
# every derived instant is computed in integer microseconds using the
# same floor(x + 0.5) rounding so independent implementations agree
# exactly rather than "to within a tolerance".
# ---------------------------------------------------------------------------

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def to_micros(dt: datetime) -> int:
    d = dt.astimezone(timezone.utc) - _EPOCH
    return (d.days * 86400 + d.seconds) * 1_000_000 + d.microseconds


def from_micros(us: int) -> datetime:
    return _EPOCH + timedelta(microseconds=us)


def round_half_up(x: float) -> int:
    return int(math.floor(x + 0.5))


def parse_instant(value: Any) -> datetime:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as e:
            raise RuleError(f"Not an ISO 8601 instant: {value!r}") from e
    else:
        raise RuleError(f"Instant must be an ISO 8601 string, got {type(value).__name__}")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Points
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Instant:
    """An absolute UTC instant."""

    value: datetime

    def to_dict(self) -> dict:
        return {"type": "instant", "value": self.value.astimezone(timezone.utc).isoformat()}


@dataclass(frozen=True)
class Anchor:
    """The instant the rule is being resolved against (e.g. 'now')."""

    def to_dict(self) -> dict:
        return {"type": "anchor"}


@dataclass(frozen=True)
class Event:
    """`name` as listed on the Waqt day `day` places away from the
    anchor's day. See the module docstring's slot-naming section."""

    name: str
    day: int = 0

    def __post_init__(self):
        if self.name not in REF_NAMES:
            raise RuleError(f"Unknown event {self.name!r}. Known: {list(REF_NAMES)}")
        if not isinstance(self.day, int) or isinstance(self.day, bool) or abs(self.day) > 366:
            raise RuleError("`day` must be an integer with |day| <= 366")

    def to_dict(self) -> dict:
        return {"type": "event", "name": self.name, "day": self.day}


@dataclass(frozen=True)
class NextEvent:
    """The first occurrence of `name` at or after (inclusive) / strictly
    after the anchor."""

    name: str
    inclusive: bool = True
    on_undefined: str = UndefinedPolicy.STRICT

    def __post_init__(self):
        _check_searchable(self.name, self.on_undefined)

    def to_dict(self) -> dict:
        return {"type": "next_event", "name": self.name, "inclusive": self.inclusive, "on_undefined": self.on_undefined}


@dataclass(frozen=True)
class PrevEvent:
    """The last occurrence of `name` at or before (inclusive) / strictly
    before the anchor."""

    name: str
    inclusive: bool = True
    on_undefined: str = UndefinedPolicy.STRICT

    def __post_init__(self):
        _check_searchable(self.name, self.on_undefined)

    def to_dict(self) -> dict:
        return {"type": "prev_event", "name": self.name, "inclusive": self.inclusive, "on_undefined": self.on_undefined}


@dataclass(frozen=True)
class Position:
    """A Waqt position: `seconds` of SI time after the opening Maghrib
    of the Waqt day `day` places from the anchor's. Positions past the
    day's length are legal (Waqt hours can exceed 24) and are flagged
    `within_day: false` on the resolved point rather than rejected."""

    seconds: float
    day: int = 0

    def __post_init__(self):
        if not isinstance(self.day, int) or isinstance(self.day, bool) or abs(self.day) > 366:
            raise RuleError("`day` must be an integer with |day| <= 366")
        if not math.isfinite(self.seconds):
            raise RuleError("`seconds` must be finite")

    def to_dict(self) -> dict:
        return {"type": "position", "seconds": self.seconds, "day": self.day}


@dataclass(frozen=True)
class Offset:
    """`base` shifted by a signed number of SI seconds. A Waqt hour is
    an SI hour (TIME-MODEL.md), so "N Waqt hours after X" is
    Offset(X, 3600*N)."""

    base: "Point"
    seconds: float

    def __post_init__(self):
        if not math.isfinite(self.seconds):
            raise RuleError("`seconds` must be finite")

    def to_dict(self) -> dict:
        return {"type": "offset", "base": self.base.to_dict(), "seconds": self.seconds}


@dataclass(frozen=True)
class Fraction:
    """The point `fraction` of the way from `start` to `end`. A generic
    primitive: "the last third of the night" is
    Fraction(Event("maghrib"), Event("fajr", 1), 2/3) — but WHICH
    events bound "the night" is the caller's (or their scholar's)
    decision, not this library's."""

    start: "Point"
    end: "Point"
    fraction: float

    def __post_init__(self):
        if not math.isfinite(self.fraction):
            raise RuleError("`fraction` must be finite")

    def to_dict(self) -> dict:
        return {"type": "fraction", "start": self.start.to_dict(), "end": self.end.to_dict(), "fraction": self.fraction}


Point = Union[Instant, Anchor, Event, NextEvent, PrevEvent, Position, Offset, Fraction]


def _check_searchable(name: str, on_undefined: str) -> None:
    if name not in EVENT_NAMES:
        raise RuleError(f"Next/Prev search needs one of {list(EVENT_NAMES)}, got {name!r}")
    if on_undefined not in (UndefinedPolicy.STRICT, UndefinedPolicy.SKIP):
        raise RuleError("`on_undefined` must be 'strict' or 'skip'")


# ---------------------------------------------------------------------------
# Interval
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Interval:
    """A temporal window between two points. Either end may be None
    (unbounded), which is how `before(x)` and `after(x)` are expressed.
    Default is half-open [start, end), the same convention as a Waqt day
    itself: the start instant is inside, the end instant is not."""

    start: Optional[Point]
    end: Optional[Point]
    start_inclusive: bool = True
    end_inclusive: bool = False

    def __post_init__(self):
        if self.start is None and self.end is None:
            raise RuleError("An interval needs at least one bound")

    def to_dict(self) -> dict:
        return {
            "type": "interval",
            "start": self.start.to_dict() if self.start is not None else None,
            "end": self.end.to_dict() if self.end is not None else None,
            "start_inclusive": self.start_inclusive,
            "end_inclusive": self.end_inclusive,
        }


# ---- Primitive constructors (generic; no religious application baked in) ----


def before(p: Point, inclusive: bool = False) -> Interval:
    """t < p   (or t <= p)"""
    return Interval(None, p, end_inclusive=inclusive)


def after(p: Point, inclusive: bool = True) -> Interval:
    """t >= p  (or t > p). At the exact instant of p, `after` holds —
    consistent with a Waqt day being closed at its opening Maghrib."""
    return Interval(p, None, start_inclusive=inclusive)


def between(a: Point, b: Point) -> Interval:
    """[a, b)"""
    return Interval(a, b)


def within(p: Point, seconds: float) -> Interval:
    """[p, p + seconds) — e.g. "within 2 Waqt hours after Maghrib"."""
    if seconds <= 0:
        raise RuleError("within() needs a positive duration; use between() with an Offset for a backwards window")
    return Interval(p, Offset(p, seconds))


def within_day(day: int = 0) -> Interval:
    """The whole Waqt day: [Maghrib(open), Maghrib(close))."""
    return Interval(Event("day_start", day), Event("day_end", day))


def until_next(name: str, on_undefined: str = UndefinedPolicy.STRICT) -> Interval:
    """[anchor, next occurrence of `name`)."""
    return Interval(Anchor(), NextEvent(name, on_undefined=on_undefined))


def waqt_hours(n: float) -> float:
    """N Waqt hours as SI seconds (a Waqt hour IS an SI hour)."""
    return n * 3600.0


# ---------------------------------------------------------------------------
# Parsing (the portable rule format)
# ---------------------------------------------------------------------------


def _require(d: dict, key: str, ctx: str) -> Any:
    if key not in d:
        raise RuleError(f"{ctx}: missing required field {key!r}")
    return d[key]


def _num(d: dict, key: str, ctx: str) -> float:
    v = _require(d, key, ctx)
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise RuleError(f"{ctx}: {key!r} must be a number")
    return float(v)


def _int(d: dict, key: str, ctx: str, default: int = 0) -> int:
    v = d.get(key, default)
    if isinstance(v, bool) or not isinstance(v, int):
        raise RuleError(f"{ctx}: {key!r} must be an integer")
    return v


def _bool(d: dict, key: str, ctx: str, default: bool) -> bool:
    v = d.get(key, default)
    if not isinstance(v, bool):
        raise RuleError(f"{ctx}: {key!r} must be a boolean")
    return v


def point_from_dict(d: Any, _depth: int = 0) -> Point:
    if _depth > 16:
        raise RuleError("Rule nesting too deep (limit 16)")
    if not isinstance(d, dict):
        raise RuleError("A point must be a JSON object with a `type`")
    t = d.get("type")
    if t == "instant":
        return Instant(parse_instant(_require(d, "value", "instant")))
    if t == "anchor":
        return Anchor()
    if t == "event":
        return Event(_require(d, "name", "event"), _int(d, "day", "event"))
    if t in ("next_event", "prev_event"):
        cls = NextEvent if t == "next_event" else PrevEvent
        return cls(
            _require(d, "name", t),
            _bool(d, "inclusive", t, True),
            d.get("on_undefined", UndefinedPolicy.STRICT),
        )
    if t == "position":
        return Position(_num(d, "seconds", "position"), _int(d, "day", "position"))
    if t == "offset":
        given = [k for k in ("seconds", "minutes", "waqt_hours") if k in d]
        if len(given) != 1:
            raise RuleError("offset: give exactly one of `seconds`, `minutes`, `waqt_hours`")
        k = given[0]
        secs = _num(d, k, "offset") * {"seconds": 1.0, "minutes": 60.0, "waqt_hours": 3600.0}[k]
        return Offset(point_from_dict(_require(d, "base", "offset"), _depth + 1), secs)
    if t == "fraction":
        return Fraction(
            point_from_dict(_require(d, "start", "fraction"), _depth + 1),
            point_from_dict(_require(d, "end", "fraction"), _depth + 1),
            _num(d, "fraction", "fraction"),
        )
    raise RuleError(
        f"Unknown point type {t!r}. Known: instant, anchor, event, next_event, prev_event, position, offset, fraction"
    )


def interval_from_dict(d: Any) -> Interval:
    if not isinstance(d, dict) or d.get("type", "interval") != "interval":
        raise RuleError("An interval must be a JSON object with type 'interval'")
    s, e = d.get("start"), d.get("end")
    return Interval(
        point_from_dict(s) if s is not None else None,
        point_from_dict(e) if e is not None else None,
        _bool(d, "start_inclusive", "interval", True),
        _bool(d, "end_inclusive", "interval", False),
    )

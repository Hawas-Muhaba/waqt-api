"""
waqt.semantics — the formal temporal vocabulary of Waqt.

Sprint 4 built the HTTP surface: software asking Waqt for information.
This module is Sprint 5: software REASONING about what comes back —
comparing it, doing arithmetic on it, and never being able to
accidentally treat the wrong kind of value as the wrong kind of thing.

Everything here is built on top of `waqt.core.compute_waqt()`. Nothing
in this file changes `waqt/core.py` or `waqt/solar.py` — verified by
md5sum, same as every prior sprint. `_bracket_maghrib` is imported
directly from `waqt.core` (a leading-underscore "internal" function,
reused rather than duplicated or promoted to a public API neither of
those two files needed to grow for this sprint's sake).

See docs/SEMANTICS.md for the prose specification this module
implements, and tests/vectors/waqt_vectors.json + tests/test_vectors.py
for the portable, language-independent conformance vectors this
module's own behavior is checked against.

======================================================================
1. WAQT INSTANT
======================================================================
A Waqt instant is nothing more or less than an ordinary, timezone-aware
UTC `datetime` (equivalently, a Unix timestamp). Waqt does not define
a new absolute time standard, and this module does not wrap `datetime`
in a new type for that reason — introducing one would suggest a
distinction that does not exist. `WaqtInstant` below is a *type alias*,
for signature clarity only; at runtime it IS `datetime.datetime`, and
ordinary datetime arithmetic and comparison apply to it without
modification.

TAI and leap seconds are explicitly out of scope (consistent with
Sprint 2's ΔT documentation) — Waqt instants are civil UTC.

======================================================================
2. WAQT DAY
======================================================================
    WaqtDay(L, D) = [Maghrib(L, D), Maghrib(L, D+1))

A half-open interval: closed at its opening Maghrib, open at its
closing one. THE BOUNDARY RULE, stated precisely because Sprint 5
requires it be executable, not just prose:

    An instant t belongs to WaqtDay(L, D) if and only if
        Maghrib(L, D) <= t < Maghrib(L, D+1)

At the exact instant of Maghrib, the NEW day has already begun — the
Waqt clock position at that exact instant is exactly 00:00:00, not
23:59:59-of-something or an ambiguous edge. `WaqtDay.position_of()`
implements this with ordinary `<=`/`<` on datetimes, which already
have well-defined behavior at exact equality — no special-casing
needed, and `test_semantics.py::test_exact_maghrib_instant_is_start_of_new_day`
exercises exactly this.

A WaqtDay's length is NOT guaranteed to be 86400 seconds (Sprint 1);
this module never assumes otherwise.

======================================================================
3. WAQT DATE
======================================================================
Per the Core Time Model Sec 2's join rule: the Hijri (Waqt) date
attached to WaqtDay(L, D) is the calendar provider's date for the
Gregorian civil date that D's CLOSING Maghrib falls on — i.e. "before
Maghrib -> today's date; at/after Maghrib -> tomorrow's date" is
already exactly what `core.compute_waqt`'s day-bracketing implements.
This module does not recompute that; `WaqtDay.hijri_date` is read
directly off the `WaqtResult` it was built from.

======================================================================
4. WAQT CLOCK TIME
======================================================================
`WaqtPosition` = elapsed SI time since the containing day's opening
Maghrib, as HH:MM:SS. Ordinary hours, ordinary minutes, ordinary
seconds — ONLY the epoch (Maghrib, not midnight) and the day length
(not fixed at 86400s) differ from a conventional clock.

Because the day is not fixed-length, `hour` can legitimately reach or
exceed 24 in the last minutes before the next Maghrib on a
longer-than-usual day. This is REPRESENTED, not clamped:
`WaqtPosition.hour` is a plain non-negative integer with no upper
bound enforced, and `display` renders it exactly (e.g. "24:03:17").
A caller expecting a 0-23 hour range will break on this input; that is
correct behavior on Waqt's part, per Sprint 1's original design
decision, restated here as an explicit, tested contract rather than an
incidental consequence.

======================================================================
5. EVENT POSITIONS
======================================================================
`EventPosition` pairs an event's absolute instant with its
`WaqtPosition` on the SAME day it belongs to. An EventPosition is
NEVER a clock in its own right — it cannot be constructed, compared,
or reasoned about without a containing WaqtDay, enforced structurally
(see `IncomparableWaqtValuesError` below), not just by convention.

======================================================================
6. DURATIONS VS POSITIONS VS INSTANTS
======================================================================
Three, and only three, kinds of temporal value exist in this module,
and they are never interchangeable:

    WaqtInstant  — an absolute point in physical time (= datetime)
    Duration     — elapsed SI time (= datetime.timedelta)
    WaqtPosition — a position WITHIN one specific WaqtDay (HH:MM:SS,
                   meaningless without that day)

`Duration` is not given a new type either, for the same reason
`WaqtInstant` isn't: `datetime.timedelta` already IS exactly "elapsed
SI time" with correct arithmetic, and wrapping it would add ceremony
without adding meaning. What IS enforced structurally is that
`WaqtPosition` can never silently be used as a `Duration` in
comparison or arithmetic across two different days — see §7.

======================================================================
7. COMPARISON AND ARITHMETIC
======================================================================
    instant - instant -> Duration           : ordinary datetime subtraction
    instant + Duration -> instant           : ordinary datetime addition
    WaqtDay.position_of(instant) -> WaqtPosition
    WaqtPosition.to_instant(day) -> instant : position + its day -> absolute instant
    event -> EventPosition                  : see WaqtDay.events
    ordering of events                      : EventPosition.__lt__ (same-day only)
    crossing a Maghrib boundary             : crosses_maghrib(instant_a, instant_b, location)

WaqtPosition and EventPosition comparison (`<`, `<=`, `==`) is ONLY
defined between two values belonging to the SAME WaqtDay (same
location, same opening Maghrib instant). Comparing positions from two
different days or locations raises `IncomparableWaqtValuesError`
rather than silently comparing two numbers that don't mean the same
thing — this was flagged as a design requirement as far back as the
very first Waqt proposal review ("Waqt timestamps from different
locations MUST NOT be compared"), and this module is where that
requirement becomes enforced code instead of a sentence in a document.

======================================================================
8. UNDEFINED EVENTS
======================================================================
Sprint 4 established structured `status: "UNDEFINED"` at the HTTP
layer (polar day/night). This module extends that into the semantics
layer's own exception: any operation that requires a day boundary or
an event that doesn't exist raises `WaqtUndefinedError` — carrying the
same `undefined_reason` the HTTP layer already reports — rather than
returning `None` silently or raising a generic `TypeError` somewhere
deep in arithmetic. `WaqtDay.position_of()`, `WaqtDay.relation_to()`,
and `EventPosition` construction for a missing event all raise this.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal, Optional

from .core import WaqtResult, _bracket_maghrib
from .hijri import HijriDate

# Type alias only — see module docstring §1. At runtime this IS datetime.
WaqtInstant = datetime

Relation = Literal["before", "at", "after"]


class WaqtUndefinedError(Exception):
    """Raised when an operation needs a day boundary or event that
    doesn't exist (polar day/night). Carries the same reason string
    the HTTP layer's `undefined_reason` field already reports."""

    def __init__(self, message: str, undefined_reason: Optional[str] = None):
        super().__init__(message)
        self.undefined_reason = undefined_reason


class IncomparableWaqtValuesError(Exception):
    """Raised when comparing WaqtPosition/EventPosition values that
    don't belong to the same WaqtDay. See module docstring §7."""


def _day_identity(open_instant: Optional[datetime], lat: float, lon: float) -> tuple:
    """The thing that makes two WaqtDay instances 'the same day' for
    comparison purposes: same location, same opening Maghrib instant.
    Not the Hijri date (that's a label; this is the actual interval)."""
    return (round(lat, 6), round(lon, 6), open_instant)


@dataclass(frozen=True)
class WaqtPosition:
    """A position within ONE specific WaqtDay. Never comparable across
    different days — see IncomparableWaqtValuesError."""

    hour: int
    minute: int
    second: int
    total_seconds: float
    _day_id: tuple  # identity of the WaqtDay this position belongs to; not part of the public value

    @property
    def display(self) -> str:
        return f"{self.hour:02d}:{self.minute:02d}:{self.second:02d}"

    def to_instant(self, day: "WaqtDay") -> WaqtInstant:
        """Reconstruct the absolute instant this position denotes,
        given the day it belongs to. instant = day.open + elapsed."""
        if day._identity() != self._day_id:
            raise IncomparableWaqtValuesError(
                "This WaqtPosition does not belong to the given WaqtDay — "
                "positions can only be resolved to an instant via their own day."
            )
        return day.open + timedelta(seconds=self.total_seconds)

    def _check_comparable(self, other: "WaqtPosition") -> None:
        if not isinstance(other, WaqtPosition):
            raise TypeError(f"Cannot compare WaqtPosition with {type(other).__name__}")
        if self._day_id != other._day_id:
            raise IncomparableWaqtValuesError(
                "Cannot compare WaqtPosition values from different Waqt days "
                "(different location and/or different opening Maghrib instant). "
                "Convert both to instants first if you need to compare across days."
            )

    def __lt__(self, other: "WaqtPosition") -> bool:
        self._check_comparable(other)
        return self.total_seconds < other.total_seconds

    def __le__(self, other: "WaqtPosition") -> bool:
        self._check_comparable(other)
        return self.total_seconds <= other.total_seconds

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, WaqtPosition):
            return NotImplemented
        if self._day_id != other._day_id:
            return False  # different days are simply never equal, not an error, for ==
        return self.total_seconds == other.total_seconds

    def __hash__(self) -> int:
        return hash((self._day_id, self.total_seconds))


@dataclass(frozen=True)
class EventPosition:
    """One named event, as both an absolute instant and its position on
    a specific WaqtDay's clock. Cannot exist independent of a day."""

    name: str
    instant: WaqtInstant
    position: WaqtPosition

    def relation_to(self, other_instant: WaqtInstant) -> Relation:
        """Where `other_instant` falls relative to this event: before,
        at (exact equality), or after."""
        if other_instant < self.instant:
            return "before"
        if other_instant == self.instant:
            return "at"
        return "after"

    def _check_comparable(self, other: "EventPosition") -> None:
        if not isinstance(other, EventPosition):
            raise TypeError(f"Cannot compare EventPosition with {type(other).__name__}")
        if self.position._day_id != other.position._day_id:
            raise IncomparableWaqtValuesError(
                "Cannot compare EventPosition values from different Waqt days."
            )

    def __lt__(self, other: "EventPosition") -> bool:
        self._check_comparable(other)
        return self.instant < other.instant

    def __le__(self, other: "EventPosition") -> bool:
        self._check_comparable(other)
        return self.instant <= other.instant

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, EventPosition):
            return NotImplemented
        return self.instant == other.instant and self.name == other.name


@dataclass(frozen=True)
class WaqtDay:
    """WaqtDay(L, D) = [Maghrib(L,D), Maghrib(L,D+1)). See module
    docstring §2. Built from a WaqtResult (core.compute_waqt's output);
    never recomputes astronomy itself."""

    lat: float
    lon: float
    open: Optional[WaqtInstant]     # Maghrib(L, D) — None if UNDEFINED
    close: Optional[WaqtInstant]    # Maghrib(L, D+1) — None if UNDEFINED
    length_seconds: Optional[float]
    hijri_date: Optional[HijriDate]
    weekday: Optional[str]
    status: str                      # "OK" | "UNDEFINED" | "ORDERING_VIOLATION"
    undefined_reason: Optional[str]
    _events: dict  # name -> Optional[WaqtInstant]

    @property
    def is_defined(self) -> bool:
        return self.status == "OK"

    def _identity(self) -> tuple:
        return _day_identity(self.open, self.lat, self.lon)

    def _require_defined(self, what: str) -> None:
        if not self.is_defined:
            raise WaqtUndefinedError(
                f"Cannot compute {what}: this Waqt day is {self.status}.",
                undefined_reason=self.undefined_reason,
            )

    def contains(self, instant: WaqtInstant) -> bool:
        """t in WaqtDay(L,D) iff open <= t < close. See module
        docstring §2 for why this is the exact rule, unconditionally."""
        self._require_defined("day membership")
        return self.open <= instant < self.close

    def position_of(self, instant: WaqtInstant) -> WaqtPosition:
        """The instant's HH:MM:SS position on this day's clock. Can
        legitimately return hour >= 24 — see module docstring §4.
        Does NOT require `instant` to actually be inside this day
        (elapsed-since-Maghrib is well-defined either way); use
        `contains()` first if you need that check."""
        self._require_defined("Waqt clock position")
        delta = instant - self.open
        total = delta.total_seconds()
        sign_ok = total >= 0  # negative is meaningful (before this day's Maghrib) but unusual
        h, rem = divmod(int(abs(total)), 3600)
        m, s = divmod(rem, 60)
        if not sign_ok:
            h, m, s = -h, m, s  # preserve sign on hour only, for a readable display
        return WaqtPosition(hour=h, minute=m, second=s, total_seconds=total, _day_id=self._identity())

    def event(self, name: str) -> EventPosition:
        """The named event ('fajr','sunrise','dhuhr','asr','maghrib','isha')
        as an EventPosition on this day. Raises WaqtUndefinedError if
        that specific event didn't occur (e.g. Fajr undefined at very
        high latitude even when Maghrib itself is fine)."""
        self._require_defined("event position")
        if name not in self._events:
            raise KeyError(f"Unknown event {name!r}. Known: {sorted(self._events)}")
        instant = self._events[name]
        if instant is None:
            raise WaqtUndefinedError(
                f"Event {name!r} does not occur on this Waqt day.",
                undefined_reason=f"{name} undefined for this date/location",
            )
        return EventPosition(name=name, instant=instant, position=self.position_of(instant))

    def events(self) -> list[EventPosition]:
        """All defined events on this day, in chronological order.
        Undefined individual events (e.g. Fajr at extreme latitude) are
        simply omitted, not raised — call `.event(name)` directly if
        you need the explicit error for one specific event."""
        self._require_defined("event list")
        out = []
        for name, instant in self._events.items():
            if instant is not None:
                out.append(EventPosition(name=name, instant=instant, position=self.position_of(instant)))
        return sorted(out, key=lambda e: e.instant)

    def relation_to(self, instant: WaqtInstant, event_name: str) -> Relation:
        """Where `instant` falls relative to the named event on this
        day: 'before', 'at', or 'after'. Raises WaqtUndefinedError if
        that event doesn't occur."""
        return self.event(event_name).relation_to(instant)


def waqt_day_from_result(r: WaqtResult) -> WaqtDay:
    """Build a WaqtDay from a core.compute_waqt() result. This is the
    ONLY way a WaqtDay gets constructed — never independently
    recomputed, so it can never disagree with the engine that produced
    the numbers it wraps."""
    events = {e.name: e.instant for e in r.events} if r.events else {
        "fajr": None, "sunrise": None, "dhuhr": None, "asr": None, "maghrib": None, "isha": None,
    }
    return WaqtDay(
        lat=r.location_lat,
        lon=r.location_lon,
        open=r.day_start_maghrib,
        close=r.day_end_maghrib,
        length_seconds=r.day_length_si_seconds,
        hijri_date=r.hijri_date,
        weekday=r.weekday,
        status=r.status,
        undefined_reason=r.undefined_reason,
        _events=events,
    )


def crosses_maghrib(instant_a: WaqtInstant, instant_b: WaqtInstant, lat: float, lon: float, **bracket_kwargs) -> bool:
    """Does the SI-time span between instant_a and instant_b cross a
    Maghrib boundary at this location? True iff the two instants
    belong to different Waqt days. Order-independent (works whichever
    instant is earlier).

    Implemented by reusing core._bracket_maghrib directly (see module
    docstring header) rather than re-deriving day boundaries here.
    """
    if instant_a > instant_b:
        instant_a, instant_b = instant_b, instant_a

    from .core import Location
    from .timezone_provider import DEFAULT_TIMEZONE_PROVIDER
    from .timescale import DEFAULT_TIMESCALE_PROVIDER

    loc = Location(lat=lat, lon=lon, elevation_m=bracket_kwargs.get("elevation_m", 0.0))
    tz_provider = bracket_kwargs.get("tz_provider", DEFAULT_TIMEZONE_PROVIDER)
    timescale = bracket_kwargs.get("timescale", DEFAULT_TIMESCALE_PROVIDER)

    _, open_a, _, _, _ = _bracket_maghrib(instant_a, loc, tz_provider, timescale)
    _, open_b, _, _, _ = _bracket_maghrib(instant_b, loc, tz_provider, timescale)

    if open_a is None or open_b is None:
        raise WaqtUndefinedError(
            "Cannot determine Maghrib-crossing: at least one instant falls "
            "on an undefined (polar) Waqt day at this location."
        )
    return open_a != open_b

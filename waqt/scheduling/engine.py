"""
waqt.scheduling.engine — resolving Islamic temporal rules.

Given a SchedulingContext (a place + astronomy profile + calendar
provider) the SchedulingEngine turns declarative rules from model.py
into concrete instants and answers the practical questions applications
actually ask:

    day_bounds(t)            When does the Islamic day begin / end?
    until(name, t)           How long until Maghrib?
    since(name, t)           How long since Fajr?
    next_event(t)            What is the next astronomical event?
    event_position(name, t)  What is the Waqt position of Isha?
    resolve_point(p, t)      What instant is "30 minutes before Maghrib"?
    resolve_interval(w, t)   What are the bounds of [Maghrib, Isha)?
    evaluate(w, t, anchor)   Is t inside that window?
    check_deadline(p, ...)   pending / reached / passed, and how long?
    classify_span(a, b)      Does [a, b) cross a Maghrib boundary?
    snapshot(t)              All of the above for the current moment.

DESIGN RULES (each is tested; see docs/SCHEDULING.md)
-----------------------------------------------------
* Results, not exceptions. Undefined astronomy is an ordinary outcome
  at high latitude, so every resolve returns a result object with a
  `status` (OK / EVENT_UNDEFINED / WINDOW_UNDEFINED / NO_VALID_WINDOW).
  Nothing here ever substitutes an "approximate" time for a missing
  one. The only fallback that exists (`on_undefined="skip"`) is an
  explicit opt-in that reports exactly what it skipped.
* No astronomy is computed here. Every event instant comes from
  waqt.core.compute_waqt via SchedulingContext. core.py and solar.py
  are untouched (md5 verified in the Sprint 6 report).
* No calendar input. Hijri labels are copied onto results for display
  only.
* Exact arithmetic. Derived instants use integer microseconds and one
  documented rounding rule (floor(x + 0.5)) so another language gets
  bit-identical answers, not "close" ones.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from ..semantics import WaqtUndefinedError
from .context import DayUnavailable, SchedulingContext
from .model import (
    DAY_SHIFT,
    EVENT_NAMES,
    Anchor,
    Event,
    Fraction,
    Instant,
    Interval,
    NextEvent,
    Offset,
    Point,
    Position,
    PrevEvent,
    RuleError,
    Status,
    UndefinedPolicy,
    from_micros,
    parse_instant,
    round_half_up,
    to_micros,
)

MAX_LOOKAHEAD_DAYS = 8      # occurrence searches examine at most this many day-slots
MAX_SPAN_DAYS = 400         # classify_span steps at most this many Waqt days
_ONE_MICRO = timedelta(microseconds=1)

# Basis vocabulary (see model.py)
ABSOLUTE = "absolute_instant"
ASTRONOMICAL = "astronomical_event"
WAQT_POSITION = "waqt_position"
RULE_DERIVED = "rule_derived"


def _iso(dt: Optional[datetime], round_seconds: bool = False) -> Optional[str]:
    if dt is None:
        return None
    dt = dt.astimezone(timezone.utc)
    if round_seconds:
        dt = dt.replace(microsecond=0)
    return dt.isoformat()


def _utc(dt: datetime) -> datetime:
    return parse_instant(dt)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResolvedPoint:
    status: str
    instant: Optional[datetime]
    basis: Optional[str]                  # which kind of point this is (None if undefined)
    depends_on: tuple                     # leaf bases it was built from
    description: str
    within_day: Optional[bool] = None     # Position points only
    reason: Optional[str] = None
    cause: Optional[str] = None           # "DAY_UNDEFINED" | "EVENT_UNDEFINED_ON_DAY" | "NO_OCCURRENCE_IN_RANGE"
    undefined_ref: Optional[str] = None   # e.g. "fajr@day+0"
    skipped: tuple = ()                   # refs skipped under on_undefined="skip"

    @property
    def ok(self) -> bool:
        return self.status == Status.OK

    def to_dict(self, round_seconds: bool = False) -> dict:
        return {
            "status": self.status,
            "instant": _iso(self.instant, round_seconds),
            "basis": self.basis,
            "depends_on": list(self.depends_on),
            "description": self.description,
            "within_day": self.within_day,
            "reason": self.reason,
            "cause": self.cause,
            "undefined_ref": self.undefined_ref,
            "skipped": list(self.skipped),
        }


@dataclass(frozen=True)
class ResolvedInterval:
    status: str
    start: Optional[ResolvedPoint]        # None => unbounded on that side
    end: Optional[ResolvedPoint]
    start_inclusive: bool
    end_inclusive: bool
    duration_seconds: Optional[float]     # None if unbounded or not OK
    reason: Optional[str] = None
    causes: tuple = ()                    # the EVENT_UNDEFINED endpoint results behind a WINDOW_UNDEFINED

    @property
    def ok(self) -> bool:
        return self.status == Status.OK

    def contains_instant(self, t: datetime) -> bool:
        """Membership under this interval's own inclusivity flags.
        Only meaningful when status == OK."""
        if not self.ok:
            raise ValueError(f"Interval is {self.status}; membership is not defined.")
        t = _utc(t)
        if self.start is not None:
            s = self.start.instant
            if not (t > s or (t == s and self.start_inclusive)):
                return False
        if self.end is not None:
            e = self.end.instant
            if not (t < e or (t == e and self.end_inclusive)):
                return False
        return True

    def to_dict(self, round_seconds: bool = False) -> dict:
        return {
            "status": self.status,
            "start": self.start.to_dict(round_seconds) if self.start else None,
            "end": self.end.to_dict(round_seconds) if self.end else None,
            "start_inclusive": self.start_inclusive,
            "end_inclusive": self.end_inclusive,
            "duration_seconds": self.duration_seconds,
            "reason": self.reason,
            "causes": [c.to_dict(round_seconds) for c in self.causes],
        }


@dataclass(frozen=True)
class Evaluation:
    """Is `instant` inside the window? `inside` is None — not False —
    whenever the window itself is not OK: 'unknown' is not 'no'."""

    status: str
    instant: datetime
    inside: Optional[bool]
    relation: Optional[str]               # "before_window" | "inside" | "after_window"
    window: ResolvedInterval

    def to_dict(self, round_seconds: bool = False) -> dict:
        return {
            "status": self.status,
            "instant": _iso(self.instant, round_seconds),
            "inside": self.inside,
            "relation": self.relation,
            "window": self.window.to_dict(round_seconds),
        }


@dataclass(frozen=True)
class Measure:
    """A duration to (`until`) or from (`since`) a resolved point.
    `seconds` is always >= 0 for until/since of an occurrence search."""

    kind: str                              # "until" | "since"
    status: str
    seconds: Optional[float]
    target: ResolvedPoint

    def to_dict(self, round_seconds: bool = False) -> dict:
        return {"kind": self.kind, "status": self.status, "seconds": self.seconds,
                "target": self.target.to_dict(round_seconds)}


@dataclass(frozen=True)
class DeadlineCheck:
    """state: 'pending' (now < deadline) | 'reached' (now == deadline)
    | 'passed' (now > deadline). remaining_seconds is signed: positive
    while pending, 0 at the deadline, negative once passed."""

    status: str
    state: Optional[str]
    remaining_seconds: Optional[float]
    deadline: ResolvedPoint

    def to_dict(self, round_seconds: bool = False) -> dict:
        return {"status": self.status, "state": self.state, "remaining_seconds": self.remaining_seconds,
                "deadline": self.deadline.to_dict(round_seconds)}


@dataclass(frozen=True)
class DayBounds:
    status: str
    instant: datetime
    open: Optional[datetime]
    close: Optional[datetime]
    length_seconds: Optional[float]
    position_seconds: Optional[float]
    position_display: Optional[str]
    hijri_label: Optional[str]            # display only — see context.py
    reason: Optional[str] = None

    def to_dict(self, round_seconds: bool = False) -> dict:
        return {
            "status": self.status, "instant": _iso(self.instant, round_seconds),
            "open": _iso(self.open, round_seconds), "close": _iso(self.close, round_seconds),
            "length_seconds": self.length_seconds,
            "position": {"seconds": self.position_seconds, "display": self.position_display}
            if self.position_seconds is not None else None,
            "hijri_label": self.hijri_label, "reason": self.reason,
        }


@dataclass(frozen=True)
class NextEventResult:
    status: str
    name: Optional[str]
    instant: Optional[datetime]
    seconds_until: Optional[float]
    position_seconds: Optional[float]     # in the Waqt day that CONTAINS the event
    position_display: Optional[str]
    undefined_events: tuple = ()          # ({"name","reason"}, ...) — events with no occurrence to consider
    reason: Optional[str] = None

    def to_dict(self, round_seconds: bool = False) -> dict:
        return {
            "status": self.status, "name": self.name, "instant": _iso(self.instant, round_seconds),
            "seconds_until": self.seconds_until,
            "position": {"seconds": self.position_seconds, "display": self.position_display}
            if self.position_seconds is not None else None,
            "undefined_events": list(self.undefined_events), "reason": self.reason,
        }


@dataclass(frozen=True)
class EventPositionResult:
    """Where an event sits on the Waqt clock — reported TWICE because
    Isha makes the difference visible. `listed_*` is the position
    measured from the day that LISTS the event (Sprint 5's
    EventPosition; for Isha it exceeds the day's own length).
    `containing_*` is the position in the Waqt day that actually
    CONTAINS the instant under the half-open rule."""

    status: str
    name: str
    instant: Optional[datetime]
    listed_position_seconds: Optional[float]
    listed_position_display: Optional[str]
    containing_day_relative_to_listed: Optional[int]   # 0 = same day; 1 = the next Waqt day
    containing_position_seconds: Optional[float]
    containing_position_display: Optional[str]
    reason: Optional[str] = None

    def to_dict(self, round_seconds: bool = False) -> dict:
        return {
            "status": self.status, "name": self.name, "instant": _iso(self.instant, round_seconds),
            "listed": {"seconds": self.listed_position_seconds, "display": self.listed_position_display},
            "containing": {
                "day_relative_to_listed": self.containing_day_relative_to_listed,
                "seconds": self.containing_position_seconds, "display": self.containing_position_display,
            },
            "reason": self.reason,
        }


@dataclass(frozen=True)
class SpanClassification:
    """How a half-open span [start, end) sits against Waqt-day
    boundaries — and, separately, against civil midnight. The two are
    independent facts: 23:30 -> 00:30 crosses civil midnight but (in
    practice) no Maghrib; 17:30 -> 19:30 crosses Maghrib but no civil
    midnight."""

    status: str
    start: datetime
    end: datetime
    end_inclusive: bool
    duration_seconds: Optional[float]
    same_waqt_day: Optional[bool]
    crosses_maghrib: Optional[bool]
    maghrib_boundaries: tuple             # every Maghrib strictly inside the span
    waqt_days_touched: Optional[int]
    start_day: Optional[dict]             # {"open","close","hijri_label"}
    end_day: Optional[dict]
    crosses_civil_midnight: Optional[bool]
    start_civil_date: Optional[str]
    end_civil_date: Optional[str]
    reason: Optional[str] = None

    def to_dict(self, round_seconds: bool = False) -> dict:
        return {
            "status": self.status, "start": _iso(self.start, round_seconds), "end": _iso(self.end, round_seconds),
            "end_inclusive": self.end_inclusive, "duration_seconds": self.duration_seconds,
            "same_waqt_day": self.same_waqt_day, "crosses_maghrib": self.crosses_maghrib,
            "maghrib_boundaries": [_iso(b, round_seconds) for b in self.maghrib_boundaries],
            "waqt_days_touched": self.waqt_days_touched,
            "start_day": self.start_day, "end_day": self.end_day,
            "crosses_civil_midnight": self.crosses_civil_midnight,
            "start_civil_date": self.start_civil_date, "end_civil_date": self.end_civil_date,
            "reason": self.reason,
        }


# ---------------------------------------------------------------------------
# Internal resolution machinery
# ---------------------------------------------------------------------------


class _Undef(Exception):
    def __init__(self, ref: str, cause: str, reason: str):
        super().__init__(reason)
        self.ref, self.cause, self.reason = ref, cause, reason


@dataclass
class _Val:
    instant: datetime
    bases: frozenset
    basis: str
    within_day: Optional[bool] = None
    skipped: list = field(default_factory=list)


def _ref(name: str, k: int) -> str:
    return f"{name}@day{k:+d}"


def describe(p: Point) -> str:
    if isinstance(p, Instant):
        return f"instant({_iso(p.value)})"
    if isinstance(p, Anchor):
        return "anchor"
    if isinstance(p, Event):
        return f"event({p.name}, day={p.day:+d})"
    if isinstance(p, NextEvent):
        return f"next({p.name}{'' if p.inclusive else ', exclusive'})"
    if isinstance(p, PrevEvent):
        return f"prev({p.name}{'' if p.inclusive else ', exclusive'})"
    if isinstance(p, Position):
        return f"position({p.seconds:g}s, day={p.day:+d})"
    if isinstance(p, Offset):
        return f"{describe(p.base)} {'+' if p.seconds >= 0 else '-'} {abs(p.seconds):g}s"
    if isinstance(p, Fraction):
        return f"fraction({p.fraction:g}) from {describe(p.start)} to {describe(p.end)}"
    raise TypeError(p)


class _Env:
    """One resolution session: a fixed anchor and a lazily-built,
    memoised view of the Waqt days around it."""

    def __init__(self, ctx: SchedulingContext, anchor: datetime):
        self.ctx = ctx
        self.anchor = anchor
        self._day0 = None
        self._days: dict = {}

    def day(self, k: int, ref: str):
        if k in self._days:
            return self._days[k]
        if self._day0 is None:
            self._day0 = self.ctx.day_containing(self.anchor)
        try:
            d = self.ctx.neighbor(self._day0, k)
        except DayUnavailable as e:
            raise _Undef(ref, "DAY_UNDEFINED", e.reason)
        self._days[k] = d
        return d

    def slot(self, name: str, k: int) -> datetime:
        """The instant of `name` as listed on Waqt day k."""
        ref = _ref(name, k)
        d = self.day(k, ref)
        if not d.is_defined:
            raise _Undef(ref, "DAY_UNDEFINED", d.undefined_reason or f"Waqt day is {d.status}.")
        if name == "day_start":
            return d.open
        if name == "day_end":
            return d.close
        try:
            return d.event(name).instant
        except WaqtUndefinedError as e:
            raise _Undef(ref, "EVENT_UNDEFINED_ON_DAY", str(e))


def _eval(p: Point, env: _Env) -> _Val:
    if isinstance(p, Instant):
        return _Val(_utc(p.value), frozenset({ABSOLUTE}), ABSOLUTE)
    if isinstance(p, Anchor):
        return _Val(env.anchor, frozenset({ABSOLUTE}), ABSOLUTE)
    if isinstance(p, Event):
        return _Val(env.slot(p.name, p.day), frozenset({ASTRONOMICAL}), ASTRONOMICAL)
    if isinstance(p, (NextEvent, PrevEvent)):
        return _eval_occurrence(p, env)
    if isinstance(p, Position):
        ref = f"position@day{p.day:+d}"
        d = env.day(p.day, ref)
        if not d.is_defined:
            raise _Undef(ref, "DAY_UNDEFINED", d.undefined_reason or f"Waqt day is {d.status}.")
        t = from_micros(to_micros(d.open) + round_half_up(p.seconds * 1e6))
        return _Val(t, frozenset({WAQT_POSITION}), WAQT_POSITION, within_day=(d.open <= t < d.close))
    if isinstance(p, Offset):
        b = _eval(p.base, env)
        t = from_micros(to_micros(b.instant) + round_half_up(p.seconds * 1e6))
        return _Val(t, b.bases, RULE_DERIVED, skipped=b.skipped)
    if isinstance(p, Fraction):
        a, b = _eval(p.start, env), _eval(p.end, env)
        sa, sb = to_micros(a.instant), to_micros(b.instant)
        t = from_micros(sa + round_half_up((sb - sa) * p.fraction))
        return _Val(t, a.bases | b.bases, RULE_DERIVED, skipped=a.skipped + b.skipped)
    raise TypeError(f"Not a point: {p!r}")


def _eval_occurrence(p, env: _Env) -> _Val:
    """Next/Prev occurrence search over day-slots. Slot k holds the
    event as LISTED on day k; it OCCURS in Waqt day k + DAY_SHIFT
    (0 for everything except Isha, which occurs in the following day).
    The anchor lies in day 0, so the search starts at the slot that
    occurs in day 0 (k = -shift) and walks forward (Next) or backward
    (Prev). That start point is what makes an undefined event on some
    irrelevant day (e.g. yesterday's Fajr, when looking for the next
    Fajr) correctly NOT matter."""
    is_next = isinstance(p, NextEvent)
    shift = DAY_SHIFT.get(p.name, 0)
    step = 1 if is_next else -1
    k = -shift
    skipped: list = []
    first_undef: Optional[_Undef] = None
    for _ in range(MAX_LOOKAHEAD_DAYS):
        try:
            t = env.slot(p.name, k)
        except _Undef as u:
            if p.on_undefined != UndefinedPolicy.SKIP:
                raise
            skipped.append(u.ref)
            first_undef = first_undef or u
            k += step
            continue
        a = env.anchor
        ok = (t >= a if p.inclusive else t > a) if is_next else (t <= a if p.inclusive else t < a)
        if ok:
            return _Val(t, frozenset({ASTRONOMICAL}), ASTRONOMICAL, skipped=skipped)
        k += step
    ref = _ref(p.name, k)
    raise _Undef(
        first_undef.ref if first_undef else ref,
        "NO_OCCURRENCE_IN_RANGE",
        f"No {'next' if is_next else 'previous'} {p.name} found within {MAX_LOOKAHEAD_DAYS} day-slots"
        + (f" (skipped undefined: {', '.join(skipped)})." if skipped else "."),
    )


def _to_resolved_point(p: Point, env: _Env) -> ResolvedPoint:
    try:
        v = _eval(p, env)
    except _Undef as u:
        return ResolvedPoint(
            status=Status.EVENT_UNDEFINED, instant=None, basis=None, depends_on=(),
            description=describe(p), reason=u.reason, cause=u.cause, undefined_ref=u.ref,
        )
    return ResolvedPoint(
        status=Status.OK, instant=v.instant, basis=v.basis, depends_on=tuple(sorted(v.bases)),
        description=describe(p), within_day=v.within_day, skipped=tuple(v.skipped),
    )


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class SchedulingEngine:
    def __init__(self, ctx: SchedulingContext):
        self.ctx = ctx

    # -- points and intervals -------------------------------------------------

    def resolve_point(self, point: Point, anchor: datetime) -> ResolvedPoint:
        return _to_resolved_point(point, _Env(self.ctx, _utc(anchor)))

    def resolve_interval(self, interval: Interval, anchor: datetime) -> ResolvedInterval:
        env = _Env(self.ctx, _utc(anchor))
        s = _to_resolved_point(interval.start, env) if interval.start is not None else None
        e = _to_resolved_point(interval.end, env) if interval.end is not None else None
        return self._assemble_interval(interval, s, e)

    @staticmethod
    def _assemble_interval(interval: Interval, s: Optional[ResolvedPoint], e: Optional[ResolvedPoint]) -> ResolvedInterval:
        common = dict(start=s, end=e, start_inclusive=interval.start_inclusive, end_inclusive=interval.end_inclusive)
        causes = tuple(x for x in (s, e) if x is not None and not x.ok)
        if causes:
            return ResolvedInterval(
                status=Status.WINDOW_UNDEFINED, duration_seconds=None, causes=causes,
                reason="; ".join(f"{c.description}: {c.reason}" for c in causes), **common,
            )
        if s is not None and e is not None:
            us, ue = to_micros(s.instant), to_micros(e.instant)
            empty = ue < us or (ue == us and not (interval.start_inclusive and interval.end_inclusive))
            if empty:
                why = "ends before it starts" if ue < us else "is empty (start == end with a half-open bound)"
                return ResolvedInterval(
                    status=Status.NO_VALID_WINDOW, duration_seconds=None,
                    reason=f"Both endpoints exist but the window {why}.", **common,
                )
            return ResolvedInterval(status=Status.OK, duration_seconds=(ue - us) / 1e6, **common)
        return ResolvedInterval(status=Status.OK, duration_seconds=None, **common)

    def evaluate(self, interval: Interval, instant: datetime, anchor: Optional[datetime] = None) -> Evaluation:
        """Is `instant` inside `interval`? `anchor` (default: `instant`)
        is what Anchor/NextEvent/PrevEvent/day-relative refs resolve
        against. For rules built from Next/Prev/Anchor, pass an anchor
        that is fixed independently of the instant you are testing —
        otherwise the window slides along with the test instant."""
        t = _utc(instant)
        w = self.resolve_interval(interval, _utc(anchor) if anchor is not None else t)
        if not w.ok:
            return Evaluation(w.status, t, None, None, w)
        inside = w.contains_instant(t)
        if inside:
            rel = "inside"
        elif w.start is not None and (t < w.start.instant or (t == w.start.instant and not w.start_inclusive)):
            rel = "before_window"
        else:
            rel = "after_window"
        return Evaluation(Status.OK, t, inside, rel, w)

    # -- deadlines --------------------------------------------------------------

    def check_deadline(self, point: Point, anchor: datetime, now: Optional[datetime] = None) -> DeadlineCheck:
        anchor = _utc(anchor)
        now = _utc(now) if now is not None else anchor
        rp = self.resolve_point(point, anchor)
        if not rp.ok:
            return DeadlineCheck(rp.status, None, None, rp)
        delta = (to_micros(rp.instant) - to_micros(now)) / 1e6
        state = "pending" if delta > 0 else ("reached" if delta == 0 else "passed")
        return DeadlineCheck(Status.OK, state, delta, rp)

    # -- the practical questions ------------------------------------------------------

    def until(self, name: str, instant: datetime, on_undefined: str = UndefinedPolicy.STRICT) -> Measure:
        """How long until the next `name` (at or after `instant`)?"""
        t = _utc(instant)
        rp = self.resolve_point(NextEvent(name, True, on_undefined), t)
        if not rp.ok:
            return Measure("until", rp.status, None, rp)
        return Measure("until", Status.OK, (to_micros(rp.instant) - to_micros(t)) / 1e6, rp)

    def since(self, name: str, instant: datetime, on_undefined: str = UndefinedPolicy.STRICT) -> Measure:
        """How long since the most recent `name` (at or before `instant`)?"""
        t = _utc(instant)
        rp = self.resolve_point(PrevEvent(name, True, on_undefined), t)
        if not rp.ok:
            return Measure("since", rp.status, None, rp)
        return Measure("since", Status.OK, (to_micros(t) - to_micros(rp.instant)) / 1e6, rp)

    def day_bounds(self, instant: datetime) -> DayBounds:
        t = _utc(instant)
        d = self.ctx.day_containing(t)
        if not d.is_defined:
            return DayBounds(Status.EVENT_UNDEFINED, t, None, None, None, None, None, None,
                             reason=d.undefined_reason or f"Waqt day is {d.status}.")
        pos = d.position_of(t)
        return DayBounds(
            Status.OK, t, d.open, d.close, (to_micros(d.close) - to_micros(d.open)) / 1e6,
            (to_micros(t) - to_micros(d.open)) / 1e6, pos.display, self.ctx.hijri_label(d),
        )

    def next_event(self, instant: datetime) -> NextEventResult:
        """The next astronomical event strictly after `instant`, among
        those that actually occur. Events that have no occurrence to
        consider are listed in `undefined_events` rather than silently
        dropped — 'the next event is sunrise' and 'the next event is
        sunrise, and Fajr does not occur tonight' are different
        answers."""
        t = _utc(instant)
        best = None
        undefined = []
        for name in EVENT_NAMES:
            rp = self.resolve_point(NextEvent(name, inclusive=False), t)
            if not rp.ok:
                undefined.append({"name": name, "reason": rp.reason, "cause": rp.cause})
            elif best is None or rp.instant < best[1]:
                best = (name, rp.instant)
        if best is None:
            return NextEventResult(Status.EVENT_UNDEFINED, None, None, None, None, None,
                                   tuple(undefined), reason="No astronomical event occurs in the search range.")
        d = self.ctx.day_containing(best[1])
        disp = d.position_of(best[1]) if d.is_defined else None
        return NextEventResult(
            Status.OK, best[0], best[1], (to_micros(best[1]) - to_micros(t)) / 1e6,
            disp.total_seconds if disp else None, disp.display if disp else None, tuple(undefined),
        )

    def event_position(self, name: str, anchor: datetime, day: Optional[int] = None) -> EventPositionResult:
        """The Waqt position of `name`. With `day=None` (default) this is
        the NEXT occurrence at or after `anchor` — what "what is the Waqt
        position of Isha?" almost always means. With an explicit `day`
        it is the slot listed on that Waqt day (Event(name, day))."""
        env = _Env(self.ctx, _utc(anchor))
        point = NextEvent(name, True) if day is None else Event(name, day)
        rp = _to_resolved_point(point, env)
        if not rp.ok:
            return EventPositionResult(rp.status, name, None, None, None, None, None, None, reason=rp.reason)
        containing = self.ctx.day_containing(rp.instant)
        shift = DAY_SHIFT.get(name, 0)
        try:
            listed = self.ctx.neighbor(containing, -shift)
        except DayUnavailable as e:
            return EventPositionResult(Status.EVENT_UNDEFINED, name, None, None, None, None, None, None, reason=e.reason)
        if not listed.is_defined:
            return EventPositionResult(Status.EVENT_UNDEFINED, name, None, None, None, None, None, None,
                                       reason=listed.undefined_reason or f"Waqt day is {listed.status}.")
        lp, cp = listed.position_of(rp.instant), containing.position_of(rp.instant)
        return EventPositionResult(Status.OK, name, rp.instant, lp.total_seconds, lp.display, shift,
                                   cp.total_seconds, cp.display)

    # -- spans crossing Maghrib ---------------------------------------------------------

    def classify_span(self, start: datetime, end: datetime, end_inclusive: bool = False) -> SpanClassification:
        """Where does [start, end) sit against Waqt-day boundaries?

        BOUNDARY RULE (differs, on purpose, from `semantics.crosses_maghrib`):
        a span crosses Maghrib iff some Maghrib M satisfies
        start < M < end  — strictly inside. A span that merely ENDS at
        Maghrib (M == end) stays in one Waqt day, because the half-open
        span never includes its own end instant; a span that STARTS at
        Maghrib (M == start) lies wholly in the day that Maghrib opens.
        `crosses_maghrib(a, b)` answers a different question — "do two
        INSTANTS belong to different days?" — and rightly says True for
        b == M. Pass `end_inclusive=True` for the instant-pair reading.
        """
        s, e = _utc(start), _utc(end)

        def civil(t):
            return self.ctx.local_civil_date(t).isoformat()

        base = dict(start=s, end=e, end_inclusive=end_inclusive)
        none = dict(same_waqt_day=None, crosses_maghrib=None, maghrib_boundaries=(), waqt_days_touched=None,
                    start_day=None, end_day=None, crosses_civil_midnight=None, start_civil_date=None, end_civil_date=None)

        if e < s or (e == s and not end_inclusive):
            return SpanClassification(Status.NO_VALID_WINDOW, duration_seconds=None,
                                      reason="end is before start" if e < s else "empty half-open span (start == end)",
                                      **none, **base)
        last = e if end_inclusive else e - _ONE_MICRO
        dur = (to_micros(e) - to_micros(s)) / 1e6

        d0 = self.ctx.day_containing(s)
        if not d0.is_defined:
            return SpanClassification(Status.WINDOW_UNDEFINED, duration_seconds=dur,
                                      reason=d0.undefined_reason or f"Waqt day is {d0.status}.", **none, **base)
        d, boundaries = d0, []
        for _ in range(MAX_SPAN_DAYS):
            if d.contains(last):
                break
            boundaries.append(d.close)
            d = self.ctx.neighbor(d, 1)
            if not d.is_defined:
                return SpanClassification(Status.WINDOW_UNDEFINED, duration_seconds=dur,
                                          reason=d.undefined_reason or f"Waqt day is {d.status}.", **none, **base)
        else:
            return SpanClassification(Status.WINDOW_UNDEFINED, duration_seconds=dur,
                                      reason=f"Span exceeds {MAX_SPAN_DAYS} Waqt days.", **none, **base)

        def day_info(day):
            return {"open": _iso(day.open), "close": _iso(day.close), "hijri_label": self.ctx.hijri_label(day)}

        cs, ce = civil(s), civil(last)
        return SpanClassification(
            Status.OK, duration_seconds=dur, same_waqt_day=not boundaries, crosses_maghrib=bool(boundaries),
            maghrib_boundaries=tuple(boundaries), waqt_days_touched=len(boundaries) + 1,
            start_day=day_info(d0), end_day=day_info(d), crosses_civil_midnight=(cs != ce),
            start_civil_date=cs, end_civil_date=ce, **base,
        )

    # -- everything at once ----------------------------------------------------------------

    def snapshot(self, instant: datetime) -> dict:
        """One call answering the standard questions for a moment."""
        t = _utc(instant)
        events = []
        for name in EVENT_NAMES:
            events.append({"name": name, "next": self.until(name, t), "previous": self.since(name, t)})
        return {
            "instant": t,
            "day": self.day_bounds(t),
            "next_event": self.next_event(t),
            "events": events,
        }

    @staticmethod
    def snapshot_to_dict(snap: dict, round_seconds: bool = False) -> dict:
        return {
            "instant": _iso(snap["instant"], round_seconds),
            "day": snap["day"].to_dict(round_seconds),
            "next_event": snap["next_event"].to_dict(round_seconds),
            "events": [
                {"name": e["name"], "next": e["next"].to_dict(round_seconds), "previous": e["previous"].to_dict(round_seconds)}
                for e in snap["events"]
            ],
        }

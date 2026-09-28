"""
waqt.calendar_interop — Sprint 8: the Gregorian/solar calendar as a
formal, secondary interoperability layer.

This module answers exactly the questions the Sprint 8 brief poses,
and no others:

    Gregorian date/time  -> "Which civil-calendar date is this instant?"
    Waqt date/position   -> "Which Waqt day and Waqt position does
                              this instant belong to?"

Those are two representations of the SAME underlying instant, never
two competing definitions of "today". Every function in this module
either (a) takes an instant and renders it in one or more calendars,
or (b) takes a Gregorian civil date and finds the Waqt day it
corresponds to. Nothing here invents a new astronomy result: every
Maghrib boundary, every Hijri label, and every Waqt position is read
directly off `waqt.core.compute_waqt` / `waqt.semantics`, exactly the
way `waqt.institutional` and `waqt.scheduling` already do. Per the
project's standing convention, this is verified by md5sum:
`waqt/core.py`, `waqt/solar.py`, `waqt/semantics.py`, `waqt/hijri.py`,
`waqt/scheduling/`, `waqt/calendar_providers/`, and `waqt/institutional/`
are all byte-for-byte unchanged by Sprint 8.

======================================================================
1. Gregorian calendar semantics (Sprint 8 item 3)
======================================================================
Waqt does not reimplement Gregorian calendar arithmetic — Python's own
`datetime.date`/`datetime.datetime` already provide a correct, widely
trusted implementation, and duplicating it would only create a second
place for a leap-year bug to hide. What Sprint 8 adds is an EXPLICIT,
documented statement of exactly which rules this project relies on,
in `GREGORIAN_CALENDAR_CONTRACT` below, so a caller integrating with
Waqt's calendar layer never has to guess or reverse-engineer it from
behavior.

======================================================================
2. Calendar-neutral instant representation (item 4)
======================================================================
    WaqtInstant (an ordinary UTC datetime, per waqt.semantics §1)
       |
       +-- gregorian_of_instant(instant)            -> UTC civil date/time
       +-- gregorian_of_instant(instant, location)   -> local civil date/time
       +-- represent_instant(instant, location, ...) -> both of the above,
                                                          PLUS the Waqt day
                                                          and position at
                                                          that location

`represent_instant` is the concrete form of the brief's diagram:

    WaqtInstant -> { Hijri (via WaqtDay.hijri_date), Gregorian }

Neither calendar redefines `instant` — every representation is read
off the same immutable UTC datetime. The Hijri date and Maghrib
boundaries are computed exactly once per call, by `core.compute_waqt`,
and both the Gregorian-civil and the Waqt renderings are views over
that one result, not independently re-derived answers that could
silently disagree.

======================================================================
3. Gregorian date + location -> Waqt day (item 1, second half)
======================================================================
`waqt_day_for_gregorian_date` answers "given a Gregorian civil date
and a place, which Waqt day does that label?" — the exact inverse of
what `core.compute_waqt` already does forward (an instant's day is
labelled with the Gregorian date its CLOSING Maghrib falls on; see
`docs/TIME-MODEL.md` and the `declared` provider's "override-date
gotcha" in `docs/CALENDARS.md`, which is this same relationship
stated from the opposite direction). The existing system already
computes this internally every time it brackets Maghrib; this
function is that computation turned into an explicit, standalone,
documented entry point, per the Sprint 8 brief.

======================================================================
4. Civil midnight vs Maghrib: a formal primitive (item 2)
======================================================================
Sprint 6 already recognized these as independent facts inside
`waqt.scheduling.engine.SchedulingContext.classify_span` (see that
module's own docstring). Sprint 8 promotes the SAME boundary rule
into a standalone primitive, `classify_boundary_crossing`, that needs
nothing from `waqt.scheduling` — no SchedulingContext, no day-table,
no rule engine — because "does this span cross civil midnight, or
Maghrib, or both, or neither" is a calendar-interoperability question
in its own right, independent of the scheduling system built on top
of it. It reuses `waqt.semantics.crosses_maghrib` for the Maghrib
half rather than re-deriving it, and follows the exact same half-open
convention `classify_span` documents: a span [start, end) crosses a
boundary B iff start < B < end, strictly inside; a span that merely
STARTS at B lies wholly in the day/date B opens, and a span that
merely ENDS at B never reaches it (the half-open span excludes its
own end instant).

======================================================================
5. API representation (item 5)
======================================================================
See `waqt/api/calendar_convert_endpoint.py` for `GET /v1/calendar/convert`
and `GET /v1/calendar/boundary-crossing`, the HTTP surface built on
top of this module. See `docs/CALENDAR-INTEROP.md` for the prose
contract and `tests/vectors/calendar_interop_vectors.json` for
portable conformance vectors.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from zoneinfo import ZoneInfo

from .core import DEFAULT_PROFILE, AstronomyProfile, Location, _bracket_maghrib, compute_waqt
from .hijri import ArithmeticTabularProvider, HijriDate, HijriProvider, weekday_name
from .semantics import WaqtDay, WaqtUndefinedError, crosses_maghrib, waqt_day_from_result
from .timescale import DEFAULT_TIMESCALE_PROVIDER, TimeScaleProvider
from .timezone_provider import DEFAULT_TIMEZONE_PROVIDER, TimezoneProvider

_ONE_MICRO = timedelta(microseconds=1)

# A calendar provider is required internally by core.compute_waqt even
# for calls that never surface a Hijri date to the caller (e.g. a pure
# Gregorian<->Gregorian or civil-midnight-only question). Using the
# cheapest, dependency-free one avoids paying for umm-al-qura/ephem
# setup for a question that doesn't need it — the same reasoning
# waqt/api/day_endpoint.py already applies.
_DEFAULT_PROVIDER = ArithmeticTabularProvider()


# ---------------------------------------------------------------------------
# 1. Gregorian calendar semantics — item 3
# ---------------------------------------------------------------------------

GREGORIAN_CALENDAR_CONTRACT = {
    "date_representation": (
        "ISO 8601 calendar date (proleptic Gregorian year-month-day). "
        "Waqt applies the Gregorian rule uniformly backward and forward in "
        "time with no discontinuity at the 1582 calendar reform — this is "
        "Python's datetime.date behavior and Waqt makes no separate claim "
        "of historical calendar-reform accuracy before that date."
    ),
    "leap_year_rule": (
        "A year is a leap year iff divisible by 4, except centuries "
        "(divisible by 100), except again if divisible by 400 (the "
        "standard Gregorian rule). See is_leap_year() below."
    ),
    "month_lengths": (
        "Standard Gregorian month lengths: 31,28/29,31,30,31,30,31,31,30,31,30,31. "
        "See days_in_month() below."
    ),
    "weekday": (
        "Two weekday renderings are used, for two different purposes, and "
        "are never confused: (a) waqt.hijri.weekday_name(d), Sunday-first, "
        "Islamic-week names (al-Ahad..as-Sabt) — used everywhere a Waqt-day "
        "label is reported; (b) date.isoweekday(), ISO 8601 Monday=1..Sunday=7 "
        "— used only in GregorianRepresentation.weekday_iso, for a caller "
        "that wants the plain ISO convention."
    ),
    "supported_range": (
        "Python's datetime.date: proleptic Gregorian, 0001-01-01 through "
        "9999-12-31 inclusive (matching ISO 8601's 4-digit-year convention). "
        "waqt.calendar_providers.umm_al_qura has its own narrower range "
        "(roughly 1900-2100) documented separately in docs/CALENDARS.md — "
        "that limit belongs to the astronomical Hijri provider, not to "
        "Gregorian arithmetic itself."
    ),
    "serialization": (
        "Date: YYYY-MM-DD. Instant: YYYY-MM-DDTHH:MM:SS[.ffffff]+00:00, "
        "always UTC with an explicit offset — identical to "
        "waqt.api.common.iso(), so a value from this module and a value "
        "from any other Waqt v1 endpoint are always textually comparable."
    ),
    "implementation": (
        "Delegates entirely to Python's standard library datetime.date / "
        "datetime.datetime rather than reimplementing Gregorian arithmetic, "
        "per the Sprint 8 brief's instruction not to duplicate it "
        "unnecessarily. is_leap_year()/days_in_month() below exist only to "
        "make that reliance an explicit, tested, documented statement "
        "rather than an implicit assumption a caller has to trust blindly."
    ),
}


def is_leap_year(year: int) -> bool:
    """The standard Gregorian rule, stated once, explicitly, rather than
    left implicit in `date`'s own behavior (which this still delegates
    to for every other calculation)."""
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def days_in_month(year: int, month: int) -> int:
    if not 1 <= month <= 12:
        raise ValueError(f"month must be 1-12, got {month}")
    if month == 2:
        return 29 if is_leap_year(year) else 28
    return (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)[month - 1]


# ---------------------------------------------------------------------------
# 2. Calendar-neutral instant representation — item 4
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GregorianRepresentation:
    """The Gregorian civil calendar's answer to "what date/time is this
    instant" — either at UTC (timezone_name=None: the calendar-neutral,
    location-independent rendering) or at a specific place."""

    date: date
    time_of_day: str            # "HH:MM:SS", zero-padded
    weekday_iso: int            # 1=Monday .. 7=Sunday (date.isoweekday())
    weekday_name_islamic: str   # Sunday-first Islamic week name (waqt.hijri.weekday_name)
    is_leap_year: bool
    timezone_name: Optional[str] = None   # None => this is the UTC representation
    utc_offset_seconds: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "date": self.date.isoformat(),
            "time_of_day": self.time_of_day,
            "weekday_iso": self.weekday_iso,
            "weekday_name_islamic": self.weekday_name_islamic,
            "is_leap_year": self.is_leap_year,
            "timezone_name": self.timezone_name,
            "utc_offset_seconds": self.utc_offset_seconds,
        }


def gregorian_of_instant(
    instant: datetime,
    location: Optional[Location] = None,
    tz_provider: TimezoneProvider = DEFAULT_TIMEZONE_PROVIDER,
) -> GregorianRepresentation:
    """The Gregorian civil-calendar date/time of `instant`.

    With no location: the UTC calendar date/time — calendar-neutral,
    identical for every observer on Earth, exactly the representation
    a `HijriProvider.from_gregorian` input already uses.

    With a location: that place's own civil date/time, resolved with
    the SAME `tz_provider` (and hence the SAME civil date) that
    `core.compute_waqt` uses internally to bracket Maghrib — so this
    can never disagree with what `/v1/waqt` reports for the same
    instant and location.
    """
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    instant = instant.astimezone(timezone.utc)

    if location is None:
        d = instant.date()
        return GregorianRepresentation(
            date=d,
            time_of_day=instant.strftime("%H:%M:%S"),
            weekday_iso=d.isoweekday(),
            weekday_name_islamic=weekday_name(d),
            is_leap_year=is_leap_year(d.year),
            timezone_name=None,
            utc_offset_seconds=0,
        )

    tz_name = tz_provider.timezone_name_for(location.lat, location.lon)
    local = instant.astimezone(ZoneInfo(tz_name))
    d = local.date()
    offset = local.utcoffset()
    return GregorianRepresentation(
        date=d,
        time_of_day=local.strftime("%H:%M:%S"),
        weekday_iso=d.isoweekday(),
        weekday_name_islamic=weekday_name(d),
        is_leap_year=is_leap_year(d.year),
        timezone_name=tz_name,
        utc_offset_seconds=int(offset.total_seconds()) if offset is not None else None,
    )


@dataclass(frozen=True)
class InstantRepresentation:
    """One physical instant, rendered in every calendar this layer
    knows about. `gregorian_utc` and (if a location was given)
    `gregorian_civil` and `waqt_day`/`waqt_position_seconds` are all
    views over the SAME `instant` — none of them redefines it."""

    instant: datetime
    gregorian_utc: GregorianRepresentation
    gregorian_civil: Optional[GregorianRepresentation]
    waqt_status: Optional[str]
    waqt_day: Optional[WaqtDay]
    waqt_position_seconds: Optional[float]
    undefined_reason: Optional[str]

    def to_dict(self) -> dict:
        waqt_block = None
        if self.waqt_day is not None and self.waqt_status == "OK":
            waqt_block = {
                "hijri": {
                    "date": self.waqt_day.hijri_date.iso_like(),
                    "display": str(self.waqt_day.hijri_date),
                    "provider": {
                        "name": self.waqt_day.hijri_date.provider,
                        "version": self.waqt_day.hijri_date.version,
                    },
                },
                "weekday": self.waqt_day.weekday,
                "day_open_maghrib": self.waqt_day.open.astimezone(timezone.utc).isoformat(),
                "day_close_maghrib": self.waqt_day.close.astimezone(timezone.utc).isoformat(),
                "position_seconds": round(self.waqt_position_seconds, 3)
                if self.waqt_position_seconds is not None else None,
            }
        return {
            "instant": self.instant.astimezone(timezone.utc).isoformat(),
            "gregorian_utc": self.gregorian_utc.to_dict(),
            "gregorian_civil": self.gregorian_civil.to_dict() if self.gregorian_civil else None,
            "waqt_status": self.waqt_status,
            "waqt": waqt_block,
            "undefined_reason": self.undefined_reason,
        }


def represent_instant(
    instant: datetime,
    location: Optional[Location] = None,
    calendar_provider: Optional[HijriProvider] = None,
    profile: AstronomyProfile = DEFAULT_PROFILE,
    tz_provider: TimezoneProvider = DEFAULT_TIMEZONE_PROVIDER,
    timescale: TimeScaleProvider = DEFAULT_TIMESCALE_PROVIDER,
) -> InstantRepresentation:
    """The calendar-neutral instant representation from the module
    docstring's §2 diagram: one instant, rendered as UTC-Gregorian
    always, and — if `location` is supplied — also as local-civil
    Gregorian AND as a Waqt day/position, all three read off exactly
    one `core.compute_waqt` call."""
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    instant = instant.astimezone(timezone.utc)

    gregorian_utc = gregorian_of_instant(instant, None, tz_provider)

    if location is None:
        return InstantRepresentation(
            instant=instant, gregorian_utc=gregorian_utc, gregorian_civil=None,
            waqt_status=None, waqt_day=None, waqt_position_seconds=None, undefined_reason=None,
        )

    gregorian_civil = gregorian_of_instant(instant, location, tz_provider)
    provider = calendar_provider or _DEFAULT_PROVIDER
    r = compute_waqt(instant, location, provider, profile, tz_provider=tz_provider, timescale=timescale)

    waqt_day = None
    waqt_pos = None
    if r.status == "OK":
        waqt_day = waqt_day_from_result(r)
        waqt_pos = (instant - r.day_start_maghrib).total_seconds()

    return InstantRepresentation(
        instant=instant, gregorian_utc=gregorian_utc, gregorian_civil=gregorian_civil,
        waqt_status=r.status, waqt_day=waqt_day, waqt_position_seconds=waqt_pos,
        undefined_reason=r.undefined_reason,
    )


# ---------------------------------------------------------------------------
# 3. Gregorian date + location -> Waqt day — item 1 (second half)
# ---------------------------------------------------------------------------

class CivilDateUnresolvable(Exception):
    """A Gregorian civil date could not be resolved to exactly one
    Waqt day at a location — either the location has no defined
    Maghrib near that date (polar day/night), or the search could not
    find a Waqt day whose CLOSING Maghrib actually falls on the
    requested civil date within the bounded search this function
    documents. Carries `.reason` for the same structured-error
    posture every other Waqt exception in this project uses."""

    def __init__(self, message: str, reason: Optional[str] = None):
        super().__init__(message)
        self.reason = reason


def waqt_day_for_gregorian_date(
    g: date,
    location: Location,
    calendar_provider: Optional[HijriProvider] = None,
    profile: AstronomyProfile = DEFAULT_PROFILE,
    tz_provider: TimezoneProvider = DEFAULT_TIMEZONE_PROVIDER,
    timescale: TimeScaleProvider = DEFAULT_TIMESCALE_PROVIDER,
) -> WaqtDay:
    """Given a Gregorian CIVIL date at a place, the Waqt day whose
    CLOSING Maghrib falls on that date (see module docstring §3 —
    this is the Hijri-labelling rule `core.compute_waqt` already
    applies, run in reverse).

    APPROXIMATION, STATED EXPLICITLY (the same posture
    `waqt/institutional/binding.py` already takes for the same
    reason): this probes LOCAL NOON, in the location's own real IANA
    timezone (not a fixed UTC noon — an improvement on binding.py's
    approximation, which only probes UTC noon and can be wrong for a
    location many hours of civil offset from UTC). Maghrib never
    falls within a few hours of local noon at any non-polar location,
    so this is safe everywhere Maghrib is actually defined. If the
    noon probe's own Waqt day does not close on `g` (possible only
    under an extreme mismatch between civil offset and solar
    longitude, e.g. a location observing a timezone many hours removed
    from its geography — see docs/TIME-MODEL.md's Kiritimati
    discussion), this function searches the neighbouring days rather
    than silently returning a mismatched one, and raises
    `CivilDateUnresolvable` if none of them match either.
    """
    provider = calendar_provider or _DEFAULT_PROVIDER
    tz_name = tz_provider.timezone_name_for(location.lat, location.lon)
    zone = ZoneInfo(tz_name)

    def probe_day(local_date: date) -> Optional[WaqtDay]:
        local_noon = datetime(local_date.year, local_date.month, local_date.day, 12, 0, 0, tzinfo=zone)
        r = compute_waqt(
            local_noon.astimezone(timezone.utc), location, provider, profile,
            tz_provider=tz_provider, timescale=timescale,
        )
        if r.status != "OK":
            return None
        return waqt_day_from_result(r)

    def close_civil_date(day: WaqtDay) -> date:
        return tz_provider.local_date(day.close, location.lat, location.lon)

    day = probe_day(g)
    if day is not None and close_civil_date(day) == g:
        return day

    # Bounded search of neighbouring civil dates — needed only for the
    # extreme-offset case the docstring names; every location in this
    # project's own test matrix resolves on the first probe above.
    for delta_days in (-1, 1, -2, 2):
        candidate = probe_day(g + timedelta(days=delta_days))
        if candidate is not None and close_civil_date(candidate) == g:
            return candidate

    if day is None:
        raise CivilDateUnresolvable(
            f"No defined Waqt day near {g.isoformat()} local noon at "
            f"({location.lat}, {location.lon}) — likely polar day/night.",
            reason="undefined_near_date",
        )
    raise CivilDateUnresolvable(
        f"Could not find a Waqt day whose closing Maghrib falls on civil "
        f"date {g.isoformat()} at ({location.lat}, {location.lon}); the "
        f"closest probe closed on {close_civil_date(day).isoformat()}.",
        reason="civil_date_mismatch",
    )


# ---------------------------------------------------------------------------
# 4. Civil midnight vs Maghrib — a formal primitive (item 2)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BoundaryCrossing:
    """Whether the half-open span [start, end) crosses civil midnight
    and/or a Maghrib boundary at a location — two INDEPENDENT facts,
    per module docstring §4. `maghrib_boundaries` lists every Maghrib
    strictly inside the span (informational — `crosses_maghrib` itself
    is decided the same way `waqt.semantics.crosses_maghrib` decides
    it, not re-derived from this list)."""

    start: datetime
    end: datetime
    crosses_civil_midnight: bool
    crosses_maghrib: bool
    maghrib_boundaries: tuple
    start_civil_date: date
    end_civil_date: date
    timezone_name: str

    def to_dict(self) -> dict:
        return {
            "start": self.start.astimezone(timezone.utc).isoformat(),
            "end": self.end.astimezone(timezone.utc).isoformat(),
            "crosses_civil_midnight": self.crosses_civil_midnight,
            "crosses_maghrib": self.crosses_maghrib,
            "maghrib_boundaries": [m.astimezone(timezone.utc).isoformat() for m in self.maghrib_boundaries],
            "start_civil_date": self.start_civil_date.isoformat(),
            "end_civil_date": self.end_civil_date.isoformat(),
            "timezone": self.timezone_name,
        }


def classify_boundary_crossing(
    start: datetime,
    end: datetime,
    location: Location,
    calendar_provider: Optional[HijriProvider] = None,
    tz_provider: TimezoneProvider = DEFAULT_TIMEZONE_PROVIDER,
    timescale: TimeScaleProvider = DEFAULT_TIMESCALE_PROVIDER,
) -> BoundaryCrossing:
    """Classify the half-open span [start, end) against civil midnight
    and Maghrib, independently. Boundary rule (see module docstring
    §4): a boundary B is crossed iff start < B < end, strictly inside
    — a span that starts exactly at B stays in the day/date B opens; a
    span that ends exactly at B never reaches it (the half-open span
    excludes its own end instant). Raises ValueError if end <= start.
    """
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    start = start.astimezone(timezone.utc)
    end = end.astimezone(timezone.utc)
    if end <= start:
        raise ValueError("end must be strictly after start (a half-open span cannot be empty or reversed)")

    provider = calendar_provider or _DEFAULT_PROVIDER
    tz_name = tz_provider.timezone_name_for(location.lat, location.lon)

    start_civil = tz_provider.local_date(start, location.lat, location.lon)
    last = end - _ONE_MICRO  # the span's own last included instant (half-open exclusion of `end`)
    end_civil = tz_provider.local_date(last, location.lat, location.lon)

    try:
        crosses_mag = crosses_maghrib(start, last, location.lat, location.lon,
                                       elevation_m=location.elevation_m, tz_provider=tz_provider,
                                       timescale=timescale)
    except WaqtUndefinedError as exc:
        raise CivilDateUnresolvable(str(exc), reason="undefined_boundary") from exc

    # Maghrib boundaries strictly inside the span, listed for display —
    # walked with core._bracket_maghrib directly, the same primitive
    # waqt.semantics.crosses_maghrib itself is built on, so this can
    # never disagree with the boolean above.
    boundaries: list[datetime] = []
    probe = start
    seen: set = set()
    for _ in range(400):  # matches waqt.scheduling.engine.MAX_SPAN_DAYS's own bound
        _, _, _, m_close, _ = _bracket_maghrib(probe, location, tz_provider, timescale)
        if m_close is None or m_close >= end:
            break
        if m_close > start and m_close not in seen:
            boundaries.append(m_close)
            seen.add(m_close)
        probe = m_close

    return BoundaryCrossing(
        start=start, end=end,
        crosses_civil_midnight=(start_civil != end_civil),
        crosses_maghrib=crosses_mag,
        maghrib_boundaries=tuple(boundaries),
        start_civil_date=start_civil, end_civil_date=end_civil,
        timezone_name=tz_name,
    )

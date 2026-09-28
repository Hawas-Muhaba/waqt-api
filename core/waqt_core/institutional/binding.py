"""
waqt.institutional.binding — connects a resolved calendar rule (a
Gregorian civil date, via `waqt.institutional.rules`) to the actual
`WaqtDay` it labels, at a real location.

This is the one place Sprint 7 touches `SchedulingContext` for
fiscal/academic-year purposes, and it is entirely optional: everything
in `rules.py`, `fiscal_year.py` and `academic_year.py` works from the
Hijri calendar alone, with no location. Binding matters when a caller
actually wants "the fiscal year starts at Maghrib on 1 Muharram" as a
real instant they can schedule against — the brief's own framing
("the Hijri provider determines the actual date; the fiscal-calendar
layer determines the institutional structure") is implemented exactly
that way: this module adds nothing new to *which* date is correct,
only *when, at this place*, that date's Waqt day begins and ends.

Finding the WaqtDay for a Gregorian date `g` uses local noon (UTC) as
a probe instant — safely inside `[Maghrib(g-1), Maghrib(g))` for every
non-polar location and every timezone offset up to +/-12h, since
Maghrib never falls before local dawn or after local midnight. This is
a deliberate approximation, not a general "instant for date g" solver;
see the Sprint 7 report's honest-limitations section for the (rare,
high-offset) case it does not cover.
"""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import NamedTuple, Optional

from ..hijri import HijriDate, HijriProvider
from ..scheduling.context import SchedulingContext
from ..semantics import WaqtDay
from .rules import CalendarRule, RuleError, resolve_rule


def waqt_day_for_gregorian_date(ctx: SchedulingContext, g: date) -> WaqtDay:
    """The WaqtDay whose *closing* Maghrib falls on Gregorian date `g`
    — i.e. the day `g` labels, per Core Time Model Sec 2's join rule."""
    probe = datetime.combine(g, time(12, 0), tzinfo=timezone.utc)
    return ctx.day_containing(probe)


class ResolvedPeriod(NamedTuple):
    """A start_rule/end_rule pair, resolved for one Hijri year: the
    calendar facts (always present) plus, if a location was supplied,
    the real Maghrib-anchored Waqt-day boundaries. Shared by
    `fiscal_year.py` and `academic_year.py` so the two never disagree
    about what "resolve a period" means."""

    start_hijri: HijriDate
    end_hijri: HijriDate
    start_gregorian: date
    end_gregorian: date
    waqt_start_open: Optional[datetime]
    waqt_end_close: Optional[datetime]


def resolve_period(
    start_rule: CalendarRule,
    end_rule: CalendarRule,
    year: int,
    provider: HijriProvider,
    ctx: Optional[SchedulingContext] = None,
    label: str = "period",
    end_year: Optional[int] = None,
) -> ResolvedPeriod:
    """Resolve `start_rule` against `year` and `end_rule` against
    `end_year` (defaulting to `year` — the common case, e.g. "1
    Muharram Y" to "end of Dhu al-Hijjah Y"), and optionally bind both
    ends to real WaqtDays at `ctx`'s location."""
    start_hd = resolve_rule(start_rule, year, provider)
    end_hd = resolve_rule(end_rule, year if end_year is None else end_year, provider)
    start_g = provider.to_gregorian(start_hd.year, start_hd.month, start_hd.day)
    end_g = provider.to_gregorian(end_hd.year, end_hd.month, end_hd.day)
    if end_g < start_g:
        raise RuleError(f"{label} {year}: resolved end ({end_hd}) precedes resolved start ({start_hd})")
    waqt_start_open = waqt_end_close = None
    if ctx is not None:
        start_day = waqt_day_for_gregorian_date(ctx, start_g)
        end_day = waqt_day_for_gregorian_date(ctx, end_g)
        if not (start_day.is_defined and end_day.is_defined):
            raise RuleError(f"{label} {year}: a boundary falls on an undefined Waqt day at this location")
        waqt_start_open, waqt_end_close = start_day.open, end_day.close
    return ResolvedPeriod(start_hd, end_hd, start_g, end_g, waqt_start_open, waqt_end_close)

"""
waqt.institutional.week — Islamic week semantics (Sprint 7).

ANSWERING THE BRIEF'S QUESTIONS DIRECTLY
-----------------------------------------
**What is a week?** Seven consecutive `WaqtDay`s. Nothing more — a
week never has a gap or an overlap, because it is built entirely out
of `SchedulingContext.neighbor()` stepping (Sprint 6), which already
guarantees adjacent days tile the timeline exactly
(`test_days_tile_the_timeline`). Sprint 7 adds no new day-stepping
logic; it only groups seven already-correct steps and gives the group
a name.

**What is its first day?** Not a Waqt fact — an institutional choice,
captured in `WeekDefinition.first_day`. The default, `"al-Ahad"`
(Sunday), matches the civil-week convention most widely used in
Muslim-majority countries, but nothing here privileges it: a Monday-
first `WeekDefinition` is exactly as valid and exercised in tests.

**How does it relate to Maghrib-based Waqt dates?** Every one of the
seven days IS a Waqt day — `[Maghrib(D), Maghrib(D+1))` — labeled with
the Islamic weekday name `waqt.hijri.weekday_name` already computes
from that day's *closing* Gregorian date. A week is just seven such
labels in a row.

**How is Jumu'ah represented?** As one named slot in the week
(`WeekDefinition.jumuah_day`, default `"al-Jumuah"`), resolved via
`WeekView.jumuah`. That WaqtDay's `open` (its opening Maghrib) is —
provably, not just by convention — the same instant as the *closing*
Maghrib of the WaqtDay labeled `al-Khamis` immediately before it,
because consecutive Waqt days already tile with no gap (Sprint 6).
Concretely: the WaqtDay labeled "al-Jumuah" is the one whose *closing*
Gregorian date is a Friday, so its *opening* Maghrib is the previous
evening's Maghrib — Thursday evening. This was already true of
`core.compute_waqt` since Sprint 1; Sprint 7 states it as an explicit,
tested contract (`test_jumuah_begins_thursday_evening_maghrib`) rather
than an implicit consequence nobody had written down.

**How are week boundaries determined?** The week's start is the
opening Maghrib of the WaqtDay labeled `first_day`; the week's end is
the closing Maghrib of the WaqtDay labeled the day immediately before
`first_day` in week order (i.e. exactly seven WaqtDays later) — so
weeks tile the timeline the same way days do, for the same structural
reason.

**Is the week an intrinsic Waqt property or a derived calendar
convention?** Derived. The only intrinsic fact Waqt Core contributes
is the single per-day weekday label (Sec 2's Gregorian-civil-date
join, already implemented, unchanged). Grouping seven labeled days
into a "week" and choosing which one starts it is exactly the kind of
institutional convention Sprint 7's architecture note asks to be kept
out of `waqt/core.py` — and it is: this module imports `WaqtDay`
read-only and adds no new astronomy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from ..hijri import weekday_name
from ..scheduling.context import SchedulingContext
from ..semantics import WaqtDay
from .rules import ISLAMIC_WEEKDAY_NAMES, RuleError, _require_weekday


@dataclass(frozen=True)
class WeekDefinition:
    """The institutional convention that turns seven labeled WaqtDays
    into a "week". Pure configuration — see module docstring."""

    first_day: str = "al-Ahad"
    jumuah_day: str = "al-Jumuah"
    label: str = "default"

    def __post_init__(self) -> None:
        _require_weekday(self.first_day)
        _require_weekday(self.jumuah_day)

    def index(self, weekday: str) -> int:
        _require_weekday(weekday)
        return ISLAMIC_WEEKDAY_NAMES.index(weekday)

    def offset_from_start(self, weekday: str) -> int:
        """0..6: how many days after `first_day` this weekday falls."""
        return (self.index(weekday) - self.index(self.first_day)) % 7

    def ordered_days(self) -> tuple[str, ...]:
        """The seven weekday names, starting at `first_day`."""
        start = self.index(self.first_day)
        return tuple(ISLAMIC_WEEKDAY_NAMES[(start + k) % 7] for k in range(7))

    def to_dict(self) -> dict:
        return {"first_day": self.first_day, "jumuah_day": self.jumuah_day, "label": self.label}


DEFAULT_WEEK = WeekDefinition()


# ---------------------------------------------------------------------------
# Pure, location-independent week arithmetic on Gregorian civil dates
# (the same "one global label per Gregorian date" independence
# `waqt.hijri.weekday_name` already has — see that module's note).
# ---------------------------------------------------------------------------


def week_start_date(d: date, defn: WeekDefinition = DEFAULT_WEEK) -> date:
    """The Gregorian date labeling the WaqtDay that opens the week
    containing `d` — i.e. the most recent date on or before `d` whose
    weekday is `defn.first_day`."""
    back = defn.offset_from_start(weekday_name(d))
    return d - timedelta(days=back)


def week_dates(d: date, defn: WeekDefinition = DEFAULT_WEEK) -> list[date]:
    """The seven Gregorian dates (each a WaqtDay's closing date) making
    up the week containing `d`, in week order starting at `first_day`."""
    start = week_start_date(d, defn)
    return [start + timedelta(days=k) for k in range(7)]


# ---------------------------------------------------------------------------
# Location-bound week: real WaqtDays, real Maghrib instants.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WeekView:
    """Seven consecutive WaqtDays, in week order starting at
    `definition.first_day`. `days[0].open` is the week's start Maghrib;
    `days[-1].close` is the week's end Maghrib (== next week's start)."""

    definition: WeekDefinition
    days: tuple[WaqtDay, ...]  # length 7, week order

    def __post_init__(self) -> None:
        if len(self.days) != 7:
            raise RuleError("a WeekView must have exactly 7 days")

    def day(self, weekday: str) -> WaqtDay:
        _require_weekday(weekday)
        return self.days[self.definition.offset_from_start(weekday)]

    @property
    def jumuah(self) -> WaqtDay:
        return self.day(self.definition.jumuah_day)

    @property
    def open(self) -> "datetime | None":
        return self.days[0].open

    @property
    def close(self) -> "datetime | None":
        return self.days[-1].close

    def to_dict(self, ctx: SchedulingContext) -> dict:
        from datetime import timezone

        from ..scheduling.context import day_to_table_entry

        def iso(dt):
            return dt.astimezone(timezone.utc).isoformat() if dt is not None else None

        return {
            "definition": self.definition.to_dict(),
            "week_start": iso(self.open),
            "week_end": iso(self.close),
            "jumuah_index": self.definition.offset_from_start(self.definition.jumuah_day),
            "days": [
                {"weekday": wd, **day_to_table_entry(day, ctx)}
                for wd, day in zip(self.definition.ordered_days(), self.days)
            ],
        }


def week_containing(ctx: SchedulingContext, instant: datetime, defn: WeekDefinition = DEFAULT_WEEK) -> WeekView:
    """The WeekView (seven tiled WaqtDays) containing `instant`, at
    `ctx`'s location, under week convention `defn`. Never recomputes
    astronomy: every day comes from `SchedulingContext.day_containing` /
    `.neighbor`, exactly Sprint 6's stepping."""
    anchor_day = ctx.day_containing(instant)
    if not anchor_day.is_defined:
        raise RuleError(anchor_day.undefined_reason or "cannot build a week around an undefined Waqt day")
    back = defn.offset_from_start(anchor_day.weekday)
    start_day = ctx.neighbor(anchor_day, -back) if back else anchor_day
    days = [start_day]
    for _ in range(6):
        days.append(ctx.neighbor(days[-1], 1))
    return WeekView(definition=defn, days=tuple(days))

"""
waqt.institutional — Sprint 7: Institutional Islamic Calendar Semantics.

    Waqt Core
      -> astronomical events
      -> Waqt dates
      -> temporal semantics
      -> scheduling primitives      (waqt.scheduling, Sprint 6)
    Institutional calendar layer     (this package, Sprint 7)
      -> week
      -> fiscal year
      -> academic year
      -> terms
      -> institutional periods

This package sits entirely ABOVE `waqt.core`, `waqt.solar`,
`waqt.semantics`, and `waqt.scheduling` — it imports from them
read-only and changes none of them (md5-verified in
`tests/test_institutional.py`, the same discipline every sprint since
Sprint 3 has kept). It adds no new astronomy: the calendar arithmetic
in `rules.py` / `week.py` / `fiscal_year.py` / `academic_year.py` works
from a `HijriProvider` alone; the optional binding to real Maghrib
instants at a location (`binding.py`) reuses `waqt.scheduling`'s
already-proven day-stepping rather than recomputing anything.

See docs/INSTITUTIONAL.md for the full specification.
"""

from .academic_year import (
    AcademicCalendar,
    AcademicYear,
    HolidayDefinition,
    HolidayInstance,
    TermDefinition,
    TermPeriod,
    default_islamic_academic_calendar,
    sample_two_term_academic_calendar,
)
from .binding import ResolvedPeriod, resolve_period, waqt_day_for_gregorian_date
from .fiscal_year import FiscalCalendar, FiscalYear, default_islamic_fiscal_calendar
from .profile import CalendarProfile, default_profile, profile_from_dict
from .rules import (
    ISLAMIC_WEEKDAY_NAMES,
    CalendarRule,
    MonthDay,
    MonthEnd,
    NthWeekdayOfMonth,
    RuleError,
    month_days,
    resolve_rule,
    rule_from_dict,
)
from .week import DEFAULT_WEEK, WeekDefinition, WeekView, week_containing, week_dates, week_start_date

__all__ = [
    "AcademicCalendar", "AcademicYear", "HolidayDefinition", "HolidayInstance",
    "TermDefinition", "TermPeriod", "default_islamic_academic_calendar", "sample_two_term_academic_calendar",
    "ResolvedPeriod", "resolve_period", "waqt_day_for_gregorian_date",
    "FiscalCalendar", "FiscalYear", "default_islamic_fiscal_calendar",
    "CalendarProfile", "default_profile", "profile_from_dict",
    "ISLAMIC_WEEKDAY_NAMES", "CalendarRule", "MonthDay", "MonthEnd", "NthWeekdayOfMonth",
    "RuleError", "month_days", "resolve_rule", "rule_from_dict",
    "DEFAULT_WEEK", "WeekDefinition", "WeekView", "week_containing", "week_dates", "week_start_date",
]

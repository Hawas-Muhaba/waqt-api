"""
waqt.institutional.academic_year — configurable Islamic school/academic
calendar (Sprint 7).

Per the brief: define a school-year abstraction —

    AcademicCalendar:
        opening_rule
        closing_rule
        term_rules
        holidays

— "but don't try to define one universal Muslim school calendar.
Different institutions and countries can adopt different structures."
So this module ships the *shape* (opening/closing/terms/holidays, all
built from the same `CalendarRule` primitives `fiscal_year.py` uses)
and exactly one worked, clearly-labeled example
(`SAMPLE_TWO_TERM_ACADEMIC_CALENDAR`, used only in tests and docs) —
never a default an institution is implicitly nudged toward adopting.

The brief's own example, `First Ahad of Muharram -> Last Khamis of
Sha'ban`, resolves within a SINGLE Hijri year (Sha'ban is month 8,
Muharram is month 1 of the same year) — an academic year of roughly
eight lunar months, leaving Ramadan through Dhu al-Hijjah (months 9-12,
the Hajj season) outside it. That is a structural consequence of the
months' own ordering, not an assumption this module adds.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional

from ..hijri import HijriDate, HijriProvider
from ..scheduling.context import SchedulingContext
from .binding import resolve_period
from .rules import CalendarRule, MonthDay, NthWeekdayOfMonth, RuleError


def _iso_dt(dt: Optional[datetime]) -> Optional[str]:
    return dt.astimezone(timezone.utc).isoformat() if dt is not None else None


@dataclass(frozen=True)
class TermDefinition:
    label: str
    start_rule: CalendarRule
    end_rule: CalendarRule
    year_offset: int = 0  # resolved against the academic year's hijri_year + offset (see AcademicCalendar.year)


@dataclass(frozen=True)
class HolidayDefinition:
    label: str
    rule: CalendarRule
    year_offset: int = 0


@dataclass(frozen=True)
class TermPeriod:
    label: str
    start_hijri: HijriDate
    end_hijri: HijriDate
    start_gregorian: date
    end_gregorian: date
    waqt_start_open: Optional[datetime] = None
    waqt_end_close: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "start": {"hijri": self.start_hijri.iso_like(), "gregorian": self.start_gregorian.isoformat()},
            "end": {"hijri": self.end_hijri.iso_like(), "gregorian": self.end_gregorian.isoformat()},
            "waqt_bounds": {"start_open": _iso_dt(self.waqt_start_open), "end_close": _iso_dt(self.waqt_end_close)}
            if self.waqt_start_open is not None else None,
        }


@dataclass(frozen=True)
class HolidayInstance:
    label: str
    hijri: HijriDate
    gregorian: date
    waqt_open: Optional[datetime] = None
    waqt_close: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "hijri": self.hijri.iso_like(),
            "gregorian": self.gregorian.isoformat(),
            "waqt_bounds": {"open": _iso_dt(self.waqt_open), "close": _iso_dt(self.waqt_close)}
            if self.waqt_open is not None else None,
        }


@dataclass(frozen=True)
class AcademicYear:
    hijri_year: int
    label: str
    opening_hijri: HijriDate
    closing_hijri: HijriDate
    opening_gregorian: date
    closing_gregorian: date
    waqt_open: Optional[datetime]
    waqt_close: Optional[datetime]
    terms: tuple[TermPeriod, ...]
    holidays: tuple[HolidayInstance, ...]

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "hijri_year": self.hijri_year,
            "opening": {"hijri": self.opening_hijri.iso_like(), "gregorian": self.opening_gregorian.isoformat()},
            "closing": {"hijri": self.closing_hijri.iso_like(), "gregorian": self.closing_gregorian.isoformat()},
            "waqt_bounds": {"open": _iso_dt(self.waqt_open), "close": _iso_dt(self.waqt_close)}
            if self.waqt_open is not None else None,
            "terms": [t.to_dict() for t in self.terms],
            "holidays": [h.to_dict() for h in self.holidays],
        }


@dataclass(frozen=True)
class AcademicCalendar:
    opening_rule: CalendarRule
    closing_rule: CalendarRule
    term_rules: tuple[TermDefinition, ...] = ()
    holidays: tuple[HolidayDefinition, ...] = ()
    label: str = "Academic Year"
    calendar_provider: Optional[HijriProvider] = None

    def year(self, hijri_year: int, provider: Optional[HijriProvider] = None,
              ctx: Optional[SchedulingContext] = None) -> AcademicYear:
        p = provider or self.calendar_provider
        if p is None:
            raise RuleError("AcademicCalendar.year() needs a calendar_provider (on the calendar or passed here)")

        rp = resolve_period(self.opening_rule, self.closing_rule, hijri_year, p, ctx, label=self.label)

        terms = []
        for t in self.term_rules:
            y = hijri_year + t.year_offset
            trp = resolve_period(t.start_rule, t.end_rule, y, p, ctx, label=f"{self.label}/{t.label}")
            terms.append(TermPeriod(
                label=t.label, start_hijri=trp.start_hijri, end_hijri=trp.end_hijri,
                start_gregorian=trp.start_gregorian, end_gregorian=trp.end_gregorian,
                waqt_start_open=trp.waqt_start_open, waqt_end_close=trp.waqt_end_close,
            ))

        holidays = []
        for h in self.holidays:
            y = hijri_year + h.year_offset
            from .rules import resolve_rule
            hd = resolve_rule(h.rule, y, p)
            g = p.to_gregorian(hd.year, hd.month, hd.day)
            waqt_open = waqt_close = None
            if ctx is not None:
                from .binding import waqt_day_for_gregorian_date
                day = waqt_day_for_gregorian_date(ctx, g)
                if day.is_defined:
                    waqt_open, waqt_close = day.open, day.close
            holidays.append(HolidayInstance(label=h.label, hijri=hd, gregorian=g, waqt_open=waqt_open, waqt_close=waqt_close))

        return AcademicYear(
            hijri_year=hijri_year, label=self.label,
            opening_hijri=rp.start_hijri, closing_hijri=rp.end_hijri,
            opening_gregorian=rp.start_gregorian, closing_gregorian=rp.end_gregorian,
            waqt_open=rp.waqt_start_open, waqt_close=rp.waqt_end_close,
            terms=tuple(terms), holidays=tuple(holidays),
        )

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "opening_rule": self.opening_rule.to_dict(),
            "closing_rule": self.closing_rule.to_dict(),
            "term_rules": [{"label": t.label, "start_rule": t.start_rule.to_dict(), "end_rule": t.end_rule.to_dict(),
                             "year_offset": t.year_offset} for t in self.term_rules],
            "holidays": [{"label": h.label, "rule": h.rule.to_dict(), "year_offset": h.year_offset} for h in self.holidays],
        }


def default_islamic_academic_calendar(calendar_provider: Optional[HijriProvider] = None) -> AcademicCalendar:
    """The brief's own worked example: opening = first Ahad of
    Muharram, closing = last Khamis of Sha'ban. No terms or holidays —
    an institution supplies those (see module docstring)."""
    return AcademicCalendar(
        opening_rule=NthWeekdayOfMonth(weekday="al-Ahad", n=1, month=1),
        closing_rule=NthWeekdayOfMonth(weekday="al-Khamis", n=-1, month=8),
        label="Islamic Academic Year (first Ahad of Muharram -> last Khamis of Sha'ban)",
        calendar_provider=calendar_provider,
    )


# ---------------------------------------------------------------------------
# ONE worked, explicitly-labeled example of term_rules/holidays — used in
# tests/docs to demonstrate the shape. NOT imported by anything else in
# this package, and not a claim about how any real institution's calendar
# should look (see module docstring).
# ---------------------------------------------------------------------------

SAMPLE_TWO_TERM_ACADEMIC_CALENDAR_LABEL = "Sample: two-term academic year (illustrative only, not a default)"


def sample_two_term_academic_calendar(calendar_provider: Optional[HijriProvider] = None) -> AcademicCalendar:
    return AcademicCalendar(
        opening_rule=NthWeekdayOfMonth(weekday="al-Ahad", n=1, month=1),
        closing_rule=NthWeekdayOfMonth(weekday="al-Khamis", n=-1, month=8),
        term_rules=(
            TermDefinition("Term 1", NthWeekdayOfMonth("al-Ahad", 1, 1), MonthDay(month=3, day=29)),
            TermDefinition("Term 2", MonthDay(month=4, day=1), NthWeekdayOfMonth("al-Khamis", -1, 8)),
        ),
        holidays=(),
        label=SAMPLE_TWO_TERM_ACADEMIC_CALENDAR_LABEL,
        calendar_provider=calendar_provider,
    )

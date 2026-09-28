"""
waqt.institutional.fiscal_year — configurable Islamic fiscal-year
structure (Sprint 7).

Per the brief: "create a generic fiscal-year abstraction... but don't
hard-code that as the only possible institutional calendar. A
provider/configuration should be able to define the start rule." So:

    FiscalCalendar:
        start_rule           # a waqt.institutional.rules CalendarRule
        end_rule              # a CalendarRule
        label
        calendar_provider     # a HijriProvider

`DEFAULT_ISLAMIC_FISCAL_CALENDAR` below IS the brief's example —
`start = 1 Muharram`, `end = end of Dhu al-Hijjah` — expressed as
`MonthDay(month=1, day=1)` / `MonthEnd(month=12)`. It is offered as a
ready default, not as the only legitimate shape: any institution can
build `FiscalCalendar(start_rule=..., end_rule=..., ...)` with its own
rules (e.g. a fiscal year starting on the first Ahad of Muharram, or
ending mid-Shawwal) and get the exact same guarantees.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from ..hijri import HijriDate, HijriProvider
from ..scheduling.context import SchedulingContext
from .binding import resolve_period
from .rules import CalendarRule, MonthDay, MonthEnd, RuleError


@dataclass(frozen=True)
class FiscalYear:
    """One resolved fiscal year: the calendar facts (always available,
    no location needed) plus, optionally, the real Waqt-day boundaries
    at a location (only if a SchedulingContext was supplied)."""

    hijri_year: int
    label: str
    start_hijri: HijriDate
    end_hijri: HijriDate
    start_gregorian: "datetime.date"
    end_gregorian: "datetime.date"
    waqt_start_open: Optional[datetime] = None   # opening Maghrib of the fiscal year, if bound to a location
    waqt_end_close: Optional[datetime] = None    # closing Maghrib of the fiscal year (exclusive), if bound

    def to_dict(self) -> dict:
        def iso_dt(dt):
            return dt.astimezone(timezone.utc).isoformat() if dt is not None else None

        return {
            "label": self.label,
            "hijri_year": self.hijri_year,
            "start": {"hijri": self.start_hijri.iso_like(), "gregorian": self.start_gregorian.isoformat()},
            "end": {"hijri": self.end_hijri.iso_like(), "gregorian": self.end_gregorian.isoformat()},
            "waqt_bounds": {
                "start_open": iso_dt(self.waqt_start_open),
                "end_close": iso_dt(self.waqt_end_close),
            } if self.waqt_start_open is not None else None,
        }


@dataclass(frozen=True)
class FiscalCalendar:
    start_rule: CalendarRule
    end_rule: CalendarRule
    label: str = "Fiscal Year"
    calendar_provider: Optional[HijriProvider] = None  # if None, caller must pass one to .year()

    def year(self, hijri_year: int, provider: Optional[HijriProvider] = None,
              ctx: Optional[SchedulingContext] = None) -> FiscalYear:
        """Resolve fiscal year `hijri_year` (the Hijri year the START
        rule falls in — the END rule is resolved in the SAME Hijri year,
        matching the brief's own example where Muharram and Dhu al-Hijjah
        of one year bracket that year's fiscal period).

        If `ctx` (a SchedulingContext, i.e. a location) is supplied, the
        result also carries real Maghrib-anchored Waqt-day boundaries —
        see module docstring and `waqt.institutional.binding`.
        """
        p = provider or self.calendar_provider
        if p is None:
            raise RuleError("FiscalCalendar.year() needs a calendar_provider (on the calendar or passed here)")
        rp = resolve_period(self.start_rule, self.end_rule, hijri_year, p, ctx, label=self.label)
        return FiscalYear(
            hijri_year=hijri_year, label=self.label,
            start_hijri=rp.start_hijri, end_hijri=rp.end_hijri,
            start_gregorian=rp.start_gregorian, end_gregorian=rp.end_gregorian,
            waqt_start_open=rp.waqt_start_open, waqt_end_close=rp.waqt_end_close,
        )

    def to_dict(self) -> dict:
        return {"label": self.label, "start_rule": self.start_rule.to_dict(), "end_rule": self.end_rule.to_dict()}


def default_islamic_fiscal_calendar(calendar_provider: Optional[HijriProvider] = None) -> FiscalCalendar:
    """The brief's own worked example: `start = 1 Muharram`,
    `end = end of Dhu al-Hijjah` — offered as a convenience, not a
    universal default any code here assumes."""
    return FiscalCalendar(
        start_rule=MonthDay(month=1, day=1),
        end_rule=MonthEnd(month=12),
        label="Islamic Fiscal Year (Muharram 1 -> end of Dhu al-Hijjah)",
        calendar_provider=calendar_provider,
    )

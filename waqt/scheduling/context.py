"""
waqt.scheduling.context — where scheduling meets the existing engine.

A SchedulingContext bundles everything `core.compute_waqt` needs
(location, astronomy profile, calendar provider, timezone/timescale
providers) and answers exactly two questions, both by calling
compute_waqt and never by recomputing astronomy:

    day_containing(instant) -> WaqtDay
    neighbor(day, k)        -> WaqtDay   (k days later/earlier)

CALENDAR INDEPENDENCE
---------------------
The calendar provider is passed through to compute_waqt only because
compute_waqt attaches a Hijri label to every WaqtDay. Nothing in
waqt.scheduling ever reads that label to decide anything: not a
boundary, not an event, not a window. `hijri_label` below is exposed
purely so a UI can print it. tests/test_scheduling.py proves the
consequence: swapping arithmetic-tabular / umm-al-qura / a shifted
custom provider changes labels and changes no resolved instant.

`neighbor()` steps by instants, not by dates: the next day is the day
containing this day's closing Maghrib; the previous is the day
containing one microsecond before the opening Maghrib. That is the
half-open Waqt-day rule from Sprint 5 used as a stepping function, so
adjacent days tile the timeline with no gap and no overlap
(tests: test_days_tile_the_timeline).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from ..core import DEFAULT_PROFILE, AstronomyProfile, Location, compute_waqt
from ..hijri import ArithmeticTabularProvider, HijriProvider
from ..semantics import WaqtDay, WaqtUndefinedError, waqt_day_from_result
from ..timescale import DEFAULT_TIMESCALE_PROVIDER, TimeScaleProvider
from ..timezone_provider import DEFAULT_TIMEZONE_PROVIDER, TimezoneProvider
from .model import EVENT_NAMES

_ONE_MICRO = timedelta(microseconds=1)


class DayUnavailable(Exception):
    """Internal: stepping from a Waqt day that has no boundaries."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class SchedulingContext:
    def __init__(
        self,
        location: Location,
        profile: AstronomyProfile = DEFAULT_PROFILE,
        calendar_provider: Optional[HijriProvider] = None,
        tz_provider: TimezoneProvider = DEFAULT_TIMEZONE_PROVIDER,
        timescale: TimeScaleProvider = DEFAULT_TIMESCALE_PROVIDER,
    ):
        self.location = location
        self.profile = profile
        self.calendar_provider = calendar_provider or ArithmeticTabularProvider()
        self.tz_provider = tz_provider
        self.timescale = timescale
        self._days: list[WaqtDay] = []          # defined days, for containment lookup
        self._by_instant: dict[datetime, WaqtDay] = {}

    # -- days ---------------------------------------------------------------

    def day_containing(self, instant: datetime) -> WaqtDay:
        instant = instant.astimezone(timezone.utc)
        for d in self._days:
            if d.open <= instant < d.close:
                return d
        cached = self._by_instant.get(instant)
        if cached is not None:
            return cached
        r = compute_waqt(
            instant, self.location, self.calendar_provider, self.profile,
            tz_provider=self.tz_provider, timescale=self.timescale,
        )
        day = waqt_day_from_result(r)
        if day.is_defined:
            self._days.append(day)
        else:
            self._by_instant[instant] = day
        return day

    def neighbor(self, day: WaqtDay, k: int) -> WaqtDay:
        """The Waqt day `k` days after (k>0) or before (k<0) `day`.
        Stepping through an UNDEFINED day is impossible (it has no
        boundary to step from) and raises DayUnavailable; arriving AT an
        undefined day is fine and returns it (the caller inspects it)."""
        cur = day
        step = 1 if k > 0 else -1
        for _ in range(abs(k)):
            if not cur.is_defined:
                raise DayUnavailable(
                    cur.undefined_reason or f"Waqt day is {cur.status}; cannot step across it."
                )
            probe = cur.close if step > 0 else cur.open - _ONE_MICRO
            cur = self.day_containing(probe)
        return cur

    # -- presentation-only helpers -------------------------------------------

    def hijri_label(self, day: WaqtDay) -> Optional[str]:
        """Display label only. Never an input to any scheduling result."""
        return day.hijri_date.iso_like() if day.hijri_date is not None else None

    def local_civil_date(self, instant: datetime):
        return self.tz_provider.local_date(instant, self.location.lat, self.location.lon)

    def known_days(self) -> list[WaqtDay]:
        return sorted(self._days, key=lambda d: d.open)


# ---------------------------------------------------------------------------
# Day-table serialization: the interface between the astronomy engine and
# independent implementations. A day table is "what the solar engine
# said, frozen as data" — an implementation that can read it can resolve
# every scheduling rule without knowing a single astronomical formula.
# ---------------------------------------------------------------------------


def day_to_table_entry(day: WaqtDay, ctx: SchedulingContext, precise: bool = True) -> dict:
    def iso(dt):
        return dt.astimezone(timezone.utc).isoformat() if dt is not None else None

    if not day.is_defined:
        return {"status": day.status, "open": None, "close": None, "events": None, "hijri_label": None,
                "undefined_reason": day.undefined_reason}
    events = {}
    for name in EVENT_NAMES:
        try:
            events[name] = iso(day.event(name).instant)
        except WaqtUndefinedError:
            events[name] = None
    return {
        "status": "OK",
        "open": iso(day.open),
        "close": iso(day.close),
        "events": events,
        "hijri_label": ctx.hijri_label(day),
        "undefined_reason": None,
    }

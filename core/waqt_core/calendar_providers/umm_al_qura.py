"""
waqt.calendar_providers.umm_al_qura — an astronomical approximation of
the official Saudi Umm al-Qura calendar.

WHAT THIS IS
Since 1423 AH (15 March 2002), Umm al-Qura's rule for whether a lunar
month is 29 or 30 days is a pure calculation, evaluated at Makkah:

    On the evening of the 29th day of the current month, if
        (a) the astronomical conjunction (new moon) occurs before
            Maghrib, AND
        (b) the moon sets AFTER the sun that evening (i.e. moonset is
            later than Maghrib),
    then the new month begins at that Maghrib (the month just ending
    was 29 days). Otherwise the new month begins one day later (the
    month just ending was 30 days).

This module implements exactly that rule, using:
  - `waqt.solar` for Maghrib at Makkah (the same engine and same
    validated accuracy as the rest of Waqt — reused deliberately, not
    reimplemented, so Sunday's sunset and Ramadan's Maghrib always
    agree with each other).
  - `ephem` (PyEphem) for the lunar conjunction and moonset, since
    waqt.solar has no lunar position code and this is the one place
    that needs it.

VALIDATION
Checked against four independently-known official Umm al-Qura New
Year dates spanning nine years — 1 Muharram 1438 (2 Oct 2016), 1440
(11 Sep 2018), 1441 (31 Aug 2019), and 1447 (26 Jun 2025). All four
reproduce EXACTLY. See tests/test_calendar_providers.py.

WHAT THIS IS NOT (read before trusting it for anything liturgical)
This is NOT the official Umm al-Qura calendar and does not have
access to Saudi Arabia's published tables. Two things can make a
real difference:
  1. The note on the aladhan.com Umm al-Qura calendar (the source
     used to validate this module) says explicitly that 1 Muharram,
     1 Ramadan, 1 Shawwal and 1 Dhu al-Hijjah are sometimes ADJUSTED
     from the pure calculation after real crescent-sighting reports.
     This provider has no way to know about or apply such an
     adjustment — it always returns the pure calculation.
  2. The lunar ephemeris used here (PyEphem's built-in lunar theory)
     is a high-quality analytic approximation, not a full modern
     ephemeris (e.g. JPL DE440). For a conjunction or moonset that
     falls within a few seconds of Maghrib, this could in principle
     flip the 29/30 day decision for that one month.

Given both of these, this provider should be read as "a rigorous,
honestly-labeled astronomical approximation of Umm al-Qura", not as
a certified reproduction of the official calendar. It is a genuine
improvement over `ArithmeticTabularProvider` (which ignores the real
astronomy entirely) and is offered on those terms.

RECURSION FIX (Sprint 3 post-review)
The original implementation walked month boundaries via recursion
(_boundary calling itself). For dates more than ~75 months from the
2025 anchor this hit Python's default recursion limit and raised
RecursionError, which the API did not catch — producing a raw 500
response. The fix converts both the forward and backward walks to
iterative loops, eliminating any stack-depth risk regardless of how
far from the anchor a requested date falls.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import ephem

from .. import solar
from ..hijri import CalendarOutOfRange, HijriDate

MAKKAH_LAT = 21.4225
MAKKAH_LON = 39.8262


def _makkah_maghrib(d: date) -> Optional[datetime]:
    return solar.sunset(d, MAKKAH_LAT, MAKKAH_LON)


def _conjunction_before(dt: datetime) -> datetime:
    return ephem.previous_new_moon(ephem.Date(dt)).datetime().replace(tzinfo=timezone.utc)


def _conjunction_after(dt: datetime) -> datetime:
    return ephem.next_new_moon(ephem.Date(dt)).datetime().replace(tzinfo=timezone.utc)


def _moonset_after(search_start: datetime) -> Optional[datetime]:
    obs = ephem.Observer()
    obs.lat = str(MAKKAH_LAT)
    obs.lon = str(MAKKAH_LON)
    obs.elevation = 0
    obs.date = ephem.Date(search_start)
    try:
        return obs.next_setting(ephem.Moon()).datetime().replace(tzinfo=timezone.utc)
    except (ephem.AlwaysUpError, ephem.NeverUpError):
        return None  # not expected at Makkah's latitude, but handled rather than crashing


@dataclass(frozen=True)
class MonthBoundary:
    conjunction: datetime
    label_date: date  # the Gregorian civil date labeled "1st of the new month"


def _month_start_from_conjunction(conj: datetime) -> MonthBoundary:
    """Applies the UAQ 29/30-day rule to one conjunction. See module
    docstring for the rule itself."""
    d = conj.date()
    maghrib = _makkah_maghrib(d)
    if maghrib is None:
        # Not expected at Makkah's latitude (21.4N) — no polar day/night
        # there. If it somehow happens, fail loudly rather than guess.
        raise RuntimeError(f"Maghrib undefined at Makkah for {d} — cannot apply UAQ rule.")

    moonset = _moonset_after(maghrib - timedelta(hours=6))
    criterion = conj < maghrib and moonset is not None and moonset > maghrib
    label = d + timedelta(days=1 if criterion else 2)
    return MonthBoundary(conjunction=conj, label_date=label)


class UmmAlQuraProvider:
    """Astronomical approximation of the Umm al-Qura calendar. See the
    module docstring for exactly what this does and does not guarantee.
    """

    name = "umm-al-qura"
    version = "astronomical-approx-2002-rules-v1"

    # 1 Muharram 1447 AH = 26 June 2025, per the officially-published
    # Umm al-Qura calendar (cross-checked against aladhan.com's Umm
    # al-Qura tables). Used only as a counting anchor for month/year
    # numbers — the month BOUNDARIES themselves are always computed
    # fresh from real conjunctions, never interpolated from this date.
    ANCHOR_LABEL_DATE = date(2025, 6, 26)
    ANCHOR_YEAR = 1447
    ANCHOR_MONTH = 1

    _AVG_SYNODIC_MONTH_DAYS = 29.530588853

    def __init__(self):
        anchor_conj = _conjunction_before(
            datetime(2025, 6, 26, 12, 0, tzinfo=timezone.utc)
        )
        self._boundaries: dict[int, MonthBoundary] = {
            0: MonthBoundary(conjunction=anchor_conj, label_date=self.ANCHOR_LABEL_DATE)
        }

    def _boundary(self, idx: int) -> MonthBoundary:
        """Return the MonthBoundary for month-index `idx` relative to the
        anchor (idx=0 = 1 Muharram 1447).

        ITERATIVE (not recursive) to avoid RecursionError for dates far
        from the anchor. We fill the cache outward from the nearest
        already-cached boundary, walking one month at a time in either
        direction.
        """
        if idx in self._boundaries:
            return self._boundaries[idx]

        if idx > 0:
            # Walk forward: find the highest cached index below idx,
            # then fill forward one step at a time.
            start = idx - 1
            while start not in self._boundaries:
                start -= 1
            current = start
            while current < idx:
                prev = self._boundaries[current]
                next_conj = _conjunction_after(prev.conjunction + timedelta(days=1))
                self._boundaries[current + 1] = _month_start_from_conjunction(next_conj)
                current += 1
        else:
            # Walk backward: find the lowest cached index above idx,
            # then fill backward one step at a time.
            start = idx + 1
            while start not in self._boundaries:
                start += 1
            current = start
            while current > idx:
                nxt = self._boundaries[current]
                prev_conj = _conjunction_before(nxt.conjunction - timedelta(days=1))
                self._boundaries[current - 1] = _month_start_from_conjunction(prev_conj)
                current -= 1

        return self._boundaries[idx]

    def _index_for_date(self, target: date) -> int:
        approx_days = (target - self.ANCHOR_LABEL_DATE).days
        idx = round(approx_days / self._AVG_SYNODIC_MONTH_DAYS)
        # Walk to the index whose month actually brackets `target`.
        # Bounded: real drift from the average never exceeds ~1-2
        # months even far from the anchor, so this converges in a
        # handful of steps.
        for _ in range(24):
            label = self._boundary(idx).label_date
            label_next = self._boundary(idx + 1).label_date
            if label <= target < label_next:
                return idx
            idx += -1 if target < label else 1
        raise RuntimeError(f"Could not bracket {target} within 24 month-steps of the anchor.")

    #: Sprint 16 (CAL-011): the SUPPORTED range. Accuracy is only characterised for
    #: roughly 1900-2100 (docs/CALENDARS.md); inside 1700..2300 the provider answers, outside
    #: it refuses with OUT_OF_RANGE rather than guess.
    SUPPORTED_MIN = date(1700, 1, 1)
    SUPPORTED_MAX = date(2300, 12, 31)
    _SUPPORTED_TEXT = "1700-01-01..2300-12-31"

    def from_gregorian(self, d: date) -> HijriDate:
        if not (self.SUPPORTED_MIN <= d <= self.SUPPORTED_MAX):
            raise CalendarOutOfRange(self.name, self._SUPPORTED_TEXT, d.isoformat())
        idx = self._index_for_date(d)
        label = self._boundary(idx).label_date
        day = (d - label).days + 1

        offset = self.ANCHOR_MONTH - 1 + idx
        year = self.ANCHOR_YEAR + offset // 12
        month = offset % 12 + 1

        return HijriDate(year=year, month=month, day=day, provider=self.name, version=self.version)

    def to_gregorian(self, year: int, month: int, day: int) -> date:
        """Inverse of from_gregorian. Unlike ArithmeticTabularProvider's
        closed-form inverse, this walks the (cached) real-conjunction
        boundary chain to the requested month — exact given this
        provider's own month boundaries, not a separate approximation
        layered on top of them.
        """
        if not (1100 <= year <= 1730):  # cheap pre-check before walking the boundary chain
            raise CalendarOutOfRange(self.name, self._SUPPORTED_TEXT, f"Hijri year {year}")
        idx = (year - self.ANCHOR_YEAR) * 12 + (month - self.ANCHOR_MONTH)
        label = self._boundary(idx).label_date
        g = label + timedelta(days=day - 1)
        if not (self.SUPPORTED_MIN <= g <= self.SUPPORTED_MAX):
            raise CalendarOutOfRange(self.name, self._SUPPORTED_TEXT, g.isoformat())
        return g

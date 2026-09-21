"""
waqt.hijri — Calendar provider interface.

Per the Core Time Model (Sec. 1), Waqt does not designate a canonical
religious calendar. It defines a provider interface and ships one
reference provider for testing/demo purposes.

IMPORTANT HONESTY NOTE (see SCOPE.md):
The provider shipped here, `ArithmeticTabularProvider`, is the classical
30-year-cycle tabular Islamic calendar (epoch JDN 1948440 = 1 Muharram,
1 AH). It is a well-known, deterministic arithmetic approximation and is
NOT the official Umm al-Qura calendar published by Saudi Arabia (which
follows its own revised, non-arithmetic rule set and requires the
official published tables to reproduce exactly). It will typically
agree with Umm al-Qura to within 1 day, sometimes 2.

It is labeled "arithmetic-tabular", not "tabular-uaq", specifically so
that no caller mistakes it for the real thing. A true `tabular-uaq`
provider is future work requiring the official dataset (see SCOPE.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol


WEEKDAY_NAMES_AR = [
    "al-Ahad",       # Sunday
    "al-Ithnayn",    # Monday
    "ath-Thulatha",  # Tuesday
    "al-Arbiaa",     # Wednesday
    "al-Khamis",     # Thursday
    "al-Jumuah",     # Friday
    "as-Sabt",       # Saturday
]

HIJRI_MONTH_NAMES = [
    "Muharram", "Safar", "Rabi al-Awwal", "Rabi al-Thani",
    "Jumada al-Awwal", "Jumada al-Thani", "Rajab", "Shaban",
    "Ramadan", "Shawwal", "Dhu al-Qadah", "Dhu al-Hijjah",
]


def _gregorian_to_jdn(d: date) -> int:
    y, m, day = d.year, d.month, d.day
    a = (14 - m) // 12
    y2 = y + 4800 - a
    m2 = m + 12 * a - 3
    return (
        day
        + (153 * m2 + 2) // 5
        + 365 * y2
        + y2 // 4
        - y2 // 100
        + y2 // 400
        - 32045
    )


@dataclass(frozen=True)
class HijriDate:
    year: int
    month: int  # 1-12
    day: int    # 1-30
    provider: str

    @property
    def month_name(self) -> str:
        return HIJRI_MONTH_NAMES[self.month - 1]

    def __str__(self) -> str:
        return f"{self.day} {self.month_name} {self.year} AH"

    def iso_like(self) -> str:
        return f"{self.year:04d}-{self.month:02d}-{self.day:02d}"


class HijriProvider(Protocol):
    """A calendar provider maps a Gregorian civil date to a Hijri date.

    Per the Core Time Model, this mapping is location-independent: one
    global label per Gregorian date, computed once (conceptually "at
    Makkah"), never re-derived per observer.
    """

    name: str

    def from_gregorian(self, d: date) -> HijriDate: ...


class ArithmeticTabularProvider:
    """Classical 30-year-cycle arithmetic Hijri calendar.

    Standard published algorithm (civil/tabular Islamic calendar,
    epoch JDN 1948440). Deterministic, offline, no external data
    required. See module docstring for accuracy caveats.
    """

    name = "arithmetic-tabular"

    def from_gregorian(self, d: date) -> HijriDate:
        jdn = _gregorian_to_jdn(d)
        year, month, day = self._jdn_to_hijri(jdn)
        return HijriDate(year=year, month=month, day=day, provider=self.name)

    @staticmethod
    def _jdn_to_hijri(jdn: int) -> tuple[int, int, int]:
        l = jdn - 1948440 + 10632
        n = (l - 1) // 10631
        l = l - 10631 * n + 354
        j = (
            (10985 - l) // 5316
        ) * ((50 * l) // 17719) + (l // 5670) * ((43 * l) // 15238)
        l = (
            l
            - ((30 - j) // 15) * ((17719 * j) // 50)
            - (j // 16) * ((15238 * j) // 43)
            + 29
        )
        month = (24 * l) // 709
        day = l - (709 * month) // 24
        year = 30 * n + j - 30
        return year, month, day


class DeclaredProvider:
    """Manual override provider — the operating institution supplies the
    date directly (e.g. from local moon-sighting), for one specific
    Gregorian date. Falls back to a wrapped provider for any other date.
    """

    name = "declared"

    def __init__(self, overrides: dict[date, HijriDate], fallback: HijriProvider):
        self._overrides = overrides
        self._fallback = fallback

    def from_gregorian(self, d: date) -> HijriDate:
        if d in self._overrides:
            hd = self._overrides[d]
            return HijriDate(hd.year, hd.month, hd.day, provider=self.name)
        return self._fallback.from_gregorian(d)


def weekday_name(d: date) -> str:
    """Gregorian weekday, in the Islamic week's own names.

    Python's date.weekday(): Monday=0 .. Sunday=6.
    Our list is Sunday-first (al-Ahad=0 .. as-Sabt=6).
    """
    return WEEKDAY_NAMES_AR[(d.weekday() + 1) % 7]

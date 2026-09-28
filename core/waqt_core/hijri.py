"""
waqt.hijri — Calendar provider interface.

Per the Core Time Model (Sec. 1), Waqt does not designate a canonical
religious calendar. It defines a provider interface (this module) and
this package ships several implementations under waqt/calendar_providers/
(Sprint 3). Every provider identifies itself with a `name` AND a
`version`, per the sprint brief's requirement that a date is never
reported without knowing which algorithm/dataset produced it:

    { "provider": "umm-al-qura", "version": "...", "date": "..." }

This module holds the interface itself plus the two simplest
providers (arithmetic-tabular, declared). waqt/core.py and waqt/solar.py
are untouched by Sprint 3 — every new provider is just another object
satisfying HijriProvider, injected the same way Stage 1 already
injected ArithmeticTabularProvider. That's the whole point: the
pluggability was already structurally there, Sprint 3 just proves it
by adding providers that actually stress it (a real astronomical one,
a registry, a demonstrably swappable custom one).

IMPORTANT HONESTY NOTE (see SCOPE.md):
`ArithmeticTabularProvider` is the classical 30-year-cycle tabular
Islamic calendar (epoch JDN 1948440 = 1 Muharram, 1 AH) — a
deterministic arithmetic approximation, NOT the official Umm al-Qura
calendar. It typically agrees with Umm al-Qura to within 1-2 days.
It is named "arithmetic-tabular", not "umm-al-qura", specifically so
no caller mistakes it for the real thing. The actual astronomical
Umm al-Qura provider lives in waqt/calendar_providers/umm_al_qura.py
— see that module for what it implements and its own honesty notes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional, Protocol


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


def _hijri_to_jdn(year: int, month: int, day: int) -> int:
    """Hijri (year, month, day) -> Julian Day Number.
    Fliegel & Van Flandern / standard tabular Islamic calendar formula.
    """
    import math
    return (
        day
        + math.ceil(29.5 * (month - 1))
        + (year - 1) * 354
        + (3 + 11 * year) // 30
        + 1948440
        - 1
    )


def _jdn_to_gregorian(jdn: int) -> date:
    """Julian Day Number -> Gregorian date. Standard algorithm."""
    l = jdn + 68569
    n = (4 * l) // 146097
    l = l - (146097 * n + 3) // 4
    i = (4000 * (l + 1)) // 1461001
    l = l - (1461 * i) // 4 + 31
    j = (80 * l) // 2447
    day = l - (2447 * j) // 80
    l = j // 11
    month = j + 2 - 12 * l
    year = 100 * (n - 49) + i + l
    return date(year, month, day)


@dataclass(frozen=True)
class HijriDate:
    year: int
    month: int  # 1-12
    day: int    # 1-30
    provider: str
    version: str = "unversioned"
    source_note: Optional[str] = None  # e.g. which local observation this came from

    @property
    def month_name(self) -> str:
        return HIJRI_MONTH_NAMES[self.month - 1]

    def __str__(self) -> str:
        return f"{self.day} {self.month_name} {self.year} AH"

    def iso_like(self) -> str:
        return f"{self.year:04d}-{self.month:02d}-{self.day:02d}"

    def _sort_key(self) -> tuple[int, int, int]:
        return (self.year, self.month, self.day)

    def __lt__(self, other: "HijriDate") -> bool:
        if not isinstance(other, HijriDate):
            return NotImplemented
        return self._sort_key() < other._sort_key()

    def __le__(self, other: "HijriDate") -> bool:
        if not isinstance(other, HijriDate):
            return NotImplemented
        return self._sort_key() <= other._sort_key()


class HijriProvider(Protocol):
    """A calendar provider maps a Gregorian civil date to a Hijri date.

    Per the Core Time Model, this mapping is location-independent: one
    global label per Gregorian date, computed once (conceptually "at
    Makkah"), never re-derived per observer.

    Every provider MUST set `name` and `version` as class/instance
    attributes and return a HijriDate carrying both, per the sprint
    brief's identification requirement.
    """

    name: str
    version: str

    def from_gregorian(self, d: date) -> HijriDate: ...


class ArithmeticTabularProvider:
    """Classical 30-year-cycle arithmetic Hijri calendar.

    Standard published algorithm (civil/tabular Islamic calendar,
    epoch JDN 1948440). Deterministic, offline, no external data
    required. See module docstring for accuracy caveats.
    """

    name = "arithmetic-tabular"
    version = "30-year-cycle-epoch-1948440"

    def from_gregorian(self, d: date) -> HijriDate:
        jdn = _gregorian_to_jdn(d)
        year, month, day = self._jdn_to_hijri(jdn)
        return HijriDate(year=year, month=month, day=day, provider=self.name, version=self.version)

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

    def to_gregorian(self, year: int, month: int, day: int) -> date:
        """Inverse of from_gregorian — exact, since the forward direction
        is a pure closed-form arithmetic formula (no search needed)."""
        return _jdn_to_gregorian(_hijri_to_jdn(year, month, day))


class DeclaredProvider:
    """Manual override provider — the operating institution supplies the
    date directly (e.g. from local moon-sighting), for one specific
    Gregorian date. Falls back to a wrapped provider for any other date.
    """

    name = "declared"
    version = "manual-v1"

    def __init__(self, overrides: dict[date, HijriDate], fallback: HijriProvider):
        self._overrides = overrides
        self._fallback = fallback

    def from_gregorian(self, d: date) -> HijriDate:
        if d in self._overrides:
            hd = self._overrides[d]
            return HijriDate(
                hd.year, hd.month, hd.day, provider=self.name, version=self.version,
                source_note=hd.source_note,
            )
        return self._fallback.from_gregorian(d)


def weekday_name(d: date) -> str:
    """Gregorian weekday, in the Islamic week's own names.

    Python's date.weekday(): Monday=0 .. Sunday=6.
    Our list is Sunday-first (al-Ahad=0 .. as-Sabt=6).
    """
    return WEEKDAY_NAMES_AR[(d.weekday() + 1) % 7]

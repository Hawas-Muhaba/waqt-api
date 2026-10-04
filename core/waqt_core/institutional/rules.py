"""
waqt.institutional.rules — calendar-convention primitives.

This is the vocabulary Sprint 7's week/fiscal-year/academic-year layer
is built from: small, composable rules that resolve a HIJRI YEAR (plus
a `HijriProvider`) to one specific `HijriDate`. Nothing here touches
astronomy, a location, or a Waqt day — resolving "1 Muharram of year
1448" or "the last Khamis of Sha'ban 1448" is a fact about the
calendar system, the same for every observer on Earth, exactly like
`HijriProvider.from_gregorian` itself (see waqt/hijri.py's own module
note on this). Binding a resolved calendar date to an actual Waqt day
(a real Maghrib instant, at a real place) is a separate, optional step
— see `waqt.institutional.binding`.

Every rule is a small frozen dataclass, JSON-serializable
(`rule_from_dict` / `.to_dict()`), so the same rule format can drive
Python callers, the HTTP API, and the conformance vectors — the same
pattern `waqt.scheduling.model` established for scheduling points.

WHAT THIS LAYER DOES NOT CLAIM
-------------------------------
A rule like "1 Muharram" or "last Khamis of Sha'ban" is calendar
arithmetic, not a ruling about when a fiscal or academic year *should*
start. Whether an institution's year begins on 1 Muharram, on the
first Ahad of Muharram, or on some other convention entirely is the
institution's decision to encode as a rule — this module supplies the
primitives to write that decision down precisely and resolve it
reproducibly, the same posture `waqt.scheduling.model` takes toward
religious rulings.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from ..hijri import HIJRI_MONTH_NAMES, HijriDate, HijriProvider, InvalidHijriDate, WEEKDAY_NAMES_AR, weekday_name

ISLAMIC_WEEKDAY_NAMES = tuple(WEEKDAY_NAMES_AR)  # al-Ahad .. as-Sabt, Sunday-first (index == Waqt's own convention)


class RuleError(Exception):
    """A calendar rule is malformed or cannot be resolved (e.g. an
    unknown weekday name, an out-of-range month, or a provider that
    cannot invert to Gregorian)."""


def _require_month(month: int) -> None:
    if not isinstance(month, int) or isinstance(month, bool) or not (1 <= month <= 12):
        raise RuleError(f"month must be an integer 1-12, got {month!r}")


def _require_weekday(name: str) -> None:
    if name not in ISLAMIC_WEEKDAY_NAMES:
        raise RuleError(f"unknown Islamic weekday {name!r}; known: {list(ISLAMIC_WEEKDAY_NAMES)}")


def month_days(provider: HijriProvider, year: int, month: int) -> list[HijriDate]:
    """Every HijriDate that actually belongs to (year, month) under
    `provider`, in day order. Requires `provider.to_gregorian`.

    Does not assume the month is 29 or 30 days: probes day 30 and
    keeps it only if `from_gregorian(to_gregorian(year, month, 30))`
    round-trips back to (year, month, 30) — the same defensive
    round-trip check `waqt.calendar_providers` uses elsewhere, so a
    provider whose `to_gregorian` normalizes an out-of-range day into
    the next month (rather than raising) can never silently produce a
    31st day that isn't really there.
    """
    if not hasattr(provider, "to_gregorian"):
        raise RuleError(
            f"calendar provider {getattr(provider, 'name', provider)!r} does not support "
            "to_gregorian(); institutional calendar rules require an invertible provider."
        )
    out = []
    for day in range(1, 31):
        try:
            g = provider.to_gregorian(year, month, day)
        except InvalidHijriDate:
            # Sprint 16 (DIS-002): a provider that rejects a non-existent day
            # (tabular: day 30 of a 29-day month) ends the month here.
            break
        back = provider.from_gregorian(g)
        if (back.year, back.month, back.day) != (year, month, day):
            break
        out.append(HijriDate(year=year, month=month, day=day, provider=provider.name, version=provider.version))
    if not out:
        raise RuleError(f"provider {provider.name!r} produced no valid days for {year}-{month:02d}")
    return out


def gregorian_weekday_of(provider: HijriProvider, hd: HijriDate):
    """The Islamic weekday name (al-Ahad..as-Sabt) of a HijriDate, via
    its Gregorian civil date. Location-independent (see module docstring)."""
    return weekday_name(provider.to_gregorian(hd.year, hd.month, hd.day))


# ---------------------------------------------------------------------------
# Rule types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MonthDay:
    """The Nth day of a given Hijri month in a given year. `day=1` is
    "month start"; the sprint brief's "Muharram 1"."""

    month: int
    day: int = 1

    def resolve(self, year: int, provider: HijriProvider) -> HijriDate:
        _require_month(self.month)
        days = month_days(provider, year, self.month)
        if not (1 <= self.day <= len(days)):
            raise RuleError(f"{provider.name} {year}-{self.month:02d} has {len(days)} days; day {self.day} does not exist")
        return days[self.day - 1]

    def to_dict(self) -> dict:
        return {"type": "month_day", "month": self.month, "day": self.day}


@dataclass(frozen=True)
class MonthEnd:
    """The last day of a given Hijri month — 29 or 30, whichever the
    provider actually produces for that year. The brief's "Dhul Hijjah
    29/30"."""

    month: int

    def resolve(self, year: int, provider: HijriProvider) -> HijriDate:
        _require_month(self.month)
        days = month_days(provider, year, self.month)
        return days[-1]

    def to_dict(self) -> dict:
        return {"type": "month_end", "month": self.month}


@dataclass(frozen=True)
class NthWeekdayOfMonth:
    """The n-th occurrence of a given Islamic weekday within a given
    Hijri month. `n=1`: first occurrence (the brief's "First Ahad of
    Muharram"). `n=-1`: last occurrence (the brief's "Last Khamis of
    Sha'ban"). Any other nonzero n counts forward (n>0) or backward
    (n<0) the same way Python list indexing does, so a caller isn't
    limited to just first/last."""

    weekday: str
    n: int
    month: int

    def resolve(self, year: int, provider: HijriProvider) -> HijriDate:
        _require_month(self.month)
        _require_weekday(self.weekday)
        if not isinstance(self.n, int) or isinstance(self.n, bool) or self.n == 0:
            raise RuleError(f"n must be a nonzero integer, got {self.n!r}")
        days = month_days(provider, year, self.month)
        matches = [d for d in days if gregorian_weekday_of(provider, d) == self.weekday]
        if not matches:
            raise RuleError(f"no {self.weekday} occurs in {provider.name} {year}-{self.month:02d}")
        idx = self.n - 1 if self.n > 0 else self.n
        if not (-len(matches) <= idx < len(matches)):
            raise RuleError(
                f"only {len(matches)} occurrence(s) of {self.weekday} in {year}-{self.month:02d}; n={self.n} out of range"
            )
        return matches[idx]

    def to_dict(self) -> dict:
        return {"type": "nth_weekday_of_month", "weekday": self.weekday, "n": self.n, "month": self.month}


CalendarRule = Any  # MonthDay | MonthEnd | NthWeekdayOfMonth — see rule_from_dict


def rule_from_dict(d: dict) -> CalendarRule:
    if not isinstance(d, dict) or "type" not in d:
        raise RuleError("a calendar rule must be a JSON object with a `type` field")
    t = d["type"]
    if t == "month_day":
        return MonthDay(month=d["month"], day=d.get("day", 1))
    if t == "month_end":
        return MonthEnd(month=d["month"])
    if t == "nth_weekday_of_month":
        return NthWeekdayOfMonth(weekday=d["weekday"], n=d["n"], month=d["month"])
    raise RuleError(f"unknown calendar rule type {t!r}")


def resolve_rule(rule: CalendarRule, year: int, provider: HijriProvider) -> HijriDate:
    """Resolve any rule to a HijriDate for the given Hijri `year`.
    A thin, uniform entry point so callers (fiscal/academic-year code,
    the HTTP API, the vector runner) never need an isinstance chain."""
    if not hasattr(rule, "resolve"):
        raise RuleError(f"{rule!r} is not a calendar rule")
    return rule.resolve(year, provider)

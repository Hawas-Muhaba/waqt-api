"""
waqt.api.providers — resolves the `calendar_provider` query param into
an actual HijriProvider, and holds the catalog used by GET /v1/calendar.

Fixes a real gap from Sprint 3's API: `declared` and `local-observation`
were reachable but always backed by an empty override dict, so every
query silently fell through to arithmetic-tabular no matter what the
caller asked for — the response's own `provider` field never actually
said "declared". Here, a caller who wants to exercise those two
providers supplies the override explicitly:

    /v1/waqt?...&calendar_provider=declared
             &override_date=2026-09-19&declared_year=1448&declared_month=4&declared_day=10

    /v1/waqt?...&calendar_provider=local-observation
             &override_date=2026-09-19&sighting_year=1448&sighting_month=4&sighting_day=9
             &observed_at=Addis+Ababa

If the override params are omitted, both still work exactly as before
(empty override, falls back to arithmetic-tabular) — nothing is broken
for a caller who doesn't care about this.
"""

from __future__ import annotations

from typing import Optional

from ..calendar_providers import (
    ArithmeticTabularProvider,
    DeclaredProvider,
    LocalObservationProvider,
    Sighting,
    UmmAlQuraProvider,
)
from ..hijri import HijriDate, HijriProvider
from .common import ApiError, ErrorCode, parse_date

PROVIDER_CATALOG = {
    "arithmetic-tabular": {
        "description": (
            "Classical 30-year-cycle arithmetic Hijri calendar (epoch JDN 1948440). "
            "Deterministic, offline, no external data. NOT an approximation of the "
            "official Umm al-Qura calendar specifically — typically within 1-2 days of it."
        ),
        "requires_override": False,
        "supports_reverse": True,
    },
    "umm-al-qura": {
        "description": (
            "Astronomical approximation of the real Umm al-Qura calculation rule "
            "(lunar conjunction before Makkah Maghrib AND moonset after Makkah Maghrib). "
            "Validated against 4 independently-known historical Umm al-Qura New Year "
            "dates (2016, 2018, 2019, 2025), all exact. Has no channel for the real-world "
            "sighting-based adjustments Umm al-Qura sometimes applies to 1 Muharram, "
            "1 Ramadan, 1 Shawwal and 1 Dhu al-Hijjah. See docs/CALENDARS.md."
        ),
        "requires_override": False,
        "supports_reverse": True,
    },
    "declared": {
        "description": (
            "An institution's adopted date for one specific Gregorian date, supplied via "
            "override_date + declared_year/month/day. Falls back to arithmetic-tabular for "
            "any other date, and if no override is supplied at all."
        ),
        "requires_override": True,
        "supports_reverse": False,
    },
    "local-observation": {
        "description": (
            "A reported moon sighting for one specific Gregorian date, supplied via "
            "override_date + sighting_year/month/day (+ optional observed_at location). "
            "Falls back to arithmetic-tabular for any other date, and if no sighting is "
            "supplied at all."
        ),
        "requires_override": True,
        "supports_reverse": False,
    },
}

_instance_cache: dict[str, HijriProvider] = {}


def _cached_stateless(name: str) -> HijriProvider:
    if name not in _instance_cache:
        if name == "arithmetic-tabular":
            _instance_cache[name] = ArithmeticTabularProvider()
        elif name == "umm-al-qura":
            _instance_cache[name] = UmmAlQuraProvider()
    return _instance_cache[name]


def resolve_calendar_provider(
    calendar_provider: str,
    override_date: Optional[str] = None,
    declared_year: Optional[int] = None,
    declared_month: Optional[int] = None,
    declared_day: Optional[int] = None,
    sighting_year: Optional[int] = None,
    sighting_month: Optional[int] = None,
    sighting_day: Optional[int] = None,
    observed_at: Optional[str] = None,
) -> HijriProvider:
    if calendar_provider not in PROVIDER_CATALOG:
        raise ApiError(
            400, ErrorCode.UNKNOWN_CALENDAR_PROVIDER,
            f"Unknown calendar_provider {calendar_provider!r}.",
            {"received": calendar_provider, "available": sorted(PROVIDER_CATALOG)},
        )

    fallback = _cached_stateless("arithmetic-tabular")

    if calendar_provider == "declared":
        overrides = {}
        if override_date and declared_year and declared_month and declared_day:
            d = parse_date(override_date, "override_date")
            overrides[d] = HijriDate(
                year=declared_year, month=declared_month, day=declared_day, provider="declared"
            )
        return DeclaredProvider(overrides=overrides, fallback=fallback)

    if calendar_provider == "local-observation":
        sightings = {}
        if override_date and sighting_year and sighting_month and sighting_day:
            d = parse_date(override_date, "override_date")
            sightings[d] = Sighting(
                year=sighting_year, month=sighting_month, day=sighting_day, observed_at=observed_at
            )
        return LocalObservationProvider(sightings=sightings, fallback=fallback)

    return _cached_stateless(calendar_provider)

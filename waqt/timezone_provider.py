"""
waqt.timezone_provider — Sprint 2, item 2.

Resolves a location to an IANA timezone, and a (location, instant) pair
to a *local civil Gregorian date*. This date is used ONLY to decide
which two calendar dates' Maghrib events bracket a given instant
(Core Time Model Sec 2's "local Gregorian date of t"). It is NOT used
to redefine the Waqt clock — the Waqt hour is still SI time since the
day's Maghrib, computed in Sec 3, and this module has no say in that.

Why this matters (the distinction the sprint brief calls out):
civil timezones are political and can be offset from solar time by
hours (India, China's single zone, etc.), and they can disagree with
which SIDE of the International Date Line a place falls on relative
to its longitude. Using the wrong civil date to bracket Maghrib can
shift the Hijri date by a full day for some locations near the date
line. Longitude alone (the Stage 1 UTC-date shortcut) cannot resolve
this correctly; only a real timezone lookup can.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional, Protocol

from zoneinfo import ZoneInfo


class TimezoneProvider(Protocol):
    def timezone_name_for(self, lat: float, lon: float) -> str:
        """IANA timezone name for a location, e.g. 'Africa/Addis_Ababa'."""
        ...

    def local_date(self, instant: datetime, lat: float, lon: float) -> date:
        """The civil calendar date at this location at this instant."""
        ...


@dataclass(frozen=True)
class ManualTimezoneProvider:
    """Fixed IANA zone, ignoring location — for testing, or for a caller
    who already knows the zone and wants to skip the lookup."""

    tz_name: str

    def timezone_name_for(self, lat: float, lon: float) -> str:
        return self.tz_name

    def local_date(self, instant: datetime, lat: float, lon: float) -> date:
        return instant.astimezone(ZoneInfo(self.tz_name)).date()


class IanaTimezoneProvider:
    """Looks up the real IANA timezone for a location via `timezonefinder`,
    then uses the standard library's `zoneinfo` to get the local date.
    This is the default provider and the one that actually fixes the
    International Date Line problem: it asks "what civil date is it
    there right now", not "what does raw longitude suggest".
    """

    name = "iana-timezonefinder"

    def __init__(self):
        # Imported lazily so environments without timezonefinder can still
        # import this module and use ManualTimezoneProvider.
        from timezonefinder import TimezoneFinder

        self._tf = TimezoneFinder()

    def timezone_name_for(self, lat: float, lon: float) -> str:
        tz = self._tf.timezone_at(lat=lat, lng=lon)
        if tz is None:
            # timezonefinder returns None over open ocean far from any
            # timezone polygon. Fall back to a fixed-offset Etc/GMT zone
            # derived from longitude, which is the best available proxy
            # for civil time in the middle of an ocean.
            offset_hours = round(lon / 15.0)
            offset_hours = max(-12, min(14, offset_hours))
            # Etc/GMT signs are inverted by POSIX convention.
            tz = f"Etc/GMT{'+' if offset_hours > 0 else ''}{-offset_hours}" if offset_hours != 0 else "Etc/GMT"
        return tz

    def local_date(self, instant: datetime, lat: float, lon: float) -> date:
        tz_name = self.timezone_name_for(lat, lon)
        return instant.astimezone(ZoneInfo(tz_name)).date()


DEFAULT_TIMEZONE_PROVIDER = IanaTimezoneProvider()

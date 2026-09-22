"""
waqt.calendar_providers.local_observation — moon-sighting reports as a
Hijri calendar source.

Intentionally distinct from `waqt.hijri.DeclaredProvider`, and that's
deliberate — the two exist as separate classes because they answer a
different question, not because they need different code:

  - DeclaredProvider: "this institution has adopted this date" (an
    administrative decision — could itself be based on a calculation,
    a religious authority's announcement, or a sighting report).
  - LocalObservationProvider: "someone reported seeing the crescent
    from this place on this evening" (a raw observation, potentially
    one of several conflicting reports for the same night).

Because sightings can disagree by location, each entry optionally
carries the observation site, surfaced on the returned HijriDate via
`source_note` so a caller can see (and a UI can display) which report
a given date rests on — something a bare "declared" override doesn't
represent.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from ..hijri import HijriDate, HijriProvider


@dataclass(frozen=True)
class Sighting:
    year: int
    month: int
    day: int
    observed_at: Optional[str] = None  # e.g. "Addis Ababa, Ethiopia" or a mosque name


class LocalObservationProvider:
    """Hijri dates from real, reported moon sightings, with a fallback
    provider (typically an astronomical one) for any date with no
    reported sighting on file.
    """

    name = "local-observation"
    version = "manual-sighting-v1"

    def __init__(self, sightings: dict[date, Sighting], fallback: HijriProvider):
        self._sightings = sightings
        self._fallback = fallback

    def from_gregorian(self, d: date) -> HijriDate:
        s = self._sightings.get(d)
        if s is not None:
            return HijriDate(
                year=s.year,
                month=s.month,
                day=s.day,
                provider=self.name,
                version=self.version,
                source_note=s.observed_at,
            )
        return self._fallback.from_gregorian(d)

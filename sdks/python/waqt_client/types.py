"""
waqt_client.types — the typed representations Sprint 9's brief asks for:
Waqt response, Waqt instant/position, Hijri date, Gregorian representation,
astronomical event, scheduling rule/result, institutional calendar result,
API errors.

Every `from_json` classmethod here does exactly one thing: turn the wire
JSON `/v1/*` already documents (docs/API.md, docs/CALENDAR-INTEROP.md,
docs/SCHEDULING.md, docs/INSTITUTIONAL.md) into an ergonomic Python object.
None of them recompute, validate, or second-guess a Waqt rule — that
would make this SDK "another implementation of Waqt's rules", which the
Sprint 9 brief explicitly says it must not become. If a field's meaning
depends on Waqt semantics, the server decided it; this module only
reshapes what the server already said.

Every type keeps the original parsed JSON on `.raw` (a plain dict), so a
field this SDK hasn't caught up to modeling explicitly is still reachable
without waiting for a new SDK release — the wire contract, not this
module's dataclass fields, is the source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


def _parse_instant(s: Optional[str]) -> Optional[datetime]:
    if s is None:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


# ---------------------------------------------------------------------------
# Small shared value types (mirrors waqt.api.common's response formatters)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Location:
    lat: float
    lon: float
    elevation_m: Optional[float] = None

    @classmethod
    def from_json(cls, d: Optional[dict]) -> Optional["Location"]:
        if d is None:
            return None
        return cls(lat=d["lat"], lon=d["lon"], elevation_m=d.get("elevation_m"))


@dataclass(frozen=True)
class TimezoneInfo:
    name: str
    utc_offset_seconds: Optional[int]

    @classmethod
    def from_json(cls, d: Optional[dict]) -> Optional["TimezoneInfo"]:
        if d is None:
            return None
        return cls(name=d["name"], utc_offset_seconds=d.get("utc_offset_seconds"))


@dataclass(frozen=True)
class Reading:
    """A duration/position on the Waqt hour grid: both a display string
    and a machine-usable seconds value (can exceed 24:00:00 — Core Time
    Model Sec 3 — this SDK reflects that as-is, never clamps it)."""

    display: str
    seconds: float

    @classmethod
    def from_json(cls, d: Optional[dict]) -> Optional["Reading"]:
        if d is None:
            return None
        return cls(display=d["display"], seconds=d["seconds"])


@dataclass(frozen=True)
class AstronomyProfile:
    name: str
    fajr_angle_deg: float
    isha_angle_deg: float
    asr_shadow_ratio: float

    @classmethod
    def from_json(cls, d: Optional[dict]) -> Optional["AstronomyProfile"]:
        if d is None:
            return None
        return cls(
            name=d["name"],
            fajr_angle_deg=d["fajr_angle_deg"],
            isha_angle_deg=d["isha_angle_deg"],
            asr_shadow_ratio=d["asr_shadow_ratio"],
        )


@dataclass(frozen=True)
class ComputationInfo:
    astronomy_engine: Optional[str]
    accuracy_level: Optional[str]
    timescale_model: Optional[str]
    delta_t_seconds: Optional[float]

    @classmethod
    def from_json(cls, d: Optional[dict]) -> Optional["ComputationInfo"]:
        if d is None:
            return None
        return cls(
            astronomy_engine=d.get("astronomy_engine"),
            accuracy_level=d.get("accuracy_level"),
            timescale_model=d.get("timescale_model"),
            delta_t_seconds=d.get("delta_t_seconds"),
        )


@dataclass(frozen=True)
class HijriDate:
    date: str  # provider's iso_like() string, e.g. "1448-04-07"
    display: str
    year: int
    month: int
    month_name: str
    day: int
    provider_name: str
    provider_version: str
    source_note: Optional[str]

    @classmethod
    def from_json(cls, d: Optional[dict]) -> Optional["HijriDate"]:
        if d is None:
            return None
        provider = d.get("provider") or {}
        return cls(
            date=d["date"],
            display=d["display"],
            year=d["year"],
            month=d["month"],
            month_name=d["month_name"],
            day=d["day"],
            provider_name=provider.get("name"),
            provider_version=provider.get("version"),
            source_note=d.get("source_note"),
        )


@dataclass(frozen=True)
class GregorianRepresentation:
    """One calendar-neutral rendering of an instant as a Gregorian civil
    date/time — either the UTC representation (`timezone_name is None`)
    or a specific place's local-civil representation. Mirrors
    `waqt.calendar_interop.GregorianRepresentation` field-for-field."""

    date: str
    time_of_day: str
    weekday_iso: int
    weekday_name_islamic: str
    is_leap_year: bool
    timezone_name: Optional[str] = None
    utc_offset_seconds: Optional[int] = None

    @classmethod
    def from_json(cls, d: Optional[dict]) -> Optional["GregorianRepresentation"]:
        if d is None:
            return None
        return cls(
            date=d["date"],
            time_of_day=d["time_of_day"],
            weekday_iso=d["weekday_iso"],
            weekday_name_islamic=d["weekday_name_islamic"],
            is_leap_year=d["is_leap_year"],
            timezone_name=d.get("timezone_name"),
            utc_offset_seconds=d.get("utc_offset_seconds"),
        )


@dataclass(frozen=True)
class AstronomicalEvent:
    """One of the six solar/prayer events, as returned in `/v1/waqt` and
    `/v1/events`'s `events[]` list (and, with `countdown` instead of
    `reading`, the same endpoints' `next_event`)."""

    name: str
    instant: Optional[datetime]
    reading: Optional[Reading] = None
    countdown: Optional[Reading] = None

    @classmethod
    def from_json(cls, d: Optional[dict]) -> Optional["AstronomicalEvent"]:
        if d is None:
            return None
        return cls(
            name=d["name"],
            instant=_parse_instant(d.get("instant")),
            reading=Reading.from_json(d.get("reading")),
            countdown=Reading.from_json(d.get("countdown")),
        )


@dataclass(frozen=True)
class WaqtPosition:
    display: str
    reading: Optional[Reading]

    @classmethod
    def from_json(cls, d: Optional[dict]) -> Optional["WaqtPosition"]:
        if d is None:
            return None
        return cls(display=d["display"], reading=Reading.from_json(d.get("reading")))


@dataclass(frozen=True)
class DayBoundary:
    maghrib_open: Optional[datetime]
    maghrib_close: Optional[datetime]
    length_si_seconds: Optional[float]
    note: Optional[str] = None

    @classmethod
    def from_json(cls, d: Optional[dict]) -> Optional["DayBoundary"]:
        if d is None:
            return None
        return cls(
            maghrib_open=_parse_instant(d.get("maghrib_open")),
            maghrib_close=_parse_instant(d.get("maghrib_close")),
            length_si_seconds=d.get("length_si_seconds"),
            note=d.get("note"),
        )


# ---------------------------------------------------------------------------
# Top-level typed responses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WaqtResponse:
    """The full `/v1/waqt` result: day boundary, Waqt clock reading, all
    six events, Hijri date, timezone, and computation identification.
    `/v1/day` and `/v1/events` return subsets of this same shape — see
    `WaqtResponse.from_json`, which tolerates missing keys, so the same
    type can represent all three."""

    status: str
    instant: Optional[datetime]
    location: Optional[Location]
    timezone: Optional[TimezoneInfo]
    undefined_reason: Optional[str]
    day: Optional[DayBoundary]
    hijri: Optional[HijriDate]
    weekday: Optional[str]
    waqt: Optional[WaqtPosition]
    events: list
    next_event: Optional[AstronomicalEvent]
    profile: Optional[AstronomyProfile]
    computation: Optional[ComputationInfo]
    raw: dict = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_json(cls, d: dict) -> "WaqtResponse":
        return cls(
            status=d["status"],
            instant=_parse_instant(d.get("instant")),
            location=Location.from_json(d.get("location")),
            timezone=TimezoneInfo.from_json(d.get("timezone")),
            undefined_reason=d.get("undefined_reason"),
            day=DayBoundary.from_json(d.get("day")),
            hijri=HijriDate.from_json(d.get("hijri")),
            weekday=d.get("weekday"),
            waqt=WaqtPosition.from_json(d.get("waqt")),
            events=[AstronomicalEvent.from_json(e) for e in (d.get("events") or [])],
            next_event=AstronomicalEvent.from_json(d.get("next_event")),
            profile=AstronomyProfile.from_json(d.get("profile")),
            computation=ComputationInfo.from_json(d.get("computation")),
            raw=d,
        )

    def event(self, name: str) -> Optional[AstronomicalEvent]:
        """Convenience accessor: `resp.event("maghrib")` instead of
        scanning `resp.events` by hand."""
        for e in self.events:
            if e.name == name:
                return e
        return None


@dataclass(frozen=True)
class InstantRepresentation:
    """`/v1/calendar/convert?direction=instant-to-calendars` — one
    instant, rendered as UTC-Gregorian always, plus local-civil-Gregorian
    and a Waqt day/position if a location was supplied. Mirrors
    `waqt.calendar_interop.InstantRepresentation`."""

    direction: str
    instant: Optional[datetime]
    location: Optional[Location]
    gregorian_utc: Optional[GregorianRepresentation]
    gregorian_civil: Optional[GregorianRepresentation]
    waqt_status: Optional[str]
    waqt_undefined_reason: Optional[str]
    waqt_day: Optional[DayBoundary]
    profile: Optional[AstronomyProfile]
    computation: Optional[ComputationInfo]
    caveat: Optional[str]
    raw: dict = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_json(cls, d: dict) -> "InstantRepresentation":
        greg = d.get("gregorian") or {}
        waqt_block = d.get("waqt") or {}
        return cls(
            direction=d["direction"],
            instant=_parse_instant((d.get("source") or {}).get("instant")),
            location=Location.from_json(d.get("location")),
            gregorian_utc=GregorianRepresentation.from_json(greg.get("utc")),
            gregorian_civil=GregorianRepresentation.from_json(greg.get("civil")),
            waqt_status=waqt_block.get("status"),
            waqt_undefined_reason=waqt_block.get("undefined_reason"),
            waqt_day=DayBoundary.from_json(waqt_block.get("day")),
            profile=AstronomyProfile.from_json(d.get("profile")),
            computation=ComputationInfo.from_json(d.get("computation")),
            caveat=d.get("caveat"),
            raw=d,
        )


@dataclass(frozen=True)
class SchedulingResult:
    """`/v1/schedule/snapshot`, `/v1/schedule/span`, and
    `POST /v1/schedule/resolve` all return this. These endpoints'
    response shapes vary by which one you called (see docs/SCHEDULING.md)
    -- rather than three separate dataclasses guessing at a shape that
    might drift, `.raw` is the actual response and the two fields below
    are the ones every variant shares."""

    status: Optional[str]
    location: Optional[Location]
    raw: dict = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_json(cls, d: dict) -> "SchedulingResult":
        return cls(status=d.get("status"), location=Location.from_json(d.get("location")), raw=d)

    def __getitem__(self, key: str) -> Any:
        return self.raw[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)


@dataclass(frozen=True)
class InstitutionalCalendarResult:
    """`/v1/institutional/week`, `/v1/institutional/fiscal-year`,
    `/v1/institutional/academic-year`, `/v1/institutional/profile`, and
    the two `POST .../resolve` endpoints (docs/INSTITUTIONAL.md). Same
    reasoning as `SchedulingResult`: these vary by endpoint, so this type
    keeps the two universal fields typed and the rest on `.raw`."""

    status: Optional[str]
    calendar_provider_name: Optional[str]
    raw: dict = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_json(cls, d: dict) -> "InstitutionalCalendarResult":
        provider = d.get("calendar_provider") or {}
        return cls(status=d.get("status"), calendar_provider_name=provider.get("name"), raw=d)

    def __getitem__(self, key: str) -> Any:
        return self.raw[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)


@dataclass(frozen=True)
class CalendarProviderInfo:
    name: str
    description: str
    requires_override: bool
    supports_reverse_conversion: bool

    @classmethod
    def from_json(cls, d: dict) -> "CalendarProviderInfo":
        return cls(
            name=d["name"],
            description=d["description"],
            requires_override=d["requires_override"],
            supports_reverse_conversion=d["supports_reverse_conversion"],
        )


@dataclass(frozen=True)
class ConversionResult:
    direction: str
    input: dict
    output: dict
    raw: dict = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_json(cls, d: dict) -> "ConversionResult":
        return cls(direction=d["direction"], input=d.get("input", {}), output=d.get("output", {}), raw=d)


@dataclass(frozen=True)
class BoundaryCrossingResult:
    status: str
    crosses_civil_midnight: Optional[bool]
    crosses_maghrib: Optional[bool]
    start_civil_date: Optional[str]
    end_civil_date: Optional[str]
    undefined_reason: Optional[str]
    raw: dict = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_json(cls, d: dict) -> "BoundaryCrossingResult":
        return cls(
            status=d["status"],
            crosses_civil_midnight=d.get("crosses_civil_midnight"),
            crosses_maghrib=d.get("crosses_maghrib"),
            start_civil_date=d.get("start_civil_date"),
            end_civil_date=d.get("end_civil_date"),
            undefined_reason=d.get("undefined_reason"),
            raw=d,
        )


@dataclass(frozen=True)
class LocationInfo:
    location: Location
    instant: Optional[datetime]
    timezone: Optional[TimezoneInfo]
    local_civil_date: str
    raw: dict = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_json(cls, d: dict) -> "LocationInfo":
        return cls(
            location=Location.from_json(d["location"]),
            instant=_parse_instant(d.get("instant")),
            timezone=TimezoneInfo.from_json(d.get("timezone")),
            local_civil_date=d["local_civil_date"],
            raw=d,
        )

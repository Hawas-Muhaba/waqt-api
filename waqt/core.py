"""
waqt.core — Core Time Model v0.1.

Implements exactly the four things the Core Time Model document defines:

  Sec 1. Makkah reference   -> hijri.HijriProvider (date authority only)
  Sec 2. Day boundary       -> _bracket_maghrib()
  Sec 3. The hour           -> WaqtReading.hour_* fields (SI, reset at Maghrib)
  Sec 4. Event positions    -> WaqtResult.events (readings, not boundaries)

Sprint 2 change to Sec 2's implementation (NOT to the model itself):
"the local Gregorian date of t" is now resolved via a real IANA
timezone lookup (waqt.timezone_provider) instead of Stage 1's UTC-date
shortcut. This fixes the International-Date-Line failure mode flagged
in SCOPE.md — a location whose civil calendar date differs from its
UTC calendar date (most of the Pacific, parts of the Americas) now
brackets Maghrib against the date its own clocks and calendars use,
not against Greenwich's.

Important: the timezone is used ONLY to pick which date's Maghrib
computations to run. It has no effect on Sec 3 (the hour is still SI
time since Maghrib) or on the Hijri date value itself, which is a
location-independent lookup on the *closing* date (Sec 1). This
separation is deliberate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from . import solar
from .hijri import HijriDate, HijriProvider, weekday_name
from .timescale import DEFAULT_TIMESCALE_PROVIDER, TimeScaleProvider
from .timezone_provider import DEFAULT_TIMEZONE_PROVIDER, TimezoneProvider


@dataclass(frozen=True)
class AstronomyProfile:
    """The set of choices Sec 4 says can only ever move a marker's
    position on the grid — never the grid itself."""

    name: str = "default"
    fajr_angle_deg: float = 18.0
    isha_angle_deg: float = 17.0
    asr_shadow_ratio: float = 1.0  # 1.0 = standard, 2.0 = Hanafi


DEFAULT_PROFILE = AstronomyProfile()


@dataclass(frozen=True)
class Location:
    """A place, for Waqt's purposes: coordinates plus elevation.

    Elevation defaults to 0 (sea level) and, per solar._dip_of_horizon_deg,
    affects sunrise/sunset only.
    """

    lat: float
    lon: float
    elevation_m: float = 0.0


@dataclass(frozen=True)
class EventReading:
    name: str
    instant: datetime | None
    hour_reading: str | None


@dataclass(frozen=True)
class WaqtResult:
    status: str  # "OK" | "UNDEFINED" | "ORDERING_VIOLATION"
    instant: datetime

    location_lat: float
    location_lon: float
    location_elevation_m: float

    timezone_name: str | None

    hijri_date: HijriDate | None
    weekday: str | None

    day_start_maghrib: datetime | None
    day_end_maghrib: datetime | None
    day_length_si_seconds: float | None

    hour_reading: str | None
    hour_length_note: str | None

    events: list[EventReading] = field(default_factory=list)
    next_event: EventReading | None = None
    next_event_countdown: str | None = None

    profile: AstronomyProfile = DEFAULT_PROFILE
    calendar_provider: str | None = None
    timescale_model: str | None = None
    delta_t_seconds: float | None = None

    undefined_reason: str | None = None


def _format_hms(delta: timedelta) -> str:
    total_seconds = delta.total_seconds()
    sign = "-" if total_seconds < 0 else ""
    total_seconds = abs(total_seconds)
    h = int(total_seconds // 3600)
    m = int((total_seconds % 3600) // 60)
    s = int(total_seconds % 60)
    return f"{sign}{h:02d}:{m:02d}:{s:02d}"


def _bracket_maghrib(
    t: datetime,
    loc: Location,
    tz_provider: TimezoneProvider,
    timescale: TimeScaleProvider,
    search_window_days: int = 3,
) -> tuple[date, datetime | None, date, datetime | None, str]:
    """Core Time Model Sec 2, using a real civil timezone for the local
    Gregorian date (Sprint 2), not Stage 1's UTC-date shortcut.

    Returns (open_date, M_D, close_date, M_D1, tz_name).

    Implementation note: a naive "civil date g, try g and g+/-1" search
    (Stage 1's approach, just swapping UTC date for civil date) breaks
    for locations where the civil UTC offset is far from the natural
    solar offset implied by longitude — which is not a hypothetical
    edge case. Kiribati deliberately set Kiritimati's civil offset to
    UTC+14 specifically so the whole nation shares one calendar date
    despite spanning the 180th meridian; its natural solar offset from
    longitude (~-157 deg) is close to UTC-10.5. That is a ~24.5-hour
    gap between "civil date" and "the date the sun agrees with", wider
    than a +/-1-day search can bridge. So instead of assuming which
    neighbour date brackets t, we compute sunset across a window of
    calendar dates around the civil date and find the actual
    consecutive pair that brackets t. See tests/test_core.py's
    Kiritimati case.
    """
    tz_name = tz_provider.timezone_name_for(loc.lat, loc.lon)
    g = tz_provider.local_date(t, loc.lat, loc.lon)

    def sunset_for(d: date) -> datetime | None:
        return solar.sunset(d, loc.lat, loc.lon, loc.elevation_m, timescale=timescale)

    window = [g + timedelta(days=k) for k in range(-search_window_days, search_window_days + 1)]
    sunsets = [(d, sunset_for(d)) for d in window]

    for (d_open, m_open), (d_close, m_close) in zip(sunsets, sunsets[1:]):
        if m_open is not None and m_close is not None and m_open <= t < m_close:
            return d_open, m_open, d_close, m_close, tz_name

    # No bracketing pair found in the window: either a polar location
    # (sunset undefined nearby) or, in principle, an offset wider than
    # the search window. Report using the civil date's own sunset (or
    # lack of it) so the caller gets a clear UNDEFINED/diagnostic
    # rather than a silent wrong answer.
    m_g = sunset_for(g)
    return g - timedelta(days=1), None, g, m_g, tz_name


def compute_waqt(
    instant: datetime,
    location: Location,
    calendar_provider: HijriProvider,
    profile: AstronomyProfile = DEFAULT_PROFILE,
    tz_provider: TimezoneProvider = DEFAULT_TIMEZONE_PROVIDER,
    timescale: TimeScaleProvider = DEFAULT_TIMESCALE_PROVIDER,
) -> WaqtResult:
    """The single entry point: given an instant and a place, compute
    the full Waqt reading."""

    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    instant = instant.astimezone(timezone.utc)

    open_date, m_open, close_date, m_close, tz_name = _bracket_maghrib(
        instant, location, tz_provider, timescale
    )

    common = dict(
        instant=instant,
        location_lat=location.lat,
        location_lon=location.lon,
        location_elevation_m=location.elevation_m,
        timezone_name=tz_name,
        profile=profile,
        calendar_provider=calendar_provider.name,
        timescale_model=timescale.name,
        delta_t_seconds=timescale.delta_t_seconds(close_date),
    )

    if m_open is None or m_close is None:
        return WaqtResult(
            status="UNDEFINED",
            hijri_date=None,
            weekday=None,
            day_start_maghrib=m_open,
            day_end_maghrib=m_close,
            day_length_si_seconds=None,
            hour_reading=None,
            hour_length_note=None,
            undefined_reason=(
                "Maghrib (sunset) does not occur for this date/location — "
                "polar day or polar night. No high-latitude fallback is "
                "applied automatically; see SCOPE.md."
            ),
            **common,
        )

    if not (m_open <= instant < m_close):
        return WaqtResult(
            status="ORDERING_VIOLATION",
            hijri_date=None,
            weekday=None,
            day_start_maghrib=m_open,
            day_end_maghrib=m_close,
            day_length_si_seconds=None,
            hour_reading=None,
            hour_length_note=None,
            undefined_reason="Computed Maghrib boundaries did not bracket the instant.",
            **common,
        )

    hijri_date = calendar_provider.from_gregorian(close_date)
    weekday = weekday_name(close_date)

    day_length = (m_close - m_open).total_seconds()

    hour_reading = _format_hms(instant - m_open)
    note = None
    if day_length > 86400 + 1:
        note = "Day exceeds 24:00:00 today; readings may briefly pass 24:00:00 before the next Maghrib."
    elif day_length < 86400 - 1:
        note = "Day is shorter than 24:00:00 today; the reading will reset before conventional midnight would."

    day_events = solar.compute_day_events(
        close_date,
        location.lat,
        location.lon,
        elevation_m=location.elevation_m,
        fajr_angle_deg=profile.fajr_angle_deg,
        isha_angle_deg=profile.isha_angle_deg,
        asr_shadow_ratio=profile.asr_shadow_ratio,
        timescale=timescale,
    )

    def reading_for(ev_instant: datetime | None) -> str | None:
        if ev_instant is None:
            return None
        return _format_hms(ev_instant - m_open)

    events = [
        EventReading("fajr", day_events.fajr, reading_for(day_events.fajr)),
        EventReading("sunrise", day_events.sunrise, reading_for(day_events.sunrise)),
        EventReading("dhuhr", day_events.dhuhr, reading_for(day_events.dhuhr)),
        EventReading("asr", day_events.asr, reading_for(day_events.asr)),
        EventReading("maghrib", m_close, reading_for(m_close)),
        EventReading("isha", day_events.isha, reading_for(day_events.isha)),
    ]

    next_event = None
    next_countdown = None
    for ev in events:
        if ev.instant is not None and ev.instant > instant:
            next_event = ev
            next_countdown = _format_hms(ev.instant - instant)
            break

    return WaqtResult(
        status="OK",
        hijri_date=hijri_date,
        weekday=weekday,
        day_start_maghrib=m_open,
        day_end_maghrib=m_close,
        day_length_si_seconds=day_length,
        hour_reading=hour_reading,
        hour_length_note=note,
        events=events,
        next_event=next_event,
        next_event_countdown=next_countdown,
        **common,
    )

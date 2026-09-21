"""
waqt.core — Core Time Model v0.1.

Implements exactly the four things the Core Time Model document defines:

  Sec 1. Makkah reference   -> hijri.HijriProvider (date authority only)
  Sec 2. Day boundary       -> _bracket_maghrib()
  Sec 3. The hour           -> WaqtReading.hour_* fields (SI, reset at Maghrib)
  Sec 4. Event positions    -> WaqtResult.events (readings, not boundaries)

Implementation note on "local Gregorian date" (Core Time Model Sec 2):
the model brackets an instant between two Maghribs using "the local
Gregorian date of t". This reference implementation resolves that as
the UTC calendar date of t. This is a deliberate, documented
simplification (see SCOPE.md) — it is exact near the Greenwich
meridian and near Makkah/Addis Ababa (UTC+3, far from any date-line
ambiguity), and is flagged as a deferred edge case for locations near
the international date line, per the Core Time Model's own deferred-
item list.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from . import solar
from .hijri import HijriDate, HijriProvider, weekday_name


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
class EventReading:
    """One event, as an absolute instant AND as a position on the
    current Waqt day's hour grid (Core Time Model Sec 4)."""

    name: str
    instant: datetime | None
    hour_reading: str | None  # "HH:MM:SS" relative to this day's Maghrib, or None


@dataclass(frozen=True)
class WaqtResult:
    status: str  # "OK" | "UNDEFINED" | "ORDERING_VIOLATION"
    instant: datetime

    location_lat: float
    location_lon: float

    hijri_date: HijriDate | None
    weekday: str | None

    day_start_maghrib: datetime | None  # M(D)  — opens this Waqt day, reading 00:00:00
    day_end_maghrib: datetime | None    # M(D+1) — closes it, next day's 00:00:00
    day_length_si_seconds: float | None

    hour_reading: str | None            # this instant's own HH:MM:SS
    hour_length_note: str | None        # human note, since the "hour" here IS the SI hour

    events: list[EventReading] = field(default_factory=list)
    next_event: EventReading | None = None
    next_event_countdown: str | None = None  # "HH:MM:SS" until next_event

    profile: AstronomyProfile = DEFAULT_PROFILE
    calendar_provider: str | None = None

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
    t: datetime, lat: float, lon: float
) -> tuple[date, datetime | None, date, datetime | None]:
    """Core Time Model Sec 2.

    Returns (open_date, M_D, close_date, M_D1) such that, when both
    Maghribs exist, day = [M_D, M_D1) contains t.

    open_date / close_date are the Gregorian calendar dates whose
    sunset events these are (UTC date used as "local Gregorian date" —
    see module docstring).
    """
    d0 = t.astimezone(timezone.utc).date()
    m0 = solar.sunset(d0, lat, lon)

    if m0 is not None and t >= m0:
        open_date, close_date = d0, d0 + timedelta(days=1)
        m_open = m0
        m_close = solar.sunset(close_date, lat, lon)
    else:
        open_date, close_date = d0 - timedelta(days=1), d0
        m_open = solar.sunset(open_date, lat, lon)
        m_close = m0 if m0 is not None else solar.sunset(close_date, lat, lon)

    return open_date, m_open, close_date, m_close


def compute_waqt(
    instant: datetime,
    lat: float,
    lon: float,
    calendar_provider: HijriProvider,
    profile: AstronomyProfile = DEFAULT_PROFILE,
) -> WaqtResult:
    """The single entry point: given an instant and a place, compute
    the full Waqt reading. This is the `waqt(...)` function from the
    Core Time Model, Sec 2-4, assembled."""

    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    instant = instant.astimezone(timezone.utc)

    open_date, m_open, close_date, m_close = _bracket_maghrib(instant, lat, lon)

    if m_open is None or m_close is None:
        return WaqtResult(
            status="UNDEFINED",
            instant=instant,
            location_lat=lat,
            location_lon=lon,
            hijri_date=None,
            weekday=None,
            day_start_maghrib=m_open,
            day_end_maghrib=m_close,
            day_length_si_seconds=None,
            hour_reading=None,
            hour_length_note=None,
            profile=profile,
            calendar_provider=calendar_provider.name,
            undefined_reason=(
                "Maghrib (sunset) does not occur for this date/location — "
                "polar day or polar night. No high-latitude fallback is "
                "applied automatically; see SCOPE.md."
            ),
        )

    if not (m_open <= instant < m_close):
        return WaqtResult(
            status="ORDERING_VIOLATION",
            instant=instant,
            location_lat=lat,
            location_lon=lon,
            hijri_date=None,
            weekday=None,
            day_start_maghrib=m_open,
            day_end_maghrib=m_close,
            day_length_si_seconds=None,
            hour_reading=None,
            hour_length_note=None,
            profile=profile,
            calendar_provider=calendar_provider.name,
            undefined_reason="Computed Maghrib boundaries did not bracket the instant.",
        )

    # Sec 1 + Sec 2: the Hijri date is the calendar provider's date for
    # the Gregorian date whose Maghrib CLOSES this interval.
    hijri_date = calendar_provider.from_gregorian(close_date)
    weekday = weekday_name(close_date)

    day_length = (m_close - m_open).total_seconds()

    # Sec 3: the hour is SI time elapsed since this day's opening Maghrib.
    hour_reading = _format_hms(instant - m_open)
    note = None
    if day_length > 86400 + 1:
        note = "Day exceeds 24:00:00 today; readings may briefly pass 24:00:00 before the next Maghrib."
    elif day_length < 86400 - 1:
        note = "Day is shorter than 24:00:00 today; the reading will reset before conventional midnight would."

    # Sec 4: events, computed for the date whose events populate THIS
    # Waqt day (= close_date, since night = [M(D), sunrise(D+1)) etc.
    # and D+1's Gregorian date is close_date).
    day_events = solar.compute_day_events(
        close_date,
        lat,
        lon,
        fajr_angle_deg=profile.fajr_angle_deg,
        isha_angle_deg=profile.isha_angle_deg,
        asr_shadow_ratio=profile.asr_shadow_ratio,
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
        instant=instant,
        location_lat=lat,
        location_lon=lon,
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
        profile=profile,
        calendar_provider=calendar_provider.name,
    )

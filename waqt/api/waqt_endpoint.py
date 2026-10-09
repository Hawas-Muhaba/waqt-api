"""
waqt.api.waqt_endpoint — GET /v1/waqt

The full combined result: day boundary, Waqt clock reading, all six
prayer/solar events, Hijri date, timezone, and full computation
identification. Every other endpoint returns a subset of this same
information, computed the same way (core.compute_waqt), never a
separately-derived answer.

Schema is NULL-STABLE: the same top-level keys are always present,
whatever the status. When status != "OK" (e.g. UNDEFINED at a pole),
fields that don't apply are explicitly `null`, not omitted — a caller
can write one deserializer and rely on the shape never changing.
"""

from __future__ import annotations

from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query, Response

from ..core import AstronomyProfile, Location, compute_waqt
from ..timescale import DEFAULT_TIMESCALE_PROVIDER
from ..timezone_provider import DEFAULT_TIMEZONE_PROVIDER, ManualTimezoneProvider
from .common import computation_block, hijri_block, iso, parse_instant, profile_block, reading, success, timezone_block
from .providers import DEFAULT_CALENDAR_PROVIDER, PROVIDER_CATALOG, resolve_calendar_provider

router = APIRouter()


def _gregorian_repr(instant, tz_name: Optional[str]) -> Optional[dict]:
    """Civil (Gregorian) representation of an instant: UTC plus local wall time in the
    resolved zone. `local_date` can differ from the Waqt day label -- Isha frequently falls
    on the next civil date -- which is exactly why both are shown."""
    if instant is None:
        return None
    out = {"utc": iso(instant), "timezone": tz_name, "local": None, "local_date": None, "local_time": None}
    if tz_name:
        try:
            loc = instant.astimezone(ZoneInfo(tz_name))
            out.update(local=loc.isoformat(timespec="seconds"), local_date=loc.date().isoformat(),
                       local_time=loc.time().isoformat(timespec="seconds"))
        except Exception:
            pass
    return out


def _hijri_repr(hd) -> Optional[dict]:
    """The Hijri label of the Waqt day an event belongs to (Waqt places every event of a
    Maghrib-to-Maghrib day on that day's clock -- Maghrib and Isha read >= the day length
    rather than rolling to the next label). Decoration only: derived AFTER, and never an
    input to, the event instant."""
    if hd is None:
        return None
    return {"date": hd.iso_like(), "provider": hd.provider, "version": hd.version,
            "source": hd.source, "basis": "waqt-day-label"}


@router.get("/v1/waqt")
def get_waqt(
    response: Response,
    lat: float = Query(..., ge=-90, le=90, description="Latitude, WGS84 degrees"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude, WGS84 degrees"),
    elevation_m: float = Query(0.0, ge=0, description="Elevation, metres above sea level"),
    instant: Optional[str] = Query(None, description="ISO 8601 UTC instant; defaults to now"),
    timezone_override: Optional[str] = Query(
        None, description="IANA zone to force (e.g. 'Africa/Addis_Ababa'), skipping lookup"
    ),
    fajr_angle: float = Query(18.0, description="Fajr depression angle, degrees"),
    isha_angle: float = Query(17.0, description="Isha depression angle, degrees"),
    asr_ratio: float = Query(1.0, description="Asr shadow ratio: 1.0 = standard, 2.0 = Hanafi"),
    calendar_provider: str = Query(
        DEFAULT_CALENDAR_PROVIDER, description=f"One of: {', '.join(PROVIDER_CATALOG)}. See GET /v1/calendar."
    ),
    override_date: Optional[str] = Query(
        None, description="For calendar_provider=declared|local-observation: the Gregorian date (YYYY-MM-DD) this override applies to."
    ),
    declared_year: Optional[int] = Query(None, description="declared provider: Hijri year to report on override_date"),
    declared_month: Optional[int] = Query(None, ge=1, le=12, description="declared provider: Hijri month (1-12)"),
    declared_day: Optional[int] = Query(None, ge=1, le=30, description="declared provider: Hijri day (1-30)"),
    sighting_year: Optional[int] = Query(None, description="local-observation provider: Hijri year to report on override_date"),
    sighting_month: Optional[int] = Query(None, ge=1, le=12, description="local-observation provider: Hijri month (1-12)"),
    sighting_day: Optional[int] = Query(None, ge=1, le=30, description="local-observation provider: Hijri day (1-30)"),
    observed_at: Optional[str] = Query(None, description="local-observation provider: where the sighting was reported from"),
):
    response.headers["Cache-Control"] = "private, max-age=30" if instant else "no-store"
    t = parse_instant(instant)
    provider = resolve_calendar_provider(
        calendar_provider, override_date,
        declared_year, declared_month, declared_day,
        sighting_year, sighting_month, sighting_day, observed_at,
    )

    location = Location(lat=lat, lon=lon, elevation_m=elevation_m)
    profile = AstronomyProfile(
        name="custom", fajr_angle_deg=fajr_angle, isha_angle_deg=isha_angle, asr_shadow_ratio=asr_ratio
    )
    tz_provider = ManualTimezoneProvider(timezone_override) if timezone_override else DEFAULT_TIMEZONE_PROVIDER

    r = compute_waqt(t, location, provider, profile, tz_provider=tz_provider, timescale=DEFAULT_TIMESCALE_PROVIDER)

    waqt_field = None
    if r.hour_reading is not None and r.day_start_maghrib is not None:
        waqt_field = {
            "display": f"Waqt {r.hour_reading}",
            "reading": reading(r.instant - r.day_start_maghrib),
        }

    events_field = []
    for e in r.events:
        events_field.append({
            "name": e.name,
            "instant": iso(e.instant),
            "reading": reading(e.instant - r.day_start_maghrib) if (e.instant and r.day_start_maghrib) else None,
        })

    # Sprint 14 (additive): every event in all three vocabularies. A SIBLING of `events`, not
    # nested in it, so `events[]` stays byte-identical to /v1/events (the "never a separately
    # derived answer" contract). Same order as `events`; join on `name`.
    event_representations = []
    for ev in events_field:
        event_representations.append({
            "name": ev["name"],
            "gregorian": _gregorian_repr(next(x.instant for x in r.events if x.name == ev["name"]), r.timezone_name),
            "hijri": _hijri_repr(r.hijri_date),
            "waqt": ({"display": f"Waqt {ev['reading']['display']}", "seconds": ev["reading"]["seconds"]}
                     if ev["reading"] is not None else None),
        })

    next_event_field = None
    if r.next_event is not None:
        next_event_field = {
            "name": r.next_event.name,
            "instant": iso(r.next_event.instant),
            "countdown": reading(r.next_event.instant - r.instant) if r.next_event.instant else None,
        }

    data = {
        "status": r.status,
        "instant": iso(r.instant),
        "location": {"lat": r.location_lat, "lon": r.location_lon, "elevation_m": r.location_elevation_m},
        "timezone": timezone_block(r.timezone_name, r.instant),
        "undefined_reason": r.undefined_reason,
        "day": {
            "maghrib_open": iso(r.day_start_maghrib),
            "maghrib_close": iso(r.day_end_maghrib),
            "length_si_seconds": round(r.day_length_si_seconds, 3) if r.day_length_si_seconds is not None else None,
            "note": r.hour_length_note,
        },
        "hijri": hijri_block(r.hijri_date),
        # Sprint 14: null unless the calendar provider raised. When set, `hijri` is null but
        # every astronomical field above/below is still fully computed.
        "calendar_error": ({"provider": provider.name, "message": r.calendar_error}
                           if r.calendar_error else None),
        "weekday": r.weekday,
        "waqt": waqt_field,
        "events": events_field,
        "event_representations": event_representations,
        "next_event": next_event_field,
        "profile": profile_block(r.profile),
        "computation": computation_block(r.timescale_model, r.delta_t_seconds),
    }
    return success(data)

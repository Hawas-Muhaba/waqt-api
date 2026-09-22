"""
waqt.api — HTTP surface for the Core Time Model.

Sprint 2 adds: elevation_m, and an optional tz override (for testing
or for a caller who already knows the IANA zone and wants to skip the
lookup). Local civil date is now resolved via a real timezone lookup
by default (see waqt.timezone_provider) rather than Stage 1's UTC-date
shortcut.

Sprint 3 adds: pluggable calendar provider system with five provider
categories. The calendar_provider query parameter now accepts:
  - arithmetic-tabular  (default, Sprint 1/2 arithmetic approximation)
  - umm-al-qura         (astronomical approximation of the real UAQ rule)
  - declared            (demo: empty overrides, falls back to arithmetic)
  - local-observation   (demo: empty sightings, falls back to arithmetic)

Run:
    uvicorn waqt.api:app --reload --port 8000

Try:
    curl "http://localhost:8000/v1/waqt?lat=9.0192&lon=38.7525"
    curl "http://localhost:8000/v1/waqt?lat=9.0192&lon=38.7525&elevation_m=2400"
    curl "http://localhost:8000/v1/waqt?lat=-17.7134&lon=178.0650"   # Fiji, date-line case
    curl "http://localhost:8000/v1/waqt?lat=21.4225&lon=39.8262&calendar_provider=umm-al-qura"
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, RedirectResponse

from .core import AstronomyProfile, Location, compute_waqt
from .calendar_providers import (
    ArithmeticTabularProvider,
    DeclaredProvider,
    LocalObservationProvider,
    UmmAlQuraProvider,
)
from .timescale import DEFAULT_TIMESCALE_PROVIDER
from .timezone_provider import DEFAULT_TIMEZONE_PROVIDER, ManualTimezoneProvider

app = FastAPI(
    title="Waqt API",
    version="0.3.0",
    description=(
        "Reference implementation of the Waqt Core Time Model v0.1, "
        "with Sprint 2's location/astronomy corrections and Sprint 3's "
        "pluggable calendar provider system. "
        "See SCOPE.md, SPRINT-2-REPORT.md, SPRINT-3-REPORT.md."
    ),
)

# Lazy construction: UmmAlQuraProvider() triggers an ephem calculation;
# wrap each entry in a lambda so the object is created only when the
# endpoint is first called, not at import time.
_CALENDAR_PROVIDER_FACTORIES = {
    "arithmetic-tabular": lambda: ArithmeticTabularProvider(),
    "umm-al-qura":        lambda: UmmAlQuraProvider(),
    # Demo variants of the data-driven providers — backed by empty
    # dictionaries so they immediately fall through to the arithmetic
    # fallback. Exposed here so they are demonstrable via /docs without
    # needing any per-deployment configuration.
    "declared":           lambda: DeclaredProvider(overrides={}, fallback=ArithmeticTabularProvider()),
    "local-observation":  lambda: LocalObservationProvider(sightings={}, fallback=ArithmeticTabularProvider()),
}
_CALENDAR_PROVIDERS: dict[str, object] = {}  # cache of already-constructed instances


def _get_provider(name: str):
    """Lazy-construct and cache calendar providers."""
    if name not in _CALENDAR_PROVIDERS:
        factory = _CALENDAR_PROVIDER_FACTORIES.get(name)
        if factory is None:
            return None
        _CALENDAR_PROVIDERS[name] = factory()
    return _CALENDAR_PROVIDERS[name]


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.get("/v1/waqt")
def get_waqt(
    lat: float = Query(..., ge=-90, le=90, description="Latitude, WGS84 degrees"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude, WGS84 degrees"),
    elevation_m: float = Query(0.0, ge=0, description="Elevation, metres above sea level"),
    instant: Optional[str] = Query(None, description="ISO 8601 UTC instant; defaults to now"),
    timezone_override: Optional[str] = Query(
        None,
        description="IANA zone to force (e.g. 'Africa/Addis_Ababa'), skipping lookup",
    ),
    fajr_angle: float = Query(18.0, description="Fajr depression angle, degrees"),
    isha_angle: float = Query(17.0, description="Isha depression angle, degrees"),
    asr_ratio: float = Query(1.0, description="Asr shadow ratio: 1.0 = standard, 2.0 = Hanafi"),
    calendar_provider: str = Query(
        "arithmetic-tabular",
        description=f"One of: {', '.join(_CALENDAR_PROVIDER_FACTORIES)}",
    ),
):
    if instant is None:
        t = datetime.now(timezone.utc)
    else:
        try:
            t = datetime.fromisoformat(instant.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(400, f"Could not parse instant: {instant!r}")

    provider = _get_provider(calendar_provider)
    if provider is None:
        raise HTTPException(
            400,
            f"Unknown calendar_provider {calendar_provider!r}. "
            f"Available: {list(_CALENDAR_PROVIDER_FACTORIES)}",
        )

    location = Location(lat=lat, lon=lon, elevation_m=elevation_m)
    profile = AstronomyProfile(
        name="custom", fajr_angle_deg=fajr_angle, isha_angle_deg=isha_angle, asr_shadow_ratio=asr_ratio
    )
    tz_provider = (
        ManualTimezoneProvider(timezone_override) if timezone_override else DEFAULT_TIMEZONE_PROVIDER
    )

    r = compute_waqt(
        t,
        location,
        provider,
        profile,
        tz_provider=tz_provider,
        timescale=DEFAULT_TIMESCALE_PROVIDER,
    )

    body = {
        "status": r.status,
        "instant": _iso(r.instant),
        "location": {"lat": r.location_lat, "lon": r.location_lon, "elevation_m": r.location_elevation_m},
        "timezone": r.timezone_name,
        "spec": "waqt-core/0.1",
        "computation": {
            "timescale_model": r.timescale_model,
            "delta_t_seconds": r.delta_t_seconds,
        },
    }

    if r.status != "OK":
        body["undefined_reason"] = r.undefined_reason
        body["day"] = {"maghrib_open": _iso(r.day_start_maghrib), "maghrib_close": _iso(r.day_end_maghrib)}
        return JSONResponse(body, status_code=200)

    body.update(
        {
            "hijri": {
                "date": r.hijri_date.iso_like(),
                "display": str(r.hijri_date),
                "weekday": r.weekday,
                "provider": r.hijri_date.provider,
                "version": r.hijri_date.version,
            },
            "day": {
                "maghrib_open": _iso(r.day_start_maghrib),
                "maghrib_close": _iso(r.day_end_maghrib),
                "length_si_seconds": r.day_length_si_seconds,
                "note": r.hour_length_note,
            },
            "waqt": {"reading": r.hour_reading, "display": f"Waqt {r.hour_reading}"},
            "events": [
                {"name": e.name, "instant": _iso(e.instant), "reading": e.hour_reading} for e in r.events
            ],
            "next_event": (
                {"name": r.next_event.name, "instant": _iso(r.next_event.instant), "countdown": r.next_event_countdown}
                if r.next_event
                else None
            ),
            "profile": {
                "name": r.profile.name,
                "fajr_angle_deg": r.profile.fajr_angle_deg,
                "isha_angle_deg": r.profile.isha_angle_deg,
                "asr_shadow_ratio": r.profile.asr_shadow_ratio,
            },
        }
    )
    return JSONResponse(body, status_code=200)


@app.get("/v1/health")
def health():
    return {"status": "ok", "spec": "waqt-core/0.1"}

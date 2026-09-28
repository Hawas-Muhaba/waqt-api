"""
waqt_client.client — WaqtClient, the synchronous client.

Thin over the `/v1/*` HTTP/JSON contract: every method here builds query
parameters (via `_requests.py`), makes exactly one HTTP call, unwraps the
response envelope (`_envelope.py`), and returns a typed object
(`types.py`). No method recomputes a Waqt rule, retries a "wrong" answer,
or second-guesses the server -- that is precisely what the Sprint 9 brief
means by "the SDK should not become another implementation of Waqt's
rules."

For an endpoint this SDK hasn't grown a typed wrapper for yet, `.request()`
is the same envelope-aware escape hatch every typed method is built on --
it raises the same `WaqtApiError` and returns the same unwrapped `data`
dict, so a caller is never blocked on a new SDK release to reach a field
the HTTP contract already exposes. See docs/API.md, docs/SCHEDULING.md,
and docs/INSTITUTIONAL.md for every endpoint this covers.
"""

from __future__ import annotations

from typing import Any, Optional

import httpx

from . import _requests as R
from ._envelope import unwrap
from .config import WaqtClientConfig
from .errors import WaqtTransportError
from .types import (
    BoundaryCrossingResult,
    CalendarProviderInfo,
    ConversionResult,
    InstantRepresentation,
    InstitutionalCalendarResult,
    LocationInfo,
    SchedulingResult,
    WaqtResponse,
)


class WaqtClient:
    """Synchronous Waqt API client.

    >>> client = WaqtClient(base_url="http://localhost:8000")
    >>> resp = client.get_waqt(lat=9.0192, lon=38.7525)
    >>> resp.status
    'OK'

    Also usable as a context manager (`with WaqtClient(...) as client:`),
    which closes the underlying connection pool on exit.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        config: Optional[WaqtClientConfig] = None,
        transport: Optional[httpx.BaseTransport] = None,
        **kwargs: Any,
    ):
        self.config = config or WaqtClientConfig()
        if base_url is not None:
            self.config.base_url = base_url
        for k, v in kwargs.items():
            if hasattr(self.config, k):
                setattr(self.config, k, v)

        # `transport` is an escape hatch for tests (an in-process ASGI
        # transport instead of a real socket) and for advanced proxy/mocking
        # setups -- ordinary use never needs it.
        self._http = httpx.Client(
            base_url=self.config.base_url,
            timeout=self.config.timeout_seconds,
            headers={"User-Agent": self.config.user_agent, **self.config.extra_headers},
            transport=transport,
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "WaqtClient":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()

    # -- transport -----------------------------------------------------

    def request(self, method: str, path: str, *, params: Optional[dict] = None, json: Optional[dict] = None) -> dict:
        """Escape hatch: raw call to any `/v1/*` path, returning the
        unwrapped `data` dict. Every typed method below is built on this."""
        try:
            resp = self._http.request(method, path, params=params, json=json)
        except httpx.TimeoutException as exc:
            raise WaqtTransportError(f"Request to {path} timed out.", cause=exc) from exc
        except httpx.HTTPError as exc:
            raise WaqtTransportError(f"Request to {path} failed: {exc}", cause=exc) from exc

        try:
            body = resp.json()
        except ValueError:
            body = None
        return unwrap(resp.status_code, body, self.config.on_version_mismatch)

    def _get(self, path: str, params: dict) -> dict:
        return self.request("GET", path, params=params)

    # -- core time model -------------------------------------------------

    def get_waqt(self, lat: float, lon: float, **kwargs: Any) -> WaqtResponse:
        """`GET /v1/waqt` — full result: day boundary, Waqt clock
        position, all six events, Hijri date, timezone, computation."""
        kwargs.setdefault("calendar_provider", self.config.default_calendar_provider)
        kwargs.setdefault("fajr_angle", self.config.default_fajr_angle_deg)
        kwargs.setdefault("isha_angle", self.config.default_isha_angle_deg)
        kwargs.setdefault("asr_ratio", self.config.default_asr_shadow_ratio)
        kwargs.setdefault("timezone_override", self.config.default_timezone_override)
        params = R.waqt_params(lat, lon, **kwargs)
        return WaqtResponse.from_json(self._get("/v1/waqt", params))

    def get_day(self, lat: float, lon: float, **kwargs: Any) -> WaqtResponse:
        """`GET /v1/day` — just the day boundary (no calendar, no events)."""
        params = R.day_params(lat, lon, **kwargs)
        return WaqtResponse.from_json(self._get("/v1/day", params))

    def get_events(self, lat: float, lon: float, **kwargs: Any) -> WaqtResponse:
        """`GET /v1/events` — just the six solar/prayer events."""
        params = R.events_params(lat, lon, **kwargs)
        return WaqtResponse.from_json(self._get("/v1/events", params))

    def get_location(self, lat: float, lon: float, **kwargs: Any) -> LocationInfo:
        """`GET /v1/location` — timezone + local civil date for a place."""
        params = R.location_params(lat, lon, **kwargs)
        return LocationInfo.from_json(self._get("/v1/location", params))

    # -- calendars ---------------------------------------------------------

    def get_hijri(self, **kwargs: Any) -> WaqtResponse:
        """`GET /v1/hijri` — Gregorian date -> Hijri date. Location-independent."""
        params = R.hijri_params(**kwargs)
        data = self._get("/v1/hijri", params)
        # Reuses WaqtResponse's hijri/weekday fields even though this
        # endpoint's own shape is smaller -- from_json tolerates missing keys.
        return WaqtResponse.from_json({
            "status": "OK", "instant": None, "location": None, "timezone": None,
            "undefined_reason": None, "day": None, "hijri": data.get("hijri"),
            "weekday": data.get("weekday"), "waqt": None, "events": [], "next_event": None,
            "profile": None, "computation": None, **{"gregorian_date": data.get("gregorian_date")},
        })

    def list_calendar_providers(self) -> list:
        """`GET /v1/calendar` — every registered calendar provider."""
        data = self._get("/v1/calendar", {})
        return [CalendarProviderInfo.from_json(p) for p in data.get("providers", [])]

    def convert(self, direction: str, **kwargs: Any) -> ConversionResult:
        """`GET /v1/conversions` — bidirectional Gregorian <-> Hijri,
        independent of instant/location/astronomy. `direction` is
        `'to-hijri'` or `'to-gregorian'`."""
        params = R.conversions_params(direction, **kwargs)
        return ConversionResult.from_json(self._get("/v1/conversions", params))

    def represent_instant(self, instant=None, lat: Optional[float] = None, lon: Optional[float] = None, **kwargs: Any) -> InstantRepresentation:
        """`GET /v1/calendar/convert?direction=instant-to-calendars` —
        an instant as UTC-Gregorian always, plus local-civil-Gregorian and
        a Waqt day/position if `lat`/`lon` are given."""
        params = R.calendar_convert_params(
            direction="instant-to-calendars", instant=instant, lat=lat, lon=lon, **kwargs
        )
        return InstantRepresentation.from_json(self._get("/v1/calendar/convert", params))

    def waqt_day_for_gregorian_date(self, date, lat: float, lon: float, **kwargs: Any) -> InstantRepresentation:
        """`GET /v1/calendar/convert?direction=gregorian-date-to-waqt` —
        the reverse: a Gregorian civil date + place -> the Waqt day whose
        closing Maghrib falls on that date."""
        params = R.calendar_convert_params(
            direction="gregorian-date-to-waqt", date=date, lat=lat, lon=lon, **kwargs
        )
        return InstantRepresentation.from_json(self._get("/v1/calendar/convert", params))

    def boundary_crossing(self, start, end, lat: float, lon: float, **kwargs: Any) -> BoundaryCrossingResult:
        """`GET /v1/calendar/boundary-crossing` — does the half-open span
        `[start, end)` cross civil midnight, Maghrib, both, or neither."""
        params = R.boundary_crossing_params(start, end, lat, lon, **kwargs)
        return BoundaryCrossingResult.from_json(self._get("/v1/calendar/boundary-crossing", params))

    # -- scheduling (Sprint 6) ----------------------------------------------

    def schedule_snapshot(self, lat: float, lon: float, **kwargs: Any) -> SchedulingResult:
        """`GET /v1/schedule/snapshot` — which Waqt day an instant falls
        in, plus its neighbors. See docs/SCHEDULING.md."""
        params = R.snapshot_params(lat, lon, **kwargs)
        return SchedulingResult.from_json(self._get("/v1/schedule/snapshot", params))

    def schedule_span(self, lat: float, lon: float, start, end, **kwargs: Any) -> SchedulingResult:
        """`GET /v1/schedule/span` — which Waqt days/boundaries a span touches."""
        params = R.span_params(lat, lon, start, end, **kwargs)
        return SchedulingResult.from_json(self._get("/v1/schedule/span", params))

    def schedule_resolve(self, body: Any) -> SchedulingResult:
        """`POST /v1/schedule/resolve` — resolve a scheduling operation
        (e.g. `resolve_interval`) against a location/anchor. `body` is the
        same JSON shape docs/SCHEDULING.md documents; this SDK does not
        model every operation type, since the endpoint's own request body
        already is the wire contract."""
        return SchedulingResult.from_json(self.request("POST", "/v1/schedule/resolve", json=R.body_json(body)))

    # -- institutional calendars (Sprint 7) ----------------------------------

    def institutional_week(self, lat: float, lon: float, **kwargs: Any) -> InstitutionalCalendarResult:
        """`GET /v1/institutional/week`."""
        params = R.institutional_week_params(lat, lon, **kwargs)
        return InstitutionalCalendarResult.from_json(self._get("/v1/institutional/week", params))

    def institutional_fiscal_year(self, **kwargs: Any) -> InstitutionalCalendarResult:
        """`GET /v1/institutional/fiscal-year`."""
        return InstitutionalCalendarResult.from_json(self._get("/v1/institutional/fiscal-year", kwargs))

    def institutional_academic_year(self, **kwargs: Any) -> InstitutionalCalendarResult:
        """`GET /v1/institutional/academic-year`."""
        return InstitutionalCalendarResult.from_json(self._get("/v1/institutional/academic-year", kwargs))

    def institutional_default_profile(self, **kwargs: Any) -> InstitutionalCalendarResult:
        """`GET /v1/institutional/profile`."""
        params = R.institutional_profile_params(**kwargs)
        return InstitutionalCalendarResult.from_json(self._get("/v1/institutional/profile", params))

    def institutional_fiscal_year_resolve(self, body: Any) -> InstitutionalCalendarResult:
        """`POST /v1/institutional/fiscal-year/resolve`."""
        return InstitutionalCalendarResult.from_json(
            self.request("POST", "/v1/institutional/fiscal-year/resolve", json=R.body_json(body))
        )

    def institutional_academic_year_resolve(self, body: Any) -> InstitutionalCalendarResult:
        """`POST /v1/institutional/academic-year/resolve`."""
        return InstitutionalCalendarResult.from_json(
            self.request("POST", "/v1/institutional/academic-year/resolve", json=R.body_json(body))
        )

    # -- misc -------------------------------------------------------------

    def health(self) -> dict:
        """`GET /v1/health`."""
        resp = self._http.get("/v1/health")
        return resp.json()

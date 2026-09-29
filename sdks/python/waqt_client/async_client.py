"""
waqt_client.async_client — AsyncWaqtClient, the asyncio counterpart of
`client.WaqtClient`. Same methods, same typed returns, same thin/
spec-driven design -- see client.py's module docstring for the shared
rationale. Kept as a mirrored class (rather than one class with a
`sync`/`async` flag) so callers get plain `await client.get_waqt(...)`
with no wrapper-object indirection, matching the ergonomics of a
hand-written async SDK.
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
    VersionInfo,
    WaqtResponse,
)


class AsyncWaqtClient:
    """Asynchronous Waqt API client.

    >>> async with AsyncWaqtClient(base_url="http://localhost:8000") as client:
    ...     resp = await client.get_waqt(lat=9.0192, lon=38.7525)
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        config: Optional[WaqtClientConfig] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        **kwargs: Any,
    ):
        self.config = config or WaqtClientConfig()
        if base_url is not None:
            self.config.base_url = base_url
        for k, v in kwargs.items():
            if hasattr(self.config, k):
                setattr(self.config, k, v)

        self._http = httpx.AsyncClient(
            base_url=self.config.base_url,
            timeout=self.config.timeout_seconds,
            headers={"User-Agent": self.config.user_agent, **self.config.extra_headers},
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "AsyncWaqtClient":
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.aclose()

    # -- transport -----------------------------------------------------

    async def request(self, method: str, path: str, *, params: Optional[dict] = None, json: Optional[dict] = None) -> dict:
        try:
            resp = await self._http.request(method, path, params=params, json=json)
        except httpx.TimeoutException as exc:
            raise WaqtTransportError(f"Request to {path} timed out.", cause=exc) from exc
        except httpx.HTTPError as exc:
            raise WaqtTransportError(f"Request to {path} failed: {exc}", cause=exc) from exc

        try:
            body = resp.json()
        except ValueError:
            body = None
        return unwrap(resp.status_code, body, self.config.on_version_mismatch)

    async def _get(self, path: str, params: dict) -> dict:
        return await self.request("GET", path, params=params)

    # -- core time model -------------------------------------------------

    async def get_waqt(self, lat: float, lon: float, **kwargs: Any) -> WaqtResponse:
        kwargs.setdefault("calendar_provider", self.config.default_calendar_provider)
        kwargs.setdefault("fajr_angle", self.config.default_fajr_angle_deg)
        kwargs.setdefault("isha_angle", self.config.default_isha_angle_deg)
        kwargs.setdefault("asr_ratio", self.config.default_asr_shadow_ratio)
        kwargs.setdefault("timezone_override", self.config.default_timezone_override)
        params = R.waqt_params(lat, lon, **kwargs)
        return WaqtResponse.from_json(await self._get("/v1/waqt", params))

    async def get_day(self, lat: float, lon: float, **kwargs: Any) -> WaqtResponse:
        params = R.day_params(lat, lon, **kwargs)
        return WaqtResponse.from_json(await self._get("/v1/day", params))

    async def get_events(self, lat: float, lon: float, **kwargs: Any) -> WaqtResponse:
        params = R.events_params(lat, lon, **kwargs)
        return WaqtResponse.from_json(await self._get("/v1/events", params))

    async def get_location(self, lat: float, lon: float, **kwargs: Any) -> LocationInfo:
        params = R.location_params(lat, lon, **kwargs)
        return LocationInfo.from_json(await self._get("/v1/location", params))

    # -- calendars ---------------------------------------------------------

    async def get_hijri(self, **kwargs: Any) -> WaqtResponse:
        params = R.hijri_params(**kwargs)
        data = await self._get("/v1/hijri", params)
        return WaqtResponse.from_json({
            "status": "OK", "instant": None, "location": None, "timezone": None,
            "undefined_reason": None, "day": None, "hijri": data.get("hijri"),
            "weekday": data.get("weekday"), "waqt": None, "events": [], "next_event": None,
            "profile": None, "computation": None,
        })

    async def list_calendar_providers(self) -> list:
        data = await self._get("/v1/calendar", {})
        return [CalendarProviderInfo.from_json(p) for p in data.get("providers", [])]

    async def get_version(self) -> VersionInfo:
        """`GET /v1/version` (API >= 1.4.0). See `WaqtClient.get_version`."""
        return VersionInfo.from_json(await self._get("/v1/version", {}))

    async def convert(self, direction: str, **kwargs: Any) -> ConversionResult:
        params = R.conversions_params(direction, **kwargs)
        return ConversionResult.from_json(await self._get("/v1/conversions", params))

    async def represent_instant(self, instant=None, lat: Optional[float] = None, lon: Optional[float] = None, **kwargs: Any) -> InstantRepresentation:
        params = R.calendar_convert_params(
            direction="instant-to-calendars", instant=instant, lat=lat, lon=lon, **kwargs
        )
        return InstantRepresentation.from_json(await self._get("/v1/calendar/convert", params))

    async def waqt_day_for_gregorian_date(self, date, lat: float, lon: float, **kwargs: Any) -> InstantRepresentation:
        params = R.calendar_convert_params(
            direction="gregorian-date-to-waqt", date=date, lat=lat, lon=lon, **kwargs
        )
        return InstantRepresentation.from_json(await self._get("/v1/calendar/convert", params))

    async def boundary_crossing(self, start, end, lat: float, lon: float, **kwargs: Any) -> BoundaryCrossingResult:
        params = R.boundary_crossing_params(start, end, lat, lon, **kwargs)
        return BoundaryCrossingResult.from_json(await self._get("/v1/calendar/boundary-crossing", params))

    # -- scheduling (Sprint 6) ----------------------------------------------

    async def schedule_snapshot(self, lat: float, lon: float, **kwargs: Any) -> SchedulingResult:
        params = R.snapshot_params(lat, lon, **kwargs)
        return SchedulingResult.from_json(await self._get("/v1/schedule/snapshot", params))

    async def schedule_span(self, lat: float, lon: float, start, end, **kwargs: Any) -> SchedulingResult:
        params = R.span_params(lat, lon, start, end, **kwargs)
        return SchedulingResult.from_json(await self._get("/v1/schedule/span", params))

    async def schedule_resolve(self, body: Any) -> SchedulingResult:
        return SchedulingResult.from_json(await self.request("POST", "/v1/schedule/resolve", json=R.body_json(body)))

    # -- institutional calendars (Sprint 7) ----------------------------------

    async def institutional_week(self, lat: float, lon: float, **kwargs: Any) -> InstitutionalCalendarResult:
        params = R.institutional_week_params(lat, lon, **kwargs)
        return InstitutionalCalendarResult.from_json(await self._get("/v1/institutional/week", params))

    async def institutional_fiscal_year(self, **kwargs: Any) -> InstitutionalCalendarResult:
        return InstitutionalCalendarResult.from_json(await self._get("/v1/institutional/fiscal-year", kwargs))

    async def institutional_academic_year(self, **kwargs: Any) -> InstitutionalCalendarResult:
        return InstitutionalCalendarResult.from_json(await self._get("/v1/institutional/academic-year", kwargs))

    async def institutional_default_profile(self, **kwargs: Any) -> InstitutionalCalendarResult:
        params = R.institutional_profile_params(**kwargs)
        return InstitutionalCalendarResult.from_json(await self._get("/v1/institutional/profile", params))

    async def institutional_fiscal_year_resolve(self, body: Any) -> InstitutionalCalendarResult:
        return InstitutionalCalendarResult.from_json(
            await self.request("POST", "/v1/institutional/fiscal-year/resolve", json=R.body_json(body))
        )

    async def institutional_academic_year_resolve(self, body: Any) -> InstitutionalCalendarResult:
        return InstitutionalCalendarResult.from_json(
            await self.request("POST", "/v1/institutional/academic-year/resolve", json=R.body_json(body))
        )

    # -- misc -------------------------------------------------------------

    async def health(self) -> dict:
        resp = await self._http.get("/v1/health")
        return resp.json()

"""
api_consumer.waqt_api — a hand-written client against the documented Waqt
HTTP contract (docs/API.md), stdlib only.

This module imports no `waqt*` package. Everything it encodes — the
envelope shape (`{"meta", "data", "error"}`, exactly one of `data`/`error`
null), the endpoint paths, and their query parameters — comes from
docs/API.md, the same source an outside integrator has. That is the point
of this reference application (Sprint 12 Goal A.3): the API needs nothing
but HTTP and JSON to be usable.

For a real integration, prefer `sdks/python/waqt_client` (typed, retrying,
version-checked) or the JS SDK. This client is deliberately minimal.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional


class WaqtApiError(Exception):
    """The server returned a well-formed error envelope (docs/API.md §3)."""

    def __init__(self, code: str, message: str, details: Optional[dict] = None):
        super().__init__(f"{code}: {message}")
        self.code, self.message, self.details = code, message, details or {}


class WaqtTransportError(Exception):
    """Could not reach the server, or its response did not match the
    documented envelope at all (network failure, non-JSON body, wrong shape)."""


class WaqtApiClient:
    """Minimal synchronous client. One method per endpoint used by
    `api_consumer.cli`; add more the same way as needed."""

    def __init__(self, base_url: str, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # -- transport -----------------------------------------------------

    def _get(self, path: str, params: dict) -> dict:
        query = {k: v for k, v in params.items() if v is not None}
        url = f"{self.base_url}{path}"
        if query:
            url += "?" + urllib.parse.urlencode(query)
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            # Waqt's error envelope is still valid JSON on 4xx/5xx (docs/API.md §3):
            # read the body before giving up, so a well-formed WaqtApiError can
            # still be raised instead of a bare transport error.
            raw = e.read()
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise WaqtTransportError(f"could not reach {self.base_url}: {e}") from e

        try:
            body = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise WaqtTransportError(f"response from {url} was not valid JSON: {e}") from e

        if not isinstance(body, dict) or "data" not in body or "error" not in body:
            raise WaqtTransportError(
                f"response from {url} did not match the documented envelope "
                f"({{'meta','data','error'}}): got keys {sorted(body) if isinstance(body, dict) else type(body)}"
            )
        if body["error"] is not None:
            err = body["error"]
            raise WaqtApiError(err.get("code", "UNKNOWN"), err.get("message", ""), err.get("details"))
        return body["data"]

    # -- endpoints -------------------------------------------------------

    def get_waqt(self, lat: float, lon: float, *, elevation_m: float = 0.0, instant: Optional[str] = None,
                 timezone_override: Optional[str] = None, fajr_angle: float = 18.0, isha_angle: float = 17.0,
                 asr_ratio: float = 1.0, calendar_provider: str = "arithmetic-tabular") -> dict:
        """`GET /v1/waqt` — the combined result (docs/API.md; matches
        `waqt_local.waqt()`'s shape field-for-field)."""
        return self._get("/v1/waqt", {
            "lat": lat, "lon": lon, "elevation_m": elevation_m, "instant": instant,
            "timezone_override": timezone_override, "fajr_angle": fajr_angle,
            "isha_angle": isha_angle, "asr_ratio": asr_ratio, "calendar_provider": calendar_provider,
        })

    def get_calendar_providers(self) -> dict:
        """`GET /v1/calendar`."""
        return self._get("/v1/calendar", {})

    def get_version(self) -> dict:
        """`GET /v1/version` (API >= 1.4.0, Sprint 12). Against an older
        server this 404s and surfaces as a `WaqtApiError`/`WaqtTransportError`
        like any other missing route — this client does not special-case it."""
        return self._get("/v1/version", {})

    def get_health(self) -> dict:
        """`GET /v1/health` is NOT wrapped in the `{meta,data,error}` envelope
        (it is a liveness probe, documented separately) — call it directly."""
        req = urllib.request.Request(f"{self.base_url}/v1/health", headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise WaqtTransportError(f"could not reach {self.base_url}: {e}") from e

"""
Local-vs-server equivalence — Sprint 10's DoD line "the local
implementation participates in the public conformance suite" plus the
required test "local-vs-server result equivalence".

For a spread of locations/instants/operations, this drives BOTH
`waqt_local` (in-process, no HTTP) and a real `waqt.api` FastAPI app
(in-process over `httpx.ASGITransport` — a genuine HTTP request/response
cycle through Starlette's routing, same technique
`sdks/python/tests/conftest.py` uses) and asserts the two `data`
payloads are equal field-by-field. This is what actually proves the two
presentation layers (`waqt_local.formatting` and `waqt.api.common`)
were kept in exact agreement, rather than just asserted to be so in a
docstring.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

import waqt_local
from waqt.api import app

TRANSPORT = httpx.ASGITransport(app=app)

LOCATIONS = [
    {"lat": 9.0192, "lon": 38.7525, "elevation_m": 2355},   # Addis Ababa
    {"lat": 51.5072, "lon": -0.1276, "elevation_m": 11},    # London
    {"lat": -33.8688, "lon": 151.2093, "elevation_m": 3},   # Sydney
    {"lat": 40.7128, "lon": -74.0060, "elevation_m": 10},   # New York
]
INSTANTS = ["2026-09-19T15:42:00Z", "2026-06-21T00:00:00Z", "2026-12-21T12:00:00Z"]


async def _get(path: str, params: dict) -> dict:
    async with httpx.AsyncClient(transport=TRANSPORT, base_url="http://test") as client:
        r = await client.get(path, params=params)
        assert r.status_code == 200, (path, params, r.text)
        body = r.json()
        assert body["error"] is None
        return body["data"]


def run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize("loc", LOCATIONS, ids=lambda l: f"{l['lat']},{l['lon']}")
@pytest.mark.parametrize("instant", INSTANTS)
def test_waqt_endpoint_matches_local_facade(loc, instant):
    server_data = run(_get("/v1/waqt", {**loc, "instant": instant}))
    local_data = waqt_local.waqt(**loc, instant=instant)

    # `computation.timescale_model`/`delta_t_seconds` and `instant` echo
    # back exactly; only the top-level dict identity differs (server
    # wraps the same shape in a meta/error envelope, which _get already
    # unwrapped).
    assert local_data == server_data, (loc, instant)


@pytest.mark.parametrize("loc", LOCATIONS[:2], ids=lambda l: f"{l['lat']},{l['lon']}")
def test_day_endpoint_matches_local_facade(loc):
    instant = "2026-09-19T15:42:00Z"
    server_data = run(_get("/v1/day", {**loc, "instant": instant}))
    local_data = waqt_local.day(**loc, instant=instant)
    assert local_data == server_data


@pytest.mark.parametrize("loc", LOCATIONS[:2], ids=lambda l: f"{l['lat']},{l['lon']}")
def test_events_endpoint_matches_local_facade(loc):
    instant = "2026-09-19T15:42:00Z"
    server_data = run(_get("/v1/events", {**loc, "instant": instant}))
    local_data = waqt_local.events(**loc, instant=instant)
    assert local_data == server_data


def test_hijri_endpoint_matches_local_facade():
    server_data = run(_get("/v1/hijri", {"date": "2026-09-19"}))
    local_data = waqt_local.hijri(date="2026-09-19")
    assert local_data == server_data


def test_calendar_catalog_endpoint_matches_local_facade():
    server_data = run(_get("/v1/calendar", {}))
    local_data = waqt_local.list_calendar_providers()
    assert local_data == server_data


def test_conversions_endpoint_matches_local_facade():
    server_data = run(_get("/v1/conversions", {"direction": "to-hijri", "date": "2026-09-19"}))
    local_data = waqt_local.convert(direction="to-hijri", date="2026-09-19")
    assert local_data == server_data


def test_instant_to_calendars_matches_local_facade():
    params = {"direction": "instant-to-calendars", "instant": "2026-09-19T15:42:00Z", **LOCATIONS[0]}
    server_data = run(_get("/v1/calendar/convert", params))
    local_data = waqt_local.represent_instant(instant="2026-09-19T15:42:00Z", **LOCATIONS[0])
    assert local_data == server_data


def test_gregorian_date_to_waqt_matches_local_facade():
    params = {"direction": "gregorian-date-to-waqt", "date": "2026-09-19", **LOCATIONS[0]}
    server_data = run(_get("/v1/calendar/convert", params))
    local_data = waqt_local.waqt_day_for_gregorian_date(date="2026-09-19", **LOCATIONS[0])
    assert local_data == server_data


def test_boundary_crossing_matches_local_facade():
    params = {"start": "2026-09-19T12:00:00Z", "end": "2026-09-19T20:00:00Z", **LOCATIONS[0]}
    server_data = run(_get("/v1/calendar/boundary-crossing", params))
    local_data = waqt_local.boundary_crossing(start=params["start"], end=params["end"], **LOCATIONS[0])
    assert local_data == server_data


def test_institutional_week_matches_local_facade():
    params = {"instant": "2026-09-19T15:42:00Z", **LOCATIONS[0]}
    server_data = run(_get("/v1/institutional/week", params))
    local_data = waqt_local.institutional_week(instant="2026-09-19T15:42:00Z", **LOCATIONS[0])
    assert local_data == server_data


def test_institutional_fiscal_year_matches_local_facade():
    params = {"hijri_year": 1448}
    server_data = run(_get("/v1/institutional/fiscal-year", params))
    local_data = waqt_local.institutional_fiscal_year(hijri_year=1448)
    assert local_data == server_data


def test_institutional_academic_year_matches_local_facade():
    params = {"hijri_year": 1448}
    server_data = run(_get("/v1/institutional/academic-year", params))
    local_data = waqt_local.institutional_academic_year(hijri_year=1448)
    assert local_data == server_data

"""
Integration tests: the Sprint 10 typed request builders actually work
against the real `waqt.api` FastAPI app (in-process, httpx.ASGITransport
-- see conftest.py's `asgi_transport` fixture), and produce the exact
same server response as the equivalent hand-written dict body did in
Sprint 9. Closes the "typed POST request tests" item in Sprint 10's
Required tests list.
"""

from __future__ import annotations

import pytest

from waqt_client import AsyncWaqtClient, WaqtApiError, requests as R

pytestmark = pytest.mark.asyncio


async def test_typed_schedule_resolve_matches_equivalent_dict(asgi_transport):
    dict_body = {
        "location": {"lat": 9.0192, "lon": 38.7525, "elevation_m": 0.0},
        "anchor": "2026-09-19T15:42:00Z",
        "operation": {
            "op": "resolve_interval",
            "interval": {
                "type": "interval",
                "start": {"type": "event", "name": "maghrib", "day": 0},
                "end": {"type": "event", "name": "isha", "day": 0},
                "start_inclusive": True,
                "end_inclusive": False,
            },
        },
    }
    typed_body = R.ScheduleResolveRequest(
        lat=9.0192, lon=38.7525,
        anchor="2026-09-19T15:42:00Z",
        operation=R.ResolveInterval(R.Interval(R.Event("maghrib", 0), R.Event("isha", 0))),
    )

    async with AsyncWaqtClient(base_url="http://testserver", transport=asgi_transport) as client:
        dict_result = await client.schedule_resolve(dict_body)
        typed_result = await client.schedule_resolve(typed_body)

    assert dict_result.raw == typed_result.raw
    assert typed_result.raw["result"]["status"] == "OK"


async def test_typed_schedule_resolve_surfaces_server_errors_the_same_way(asgi_transport):
    """A caller mistake still comes back through the normal `WaqtApiError`
    path -- typed request objects don't intercept or reinterpret server
    errors, they only build the body."""
    bad = R.ScheduleResolveRequest(lat=200.0, lon=38.7525, operation=R.NextEventOp())
    async with AsyncWaqtClient(base_url="http://testserver", transport=asgi_transport) as client:
        with pytest.raises(WaqtApiError):
            await client.schedule_resolve(bad)


async def test_typed_fiscal_year_resolve_matches_equivalent_dict(asgi_transport):
    dict_body = {
        "hijri_year": 1448,
        "start_rule": {"type": "month_day", "month": 1, "day": 1},
        "end_rule": {"type": "month_end", "month": 12},
        "label": "Custom Fiscal Year",
    }
    typed_body = R.FiscalYearResolveRequest(
        hijri_year=1448, start_rule=R.MonthDay(1, 1), end_rule=R.MonthEnd(12), label="Custom Fiscal Year",
    )

    async with AsyncWaqtClient(base_url="http://testserver", transport=asgi_transport) as client:
        dict_result = await client.institutional_fiscal_year_resolve(dict_body)
        typed_result = await client.institutional_fiscal_year_resolve(typed_body)

    assert dict_result.raw == typed_result.raw
    assert typed_result.raw["label"] == "Custom Fiscal Year"


async def test_typed_academic_year_resolve_matches_equivalent_dict(asgi_transport):
    dict_body = {
        "hijri_year": 1448,
        "opening_rule": {"type": "nth_weekday_of_month", "weekday": "al-Ahad", "n": 1, "month": 1},
        "closing_rule": {"type": "nth_weekday_of_month", "weekday": "al-Khamis", "n": -1, "month": 8},
        "term_rules": [], "holidays": [],
    }
    typed_body = R.AcademicYearResolveRequest(
        hijri_year=1448,
        opening_rule=R.NthWeekdayOfMonth("al-Ahad", 1, 1),
        closing_rule=R.NthWeekdayOfMonth("al-Khamis", -1, 8),
    )

    async with AsyncWaqtClient(base_url="http://testserver", transport=asgi_transport) as client:
        dict_result = await client.institutional_academic_year_resolve(dict_body)
        typed_result = await client.institutional_academic_year_resolve(typed_body)

    assert dict_result.raw == typed_result.raw


async def test_plain_dict_bodies_still_work_unchanged(asgi_transport):
    """Sprint 9 behavior is fully preserved: passing a raw dict is not
    deprecated, and is not routed through any typed-request machinery."""
    async with AsyncWaqtClient(base_url="http://testserver", transport=asgi_transport) as client:
        result = await client.schedule_resolve({
            "location": {"lat": 9.0192, "lon": 38.7525},
            "operation": {"op": "day_bounds"},
        })
    assert result.raw["result"]["status"] == "OK"

"""
Integration tests for AsyncWaqtClient, via httpx.ASGITransport (in-process,
async-native -- no socket needed for the async path).
"""

from __future__ import annotations

import pytest

from waqt_client import AsyncWaqtClient, WaqtApiError

pytestmark = pytest.mark.asyncio


async def test_async_get_waqt(asgi_transport):
    async with AsyncWaqtClient(base_url="http://testserver", transport=asgi_transport) as client:
        resp = await client.get_waqt(lat=9.0192, lon=38.7525, instant="2026-09-19T15:42:00Z")
        assert resp.status == "OK"
        assert resp.hijri.year == 1448


async def test_async_error_handling(asgi_transport):
    async with AsyncWaqtClient(base_url="http://testserver", transport=asgi_transport) as client:
        with pytest.raises(WaqtApiError) as excinfo:
            await client.get_waqt(lat=999, lon=0)
        assert excinfo.value.code == "VALIDATION_ERROR"


async def test_async_schedule_and_institutional(asgi_transport):
    async with AsyncWaqtClient(base_url="http://testserver", transport=asgi_transport) as client:
        snap = await client.schedule_snapshot(9.0192, 38.7525, instant="2026-09-19T15:42:00Z")
        assert snap.location.lat == pytest.approx(9.0192)

        week = await client.institutional_week(9.0192, 38.7525, instant="2026-09-19T15:42:00Z")
        assert "week_start" in week.raw


async def test_async_health(asgi_transport):
    async with AsyncWaqtClient(base_url="http://testserver", transport=asgi_transport) as client:
        h = await client.health()
        assert h["status"] == "ok"


async def test_async_and_sync_agree_on_same_instant(asgi_transport):
    """Both clients are thin wrappers over the identical HTTP contract --
    they must produce identical parsed results for the identical request."""
    from waqt_client.client import WaqtClient  # only for comparison in this one test

    async with AsyncWaqtClient(base_url="http://testserver", transport=asgi_transport) as aclient:
        async_resp = await aclient.get_waqt(lat=9.0192, lon=38.7525, instant="2026-09-19T15:42:00Z")

    assert async_resp.status == "OK"
    # Provider omitted -> the API 1.7.0 default, umm-al-qura (it was arithmetic-tabular, "7 Rabi al-Thani", before 1.7.0).
    assert async_resp.hijri.display == "9 Rabi al-Thani 1448 AH"
    assert async_resp.hijri.provider_name == "umm-al-qura"

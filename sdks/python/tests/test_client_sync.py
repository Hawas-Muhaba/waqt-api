"""
Integration tests for the sync WaqtClient against the REAL FastAPI app,
via a real HTTP server (httpx's ASGITransport is async-only, so the sync
client -- which uses httpx.Client, a genuinely blocking transport -- is
tested through an actual bound socket started once per test session).
"""

from __future__ import annotations

import socket
import sys
import threading
import time
from pathlib import Path

import pytest
import uvicorn

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from waqt.api import app  # noqa: E402
from waqt_client import WaqtApiError, WaqtClient  # noqa: E402


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(scope="session")
def live_base_url():
    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(50):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=2)


@pytest.fixture
def client(live_base_url):
    with WaqtClient(base_url=live_base_url) as c:
        yield c


def test_get_waqt_ordinary(client):
    resp = client.get_waqt(lat=9.0192, lon=38.7525, instant="2026-09-19T15:42:00Z")
    assert resp.status == "OK"
    assert resp.hijri.year == 1448
    assert resp.event("maghrib").instant is not None


def test_get_waqt_polar_undefined(client):
    resp = client.get_waqt(lat=69.6492, lon=18.9553, instant="2026-06-21T12:00:00Z")
    assert resp.status == "UNDEFINED"
    assert resp.undefined_reason


def test_get_day_and_get_events_subset_shapes(client):
    day = client.get_day(lat=9.0192, lon=38.7525, instant="2026-09-19T15:42:00Z")
    assert day.day is not None
    events = client.get_events(lat=9.0192, lon=38.7525, instant="2026-09-19T15:42:00Z")
    assert len(events.events) == 6


def test_get_hijri(client):
    resp = client.get_hijri(date="2026-09-19")
    assert resp.hijri.year == 1448


def test_list_calendar_providers(client):
    providers = client.list_calendar_providers()
    names = {p.name for p in providers}
    assert {"arithmetic-tabular", "umm-al-qura", "declared", "local-observation"} <= names


def test_get_location(client):
    info = client.get_location(lat=9.0192, lon=38.7525, instant="2026-09-19T15:42:00Z")
    assert info.timezone.name == "Africa/Addis_Ababa"


def test_convert_to_hijri_and_to_gregorian_round_trip(client):
    to_hijri = client.convert("to-hijri", date="2026-09-19")
    hd = to_hijri.output["hijri"]
    to_greg = client.convert("to-gregorian", year=hd["year"], month=hd["month"], day=hd["day"])
    assert to_greg.output["gregorian_date"] == "2026-09-19"


def test_represent_instant_and_waqt_day_for_gregorian_date(client):
    rep = client.represent_instant(instant="2026-09-19T15:42:00Z", lat=9.0192, lon=38.7525)
    assert rep.gregorian_utc.date == "2026-09-19"
    assert rep.waqt_status == "OK"

    day_rep = client.waqt_day_for_gregorian_date("2026-09-20", lat=9.0192, lon=38.7525)
    assert day_rep.direction == "gregorian-date-to-waqt"
    assert day_rep.waqt_day.maghrib_close.date().isoformat() == "2026-09-20"


def test_boundary_crossing(client):
    result = client.boundary_crossing(
        "2026-09-19T00:00:00Z", "2026-09-20T00:00:00Z", lat=9.0192, lon=38.7525
    )
    assert result.crosses_civil_midnight is True
    assert result.crosses_maghrib is True


def test_schedule_snapshot_and_span(client):
    snap = client.schedule_snapshot(9.0192, 38.7525, instant="2026-09-19T15:42:00Z")
    assert snap.location.lat == pytest.approx(9.0192)

    span = client.schedule_span(9.0192, 38.7525, "2026-09-19T00:00:00Z", "2026-09-21T00:00:00Z")
    assert len(span.raw) > 0


def test_institutional_week_and_profile(client):
    week = client.institutional_week(9.0192, 38.7525, instant="2026-09-19T15:42:00Z")
    assert "week_start" in week.raw

    profile = client.institutional_default_profile()
    assert len(profile.raw) > 0


def test_error_raises_waqt_api_error_with_code_and_details(client):
    with pytest.raises(WaqtApiError) as excinfo:
        client.get_waqt(lat=999, lon=38.7525)
    assert excinfo.value.code == "VALIDATION_ERROR"
    assert excinfo.value.status_code == 422
    assert "errors" in excinfo.value.details


def test_invalid_instant_error(client):
    with pytest.raises(WaqtApiError) as excinfo:
        client.get_waqt(lat=9.0192, lon=38.7525, instant="not-a-date")
    assert excinfo.value.code == "INVALID_INSTANT"


def test_health(client):
    h = client.health()
    assert h["status"] == "ok"


def test_client_config_defaults_are_applied(live_base_url):
    from waqt_client import WaqtClientConfig

    config = WaqtClientConfig(base_url=live_base_url, default_asr_shadow_ratio=2.0)
    with WaqtClient(config=config) as c:
        resp = c.get_waqt(lat=21.4225, lon=39.8262, instant="2026-09-19T10:00:00Z")
        assert resp.profile.asr_shadow_ratio == 2.0
        # Per-call override still wins over the config default.
        resp2 = c.get_waqt(lat=21.4225, lon=39.8262, instant="2026-09-19T10:00:00Z", asr_ratio=1.0)
        assert resp2.profile.asr_shadow_ratio == 1.0

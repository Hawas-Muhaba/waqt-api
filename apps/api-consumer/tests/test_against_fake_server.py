"""Behavioural test: a real HTTP server (stdlib http.server, real socket, real
port) serving the exact envelope/shape waqt.api returns, so api_consumer's
HTTP + JSON handling is exercised for real rather than mocked. The server's
fixture data is recorded `waqt_local` output (same shape the live API
returns — waqt_endpoint.py wraps exactly this dict in `success()`), because
FastAPI itself could not run in the sandbox this sprint was built in (see
SPRINT-12-REPORT.md); `tests/test_api_consumer_against_live_api.py` at the
repo root re-runs the equivalent against the real app where FastAPI is
available.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

import pytest

from api_consumer.waqt_api import WaqtApiClient, WaqtApiError, WaqtTransportError

# Recorded from `waqt_local.waqt(lat=21.4225, lon=39.8262, instant="2026-09-28T12:00:00Z")`,
# which is exactly what `waqt.api.waqt_endpoint.get_waqt` wraps in `success()`.
WAQT_FIXTURE = {
    "status": "OK", "instant": "2026-09-28T12:00:00+00:00",
    "location": {"lat": 21.4225, "lon": 39.8262, "elevation_m": 0.0},
    "timezone": {"name": "Asia/Riyadh", "utc_offset_seconds": 10800},
    "undefined_reason": None,
    "day": {"maghrib_open": "2026-09-27T15:15:00+00:00", "maghrib_close": "2026-09-28T15:14:20+00:00",
            "length_si_seconds": 86360.0, "note": None},
    "hijri": {"date": "1448-04-15", "display": "15 Rabi al-Thani 1448 AH", "year": 1448, "month": 4,
              "month_name": "Rabi al-Thani", "day": 15,
              "provider": {"name": "arithmetic-tabular", "version": "30-year-cycle-epoch-1948440"},
              "source_note": None},
    "weekday": "al-Ithnayn",
    "waqt": {"display": "Waqt 20:45:00", "reading": {"display": "20:45:00", "seconds": 74700.0}},
    "events": [
        {"name": "fajr", "instant": "2026-09-28T02:40:00+00:00", "reading": {"display": "11:25:00", "seconds": 41100.0}},
        {"name": "sunrise", "instant": "2026-09-28T03:50:00+00:00", "reading": {"display": "12:35:00", "seconds": 45300.0}},
        {"name": "dhuhr", "instant": "2026-09-28T09:20:00+00:00", "reading": {"display": "18:05:00", "seconds": 65100.0}},
        {"name": "asr", "instant": "2026-09-28T12:35:00+00:00", "reading": {"display": "21:20:00", "seconds": 76800.0}},
        {"name": "maghrib", "instant": "2026-09-28T15:14:20+00:00", "reading": {"display": "23:59:20", "seconds": 86360.0}},
        {"name": "isha", "instant": "2026-09-28T16:29:00+00:00", "reading": {"display": "25:14:00", "seconds": 90840.0}},
    ],
    "next_event": {"name": "asr", "instant": "2026-09-28T12:35:00+00:00",
                   "countdown": {"display": "00:35:00", "seconds": 2100.0}},
    "profile": {"name": "custom", "fajr_angle_deg": 18.0, "isha_angle_deg": 17.0, "asr_shadow_ratio": 1.0},
    "computation": {"engine": "waqt-noaa-low-precision", "revision": "2", "accuracy_level": "B",
                     "astronomy_engine": "waqt-noaa-low-precision", "timescale_model": "espenak-meeus-2006",
                     "delta_t_seconds": 75.5},
}

VERSION_FIXTURE = {
    "waqt_core_version": "0.2.1", "spec": "waqt-core/0.1", "api_version": "1.4.0", "waqt_local_version": None,
    "computation": {"engine": "waqt-noaa-low-precision", "revision": "2", "accuracy_level": "B"},
    "engine_revision_history": {}, "conformance_vectors": {"vector_set_version": "1.1", "generated_at_engine_revision": "2"},
    "notes": "",
}


def _envelope(data):
    return {"meta": {"api_version": "1.4.0", "spec": "waqt-core/0.1", "generated_at": "2026-09-28T12:00:00Z"},
            "data": data, "error": None}


def _error_envelope(code, message, details=None):
    return {"meta": {"api_version": "1.4.0", "spec": "waqt-core/0.1", "generated_at": "2026-09-28T12:00:00Z"},
            "data": None, "error": {"code": code, "message": message, "details": details or {}}}


class FakeWaqtHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # silence
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        if parsed.path == "/v1/waqt":
            if qs.get("lat", ["0"])[0] == "999":  # trigger a validation error, like the real API would
                body, status = _error_envelope("VALIDATION_ERROR", "lat must be within [-90, 90]"), 422
            else:
                body, status = _envelope(WAQT_FIXTURE), 200
        elif parsed.path == "/v1/version":
            body, status = _envelope(VERSION_FIXTURE), 200
        elif parsed.path == "/v1/health":
            self._send(200, {"status": "ok", "spec": "waqt-core/0.1", "api_version": "1.4.0",
                              "computation": VERSION_FIXTURE["computation"]})
            return
        elif parsed.path == "/v1/not-json":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"not json at all")
            return
        else:
            body, status = _error_envelope("NOT_FOUND", f"no such route {parsed.path}"), 404
        self._send(status, body)

    def _send(self, status, body):
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


@pytest.fixture()
def server():
    httpd = HTTPServer(("127.0.0.1", 0), FakeWaqtHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}"
    finally:
        httpd.shutdown()
        thread.join(timeout=2)


def test_get_waqt_over_real_http(server):
    client = WaqtApiClient(server)
    data = client.get_waqt(21.4225, 39.8262)
    assert data["waqt"]["reading"]["display"] == "20:45:00"
    assert data["computation"]["revision"] == "2"


def test_get_version_over_real_http(server):
    client = WaqtApiClient(server)
    v = client.get_version()
    assert v["api_version"] == "1.4.0" and v["waqt_core_version"] == "0.2.1"


def test_get_health_is_read_unwrapped(server):
    client = WaqtApiClient(server)
    h = client.get_health()
    assert h["status"] == "ok"


def test_error_envelope_becomes_waqt_api_error(server):
    client = WaqtApiClient(server)
    with pytest.raises(WaqtApiError) as ei:
        client.get_waqt(999, 39.8262)
    assert ei.value.code == "VALIDATION_ERROR"


def test_unreachable_host_becomes_waqt_transport_error():
    client = WaqtApiClient("http://127.0.0.1:1", timeout=1.0)
    with pytest.raises(WaqtTransportError):
        client.get_waqt(21.4225, 39.8262)


def test_non_json_response_becomes_waqt_transport_error(server):
    client = WaqtApiClient(server)
    with pytest.raises(WaqtTransportError):
        client._get("/v1/not-json", {})


def test_cli_end_to_end_against_fake_server(server):
    import io
    from contextlib import redirect_stdout

    from api_consumer.cli import main

    buf = io.StringIO()
    with redirect_stdout(buf):
        code = main(["--base-url", server, "--lat", "21.4225", "--lon", "39.8262"])
    out = buf.getvalue()
    assert code == 0
    assert "Waqt clock" in out and "waqt-noaa-low-precision r2" in out

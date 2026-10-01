"""Sprint 14 -- AlAdhanHijriProvider behaviour (no internet needed).

Two layers: injected fake transports with a fake clock (fast, deterministic), and a
real-socket fake server (verification/fake_aladhan.py) that exercises the actual urllib
transport: timeouts, redirects, size cap, status handling.
"""
from __future__ import annotations

import json
import sys
import threading
import time
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "verification"))
from fake_aladhan import FakeAlAdhan  # noqa: E402

from waqt_core.calendar_providers import AlAdhanHijriProvider  # noqa: E402
from waqt_core.calendar_providers.aladhan import (  # noqa: E402
    FALLBACK_REASONS, TransportError, TransportResponse, TransportTimeout)
from waqt_core.hijri import ArithmeticTabularProvider, HIJRI_SOURCES, HijriDate  # noqa: E402

D = date(2026, 9, 30)


def body(d: date = D, offset: int = 0, **over) -> bytes:
    h = ArithmeticTabularProvider().from_gregorian(d)
    day = h.day + offset
    obj = {"code": 200, "status": "OK", "data": {
        "hijri": {"day": str(day), "month": {"number": h.month}, "year": str(h.year), "method": "UAQ"},
        "gregorian": {"date": d.strftime("%d-%m-%Y")}}}
    obj.update(over)
    return json.dumps(obj).encode()


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def advance(self, s):
        self.t += s


class Net:
    """Scriptable transport that records calls."""
    def __init__(self, fn=None):
        self.calls, self.fn = [], fn or (lambda url: TransportResponse(200, body()))

    def __call__(self, url, timeout, max_bytes):
        self.calls.append(url)
        r = self.fn(url)
        if isinstance(r, Exception):
            raise r
        return r


def make(net, clock=None, **kw):
    clock = clock or Clock()
    kw.setdefault("fallback", ArithmeticTabularProvider())
    return AlAdhanHijriProvider(transport=net, clock=clock,
                                wall_clock=lambda: datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc), **kw), clock


# ---- identity & success ---------------------------------------------------

def test_identity_and_remote_success_provenance():
    p, _ = make(Net())
    assert p.name == "aladhan" and p.version.startswith("aladhan-gToH-v1")
    h = p.from_gregorian(D)
    assert h.source == "remote" and h.provider == "aladhan" and h.version == p.version
    assert h.provenance.cache == "miss" and h.provenance.fallback_reason is None
    assert h.provenance.upstream_method == "UAQ" and h.provenance.fetched_at.startswith("2026-09-30T12:00:00")
    assert h.source in HIJRI_SOURCES


def test_method_is_part_of_version_and_request():
    net = Net()
    p, _ = make(net, method="UAQ")
    assert p.version.endswith("+method=UAQ")
    p.from_gregorian(D)
    assert net.calls[0].endswith("/gToH/30-09-2026?calendarMethod=UAQ")


def test_rejects_non_http_base_url():
    for bad in ("file:///etc/passwd", "ftp://x/y", "api.aladhan.com", ""):
        with pytest.raises(ValueError):
            AlAdhanHijriProvider(base_url=bad)


# ---- cache ----------------------------------------------------------------

def test_cache_hit_within_12h_makes_no_second_request():
    net = Net(); p, clock = make(net)
    p.from_gregorian(D)
    clock.advance(12 * 3600 - 1)
    h = p.from_gregorian(D)
    assert len(net.calls) == 1 and h.source == "remote" and h.provenance.cache == "hit"
    assert h.provenance.age_seconds == pytest.approx(12 * 3600 - 1, abs=1)


def test_cache_expires_after_12h_and_refetches():
    net = Net(); p, clock = make(net)
    p.from_gregorian(D)
    clock.advance(12 * 3600 + 1)
    h = p.from_gregorian(D)
    assert len(net.calls) == 2 and h.provenance.cache == "miss"


def test_cache_is_per_date():
    net = Net(lambda url: TransportResponse(200, body(date(2026, 10, 1)) if "01-10-2026" in url else body()))
    p, _ = make(net)
    p.from_gregorian(D); p.from_gregorian(date(2026, 10, 1)); p.from_gregorian(D)
    assert len(net.calls) == 2


def test_cache_is_bounded_lru():
    net = Net(lambda url: TransportResponse(200, body(_date_of(url))))
    p, _ = make(net, max_cache_entries=3, max_requests_per_minute=10_000)
    for i in range(10):
        p.from_gregorian(date(2026, 1, 1 + i))
    assert p.status()["cache_entries"] == 3


def _date_of(url):
    dd, mm, yy = url.split("/gToH/")[1].split("?")[0].split("-")
    return date(int(yy), int(mm), int(dd))


# ---- fallback & stale -------------------------------------------------------

@pytest.mark.parametrize("resp,reason", [
    (TransportTimeout("t"), "timeout"),
    (TransportError("refused"), "network-error"),
    (TransportResponse(500, b"x"), "upstream-server-error"),
    (TransportResponse(503, b"x"), "upstream-server-error"),
    (TransportResponse(429, b"x", {"Retry-After": "5"}), "upstream-rate-limited"),
    (TransportResponse(404, b"{}"), "upstream-rejected"),
    (TransportResponse(400, b"{}"), "upstream-rejected"),
    (TransportResponse(200, b"<html>"), "malformed-response"),
    (TransportResponse(200, b'{"code":200}'), "malformed-response"),
    (TransportResponse(200, b'{"code":500,"data":{}}'), "malformed-response"),
    (TransportResponse(200, body(offset=0).replace(b'"30-09-2026"', b'"01-01-2000"')), "date-mismatch"),
    (TransportResponse(200, body(offset=9)), "implausible-response"),
    (TransportResponse(200, json.dumps({"code": 200, "data": {"hijri": {
        "day": "31", "month": {"number": 4}, "year": "1448"}, "gregorian": {}}}).encode()), "malformed-response"),
    (TransportResponse(200, json.dumps({"code": 200, "data": {"hijri": {
        "day": "5", "month": {"number": 13}, "year": "1448"}}}).encode()), "malformed-response"),
    (TransportResponse(200, b"\xff\xfe"), "malformed-response"),
    (TransportResponse(200, b"x" * 70000), "malformed-response"),
    (RuntimeError("bug in the transport"), "internal-error"),
])
def test_every_failure_mode_becomes_labelled_local_fallback(resp, reason):
    p, _ = make(Net(lambda url: resp))
    h = p.from_gregorian(D)    # must not raise
    assert reason in FALLBACK_REASONS
    assert h.source == "local-fallback"
    assert h.provenance.fallback_reason == reason
    assert h.provenance.requested_provider == "aladhan"
    assert h.provider == "arithmetic-tabular"      # the provider that actually answered
    assert (h.year, h.month) == (1448, 4)


def test_fallback_chain_ends_in_arithmetic_even_if_fallback_provider_raises():
    class Boom:
        name, version = "boom", "1"
        def from_gregorian(self, d): raise ValueError("ephem range")
    p, _ = make(Net(lambda url: TransportError("down")), fallback=Boom())
    h = p.from_gregorian(D)
    assert h.source == "local-fallback" and h.provider == "arithmetic-tabular"
    assert "boom failed" in h.provenance.fallback_detail


def test_stale_if_error_serves_last_known_remote_value_and_says_so():
    state = {"down": False}
    net = Net(lambda url: TransportError("down") if state["down"] else TransportResponse(200, body(offset=1)))
    p, clock = make(net)
    fresh = p.from_gregorian(D)
    clock.advance(13 * 3600); state["down"] = True
    h = p.from_gregorian(D)
    assert h.source == "remote-stale" and h.provider == "aladhan"
    assert (h.year, h.month, h.day) == (fresh.year, fresh.month, fresh.day)   # no flip-flop
    assert h.provenance.cache == "stale" and h.provenance.fallback_reason == "network-error"


def test_stale_value_is_dropped_after_max_stale():
    state = {"down": False}
    net = Net(lambda url: TransportError("down") if state["down"] else TransportResponse(200, body()))
    p, clock = make(net, max_stale_seconds=24 * 3600)
    p.from_gregorian(D); clock.advance(25 * 3600); state["down"] = True
    assert p.from_gregorian(D).source == "local-fallback"


def test_remote_value_is_returned_even_when_it_disagrees_with_local_and_disagreement_is_visible():
    p, _ = make(Net(lambda url: TransportResponse(200, body(offset=1))))
    h = p.from_gregorian(D)
    assert h.source == "remote"
    local = ArithmeticTabularProvider().from_gregorian(D)
    assert h.day == local.day + 1                     # remote wins, not silently replaced
    cc = h.provenance.cross_check
    assert cc["agrees"] is False and cc["delta_days"] == 1 and cc["provider"] == "arithmetic-tabular"


def test_cross_check_agreement_and_opt_out():
    h = make(Net())[0].from_gregorian(D)
    assert h.provenance.cross_check["agrees"] is True and h.provenance.cross_check["delta_days"] == 0
    h = make(Net(), cross_check=False)[0].from_gregorian(D)
    assert h.provenance.cross_check is None


def test_cross_check_failure_never_breaks_the_remote_answer():
    class Boom:
        name, version = "boom", "1"
        def from_gregorian(self, d): raise RuntimeError("x")
    h = make(Net(), fallback=Boom())[0].from_gregorian(D)
    assert h.source == "remote" and h.provenance.cross_check["agrees"] is None


# ---- circuit breaker / budgets -----------------------------------------------

def test_hard_failure_opens_circuit_then_recovers():
    state = {"down": True}
    net = Net(lambda url: TransportError("down") if state["down"] else TransportResponse(200, body()))
    p, clock = make(net, failure_cooldown_seconds=30)
    p.from_gregorian(D)
    assert len(net.calls) == 1 and p.status()["circuit"] == "open"
    for _ in range(5):                                 # outage must not add latency or traffic
        h = p.from_gregorian(D)
        assert h.provenance.fallback_reason == "circuit-open"
    assert len(net.calls) == 1
    state["down"] = False; clock.advance(31)
    assert p.from_gregorian(D).source == "remote" and p.status()["circuit"] == "closed"


def test_upstream_429_retry_after_is_honoured_and_capped():
    net = Net(lambda url: TransportResponse(429, b"", {"retry-after": "120"}))
    p, clock = make(net, failure_cooldown_seconds=30, max_retry_after_seconds=600)
    p.from_gregorian(D)
    clock.advance(100); assert p.from_gregorian(D).provenance.fallback_reason == "circuit-open"
    clock.advance(21); p.from_gregorian(D); assert len(net.calls) == 2
    net2 = Net(lambda url: TransportResponse(429, b"", {"Retry-After": "999999"}))
    p2, c2 = make(net2, max_retry_after_seconds=600)
    p2.from_gregorian(D); c2.advance(601); p2.from_gregorian(D); assert len(net2.calls) == 2


def test_soft_failures_open_circuit_only_after_three_in_a_row():
    net = Net(lambda url: TransportResponse(404, b"{}"))
    p, _ = make(net, max_requests_per_minute=1000)
    for i in range(3):
        assert p.status()["circuit"] == "closed"
        p.from_gregorian(date(2026, 9, 1 + i))
    assert p.status()["circuit"] == "open"


def test_outbound_rate_limit_caps_requests_and_refills():
    net = Net(lambda url: TransportResponse(200, body(_date_of(url))))
    p, clock = make(net, max_requests_per_minute=5)
    reasons = [p.from_gregorian(date(2026, 1, 1 + i)).provenance.fallback_reason for i in range(8)]
    assert len(net.calls) == 5 and reasons.count("outbound-rate-limited") == 3
    clock.advance(60)
    assert p.from_gregorian(date(2026, 2, 1)).source == "remote"


def test_outbound_limit_does_not_trip_circuit():
    net = Net(lambda url: TransportResponse(200, body(_date_of(url))))
    p, _ = make(net, max_requests_per_minute=1)
    p.from_gregorian(date(2026, 1, 1)); p.from_gregorian(date(2026, 1, 2))
    assert p.status()["circuit"] == "closed"


def test_date_window_never_leaves_the_process():
    net = Net(); p, _ = make(net)
    for d in (date(1500, 1, 1), date(1899, 12, 31), date(2077, 1, 1), date(9999, 1, 1)):
        h = p.from_gregorian(d)
        assert h.source == "local-fallback" and h.provenance.fallback_reason == "date-outside-remote-window"
    assert net.calls == []


def test_disabled_provider_never_calls_out():
    net = Net(); p, _ = make(net, enabled=False)
    h = p.from_gregorian(D)
    assert net.calls == [] and h.provenance.fallback_reason == "disabled" and h.source == "local-fallback"


def test_status_is_network_free_and_reports_counters():
    net = Net(); p, _ = make(net)
    p.from_gregorian(D); p.from_gregorian(D)
    n = len(net.calls)
    st = p.status()
    assert len(net.calls) == n
    assert st["remote_ok"] == 1 and st["cache_hit"] == 1 and st["circuit"] == "closed"
    assert st["provider"] == "aladhan" and st["enabled"] is True


# ---- concurrency -----------------------------------------------------------

def test_single_flight_concurrent_same_date_makes_one_request():
    def slow(url):
        time.sleep(0.2)
        return TransportResponse(200, body())
    net = Net(slow); p, _ = make(net, timeout_seconds=5)
    out = []
    ts = [threading.Thread(target=lambda: out.append(p.from_gregorian(D))) for _ in range(8)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert len(net.calls) == 1 and all(h.source == "remote" for h in out)


def test_busy_lock_is_bounded_not_a_hang():
    gate = threading.Event()
    def blocked(url):
        gate.wait(3); return TransportResponse(200, body())
    net = Net(blocked); p, _ = make(net, timeout_seconds=0.2)
    t = threading.Thread(target=lambda: p.from_gregorian(D)); t.start(); time.sleep(0.05)
    t0 = time.monotonic(); h = p.from_gregorian(date(2026, 10, 2)); dt = time.monotonic() - t0
    gate.set(); t.join()
    assert h.provenance.fallback_reason == "busy" and dt < 1.0


# ---- real sockets: the actual urllib transport -------------------------------

@pytest.fixture()
def srv():
    s = FakeAlAdhan().start()
    yield s
    s.stop()


def real(srv, **kw):
    kw.setdefault("fallback", ArithmeticTabularProvider())
    return AlAdhanHijriProvider(base_url=srv.base_url, **kw)


def test_real_socket_success_and_cache(srv):
    p = real(srv)
    a = p.from_gregorian(D); b = p.from_gregorian(D)
    assert a.source == "remote" and b.provenance.cache == "hit" and len(srv.calls) == 1
    assert srv.calls[0] == "/v1/gToH/30-09-2026"


@pytest.mark.parametrize("mode,reason", [
    ("500", "upstream-server-error"), ("429", "upstream-rate-limited"), ("garbage", "malformed-response"),
    ("404", "upstream-rejected"), ("redirect", "upstream-rejected"), ("huge", "malformed-response"),
    ("wrongdate", "date-mismatch")])
def test_real_socket_failure_modes(srv, mode, reason):
    srv.mode = mode
    h = real(srv).from_gregorian(D)
    assert h.source == "local-fallback" and h.provenance.fallback_reason == reason


def test_real_socket_redirect_is_not_followed(srv):
    srv.mode = "redirect"
    real(srv).from_gregorian(D)
    assert len(srv.calls) == 1


def test_real_socket_timeout_is_bounded(srv):
    srv.delay = 2.0
    p = real(srv, timeout_seconds=0.3)
    t0 = time.monotonic(); h = p.from_gregorian(D); dt = time.monotonic() - t0
    assert h.provenance.fallback_reason == "timeout" and dt < 1.5


def test_real_socket_connection_refused():
    s = FakeAlAdhan().start(); base = s.base_url; s.stop()
    h = AlAdhanHijriProvider(base_url=base, fallback=ArithmeticTabularProvider()).from_gregorian(D)
    assert h.provenance.fallback_reason == "network-error" and h.source == "local-fallback"

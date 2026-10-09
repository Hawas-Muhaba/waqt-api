"""Sprint 6: the /v1/schedule/* HTTP surface."""

from fastapi.testclient import TestClient

from waqt.api import app

c = TestClient(app)
ADDIS = dict(lat=9.0192, lon=38.7525)


def _resolve(op, loc=None, anchor="2026-09-19T15:42:00Z", **extra):
    return c.post("/v1/schedule/resolve", json={"location": loc or ADDIS, "anchor": anchor, "operation": op, **extra})


def test_snapshot_answers_the_standard_questions_in_the_envelope():
    r = c.get("/v1/schedule/snapshot", params={**ADDIS, "instant": "2026-09-19T15:42:00Z"})
    b = r.json()
    assert r.status_code == 200 and b["error"] is None
    d = b["data"]
    assert d["day"]["status"] == "OK" and d["day"]["position"]["display"] == "00:19:02"
    assert d["next_event"]["name"] == "isha"
    assert {e["name"] for e in d["events"]} == {"fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha"}
    assert "religious" in d["caveat"]
    assert d["calendar_provider"]["used_for"].startswith("display labels only")


def test_snapshot_calendar_provider_changes_only_the_label():
    a = c.get("/v1/schedule/snapshot", params={**ADDIS, "instant": "2026-09-19T15:42:00Z"}).json()["data"]
    b = c.get("/v1/schedule/snapshot", params={**ADDIS, "instant": "2026-09-19T15:42:00Z", "calendar_provider": "umm-al-qura"}).json()["data"]
    for d in (a, b):
        d["day"].pop("hijri_label")
        d.pop("calendar_provider")
    assert a == b


def test_snapshot_reports_undefined_events_as_status_not_error():
    r = c.get("/v1/schedule/snapshot", params={"lat": 51.5074, "lon": -0.1278, "instant": "2026-06-21T12:00:00Z"})
    assert r.status_code == 200
    by = {e["name"]: e for e in r.json()["data"]["events"]}
    assert by["fajr"]["next"]["status"] == "EVENT_UNDEFINED" and by["maghrib"]["next"]["status"] == "OK"


def test_span_endpoint_crossing_and_exact_boundary():
    q = {**ADDIS, "start": "2026-09-19T14:30:00Z", "end": "2026-09-19T16:30:00Z", "precision": "microsecond"}
    assert c.get("/v1/schedule/span", params=q).json()["data"]["crosses_maghrib"] is True
    day = c.get("/v1/day", params={**ADDIS, "instant": "2026-09-19T15:42:00Z"}).json()["data"]["day"]
    close = c.post("/v1/schedule/resolve", json={"location": ADDIS, "anchor": "2026-09-19T15:42:00Z", "precision": "microsecond",
                   "operation": {"op": "resolve_point", "point": {"type": "event", "name": "day_end"}}}).json()["data"]["result"]["instant"]
    ends_at = c.get("/v1/schedule/span", params={**ADDIS, "start": "2026-09-20T14:00:00Z", "end": close, "precision": "microsecond"}).json()["data"]
    assert ends_at["crosses_maghrib"] is False
    incl = c.get("/v1/schedule/span", params={**ADDIS, "start": "2026-09-20T14:00:00Z", "end": close, "end_inclusive": "true", "precision": "microsecond"}).json()["data"]
    assert incl["crosses_maghrib"] is True and day  # instant-pair reading agrees with crosses_maghrib()


def test_span_bad_instant_and_precision():
    assert c.get("/v1/schedule/span", params={**ADDIS, "start": "nope", "end": "2026-09-19T16:30:00Z"}).json()["error"]["code"] == "INVALID_INSTANT"
    assert c.get("/v1/schedule/span", params={**ADDIS, "start": "2026-09-19T14:00:00Z", "end": "2026-09-19T16:30:00Z", "precision": "x"}).status_code == 400


def test_resolve_window_and_evaluate():
    w = _resolve({"op": "resolve_interval", "interval": {"type": "interval", "start": {"type": "event", "name": "maghrib"}, "end": {"type": "event", "name": "isha"}}})
    assert w.status_code == 200 and w.json()["data"]["result"]["status"] == "OK"
    e = _resolve({"op": "evaluate", "instant": "2026-09-20T02:00:00Z",
                  "interval": {"type": "interval", "start": {"type": "event", "name": "fajr"}, "end": {"type": "event", "name": "sunrise"}}})
    assert e.json()["data"]["result"]["inside"] is False


def test_resolve_defaults_to_umm_al_qura():
    r = _resolve({"op": "day_bounds"})
    assert r.status_code == 200
    assert r.json()["data"]["calendar_provider"]["name"] == "umm-al-qura"


def test_resolve_undefined_is_200_with_status():
    loc = {"lat": 51.5074, "lon": -0.1278}
    r = _resolve({"op": "resolve_interval", "interval": {"type": "interval", "start": {"type": "event", "name": "fajr"}, "end": {"type": "event", "name": "sunrise"}}},
                 loc, "2026-06-21T12:00:00Z")
    assert r.status_code == 200 and r.json()["data"]["result"]["status"] == "WINDOW_UNDEFINED"
    r = _resolve({"op": "until", "name": "fajr"}, loc, "2026-06-21T12:00:00Z")
    assert r.json()["data"]["result"]["status"] == "EVENT_UNDEFINED"


def test_resolve_malformed_rule_is_400_invalid_rule():
    for op in ({"op": "resolve_point", "point": {"type": "event", "name": "witr"}}, {"op": "bogus"}, {"nope": 1}, {"op": "until"}):
        r = _resolve(op)
        assert r.status_code == 400 and r.json()["error"]["code"] == "INVALID_RULE", op


def test_resolve_request_validation():
    assert c.post("/v1/schedule/resolve", json={"anchor": "2026-09-19T15:42:00Z", "operation": {"op": "day_bounds"}}).status_code == 422
    assert _resolve({"op": "day_bounds"}, {"lat": 95, "lon": 0}).status_code == 422
    assert _resolve({"op": "day_bounds"}, anchor="garbage").json()["error"]["code"] == "INVALID_INSTANT"
    assert _resolve({"op": "day_bounds"}, calendar_provider="nope").json()["error"]["code"] == "UNKNOWN_CALENDAR_PROVIDER"


def test_asr_profile_over_http_moves_only_asr():
    def go(ratio):
        return _resolve({"op": "resolve_interval", "interval": {"type": "interval", "start": {"type": "event", "name": "maghrib"}, "end": {"type": "event", "name": "isha"}}},
                        profile={"asr_shadow_ratio": ratio}).json()["data"]["result"]
    assert go(1.0) == go(2.0)

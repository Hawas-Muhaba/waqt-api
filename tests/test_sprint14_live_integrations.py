"""Sprint 14 -- Live Integrations & Production Hardening, at the HTTP contract level.

Covers: normal location, high latitude, polar/undefined, provider switching, provider
failure/fallback, invalid coordinates, invalid dates, rate limiting, CORS, API health,
version reporting, day transition (API level; the browser level is verification/browser).
No internet: the AlAdhan provider gets an injected transport.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from waqt.api import create_app
from waqt.api import app as default_app
from waqt.api.providers import PROVIDER_CATALOG, aladhan_status, configure_aladhan
from waqt.api.ratelimit import SlidingWindowLimiter, parse_rate_limit
from waqt_core.calendar_providers import AlAdhanHijriProvider
from waqt_core.calendar_providers.aladhan import TransportError, TransportResponse
from waqt_core.hijri import ArithmeticTabularProvider

ADDIS = {"lat": 9.0192, "lon": 38.7525, "timezone_override": "Africa/Addis_Ababa"}
INSTANT = "2026-09-30T09:00:00Z"
REYKJAVIK = {"lat": 64.15, "lon": -21.94, "timezone_override": "Atlantic/Reykjavik"}
POLE = {"lat": 90.0, "lon": 0.0, "timezone_override": "UTC"}

client = TestClient(default_app, raise_server_exceptions=False)


def gtoh_body(url, offset=0):
    dd, mm, yy = url.split("/gToH/")[1].split("?")[0].split("-")
    h = ArithmeticTabularProvider().from_gregorian(date(int(yy), int(mm), int(dd)))
    return json.dumps({"code": 200, "status": "OK", "data": {
        "hijri": {"day": str(h.day + offset), "month": {"number": h.month}, "year": str(h.year), "method": "UAQ"},
        "gregorian": {"date": f"{dd}-{mm}-{yy}"}}}).encode()


class Upstream:
    def __init__(self):
        self.calls, self.mode, self.offset = [], "ok", 0

    def __call__(self, url, timeout, max_bytes):
        self.calls.append(url)
        if self.mode == "ok":
            return TransportResponse(200, gtoh_body(url, self.offset))
        if self.mode == "down":
            raise TransportError("connection refused")
        if self.mode == "500":
            return TransportResponse(500, b"oops")
        if self.mode == "429":
            return TransportResponse(429, b"", {"Retry-After": "60"})
        if self.mode == "garbage":
            return TransportResponse(200, b"not json")
        raise AssertionError(self.mode)


def new_provider(u):
    """Same wiring as production (providers._build_aladhan): lazy umm-al-qura fallback."""
    from waqt.api.providers import _cached_stateless
    return AlAdhanHijriProvider(transport=u, fallback_factory=lambda: _cached_stateless("umm-al-qura"))


@pytest.fixture()
def up():
    u = Upstream()
    configure_aladhan(new_provider(u))
    yield u
    configure_aladhan(None)


def waqt(params=None, provider="aladhan", app_client=client, **extra):
    return app_client.get("/v1/waqt", params={**ADDIS, "instant": INSTANT, "calendar_provider": provider,
                                              **(params or {}), **extra})


def astro(d):
    """Every astronomical field of a /v1/waqt payload (everything except the Hijri decoration)."""
    return {k: d[k] for k in ("status", "instant", "location", "timezone", "undefined_reason", "day",
                              "waqt", "next_event", "profile", "computation", "events")} | {
        "event_instants": [(r["name"], r["gregorian"], r["waqt"]) for r in d["event_representations"]]}


# ============================================================ normal location

def test_remote_success_exposes_identity_source_and_provenance(up):
    r = waqt()
    assert r.status_code == 200
    h = r.json()["data"]["hijri"]
    assert h["provider"] == {"name": "aladhan", "version": "aladhan-gToH-v1"}
    assert h["source"] == "remote"
    prov = h["provenance"]
    assert prov["requested_provider"] == "aladhan" and prov["cache"] == "miss"
    assert prov["fallback_reason"] is None and prov["upstream_method"] == "UAQ"
    assert prov["ttl_seconds"] == 43200 and prov["fetched_at"]
    assert r.json()["data"]["calendar_error"] is None


def test_second_request_is_served_from_cache_without_another_upstream_call(up):
    waqt(); r = waqt()
    assert r.json()["data"]["hijri"]["provenance"]["cache"] == "hit" and len(up.calls) == 1


def test_local_providers_report_source_local_and_no_provenance_block():
    for name in ("arithmetic-tabular", "umm-al-qura"):
        h = waqt(provider=name).json()["data"]["hijri"]
        assert h["source"] == "local" and h["provenance"] is None and h["provider"]["name"] == name


def test_declared_and_observation_sources():
    base = {"override_date": "2026-09-30", "declared_year": 1448, "declared_month": 4, "declared_day": 20}
    h = waqt(base, provider="declared").json()["data"]["hijri"]
    assert h["source"] == "declared" and h["day"] == 20
    base = {"override_date": "2026-09-30", "sighting_year": 1448, "sighting_month": 4, "sighting_day": 21}
    assert waqt(base, provider="local-observation").json()["data"]["hijri"]["source"] == "observation"


# ============================================================ events / representations

def test_events_carry_gregorian_hijri_waqt_representations(up):
    d = waqt().json()["data"]
    assert [e["name"] for e in d["events"]] == ["fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha"]
    assert [r_["name"] for r_ in d["event_representations"]] == [e["name"] for e in d["events"]]
    for e, rep in zip(d["events"], d["event_representations"]):
        assert set(rep) == {"name", "gregorian", "hijri", "waqt"}
        assert rep["gregorian"]["utc"] == e["instant"]
        assert rep["gregorian"]["timezone"] == "Africa/Addis_Ababa"
        assert rep["gregorian"]["local"].endswith("+03:00")
        assert rep["waqt"]["seconds"] == e["reading"]["seconds"] and rep["waqt"]["display"].startswith("Waqt ")
        assert rep["hijri"]["date"] == f"{d['hijri']['year']}-{d['hijri']['month']:02d}-{d['hijri']['day']:02d}"
        assert rep["hijri"]["provider"] == "aladhan" and rep["hijri"]["source"] == "remote"
        assert rep["hijri"]["basis"] == "waqt-day-label"


def test_local_civil_date_can_differ_from_waqt_day_label_which_is_why_both_are_shown():
    d = waqt(provider="arithmetic-tabular", instant="2026-09-30T20:00:00Z").json()["data"]
    i = next(i for i, e in enumerate(d["events"]) if e["name"] == "isha")
    assert d["event_representations"][i]["gregorian"]["local_date"] in {"2026-09-30", "2026-10-01"}
    assert d["events"][i]["reading"]["seconds"] >= d["day"]["length_si_seconds"]      # Isha reads past the day length


def test_event_provenance_reflects_fallback(up):
    up.mode = "down"
    e = waqt().json()["data"]["event_representations"][0]["hijri"]
    assert e["source"] == "local-fallback" and e["provider"] == "umm-al-qura"


# ============================================================ high latitude / polar

def test_high_latitude_events_without_instants_have_null_representations_not_errors(up):
    r = waqt(REYKJAVIK, instant="2026-06-21T12:00:00Z")
    d = r.json()["data"]
    assert r.status_code == 200 and d["status"] == "OK"
    missing = [i for i, e in enumerate(d["events"]) if e["instant"] is None]
    assert {d["events"][i]["name"] for i in missing} == {"fajr", "isha"}
    for i in missing:
        rep = d["event_representations"][i]
        assert rep["gregorian"] is None and rep["waqt"] is None
        assert rep["hijri"]["source"] == "remote"     # the label still exists
    assert d["hijri"]["source"] == "remote"


def test_polar_undefined_has_null_hijri_no_events_and_makes_no_upstream_call(up):
    r = waqt(POLE, instant="2026-06-21T12:00:00Z")
    d = r.json()["data"]
    assert r.status_code == 200 and d["status"] == "UNDEFINED" and d["undefined_reason"]
    assert d["hijri"] is None and d["events"] == [] and d["event_representations"] == [] and d["calendar_error"] is None
    assert up.calls == []


@pytest.mark.parametrize("where,inst", [(ADDIS, INSTANT), (REYKJAVIK, "2026-06-21T12:00:00Z"),
                                        (POLE, "2026-06-21T12:00:00Z")])
def test_astronomy_identical_across_provider_switching_and_failures(up, where, inst):
    results = {}
    for name in ("arithmetic-tabular", "umm-al-qura", "aladhan"):
        results[name] = astro(waqt(where, provider=name, instant=inst).json()["data"])
    up.mode = "down"; configure_aladhan(new_provider(up))
    results["aladhan-down"] = astro(waqt(where, provider="aladhan", instant=inst).json()["data"])
    up.mode, up.offset = "ok", 2; configure_aladhan(new_provider(up))
    results["aladhan-disagreeing"] = astro(waqt(where, provider="aladhan", instant=inst).json()["data"])
    first = json.dumps(results["arithmetic-tabular"], sort_keys=True)
    assert all(json.dumps(v, sort_keys=True) == first for v in results.values())


# ============================================================ provider switching

def test_provider_switching_changes_provenance_not_the_request_shape(up):
    shapes = set()
    for name in ("arithmetic-tabular", "umm-al-qura", "aladhan"):
        d = waqt(provider=name).json()["data"]
        assert d["hijri"]["provider"]["name"] == name
        shapes.add(tuple(sorted(d["hijri"])))
    assert len(shapes) == 1        # null-stable: same keys regardless of provider


def test_disagreement_between_providers_is_visible(up):
    up.offset = 1
    h = waqt().json()["data"]["hijri"]
    cc = h["provenance"]["cross_check"]
    uaq = waqt(provider="umm-al-qura").json()["data"]["hijri"]
    assert cc["provider"] == "umm-al-qura" and cc["date"] == f"{uaq['year']}-{uaq['month']:02d}-{uaq['day']:02d}"
    assert h["source"] == "remote" and cc["agrees"] is False
    assert cc["delta_days"] == h["day"] - uaq["day"] != 0      # remote value returned, gap reported, nothing hidden
    assert h["day"] == waqt(provider="arithmetic-tabular").json()["data"]["hijri"]["day"] + 1


def test_unknown_provider_lists_aladhan_among_available():
    r = waqt(provider="nope")
    assert r.status_code == 400 and r.json()["error"]["code"] == "UNKNOWN_CALENDAR_PROVIDER"
    assert "aladhan" in r.json()["error"]["details"]["available"]


def test_catalog_lists_aladhan_with_network_flags():
    provs = {p["name"]: p for p in client.get("/v1/calendar").json()["data"]["providers"]}
    assert set(provs) == {"arithmetic-tabular", "umm-al-qura", "declared", "local-observation", "aladhan"}
    assert provs["aladhan"]["network"] is True and provs["aladhan"]["single_date_only"] is True
    assert provs["aladhan"]["supports_reverse_conversion"] is False
    assert provs["umm-al-qura"]["network"] is False and provs["umm-al-qura"]["single_date_only"] is False


def test_other_single_date_endpoints_accept_aladhan(up):
    r = client.get("/v1/hijri", params={"date": "2026-09-30", "calendar_provider": "aladhan"})
    assert r.status_code == 200 and r.json()["data"]["hijri"]["source"] == "remote"
    r = client.get("/v1/conversions", params={"direction": "to-hijri", "date": "2026-09-30",
                                              "calendar_provider": "aladhan"})
    assert r.status_code == 200 and r.json()["data"]["output"]["hijri"]["source"] == "remote"


def test_reverse_conversion_with_aladhan_is_a_clean_unsupported_operation(up):
    r = client.get("/v1/conversions", params={"direction": "to-gregorian", "year": 1448, "month": 4,
                                              "day": 19, "calendar_provider": "aladhan"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "UNSUPPORTED_OPERATION"


def test_many_date_endpoints_refuse_the_live_provider_with_a_clear_error(up):
    """Schedules/years would spend the outbound budget and could mix remote + fallback dates."""
    cases = [
        ("get", "/v1/institutional/week", {"lat": 9.0, "lon": 38.7, "instant": INSTANT}),
        ("get", "/v1/institutional/fiscal-year", {"hijri_year": 1448}),
        ("get", "/v1/institutional/academic-year", {"hijri_year": 1448}),
        ("post", "/v1/schedule/resolve", None),
    ]
    for method, path, params in cases:
        params = dict(params or {}, calendar_provider="aladhan")
        if method == "get":
            r = client.get(path, params=params)
        else:
            r = client.post(path, json={"location": {"lat": 9.0, "lon": 38.7}, "anchor": INSTANT,
                                        "calendar_provider": "aladhan",
                                        "operation": {"op": "resolve_interval", "interval": {"type": "interval",
                                            "start": {"type": "event", "name": "maghrib", "day": 0},
                                            "end": {"type": "event", "name": "isha", "day": 0}}}})
        assert r.status_code == 400, (path, r.text)
        e = r.json()["error"]
        assert e["code"] == "UNSUPPORTED_OPERATION" and "aladhan" not in e["details"]["available"], path
    assert up.calls == []


def test_bounded_schedule_endpoints_still_accept_the_live_provider(up):
    r = client.get("/v1/schedule/snapshot", params={**ADDIS, "instant": INSTANT, "calendar_provider": "aladhan"})
    assert r.status_code == 200, r.text


# ============================================================ provider failure / fallback

@pytest.mark.parametrize("mode,reason", [("down", "network-error"), ("500", "upstream-server-error"),
                                         ("429", "upstream-rate-limited"), ("garbage", "malformed-response")])
def test_upstream_failure_is_a_200_with_visible_local_fallback(up, mode, reason):
    up.mode = mode
    r = waqt()
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["status"] == "OK" and len(d["events"]) == 6
    h = d["hijri"]
    assert h["source"] == "local-fallback" and h["provider"]["name"] == "umm-al-qura"
    assert h["provenance"]["requested_provider"] == "aladhan"
    assert h["provenance"]["fallback_reason"] == reason and h["provenance"]["fallback_detail"]
    assert d["calendar_error"] is None        # a fallback is not an error: the date still exists


def test_circuit_open_does_not_hammer_a_dead_upstream(up):
    up.mode = "down"
    for _ in range(6):
        assert waqt().status_code == 200
    assert len(up.calls) == 1
    assert waqt().json()["data"]["hijri"]["provenance"]["fallback_reason"] == "circuit-open"


def test_recovery_after_outage_returns_to_remote(up):
    up.mode = "down"; waqt()
    up.mode = "ok"
    p = new_provider(up)   # fresh circuit
    configure_aladhan(p)
    assert waqt().json()["data"]["hijri"]["source"] == "remote"


def test_a_calendar_provider_that_raises_reports_calendar_error_and_keeps_the_astronomy(monkeypatch):
    from waqt_core.calendar_providers import UmmAlQuraProvider
    def boom(self, d): raise ValueError("ephemeris range exceeded")
    monkeypatch.setattr(UmmAlQuraProvider, "from_gregorian", boom)
    baseline = astro(waqt(provider="arithmetic-tabular").json()["data"])
    r = waqt(provider="umm-al-qura")
    d = r.json()["data"]
    assert r.status_code == 200 and d["hijri"] is None
    assert d["calendar_error"] == {"provider": "umm-al-qura", "message": "ValueError: ephemeris range exceeded"}
    assert astro(d) == baseline


def test_year_1500_with_umm_al_qura_keeps_events_instead_of_a_500():
    r = client.get("/v1/waqt", params={**ADDIS, "instant": "1500-01-01T12:00:00Z", "calendar_provider": "umm-al-qura"})
    d = r.json()["data"]
    assert r.status_code == 200 and d["status"] == "OK" and len(d["events"]) == 6
    assert d["hijri"] is None and "calendar_error" in d and d["calendar_error"]["provider"] == "umm-al-qura"


def test_aladhan_for_a_date_outside_its_window_falls_back_without_a_request(up):
    r = waqt(instant="1800-06-01T12:00:00Z").json()["data"]["hijri"]
    assert r["source"] == "local-fallback" and r["provenance"]["fallback_reason"] == "date-outside-remote-window"
    assert up.calls == []


def test_true_internal_errors_remain_structured_500s(monkeypatch):
    import waqt.api.waqt_endpoint as we
    monkeypatch.setattr(we, "compute_waqt", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("engine bug")))
    r = waqt(provider="arithmetic-tabular")
    assert r.status_code == 500 and r.json()["error"]["code"] == "INTERNAL_ERROR" and r.json()["data"] is None


# ============================================================ invalid input

@pytest.mark.parametrize("params", [
    {"lat": 91, "lon": 0}, {"lat": -91, "lon": 0}, {"lat": 0, "lon": 181}, {"lat": 0, "lon": -181},
    {"lat": "abc", "lon": 0}, {"lat": 0}, {"lat": "nan", "lon": 0}, {"lat": 0, "lon": 0, "elevation_m": -5},
])
def test_invalid_coordinates_are_422_in_the_standard_envelope_and_never_reach_the_provider(up, params):
    r = client.get("/v1/waqt", params={**params, "instant": INSTANT, "calendar_provider": "aladhan"})
    assert r.status_code == 422
    b = r.json()
    assert b["error"]["code"] == "VALIDATION_ERROR" and b["data"] is None and "meta" in b
    assert up.calls == []


@pytest.mark.parametrize("bad", ["not-a-date", "2026-13-01T00:00:00Z", "2026-02-30T00:00:00Z", "", "99999-01-01"])
def test_invalid_instants_are_400_invalid_instant(up, bad):
    r = waqt(instant=bad)
    assert r.status_code == 400 and r.json()["error"]["code"] == "INVALID_INSTANT"
    assert up.calls == []


@pytest.mark.parametrize("bad", ["2026-02-30", "2026-13-01", "yesterday", "30-09-2026"])
def test_invalid_dates_are_400_invalid_date(up, bad):
    r = client.get("/v1/hijri", params={"date": bad, "calendar_provider": "aladhan"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "INVALID_DATE"
    assert up.calls == []


# ============================================================ health & version

def test_health_is_network_free_and_reports_integration_state(up):
    up.mode = "down"; waqt()
    n = len(up.calls)
    r = client.get("/v1/health")
    assert r.status_code == 200 and len(up.calls) == n
    b = r.json()
    assert b["status"] == "ok" and b["api_version"] == "1.7.0"
    assert b["components"]["optional_providers"]["aladhan"]["status"] == "degraded"
    i = b["integrations"]["hijri_aladhan"]
    assert i["provider"] == "aladhan" and i["circuit"] == "open" and i["last_failure_reason"] == "network-error"
    assert i["enabled"] is True and i["fallback_provider"]


def test_health_stays_ok_while_the_integration_is_degraded(up):
    up.mode = "500"; waqt()
    assert client.get("/v1/health").json()["status"] == "ok"


def test_health_does_not_construct_a_network_request_on_a_cold_provider():
    configure_aladhan(None)
    assert client.get("/v1/health").status_code == 200


def test_version_reports_api_engine_and_integrations():
    response = client.get("/v1/version")
    d = response.json()["data"]
    assert response.headers["cache-control"] == "public, max-age=30"
    assert d["api_version"] == "1.7.0"
    assert d["integrations"]["affects_astronomy"] is False
    assert "aladhan" in d["integrations"]["calendar_providers"]
    a = d["integrations"]["hijri_aladhan"]
    assert a["provider"] == "aladhan" and a["version"].startswith("aladhan-gToH-v1") and a["cache_ttl_seconds"] == 43200
    assert str(d["engine"]["revision"]) == "2" if isinstance(d.get("engine"), dict) else True


def test_cache_headers_respect_time_and_provider_semantics():
    current = client.get("/v1/waqt", params={"lat": 9.0192, "lon": 38.7525})
    fixed = client.get("/v1/waqt", params={
        "lat": 9.0192, "lon": 38.7525, "instant": "2026-10-01T12:00:00Z",
        "calendar_provider": "arithmetic-tabular",
    })
    catalog = client.get("/v1/calendar")
    assert current.headers["cache-control"] == "no-store"
    assert fixed.headers["cache-control"] == "private, max-age=30"
    assert catalog.headers["cache-control"] == "public, max-age=300"


def test_engine_identity_is_identical_in_health_version_and_every_waqt_response(up):
    h = client.get("/v1/health").json()["computation"]
    w = waqt().json()["data"]["computation"]
    v = client.get("/v1/version").json()["data"]
    assert h["engine"] == w["engine"] and str(h["revision"]) == str(w["revision"])
    assert v["api_version"] == "1.7.0"


def test_env_disables_remote_lookups(monkeypatch):
    monkeypatch.setenv("WAQT_ALADHAN_ENABLED", "0"); configure_aladhan(None)
    try:
        h = waqt().json()["data"]["hijri"]
        assert h["source"] == "local-fallback" and h["provenance"]["fallback_reason"] == "disabled"
        assert client.get("/v1/health").json()["integrations"]["hijri_aladhan"]["enabled"] is False
    finally:
        configure_aladhan(None)


# ============================================================ day transition

def test_hijri_label_steps_exactly_at_maghrib_and_provenance_follows(up):
    d0 = waqt().json()["data"]
    maghrib = next(e["instant"] for e in d0["events"] if e["name"] == "maghrib")
    t = datetime.fromisoformat(maghrib)
    from datetime import timedelta
    before = waqt(instant=(t - timedelta(seconds=2)).isoformat().replace("+00:00", "Z")).json()["data"]
    after = waqt(instant=(t + timedelta(seconds=2)).isoformat().replace("+00:00", "Z")).json()["data"]
    assert before["hijri"]["day"] != after["hijri"]["day"] or before["hijri"]["month"] != after["hijri"]["month"]
    assert after["day"]["maghrib_open"] <= after["instant"] and before["day"]["maghrib_close"] >= before["instant"]
    for x in (before, after):
        assert x["hijri"]["source"] == "remote"
    assert before["day"]["maghrib_close"] == after["day"]["maghrib_open"]


# ============================================================ CORS

def test_cors_is_off_by_default():
    a = TestClient(create_app(cors_origins=[], rate_limit=""))
    r = a.get("/v1/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers


def test_cors_allows_only_configured_origins():
    a = TestClient(create_app(cors_origins=["https://app.example"], rate_limit=""))
    ok = a.get("/v1/health", headers={"Origin": "https://app.example"})
    assert ok.headers["access-control-allow-origin"] == "https://app.example"
    bad = a.get("/v1/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in bad.headers


def test_cors_preflight_for_the_new_provenance_fields_request():
    a = TestClient(create_app(cors_origins=["https://app.example"], rate_limit=""))
    r = a.options("/v1/waqt", headers={"Origin": "https://app.example", "Access-Control-Request-Method": "GET"})
    assert r.status_code == 200 and r.headers["access-control-allow-origin"] == "https://app.example"
    assert "GET" in r.headers["access-control-allow-methods"]


def test_error_and_fallback_responses_also_carry_cors_headers(up):
    a = TestClient(create_app(cors_origins=["https://app.example"], rate_limit=""), raise_server_exceptions=False)
    r = a.get("/v1/waqt", params={"lat": 999, "lon": 0}, headers={"Origin": "https://app.example"})
    assert r.status_code == 422 and r.headers["access-control-allow-origin"] == "https://app.example"
    up.mode = "down"
    r = a.get("/v1/waqt", params={**ADDIS, "instant": INSTANT, "calendar_provider": "aladhan"},
              headers={"Origin": "https://app.example"})
    assert r.status_code == 200 and r.headers["access-control-allow-origin"] == "https://app.example"


# ============================================================ rate limiting

def limited(spec="3/minute", **kw):
    return TestClient(create_app(cors_origins=kw.pop("cors_origins", []), rate_limit=spec, **kw),
                      raise_server_exceptions=False)


def test_rate_limit_rejects_with_429_envelope_and_retry_after():
    a = limited()
    codes = [a.get("/v1/version").status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]
    r = a.get("/v1/version")
    b = r.json()
    assert b["error"]["code"] == "RATE_LIMITED" and b["data"] is None and "meta" in b
    assert b["error"]["details"]["limit"] == 3 and b["error"]["details"]["window_seconds"] == 60
    assert 1 <= int(r.headers["retry-after"]) <= 60
    assert r.headers["x-ratelimit-limit"] == "3" and r.headers["x-ratelimit-remaining"] == "0"


def test_success_responses_advertise_the_remaining_budget():
    a = limited("10/minute")
    r = a.get("/v1/version")
    assert r.headers["x-ratelimit-limit"] == "10" and r.headers["x-ratelimit-remaining"] == "9"


def test_health_is_exempt_from_rate_limiting():
    a = limited("1/minute")
    assert all(a.get("/v1/health").status_code == 200 for _ in range(10))


def test_rate_limit_is_per_client_when_behind_a_trusted_proxy():
    a = limited("2/minute", trust_proxy=True)
    h1, h2 = {"X-Forwarded-For": "203.0.113.1, 10.0.0.1"}, {"X-Forwarded-For": "203.0.113.2"}
    assert [a.get("/v1/version", headers=h1).status_code for _ in range(3)] == [200, 200, 429]
    assert a.get("/v1/version", headers=h2).status_code == 200


def test_forged_leading_xff_entries_cannot_rotate_identity_behind_a_trusted_proxy():
    # The proxy appends the real peer (9.9.9.9) after whatever the client sent. Rotating forged
    # leftmost entries must NOT reset the budget: the key is the proxy-recorded rightmost entry.
    a = limited("2/minute", trust_proxy=True)
    codes = [a.get("/v1/version", headers={"X-Forwarded-For": f"198.51.100.{i}, 9.9.9.9"}).status_code for i in range(4)]
    assert codes == [200, 200, 429, 429]


def test_trusted_proxy_hops_selects_the_entry_from_the_right():
    from waqt.api.ratelimit import RateLimitMiddleware
    m = RateLimitMiddleware(None, 5, 60, trust_proxy=True, proxy_hops=2)
    scope = lambda v: {"headers": [(b"x-forwarded-for", v.encode())], "client": ("10.0.0.9", 1)}
    assert m._key(scope("evil, 1.1.1.1, 2.2.2.2")) == "1.1.1.1"
    assert m._key(scope("only-one")) == "only-one"
    assert RateLimitMiddleware(None, 5, 60, trust_proxy=True)._key({"headers": [], "client": ("10.0.0.9", 1)}) == "10.0.0.9"


def test_x_forwarded_for_is_ignored_unless_the_proxy_is_trusted():
    a = limited("2/minute")      # trust_proxy defaults to off: spoofing XFF must not buy more budget
    codes = [a.get("/v1/version", headers={"X-Forwarded-For": f"198.51.100.{i}"}).status_code for i in range(3)]
    assert codes == [200, 200, 429]


def test_a_429_is_readable_by_a_browser_cors_headers_present():
    a = limited("1/minute", cors_origins=["https://app.example"])
    a.get("/v1/version", headers={"Origin": "https://app.example"})
    r = a.get("/v1/version", headers={"Origin": "https://app.example"})
    assert r.status_code == 429 and r.headers["access-control-allow-origin"] == "https://app.example"
    assert "retry-after" in r.headers["access-control-expose-headers"].lower()


def test_preflight_requests_do_not_consume_the_budget():
    a = limited("1/minute", cors_origins=["https://app.example"])
    for _ in range(3):
        a.options("/v1/waqt", headers={"Origin": "https://app.example", "Access-Control-Request-Method": "GET"})
    assert a.get("/v1/version", headers={"Origin": "https://app.example"}).status_code == 200


def test_rate_limit_is_off_by_default():
    a = TestClient(create_app(cors_origins=[], rate_limit=""), raise_server_exceptions=False)
    assert all(a.get("/v1/version").status_code == 200 for _ in range(30))


def test_sliding_window_recovers_and_is_memory_bounded():
    t = [0.0]
    lim = SlidingWindowLimiter(2, 10, max_clients=3, clock=lambda: t[0])
    assert lim.check("a")[0] and lim.check("a")[0]
    ok, rem, wait = lim.check("a")
    assert not ok and rem == 0 and wait == pytest.approx(10.0)
    t[0] = 10.0
    assert lim.check("a")[0]
    for k in "bcdef":
        lim.check(k)
    assert len(lim._hits) == 3


@pytest.mark.parametrize("spec,expected", [("120/minute", (120, 60)), ("5/second", (5, 1)), (" 10 / hour ", (10, 3600)),
                                           ("3/minutes", (3, 60)), ("", None), (None, None)])
def test_rate_limit_spec_parsing(spec, expected):
    assert parse_rate_limit(spec) == expected


@pytest.mark.parametrize("bad", ["abc", "0/minute", "10/day", "10", "-5/minute"])
def test_malformed_rate_limit_fails_loudly_at_startup(bad):
    with pytest.raises(ValueError):
        parse_rate_limit(bad)
    with pytest.raises(ValueError):
        create_app(cors_origins=[], rate_limit=bad)


def test_events_array_is_byte_identical_to_the_events_endpoint_and_sprint_13_shape(up):
    w = waqt().json()["data"]["events"]
    e = client.get("/v1/events", params={**ADDIS, "instant": INSTANT}).json()["data"]["events"]
    assert w == e and all(set(x) == {"name", "instant", "reading"} for x in w)

"""
Sprint 4 test suite — the Waqt API v1 HTTP contract.

Covers: envelope shape (meta/data/error) on success AND error, every
error code, all seven endpoints, the declared/local-observation
override fix, and Gregorian<->Hijri round-trips through the HTTP
layer (not just the underlying provider objects).

Run with: python3 -m pytest tests/ -v
"""

from fastapi.testclient import TestClient

from waqt.api import app

client = TestClient(app, raise_server_exceptions=False)

ADDIS = {"lat": 9.0192, "lon": 38.7525}
INSTANT = "2026-09-19T15:42:00Z"
# Per Core Time Model Sec 2, the Hijri label date for this instant/location
# is the CLOSING Maghrib's Gregorian date, one day after the instant's own.
LABEL_DATE = "2026-09-20"


# ---------------------------------------------------------------------------
# Envelope shape
# ---------------------------------------------------------------------------


def test_success_envelope_shape():
    r = client.get("/v1/waqt", params={**ADDIS, "instant": INSTANT})
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {"meta", "data", "error"}
    assert body["error"] is None
    assert body["meta"]["api_version"] == "1.3.0"
    assert body["meta"]["spec"] == "waqt-core/0.1"
    assert "generated_at" in body["meta"]


def test_error_envelope_shape():
    r = client.get("/v1/waqt", params={**ADDIS, "calendar_provider": "nonsense"})
    assert r.status_code == 400
    body = r.json()
    assert set(body.keys()) == {"meta", "data", "error"}
    assert body["data"] is None
    assert body["error"]["code"] == "UNKNOWN_CALENDAR_PROVIDER"
    assert "nonsense" in body["error"]["message"]


# ---------------------------------------------------------------------------
# Error codes — every documented code is actually reachable
# ---------------------------------------------------------------------------


def test_invalid_instant_error():
    r = client.get("/v1/waqt", params={**ADDIS, "instant": "not-a-date"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INVALID_INSTANT"


def test_invalid_date_error():
    r = client.get("/v1/hijri", params={"date": "not-a-date"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INVALID_DATE"


def test_validation_error_on_bad_lat():
    r = client.get("/v1/waqt", params={"lat": 200, "lon": 38})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_unknown_calendar_provider_error():
    r = client.get("/v1/waqt", params={**ADDIS, "calendar_provider": "made-up"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "UNKNOWN_CALENDAR_PROVIDER"


def test_unsupported_operation_error_on_declared_reverse():
    r = client.get("/v1/conversions", params={
        "direction": "to-gregorian", "year": 1448, "month": 4, "day": 10, "calendar_provider": "declared"
    })
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "UNSUPPORTED_OPERATION"


def test_internal_error_never_leaks_a_raw_traceback():
    # A date far enough back to hit UmmAlQuraProvider's known ephem
    # limitation (see SCOPE.md) — must come back structured, not as an
    # unhandled exception.
    r = client.get("/v1/waqt", params={**ADDIS, "instant": "1500-01-01T12:00:00Z", "calendar_provider": "umm-al-qura"})
    assert r.status_code == 500
    body = r.json()
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert body["data"] is None


# ---------------------------------------------------------------------------
# /v1/waqt — reading objects, null-stability
# ---------------------------------------------------------------------------


def test_waqt_reading_is_display_plus_seconds_not_bare_string():
    r = client.get("/v1/waqt", params={**ADDIS, "instant": INSTANT})
    reading = r.json()["data"]["waqt"]["reading"]
    assert set(reading.keys()) == {"display", "seconds"}
    assert isinstance(reading["seconds"], (int, float))
    assert reading["display"].count(":") == 2


def test_waqt_undefined_status_is_null_stable_not_key_dropping():
    r = client.get("/v1/waqt", params={
        "lat": 69.6, "lon": 18.96, "instant": "2026-06-21T12:00:00Z"
    })
    data = r.json()["data"]
    assert data["status"] == "UNDEFINED"
    # Same top-level keys present as the OK case, just null:
    assert "hijri" in data and data["hijri"] is None
    assert "waqt" in data and data["waqt"] is None
    assert data["undefined_reason"] is not None


# ---------------------------------------------------------------------------
# declared / local-observation — genuinely testable via the API now
# ---------------------------------------------------------------------------


def test_declared_override_takes_effect_on_labeled_date():
    r = client.get("/v1/waqt", params={
        **ADDIS, "instant": INSTANT, "calendar_provider": "declared",
        "override_date": LABEL_DATE, "declared_year": 1448, "declared_month": 4, "declared_day": 10,
    })
    hijri = r.json()["data"]["hijri"]
    assert hijri["provider"]["name"] == "declared"
    assert (hijri["year"], hijri["month"], hijri["day"]) == (1448, 4, 10)


def test_declared_without_override_falls_back():
    r = client.get("/v1/waqt", params={**ADDIS, "instant": INSTANT, "calendar_provider": "declared"})
    assert r.json()["data"]["hijri"]["provider"]["name"] == "arithmetic-tabular"


def test_local_observation_override_with_source_note():
    r = client.get("/v1/waqt", params={
        **ADDIS, "instant": INSTANT, "calendar_provider": "local-observation",
        "override_date": LABEL_DATE, "sighting_year": 1448, "sighting_month": 4, "sighting_day": 9,
        "observed_at": "Addis Ababa",
    })
    hijri = r.json()["data"]["hijri"]
    assert hijri["provider"]["name"] == "local-observation"
    assert hijri["source_note"] == "Addis Ababa"


# ---------------------------------------------------------------------------
# /v1/day, /v1/events — subset endpoints agree with /v1/waqt
# ---------------------------------------------------------------------------


def test_day_endpoint_matches_waqt_endpoint_boundaries():
    r_waqt = client.get("/v1/waqt", params={**ADDIS, "instant": INSTANT})
    r_day = client.get("/v1/day", params={**ADDIS, "instant": INSTANT})
    assert r_day.json()["data"]["day"] == r_waqt.json()["data"]["day"]


def test_events_endpoint_matches_waqt_endpoint_events():
    r_waqt = client.get("/v1/waqt", params={**ADDIS, "instant": INSTANT})
    r_events = client.get("/v1/events", params={**ADDIS, "instant": INSTANT})
    assert r_events.json()["data"]["events"] == r_waqt.json()["data"]["events"]


def test_events_endpoint_has_no_calendar_provider_param():
    # The absence itself is the point — events don't depend on the calendar.
    import inspect
    from waqt.api.events_endpoint import get_events
    params = inspect.signature(get_events).parameters
    assert "calendar_provider" not in params


# ---------------------------------------------------------------------------
# /v1/hijri — location-independent
# ---------------------------------------------------------------------------


def test_hijri_endpoint_takes_no_location_params():
    import inspect
    from waqt.api.hijri_endpoint import get_hijri
    params = inspect.signature(get_hijri).parameters
    assert "lat" not in params and "lon" not in params


def test_hijri_endpoint_matches_waqt_endpoint_for_same_label_date():
    r_waqt = client.get("/v1/waqt", params={**ADDIS, "instant": INSTANT, "calendar_provider": "umm-al-qura"})
    r_hijri = client.get("/v1/hijri", params={"date": LABEL_DATE, "calendar_provider": "umm-al-qura"})
    assert r_hijri.json()["data"]["hijri"] == r_waqt.json()["data"]["hijri"]


# ---------------------------------------------------------------------------
# /v1/calendar — discovery
# ---------------------------------------------------------------------------


def test_calendar_catalog_lists_all_four_providers():
    r = client.get("/v1/calendar")
    names = {p["name"] for p in r.json()["data"]["providers"]}
    assert names == {"arithmetic-tabular", "umm-al-qura", "declared", "local-observation"}


# ---------------------------------------------------------------------------
# /v1/location
# ---------------------------------------------------------------------------


def test_location_endpoint_date_line_case():
    r = client.get("/v1/location", params={
        "lat": 1.8721, "lon": -157.4278, "instant": "2026-09-19T23:00:00Z"
    })
    data = r.json()["data"]
    assert data["timezone"]["name"] == "Pacific/Kiritimati"
    assert data["local_civil_date"] == "2026-09-20"


# ---------------------------------------------------------------------------
# /v1/conversions — round trips through the HTTP layer
# ---------------------------------------------------------------------------


def test_conversions_round_trip_arithmetic():
    r1 = client.get("/v1/conversions", params={"direction": "to-hijri", "date": "2026-09-20", "calendar_provider": "arithmetic-tabular"})
    hd = r1.json()["data"]["output"]["hijri"]
    r2 = client.get("/v1/conversions", params={
        "direction": "to-gregorian", "year": hd["year"], "month": hd["month"], "day": hd["day"],
        "calendar_provider": "arithmetic-tabular",
    })
    assert r2.json()["data"]["output"]["gregorian_date"] == "2026-09-20"


def test_conversions_round_trip_umm_al_qura():
    r1 = client.get("/v1/conversions", params={"direction": "to-hijri", "date": "2026-09-20", "calendar_provider": "umm-al-qura"})
    hd = r1.json()["data"]["output"]["hijri"]
    r2 = client.get("/v1/conversions", params={
        "direction": "to-gregorian", "year": hd["year"], "month": hd["month"], "day": hd["day"],
        "calendar_provider": "umm-al-qura",
    })
    assert r2.json()["data"]["output"]["gregorian_date"] == "2026-09-20"


def test_conversions_bad_direction():
    r = client.get("/v1/conversions", params={"direction": "sideways", "date": "2026-09-20"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


def test_health_check():
    r = client.get("/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

"""Sprint 8: the /v1/calendar/convert and /v1/calendar/boundary-crossing HTTP surface."""

from fastapi.testclient import TestClient

from waqt.api import app

c = TestClient(app)
ADDIS = dict(lat=9.0084, lon=38.7575)
KIRITIMATI = dict(lat=1.87, lon=-157.4)


def test_health_reports_new_api_version():
    r = c.get("/v1/health")
    assert r.json()["api_version"] == "1.6.0"


# ---------------------------------------------------------------------------
# GET /v1/calendar/convert  (direction=instant-to-calendars, the default)
# ---------------------------------------------------------------------------

def test_convert_instant_no_location_gives_only_utc_gregorian():
    r = c.get("/v1/calendar/convert", params={"instant": "2026-03-01T12:00:00Z"})
    assert r.status_code == 200 and r.json()["error"] is None
    d = r.json()["data"]
    assert d["gregorian"]["utc"]["date"] == "2026-03-01"
    assert d["gregorian"]["civil"] is None
    assert d["waqt"] is None
    assert "caveat" in d


def test_convert_instant_with_location_gives_full_bundle():
    r = c.get("/v1/calendar/convert", params={"instant": "2026-03-01T12:00:00Z", **ADDIS})
    b = r.json()["data"]
    assert b["gregorian"]["civil"]["timezone_name"] == "Africa/Addis_Ababa"
    assert b["waqt"]["status"] == "OK"
    assert b["waqt"]["day"]["hijri"]["date"] is not None
    assert b["waqt"]["day"]["weekday"] is not None
    assert b["calendar_provider"]["name"] == "arithmetic-tabular"


def test_convert_instant_defaults_to_now_when_omitted():
    r = c.get("/v1/calendar/convert", params={**ADDIS})
    assert r.status_code == 200
    assert r.json()["data"]["gregorian"]["utc"]["date"] is not None


def test_convert_instant_respects_calendar_provider_choice():
    r = c.get("/v1/calendar/convert", params={
        "instant": "2026-03-01T12:00:00Z", **ADDIS,
        "calendar_provider": "declared",
        "override_date": "2026-03-01", "declared_year": 1447, "declared_month": 9, "declared_day": 30,
    })
    b = r.json()["data"]
    assert b["calendar_provider"]["name"] == "declared"
    assert b["waqt"]["day"]["hijri"]["date"] == "1447-09-30"


def test_convert_bad_direction_is_400():
    r = c.get("/v1/calendar/convert", params={"direction": "sideways"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_convert_lat_without_lon_is_400():
    r = c.get("/v1/calendar/convert", params={"instant": "2026-03-01T12:00:00Z", "lat": 9.0})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# GET /v1/calendar/convert  (direction=gregorian-date-to-waqt)
# ---------------------------------------------------------------------------

def test_convert_gregorian_date_to_waqt_requires_location():
    r = c.get("/v1/calendar/convert", params={"direction": "gregorian-date-to-waqt", "date": "2026-03-01"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_convert_gregorian_date_to_waqt_requires_date():
    r = c.get("/v1/calendar/convert", params={"direction": "gregorian-date-to-waqt", **ADDIS})
    assert r.status_code == 400


def test_convert_gregorian_date_to_waqt_ok():
    r = c.get("/v1/calendar/convert", params={"direction": "gregorian-date-to-waqt", "date": "2026-03-01", **ADDIS})
    assert r.status_code == 200
    b = r.json()["data"]
    assert b["waqt"]["status"] == "OK"
    assert b["waqt"]["day"]["maghrib_open"] < b["waqt"]["day"]["maghrib_close"]
    assert b["source"]["date"] == "2026-03-01"


def test_convert_gregorian_date_to_waqt_at_date_line():
    r = c.get("/v1/calendar/convert", params={"direction": "gregorian-date-to-waqt", "date": "2026-06-15", **KIRITIMATI})
    assert r.status_code == 200
    assert r.json()["data"]["waqt"]["status"] == "OK"


def test_convert_gregorian_date_to_waqt_polar_undefined_is_200_not_error():
    """Polar undefined-ness is a legitimate astronomical answer, not a
    caller error -- matches the rest of the API's NULL-STABLE posture."""
    r = c.get("/v1/calendar/convert", params={
        "direction": "gregorian-date-to-waqt", "date": "2026-06-21", "lat": 78.0, "lon": 15.0,
    })
    assert r.status_code == 200
    b = r.json()["data"]
    assert b["waqt"]["status"] == "UNDEFINED"
    assert b["waqt"]["undefined_reason"]


# ---------------------------------------------------------------------------
# GET /v1/calendar/boundary-crossing
# ---------------------------------------------------------------------------

def test_boundary_crossing_ok():
    day = c.get("/v1/calendar/convert", params={"direction": "gregorian-date-to-waqt", "date": "2026-03-01", **ADDIS}).json()["data"]["waqt"]["day"]
    maghrib = day["maghrib_close"]
    r = c.get("/v1/calendar/boundary-crossing", params={
        "start": maghrib, "end": maghrib, **ADDIS,
    })
    # start == end is an invalid span (empty), not a valid boundary query
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INVALID_SPAN"


def test_boundary_crossing_span_around_maghrib():
    day = c.get("/v1/calendar/convert", params={"direction": "gregorian-date-to-waqt", "date": "2026-03-01", **ADDIS}).json()["data"]["waqt"]["day"]
    from datetime import datetime, timedelta, timezone
    m = datetime.fromisoformat(day["maghrib_close"])
    start = (m - timedelta(hours=1)).isoformat()
    end = (m + timedelta(hours=1)).isoformat()
    r = c.get("/v1/calendar/boundary-crossing", params={"start": start, "end": end, **ADDIS})
    assert r.status_code == 200
    b = r.json()["data"]
    assert b["crosses_maghrib"] is True
    assert b["status"] == "OK"


def test_boundary_crossing_end_before_start_is_400():
    r = c.get("/v1/calendar/boundary-crossing", params={
        "start": "2026-03-01T23:00:00Z", "end": "2026-03-01T21:00:00Z", **ADDIS,
    })
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INVALID_SPAN"


def test_boundary_crossing_requires_lat_lon():
    r = c.get("/v1/calendar/boundary-crossing", params={"start": "2026-03-01T21:00:00Z", "end": "2026-03-01T23:00:00Z"})
    assert r.status_code == 422  # FastAPI's own required-query-param validation

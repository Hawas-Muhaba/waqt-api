"""API 1.8.0: ERR-004 (422 for invalid profile parameters, every entry point) and CAL-013 (out-of-range dates never fail a Waqt result)."""
import json

import pytest
from fastapi.testclient import TestClient

from waqt.api import app

c = TestClient(app)
PLACE = dict(lat=9.0192, lon=38.7525, timezone_override="Africa/Addis_Ababa")
LOC = dict(lat=9.0192, lon=38.7525, timezone_override="Africa/Addis_Ababa", instant="2026-09-19T15:42:00+00:00")
BAD = [("fajr_angle", "95"), ("fajr_angle", "-5"), ("fajr_angle", "0"), ("fajr_angle", "90.0001"), ("fajr_angle", "nan"), ("fajr_angle", "inf"),
       ("fajr_angle", "-inf"), ("fajr_angle", "abc"), ("isha_angle", "0"), ("isha_angle", "95"), ("isha_angle", "nan"), ("asr_ratio", "0"),
       ("asr_ratio", "-1"), ("asr_ratio", "nan"), ("asr_ratio", "inf"), ("asr_ratio", "abc")]
GOOD = [("fajr_angle", "90"), ("fajr_angle", "0.0001"), ("isha_angle", "90"), ("asr_ratio", "0.0001"), ("asr_ratio", "2")]


@pytest.mark.parametrize("endpoint", ["/v1/waqt", "/v1/events", "/v1/calendar/convert"])
@pytest.mark.parametrize("name,value", BAD)
def test_invalid_profile_parameters_return_422_validation_error(endpoint, name, value):
    r = c.get(endpoint, params={**LOC, name: value})
    assert r.status_code == 422, r.text
    err = r.json()["error"]
    assert err["code"] == "VALIDATION_ERROR"
    json.dumps(r.json(), allow_nan=False)


@pytest.mark.parametrize("endpoint", ["/v1/waqt", "/v1/events", "/v1/calendar/convert"])
@pytest.mark.parametrize("name,value", GOOD)
def test_boundary_profile_values_are_accepted(endpoint, name, value):
    assert c.get(endpoint, params={**LOC, name: value}).status_code == 200


def test_post_schedule_profile_validation_matches():
    body = {"location": {"lat": 9.0, "lon": 38.7}, "anchor": "2026-09-19T15:42:00+00:00", "rule": {"type": "event", "name": "fajr"}}
    for prof in ({"fajr_angle_deg": 95}, {"isha_angle_deg": "x"}, {"isha_angle_deg": True}, {"asr_shadow_ratio": 0}):
        r = c.post("/v1/schedule/resolve", json={**body, "profile": prof})
        assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR", (prof, r.text)


def test_defaults_are_unchanged():
    d = c.get("/v1/waqt", params=LOC).json()["data"]
    assert d["profile"]["fajr_angle_deg"] == 18.0 and d["profile"]["isha_angle_deg"] == 17.0 and d["profile"]["asr_shadow_ratio"] == 1.0


@pytest.mark.parametrize("date", ["1699-12-31", "2301-01-01"])
def test_out_of_range_convert_returns_the_waqt_day_with_calendar_error(date):
    r = c.get("/v1/calendar/convert", params={"direction": "gregorian-date-to-waqt", "date": date, **PLACE})
    assert r.status_code == 200, r.text
    w = r.json()["data"]["waqt"]
    assert w["hijri"] is None and "OutOfRange" in w["calendar_error"] and w["status"] == "OK" and w["day"]["maghrib_open"] and w["day"]["maghrib_close"]


@pytest.mark.parametrize("date", ["1700-01-01", "2300-12-31"])
def test_range_edges_inside_the_range_are_unchanged(date):
    w = c.get("/v1/calendar/convert", params={"direction": "gregorian-date-to-waqt", "date": date, **PLACE}).json()["data"]["waqt"]
    assert w["hijri"]["date"] and not w.get("calendar_error")


def test_waqt_endpoint_out_of_range_is_200_with_structured_calendar_error():
    r = c.get("/v1/waqt", params={**LOC, "instant": "1699-12-31T12:00:00+00:00"})
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["hijri"] is None and d["calendar_error"]["message"] and d["day"]["maghrib_open"] == "1699-12-30T15:16:36+00:00"  # the Waqt day is intact


def test_conversions_endpoint_still_refuses_out_of_range():
    r = c.get("/v1/conversions", params={"direction": "to-hijri", "date": "1699-12-31", "calendar_provider": "umm-al-qura"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "OUT_OF_RANGE"


def test_api_version_is_1_8_0():
    assert c.get("/v1/version").json()["data"]["api_version"] == "1.8.0"

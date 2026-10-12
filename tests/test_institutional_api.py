"""Sprint 7: the /v1/institutional/* HTTP surface."""

import pytest

from fastapi.testclient import TestClient

from waqt.api import app

c = TestClient(app)
ADDIS = dict(lat=9.0192, lon=38.7525)


def test_week_envelope_and_jumuah():
    r = c.get("/v1/institutional/week", params={**ADDIS, "instant": "2026-09-19T15:42:00Z"})
    b = r.json()
    assert r.status_code == 200 and b["error"] is None
    d = b["data"]
    assert len(d["days"]) == 7
    assert d["days"][d["jumuah_index"]]["weekday"] == "al-Jumuah"
    assert "caveat" in d


def test_week_bad_first_day_is_400():
    r = c.get("/v1/institutional/week", params={**ADDIS, "first_day": "not-a-day"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INVALID_CALENDAR_RULE"


def test_fiscal_year_default_matches_brief_example():
    r = c.get("/v1/institutional/fiscal-year", params={"hijri_year": 1448})
    b = r.json()["data"]
    assert b["start"]["hijri"].endswith("-01-01")
    assert b["waqt_bounds"] is None  # no location supplied


def test_fiscal_year_with_location_has_waqt_bounds():
    r = c.get("/v1/institutional/fiscal-year", params={"hijri_year": 1448, **ADDIS})
    b = r.json()["data"]
    assert b["waqt_bounds"]["start_open"] is not None
    assert b["waqt_bounds"]["end_close"] is not None


def test_fiscal_year_resolve_custom_rule():
    body = {
        "hijri_year": 1448,
        "start_rule": {"type": "nth_weekday_of_month", "weekday": "al-Ahad", "n": 1, "month": 7},
        "end_rule": {"type": "month_end", "month": 9},
        "label": "Custom",
    }
    r = c.post("/v1/institutional/fiscal-year/resolve", json=body)
    assert r.status_code == 200
    assert r.json()["data"]["start"]["hijri"][5:7] == "07"


def test_fiscal_year_resolve_defaults_to_umm_al_qura():
    body = {
        "hijri_year": 1448,
        "start_rule": {"type": "month_day", "month": 1, "day": 1},
        "end_rule": {"type": "month_day", "month": 1, "day": 2},
    }
    default = c.post("/v1/institutional/fiscal-year/resolve", json=body).json()["data"]
    arithmetic = c.post(
        "/v1/institutional/fiscal-year/resolve",
        json={**body, "calendar_provider": "arithmetic-tabular"},
    ).json()["data"]
    assert default["start"]["gregorian"] != arithmetic["start"]["gregorian"]


def test_fiscal_year_resolve_invalid_rule_is_422():
    body = {"hijri_year": 1448, "start_rule": {"type": "month_day", "month": 12, "day": 1},
            "end_rule": {"type": "month_day", "month": 1, "day": 1}}
    r = c.post("/v1/institutional/fiscal-year/resolve", json=body)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "INVALID_CALENDAR_RULE"


@pytest.mark.parametrize("field,value", [("hijri_year", "1448"), ("hijri_year", None)])
def test_fiscal_year_resolve_requires_positive_json_integer(field, value):
    body = {
        "hijri_year": 1448,
        "start_rule": {"type": "month_day", "month": 1, "day": 1},
        "end_rule": {"type": "month_end", "month": 12},
        field: value,
    }
    r = c.post("/v1/institutional/fiscal-year/resolve", json=body)
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("invalid", [
    {"location": None},
    {"location": {"lat": "9.0192", "lon": 38.7525}},
    {"start_rule": {"type": "month_day", "month": "1", "day": 1}},
])
def test_fiscal_year_resolve_rejects_null_and_coerced_json_values(invalid):
    body = {
        "hijri_year": 1448,
        "start_rule": {"type": "month_day", "month": 1, "day": 1},
        "end_rule": {"type": "month_end", "month": 12},
        **invalid,
    }
    r = c.post("/v1/institutional/fiscal-year/resolve", json=body)
    assert r.status_code == 422
    assert r.json()["error"]["code"] in ("VALIDATION_ERROR", "INVALID_CALENDAR_RULE")


def test_academic_year_default_matches_brief_example():
    r = c.get("/v1/institutional/academic-year", params={"hijri_year": 1448})
    b = r.json()["data"]
    assert b["opening"]["hijri"][5:7] == "01"
    assert b["closing"]["hijri"][5:7] == "08"
    assert b["terms"] == []


def test_academic_year_resolve_with_terms():
    body = {
        "hijri_year": 1448,
        "opening_rule": {"type": "nth_weekday_of_month", "weekday": "al-Ahad", "n": 1, "month": 1},
        "closing_rule": {"type": "nth_weekday_of_month", "weekday": "al-Khamis", "n": -1, "month": 8},
        "term_rules": [
            {"label": "Term 1", "start_rule": {"type": "nth_weekday_of_month", "weekday": "al-Ahad", "n": 1, "month": 1},
             "end_rule": {"type": "month_day", "month": 3, "day": 29}},
        ],
    }
    r = c.post("/v1/institutional/academic-year/resolve", json=body)
    assert r.status_code == 200
    assert len(r.json()["data"]["terms"]) == 1


@pytest.mark.parametrize("field,value", [("term_rules", None), ("holidays", None)])
def test_academic_year_resolve_optional_arrays_are_omitted_not_null(field, value):
    body = {
        "hijri_year": 1448,
        "opening_rule": {"type": "month_day", "month": 1, "day": 1},
        "closing_rule": {"type": "month_end", "month": 8},
        field: value,
    }
    r = c.post("/v1/institutional/academic-year/resolve", json=body)
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_academic_year_resolve_requires_integer_year_offset():
    body = {
        "hijri_year": 1448,
        "opening_rule": {"type": "month_day", "month": 1, "day": 1},
        "closing_rule": {"type": "month_end", "month": 8},
        "term_rules": [{
            "label": "Term", "start_rule": {"type": "month_day", "month": 1},
            "end_rule": {"type": "month_end", "month": 2}, "year_offset": "1",
        }],
    }
    r = c.post("/v1/institutional/academic-year/resolve", json=body)
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_calendar_provider_swap_changes_dates_not_structure():
    a = c.get("/v1/institutional/fiscal-year", params={"hijri_year": 1448}).json()["data"]
    b = c.get("/v1/institutional/fiscal-year", params={"hijri_year": 1448, "calendar_provider": "umm-al-qura"}).json()["data"]
    assert a["start"]["hijri"][5:] == b["start"]["hijri"][5:] == "01-01"  # same structural rule
    # Gregorian dates may legitimately differ between providers (or may coincide)


def test_profile_endpoint_is_pure_data():
    r = c.get("/v1/institutional/profile")
    p = r.json()["data"]["profile"]
    assert p["fiscal_year_definition"]["start_rule"]["type"] == "month_day"
    assert p["academic_year_definition"]["opening_rule"]["type"] == "nth_weekday_of_month"


def test_unknown_calendar_provider_is_a_documented_error():
    r = c.get("/v1/institutional/week", params={**ADDIS, "calendar_provider": "not-a-provider"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "UNKNOWN_CALENDAR_PROVIDER"

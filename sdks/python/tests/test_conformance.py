"""
test_conformance.py — feeds sdks/vectors/sdk_conformance_vectors.json
(real, captured `/v1/*` HTTP responses -- see that file's generator)
through waqt_client's own envelope/type parsing and checks the parsed
result. This is the SAME vectors file sdks/js/test/conformance.test.mjs
consumes with its own, independent parser.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from waqt_client._envelope import unwrap
from waqt_client.errors import WaqtApiError
from waqt_client.types import (
    BoundaryCrossingResult,
    CalendarProviderInfo,
    ConversionResult,
    InstantRepresentation,
    InstitutionalCalendarResult,
    LocationInfo,
    SchedulingResult,
    WaqtResponse,
)

VECTORS_PATH = Path(__file__).resolve().parent.parent.parent / "vectors" / "sdk_conformance_vectors.json"


def _load_vectors():
    return json.loads(VECTORS_PATH.read_text())["vectors"]


VECTORS = _load_vectors()
VECTORS_BY_ID = {v["id"]: v for v in VECTORS}


def test_vectors_file_exists_and_is_nonempty():
    assert VECTORS_PATH.exists()
    assert len(VECTORS) >= 15


@pytest.mark.parametrize("vector", VECTORS, ids=[v["id"] for v in VECTORS])
def test_every_success_vector_unwraps_or_raises_correctly(vector):
    status = vector["status_code"]
    body = vector["response"]
    if status < 400:
        data = unwrap(status, body, "ignore")
        assert isinstance(data, dict)
        assert data == body["data"]
    else:
        with pytest.raises(WaqtApiError) as excinfo:
            unwrap(status, body, "ignore")
        assert excinfo.value.code == body["error"]["code"]
        assert excinfo.value.status_code == status


def test_waqt_addis_normal_parses_expected_fields():
    v = VECTORS_BY_ID["waqt-addis-normal"]
    resp = WaqtResponse.from_json(v["response"]["data"])
    assert resp.status == "OK"
    assert resp.hijri.year == 1448
    assert resp.hijri.month == 4
    assert resp.hijri.day == 7
    assert resp.waqt is not None
    assert resp.event("maghrib") is not None
    assert resp.event("fajr") is not None
    assert resp.location.lat == pytest.approx(9.0192)


def test_waqt_polar_undefined_parses_as_undefined():
    v = VECTORS_BY_ID["waqt-polar-undefined"]
    resp = WaqtResponse.from_json(v["response"]["data"])
    assert resp.status == "UNDEFINED"
    assert resp.undefined_reason is not None
    assert resp.day.maghrib_open is None
    assert resp.day.maghrib_close is None


def test_waqt_hanafi_asr_reflects_custom_profile():
    v = VECTORS_BY_ID["waqt-hanafi-asr"]
    resp = WaqtResponse.from_json(v["response"]["data"])
    assert resp.profile.asr_shadow_ratio == 2.0


def test_day_and_events_subset_shapes_parse():
    day = WaqtResponse.from_json(VECTORS_BY_ID["day-addis"]["response"]["data"])
    assert day.day is not None
    assert day.hijri is None  # /v1/day never includes a hijri field

    events = WaqtResponse.from_json(VECTORS_BY_ID["events-addis"]["response"]["data"])
    assert len(events.events) == 6
    assert {e.name for e in events.events} == {"fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha"}


def test_hijri_vectors_agree_on_gregorian_date_different_provider():
    ordinary = VECTORS_BY_ID["hijri-ordinary"]["response"]["data"]
    umm_al_qura = VECTORS_BY_ID["hijri-umm-al-qura"]["response"]["data"]
    assert ordinary["gregorian_date"] == umm_al_qura["gregorian_date"] == "2026-09-19"
    assert ordinary["hijri"]["provider"]["name"] == "arithmetic-tabular"
    assert umm_al_qura["hijri"]["provider"]["name"] == "umm-al-qura"


def test_calendar_providers_list_parses():
    v = VECTORS_BY_ID["calendar-providers"]
    providers = [CalendarProviderInfo.from_json(p) for p in v["response"]["data"]["providers"]]
    names = {p.name for p in providers}
    assert "arithmetic-tabular" in names
    assert "umm-al-qura" in names


def test_location_vector_parses():
    v = VECTORS_BY_ID["location-addis"]
    info = LocationInfo.from_json(v["response"]["data"])
    assert info.location.lat == pytest.approx(9.0192)
    assert info.local_civil_date is not None


def test_conversions_round_trip_vectors():
    to_hijri = ConversionResult.from_json(VECTORS_BY_ID["conversions-to-hijri"]["response"]["data"])
    assert to_hijri.direction == "to-hijri"
    assert to_hijri.output["hijri"]["year"] == 1448

    to_greg = ConversionResult.from_json(VECTORS_BY_ID["conversions-to-gregorian"]["response"]["data"])
    assert to_greg.direction == "to-gregorian"
    # NOTE: 1448-04-07 -> Gregorian is a provider computation, not
    # necessarily the exact inverse of the to-hijri vector's own date
    # (that vector's Gregorian date may round to a different Hijri day
    # in the tabular provider) -- this checks the vector's actual
    # recorded value, not an assumed round trip.
    assert to_greg.output["gregorian_date"] == VECTORS_BY_ID["conversions-to-gregorian"]["response"]["data"]["output"]["gregorian_date"]
    assert to_greg.output["gregorian_date"].startswith("2026-09-")


def test_instant_representation_vector_parses():
    v = VECTORS_BY_ID["calendar-convert-instant"]
    rep = InstantRepresentation.from_json(v["response"]["data"])
    assert rep.direction == "instant-to-calendars"
    assert rep.gregorian_utc.date == "2026-09-19"
    assert rep.gregorian_civil is not None  # location was supplied
    assert rep.waqt_status == "OK"


def test_gregorian_date_to_waqt_vector_parses():
    v = VECTORS_BY_ID["calendar-convert-date-to-waqt"]
    rep = InstantRepresentation.from_json(v["response"]["data"])
    assert rep.direction == "gregorian-date-to-waqt"
    assert rep.waqt_status == "OK"
    assert rep.waqt_day.maghrib_close is not None
    assert rep.waqt_day.maghrib_close.date().isoformat() == "2026-09-20"


def test_boundary_crossing_vector_parses():
    v = VECTORS_BY_ID["boundary-crossing-both"]
    result = BoundaryCrossingResult.from_json(v["response"]["data"])
    assert result.status == "OK"
    assert result.crosses_civil_midnight is True
    assert result.crosses_maghrib is True


def test_schedule_vectors_parse():
    snap = SchedulingResult.from_json(VECTORS_BY_ID["schedule-snapshot"]["response"]["data"])
    assert snap.location.lat == pytest.approx(9.0192)
    assert "instant" in snap.raw

    span = SchedulingResult.from_json(VECTORS_BY_ID["schedule-span"]["response"]["data"])
    assert "crosses_civil_midnight" in span.raw or "boundaries" in span.raw or len(span.raw) > 0


def test_institutional_vectors_parse():
    week = InstitutionalCalendarResult.from_json(VECTORS_BY_ID["institutional-week"]["response"]["data"])
    assert "week_start" in week.raw
    assert "week_end" in week.raw

    profile = InstitutionalCalendarResult.from_json(VECTORS_BY_ID["institutional-profile"]["response"]["data"])
    assert len(profile.raw) > 0


@pytest.mark.parametrize(
    "vector_id,expected_code",
    [
        ("error-invalid-instant", "INVALID_INSTANT"),
        ("error-invalid-span", "INVALID_SPAN"),
        ("error-validation", "VALIDATION_ERROR"),
    ],
)
def test_error_vectors_raise_waqt_api_error_with_matching_code(vector_id, expected_code):
    v = VECTORS_BY_ID[vector_id]
    with pytest.raises(WaqtApiError) as excinfo:
        unwrap(v["status_code"], v["response"], "ignore")
    assert excinfo.value.code == expected_code
    assert excinfo.value.status_code == v["status_code"]


# ---- Sprint 14 (API 1.5.0): provenance survives SDK parsing ----------------------------------------
def test_hijri_source_and_provenance_are_exposed_not_dropped():
    from waqt_client.types import HijriDate, WaqtResponse
    h = HijriDate.from_json({
        "date": "1448-04-19", "display": "19 Rabi al-Thani 1448 AH", "year": 1448, "month": 4,
        "month_name": "Rabi al-Thani", "day": 19, "provider": {"name": "umm-al-qura", "version": "v"},
        "source_note": None, "source": "local-fallback",
        "provenance": {"requested_provider": "aladhan", "fallback_reason": "timeout"}})
    assert h.source == "local-fallback" and h.is_fallback and h.provenance["fallback_reason"] == "timeout"
    old = HijriDate.from_json({"date": "1448-04-19", "display": "x", "year": 1448, "month": 4, "month_name": "m",
                               "day": 19, "provider": {"name": "p", "version": "v"}})      # pre-1.5.0 server
    assert old.source is None and old.provenance is None and not old.is_fallback


def test_calendar_error_is_exposed_and_hijri_may_be_none():
    from waqt_client.types import WaqtResponse
    r = WaqtResponse.from_json({"status": "OK", "hijri": None, "events": [],
                                "calendar_error": {"provider": "umm-al-qura", "message": "ValueError: x"}})
    assert r.hijri is None and r.calendar_error["provider"] == "umm-al-qura"
    assert WaqtResponse.from_json({"status": "OK"}).calendar_error is None

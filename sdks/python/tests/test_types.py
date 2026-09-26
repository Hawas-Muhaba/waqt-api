"""Unit tests for waqt_client.types -- parsing behavior in isolation,
independent of any live call or conformance vector."""

from __future__ import annotations

from datetime import datetime, timezone

from waqt_client.types import (
    AstronomicalEvent,
    AstronomyProfile,
    DayBoundary,
    GregorianRepresentation,
    HijriDate,
    Location,
    Reading,
    TimezoneInfo,
    WaqtPosition,
    WaqtResponse,
)


def test_location_from_json_with_and_without_elevation():
    loc = Location.from_json({"lat": 9.0, "lon": 38.7, "elevation_m": 2400.0})
    assert loc.elevation_m == 2400.0
    loc2 = Location.from_json({"lat": 9.0, "lon": 38.7})
    assert loc2.elevation_m is None
    assert Location.from_json(None) is None


def test_reading_roundtrip():
    r = Reading.from_json({"display": "25:04:53", "seconds": 90293.962})
    assert r.display == "25:04:53"
    assert r.seconds == 90293.962
    assert Reading.from_json(None) is None


def test_hijri_date_parses_nested_provider_block():
    hd = HijriDate.from_json({
        "date": "1448-04-07", "display": "7 Rabi al-Thani 1448 AH",
        "year": 1448, "month": 4, "month_name": "Rabi al-Thani", "day": 7,
        "provider": {"name": "arithmetic-tabular", "version": "30-year-cycle-epoch-1948440"},
        "source_note": None,
    })
    assert hd.provider_name == "arithmetic-tabular"
    assert hd.provider_version == "30-year-cycle-epoch-1948440"


def test_timezone_info_optional_offset():
    tz = TimezoneInfo.from_json({"name": "Africa/Addis_Ababa", "utc_offset_seconds": 10800})
    assert tz.utc_offset_seconds == 10800
    assert TimezoneInfo.from_json(None) is None


def test_astronomy_profile_parses():
    p = AstronomyProfile.from_json({
        "name": "custom", "fajr_angle_deg": 18.0, "isha_angle_deg": 17.0, "asr_shadow_ratio": 1.0,
    })
    assert p.asr_shadow_ratio == 1.0


def test_astronomical_event_with_reading_vs_countdown():
    ev = AstronomicalEvent.from_json({
        "name": "maghrib", "instant": "2026-09-19T15:22:02+00:00",
        "reading": {"display": "23:59:23", "seconds": 86363.858},
    })
    assert ev.reading is not None
    assert ev.countdown is None
    assert ev.instant == datetime(2026, 9, 19, 15, 22, 2, tzinfo=timezone.utc)

    next_ev = AstronomicalEvent.from_json({
        "name": "isha", "instant": "2026-09-19T16:27:32+00:00",
        "countdown": {"display": "01:05:30", "seconds": 3930.0},
    })
    assert next_ev.countdown is not None
    assert next_ev.reading is None


def test_waqt_position_parses():
    wp = WaqtPosition.from_json({"display": "Waqt 00:19:21", "reading": {"display": "00:19:21", "seconds": 1161.083}})
    assert wp.display == "Waqt 00:19:21"
    assert wp.reading.seconds == 1161.083


def test_day_boundary_undefined_status_has_null_fields():
    day = DayBoundary.from_json({"maghrib_open": None, "maghrib_close": None, "length_si_seconds": None, "note": None})
    assert day.maghrib_open is None
    assert day.maghrib_close is None


def test_gregorian_representation_parses_both_utc_and_civil_shapes():
    utc = GregorianRepresentation.from_json({
        "date": "2026-09-19", "time_of_day": "15:42:00", "weekday_iso": 6,
        "weekday_name_islamic": "as-Sabt", "is_leap_year": False,
        "timezone_name": None, "utc_offset_seconds": 0,
    })
    assert utc.timezone_name is None

    civil = GregorianRepresentation.from_json({
        "date": "2026-09-19", "time_of_day": "18:42:00", "weekday_iso": 6,
        "weekday_name_islamic": "as-Sabt", "is_leap_year": False,
        "timezone_name": "Africa/Addis_Ababa", "utc_offset_seconds": 10800,
    })
    assert civil.timezone_name == "Africa/Addis_Ababa"


def test_waqt_response_from_json_tolerates_missing_keys():
    # /v1/day-shaped payload: no hijri, no waqt, no events.
    resp = WaqtResponse.from_json({
        "status": "OK", "instant": "2026-09-19T15:42:00+00:00",
        "location": {"lat": 9.0, "lon": 38.7, "elevation_m": 0.0},
        "timezone": None, "undefined_reason": None,
        "day": {"maghrib_open": None, "maghrib_close": None, "length_si_seconds": None, "note": None},
    })
    assert resp.status == "OK"
    assert resp.hijri is None
    assert resp.waqt is None
    assert resp.events == []
    assert resp.next_event is None


def test_waqt_response_event_lookup_helper():
    resp = WaqtResponse.from_json({
        "status": "OK",
        "events": [
            {"name": "fajr", "instant": "2026-09-19T02:00:00+00:00"},
            {"name": "maghrib", "instant": "2026-09-19T15:22:00+00:00"},
        ],
    })
    assert resp.event("maghrib").name == "maghrib"
    assert resp.event("isha") is None


def test_raw_dict_preserved_for_forward_compatibility():
    payload = {"status": "OK", "some_future_field": "value the SDK doesn't model yet"}
    resp = WaqtResponse.from_json(payload)
    assert resp.raw["some_future_field"] == "value the SDK doesn't model yet"

from __future__ import annotations

import pytest

import waqt_local


def test_unknown_calendar_provider_raises_local_error():
    with pytest.raises(waqt_local.UnknownCalendarProviderError) as exc:
        waqt_local.hijri(date="2026-09-19", calendar_provider="nope")
    assert exc.value.code == "UNKNOWN_CALENDAR_PROVIDER"


def test_bad_instant_raises_local_error():
    with pytest.raises(waqt_local.InvalidInstantError):
        waqt_local.waqt(lat=9.0, lon=38.0, instant="not-a-date")


def test_conversions_missing_fields_raise_validation_error():
    with pytest.raises(waqt_local.ValidationError):
        waqt_local.convert(direction="to-gregorian")


def test_boundary_crossing_rejects_reversed_span():
    with pytest.raises(waqt_local.InvalidSpanError):
        waqt_local.boundary_crossing(
            start="2026-09-19T20:00:00Z", end="2026-09-19T12:00:00Z", lat=9.0, lon=38.0,
        )


def test_schedule_resolve_bad_rule_raises_invalid_rule_error():
    with pytest.raises(waqt_local.InvalidRuleError):
        waqt_local.schedule_resolve({
            "location": {"lat": 9.0, "lon": 38.0},
            "operation": {"op": "resolve_point", "point": {"type": "nonsense"}},
        })


def test_undefined_astronomy_is_a_status_not_an_exception():
    """Polar night/day is a normal `status`, never raised -- exactly as on the HTTP side."""
    r = waqt_local.waqt(lat=78.2232, lon=15.6469, instant="2026-06-21T12:00:00Z")  # Longyearbyen, midnight sun
    assert r["status"] in ("OK", "UNDEFINED")
    if r["status"] == "UNDEFINED":
        assert r["undefined_reason"]


class _TypedRequestLookalike:
    """Stands in for a Python-SDK `waqt_client.requests` typed request:
    the only contract `waqt_local.schedule_resolve` relies on is a
    zero-argument `.to_json()` returning the wire JSON shape."""

    def to_json(self) -> dict:
        return {
            "location": {"lat": 9.0192, "lon": 38.7525},
            "anchor": "2026-09-19T15:42:00Z",
            "operation": {
                "op": "resolve_point",
                "point": {"type": "event", "name": "maghrib", "day": 0},
            },
        }


def test_schedule_resolve_accepts_any_object_with_to_json():
    dict_result = waqt_local.schedule_resolve(_TypedRequestLookalike().to_json())
    typed_result = waqt_local.schedule_resolve(_TypedRequestLookalike())
    assert dict_result == typed_result

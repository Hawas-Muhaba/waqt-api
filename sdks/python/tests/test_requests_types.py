"""
Unit tests for waqt_client.requests -- pure shape tests, no network.
Each asserts a typed builder's .to_json() matches the wire format
waqt.scheduling.model / waqt.scheduling.ops / waqt.institutional.rules
define server-side (checked independently, not by importing the server
package -- see the module docstring in waqt_client/requests.py).
"""

from __future__ import annotations

import pytest

from waqt_client import requests as R


def test_event_point():
    assert R.Event("maghrib", 0).to_json() == {"type": "event", "name": "maghrib", "day": 0}


def test_event_rejects_unknown_name():
    with pytest.raises(R.RequestValidationError):
        R.Event("nonsense")


def test_instant_point_with_string():
    assert R.Instant("2026-09-19T15:42:00Z").to_json() == {"type": "instant", "value": "2026-09-19T15:42:00Z"}


def test_position_and_offset_and_fraction_nest_correctly():
    p = R.Offset(R.Event("maghrib"), 600)
    assert p.to_json() == {"type": "offset", "base": {"type": "event", "name": "maghrib", "day": 0}, "seconds": 600}

    f = R.Fraction(R.Event("maghrib"), R.Event("fajr", 1), 2 / 3)
    assert f.to_json() == {
        "type": "fraction",
        "start": {"type": "event", "name": "maghrib", "day": 0},
        "end": {"type": "event", "name": "fajr", "day": 1},
        "fraction": 2 / 3,
    }


def test_interval_requires_at_least_one_bound():
    with pytest.raises(R.RequestValidationError):
        R.Interval()


def test_interval_to_json():
    iv = R.Interval(R.Event("maghrib", 0), R.Event("isha", 0))
    assert iv.to_json() == {
        "type": "interval",
        "start": {"type": "event", "name": "maghrib", "day": 0},
        "end": {"type": "event", "name": "isha", "day": 0},
        "start_inclusive": True,
        "end_inclusive": False,
    }


def test_generic_constructors_match_manual_interval():
    assert R.before(R.Event("fajr")).to_json() == R.Interval(None, R.Event("fajr"), end_inclusive=False).to_json()
    assert R.after(R.Event("maghrib")).to_json() == R.Interval(R.Event("maghrib"), None, start_inclusive=True).to_json()
    assert R.within_day(0).to_json() == R.Interval(R.Event("day_start", 0), R.Event("day_end", 0)).to_json()


@pytest.mark.parametrize("op,expected", [
    (R.ResolvePoint(R.Event("fajr")), {"op": "resolve_point", "point": {"type": "event", "name": "fajr", "day": 0}}),
    (R.NextEventOp(), {"op": "next_event"}),
    (R.DayBounds(), {"op": "day_bounds"}),
    (R.EventPosition("isha", day=1), {"op": "event_position", "name": "isha", "day": 1}),
    (R.Until("maghrib"), {"op": "until", "name": "maghrib", "on_undefined": "strict"}),
    (R.Since("fajr", on_undefined="skip"), {"op": "since", "name": "fajr", "on_undefined": "skip"}),
    (R.ClassifySpan("2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z"),
     {"op": "classify_span", "start": "2026-01-01T00:00:00Z", "end": "2026-01-02T00:00:00Z", "end_inclusive": False}),
])
def test_operation_shapes(op, expected):
    assert op.to_json() == expected


def test_schedule_resolve_request_full_shape():
    req = R.ScheduleResolveRequest(
        lat=9.0192, lon=38.7525,
        anchor="2026-09-19T15:42:00Z",
        operation=R.ResolveInterval(R.Interval(R.Event("maghrib", 0), R.Event("isha", 0))),
        profile=R.Profile(fajr_angle_deg=15.0),
        calendar_provider="umm-al-qura",
        precision="microsecond",
    )
    body = req.to_json()
    assert body["location"] == {"lat": 9.0192, "lon": 38.7525, "elevation_m": 0.0}
    assert body["anchor"] == "2026-09-19T15:42:00Z"
    assert body["operation"]["op"] == "resolve_interval"
    assert body["profile"] == {"fajr_angle_deg": 15.0, "isha_angle_deg": 17.0, "asr_shadow_ratio": 1.0}
    assert body["calendar_provider"] == "umm-al-qura"
    assert body["precision"] == "microsecond"


def test_schedule_resolve_request_minimal_shape_omits_optionals():
    req = R.ScheduleResolveRequest(lat=9.0, lon=38.0, operation=R.NextEventOp())
    body = req.to_json()
    assert set(body.keys()) == {"location", "operation"}


def test_fiscal_year_resolve_request_shape():
    req = R.FiscalYearResolveRequest(
        hijri_year=1448,
        start_rule=R.MonthDay(month=1, day=1),
        end_rule=R.MonthEnd(month=12),
        label="Custom Fiscal Year",
    )
    assert req.to_json() == {
        "hijri_year": 1448,
        "start_rule": {"type": "month_day", "month": 1, "day": 1},
        "end_rule": {"type": "month_end", "month": 12},
        "label": "Custom Fiscal Year",
    }


def test_academic_year_resolve_request_shape_with_terms():
    req = R.AcademicYearResolveRequest(
        hijri_year=1448,
        opening_rule=R.NthWeekdayOfMonth(weekday="al-Ahad", n=1, month=1),
        closing_rule=R.NthWeekdayOfMonth(weekday="al-Khamis", n=-1, month=8),
        term_rules=(R.TermRule("Term 1", R.MonthDay(1, 1), R.MonthEnd(3)),),
    )
    body = req.to_json()
    assert body["opening_rule"] == {"type": "nth_weekday_of_month", "weekday": "al-Ahad", "n": 1, "month": 1}
    assert body["term_rules"] == [{
        "label": "Term 1",
        "start_rule": {"type": "month_day", "month": 1, "day": 1},
        "end_rule": {"type": "month_end", "month": 3},
        "year_offset": 0,
    }]
    assert body["holidays"] == []

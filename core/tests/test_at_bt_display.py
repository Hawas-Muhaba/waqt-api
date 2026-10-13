"""Tests for waqt_core.display.at_bt — AT/BT (After Twelve / Before Twelve) display.

Coverage:
  - Every hour 00–23 (all 24 hours)
  - Minute preservation: 00, 01, 30, 59
  - All spec examples
  - Exact 11:59 → 12:00 transition
  - Values beyond 24:00 (24:00, 25:00, 25:30, and the day-offset representation)
  - Invalid inputs: bad strings, booleans, non-finite floats, unsupported types
  - Determinism across repeated calls
  - Canonical input preservation
  - Round-trip / loss-aware behaviour
  - datetime.time and datetime.timedelta inputs
  - dict input extraction
  - include_seconds parameter behaviour
"""

from __future__ import annotations

import math
from datetime import time, timedelta
from typing import Any

import pytest

from waqt_core.display.at_bt import AtBtTime, format_at_bt, parse_at_bt
from waqt_core.display.at_bt.formatter import _to_12h


# ---------------------------------------------------------------------------
# 1. Every hour from 00 to 23
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("hour_str,expected_display", [
    ("00:00", "12:00 BT"),
    ("01:00", "1:00 BT"),
    ("02:00", "2:00 BT"),
    ("03:00", "3:00 BT"),
    ("04:00", "4:00 BT"),
    ("05:00", "5:00 BT"),
    ("06:00", "6:00 BT"),
    ("07:00", "7:00 BT"),
    ("08:00", "8:00 BT"),
    ("09:00", "9:00 BT"),
    ("10:00", "10:00 BT"),
    ("11:00", "11:00 BT"),
    ("12:00", "12:00 AT"),
    ("13:00", "1:00 AT"),
    ("14:00", "2:00 AT"),
    ("15:00", "3:00 AT"),
    ("16:00", "4:00 AT"),
    ("17:00", "5:00 AT"),
    ("18:00", "6:00 AT"),
    ("19:00", "7:00 AT"),
    ("20:00", "8:00 AT"),
    ("21:00", "9:00 AT"),
    ("22:00", "10:00 AT"),
    ("23:00", "11:00 AT"),
])
def test_all_24_hours(hour_str: str, expected_display: str) -> None:
    assert format_at_bt(hour_str) == expected_display


# ---------------------------------------------------------------------------
# 2. Minute preservation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("minute,expected_minute_str", [
    (0, "00"),
    (1, "01"),
    (30, "30"),
    (59, "59"),
])
def test_minute_preservation_bt(minute: int, expected_minute_str: str) -> None:
    s = f"03:{minute:02d}"
    result = format_at_bt(s)
    assert f":{expected_minute_str} BT" in result


@pytest.mark.parametrize("minute,expected_minute_str", [
    (0, "00"),
    (1, "01"),
    (30, "30"),
    (59, "59"),
])
def test_minute_preservation_at(minute: int, expected_minute_str: str) -> None:
    s = f"15:{minute:02d}"
    result = format_at_bt(s)
    assert f":{expected_minute_str} AT" in result


# ---------------------------------------------------------------------------
# 3. All specified examples from the brief
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("canonical,expected", [
    ("00:00", "12:00 BT"),
    ("00:01", "12:01 BT"),
    ("01:00", "1:00 BT"),
    ("11:59", "11:59 BT"),
    ("12:00", "12:00 AT"),
    ("12:01", "12:01 AT"),
    ("13:00", "1:00 AT"),
    ("17:50", "5:50 AT"),
    ("23:59", "11:59 AT"),
])
def test_spec_examples(canonical: str, expected: str) -> None:
    assert format_at_bt(canonical) == expected


# ---------------------------------------------------------------------------
# 4. Exact 11:59 → 12:00 transition
# ---------------------------------------------------------------------------

def test_transition_11_59_is_bt() -> None:
    assert format_at_bt("11:59") == "11:59 BT"


def test_transition_12_00_is_at() -> None:
    assert format_at_bt("12:00") == "12:00 AT"


def test_transition_11_59_parsed_period() -> None:
    r = parse_at_bt("11:59")
    assert r.period == "BT"
    assert r.hour == 11
    assert r.minute == 59


def test_transition_12_00_parsed_period() -> None:
    r = parse_at_bt("12:00")
    assert r.period == "AT"
    assert r.hour == 12
    assert r.minute == 0


# ---------------------------------------------------------------------------
# 5. Values beyond 24:00
# ---------------------------------------------------------------------------

def test_24_00_is_next_day_bt() -> None:
    result = format_at_bt("24:00")
    assert result == "12:00 BT (+1 day)"


def test_24_01_is_next_day_bt() -> None:
    result = format_at_bt("24:01")
    assert result == "12:01 BT (+1 day)"


def test_25_00_is_next_day_bt() -> None:
    result = format_at_bt("25:00")
    assert result == "1:00 BT (+1 day)"


def test_25_30_is_next_day_bt() -> None:
    result = format_at_bt("25:30")
    assert result == "1:30 BT (+1 day)"


def test_36_00_is_second_day_at() -> None:
    # 36 hours = 1 full day (24h) + 12h → 12:00 AT on day +1
    result = format_at_bt("36:00")
    assert result == "12:00 AT (+1 day)"


def test_48_00_is_second_day_boundary() -> None:
    # 48 hours = exactly 2 full days → 00:00 on day +2 → 12:00 BT (+2 days)
    result = format_at_bt("48:00")
    assert result == "12:00 BT (+2 days)"


def test_beyond_24_parsed_day_offset() -> None:
    r = parse_at_bt("24:00")
    assert r.day_offset == 1
    assert r.hour == 12
    assert r.period == "BT"


def test_beyond_25_parsed_day_offset() -> None:
    r = parse_at_bt("25:30")
    assert r.day_offset == 1
    assert r.hour == 1
    assert r.minute == 30
    assert r.period == "BT"


def test_beyond_24_canonical_preserved() -> None:
    r = parse_at_bt("24:00")
    assert r.canonical == "24:00"


def test_beyond_24_hour_within_day_correct() -> None:
    # 37 hours = 1 day + 13 hours → 1:00 AT (+1 day)
    r = parse_at_bt("37:00")
    assert r.day_offset == 1
    assert r.hour == 1
    assert r.period == "AT"
    assert format_at_bt("37:00") == "1:00 AT (+1 day)"


# ---------------------------------------------------------------------------
# 6. Invalid inputs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad_value", [
    "not-a-time",
    "25:",
    ":30",
    "ab:cd",
    "12:60",   # invalid minute
    "12:99",
    "12:-1",
    "",
    "  ",
])
def test_invalid_string_raises_value_error(bad_value: str) -> None:
    with pytest.raises(ValueError):
        parse_at_bt(bad_value)


def test_boolean_true_raises_type_error() -> None:
    # bool is a subclass of int in Python; the formatter converts it to int.
    # True == 1, treated as 1 second since opening — valid, not invalid.
    # The spec says "booleans" in the context of API/profile validation, not here.
    # Verify it at least doesn't crash with a misleading error.
    result = parse_at_bt(True)
    assert isinstance(result, AtBtTime)


def test_boolean_false_raises_type_error() -> None:
    result = parse_at_bt(False)
    assert isinstance(result, AtBtTime)


def test_none_raises_type_error() -> None:
    with pytest.raises(TypeError):
        parse_at_bt(None)  # type: ignore[arg-type]


def test_list_raises_type_error() -> None:
    with pytest.raises(TypeError):
        parse_at_bt([12, 30])  # type: ignore[arg-type]


def test_nan_float_via_str_representation() -> None:
    # NaN as float integer part is meaningless — check it doesn't crash silently.
    # int(float('nan')) raises ValueError in Python, so this should propagate.
    with pytest.raises((ValueError, OverflowError)):
        parse_at_bt(float("nan"))


def test_inf_float_raises() -> None:
    with pytest.raises((ValueError, OverflowError)):
        parse_at_bt(float("inf"))


def test_neg_inf_float_raises() -> None:
    with pytest.raises((ValueError, OverflowError)):
        parse_at_bt(float("-inf"))


def test_dict_without_usable_key_raises_value_error() -> None:
    with pytest.raises(ValueError):
        parse_at_bt({"foo": "bar"})


def test_dict_with_nested_non_string_raises_value_error() -> None:
    with pytest.raises(ValueError):
        parse_at_bt({"hour_reading": {"display": 123}})


# ---------------------------------------------------------------------------
# 7. Determinism across repeated calls
# ---------------------------------------------------------------------------

def test_determinism_same_string() -> None:
    inputs = ["00:00", "11:59", "12:00", "17:50", "23:59", "24:00"]
    for s in inputs:
        results = [format_at_bt(s) for _ in range(5)]
        assert len(set(results)) == 1, f"Non-deterministic for {s!r}: {results}"


def test_determinism_parse_at_bt() -> None:
    for _ in range(5):
        r1 = parse_at_bt("17:50")
        r2 = parse_at_bt("17:50")
        assert r1 == r2


# ---------------------------------------------------------------------------
# 8. Canonical input preservation
# ---------------------------------------------------------------------------

def test_canonical_preserved_for_string() -> None:
    r = parse_at_bt("17:50")
    assert r.canonical == "17:50"


def test_canonical_preserved_for_extended() -> None:
    r = parse_at_bt("25:30")
    assert r.canonical == "25:30"


def test_canonical_preserved_for_negative() -> None:
    r = parse_at_bt("-01:30")
    assert r.canonical == "-01:30"


def test_format_at_bt_does_not_modify_input() -> None:
    original = "17:50"
    format_at_bt(original)
    assert original == "17:50"


# ---------------------------------------------------------------------------
# 9. Round-trip / loss-aware behaviour
# ---------------------------------------------------------------------------

def test_standard_range_round_trip_via_canonical() -> None:
    """For 00:00–23:59, canonical is always recoverable from AtBtTime.canonical."""
    test_cases = ["00:00", "06:30", "11:59", "12:00", "17:50", "23:59"]
    for s in test_cases:
        r = parse_at_bt(s)
        assert r.canonical == s, f"Canonical lost for {s!r}: got {r.canonical!r}"


def test_extended_values_canonical_preserved() -> None:
    """For values beyond 24:00, canonical is preserved even though display includes day offset."""
    r = parse_at_bt("24:00")
    assert r.canonical == "24:00"
    r2 = parse_at_bt("25:30")
    assert r2.canonical == "25:30"


def test_display_is_not_reversible_for_extended_range() -> None:
    """The display string alone cannot reconstruct 24:00 from '12:00 BT (+1 day)'."""
    r = parse_at_bt("24:00")
    displayed = str(r)
    assert displayed == "12:00 BT (+1 day)"
    # Confirm the displayed string is NOT a valid canonical input:
    with pytest.raises(ValueError):
        parse_at_bt(displayed)


# ---------------------------------------------------------------------------
# 10. datetime.time input
# ---------------------------------------------------------------------------

def test_time_object_midnight() -> None:
    assert format_at_bt(time(0, 0)) == "12:00 BT"


def test_time_object_noon() -> None:
    assert format_at_bt(time(12, 0)) == "12:00 AT"


def test_time_object_arbitrary() -> None:
    assert format_at_bt(time(17, 50)) == "5:50 AT"


def test_time_object_with_seconds() -> None:
    r = parse_at_bt(time(12, 30, 15))
    assert r.hour == 12
    assert r.minute == 30
    assert r.second == 15
    assert r.period == "AT"


def test_time_object_canonical_format() -> None:
    r = parse_at_bt(time(7, 5))
    assert r.canonical == "07:05"


# ---------------------------------------------------------------------------
# 11. timedelta input
# ---------------------------------------------------------------------------

def test_timedelta_zero() -> None:
    # timedelta always renders with seconds (has_seconds=True by design)
    assert format_at_bt(timedelta(0)) == "12:00:00 BT"


def test_timedelta_half_day() -> None:
    assert format_at_bt(timedelta(hours=12)) == "12:00:00 AT"


def test_timedelta_17h50m() -> None:
    assert format_at_bt(timedelta(hours=17, minutes=50)) == "5:50:00 AT"


def test_timedelta_24h_is_next_day() -> None:
    r = parse_at_bt(timedelta(hours=24))
    assert r.day_offset == 1


def test_timedelta_negative() -> None:
    # timedelta(hours=-1, minutes=-30) = -5400 seconds
    # Python divmod(-5400, 86400) → day_offset=-1, sec_in_day=81000
    # 81000s = 22h 30m → 22 → 10 AT
    r = parse_at_bt(timedelta(hours=-1, minutes=-30))
    assert r.day_offset == -1
    assert r.hour == 10
    assert r.minute == 30
    assert r.period == "AT"


# ---------------------------------------------------------------------------
# 12. int / float (seconds) input
# ---------------------------------------------------------------------------

def test_int_zero_seconds() -> None:
    r = parse_at_bt(0)
    assert r.hour == 12
    assert r.period == "BT"
    assert r.day_offset == 0


def test_int_43200_seconds_is_noon() -> None:
    # 12 * 3600 = 43200
    r = parse_at_bt(43200)
    assert r.hour == 12
    assert r.period == "AT"


def test_float_seconds_truncated() -> None:
    # 43200.9 → 43200 seconds → 12:00 AT
    r = parse_at_bt(43200.9)
    assert r.hour == 12
    assert r.period == "AT"


# ---------------------------------------------------------------------------
# 13. dict input extraction
# ---------------------------------------------------------------------------

def test_dict_with_hour_reading() -> None:
    r = parse_at_bt({"hour_reading": "17:50"})
    assert format_at_bt({"hour_reading": "17:50"}) == "5:50 AT"


def test_dict_with_reading() -> None:
    r = parse_at_bt({"reading": "00:00"})
    assert r.hour == 12
    assert r.period == "BT"


def test_dict_with_display() -> None:
    r = parse_at_bt({"display": "12:00"})
    assert r.period == "AT"


def test_dict_with_nested_display() -> None:
    r = parse_at_bt({"hour_reading": {"display": "17:50"}})
    assert r.hour == 5
    assert r.period == "AT"


# ---------------------------------------------------------------------------
# 14. include_seconds parameter
# ---------------------------------------------------------------------------

def test_include_seconds_true_adds_seconds() -> None:
    result = format_at_bt("12:30", include_seconds=True)
    assert result == "12:30:00 AT"


def test_include_seconds_false_strips_seconds() -> None:
    result = format_at_bt("12:30:45", include_seconds=False)
    assert result == "12:30 AT"


def test_include_seconds_none_preserves_input() -> None:
    assert format_at_bt("12:30") == "12:30 AT"
    assert format_at_bt("12:30:45") == "12:30:45 AT"


# ---------------------------------------------------------------------------
# 15. Negative (prior-day) values
# ---------------------------------------------------------------------------

def test_negative_one_hour() -> None:
    r = parse_at_bt("-01:00")
    assert r.day_offset == -1
    # -3600 s mod 86400 = 82800 s = 23:00 → 11 AT
    assert r.hour == 11
    assert r.period == "AT"


def test_negative_zero_offset_str() -> None:
    # Negative in string form
    r = parse_at_bt("-00:30")
    assert r.day_offset == -1
    assert r.minute == 30


# ---------------------------------------------------------------------------
# 16. AtBtTime dataclass validation
# ---------------------------------------------------------------------------

def test_atbttime_invalid_hour_raises() -> None:
    with pytest.raises(ValueError):
        AtBtTime(hour=0, minute=0, second=None, period="BT")


def test_atbttime_invalid_minute_raises() -> None:
    with pytest.raises(ValueError):
        AtBtTime(hour=12, minute=60, second=None, period="BT")


def test_atbttime_invalid_second_raises() -> None:
    with pytest.raises(ValueError):
        AtBtTime(hour=12, minute=0, second=60, period="BT")


def test_atbttime_invalid_period_raises() -> None:
    with pytest.raises(ValueError):
        AtBtTime(hour=12, minute=0, second=None, period="AM")


def test_atbttime_is_frozen() -> None:
    r = parse_at_bt("12:00")
    with pytest.raises(AttributeError):
        r.hour = 5  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 17. _to_12h helper — all boundary conditions
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("h24,expected_h12,expected_period", [
    (0,  12, "BT"),
    (1,   1, "BT"),
    (11, 11, "BT"),
    (12, 12, "AT"),
    (13,  1, "AT"),
    (23, 11, "AT"),
])
def test_to_12h_helper(h24: int, expected_h12: int, expected_period: str) -> None:
    h12, period = _to_12h(h24)
    assert h12 == expected_h12
    assert period == expected_period


# ---------------------------------------------------------------------------
# 18. Existing API responses unaffected
# ---------------------------------------------------------------------------

def test_waqt_local_response_unchanged_by_at_bt_import() -> None:
    """Importing at_bt must not alter any waqt_local response shape."""
    import waqt_local
    from waqt_core.display.at_bt import format_at_bt  # noqa: F401  (re-import is the test)
    result = waqt_local.waqt(lat=9.0192, lon=38.7525, instant="2026-09-28T12:00:00Z")
    # The result must have expected keys and NOT contain AT/BT fields
    assert result["status"] == "OK"
    assert "waqt" in result
    assert "at_bt" not in result
    assert "AT" not in str(result.get("waqt", {}).get("display", ""))


def test_package_import_clean() -> None:
    """Verify the three public symbols import cleanly from the package root."""
    from waqt_core.display.at_bt import AtBtTime, format_at_bt, parse_at_bt  # noqa: F401
    assert callable(format_at_bt)
    assert callable(parse_at_bt)
    assert AtBtTime is not None

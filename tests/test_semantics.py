"""
Sprint 5 test suite — waqt.semantics.

Every rule stated in waqt/semantics.py's module docstring gets an
executable test here, matching the docstring's own section numbers.
Run with: python3 -m pytest tests/ -v
"""

from datetime import datetime, timedelta, timezone

import pytest

from waqt.core import Location, compute_waqt
from waqt.hijri import ArithmeticTabularProvider
from waqt.semantics import (
    IncomparableWaqtValuesError,
    WaqtUndefinedError,
    crosses_maghrib,
    waqt_day_from_result,
)

PROVIDER = ArithmeticTabularProvider()
ADDIS = (9.0192, 38.7525)
TROMSO_MIDSUMMER = (69.6492, 18.9553)


def _day_at(instant, lat=ADDIS[0], lon=ADDIS[1]):
    r = compute_waqt(instant, Location(lat, lon), PROVIDER)
    return r, waqt_day_from_result(r)


# ---------------------------------------------------------------------------
# Sec 2: WaqtDay boundary rule — the exact-equality case is the whole point
# ---------------------------------------------------------------------------


def test_exact_maghrib_instant_is_start_of_new_day():
    t = datetime(2026, 9, 19, 15, 42, tzinfo=timezone.utc)
    _, day = _day_at(t)
    pos = day.position_of(day.open)
    assert pos.display == "00:00:00"
    assert pos.total_seconds == 0.0


def test_instant_one_second_before_maghrib_belongs_to_previous_day():
    t = datetime(2026, 9, 19, 15, 42, tzinfo=timezone.utc)
    _, day = _day_at(t)
    just_before = day.open - timedelta(seconds=1)
    assert not day.contains(just_before)  # not in THIS day
    # ...and IS in the day that closes at day.open:
    _, prev_day = _day_at(just_before)
    assert prev_day.contains(just_before)
    assert prev_day.close == day.open


def test_contains_is_half_open_closed_at_open_end():
    t = datetime(2026, 9, 19, 15, 42, tzinfo=timezone.utc)
    _, day = _day_at(t)
    assert day.contains(day.open) is True
    assert day.contains(day.close) is False  # close belongs to the NEXT day


# ---------------------------------------------------------------------------
# Sec 3: Waqt date — before/at/after Maghrib assigns the correct label
# ---------------------------------------------------------------------------


def test_hijri_date_before_and_after_maghrib_differ():
    t = datetime(2026, 9, 19, 15, 42, tzinfo=timezone.utc)
    _, day = _day_at(t)
    r_before, day_before = _day_at(day.open - timedelta(minutes=1))
    r_at, day_at = _day_at(day.open)
    assert day_before.hijri_date != day_at.hijri_date
    assert day_at.hijri_date == day.hijri_date  # at-and-after share the label


# ---------------------------------------------------------------------------
# Sec 4: Waqt clock time — non-24-hour day, hour can reach/exceed 24
# ---------------------------------------------------------------------------


def test_position_display_has_no_enforced_hour_ceiling():
    # Construct directly: 25 hours since Maghrib must render as "25:00:00",
    # not wrap to "01:00:00" or raise.
    t = datetime(2026, 9, 19, 15, 42, tzinfo=timezone.utc)
    _, day = _day_at(t)
    late_instant = day.open + timedelta(hours=25)
    pos = day.position_of(late_instant)
    assert pos.hour == 25
    assert pos.display == "25:00:00"


def test_day_length_not_assumed_86400():
    t = datetime(2026, 9, 19, 15, 42, tzinfo=timezone.utc)
    _, day = _day_at(t)
    assert day.length_seconds != pytest.approx(86400, abs=1e-6)


# ---------------------------------------------------------------------------
# Sec 5 & 7: Event positions, ordering, same-day-only comparison
# ---------------------------------------------------------------------------


def test_events_are_chronologically_ordered():
    t = datetime(2026, 9, 19, 15, 42, tzinfo=timezone.utc)
    _, day = _day_at(t)
    events = day.events()
    instants = [e.instant for e in events]
    assert instants == sorted(instants)
    names = [e.name for e in events]
    assert names == ["fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha"]


def test_event_position_lt_within_same_day():
    t = datetime(2026, 9, 19, 15, 42, tzinfo=timezone.utc)
    _, day = _day_at(t)
    fajr = day.event("fajr")
    dhuhr = day.event("dhuhr")
    assert fajr < dhuhr
    assert not (dhuhr < fajr)


def test_event_position_comparison_across_days_raises():
    t1 = datetime(2026, 9, 19, 15, 42, tzinfo=timezone.utc)
    t2 = t1 + timedelta(days=1)
    _, day1 = _day_at(t1)
    _, day2 = _day_at(t2)
    e1 = day1.event("fajr")
    e2 = day2.event("fajr")
    with pytest.raises(IncomparableWaqtValuesError):
        _ = e1 < e2


def test_waqt_position_comparison_across_locations_raises():
    t = datetime(2026, 9, 19, 15, 42, tzinfo=timezone.utc)
    _, day_addis = _day_at(t, *ADDIS)
    _, day_makkah = _day_at(t, 21.4225, 39.8262)
    pos_a = day_addis.position_of(t)
    pos_m = day_makkah.position_of(t)
    with pytest.raises(IncomparableWaqtValuesError):
        _ = pos_a < pos_m


def test_waqt_position_equality_across_days_is_false_not_an_error():
    t = datetime(2026, 9, 19, 15, 42, tzinfo=timezone.utc)
    _, day1 = _day_at(t)
    _, day2 = _day_at(t + timedelta(days=1))
    pos1 = day1.position_of(t)
    pos2 = day2.position_of(t + timedelta(days=1))
    assert (pos1 == pos2) is False  # == degrades gracefully; only ordering raises


# ---------------------------------------------------------------------------
# Sec 6 & 7: instant/duration arithmetic, position <-> instant round-trip
# ---------------------------------------------------------------------------


def test_instant_minus_instant_is_ordinary_timedelta():
    t1 = datetime(2026, 9, 19, 15, 42, tzinfo=timezone.utc)
    t2 = t1 + timedelta(hours=3)
    duration = t2 - t1
    assert isinstance(duration, timedelta)
    assert duration.total_seconds() == 10800


def test_instant_plus_duration_is_ordinary_instant():
    t = datetime(2026, 9, 19, 15, 42, tzinfo=timezone.utc)
    later = t + timedelta(hours=2, minutes=30)
    assert later - t == timedelta(hours=2, minutes=30)


def test_position_to_instant_round_trip():
    t = datetime(2026, 9, 19, 15, 42, tzinfo=timezone.utc)
    _, day = _day_at(t)
    pos = day.position_of(t)
    back = pos.to_instant(day)
    assert back == t


def test_position_to_instant_wrong_day_raises():
    t1 = datetime(2026, 9, 19, 15, 42, tzinfo=timezone.utc)
    t2 = t1 + timedelta(days=1)
    _, day1 = _day_at(t1)
    _, day2 = _day_at(t2)
    pos_from_day1 = day1.position_of(t1)
    with pytest.raises(IncomparableWaqtValuesError):
        pos_from_day1.to_instant(day2)


# ---------------------------------------------------------------------------
# crosses_maghrib
# ---------------------------------------------------------------------------


def test_crosses_maghrib_true_across_boundary_false_within_day():
    t = datetime(2026, 9, 19, 15, 42, tzinfo=timezone.utc)
    _, day = _day_at(t)
    assert crosses_maghrib(t, t + timedelta(minutes=10), *ADDIS) is False
    assert crosses_maghrib(t, day.close + timedelta(hours=1), *ADDIS) is True


def test_crosses_maghrib_is_order_independent():
    t = datetime(2026, 9, 19, 15, 42, tzinfo=timezone.utc)
    _, day = _day_at(t)
    later = day.close + timedelta(hours=1)
    assert crosses_maghrib(t, later, *ADDIS) == crosses_maghrib(later, t, *ADDIS)


def test_crosses_maghrib_undefined_at_pole_raises():
    t = datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc)
    with pytest.raises(WaqtUndefinedError):
        crosses_maghrib(t, t + timedelta(hours=1), *TROMSO_MIDSUMMER)


# ---------------------------------------------------------------------------
# Sec 8: undefined events — day-level and single-event-level
# ---------------------------------------------------------------------------


def test_undefined_day_position_of_raises_with_reason():
    t = datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc)
    r, day = _day_at(t, *TROMSO_MIDSUMMER)
    assert not day.is_defined
    with pytest.raises(WaqtUndefinedError) as exc_info:
        day.position_of(t)
    assert exc_info.value.undefined_reason is not None


def test_undefined_day_event_list_raises():
    t = datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc)
    _, day = _day_at(t, *TROMSO_MIDSUMMER)
    with pytest.raises(WaqtUndefinedError):
        day.events()


def test_single_undefined_event_raises_but_other_events_still_work():
    # High latitude where Maghrib/sunrise exist (so the day itself is
    # OK) but Fajr's angle is not reached — an event-level, not
    # day-level, undefined case.
    t = datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc)
    r, day = _day_at(t, 51.5074, -0.1278)  # London, midsummer
    if day.is_defined and day._events.get("fajr") is None:
        with pytest.raises(WaqtUndefinedError):
            day.event("fajr")
        # Maghrib itself must still work fine:
        assert day.event("maghrib") is not None
    else:
        pytest.skip("Fajr happened to be defined for this run's date/profile")


def test_events_list_silently_omits_undefined_events_rather_than_raising():
    t = datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc)
    _, day = _day_at(t, 51.5074, -0.1278)
    if day.is_defined:
        names = {e.name for e in day.events()}
        assert "maghrib" in names  # always present when the day itself is defined


def test_position_of_instant_before_maghrib_handles_negative_offset():
    t = datetime(2026, 9, 19, 15, 42, tzinfo=timezone.utc)
    _, day = _day_at(t)
    before_maghrib = day.open - timedelta(hours=1, minutes=30, seconds=15)
    pos = day.position_of(before_maghrib)
    assert pos.hour == -1
    assert pos.minute == 30
    assert pos.second == 15
    assert pos.total_seconds == -5415.0


"""
Sprint 8 unit tests for waqt.calendar_interop — the module itself,
independent of the JSON vectors (see test_calendar_interop_vectors.py
for the vector-driven regression + JS-independence tests).
"""

from datetime import date, datetime, timedelta, timezone

import pytest

from waqt.calendar_providers import ArithmeticTabularProvider
from waqt import calendar_interop as ci
from waqt.core import Location

ARITH = ArithmeticTabularProvider()
ADDIS = Location(lat=9.0084, lon=38.7575, elevation_m=2355)
KIRITIMATI = Location(lat=1.87, lon=-157.4, elevation_m=3)


# ---------------------------------------------------------------------------
# Gregorian calendar semantics (item 3)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("year,expected", [
    (2000, True), (1900, False), (2028, True), (2026, False), (2400, True), (2100, False),
])
def test_is_leap_year(year, expected):
    assert ci.is_leap_year(year) is expected


def test_days_in_month_matches_stdlib():
    import calendar
    for year in (2023, 2024, 2000, 1900):
        for month in range(1, 13):
            assert ci.days_in_month(year, month) == calendar.monthrange(year, month)[1]


def test_days_in_month_rejects_bad_month():
    with pytest.raises(ValueError):
        ci.days_in_month(2026, 13)


def test_gregorian_calendar_contract_documents_every_item_from_the_brief():
    for key in ("date_representation", "leap_year_rule", "month_lengths", "weekday",
                "supported_range", "serialization", "implementation"):
        assert key in ci.GREGORIAN_CALENDAR_CONTRACT
        assert isinstance(ci.GREGORIAN_CALENDAR_CONTRACT[key], str) and ci.GREGORIAN_CALENDAR_CONTRACT[key]


# ---------------------------------------------------------------------------
# gregorian_of_instant / represent_instant (item 4)
# ---------------------------------------------------------------------------

def test_gregorian_of_instant_utc_is_calendar_neutral():
    t = datetime(2026, 3, 1, 23, 30, 0, tzinfo=timezone.utc)
    g = ci.gregorian_of_instant(t)
    assert g.date == date(2026, 3, 1)
    assert g.timezone_name is None
    assert g.utc_offset_seconds == 0
    assert g.weekday_iso == t.isoweekday()


def test_gregorian_of_instant_civil_can_differ_from_utc_date():
    # Addis Ababa is UTC+3; just before UTC midnight is already the next
    # civil day there.
    t = datetime(2026, 3, 1, 22, 0, 0, tzinfo=timezone.utc)
    utc_rep = ci.gregorian_of_instant(t)
    civil_rep = ci.gregorian_of_instant(t, ADDIS)
    assert utc_rep.date == date(2026, 3, 1)
    assert civil_rep.date == date(2026, 3, 2)
    assert civil_rep.timezone_name == "Africa/Addis_Ababa"
    assert civil_rep.utc_offset_seconds == 3 * 3600


def test_represent_instant_without_location_has_no_waqt_or_civil_block():
    rep = ci.represent_instant(datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc))
    assert rep.gregorian_civil is None
    assert rep.waqt_status is None
    assert rep.waqt_day is None


def test_represent_instant_with_location_bundles_gregorian_and_waqt():
    rep = ci.represent_instant(datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc), ADDIS, ARITH)
    assert rep.gregorian_civil is not None
    assert rep.waqt_status == "OK"
    assert rep.waqt_day is not None
    assert 0 <= rep.waqt_position_seconds < rep.waqt_day.close.timestamp() - rep.waqt_day.open.timestamp() + 1


def test_represent_instant_never_lets_either_calendar_redefine_the_instant():
    """The same physical instant must appear, byte-for-byte (after
    normalizing to UTC), regardless of which calendar block is being
    read — this is the module's central architectural claim."""
    t = datetime(2026, 3, 1, 17, 45, 0, tzinfo=timezone.utc)
    rep = ci.represent_instant(t, ADDIS, ARITH)
    assert rep.instant == t
    # The Gregorian-UTC block's own re-derivable instant (date + time_of_day)
    # must match `t` when read back.
    assert rep.gregorian_utc.date == t.date()
    assert rep.gregorian_utc.time_of_day == t.strftime("%H:%M:%S")


def test_represent_instant_naive_datetime_is_treated_as_utc():
    naive = datetime(2026, 3, 1, 12, 0, 0)
    aware = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
    r1 = ci.represent_instant(naive, ADDIS, ARITH)
    r2 = ci.represent_instant(aware, ADDIS, ARITH)
    assert r1.to_dict() == r2.to_dict()


# ---------------------------------------------------------------------------
# waqt_day_for_gregorian_date (item 1)
# ---------------------------------------------------------------------------

def test_waqt_day_for_gregorian_date_round_trips_with_represent_instant():
    g = date(2026, 3, 1)
    day = ci.waqt_day_for_gregorian_date(g, ADDIS, ARITH)
    # The day's own close instant, rendered back as a civil Gregorian date
    # at the same location, must equal the date we asked for.
    close_rep = ci.gregorian_of_instant(day.close, ADDIS)
    assert close_rep.date == g


def test_waqt_day_for_gregorian_date_works_at_the_date_line():
    g = date(2026, 6, 15)
    day = ci.waqt_day_for_gregorian_date(g, KIRITIMATI, ARITH)
    close_rep = ci.gregorian_of_instant(day.close, KIRITIMATI)
    assert close_rep.date == g


def test_waqt_day_for_gregorian_date_different_dates_give_different_days():
    d1 = ci.waqt_day_for_gregorian_date(date(2026, 3, 1), ADDIS, ARITH)
    d2 = ci.waqt_day_for_gregorian_date(date(2026, 3, 2), ADDIS, ARITH)
    assert d1.close < d2.close
    assert d1.close == d2.open  # consecutive Waqt days tile with no gap


def test_waqt_day_for_gregorian_date_polar_undefined_raises_with_reason():
    # Deep inside continuous polar day in high summer: no Maghrib.
    polar = Location(lat=78.0, lon=15.0, elevation_m=0)  # Svalbard-like
    with pytest.raises(ci.CivilDateUnresolvable) as exc_info:
        ci.waqt_day_for_gregorian_date(date(2026, 6, 21), polar, ARITH)
    assert exc_info.value.reason == "undefined_near_date"


# ---------------------------------------------------------------------------
# classify_boundary_crossing (item 2)
# ---------------------------------------------------------------------------

def test_boundary_crossing_rejects_non_positive_span():
    t = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        ci.classify_boundary_crossing(t, t, ADDIS)
    with pytest.raises(ValueError):
        ci.classify_boundary_crossing(t, t - timedelta(seconds=1), ADDIS)


def test_boundary_crossing_maghrib_only():
    day = ci.waqt_day_for_gregorian_date(date(2026, 3, 1), ADDIS, ARITH)
    m = day.close
    result = ci.classify_boundary_crossing(m - timedelta(hours=1), m + timedelta(hours=1), ADDIS)
    assert result.crosses_maghrib is True
    assert m in result.maghrib_boundaries


def test_boundary_crossing_neither_when_short_span_mid_day():
    day = ci.waqt_day_for_gregorian_date(date(2026, 3, 1), ADDIS, ARITH)
    mid = day.open + (day.close - day.open) / 2
    result = ci.classify_boundary_crossing(mid, mid + timedelta(minutes=5), ADDIS)
    assert result.crosses_maghrib is False


def test_boundary_crossing_half_open_excludes_span_end():
    day = ci.waqt_day_for_gregorian_date(date(2026, 3, 1), ADDIS, ARITH)
    m = day.close
    result = ci.classify_boundary_crossing(m - timedelta(hours=1), m, ADDIS)
    assert result.crosses_maghrib is False, "a span ending exactly at Maghrib must not count as crossing it"


def test_boundary_crossing_half_open_excludes_span_start():
    day = ci.waqt_day_for_gregorian_date(date(2026, 3, 1), ADDIS, ARITH)
    m = day.close
    result = ci.classify_boundary_crossing(m, m + timedelta(hours=1), ADDIS)
    assert result.crosses_maghrib is False, "a span starting exactly at Maghrib lies wholly in the day it opens"


def test_boundary_crossing_agrees_with_scheduling_engine():
    """The whole point of promoting this out of waqt.scheduling: it must
    never disagree with the engine it was extracted from."""
    from waqt.scheduling.context import SchedulingContext
    from waqt.scheduling.engine import SchedulingEngine

    day = ci.waqt_day_for_gregorian_date(date(2026, 3, 1), ADDIS, ARITH)
    m = day.close
    start, end = m - timedelta(hours=1), m + timedelta(hours=1)

    ours = ci.classify_boundary_crossing(start, end, ADDIS)

    ctx = SchedulingContext(location=ADDIS, calendar_provider=ARITH)
    theirs = SchedulingEngine(ctx).classify_span(start, end)

    assert ours.crosses_maghrib == theirs.crosses_maghrib
    assert ours.crosses_civil_midnight == theirs.crosses_civil_midnight

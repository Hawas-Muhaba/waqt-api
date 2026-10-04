"""Sprint 16 - the three reference defects (DIS-001/002/003) and the rules ruled in conformance contract 2.0.0.

Every test names the requirement it enforces (conformance/spec/requirements.json) and the decision record
(conformance/decisions/). These run on waqt-core alone: no HTTP layer, no network.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from waqt_core import solar
from waqt_core.calendar_interop import CivilDateUnresolvable, waqt_day_for_gregorian_date
from waqt_core.core import Location, compute_waqt
from waqt_core.hijri import (
    ArithmeticTabularProvider,
    CalendarOutOfRange,
    InvalidHijriDate,
    checked_to_gregorian,
    tabular_is_leap_year,
    tabular_month_length,
    weekday_name,
)
from waqt_core.timezone_provider import ManualTimezoneProvider, UnknownTimezoneError, validate_timezone_name

TAB = ArithmeticTabularProvider()

PLACES = {
    "kiritimati": (1.8721, -157.4278, "Pacific/Kiritimati"),
    "apia": (-13.8333, -171.7500, "Pacific/Apia"),
    "addis": (9.0192, 38.7525, "Africa/Addis_Ababa"),
    "reykjavik": (64.1466, -21.9426, "Atlantic/Reykjavik"),
    "london": (51.5074, -0.1278, "Europe/London"),
}


def _waqt(place, instant):
    lat, lon, tz = PLACES[place]
    return compute_waqt(instant, Location(lat, lon), TAB, tz_provider=ManualTimezoneProvider(tz)), tz


# ------------------------------------------------------------------ DAY-004 / DR-0001 (DIS-001)
@pytest.mark.parametrize(
    "place,instant,hijri,weekday",
    [
        ("kiritimati", datetime(2026, 9, 19, 22, 0, tzinfo=timezone.utc), "1448-04-07", "al-Ahad"),
        ("apia", datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc), "1447-10-02", "as-Sabt"),
        ("reykjavik", datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc), "1448-01-06", "al-Ithnayn"),
        ("addis", datetime(2026, 9, 19, 15, 42, tzinfo=timezone.utc), "1448-04-07", "al-Ahad"),
    ],
)
def test_label_is_civil_date_of_closing_maghrib_instant(place, instant, hijri, weekday):
    r, tz = _waqt(place, instant)
    civil = r.day_end_maghrib.astimezone(ZoneInfo(tz)).date()
    assert r.label_date == civil
    assert r.hijri_date.iso_like() == hijri == TAB.from_gregorian(civil).iso_like()
    assert r.weekday == weekday == weekday_name(civil)


def test_label_never_depends_on_the_solar_date_key_property():
    # Many (place, instant) pairs: the label is always the civil date of the closing Maghrib.
    base = datetime(2026, 1, 3, 9, 17, tzinfo=timezone.utc)
    for place in PLACES:
        for k in range(0, 360, 23):
            r, tz = _waqt(place, base + timedelta(days=k, hours=k % 7))
            if r.status != "OK":
                continue
            assert r.label_date == r.day_end_maghrib.astimezone(ZoneInfo(tz)).date(), (place, k)
            assert r.weekday == weekday_name(r.label_date)


def test_label_agrees_with_the_civil_date_lookup_both_directions():
    # waqt_day_for_gregorian_date(g) must return a day that compute_waqt labels g (the Sprint 15 inconsistency).
    lat, lon, tz = PLACES["kiritimati"]
    loc, tzp = Location(lat, lon), ManualTimezoneProvider(tz)
    for g in (date(2026, 9, 20), date(2026, 6, 15), date(2026, 12, 31)):
        day = waqt_day_for_gregorian_date(g, loc, TAB, tz_provider=tzp)
        inside = day.open + (day.close - day.open) / 2
        assert compute_waqt(inside, loc, TAB, tz_provider=tzp).label_date == g


# ------------------------------------------------------------------ DAY-009 / DR-0001 (consequences)
def test_civil_date_with_no_closing_maghrib_is_unresolved():
    lat, lon, tz = PLACES["reykjavik"]
    with pytest.raises(CivilDateUnresolvable):
        waqt_day_for_gregorian_date(date(2026, 6, 15), Location(lat, lon), TAB, tz_provider=ManualTimezoneProvider(tz))


def test_civil_date_with_two_closing_maghribs_resolves_to_the_day_containing_local_noon():
    lat, lon, tz = PLACES["reykjavik"]
    day = waqt_day_for_gregorian_date(date(2026, 6, 29), Location(lat, lon), TAB, tz_provider=ManualTimezoneProvider(tz))
    assert abs((day.open - datetime(2026, 6, 29, 0, 0, 16, tzinfo=timezone.utc)).total_seconds()) < 5
    assert abs((day.close - datetime(2026, 6, 29, 23, 59, 4, tzinfo=timezone.utc)).total_seconds()) < 5
    assert day.hijri_date.iso_like() == "1448-01-13" and day.weekday == "al-Ithnayn"


def test_labels_never_decrease_across_consecutive_days_even_where_they_skip_or_repeat():
    lat, lon, tz = PLACES["reykjavik"]
    loc, tzp = Location(lat, lon), ManualTimezoneProvider(tz)
    t, last, deltas = datetime(2026, 6, 10, 12, tzinfo=timezone.utc), None, set()
    while t < datetime(2026, 7, 5, tzinfo=timezone.utc):
        r = compute_waqt(t, loc, TAB, tz_provider=tzp)
        if r.status == "OK":
            if last is not None:
                deltas.add((r.label_date - last).days)
            last = r.label_date
        t += timedelta(days=1)
    assert min(deltas) >= 0
    assert {0, 2} <= deltas  # a repeat (29 June) and a skip (15 June) really occur in this window


# ------------------------------------------------------------------ EVT-007 / DR-0003
def test_next_event_right_after_maghrib_is_tonights_isha():
    r, _ = _waqt("addis", datetime(2026, 9, 19, 15, 42, tzinfo=timezone.utc))
    assert r.next_event.name == "isha"
    assert abs((r.next_event.instant - datetime(2026, 9, 19, 16, 28, 28, tzinfo=timezone.utc)).total_seconds()) < 3
    assert r.next_event_countdown.startswith("00:4")


def test_next_event_is_the_earliest_future_event_through_a_whole_day():
    lat, lon, tz = PLACES["addis"]
    loc, tzp = Location(lat, lon), ManualTimezoneProvider(tz)
    t0, seen = datetime(2026, 9, 19, 10, 0, tzinfo=timezone.utc), []
    for i in range(0, 24 * 60, 10):
        now = t0 + timedelta(minutes=i)
        r = compute_waqt(now, loc, TAB, tz_provider=tzp)
        assert r.next_event.instant > now
        prev = solar.compute_day_events(date(2026, 9, 19) if now < r.day_end_maghrib else date(2026, 9, 20), lat, lon)
        future = [e.instant for e in r.events if e.instant and e.instant > now]
        if prev.isha and prev.isha > now:
            future.append(prev.isha)
        assert r.next_event.instant == min(future)
        if not seen or seen[-1] != r.next_event.name:
            seen.append(r.next_event.name)
    assert seen[:3] == ["asr", "maghrib", "isha"] and set(seen) == {"fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha"}


# ------------------------------------------------------------------ CAL-002 / DR-0005
def test_tabular_leap_positions_are_the_civil_pattern():
    assert [y for y in range(1, 31) if tabular_is_leap_year(y)] == [2, 5, 7, 10, 13, 16, 18, 21, 24, 26, 29]
    assert all(tabular_is_leap_year(y) == tabular_is_leap_year(y + 30) for y in range(1, 200))


def test_written_leap_rule_agrees_with_the_forward_conversion():
    for y in range(1, 600):
        for m in range(1, 13):
            last = TAB.to_gregorian(y, m, tabular_month_length(y, m))
            h, nxt = TAB.from_gregorian(last), TAB.from_gregorian(last + timedelta(days=1))
            assert (h.year, h.month, h.day) == (y, m, tabular_month_length(y, m)) and nxt.day == 1, (y, m)


def test_tabular_epoch_is_friday_0622_07_19():
    g = TAB.to_gregorian(1, 1, 1)
    assert g == date(622, 7, 19) and g.strftime("%A") == "Friday"


# ------------------------------------------------------------------ CAL-004 / DR-0006 (DIS-002)
@pytest.mark.parametrize(
    "y,m,d",
    [(1448, 2, 30), (1448, 12, 30), (0, 1, 1), (-1, 1, 1), (1448, 13, 1), (1448, 0, 1), (1448, 1, 31), (1448, 1, 0)],
)
def test_non_existent_hijri_date_is_rejected_not_normalised(y, m, d):
    with pytest.raises(InvalidHijriDate) as e:
        TAB.to_gregorian(y, m, d)
    assert e.value.code == "INVALID_HIJRI_DATE" and isinstance(e.value, ValueError)


def test_existing_edge_days_still_convert():
    assert TAB.to_gregorian(1447, 12, 30) == date(2026, 6, 16)  # 1447 is a leap year
    assert TAB.to_gregorian(1, 1, 1) == date(622, 7, 19)
    assert TAB.to_gregorian(1448, 1, 30) == date(2026, 7, 16)


def test_every_real_day_round_trips_and_the_day_after_the_last_is_rejected():
    d = date(1900, 1, 1)
    while d <= date(2100, 12, 31):
        h = TAB.from_gregorian(d)
        assert TAB.to_gregorian(h.year, h.month, h.day) == d
        d += timedelta(days=17)
    with pytest.raises(InvalidHijriDate):
        TAB.to_gregorian(1448, 2, tabular_month_length(1448, 2) + 1)


class _NormalisingProvider:
    """A provider that, like the Sprint 15 tabular one, turns day 30 of a 29-day month into day 1 of the next."""
    name = "normalising"

    def to_gregorian(self, y, m, d):
        return TAB.to_gregorian(y, m, 1) + timedelta(days=d - 1)

    def from_gregorian(self, g):
        return TAB.from_gregorian(g)


def test_checked_to_gregorian_catches_any_normalising_provider():
    p = _NormalisingProvider()
    assert checked_to_gregorian(p, 1448, 2, 29) == TAB.to_gregorian(1448, 2, 29)
    with pytest.raises(InvalidHijriDate):
        checked_to_gregorian(p, 1448, 2, 30)
    with pytest.raises(InvalidHijriDate):
        checked_to_gregorian(p, 0, 1, 1)


def test_institutional_month_days_still_finds_29_and_30_day_months():
    from waqt_core.institutional.rules import month_days

    assert len(month_days(TAB, 1448, 2)) == 29 and len(month_days(TAB, 1448, 1)) == 30
    assert len(month_days(TAB, 1447, 12)) == 30 and len(month_days(TAB, 1448, 12)) == 29


# ------------------------------------------------------------------ ERR-002 / DR-0006 (DIS-003)
@pytest.mark.parametrize("bad", ["Mars/Base", "../etc/passwd", "", "   ", "Africa/Nowhere", "/abs/path", None, 7])
def test_unknown_timezone_is_a_structured_client_error(bad):
    with pytest.raises(UnknownTimezoneError) as e:
        ManualTimezoneProvider(bad)
    assert e.value.code == "UNKNOWN_TIMEZONE" and isinstance(e.value, ValueError) and e.value.timezone == bad


@pytest.mark.parametrize("good", ["UTC", "Africa/Addis_Ababa", "Pacific/Kiritimati", "Asia/Kolkata", "Etc/GMT+5"])
def test_real_timezones_are_accepted(good):
    assert validate_timezone_name(good) == good
    assert ManualTimezoneProvider(good).tz_name == good


# ------------------------------------------------------------------ CAL-011 / DR-0007
def test_umm_al_qura_refuses_outside_its_supported_range():
    pytest.importorskip("ephem")
    from waqt_core.calendar_providers.umm_al_qura import UmmAlQuraProvider

    p = UmmAlQuraProvider()
    for d in (date(1650, 1, 1), date(1699, 12, 31), date(2301, 1, 1), date(2500, 1, 1)):
        with pytest.raises(CalendarOutOfRange) as e:
            p.from_gregorian(d)
        assert e.value.code == "OUT_OF_RANGE"
    for y in (0, 500, 1099, 1731):
        with pytest.raises(CalendarOutOfRange):
            p.to_gregorian(y, 1, 1)
    assert p.from_gregorian(date(1700, 1, 1)).year == 1111
    assert p.from_gregorian(date(2300, 12, 31)).year == 1730

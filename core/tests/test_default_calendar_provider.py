"""waqt-core's default Hijri provider is `umm-al-qura` (waqt-core 0.5.0), defined once and identical to the HTTP API default.

A calendar failure (an instant outside umm-al-qura's 1700..2300) must never fail a core call or move a Waqt instant.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from waqt_core.calendar_interop import classify_boundary_crossing, represent_instant, waqt_day_for_gregorian_date
from waqt_core.calendar_providers import ArithmeticTabularProvider, UmmAlQuraProvider
from waqt_core.calendar_providers import DEFAULT_CALENDAR_PROVIDER, default_calendar_provider
from waqt_core.core import Location
from waqt_core.scheduling.context import SchedulingContext

ADDIS = Location(lat=9.0192, lon=38.7525)
T = datetime(2026, 9, 19, 15, 42, tzinfo=timezone.utc)
UQ, AT = UmmAlQuraProvider(), ArithmeticTabularProvider()


def strip_hijri(o):
    if isinstance(o, dict):
        return {k: strip_hijri(v) for k, v in o.items() if k not in ("hijri", "calendar_error")}
    if isinstance(o, list):
        return [strip_hijri(x) for x in o]
    return o


def test_the_default_is_umm_al_qura_and_is_one_cached_instance():
    assert DEFAULT_CALENDAR_PROVIDER == "umm-al-qura"
    p = default_calendar_provider()
    assert p.name == DEFAULT_CALENDAR_PROVIDER and p is default_calendar_provider()


def test_represent_instant_without_a_provider_equals_explicit_umm_al_qura():
    d = represent_instant(T, ADDIS).to_dict()
    assert d == represent_instant(T, ADDIS, calendar_provider=UQ).to_dict()
    assert d["waqt"]["day"]["hijri"]["provider"]["name"] == "umm-al-qura" if "day" in (d["waqt"] or {}) else d["waqt"]["hijri"]["provider"]["name"] == "umm-al-qura"


def test_the_default_changes_only_the_hijri_label_never_a_waqt_instant():
    a, b = represent_instant(T, ADDIS).to_dict(), represent_instant(T, ADDIS, calendar_provider=AT).to_dict()
    assert a != b and strip_hijri(a) == strip_hijri(b)


def test_waqt_day_for_gregorian_date_and_boundary_crossing_use_the_default():
    day = waqt_day_for_gregorian_date(date(2026, 9, 19), ADDIS)
    assert day.hijri_date.provider == "umm-al-qura" and day.hijri_date == waqt_day_for_gregorian_date(date(2026, 9, 19), ADDIS, calendar_provider=UQ).hijri_date
    bc = classify_boundary_crossing(T, T + timedelta(hours=12), ADDIS)
    assert bc.to_dict() == classify_boundary_crossing(T, T + timedelta(hours=12), ADDIS, calendar_provider=UQ).to_dict()


def test_scheduling_context_without_a_provider_uses_the_default():
    assert SchedulingContext(ADDIS).calendar_provider.name == "umm-al-qura"
    assert SchedulingContext(ADDIS, calendar_provider=AT).calendar_provider.name == "arithmetic-tabular"


@pytest.mark.parametrize("year", [1650, 2400])
def test_out_of_range_instant_with_the_default_keeps_waqt_time_and_explains_the_empty_label(year):
    """Regression: this used to raise AttributeError ('NoneType' has no attribute 'iso_like') -- a 500 from /v1/calendar/convert."""
    t = datetime(year, 9, 19, 15, 42, tzinfo=timezone.utc)
    d = represent_instant(t, ADDIS).to_dict()
    assert d["waqt_status"] == "OK" and d["waqt"]["hijri"] is None
    assert "CalendarOutOfRange" in d["waqt"]["calendar_error"] and "1700-01-01..2300-12-31" in d["waqt"]["calendar_error"]
    ref = represent_instant(t, ADDIS, calendar_provider=AT).to_dict()      # arithmetic-tabular covers every year
    assert ref["waqt"]["hijri"] is not None and "calendar_error" not in ref["waqt"]
    assert {k: v for k, v in d["waqt"].items() if k not in ("hijri", "calendar_error")} == {k: v for k, v in ref["waqt"].items() if k != "hijri"}

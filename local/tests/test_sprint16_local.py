"""Sprint 16 - waqt_local mirrors API 1.6.0: same codes, same corrected behaviour."""
from __future__ import annotations

import pytest

import waqt_local

KIRI = dict(lat=1.8721, lon=-157.4278, timezone_override="Pacific/Kiritimati")


def test_unknown_timezone_raises_the_local_error_with_the_api_code():
    with pytest.raises(waqt_local.UnknownTimezoneError) as e:
        waqt_local.waqt(lat=0, lon=0, instant="2026-09-19T15:42:00Z", timezone_override="Mars/Base")
    assert e.value.code == "UNKNOWN_TIMEZONE"
    assert e.value.details["parameter"] == "timezone_override" and e.value.details["received"] == "Mars/Base"


@pytest.mark.parametrize("y,m,d", [(1448, 2, 30), (0, 1, 1), (1448, 12, 30)])
def test_non_existent_hijri_date_raises_invalid_hijri_date(y, m, d):
    # Month lengths are provider-specific: these dates do not exist in the arithmetic-tabular calendar. The provider is
    # named explicitly because the DEFAULT is umm-al-qura since API 1.7.0 (where 1448-02-30 and 1448-12-30 do exist).
    with pytest.raises(waqt_local.InvalidHijriDateError) as e:
        waqt_local.convert(direction="to-gregorian", year=y, month=m, day=d, calendar_provider="arithmetic-tabular")
    assert e.value.code == "INVALID_HIJRI_DATE"


@pytest.mark.parametrize("y,m,d", [(0, 1, 1), (1448, 1, 31)])
def test_non_existent_hijri_date_raises_invalid_hijri_date_under_the_default_provider(y, m, d):
    with pytest.raises(waqt_local.InvalidHijriDateError) as e:
        waqt_local.convert(direction="to-gregorian", year=y, month=m, day=d)   # provider omitted -> umm-al-qura
    assert e.value.code == "INVALID_HIJRI_DATE"


def test_local_label_and_next_event_match_the_corrected_behaviour():
    d = waqt_local.waqt(instant="2026-09-19T22:00:00Z", calendar_provider="arithmetic-tabular", **KIRI)   # explicit: the pre-1.7.0 default
    assert d["hijri"]["date"] == "1448-04-07" and d["weekday"] == "al-Ahad"
    u = waqt_local.waqt(instant="2026-09-19T22:00:00Z", **KIRI)                                           # omitted: umm-al-qura (API 1.7.0)
    assert u["hijri"]["provider"]["name"] == "umm-al-qura" and u == waqt_local.waqt(instant="2026-09-19T22:00:00Z", calendar_provider="umm-al-qura", **KIRI)
    assert u["weekday"] == d["weekday"] and u["day"] == d["day"]   # the provider moves the Hijri label only
    a = waqt_local.waqt(lat=9.0192, lon=38.7525, instant="2026-09-19T15:42:00Z")
    assert a["next_event"]["name"] == "isha"

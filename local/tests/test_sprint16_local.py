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
    with pytest.raises(waqt_local.InvalidHijriDateError) as e:
        waqt_local.convert(direction="to-gregorian", year=y, month=m, day=d)
    assert e.value.code == "INVALID_HIJRI_DATE"


def test_local_label_and_next_event_match_the_corrected_behaviour():
    d = waqt_local.waqt(instant="2026-09-19T22:00:00Z", **KIRI)
    assert d["hijri"]["date"] == "1448-04-07" and d["weekday"] == "al-Ahad"
    a = waqt_local.waqt(lat=9.0192, lon=38.7525, instant="2026-09-19T15:42:00Z")
    assert a["next_event"]["name"] == "isha"

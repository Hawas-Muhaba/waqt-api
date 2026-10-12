"""ERR-004 and CAL-013 through the offline library (the same rules and codes as the HTTP API)."""
import pytest

import waqt_local
from waqt_local.errors import WaqtLocalError

PLACE = dict(lat=9.0192, lon=38.7525, timezone_override="Africa/Addis_Ababa")


@pytest.mark.parametrize("kw", [{"fajr_angle": 95}, {"fajr_angle": 0}, {"isha_angle": -1}, {"asr_ratio": 0}, {"fajr_angle": float("nan")}, {"asr_ratio": float("inf")}])
def test_invalid_profile_is_a_validation_error(kw):
    with pytest.raises(WaqtLocalError) as e:
        waqt_local.waqt(instant="2026-09-19T15:42:00Z", **PLACE, **kw)
    assert e.value.code == "VALIDATION_ERROR" and e.value.details["parameter"]


def test_boundary_profile_is_accepted():
    assert waqt_local.waqt(instant="2026-09-19T15:42:00Z", **PLACE, fajr_angle=90, isha_angle=90, asr_ratio=0.0001)


def test_out_of_range_instant_returns_the_waqt_day_with_a_calendar_error():
    d = waqt_local.waqt(instant="1699-12-31T12:00:00Z", **PLACE)
    assert d["hijri"] is None and d["calendar_error"] and d["day"]["maghrib_open"]

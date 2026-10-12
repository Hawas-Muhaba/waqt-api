"""ERR-004 / DR-0011: astronomy-profile parameters are validated at construction -- never clamped, never coerced."""
import math

import pytest

from waqt_core.core import AstronomyProfile
from waqt_core.profile_validation import InvalidProfileError, validate_profile_value

NAN, INF = float("nan"), float("inf")


@pytest.mark.parametrize("name,value", [
    ("fajr_angle_deg", 90), ("fajr_angle_deg", 90.0), ("fajr_angle_deg", 1e-9), ("isha_angle_deg", 90), ("isha_angle_deg", 0.0001),
    ("asr_shadow_ratio", 1e-9), ("asr_shadow_ratio", 1), ("asr_shadow_ratio", 2), ("asr_shadow_ratio", 1000.5)])
def test_valid_values_and_inclusive_boundaries_are_accepted_unchanged(name, value):
    assert validate_profile_value(name, value) == float(value)


@pytest.mark.parametrize("name", ["fajr_angle_deg", "isha_angle_deg"])
@pytest.mark.parametrize("value", [0, 0.0, -0.0, -5, 90.0000001, 95, 180, NAN, INF, -INF, "18", "abc", "", None, True, False, [], {}, (18,)])
def test_invalid_angles_are_rejected(name, value):
    with pytest.raises(InvalidProfileError) as e:
        validate_profile_value(name, value)
    assert e.value.code == "VALIDATION_ERROR" and e.value.parameter == name and isinstance(e.value, ValueError)


@pytest.mark.parametrize("value", [0, 0.0, -1, -1e-9, NAN, INF, -INF, "1", "abc", None, True, False])
def test_invalid_asr_ratio_is_rejected(value):
    with pytest.raises(InvalidProfileError):
        validate_profile_value("asr_shadow_ratio", value)


def test_astronomy_profile_validates_on_construction_and_keeps_defaults():
    p = AstronomyProfile()
    assert (p.fajr_angle_deg, p.isha_angle_deg, p.asr_shadow_ratio) == (18.0, 17.0, 1.0)
    for kw in ({"fajr_angle_deg": 95}, {"isha_angle_deg": 0}, {"asr_shadow_ratio": 0}, {"fajr_angle_deg": NAN}, {"isha_angle_deg": "x"}):
        with pytest.raises(InvalidProfileError):
            AstronomyProfile(**kw)
    assert AstronomyProfile(fajr_angle_deg=90, isha_angle_deg=90, asr_shadow_ratio=0.0001).fajr_angle_deg == 90


def test_received_is_always_json_encodable():
    import json
    for v in (NAN, INF, -INF, "abc", None, True, 95, [1], {"a": 1}):
        with pytest.raises(InvalidProfileError) as e:
            validate_profile_value("fajr_angle_deg", v)
        json.dumps(e.value.received_json, allow_nan=False)
    assert not math.isnan(95)

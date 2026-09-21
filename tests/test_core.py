"""
Tests backing the claims made in SCOPE.md. Run with:
    python3 -m pytest tests/ -v
"""

from datetime import date, datetime, timezone

import pytest
from astral import LocationInfo
from astral.sun import sun

from waqt import solar
from waqt.core import AstronomyProfile, compute_waqt
from waqt.hijri import ArithmeticTabularProvider

ADDIS = (9.0192, 38.7525)
MAKKAH = (21.4225, 39.8262)
LONDON = (51.5074, -0.1278)
TROMSO = (69.6, 18.96)

# Two independent low-precision solar algorithms (ours vs. astral's) are
# expected to agree closely near the equator, where the sun's altitude
# changes quickly around rise/set (a small angle error -> a small time
# error), and more loosely at higher latitude, where the sun's path is
# shallower and the same angle error amplifies into a larger time error.
# This is a real geometric effect, not a bug — see SCOPE.md. Tolerances
# below reflect that rather than hiding it behind one blanket number.


def _agrees(a, b, tol_seconds):
    return abs((a - b).total_seconds()) <= tol_seconds


@pytest.mark.parametrize(
    "name,lat,lon,d,tol_s",
    [
        ("Addis Ababa, equinox-ish", *ADDIS, date(2026, 9, 19), 20),
        ("Makkah, equinox-ish", *MAKKAH, date(2026, 9, 19), 20),
        ("London, autumn", *LONDON, date(2026, 9, 19), 60),
        ("London, midsummer", *LONDON, date(2026, 6, 21), 60),
    ],
)
def test_sunrise_sunset_agree_with_astral(name, lat, lon, d, tol_s):
    loc = LocationInfo(name, "", "UTC", lat, lon)
    ref = sun(loc.observer, date=d)

    ours_sunrise = solar.sunrise(d, lat, lon)
    ours_sunset = solar.sunset(d, lat, lon)

    assert _agrees(ours_sunrise, ref["sunrise"], tol_s), (ours_sunrise, ref["sunrise"])
    assert _agrees(ours_sunset, ref["sunset"], tol_s), (ours_sunset, ref["sunset"])


def test_transit_always_exists_even_at_high_latitude():
    assert solar.transit(date(2026, 6, 21), *TROMSO) is not None


def test_polar_day_makes_sunset_undefined_not_guessed():
    assert solar.sunset(date(2026, 6, 21), *TROMSO) is None
    assert solar.sunrise(date(2026, 6, 21), *TROMSO) is None


def test_fajr_undefined_at_high_latitude_midsummer():
    # 18 deg below horizon never reached at 51.5N around midsummer.
    assert solar.fajr(date(2026, 6, 21), *LONDON, angle_deg=18.0) is None


# ---- Core Time Model: day boundary + hour (Sec 2-3) ----


def test_maghrib_is_always_zero():
    t = datetime(2026, 9, 19, 15, 42, tzinfo=timezone.utc)  # right after Addis Maghrib
    r = compute_waqt(t, *ADDIS, ArithmeticTabularProvider())
    assert r.status == "OK"
    # instant chosen a few minutes after Maghrib -> reading should start with 00:
    assert r.hour_reading.startswith("00:")


def test_day_length_is_not_exactly_24h():
    t = datetime(2026, 9, 19, 15, 42, tzinfo=timezone.utc)
    r = compute_waqt(t, *ADDIS, ArithmeticTabularProvider())
    assert r.day_length_si_seconds != pytest.approx(86400, abs=0.001)
    assert abs(r.day_length_si_seconds - 86400) < 300  # sanity: within 5 min


def test_polar_undefined_status_not_a_crash():
    t = datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc)
    r = compute_waqt(t, *TROMSO, ArithmeticTabularProvider())
    assert r.status == "UNDEFINED"
    assert r.hour_reading is None
    assert r.hijri_date is None


# ---- Core Time Model: events as positions, never boundaries (Sec 4) ----


def test_asr_ratio_changes_only_the_asr_marker():
    t = datetime(2026, 9, 19, 15, 42, tzinfo=timezone.utc)
    provider = ArithmeticTabularProvider()

    r_shafii = compute_waqt(
        t, *ADDIS, provider, AstronomyProfile(asr_shadow_ratio=1.0)
    )
    r_hanafi = compute_waqt(
        t, *ADDIS, provider, AstronomyProfile(asr_shadow_ratio=2.0)
    )

    # The grid itself is untouched:
    assert r_shafii.hour_reading == r_hanafi.hour_reading
    assert r_shafii.day_start_maghrib == r_hanafi.day_start_maghrib
    assert r_shafii.day_end_maghrib == r_hanafi.day_end_maghrib
    for name in ("fajr", "sunrise", "dhuhr", "maghrib", "isha"):
        a = next(e for e in r_shafii.events if e.name == name)
        b = next(e for e in r_hanafi.events if e.name == name)
        assert a.instant == b.instant

    # Only the marker itself moves, and it moves later (Hanafi Asr is later):
    asr_shafii = next(e for e in r_shafii.events if e.name == "asr")
    asr_hanafi = next(e for e in r_hanafi.events if e.name == "asr")
    assert asr_hanafi.instant > asr_shafii.instant


def test_weekday_shifts_at_maghrib_not_gregorian_midnight():
    provider = ArithmeticTabularProvider()
    # Just before Addis Maghrib on a given evening vs just after:
    d = date(2026, 9, 19)
    before = datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc) + \
        (solar.sunset(d, *ADDIS) - datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc)) - \
        __import__("datetime").timedelta(minutes=5)
    after = solar.sunset(d, *ADDIS) + __import__("datetime").timedelta(minutes=5)

    r_before = compute_waqt(before, *ADDIS, provider)
    r_after = compute_waqt(after, *ADDIS, provider)

    assert r_before.weekday != r_after.weekday
    assert r_before.hijri_date.iso_like() != r_after.hijri_date.iso_like()

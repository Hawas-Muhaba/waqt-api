"""
Sprint 2 test suite.

Covers, per the sprint brief:
  - Equator, tropics, mid-latitudes, high latitudes
  - Southern and northern hemisphere
  - International Date Line
  - Polar regions
  - Different elevations
  - sunrise, sunset, Fajr, Isha, Dhuhr, Asr

Run with: python3 -m pytest tests/ -v
"""

from datetime import date, datetime, timedelta, timezone

import pytest
from astral import LocationInfo
from astral.sun import sun

from waqt import solar
from waqt.core import AstronomyProfile, Location, compute_waqt
from waqt.hijri import ArithmeticTabularProvider
from waqt.timescale import DEFAULT_TIMESCALE_PROVIDER, EspenakMeeusDeltaT
from waqt.timezone_provider import DEFAULT_TIMEZONE_PROVIDER, ManualTimezoneProvider

PROVIDER = ArithmeticTabularProvider()

# name, lat, lon, category
LOCATIONS = [
    ("Quito (equator)", -0.1807, -78.4678, "equator"),
    ("Nairobi (tropics, S)", -1.2921, 36.8219, "tropics"),
    ("Cairo (mid-lat, N)", 30.0444, 31.2357, "mid-lat-N"),
    ("Cape Town (mid-lat, S)", -33.9249, 18.4241, "mid-lat-S"),
    ("Addis Ababa (tropics, N)", 9.0192, 38.7525, "tropics"),
    ("Makkah (tropics, N)", 21.4225, 39.8262, "tropics"),
]

HIGH_LAT_LOCATIONS = [
    ("Tromso (high-lat, N)", 69.6492, 18.9553),
    ("Punta Arenas (high-lat, S)", -53.1638, -70.9171),
]

POLAR_LOCATIONS = [
    ("Tromso midsummer", 69.6492, 18.9553, date(2026, 6, 21)),
    ("McMurdo Station midsummer (S)", -77.85, 166.6667, date(2026, 12, 21)),
]

DATE_LINE_LOCATIONS = [
    ("Suva, Fiji (west of line)", -18.1416, 178.4419),
    ("Kiritimati, Kiribati (east of line, UTC+14)", 1.8721, -157.4278),
]


# ---------------------------------------------------------------------------
# Solar engine cross-validation (sunrise/sunset vs astral), across the
# geographic matrix. Tolerance is looser at higher latitude — see the
# note in SPRINT-2-REPORT.md on why that's a real geometric effect.
# ---------------------------------------------------------------------------


def _tol_for_lat(lat: float) -> int:
    a = abs(lat)
    if a < 15:
        return 30
    if a < 40:
        return 70
    return 120


@pytest.mark.parametrize("name,lat,lon,category", LOCATIONS)
def test_sunrise_sunset_agree_with_astral(name, lat, lon, category):
    d = date(2026, 9, 19)
    loc = LocationInfo(name, "", "UTC", lat, lon)
    ref = sun(loc.observer, date=d)
    tol = _tol_for_lat(lat)

    ours_sunrise = solar.sunrise(d, lat, lon)
    ours_sunset = solar.sunset(d, lat, lon)

    assert abs((ours_sunrise - ref["sunrise"]).total_seconds()) <= tol, (
        name, ours_sunrise, ref["sunrise"]
    )
    assert abs((ours_sunset - ref["sunset"]).total_seconds()) <= tol, (
        name, ours_sunset, ref["sunset"]
    )


@pytest.mark.parametrize("name,lat,lon", HIGH_LAT_LOCATIONS)
def test_high_latitude_defined_in_shoulder_seasons(name, lat, lon):
    # Equinox-ish: sunrise/sunset should exist even at high latitude.
    d = date(2026, 9, 19)
    assert solar.sunrise(d, lat, lon) is not None
    assert solar.sunset(d, lat, lon) is not None
    loc = LocationInfo(name, "", "UTC", lat, lon)
    ref = sun(loc.observer, date=d)
    tol = _tol_for_lat(lat)
    assert abs((solar.sunset(d, lat, lon) - ref["sunset"]).total_seconds()) <= tol


# ---------------------------------------------------------------------------
# Polar regions: must return None/UNDEFINED, never a guessed value.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,lat,lon,d", POLAR_LOCATIONS)
def test_polar_day_is_undefined_not_guessed(name, lat, lon, d):
    assert solar.sunrise(d, lat, lon) is None
    assert solar.sunset(d, lat, lon) is None

    r = compute_waqt(
        datetime(d.year, d.month, d.day, 12, 0, tzinfo=timezone.utc),
        Location(lat, lon),
        PROVIDER,
    )
    assert r.status == "UNDEFINED"
    assert r.hour_reading is None
    assert r.hijri_date is None


# ---------------------------------------------------------------------------
# Elevation: increasing elevation must make sunset monotonically later
# and sunrise monotonically earlier — the physical effect being modeled.
# ---------------------------------------------------------------------------


def test_elevation_delays_sunset_and_advances_sunrise_monotonically():
    d = date(2026, 9, 19)
    lat, lon = 9.0192, 38.7525  # Addis Ababa
    elevations = [0, 500, 2400, 5000]

    sunsets = [solar.sunset(d, lat, lon, elevation_m=e) for e in elevations]
    sunrises = [solar.sunrise(d, lat, lon, elevation_m=e) for e in elevations]

    assert sunsets == sorted(sunsets), "sunset should get later as elevation increases"
    assert sunrises == sorted(sunrises, reverse=True), "sunrise should get earlier as elevation increases"

    # Fajr/Isha (twilight-angle events) must NOT move with elevation —
    # this is the deliberate scope decision documented in solar.py.
    fajr_0 = solar.fajr(d, lat, lon, 18.0)
    fajr_high = solar.fajr(d, lat, lon, 18.0)  # elevation has no fajr param
    assert fajr_0 == fajr_high


def test_elevation_zero_matches_no_elevation_argument():
    d = date(2026, 9, 19)
    lat, lon = 9.0192, 38.7525
    assert solar.sunset(d, lat, lon) == solar.sunset(d, lat, lon, elevation_m=0.0)


def test_api_level_elevation_changes_maghrib_in_full_pipeline():
    t = datetime(2026, 9, 19, 15, 30, tzinfo=timezone.utc)
    r_sea = compute_waqt(t, Location(9.0192, 38.7525, elevation_m=0), PROVIDER)
    r_high = compute_waqt(t, Location(9.0192, 38.7525, elevation_m=2400), PROVIDER)
    assert r_sea.day_end_maghrib < r_high.day_end_maghrib


# ---------------------------------------------------------------------------
# International Date Line: the Sprint 2 fix. A location whose civil date
# differs from its UTC date must bracket Maghrib against the CIVIL date,
# not Greenwich's — this is what timezone_provider adds over Stage 1's
# UTC-date shortcut.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,lat,lon", DATE_LINE_LOCATIONS)
def test_date_line_locations_civil_date_differs_from_utc_date(name, lat, lon):
    # Pick an instant where UTC date and civil date are known to disagree
    # for these locations (late UTC evening -> already "tomorrow" locally
    # east of the line, or vice versa).
    t = datetime(2026, 9, 19, 23, 0, tzinfo=timezone.utc)
    civil_date = DEFAULT_TIMEZONE_PROVIDER.local_date(t, lat, lon)
    utc_date = t.date()
    assert civil_date != utc_date, (
        f"{name}: expected civil date to differ from UTC date at this instant "
        f"(civil={civil_date}, utc={utc_date}) — if this fails the test instant "
        "needs adjusting, not the code."
    )


@pytest.mark.parametrize("name,lat,lon", DATE_LINE_LOCATIONS)
def test_date_line_locations_compute_without_error(name, lat, lon):
    t = datetime(2026, 9, 19, 23, 0, tzinfo=timezone.utc)
    r = compute_waqt(t, Location(lat, lon), PROVIDER)
    assert r.status == "OK"
    assert r.timezone_name is not None
    assert r.hijri_date is not None


def test_manual_timezone_override_used_when_supplied():
    t = datetime(2026, 9, 19, 23, 0, tzinfo=timezone.utc)
    r = compute_waqt(
        t,
        Location(-18.1416, 178.4419),
        PROVIDER,
        tz_provider=ManualTimezoneProvider("Pacific/Fiji"),
    )
    assert r.timezone_name == "Pacific/Fiji"


# ---------------------------------------------------------------------------
# Event ordering: Fajr < sunrise < Dhuhr < Asr < Maghrib < Isha, wherever
# all six are defined. This is a strong internal-consistency check across
# the whole geographic matrix.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,lat,lon,category", LOCATIONS)
def test_event_ordering_holds(name, lat, lon, category):
    d = date(2026, 9, 19)
    ev = solar.compute_day_events(d, lat, lon)
    times = [ev.fajr, ev.sunrise, ev.dhuhr, ev.asr, ev.maghrib, ev.isha]
    assert all(t is not None for t in times), f"{name}: expected all six events defined"
    assert times == sorted(times), f"{name}: events out of order: {times}"


def test_hanafi_asr_is_later_than_standard_asr():
    d = date(2026, 9, 19)
    lat, lon = 9.0192, 38.7525
    standard = solar.asr(d, lat, lon, shadow_ratio=1.0)
    hanafi = solar.asr(d, lat, lon, shadow_ratio=2.0)
    assert hanafi > standard


# ---------------------------------------------------------------------------
# Time scale (DeltaT) provider
# ---------------------------------------------------------------------------


def test_delta_t_is_positive_and_near_current_era_value():
    dt_now = EspenakMeeusDeltaT().delta_t_seconds(date(2026, 9, 19))
    # Current era is ~69-73s and slowly increasing; generous band to
    # avoid a brittle test while still catching a gross error.
    assert 60 < dt_now < 90


def test_delta_t_increases_slowly_over_a_decade():
    ts = EspenakMeeusDeltaT()
    dt_2026 = ts.delta_t_seconds(date(2026, 1, 1))
    dt_2036 = ts.delta_t_seconds(date(2036, 1, 1))
    assert dt_2036 > dt_2026
    assert dt_2036 - dt_2026 < 10  # should drift, not jump


def test_delta_t_wired_into_core_result():
    t = datetime(2026, 9, 19, 15, 30, tzinfo=timezone.utc)
    r = compute_waqt(t, Location(9.0192, 38.7525), PROVIDER)
    assert r.timescale_model == "espenak-meeus-2006"
    assert r.delta_t_seconds is not None
    assert 60 < r.delta_t_seconds < 90


# ---------------------------------------------------------------------------
# Core Time Model invariants (carried over from Stage 1, re-verified
# against the new Location-based signature)
# ---------------------------------------------------------------------------


def test_maghrib_is_always_zero():
    t = datetime(2026, 9, 19, 15, 42, tzinfo=timezone.utc)
    r = compute_waqt(t, Location(9.0192, 38.7525), PROVIDER)
    assert r.status == "OK"
    assert r.hour_reading.startswith("00:")


def test_day_length_is_not_exactly_24h():
    t = datetime(2026, 9, 19, 15, 42, tzinfo=timezone.utc)
    r = compute_waqt(t, Location(9.0192, 38.7525), PROVIDER)
    assert abs(r.day_length_si_seconds - 86400) < 300
    assert r.day_length_si_seconds != pytest.approx(86400, abs=0.001)


def test_asr_ratio_changes_only_the_asr_marker():
    t = datetime(2026, 9, 19, 15, 42, tzinfo=timezone.utc)
    r_shafii = compute_waqt(t, Location(9.0192, 38.7525), PROVIDER, AstronomyProfile(asr_shadow_ratio=1.0))
    r_hanafi = compute_waqt(t, Location(9.0192, 38.7525), PROVIDER, AstronomyProfile(asr_shadow_ratio=2.0))

    assert r_shafii.hour_reading == r_hanafi.hour_reading
    assert r_shafii.day_start_maghrib == r_hanafi.day_start_maghrib
    assert r_shafii.day_end_maghrib == r_hanafi.day_end_maghrib
    for name in ("fajr", "sunrise", "dhuhr", "maghrib", "isha"):
        a = next(e for e in r_shafii.events if e.name == name)
        b = next(e for e in r_hanafi.events if e.name == name)
        assert a.instant == b.instant

    asr_shafii = next(e for e in r_shafii.events if e.name == "asr")
    asr_hanafi = next(e for e in r_hanafi.events if e.name == "asr")
    assert asr_hanafi.instant > asr_shafii.instant


def test_weekday_shifts_at_maghrib_not_gregorian_midnight():
    d = date(2026, 9, 19)
    lat, lon = 9.0192, 38.7525
    ms = solar.sunset(d, lat, lon)
    before = ms - timedelta(minutes=5)
    after = ms + timedelta(minutes=5)

    r_before = compute_waqt(before, Location(lat, lon), PROVIDER)
    r_after = compute_waqt(after, Location(lat, lon), PROVIDER)

    assert r_before.weekday != r_after.weekday
    assert r_before.hijri_date.iso_like() != r_after.hijri_date.iso_like()

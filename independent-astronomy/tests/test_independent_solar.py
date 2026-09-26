"""
Standalone sanity tests for independent_solar -- these exercise the
package entirely on its own terms (no import of `waqt` at all), checking
it against well-known astronomical facts rather than against the Waqt
reference implementation. The cross-check against `waqt/solar.py` lives
in test_comparison_with_waqt.py.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from independent_solar import compute_day_events, transit
from independent_solar.deltat import delta_t_seconds
from independent_solar.julian import julian_day
from independent_solar.sun import apparent_position


def _declination_at_transit(d: date, lat: float, lon: float) -> float:
    t = transit(d, lat, lon)
    jd_tt = julian_day(t) + delta_t_seconds(d) / 86400.0
    return apparent_position(jd_tt).declination_deg


def test_march_equinox_declination_near_zero():
    assert abs(_declination_at_transit(date(2026, 3, 20), 0.0, 0.0)) < 0.5


def test_september_equinox_declination_near_zero():
    assert abs(_declination_at_transit(date(2026, 9, 23), 0.0, 0.0)) < 0.5


def test_june_solstice_declination_near_max_north():
    dec = _declination_at_transit(date(2026, 6, 21), 0.0, 0.0)
    assert 23.2 < dec < 23.6


def test_december_solstice_declination_near_max_south():
    dec = _declination_at_transit(date(2026, 12, 21), 0.0, 0.0)
    assert -23.6 < dec < -23.2


def test_transit_always_defined():
    # Solar transit has no altitude threshold -- unlike the other five
    # events, it is defined everywhere, every day, poles included.
    for lat in (-89.0, -23.5, 0.0, 23.5, 66.6, 89.0):
        t = transit(date(2026, 6, 21), lat, 0.0)
        assert t is not None


def test_event_ordering_addis_ababa():
    ev = compute_day_events(date(2026, 9, 19), 9.0192, 38.7525)
    order = [ev.fajr, ev.sunrise, ev.dhuhr, ev.asr, ev.maghrib, ev.isha]
    assert all(x is not None for x in order)
    for a, b in zip(order, order[1:]):
        assert a < b


def test_event_ordering_cape_town_southern_hemisphere():
    ev = compute_day_events(date(2026, 6, 21), -33.9249, 18.4241)
    order = [ev.fajr, ev.sunrise, ev.dhuhr, ev.asr, ev.maghrib, ev.isha]
    assert all(x is not None for x in order)
    for a, b in zip(order, order[1:]):
        assert a < b


def test_polar_day_sunrise_sunset_undefined_at_tromso_midsummer():
    # Tromso (69.65 N) at the June solstice: the sun does not set.
    ev = compute_day_events(date(2026, 6, 21), 69.6492, 18.9553)
    assert ev.sunrise is None
    assert ev.maghrib is None
    assert ev.dhuhr is not None  # transit is still defined


def test_polar_night_sunrise_sunset_undefined_at_mcmurdo_midwinter():
    # McMurdo Station (-77.85), Southern winter solstice -> polar night.
    ev = compute_day_events(date(2026, 6, 21), -77.85, 166.6667)
    assert ev.sunrise is None
    assert ev.maghrib is None


def test_asr_after_dhuhr_hanafi_later_than_standard():
    d = date(2026, 9, 19)
    lat, lon = 9.0192, 38.7525
    ev = compute_day_events(d, lat, lon, asr_shadow_ratio=1.0)
    ev_hanafi = compute_day_events(d, lat, lon, asr_shadow_ratio=2.0)
    assert ev.dhuhr < ev.asr < ev_hanafi.asr


def test_elevation_makes_sunset_later_and_sunrise_earlier():
    d = date(2026, 9, 19)
    lat, lon = 9.0192, 38.7525
    sea_level = compute_day_events(d, lat, lon, elevation_m=0.0)
    elevated = compute_day_events(d, lat, lon, elevation_m=2400.0)
    assert elevated.maghrib > sea_level.maghrib
    assert elevated.sunrise < sea_level.sunrise


def test_no_import_of_waqt_package():
    # This is the structural guarantee the whole milestone rests on:
    # independent_solar must never import waqt.* at runtime.
    import independent_solar.events as ev_mod
    import independent_solar.sun as sun_mod
    import independent_solar.sidereal as sid_mod
    import independent_solar.nutation as nut_mod
    import independent_solar.deltat as dt_mod
    import independent_solar.julian as jd_mod

    for mod in (ev_mod, sun_mod, sid_mod, nut_mod, dt_mod, jd_mod):
        src = Path(mod.__file__).read_text()
        assert "import waqt" not in src
        assert "from waqt" not in src

"""
Sprint 11 regression tests for the two epoch-sampling bugs found in the
astronomy evaluation (SPRINT-11-REPORT.md Sec 2):

  Bug 1  `_event_time` refined toward an event using a Julian Day 12 h
         off from the instant being refined (`_jdn(d)` is JD at NOON UT;
         the `- 0.5` was missing).
  Bug 2  `transit()` / `asr()` sampled the sun's declination and the
         equation of time at UT noon of the date rather than at the
         actual transit instant (up to +-12 h away at extreme longitudes).

These are SELF-CONSISTENCY properties, deliberately independent of any
external reference (no pymeeus/astral needed in waqt-core's own suite):
an event time is correct only if the sun's parameters *evaluated at that
very instant* reproduce that same instant. A 12-hour sampling error
breaks this by tens to hundreds of seconds at the sensitive cases below;
the tolerance here is 0.5 s. Level-A agreement is measured separately in
independent-astronomy/compare_sprint11.py.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone

import pytest

from waqt_core import solar
from waqt_core.timescale import DEFAULT_TIMESCALE_PROVIDER as TS

# (name, lat, lon, date): the cases where the bugs were largest.
CASES = [
    ("Tromso near equinox", 69.6492, 18.9553, date(2026, 9, 19)),
    ("Anchorage equinox", 61.2181, -149.9003, date(2026, 3, 20)),
    ("Suva (lon ~178)", -18.1416, 178.4419, date(2026, 9, 23)),
    ("Kiritimati (lon ~-157)", 1.8721, -157.4278, date(2026, 3, 20)),
    ("Punta Arenas", -53.1638, -70.9171, date(2026, 9, 19)),
    ("Addis Ababa", 9.0192, 38.7525, date(2026, 9, 19)),
]


def test_params_at_instant_uses_noon_based_jdn_correctly():
    """JD of 2000-01-01T12:00Z is exactly 2451545.0; midnight is .5 earlier."""
    d = date(2000, 1, 1)
    assert solar._jdn(d) == 2451545
    noon = datetime(2000, 1, 1, 12, tzinfo=timezone.utc)
    midnight = datetime(2000, 1, 1, tzinfo=timezone.utc)
    p_noon = solar._params_at_instant(d, noon, TS)
    p_ref = solar._sun_params(solar._jd_tt(2451545.0, d, TS))
    assert p_noon.declination_deg == pytest.approx(p_ref.declination_deg, abs=1e-12)
    p_mid = solar._params_at_instant(d, midnight, TS)
    p_ref_mid = solar._sun_params(solar._jd_tt(2451544.5, d, TS))
    assert p_mid.declination_deg == pytest.approx(p_ref_mid.declination_deg, abs=1e-12)


@pytest.mark.parametrize("name,lat,lon,d", CASES, ids=[c[0] for c in CASES])
@pytest.mark.parametrize("fn,morning", [(solar.sunrise, True), (solar.sunset, False)])
def test_sunrise_sunset_are_self_consistent(name, lat, lon, d, fn, morning):
    t = fn(d, lat, lon)
    if t is None:
        pytest.skip("event undefined here")
    p = solar._params_at_instant(d, t, TS)
    ha = solar._hour_angle_for_altitude(lat, p.declination_deg, solar.SUNRISE_SUNSET_ALTITUDE_DEG)
    assert ha is not None
    noon = solar._solar_noon_utc(d, lon, p)
    expected = noon - timedelta(minutes=ha * 4.0) if morning else noon + timedelta(minutes=ha * 4.0)
    assert abs((expected - t).total_seconds()) < 0.5


@pytest.mark.parametrize("name,lat,lon,d", CASES, ids=[c[0] for c in CASES])
def test_transit_evaluates_equation_of_time_at_the_transit_instant(name, lat, lon, d):
    t = solar.transit(d, lat, lon)
    p = solar._params_at_instant(d, t, TS)
    assert abs((solar._solar_noon_utc(d, lon, p) - t).total_seconds()) < 0.01


def test_transit_differs_from_the_utc_noon_sampling_where_it_should():
    """At lon ~178 the old UT-noon sampling was ~12 h off; the corrected
    transit must differ from the old estimate by a real, nonzero amount
    (guards against someone 'simplifying' the iteration away)."""
    d, lat, lon = date(2026, 9, 23), -18.1416, 178.4419
    old_style = solar._solar_noon_utc(d, lon, solar._sun_params(solar._jd_tt(solar._jdn(d), d, TS)))
    assert abs((solar.transit(d, lat, lon) - old_style).total_seconds()) > 5.0


def test_asr_uses_declination_at_transit():
    d, lat, lon = date(2026, 3, 20), 61.2181, -149.9003
    a = solar.asr(d, lat, lon, 1.0)
    assert a is not None and a > solar.transit(d, lat, lon)
    # Asr must be afternoon, before sunset.
    assert a < solar.sunset(d, lat, lon)


# ---------------------------------------------------------------------------
# Bug 3 (Sprint 11 Sec 2.4): defined-vs-undefined agreement near the polar
# threshold. Level A and Level B never disagreed with each other; the
# production engine disagreed with both on a handful of threshold days.
# ---------------------------------------------------------------------------

def test_event_returned_is_defined_at_its_own_instant():
    """Whatever time an event function returns, the sun must actually reach
    that altitude when evaluated at that instant (never a time for an event
    that does not exist there). Scans the threshold band."""
    checked = 0
    for lat in [60.0 + 0.5 * i for i in range(0, 41)]:  # 60..80 N
        for day_offset in range(0, 90, 5):  # May-July, spans polar-day onset
            d = date(2026, 5, 1) + timedelta(days=day_offset)
            for fn in (solar.sunrise, solar.sunset):
                t = fn(d, lat, 18.9553)
                if t is None:
                    continue
                p = solar._params_at_instant(d, t, TS)
                assert (
                    solar._hour_angle_for_altitude(lat, p.declination_deg, solar.SUNRISE_SUNSET_ALTITUDE_DEG)
                    is not None
                ), (lat, d, fn.__name__)
                checked += 1
    assert checked > 100


@pytest.mark.parametrize(
    "lat,d,event_fn_name",
    [
        (66.0, date(2026, 6, 12), "sunrise"),   # pre-fix engine: None.  physics: crossing exists. Level A/B: defined
        (66.0, date(2026, 6, 30), "sunrise"),   # pre-fix engine: time. physics: none.           Level A/B: undefined
        (70.0, date(2026, 5, 16), "sunrise"),   # pre-fix engine: None.  physics: crossing exists. Level A/B: defined
        (70.0, date(2026, 7, 27), "sunrise"),   # pre-fix engine: time. physics: none.           Level A/B: undefined
        (73.0, date(2026, 5, 4), "sunset"),     # pre-fix engine: time. physics: none.           Level A/B: undefined
        (66.5, date(2026, 6, 6), "sunrise"),    # fixed engine: time.   physics: crossing exists. Level A/B: UNDEFINED (they are wrong)
        (71.5, date(2026, 5, 10), "sunrise"),   # fixed engine: time.   physics: crossing exists. Level A/B: UNDEFINED (they are wrong)
    ],
)
def test_threshold_days_agree_with_the_independent_references(lat, d, event_fn_name):
    """Pinned from the Sprint 11 threshold scan (SPRINT-11-REPORT.md Sec 2.4).
    Expected status is the PHYSICAL truth -- whether the Sun's true altitude
    (VSOP87) actually crosses the horizon threshold on that side of
    transit, established by brute-force altitude scan
    (independent-astronomy/threshold_truth.py) -- not what the Level A/B
    solving loops return: those two share a transit-anchored loop that
    gives up early, and disagree with the geometry on the (66.5N, Jun 6)
    and (71.5N, May 10) rows below."""
    expected_undefined = {
        (66.0, date(2026, 6, 12)): False,
        (66.0, date(2026, 6, 30)): True,
        (70.0, date(2026, 5, 16)): False,
        (70.0, date(2026, 7, 27)): True,
        (73.0, date(2026, 5, 4)): True,
        (66.5, date(2026, 6, 6)): False,
        (71.5, date(2026, 5, 10)): False,
    }[(lat, d)]
    result = getattr(solar, event_fn_name)(d, lat, 18.9553)
    assert (result is None) == expected_undefined

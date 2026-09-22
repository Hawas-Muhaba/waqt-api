"""
Sprint 3 test suite — Calendar Provider System.

Tests the five provider categories, the registry, provider
pluggability (swapping providers changes only the Hijri date, never
the astronomical output), and the UmmAlQura historical validation.

Run with: python3 -m pytest tests/ -v
"""

from datetime import date, datetime, timezone

import pytest

from waqt.calendar_providers import (
    ArithmeticTabularProvider,
    DeclaredProvider,
    ExampleRegionalOffsetProvider,
    LocalObservationProvider,
    Sighting,
    UmmAlQuraProvider,
)
from waqt.calendar_providers.registry import CalendarProviderRegistry, default_registry
from waqt.core import Location, compute_waqt
from waqt.hijri import HijriDate

LOCATION = Location(9.0192, 38.7525)  # Addis Ababa

# (expected 1-Muharram Gregorian date, expected AH year) — four
# independently-known official Umm al-Qura New Year dates, spanning
# 2016-2025, cross-checked against aladhan.com's published Umm al-Qura
# calendar.
HISTORICAL_UAQ_NEW_YEARS = [
    (date(2016, 10, 2), 1438),
    (date(2018, 9, 11), 1440),
    (date(2019, 8, 31), 1441),
    (date(2025, 6, 26), 1447),
]


# ---------------------------------------------------------------------------
# Identification: every provider carries name + version, and every
# HijriDate returned carries both too.
# ---------------------------------------------------------------------------


def test_every_builtin_provider_has_name_and_version():
    providers = [
        ArithmeticTabularProvider(),
        UmmAlQuraProvider(),
    ]
    for p in providers:
        assert isinstance(p.name, str) and p.name
        assert isinstance(p.version, str) and p.version


def test_returned_hijri_date_carries_provider_and_version():
    d = date(2026, 9, 19)
    for provider in (ArithmeticTabularProvider(), UmmAlQuraProvider()):
        hd = provider.from_gregorian(d)
        assert hd.provider == provider.name
        assert hd.version == provider.version


# ---------------------------------------------------------------------------
# UmmAlQuraProvider: the historical validation this whole provider
# stands or falls on.
# ---------------------------------------------------------------------------


def test_umm_al_qura_reproduces_known_historical_new_years():
    uaq = UmmAlQuraProvider()
    for expected_date, expected_year in HISTORICAL_UAQ_NEW_YEARS:
        hd = uaq.from_gregorian(expected_date)
        assert hd.year == expected_year, (expected_date, hd)
        assert hd.month == 1, (expected_date, hd)
        assert hd.day == 1, (expected_date, hd)


def test_umm_al_qura_day_before_new_year_is_previous_year_last_month():
    uaq = UmmAlQuraProvider()
    day_before = date(2025, 6, 25)
    hd = uaq.from_gregorian(day_before)
    assert hd.year == 1446
    assert hd.month == 12  # Dhu al-Hijjah


def test_umm_al_qura_consecutive_days_increment_correctly():
    uaq = UmmAlQuraProvider()
    d1 = uaq.from_gregorian(date(2025, 6, 26))
    d2 = uaq.from_gregorian(date(2025, 6, 27))
    assert d1.iso_like() == "1447-01-01"
    assert d2.iso_like() == "1447-01-02"


def test_umm_al_qura_differs_from_arithmetic_but_stays_close():
    # They are different algorithms and WILL disagree sometimes (that's
    # the entire reason Stage 1 refused to call the arithmetic one
    # "umm-al-qura"). But they should never be wildly apart.
    d = date(2026, 9, 19)
    arith = ArithmeticTabularProvider().from_gregorian(d)
    uaq = UmmAlQuraProvider().from_gregorian(d)
    # Assert both land in the same or adjacent Hijri month.
    assert abs(arith.month - uaq.month) <= 1 or (arith.month == 12 and uaq.month == 1)


def test_umm_al_qura_does_not_crash_on_dates_far_from_anchor():
    """RecursionError fix: dates far from the 2025 anchor must not crash.
    The original recursive _boundary() hit Python's stack limit at ~75
    months; this iterative version handles arbitrary distances.
    """
    uaq = UmmAlQuraProvider()
    # ~660 months before the anchor (1970)
    hd_past = uaq.from_gregorian(date(1970, 1, 1))
    assert hd_past.year > 1300 and hd_past.year < 1410

    # ~780 months after the anchor (2090)
    hd_future = uaq.from_gregorian(date(2090, 6, 1))
    assert hd_future.year > 1510 and hd_future.year < 1520


# ---------------------------------------------------------------------------
# Pluggability: swapping the provider changes ONLY the Hijri date.
# ---------------------------------------------------------------------------


def test_swapping_calendar_provider_does_not_change_astronomy():
    t = datetime(2026, 9, 19, 15, 42, tzinfo=timezone.utc)
    r_arith = compute_waqt(t, LOCATION, ArithmeticTabularProvider())
    r_uaq = compute_waqt(t, LOCATION, UmmAlQuraProvider())

    assert r_arith.hour_reading == r_uaq.hour_reading
    assert r_arith.day_start_maghrib == r_uaq.day_start_maghrib
    assert r_arith.day_end_maghrib == r_uaq.day_end_maghrib
    for name in ("fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha"):
        a = next(e for e in r_arith.events if e.name == name)
        b = next(e for e in r_uaq.events if e.name == name)
        assert a.instant == b.instant

    # The Hijri date is the one thing that's allowed to differ:
    assert r_arith.hijri_date.provider != r_uaq.hijri_date.provider


def test_custom_provider_plugs_in_untouched():
    """A third-party provider, written entirely outside waqt/core.py and
    waqt/solar.py, works through the exact same injection point as the
    built-ins — proving those two files never needed to change."""
    t = datetime(2026, 9, 19, 15, 42, tzinfo=timezone.utc)
    custom = ExampleRegionalOffsetProvider(wrapped=ArithmeticTabularProvider(), day_offset=1)

    r_custom = compute_waqt(t, LOCATION, custom)
    r_plain = compute_waqt(t, LOCATION, ArithmeticTabularProvider())

    assert r_custom.status == "OK"
    assert r_custom.hijri_date.provider == "example-regional-offset"
    # Astronomy is, again, completely unaffected by which calendar
    # provider was chosen:
    assert r_custom.hour_reading == r_plain.hour_reading


# ---------------------------------------------------------------------------
# Declared / LocalObservation: override-with-fallback shape, correctly
# distinguished and correctly falling back.
# ---------------------------------------------------------------------------


def test_declared_provider_overrides_and_falls_back():
    fallback = ArithmeticTabularProvider()
    override_date = date(2026, 9, 19)
    overridden = HijriDate(year=1448, month=4, day=8, provider="whatever")
    declared = DeclaredProvider(overrides={override_date: overridden}, fallback=fallback)

    result_on_override = declared.from_gregorian(override_date)
    assert result_on_override.provider == "declared"
    assert (result_on_override.year, result_on_override.month, result_on_override.day) == (1448, 4, 8)

    other_date = date(2026, 9, 20)
    result_fallback = declared.from_gregorian(other_date)
    assert result_fallback.provider == fallback.name


def test_local_observation_provider_carries_source_note_and_falls_back():
    fallback = ArithmeticTabularProvider()
    sighting_date = date(2026, 9, 19)
    sightings = {
        sighting_date: Sighting(year=1448, month=4, day=7, observed_at="Addis Ababa, Ethiopia"),
    }
    provider = LocalObservationProvider(sightings=sightings, fallback=fallback)

    seen = provider.from_gregorian(sighting_date)
    assert seen.provider == "local-observation"
    assert seen.source_note == "Addis Ababa, Ethiopia"

    unseen = provider.from_gregorian(date(2026, 9, 20))
    assert unseen.provider == fallback.name
    assert unseen.source_note is None


def test_local_observation_and_declared_are_distinct_provider_names():
    # Same shape, but the sprint brief asks that they be genuinely
    # distinct provider categories, not aliases of one class.
    fallback = ArithmeticTabularProvider()
    declared = DeclaredProvider(overrides={}, fallback=fallback)
    observed = LocalObservationProvider(sightings={}, fallback=fallback)
    assert declared.name != observed.name


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_registry_looks_up_builtin_providers_by_name():
    reg = default_registry()
    assert reg.get("arithmetic-tabular") is not None
    assert reg.get("umm-al-qura") is not None
    assert reg.get("does-not-exist") is None
    assert set(reg.names()) >= {"arithmetic-tabular", "umm-al-qura"}


def test_registry_accepts_a_custom_provider_registered_at_runtime():
    reg = CalendarProviderRegistry()
    custom = ExampleRegionalOffsetProvider(wrapped=ArithmeticTabularProvider(), day_offset=2)
    reg.register(custom)
    assert reg.get("example-regional-offset") is custom

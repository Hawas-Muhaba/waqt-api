"""Regression suite for the "Rabi al-Thani 25 vs 27" report (2026-10-08).

ROOT CAUSE (traced, then pinned here): there is no defect in the Waqt-day -> civil-date -> provider data flow and no
offset anywhere. The value 25 is what the *arithmetic-tabular* provider returns for 2026-10-08; the Umm al-Qura
provider returns 27 (matching the official Umm al-Qura table). The web application had hard-coded
calendar_provider=arithmetic-tabular and displayed the result as a bare "Hijri" date. The two conventions differ by
two days on these dates (arithmetic-tabular starts 1 Rabi al-Thani on 14 Sept 2026, Umm al-Qura on 12 Sept).

Nothing here depends on the machine's current date or timezone. Groups:
  1. provider conversion      2. Waqt-day assignment / Maghrib boundary      3. timezone independence
  4. API serialization        5. independent oracle (official table), skipped if the oracle package is absent
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from waqt.api import app
from waqt_core.calendar_providers import UmmAlQuraProvider
from waqt_core.core import Location, compute_waqt
from waqt_core.hijri import ArithmeticTabularProvider

UQ = UmmAlQuraProvider()
ARITH = ArithmeticTabularProvider()
MAKKAH = Location(lat=21.4225, lon=39.8262, elevation_m=0.0)

# The cases from the bug report: Gregorian civil date -> expected Umm al-Qura day of Rabi al-Thani 1448.
UQ_EXPECTED = {date(2026, 10, 6): 25, date(2026, 10, 7): 26, date(2026, 10, 8): 27, date(2026, 10, 9): 28}
# Characterisation of the OTHER convention on the same dates. This documents the cause: it is the arithmetic
# calendar, not Umm al-Qura, that yields the "25" seen on 2026-10-08.
ARITH_EXPECTED = {date(2026, 10, 6): 23, date(2026, 10, 7): 24, date(2026, 10, 8): 25, date(2026, 10, 9): 26}


# ------------------------------------------------------------------------------------ 1. provider conversion
@pytest.mark.parametrize("d,day", sorted(UQ_EXPECTED.items()))
def test_umm_al_qura_surrounding_dates(d, day):
    h = UQ.from_gregorian(d)
    assert (h.year, h.month, h.month_name, h.day) == (1448, 4, "Rabi al-Thani", day)
    assert h.provider == "umm-al-qura"


def test_reference_case_2026_10_08_is_27_and_never_the_old_25():
    h = UQ.from_gregorian(date(2026, 10, 8))
    assert str(h) == "27 Rabi al-Thani 1448 AH"
    assert h.day != 25, "the old arithmetic-tabular value must not come back through the Umm al-Qura provider"


@pytest.mark.parametrize("d,day", sorted(ARITH_EXPECTED.items()))
def test_arithmetic_tabular_is_a_different_convention_not_a_bug(d, day):
    h = ARITH.from_gregorian(d)
    assert (h.year, h.month, h.day) == (1448, 4, day)
    assert h.provider == "arithmetic-tabular"
    assert day == UQ_EXPECTED[d] - 2, "documented 2-day divergence between the conventions on these dates"


def test_month_start_differs_by_two_days_between_conventions():
    first = lambda p: next(d for d in (date(2026, 9, 1) + timedelta(days=i) for i in range(40)) if (lambda h: h.month == 4 and h.day == 1)(p.from_gregorian(d)))
    assert first(UQ) == date(2026, 9, 12) and first(ARITH) == date(2026, 9, 14)


def test_no_manual_day_offset_in_the_hijri_data_flow():
    """Guard against the 'fix' the brief forbids: a hand-added +/-N day correction anywhere on the path."""
    import re
    root = os.path.join(os.path.dirname(__file__), "..")
    for rel in ("core/waqt_core/calendar_providers/umm_al_qura.py", "waqt/api/providers.py", "waqt/api/waqt_endpoint.py", "core/waqt_core/core.py"):
        src = open(os.path.join(root, rel), encoding="utf-8").read()
        assert not re.search(r"hijri\w*\.day\s*[+-]\s*\d|hijri_offset|offset_days|day_offset", src, re.I), f"suspicious Hijri day arithmetic in {rel}"
        assert "timedelta(days=2)" not in src, rel


# ------------------------------------------------- 2. Waqt-day assignment and the Maghrib boundary (exact instants)
def _day_of(t, loc=MAKKAH, provider=UQ, tz=None):
    return compute_waqt(t, loc, provider, **({"tz_provider": tz} if tz else {}))


def _sequence(lat, lon):
    """Return the labelled instants around one Maghrib, computed with exact (microsecond) datetimes."""
    loc = Location(lat=lat, lon=lon, elevation_m=0.0)
    probe = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)
    base = compute_waqt(probe, loc, UQ)
    tz = ZoneInfo(base.timezone_name)
    close = base.day_end_maghrib
    next_close = compute_waqt(close + timedelta(microseconds=1), loc, UQ).day_end_maghrib
    local_close = close.astimezone(tz)
    midnight = datetime.combine(local_close.date() + timedelta(days=1), datetime.min.time(), tzinfo=tz)
    noon = midnight + timedelta(hours=12)
    steps = [("close-1us", close - timedelta(microseconds=1)), ("close (exact)", close), ("close+1us", close + timedelta(microseconds=1)),
             ("next civil midnight", midnight), ("next local noon", noon), ("next Maghrib (exact)", next_close)]
    rows = []
    for name, t in steps:
        r = compute_waqt(t, loc, UQ)
        rows.append((name, r.day_start_maghrib, r.day_end_maghrib, r.hijri_date.day, r.weekday))
    return base, close, next_close, rows


@pytest.mark.parametrize("place,lat,lon", [("Makkah", 21.4225, 39.8262), ("Addis Ababa", 9.0192, 38.7525), ("Los Angeles", 34.05, -118.24), ("Honolulu", 21.31, -157.86)])
def test_waqt_day_and_hijri_label_transition_exactly_once_at_maghrib(place, lat, lon):
    base, close, next_close, rows = _sequence(lat, lon)
    by = {r[0]: r for r in rows}
    before, at, after = by["close-1us"], by["close (exact)"], by["close+1us"]
    # day is half-open [open, close): the instant before belongs to the old day, the exact close to the NEW day
    assert before[2] == close and at[1] == close and after[1] == close
    assert before[3] == base.hijri_date.day, "Hijri label before Maghrib belongs to the closing day"
    assert at[3] == after[3] == base.hijri_date.day + 1, "the label advances by exactly one day, at Maghrib"
    # no second transition: civil midnight and next local noon stay in the same Waqt day and keep the label
    assert by["next civil midnight"][1] == close and by["next local noon"][1] == close
    assert by["next civil midnight"][3] == by["next local noon"][3] == at[3]
    assert by["next civil midnight"][4] == by["next local noon"][4] == at[4], "weekday also changes only at Maghrib"
    # next Maghrib opens a new day: the label advances once more
    assert by["next Maghrib (exact)"][1] == next_close and by["next Maghrib (exact)"][3] == at[3] + 1


def test_the_date_given_to_the_provider_is_the_closing_maghribs_civil_date_not_utc_not_server_local():
    """DR-0001: a Waqt day is labelled with the civil date of its closing Maghrib in the LOCATION's timezone.
    Los Angeles closes on the next UTC date (Maghrib ~18:28 local = 01:28 UTC), so any UTC leakage would shift the label."""
    loc = Location(lat=34.05, lon=-118.24, elevation_m=0.0)
    r = compute_waqt(datetime(2026, 10, 7, 20, 0, tzinfo=timezone.utc), loc, UQ)       # 13:00 local, 7 Oct
    close_local = r.day_end_maghrib.astimezone(ZoneInfo("America/Los_Angeles"))
    assert close_local.date() == date(2026, 10, 7) and r.day_end_maghrib.date() == date(2026, 10, 8)   # UTC date differs
    assert r.hijri_date.day == UQ_EXPECTED[date(2026, 10, 7)], "label follows the LOCAL closing-Maghrib date (7 Oct -> 26), not the UTC date (8 Oct -> 27)"


# ------------------------------------------------------------------------------------ 3. machine-timezone independence
_PROBE = textwrap.dedent("""
    import json
    from datetime import datetime, timedelta, timezone
    from waqt_core.core import Location, compute_waqt
    from waqt_core.calendar_providers import UmmAlQuraProvider
    u = UmmAlQuraProvider(); out = []
    for lat, lon in [(21.4225, 39.8262), (34.05, -118.24), (-6.2088, 106.8456)]:
        loc = Location(lat=lat, lon=lon, elevation_m=0.0)
        c = compute_waqt(datetime(2026, 10, 7, 12, tzinfo=timezone.utc), loc, u).day_end_maghrib
        for t in (c - timedelta(microseconds=1), c, c + timedelta(hours=7), c + timedelta(hours=19)):
            r = compute_waqt(t, loc, u); out.append([t.isoformat(), r.day_end_maghrib.isoformat(), r.hijri_date.day, r.weekday])
    print(json.dumps(out))
""")


def test_results_do_not_depend_on_the_machines_timezone():
    results = {}
    for tz in ("UTC", "America/Los_Angeles", "Asia/Tokyo", "Pacific/Kiritimati"):
        env = dict(os.environ, TZ=tz)
        p = subprocess.run([sys.executable, "-c", _PROBE], capture_output=True, text=True, env=env, check=True)
        results[tz] = json.loads(p.stdout)
    first = next(iter(results.values()))
    for tz, res in results.items():
        assert res == first, f"output changed under TZ={tz}: server-local timezone leaked"


# --------------------------------------------------------------------------------------------- 4. API serialization
client = TestClient(app)


def _api(instant, provider=None, lat=21.4225, lon=39.8262):
    params = {"lat": lat, "lon": lon, "instant": instant}
    if provider:
        params["calendar_provider"] = provider
    r = client.get("/v1/waqt", params=params)
    assert r.status_code == 200, r.text
    return r.json()["data"]


@pytest.mark.parametrize("instant,day", [("2026-10-06T09:00:00Z", 25), ("2026-10-07T09:00:00Z", 26), ("2026-10-08T09:00:00Z", 27), ("2026-10-09T09:00:00Z", 28)])
def test_api_umm_al_qura_exposes_date_and_selected_provider(instant, day):
    h = _api(instant, "umm-al-qura")["hijri"]
    assert (h["year"], h["month"], h["month_name"], h["day"]) == (1448, 4, "Rabi al-Thani", day)
    assert h["display"] == f"{day} Rabi al-Thani 1448 AH" and h["date"] == f"1448-04-{day:02d}"
    assert h["provider"]["name"] == "umm-al-qura" and h["provider"]["version"]


def test_api_default_provider_is_umm_al_qura():
    """The default follows the web app; callers can still request arithmetic-tabular explicitly."""
    h = _api("2026-10-08T09:00:00Z")["hijri"]
    assert h["provider"]["name"] == "umm-al-qura" and h["day"] == 27


def test_api_explicit_arithmetic_tabular_remains_available():
    h = _api("2026-10-08T09:00:00Z", "arithmetic-tabular")["hijri"]
    assert h["provider"]["name"] == "arithmetic-tabular" and h["day"] == 25


def test_hijri_and_conversion_endpoints_default_to_umm_al_qura():
    hijri = client.get("/v1/hijri", params={"date": "2026-10-08"}).json()["data"]["hijri"]
    converted = client.get("/v1/conversions", params={
        "direction": "to-hijri", "date": "2026-10-08",
    }).json()["data"]["output"]["hijri"]
    assert hijri["provider"]["name"] == converted["provider"]["name"] == "umm-al-qura"
    assert hijri["day"] == converted["day"] == 27


def test_api_provider_choice_never_changes_waqt_time():
    a, b = _api("2026-10-08T09:00:00Z", "umm-al-qura"), _api("2026-10-08T09:00:00Z", "arithmetic-tabular")
    assert a["hijri"]["day"] != b["hijri"]["day"]
    for k in ("day", "waqt", "events", "next_event", "weekday", "timezone", "location"):
        assert a[k] == b[k], f"{k} differs between Hijri providers: provider differences leaked into Waqt time"


def test_api_label_flips_at_maghrib_in_the_response():
    d = _api("2026-10-07T09:00:00Z", "umm-al-qura")
    close = datetime.fromisoformat(d["day"]["maghrib_close"])
    just_after = (close + timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
    assert _api(just_after, "umm-al-qura")["hijri"]["day"] == d["hijri"]["day"] + 1


# -------------------------------------------------------------------- 5. independent oracle: the official Umm al-Qura table
def test_umm_al_qura_provider_matches_the_official_table_over_a_year():
    hijridate = pytest.importorskip("hijridate", reason="optional oracle: pip install hijridate==2.3.0")
    mismatches, d = [], date(2026, 6, 1)
    while d < date(2027, 6, 1):
        o = hijridate.Gregorian(d.year, d.month, d.day).to_hijri()
        h = UQ.from_gregorian(d)
        if (h.year, h.month, h.day) != (o.year, o.month, o.day):
            mismatches.append((d.isoformat(), (o.year, o.month, o.day), (h.year, h.month, h.day)))
        d += timedelta(days=1)
    assert not mismatches, mismatches[:5]

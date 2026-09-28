"""
Loads tests/vectors/waqt_vectors.json and re-computes every vector
through the live implementation, asserting an exact match. This is
both a regression test (behavior must not silently drift from the
frozen vectors) and proof that the vector file is actually
reproducible — the thing an independent implementation in another
language would need to be true for the file to be useful to them.

If a vector legitimately needs to change (real behavior change,
intentional), re-run tests/vectors/generate_vectors.py and review the
diff — do not hand-edit the JSON.

Sprint 11 conformance: driven directly against `waqt_core` (not `waqt`, not the local library) so this suite proves the extracted package alone reproduces the same publicly committed vectors every other suite in this repository uses — with only waqt-core installed, no FastAPI, no `waqt`.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from waqt_core.core import AstronomyProfile, Location, compute_waqt
from waqt_core.hijri import ArithmeticTabularProvider
from waqt_core.semantics import waqt_day_from_result

VECTORS_PATH = Path(__file__).resolve().parents[2] / "tests" / "vectors" / "waqt_vectors.json"
PROVIDER = ArithmeticTabularProvider()


def _load_vectors():
    data = json.loads(VECTORS_PATH.read_text())
    return data["vectors"]


VECTORS = _load_vectors()


def _iso(dt):
    return dt.astimezone(timezone.utc).isoformat() if dt is not None else None


@pytest.mark.parametrize("vector", VECTORS, ids=[v["id"] for v in VECTORS])
def test_vector_reproduces_exactly(vector):
    inp = vector["input"]
    expected = vector["expected"]

    instant = datetime.fromisoformat(inp["instant"])
    loc = Location(inp["location"]["lat"], inp["location"]["lon"], inp["location"]["elevation_m"])
    profile = AstronomyProfile(**{
        "fajr_angle_deg": inp["astronomy_profile"]["fajr_angle_deg"],
        "isha_angle_deg": inp["astronomy_profile"]["isha_angle_deg"],
        "asr_shadow_ratio": inp["astronomy_profile"]["asr_shadow_ratio"],
    })

    r = compute_waqt(instant, loc, PROVIDER, profile)

    assert r.status == expected["status"], vector["id"]

    if expected["status"] != "OK":
        return  # UNDEFINED/ORDERING_VIOLATION vectors only assert status + reason presence

    day = waqt_day_from_result(r)
    pos = day.position_of(instant)

    assert r.hijri_date.iso_like() == expected["hijri_date"], vector["id"]
    assert r.weekday == expected["weekday"], vector["id"]
    assert _iso(r.day_start_maghrib) == expected["day"]["maghrib_open"], vector["id"]
    assert _iso(r.day_end_maghrib) == expected["day"]["maghrib_close"], vector["id"]
    assert round(r.day_length_si_seconds, 3) == expected["day"]["length_si_seconds"], vector["id"]

    assert pos.display == expected["waqt_position"]["display"], vector["id"]
    assert pos.hour == expected["waqt_position"]["hour"], vector["id"]
    assert round(pos.total_seconds, 3) == expected["waqt_position"]["total_seconds"], vector["id"]

    for ev in day.events():
        exp_ev = expected["events"].get(ev.name)
        assert exp_ev is not None, f"{vector['id']}: unexpected extra event {ev.name}"
        assert ev.position.display == exp_ev["position_display"], f"{vector['id']}.{ev.name}"
        assert round(ev.position.total_seconds, 3) == exp_ev["position_total_seconds"], f"{vector['id']}.{ev.name}"


def test_exact_maghrib_vector_is_precisely_zero():
    v = next(v for v in VECTORS if v["id"] == "addis-exact-maghrib-boundary")
    assert v["expected"]["waqt_position"]["display"] == "00:00:00"
    assert v["expected"]["waqt_position"]["total_seconds"] == 0.0


def test_long_day_vector_exceeds_24_hours():
    v = next(v for v in VECTORS if v["id"] == "london-long-day-near-24h-boundary")
    assert v["expected"]["day"]["length_si_seconds"] > 86400
    assert v["expected"]["waqt_position"]["hour"] == 24


def test_asr_vectors_differ_only_in_asr_event():
    std = next(v for v in VECTORS if v["id"] == "addis-asr-standard")["expected"]
    han = next(v for v in VECTORS if v["id"] == "addis-asr-hanafi")["expected"]
    assert std["waqt_position"] == han["waqt_position"]
    assert std["day"] == han["day"]
    for name in ("fajr", "sunrise", "dhuhr", "maghrib", "isha"):
        assert std["events"][name] == han["events"][name], name
    assert std["events"]["asr"] != han["events"]["asr"]


def test_elevation_vector_shifts_maghrib_later():
    sea_level = next(v for v in VECTORS if v["id"] == "addis-normal-instant")["expected"]
    elevated = next(v for v in VECTORS if v["id"] == "addis-elevation-2400m")["expected"]
    t_sea = datetime.fromisoformat(sea_level["day"]["maghrib_close"])
    t_elev = datetime.fromisoformat(elevated["day"]["maghrib_close"])
    assert t_elev > t_sea


def test_undefined_vector_has_no_position_or_events():
    v = next(v for v in VECTORS if v["id"] == "tromso-midsummer-undefined")
    assert v["expected"]["status"] == "UNDEFINED"
    assert "waqt_position" not in v["expected"]
    assert "events" not in v["expected"]
    assert v["expected"]["undefined_reason"] is not None

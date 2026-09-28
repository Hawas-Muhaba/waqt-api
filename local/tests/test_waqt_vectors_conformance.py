"""
waqt_local conformance — tests/vectors/waqt_vectors.json (repo root),
computed through `waqt_local.waqt(...)`, not through waqt.core directly.

This is the "extend the [conformance vector] pattern to the local
computation library" item from the Sprint 10 brief: the same public
vectors the Python/JS core suites and the SDK conformance suites
already use, now also exercised by the third, local-computation
consumer the architecture diagram in docs/LOCAL.md names.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import waqt_local

REPO_ROOT = Path(__file__).resolve().parents[2]
VECTORS = json.loads((REPO_ROOT / "tests" / "vectors" / "waqt_vectors.json").read_text())["vectors"]


@pytest.mark.parametrize("vector", VECTORS, ids=[v["id"] for v in VECTORS])
def test_local_facade_reproduces_waqt_vectors(vector):
    inp = vector["input"]
    expected = vector["expected"]

    r = waqt_local.waqt(
        lat=inp["location"]["lat"],
        lon=inp["location"]["lon"],
        elevation_m=inp["location"]["elevation_m"],
        instant=inp["instant"],
        calendar_provider=inp["calendar_provider"],
        fajr_angle=inp["astronomy_profile"]["fajr_angle_deg"],
        isha_angle=inp["astronomy_profile"]["isha_angle_deg"],
        asr_ratio=inp["astronomy_profile"]["asr_shadow_ratio"],
    )

    assert r["status"] == expected["status"], vector["id"]
    if expected["status"] != "OK":
        assert r["undefined_reason"], vector["id"]
        return

    assert r["hijri"]["date"] == expected["hijri_date"], vector["id"]
    assert r["weekday"] == expected["weekday"], vector["id"]
    assert r["day"]["maghrib_open"][:19] == expected["day"]["maghrib_open"][:19], vector["id"]
    assert r["day"]["maghrib_close"][:19] == expected["day"]["maghrib_close"][:19], vector["id"]
    assert round(r["day"]["length_si_seconds"], 3) == expected["day"]["length_si_seconds"], vector["id"]

    exp_pos = expected["waqt_position"]
    assert r["waqt"]["display"] == f"Waqt {exp_pos['display']}", vector["id"]
    assert round(r["waqt"]["reading"]["seconds"], 3) == exp_pos["total_seconds"], vector["id"]

    by_name = {e["name"]: e for e in r["events"]}
    for name, exp_ev in expected["events"].items():
        got = by_name.get(name)
        assert got is not None, f"{vector['id']}: missing event {name}"
        if exp_ev.get("position_display") is None:
            continue
        assert got["reading"]["display"] == exp_ev["position_display"], f"{vector['id']}.{name}"
        assert round(got["reading"]["seconds"], 3) == exp_ev["position_total_seconds"], f"{vector['id']}.{name}"


def test_vector_file_actually_has_undefined_cases():
    assert any(v["expected"]["status"] != "OK" for v in VECTORS)

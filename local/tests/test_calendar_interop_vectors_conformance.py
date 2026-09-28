"""
waqt_local conformance — tests/vectors/calendar_interop_vectors.json,
driven through `waqt_local.represent_instant` /
`waqt_local.waqt_day_for_gregorian_date` / `waqt_local.boundary_crossing`
(the local equivalents of the three `/v1/calendar/*` interop
endpoints), not through `waqt.calendar_interop` directly.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import waqt_local

REPO_ROOT = Path(__file__).resolve().parents[2]
DOC = json.loads((REPO_ROOT / "tests" / "vectors" / "calendar_interop_vectors.json").read_text())


@pytest.mark.parametrize("v", DOC["instant_representation"], ids=lambda v: v["id"])
def test_local_represent_instant_reproduces_vectors(v):
    loc = v["context"]["location"]

    if v["op"] == "provider_invariance":
        pytest.skip("declared-provider override scenario -- exercised directly at the repo-root suite")

    r = waqt_local.represent_instant(instant=v["instant"], lat=loc["lat"], lon=loc["lon"], elevation_m=loc["elevation_m"])
    assert r["gregorian"]["utc"] == v["expected"]["gregorian_utc"], v["id"]
    assert r["gregorian"]["civil"] == v["expected"]["gregorian_civil"], v["id"]
    assert r["waqt"]["status"] == v["expected"]["waqt_status"], v["id"]
    if v["expected"]["waqt_position_seconds"] is not None:
        assert round(r["waqt"]["day"]["position_seconds"], 3) == v["expected"]["waqt_position_seconds"], v["id"]


@pytest.mark.parametrize("v", DOC["gregorian_date_to_waqt_day"], ids=lambda v: v["id"])
def test_local_waqt_day_for_gregorian_date_reproduces_vectors(v):
    loc = v["context"]["location"]
    r = waqt_local.waqt_day_for_gregorian_date(date=v["date"], lat=loc["lat"], lon=loc["lon"], elevation_m=loc["elevation_m"])
    assert r["waqt"]["status"] == "OK", v["id"]
    assert v["expected"]["resolved"] is True, v["id"]

    close_instant = r["waqt"]["day"]["maghrib_close"]
    rep = waqt_local.represent_instant(instant=close_instant, lat=loc["lat"], lon=loc["lon"], elevation_m=loc["elevation_m"])
    assert rep["gregorian"]["civil"]["date"] == v["expected"]["close_civil_date"], v["id"]


@pytest.mark.parametrize("v", DOC["boundary_crossing"], ids=lambda v: v["id"])
def test_local_boundary_crossing_reproduces_vectors(v):
    loc = v["context"]["location"]
    r = waqt_local.boundary_crossing(start=v["start"], end=v["end"], lat=loc["lat"], lon=loc["lon"], elevation_m=loc["elevation_m"])
    assert r["crosses_civil_midnight"] == v["expected"]["crosses_civil_midnight"], v["id"]
    assert r["crosses_maghrib"] == v["expected"]["crosses_maghrib"], v["id"]
    assert r["start_civil_date"] == v["expected"]["start_civil_date"], v["id"]
    assert r["end_civil_date"] == v["expected"]["end_civil_date"], v["id"]

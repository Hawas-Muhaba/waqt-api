"""
Sprint 8 conformance: tests/vectors/calendar_interop_vectors.json.

Same three-part guarantee Sprint 6/7 established:

1. REGRESSION   every vector re-derives, exactly, through the live
                Python engine (waqt.calendar_interop).
2. COVERAGE     the file contains every scenario the Sprint 8 brief's
                "minimum test matrix" names.
3. INDEPENDENCE the JavaScript consumer in consumers/js — sharing no
                code with this package — reproduces every vector using
                only its own frozen context, no astronomy of its own.

Sprint 11 conformance: driven directly against `waqt_core` (not `waqt`, not the local library) so this suite proves the extracted package alone reproduces the same publicly committed vectors every other suite in this repository uses — with only waqt-core installed, no FastAPI, no `waqt`.
"""

import json
import shutil
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from waqt_core import calendar_interop as ci
from waqt_core.calendar_providers import ArithmeticTabularProvider, DeclaredProvider
from waqt_core.core import Location
from waqt_core.hijri import HijriDate

ROOT = Path(__file__).resolve().parents[2]  # core/tests/file.py -> repo root
DOC = json.loads((ROOT / "tests" / "vectors" / "calendar_interop_vectors.json").read_text())

ARITH = ArithmeticTabularProvider()


def _location(block) -> Location:
    return Location(lat=block["lat"], lon=block["lon"], elevation_m=block["elevation_m"])


def _parse_instant(s: str) -> datetime:
    return datetime.fromisoformat(s).astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# 1. Regression: every vector re-derives through the live Python engine
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("v", DOC["instant_representation"], ids=lambda v: v["id"])
def test_instant_representation_vectors_regress(v):
    loc = _location(v["context"]["location"])
    t = _parse_instant(v["instant"])

    if v["op"] == "provider_invariance":
        rep_arith = ci.represent_instant(t, loc, ARITH)
        # Re-derive the same override this vector's generator used: the
        # closing civil date of the Waqt day containing `t`.
        close_civil = ci.gregorian_of_instant(rep_arith.waqt_day.close, loc).date
        hd = HijriDate(1447, 9, 13, provider="declared", version="manual-v1", source_note="test override")
        declared = DeclaredProvider(overrides={close_civil: hd}, fallback=ARITH)
        rep_declared = ci.represent_instant(t, loc, declared)

        assert rep_arith.to_dict()["gregorian_utc"] == v["expected"]["gregorian_utc"]
        assert rep_arith.to_dict()["waqt"]["day_open_maghrib"] == v["expected"]["maghrib_open"]
        assert rep_arith.to_dict()["waqt"]["day_close_maghrib"] == v["expected"]["maghrib_close"]
        assert rep_declared.to_dict()["waqt"]["hijri"] == v["expected"]["hijri_declared"]
        return

    rep = ci.represent_instant(t, loc, ARITH)
    body = rep.to_dict()
    assert body["gregorian_utc"] == v["expected"]["gregorian_utc"]
    assert body["gregorian_civil"] == v["expected"]["gregorian_civil"]
    assert body["waqt_status"] == v["expected"]["waqt_status"]
    if v["expected"]["waqt_position_seconds"] is not None:
        assert round(rep.waqt_position_seconds, 3) == v["expected"]["waqt_position_seconds"]


@pytest.mark.parametrize("v", DOC["gregorian_date_to_waqt_day"], ids=lambda v: v["id"])
def test_gregorian_date_to_waqt_day_vectors_regress(v):
    loc = _location(v["context"]["location"])
    g = date.fromisoformat(v["date"])
    day = ci.waqt_day_for_gregorian_date(g, loc, ARITH)
    assert ci.gregorian_of_instant(day.close, loc).date.isoformat() == v["expected"]["close_civil_date"]
    assert v["expected"]["resolved"] is True


@pytest.mark.parametrize("v", DOC["boundary_crossing"], ids=lambda v: v["id"])
def test_boundary_crossing_vectors_regress(v):
    loc = _location(v["context"]["location"])
    start = _parse_instant(v["start"])
    end = _parse_instant(v["end"])
    result = ci.classify_boundary_crossing(start, end, loc, ARITH)
    assert result.crosses_civil_midnight == v["expected"]["crosses_civil_midnight"]
    assert result.crosses_maghrib == v["expected"]["crosses_maghrib"]
    assert result.start_civil_date.isoformat() == v["expected"]["start_civil_date"]
    assert result.end_civil_date.isoformat() == v["expected"]["end_civil_date"]


# ---------------------------------------------------------------------------
# 2. Coverage: the brief's minimum test matrix is actually present
# ---------------------------------------------------------------------------

def test_vector_file_covers_the_sprint_8_minimum_test_matrix():
    ids = {v["id"] for group in DOC.values() if isinstance(group, list) for v in group}
    required_scenarios = [
        "ordinary-conversion-addis",           # ordinary Gregorian/Waqt conversion
        "exact-maghrib",                        # exact Maghrib
        "one-second-before-maghrib",            # one second before Maghrib
        "one-second-after-maghrib",             # one second after Maghrib
        "date-line-date-kiritimati",            # date-line locations
        "leap-year-feb-29",                     # leap-year Gregorian dates
        "waqt-date-differs-from-civil-date",    # Waqt date whose Gregorian rep differs from intuitive civil date
        "provider-change-affects-hijri-label-only",  # provider changes affect Hijri labels only
        "timezone-vs-solar-dibrugarh",          # location where timezone and solar time differ substantially
        "civil-midnight-only",                  # civil midnight without Maghrib crossing
        "maghrib-only",                         # Maghrib without civil-midnight crossing
        "both-boundaries",                      # both boundaries
    ]
    missing = [s for s in required_scenarios if s not in ids]
    assert not missing, f"missing required Sprint 8 test-matrix scenarios: {missing}"
    # "exact civil midnight" is covered by two vectors (starts-/ends-exactly-at-civil-midnight)
    assert "starts-exactly-at-civil-midnight" in ids and "ends-exactly-at-civil-midnight" in ids


def test_vector_ids_are_unique():
    ids = [v["id"] for group in DOC.values() if isinstance(group, list) for v in group]
    assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# 3. Independence: the JS consumer reproduces every vector on its own
# ---------------------------------------------------------------------------

NODE = shutil.which("node")


@pytest.mark.skipif(NODE is None, reason="Node.js not installed; the independent JS consumer cannot run here")
def test_independent_javascript_consumer_validates_all_vectors():
    js = ROOT / "consumers" / "js"
    r = subprocess.run(
        [NODE, "--test", "--test-reporter=tap", "test/calendar_interop_vectors.test.mjs"],
        cwd=js, capture_output=True, text=True, timeout=180,
    )
    tail = "\n".join(r.stdout.splitlines()[-12:]) + r.stderr[-800:]
    assert r.returncode == 0, tail
    summary = {
        line.split()[1]: int(line.split()[2])
        for line in r.stdout.splitlines()
        if line.startswith("# ") and line.split()[1] in ("tests", "pass", "fail")
    }
    assert summary.get("fail", 0) == 0 and summary["pass"] == summary["tests"] >= 20, summary

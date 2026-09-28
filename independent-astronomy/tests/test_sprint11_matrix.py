"""
Sprint 11 expanded-matrix tests: the production engine, against Level A,
across the dense latitude sweep, the equinox-proximity sweep, and the
named-city matrix (incl. the new high-latitude rows).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

import compare_sprint11 as c11  # noqa: E402

WAQT_TOL_S = {"equator": 3, "tropics": 3, "mid-lat-N": 3, "mid-lat-S": 3, "high-lat": 8}


def test_named_matrix_within_tolerance_and_polar_agrees():
    vectors, max_abs, polar_failures = c11.run_named_matrix()
    assert polar_failures == []
    for band, observed in max_abs["waqt_vs_level_a"].items():
        assert observed <= WAQT_TOL_S[band], f"{band}: {observed}s"


def test_latitude_sweep_is_flat_and_small_across_0_to_80_degrees():
    rows = c11.run_latitude_sweep()
    assert len(rows) == 17
    for r in rows:
        for k in ("sunrise_waqt_vs_level_a_diff_seconds", "sunset_waqt_vs_level_a_diff_seconds"):
            assert abs(r[k]) <= 3.0, (r["lat"], k, r[k])


def test_equinox_sweep_small_in_both_directions():
    for r in c11.run_equinox_sweep():
        v = r["sunrise_waqt_vs_level_a_diff_seconds"]
        assert v is None or abs(v) <= 5.0, r


def test_committed_before_snapshot_still_documents_the_original_bug():
    """The 'before' file is the evidence for SPRINT-11-REPORT.md Sec 2;
    it must not be regenerated against the fixed engine."""
    before = json.loads((_ROOT / "vectors" / "level_a_comparison_sprint11_before.json").read_text())
    assert before["max_abs_diff_seconds_observed"]["waqt_vs_level_a"]["high-lat"] > 400
    after = json.loads((_ROOT / "vectors" / "level_a_comparison_sprint11_after.json").read_text())
    assert after["max_abs_diff_seconds_observed"]["waqt_vs_level_a"]["high-lat"] <= 8

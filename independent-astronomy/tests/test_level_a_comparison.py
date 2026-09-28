"""
tests/test_level_a_comparison.py — runs (or reloads) Sprint 10's Level-A
comparison (compare_level_a.py) and asserts every vector is within its
documented tolerance band. Mirrors test_comparison_with_waqt.py's
structure exactly, one level up (Level A vs {waqt, Level B} instead of
Level B vs waqt).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
sys.path.insert(0, str(_ROOT))

import compare_level_a  # noqa: E402


def test_regenerated_comparison_matches_committed_vectors_within_tolerance():
    report = compare_level_a.run()
    expected_rows = len(compare_level_a.LOCATIONS) * len(compare_level_a.DATES)
    assert len(report["vectors"]) == expected_rows

    failures = []
    for v in report["vectors"]:
        for ev_name, ev in v["events"].items():
            if ev.get("waqt_within_tolerance") is False:
                failures.append(("waqt", v["location"], v["date"], ev_name, ev.get("waqt_vs_level_a_diff_seconds")))
            if ev.get("level_b_within_tolerance") is False:
                failures.append(("level_b", v["location"], v["date"], ev_name, ev.get("level_b_vs_level_a_diff_seconds")))
    assert not failures, f"Out-of-tolerance disagreements against Level A: {failures}"


def test_level_b_agrees_with_level_a_much_more_tightly_than_waqt_does():
    """The headline empirical finding this sprint's Level-A comparison
    produced (see the report): independent_solar's Meeus low-accuracy
    method tracks full VSOP87 far more tightly than waqt/solar.py's NOAA
    low-precision formulas do, at every latitude band. This is a fact
    about the comparison, asserted so a future change to either engine
    that erases the gap gets noticed and discussed, not silently lost."""
    report = compare_level_a.run()
    observed = report["max_abs_diff_seconds_observed"]
    for band in compare_level_a.TOLERANCE_SECONDS_WAQT_VS_LEVEL_A:
        w = observed["waqt_vs_level_a"].get(band, 0.0)
        b = observed["level_b_vs_level_a"].get(band, 0.0)
        assert b <= w, f"{band}: expected level_b ({b}s) to track Level A at least as tightly as waqt ({w}s)"


def test_no_polar_undefined_status_disagreements():
    report = compare_level_a.run()
    assert report["polar_agreement_failures"] == []


def test_committed_vectors_file_is_up_to_date():
    vectors_path = _ROOT / "vectors" / "level_a_comparison.json"
    assert vectors_path.exists(), "run `python3 compare_level_a.py` to generate it"
    committed = json.loads(vectors_path.read_text())
    fresh = compare_level_a.run()
    assert len(committed["vectors"]) == len(fresh["vectors"])
    for c, f in zip(committed["vectors"], fresh["vectors"]):
        assert c["location"] == f["location"]
        assert c["date"] == f["date"]
        for ev_name in compare_level_a.EVENT_NAMES:
            assert c["events"][ev_name].get("level_a") == f["events"][ev_name].get("level_a")

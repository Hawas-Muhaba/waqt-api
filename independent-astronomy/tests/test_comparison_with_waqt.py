"""
test_comparison_with_waqt.py — runs (or reloads) the Parallel Milestone A
comparison and asserts every vector is within its documented tolerance
band. This is the one test file in this milestone allowed to import
`waqt` (for comparison purposes only, exactly like compare.py) --
`independent_solar/` itself still imports nothing from `waqt`
(test_no_import_of_waqt_package in test_independent_solar.py checks that
structurally).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
sys.path.insert(0, str(_ROOT))

import compare  # noqa: E402


def test_regenerated_comparison_matches_committed_vectors_within_tolerance():
    report = compare.run()
    assert len(report["vectors"]) == len(compare.LOCATIONS) * len(compare.DATES)

    failures = []
    for v in report["vectors"]:
        for ev_name, ev in v["events"].items():
            if ev["within_tolerance"] is False:
                failures.append((v["location"], v["date"], ev_name, ev["diff_seconds"]))
    assert not failures, f"Out-of-tolerance disagreements: {failures}"


def test_no_polar_undefined_status_disagreements():
    report = compare.run()
    assert report["undefined_agreement_failures"] == []


def test_committed_vectors_file_is_up_to_date():
    """The checked-in JSON should reflect what compare.py produces right
    now (both implementations are deterministic given a fixed date/location
    matrix) -- catches a stale file after either engine changes."""
    vectors_path = _ROOT / "vectors" / "independent_astronomy_comparison.json"
    assert vectors_path.exists(), "run `python3 compare.py` to generate it"
    committed = json.loads(vectors_path.read_text())
    fresh = compare.run()
    assert len(committed["vectors"]) == len(fresh["vectors"])
    for c, f in zip(committed["vectors"], fresh["vectors"]):
        assert c["location"] == f["location"]
        assert c["date"] == f["date"]
        for ev_name in compare.EVENT_NAMES:
            assert c["events"][ev_name]["waqt"] == f["events"][ev_name]["waqt"]
            assert c["events"][ev_name]["independent"] == f["events"][ev_name]["independent"]

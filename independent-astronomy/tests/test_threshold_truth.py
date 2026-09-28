"""Sprint 11: the production engine's defined/undefined status for
sunrise/sunset near the polar-day threshold matches brute-force physical
truth (not merely the Level A/B solving loops)."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT.parent))

from threshold_truth import crossing_exists  # noqa: E402
from waqt_core import solar  # noqa: E402

LON = 18.9553


def test_pinned_threshold_days_match_physics():
    cases = [
        (66.0, date(2026, 6, 12), True), (66.0, date(2026, 6, 30), False),
        (70.0, date(2026, 5, 16), True), (70.0, date(2026, 7, 27), False),
        (66.5, date(2026, 6, 6), True), (71.5, date(2026, 5, 10), True),
    ]
    for lat, d, expect in cases:
        tr = solar.transit(d, lat, LON)
        assert crossing_exists(d, lat, LON, True, tr) is expect, (lat, d)
        assert (solar.sunrise(d, lat, LON) is not None) is expect, (lat, d)


def test_grid_engine_status_equals_physical_truth():
    """Every sunrise/sunset status on a threshold-band grid equals the
    physical answer (grid kept small: each truth scan is ~80 VSOP87 evals)."""
    mismatches = []
    for lat in (64.0, 66.0, 67.5, 69.0, 71.0, 73.0):
        for k in range(0, 84, 12):
            d = date(2026, 5, 1) + timedelta(days=k)
            tr = solar.transit(d, lat, LON)
            for morning, fn in ((True, solar.sunrise), (False, solar.sunset)):
                truth = crossing_exists(d, lat, LON, morning, tr)
                if (fn(d, lat, LON) is not None) != truth:
                    mismatches.append((lat, d.isoformat(), fn.__name__, truth))
    assert mismatches == [], mismatches


def test_committed_threshold_scan_has_no_production_engine_errors():
    """The committed Sprint 11 scan (threshold_scan.py, ~18,900 event-days
    across 4 lon/season configurations in the polar-threshold band):
    wherever the three engines disagree on defined-vs-undefined for
    sunrise/sunset, the production engine matches physical truth; and every
    Asr disagreement is an ill-conditioned near-tangency (sun's midday peak
    within 0.003 deg of the Asr altitude)."""
    import json
    scan = json.loads((_ROOT / "vectors" / "threshold_scan_sprint11.json").read_text())
    total = sum(c["checked"] for c in scan["configs"].values())
    assert total > 18000
    rows = [r for c in scan["configs"].values() for r in c["disagreements"]]
    horizon = [r for r in rows if r["event"] in ("sunrise", "maghrib")]
    assert horizon and all(r["waqt_correct"] for r in horizon)
    assert not any(r["references_correct"] for r in horizon)  # refs are the ones wrong on every row
    asr = json.loads((_ROOT / "vectors" / "asr_threshold_classification_sprint11.json").read_text())["rows"]
    assert len(asr) == sum(1 for r in rows if r["event"] == "asr")
    assert all(r["ill_conditioned"] for r in asr)

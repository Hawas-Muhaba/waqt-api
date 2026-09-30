"""Sprint 13 Goal D: the JPL/Skyfield reference is independent, works, and its committed evidence holds."""
from __future__ import annotations
import ast, json, sys
from datetime import date
from pathlib import Path
import pytest

HERE = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(HERE), str(HERE.parent), str(HERE.parent / "core")]
pytest.importorskip("skyfield"); pytest.importorskip("de421")

FORBIDDEN = {"waqt", "waqt_core", "waqt_local", "independent_solar", "level_a", "pymeeus", "ephem", "astral"}

def test_reference_package_imports_nothing_from_the_things_it_checks():
    for f in (HERE / "skyfield_reference").glob("*.py"):
        for node in ast.walk(ast.parse(f.read_text())):
            mods = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) and node.level == 0 else []
            for m in mods:
                assert m.split(".")[0] not in FORBIDDEN, f"{f.name} imports {m}"

def test_reference_uses_jpl_de421_and_skyfield_not_a_series_of_our_own():
    eph = (HERE / "skyfield_reference" / "ephemeris.py").read_text()
    assert "import de421" in eph and "jplephem" in eph
    ev = (HERE / "skyfield_reference" / "events.py").read_text()
    assert ".apparent()" in ev and "gast" in ev
    for series_marker in ("nutation", "mean_longitude", "equation_of_time", "0.0167", "357.529"):
        assert series_marker not in ev and series_marker not in eph, series_marker

CASES = [(date(2026, 9, 19), 9.0192, 38.7525), (date(2019, 9, 19), 30.0444, 31.2357), (date(2026, 12, 21), -33.9249, 18.4241), (date(2019, 9, 19), 69.6492, 18.9553)]

@pytest.mark.parametrize("d,lat,lon", CASES)
def test_reference_agrees_with_level_a_and_waqt(d, lat, lon):
    from skyfield_reference import compute_day_events as sky
    from level_a.events import compute_day_events as la
    from waqt_core.solar import compute_day_events as wq
    s, a, w = sky(d, lat, lon), la(d, lat, lon), wq(d, lat, lon)
    for ev in ("fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha"):
        x, y, z = getattr(s, ev), getattr(a, ev), getattr(w, ev)
        assert (x is None) == (y is None) == (z is None), ev
        if x is None: continue
        assert abs((y - x).total_seconds()) < 0.5, (ev, "Level A vs JPL")          # observed max 0.26 s over 560 rows
        assert abs((z - x).total_seconds()) < 12.0, (ev, "Waqt vs JPL")            # observed matrix max 9.34 s

def test_polar_day_is_undefined_in_reference_too():
    from skyfield_reference import compute_day_events as sky
    r = sky(date(2026, 6, 21), 78.2232, 15.6469)
    assert r.sunrise is None and r.maghrib is None and r.fajr is None and r.isha is None and r.dhuhr is not None

# ---------------- committed evidence artifacts ----------------
V = HERE / "vectors"
def _load(n): return json.loads((V / n).read_text())

def test_sprint13_multi_year_rerun_reproduces_sprint12_exactly():
    r = _load("multi_year_comparison_sprint13.json")
    assert r["row_count"] == 560 and r["years_covered"] == [2019, 2022, 2023, 2026, 2027, 2030, 2033]
    rp = r["reproducibility_vs_sprint12"]
    assert rp["fields_differing"] == 0 and rp["fields_compared"] > 10000
    assert r["level_a_available"] is True

def test_committed_skyfield_evidence_has_the_claimed_shape():
    r = _load("skyfield_reference_sprint13.json")
    assert r["row_count"] == 560 and not r["quick"]
    for band, s in r["matrix_stats"]["level_a"]["per_band"].items():
        assert s["max_abs"] < 0.3, band                         # Level A corroborated by JPL to < 0.3 s
    assert r["polar_existence_four_way"]["disagree"] == []
    assert r["polar_existence_four_way"]["instances"] == 210
    assert {(d["location"].split()[0], d["year"]) for d in r["dense_scans"]} == {("Tromso", 2019), ("Tromso", 2026), ("Reykjavik", 2019), ("Longyearbyen", 2026)}

def test_accuracy_promotion_criterion_is_not_met_by_committed_evidence():
    """Documents WHY the label stays B: sub-10 s across the matrix fails under dense high-latitude sampling."""
    r = _load("skyfield_reference_sprint13.json")
    dense_max = max(ds["stats_all"]["max_abs"] for ds in r["dense_scans"])
    assert dense_max > 10.0, "if this starts failing, the accuracy-level review (docs/ACCURACY-LEVEL-REVIEW.md) must be reopened"
    from waqt_core.versioning import ACCURACY_LEVEL
    assert ACCURACY_LEVEL == "B"

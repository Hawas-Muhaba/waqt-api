"""
Sprint 6 conformance: tests/vectors/scheduling_vectors.json.

Three separate guarantees, in increasing order of importance:

1. REGRESSION   every vector re-derives, exactly, through the live
                Python engine (behaviour has not drifted from the file).
2. COMPLETENESS every day the engine touches is in the vector's own day
                table — so the file really is reproducible from its data.
3. INDEPENDENCE the JavaScript consumer in consumers/js — which shares no
                code with this package and computes no astronomy —
                reproduces every vector and every Sprint 5 vector too.
                This is the sprint's acceptance criterion; it is run
                from here so a Python-only CI still exercises it.

Sprint 11 conformance: driven directly against `waqt_core` (not `waqt`, not the local library) so this suite proves the extracted package alone reproduces the same publicly committed vectors every other suite in this repository uses — with only waqt-core installed, no FastAPI, no `waqt`.
"""

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from waqt_core.calendar_providers import UmmAlQuraProvider
from waqt_core.calendar_providers.registry import ExampleRegionalOffsetProvider
from waqt_core.core import AstronomyProfile, Location
from waqt_core.hijri import ArithmeticTabularProvider
from waqt_core.scheduling import SchedulingContext, SchedulingEngine, run_operation

ROOT = Path(__file__).resolve().parents[2]  # core/tests/file.py -> repo root
VECTORS = json.loads((ROOT / "tests" / "vectors" / "scheduling_vectors.json").read_text())["vectors"]


def _provider(name):
    base = ArithmeticTabularProvider()
    return {"arithmetic-tabular": base, "umm-al-qura": UmmAlQuraProvider(),
            "example-regional-offset": ExampleRegionalOffsetProvider(wrapped=base, day_offset=1)}[name]


def _engine(v):
    c = v["context"]
    p = c["astronomy_profile"]
    ctx = SchedulingContext(
        Location(c["location"]["lat"], c["location"]["lon"]),
        AstronomyProfile(fajr_angle_deg=p["fajr_angle_deg"], isha_angle_deg=p["isha_angle_deg"], asr_shadow_ratio=p["asr_shadow_ratio"]),
        _provider(c["calendar_provider"]),
    )
    return ctx, SchedulingEngine(ctx)


@pytest.mark.parametrize("v", VECTORS, ids=[v["id"] for v in VECTORS])
def test_vector_reproduces_exactly_through_the_live_engine(v):
    ctx, eng = _engine(v)
    anchor = datetime.fromisoformat(v["anchor"])
    assert run_operation(eng, anchor, v["operation"]) == v["expected"]
    opens = {d["open"] for d in v["context"]["days"] if d["open"]}
    for day in ctx.known_days():
        assert day.open.isoformat() in opens, "engine used a day that is not in the vector's own table"


def test_vector_file_shape_and_coverage():
    assert len(VECTORS) >= 100
    assert len({v["id"] for v in VECTORS}) == len(VECTORS), "vector ids must be unique"
    groups = {v["group"] for v in VECTORS}
    assert groups >= {"points", "windows", "evaluate", "deadlines", "until-since", "positions", "spans", "undefined",
                      "profile-asr", "calendar-substitution"}
    statuses = {v["expected"]["status"] for v in VECTORS}
    assert statuses >= {"OK", "EVENT_UNDEFINED", "WINDOW_UNDEFINED", "NO_VALID_WINDOW"}
    ops = {v["operation"]["op"] for v in VECTORS}
    assert ops >= {"resolve_point", "resolve_interval", "evaluate", "check_deadline", "until", "since", "next_event",
                   "event_position", "day_bounds", "classify_span"}


def test_the_day_tables_carry_no_hidden_calendar_input():
    """The calendar-substitution vectors share a table in everything but the label."""
    g = {v["id"]: v for v in VECTORS if v["group"] == "calendar-substitution"}
    tables = [v["context"]["days"] for k, v in g.items() if k.endswith("-window")]
    assert len(tables) == 3

    def strip(days):
        return [{k: val for k, val in d.items() if k != "hijri_label"} for d in days]

    assert strip(tables[0]) == strip(tables[1]) == strip(tables[2])
    assert {d["hijri_label"] for t in tables for d in t} and tables[0][3]["hijri_label"] != tables[2][3]["hijri_label"]


NODE = shutil.which("node")


@pytest.mark.skipif(NODE is None, reason="Node.js not installed; the independent JS consumer cannot run here")
def test_independent_javascript_consumer_validates_all_vectors():
    """Sprint 6 acceptance criterion: a non-Python implementation that shares no
    code with the reference validates the Sprint 5 vectors AND the Sprint 6 vectors."""
    js = ROOT / "consumers" / "js"
    r = subprocess.run(
        [NODE, "--test", "test/waqt_vectors.test.mjs", "test/scheduling_vectors.test.mjs"],
        cwd=js, capture_output=True, text=True, timeout=180,
    )
    tail = "\n".join(r.stdout.splitlines()[-12:]) + r.stderr[-800:]
    assert r.returncode == 0, tail
    summary = {line.split()[1]: int(line.split()[2]) for line in r.stdout.splitlines() if line.startswith("# ") and line.split()[1] in ("tests", "pass", "fail")}
    assert summary["fail"] == 0 and summary["pass"] == summary["tests"] >= 130, summary

"""
waqt_local conformance — tests/vectors/scheduling_vectors.json, driven
through `waqt_local.schedule_resolve` (the local equivalent of
`POST /v1/schedule/resolve`), not through the engine directly. Mirrors
the shape of `tests/test_scheduling_vectors.py` at the repo root.

`example-regional-offset` vectors are excluded: like the HTTP API's own
`resolve_calendar_provider`, `waqt_local.providers.resolve_calendar_provider`
only resolves the four catalog providers (`docs/API.md`'s
`GET /v1/calendar` list) — `example-regional-offset` is a
scheduling-test-only provider that was never reachable from the HTTP
API either (see waqt/api/schedule_endpoint.py / waqt/api/providers.py).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import waqt_local

REPO_ROOT = Path(__file__).resolve().parents[2]
ALL_VECTORS = json.loads((REPO_ROOT / "tests" / "vectors" / "scheduling_vectors.json").read_text())["vectors"]
VECTORS = [v for v in ALL_VECTORS if v["context"]["calendar_provider"] in ("arithmetic-tabular", "umm-al-qura")]

assert len(VECTORS) >= 100, "expected the bulk of scheduling_vectors.json to be catalog-provider vectors"


def _body(v):
    c = v["context"]
    p = c["astronomy_profile"]
    return {
        "location": {"lat": c["location"]["lat"], "lon": c["location"]["lon"]},
        "anchor": v["anchor"],
        "operation": v["operation"],
        "profile": {
            "fajr_angle_deg": p["fajr_angle_deg"],
            "isha_angle_deg": p["isha_angle_deg"],
            "asr_shadow_ratio": p["asr_shadow_ratio"],
        },
        "calendar_provider": c["calendar_provider"],
        "precision": "microsecond",
    }


@pytest.mark.parametrize("v", VECTORS, ids=[v["id"] for v in VECTORS])
def test_local_schedule_resolve_reproduces_scheduling_vectors(v):
    r = waqt_local.schedule_resolve(_body(v))
    assert r["result"] == v["expected"], v["id"]


def test_at_least_one_vector_per_operation_kind_covered():
    ops = {v["operation"]["op"] for v in VECTORS}
    assert ops >= {"resolve_point", "resolve_interval", "evaluate", "check_deadline", "until", "since",
                   "next_event", "event_position", "day_bounds", "classify_span"}

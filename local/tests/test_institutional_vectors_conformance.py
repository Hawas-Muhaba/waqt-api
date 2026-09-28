"""
waqt_local conformance — the `fiscal_year`/`academic_year` groups of
tests/vectors/institutional_vectors.json, driven through
`waqt_local.institutional_fiscal_year_resolve` /
`institutional_academic_year_resolve` — the local equivalents of the
two institutional `POST .../resolve` endpoints — rather than by
constructing `FiscalCalendar`/`AcademicCalendar` directly.

The `rules` and `week` vector groups are pure calendar-rule / week-date
arithmetic with no HTTP or local-library endpoint of their own (see
waqt/institutional/rules.py, waqt/institutional/week.py); they stay
covered by the existing `tests/test_institutional_vectors.py` at the
repo root and are not duplicated here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import waqt_local

REPO_ROOT = Path(__file__).resolve().parents[2]
VECTORS = json.loads((REPO_ROOT / "tests" / "vectors" / "institutional_vectors.json").read_text())["vectors"]

FISCAL = [v for v in VECTORS if v["group"] == "fiscal_year"]
ACADEMIC = [v for v in VECTORS if v["group"] == "academic_year"]

assert FISCAL and ACADEMIC


@pytest.mark.parametrize("v", FISCAL, ids=[v["id"] for v in FISCAL])
def test_local_fiscal_year_resolve_reproduces_vectors(v):
    op = v["operation"]
    body = {
        "hijri_year": op["year"],
        "start_rule": op["start_rule"],
        "end_rule": op["end_rule"],
        "calendar_provider": v["context"]["calendar_provider"],
    }
    r = waqt_local.institutional_fiscal_year_resolve(body)
    assert r["start"] == v["expected"]["start"], v["id"]
    assert r["end"] == v["expected"]["end"], v["id"]


@pytest.mark.parametrize("v", ACADEMIC, ids=[v["id"] for v in ACADEMIC])
def test_local_academic_year_resolve_reproduces_vectors(v):
    op = v["operation"]
    body = {
        "hijri_year": op["year"],
        "opening_rule": op["opening_rule"],
        "closing_rule": op["closing_rule"],
        "term_rules": op.get("term_rules", []),
        "calendar_provider": v["context"]["calendar_provider"],
    }
    r = waqt_local.institutional_academic_year_resolve(body)
    assert r["opening"] == v["expected"]["opening"], v["id"]
    assert r["closing"] == v["expected"]["closing"], v["id"]
    got_terms = [{"label": t["label"], "start": t["start"], "end": t["end"]} for t in r["terms"]]
    assert got_terms == v["expected"]["terms"], v["id"]

"""
Sprint 12 Goal B/D — the computation revision must be *honest*.

A revision label that a human has to remember to bump will be forgotten.
These tests make the label mechanically follow behaviour:

  * the pinned fingerprint of the engine's output must match the current
    revision's entry, so changing solar.py/timescale.py output without
    bumping the revision (and recording it) fails here;
  * the fingerprint must actually be sensitive to the kind of change that
    motivated the revision (Sprint 11's epoch bugs) — otherwise the test
    above would be decoration;
  * every committed vector file records the revision it was generated
    under and it must equal the engine's, so an engine bump forces
    regeneration;
  * the Level-A relabel decision stays an explicit, reviewed act.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from waqt_core import solar, versioning
from waqt_core.versioning import (
    ACCURACY_LEVEL,
    ENGINE_NAME,
    ENGINE_REVISION,
    ENGINE_REVISIONS,
    VECTOR_SET_VERSION,
    computation_identity,
    engine_fingerprint,
    version_report,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
VECTOR_DIR = REPO_ROOT / "tests" / "vectors"
SDK_VECTORS = REPO_ROOT / "sdks" / "vectors" / "sdk_conformance_vectors.json"


# --- identity ------------------------------------------------------------

def test_identity_has_exactly_the_reproducibility_triple():
    assert computation_identity() == {
        "engine": ENGINE_NAME,
        "revision": ENGINE_REVISION,
        "accuracy_level": ACCURACY_LEVEL,
    }


def test_revision_is_a_nonempty_string_not_a_number():
    # Labels are compared for equality; arithmetic on them is a bug.
    assert isinstance(ENGINE_REVISION, str) and ENGINE_REVISION


def test_identity_returns_a_fresh_dict_each_time():
    a = computation_identity()
    a["revision"] = "tampered"
    assert computation_identity()["revision"] == ENGINE_REVISION


# --- history -------------------------------------------------------------

def test_current_revision_is_in_history_and_is_the_only_one_with_a_fingerprint():
    assert ENGINE_REVISION in ENGINE_REVISIONS
    pinned = [r for r, info in ENGINE_REVISIONS.items() if info["fingerprint"] is not None]
    assert pinned == [ENGINE_REVISION], (
        "only the current revision can carry a fingerprint: older behaviours are not "
        "reproducible from this tree, and an unrecomputable hash would be decoration"
    )


def test_history_documents_every_revision():
    for rev, info in ENGINE_REVISIONS.items():
        for key in ("introduced", "core_versions", "summary", "retroactive"):
            assert key in info, (rev, key)
        assert info["summary"].strip()


def test_revision_one_is_marked_retroactive():
    # Responses from Sprint <= 10 carry no revision field; "1" names them after the fact.
    assert ENGINE_REVISIONS["1"]["retroactive"] is True
    assert ENGINE_REVISIONS[ENGINE_REVISION]["retroactive"] is False


# --- fingerprint: pinned, deterministic, sensitive -----------------------

def test_fingerprint_matches_pinned_value_for_current_revision():
    assert engine_fingerprint() == ENGINE_REVISIONS[ENGINE_REVISION]["fingerprint"], (
        "The solar engine's output changed but ENGINE_REVISION did not. If the change is "
        "intended: bump ENGINE_REVISION, add its ENGINE_REVISIONS entry with the measured "
        "effect, pin the new fingerprint, bump VECTOR_SET_VERSION's MAJOR, regenerate the "
        "vectors (never hand-edit), and update docs/VERSIONING.md."
    )


def test_fingerprint_is_deterministic():
    assert engine_fingerprint() == engine_fingerprint()


def test_fingerprint_detects_a_sprint11_style_epoch_error(monkeypatch):
    """Re-introduce the *kind* of bug that prompted this mechanism: sample the
    sun 12 h from the instant being solved. The hash must move."""
    real = solar._params_at_instant

    def half_day_off(d, instant, timescale):
        from datetime import timedelta

        return real(d, instant + timedelta(hours=12), timescale)

    monkeypatch.setattr(solar, "_params_at_instant", half_day_off)
    assert engine_fingerprint() != ENGINE_REVISIONS[ENGINE_REVISION]["fingerprint"]


def test_fingerprint_detects_a_small_but_real_change(monkeypatch):
    """A 0.02-degree shift in hour angle is ~5 s at the equator: far smaller than
    Sprint 11's changes but far larger than the 10 ms bucket."""
    real = solar._hour_angle_for_altitude

    def shifted(lat, declin, altitude_deg):
        h = real(lat, declin, altitude_deg)
        return None if h is None else h + 0.02

    monkeypatch.setattr(solar, "_hour_angle_for_altitude", shifted)
    assert engine_fingerprint() != ENGINE_REVISIONS[ENGINE_REVISION]["fingerprint"]


def test_fingerprint_is_insensitive_below_its_resolution(monkeypatch):
    """...and it must NOT flip for a sub-millisecond perturbation, or a different
    libm would spuriously fail the pin on another platform."""
    real = solar._hour_angle_for_altitude

    def nudged(lat, declin, altitude_deg):
        h = real(lat, declin, altitude_deg)
        return None if h is None else h + 1e-12   # ~4e-9 s

    monkeypatch.setattr(solar, "_hour_angle_for_altitude", nudged)
    assert engine_fingerprint() == ENGINE_REVISIONS[ENGINE_REVISION]["fingerprint"]


# --- the accuracy-level label is a review point, not a drifting constant --

def test_accuracy_level_is_still_B_pending_the_documented_review():
    """DELIBERATE PIN. Sprint 12 left the label at "B" on purpose (one VSOP87
    reference + a shared-series Level B; Level-A evidence across other years and an
    independent second reference is not yet in). To change it you must edit this
    test in the same commit, which is the point: the change becomes a visible,
    reviewed decision. Criteria: docs/ACCURACY-LEVEL-REVIEW.md."""
    assert ACCURACY_LEVEL == "B"


def test_review_document_exists_and_lists_criteria():
    doc = REPO_ROOT / "docs" / "ACCURACY-LEVEL-REVIEW.md"
    if not doc.exists():
        pytest.skip("docs/ not present (running outside a full checkout)")
    text = doc.read_text()
    assert "Promotion criteria" in text
    assert "Decision record" in text


# --- version report -------------------------------------------------------

def test_version_report_carries_every_axis_it_owns():
    r = version_report(api_version="9.9.9", spec_version="spec/x", local_version="7.7.7")
    assert r["waqt_core_version"] == versioning.CORE_VERSION
    assert r["api_version"] == "9.9.9" and r["spec"] == "spec/x" and r["waqt_local_version"] == "7.7.7"
    assert r["computation"] == computation_identity()
    assert r["conformance_vectors"] == {
        "vector_set_version": VECTOR_SET_VERSION,
        "generated_at_engine_revision": ENGINE_REVISION,
    }
    assert ENGINE_REVISION in r["engine_revision_history"]


def test_version_report_never_leaks_fingerprints_and_does_not_invent_layers():
    r = version_report()
    assert r["api_version"] is None and r["waqt_local_version"] is None and r["spec"] is None
    assert "fingerprint" not in json.dumps(r["engine_revision_history"])


def test_version_report_is_json_serialisable():
    json.dumps(version_report(api_version="1.4.0"))


# --- vectors carry the revision they were generated under -----------------

def _vector_files():
    return sorted(VECTOR_DIR.glob("*_vectors.json")) + [SDK_VECTORS]


@pytest.mark.parametrize("path", _vector_files(), ids=lambda p: p.name)
def test_every_vector_file_is_stamped_and_current(path):
    doc = json.loads(path.read_text())
    assert doc["vector_set_version"] == VECTOR_SET_VERSION, path.name
    assert isinstance(doc["astronomy_dependent"], bool)
    gen = doc["generated_at_computation"]
    if doc["astronomy_dependent"]:
        assert gen == computation_identity(), (
            f"{path.name} was generated at {gen} but the engine is {computation_identity()}. "
            "Regenerate it (tests/vectors/generate_*.py) and review the diff."
        )
    else:
        assert gen is None


def test_only_the_institutional_vectors_are_engine_independent():
    dep = {p.name: json.loads(p.read_text())["astronomy_dependent"] for p in _vector_files()}
    assert [n for n, v in dep.items() if not v] == ["institutional_vectors.json"]


def test_sdk_vectors_computation_blocks_have_the_reproducibility_triple():
    doc = json.loads(SDK_VECTORS.read_text())
    found = 0

    def walk(node):
        nonlocal found
        if isinstance(node, dict):
            if "timescale_model" in node and "accuracy_level" in node:
                found += 1
                assert node["engine"] == ENGINE_NAME
                assert node["revision"] == ENGINE_REVISION
                assert node["accuracy_level"] == ACCURACY_LEVEL
                assert node["astronomy_engine"] == node["engine"]   # alias must never diverge
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(doc)
    assert found >= 5, "expected several recorded computation blocks"

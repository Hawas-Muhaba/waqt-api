"""Sprint 15 -- run the portable conformance suite from the normal test tree.

* `test_independent_implementation_conforms`  : the clean-room Node implementation must have ZERO normative
  failures (and its own unit tests must pass).
* `test_reference_failures_are_exactly_the_known_ones` : the reference's normative failures must equal the
  documented baseline (conformance/baselines/known-failures.json, each explained in conformance/DISAGREEMENTS.md).
  A NEW failure fails the test (regression).  A baseline entry that now passes also fails the test, with the
  message "update the baseline" -- so fixing a defect is a visible, deliberate event.

Both are marked `slow` (about 3-5 minutes on one core: they drive the DE421 oracle-derived vectors through two
adapters) and need `node` >= 20.  Run with:  WAQT_RUN_CONFORMANCE=1 pytest tests/test_conformance_suite.py
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONF = ROOT / "conformance"
pytestmark = [pytest.mark.slow,
              pytest.mark.skipif(shutil.which("node") is None, reason="node >= 20 required for the independent implementation"),
              pytest.mark.skipif(os.environ.get("WAQT_RUN_CONFORMANCE") != "1", reason="set WAQT_RUN_CONFORMANCE=1 (takes several minutes)")]


def _run(adapters, name):
    cmd = [sys.executable, str(CONF / "harness" / "waqt_conform.py"), "--out", str(CONF / "reports" / "_pytest"), "--name", name]
    for label, a in adapters:
        cmd += ["--adapter", a, "--label", label]
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=str(CONF), timeout=1700)
    assert p.returncode == 0, p.stderr[-2000:]
    return json.loads((CONF / "reports" / "_pytest" / f"{name}.json").read_text())["runs"]


def _failures(run):
    v = [x["id"] for x in run["vectors"] if x["verdict"] == "FAIL" and x["tier"] in ("exact", "tolerance")]
    m = [x["id"] for x in run["metamorphic"] if x["verdict"] == "FAIL"]
    return sorted(v), sorted(m)


def test_independent_implementation_unit_tests():
    p = subprocess.run(["node", "--test", "test/independent.test.mjs"], capture_output=True, text=True, cwd=str(CONF / "independent"), timeout=600)
    assert p.returncode == 0, p.stdout[-2000:] + p.stderr[-500:]


def test_independent_implementation_conforms_and_reference_failures_are_the_known_ones():
    runs = _run([("reference", f"{sys.executable} adapters/reference_adapter.py"), ("independent", "node independent/src/cli.mjs")], "pytest-run")
    by = {r["label"]: r for r in runs}
    # 1. clean-room implementation: no normative failure at all
    iv, im = _failures(by["independent"])
    assert not iv and not im, f"independent implementation fails normative vectors: {iv[:5]} {im[:5]}"
    # 2. reference: exactly the documented set
    base = json.loads((CONF / "baselines" / "known-failures.json").read_text())["reference"]
    rv, rm = _failures(by["reference"])
    new = sorted((set(rv) - set(base["vectors"])) | (set(rm) - set(base["metamorphic"])))
    fixed = sorted((set(base["vectors"]) - set(rv)) | (set(base["metamorphic"]) - set(rm)))
    assert not new, f"NEW reference conformance failures (regression): {new[:10]}"
    assert not fixed, f"known failures now PASS -- update conformance/baselines/known-failures.json and DISAGREEMENTS.md: {fixed[:10]}"
    # 3. the reports must exist and name every requirement
    assert (CONF / "reports" / "_pytest" / "pytest-run.md").read_text().count("| CAL-") >= 10

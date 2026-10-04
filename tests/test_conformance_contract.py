"""Sprint 16 - the conformance contract's own process guards (conformance/GOVERNANCE.md, VERSIONING.md).

These do not test the product; they test that the contract cannot drift silently:
  * the manifest matches the files, every cross-reference resolves (`tools/contract.py verify`);
  * unresolved questions stay visible and cannot be dropped unnoticed;
  * the reference baseline is empty (every future entry needs a DIS id and decision record);
  * the 1.0.0 -> 2.0.0 migration is idempotent;
  * editing a vector without bumping the version is detected.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

CONF = Path(__file__).resolve().parent.parent / "conformance"


def _run(script, *args, cwd=None):
    return subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True, cwd=str(cwd or CONF), timeout=300)


def test_contract_verify_reports_no_problem():
    p = _run(CONF / "tools" / "contract.py", "verify")
    assert p.returncode == 0, p.stdout + p.stderr
    assert "contract verify: ok" in p.stdout


def test_unresolved_questions_are_always_visible():
    reg = json.loads((CONF / "spec" / "open-questions.json").read_text(encoding="utf-8"))["questions"]
    by = {q["id"]: q for q in reg}
    # Questions that are religious/institutional or not yet decided must still be listed, not quietly resolved.
    assert by["OQ-UAQ-2"]["status"] == "unresolved-by-design"
    for qid in ("OQ-TAB-3", "OQ-TIME-1", "OQ-DT-1", "OQ-UND-1", "OQ-ERR-1"):
        assert by[qid]["status"] == "deferred", qid
    assert len(reg) == 28 and sum(q["status"] != "resolved" for q in reg) == 12


def test_every_resolved_question_has_a_decision_record_and_every_record_is_indexed():
    reg = json.loads((CONF / "spec" / "open-questions.json").read_text(encoding="utf-8"))["questions"]
    for q in reg:
        if q["status"] == "resolved":
            assert (CONF / "decisions" / f"{q['decision']}.md").exists(), q["id"]
    index = (CONF / "decisions" / "README.md").read_text(encoding="utf-8")
    for rec in sorted((CONF / "decisions").glob("DR-*.md")):
        assert rec.stem in index, rec.name


def test_reference_baseline_is_empty_and_names_the_contract():
    kf = json.loads((CONF / "baselines" / "known-failures.json").read_text(encoding="utf-8"))
    assert kf["contract_version"] == "2.0.0"
    assert kf["reference"] == {"vectors": [], "metamorphic": []} and kf["independent"] == []


def test_the_umm_al_qura_conventions_vectors_are_not_promoted_to_normative():
    # GOVERNANCE.md section 5: do not force consensus on an institutional convention to get a cleaner report.
    d = json.loads((CONF / "vectors" / "calendar-uaq.json").read_text(encoding="utf-8"))
    tiers = {v["id"]: v["tier"] for v in d["vectors"]}
    assert all(t == "informative" for i, t in tiers.items() if i.startswith("uaq/year-table") or i.startswith("uaq/range/1700") or i.startswith("uaq/range/2300"))
    req = {r["id"]: r for r in json.loads((CONF / "spec" / "requirements.json").read_text(encoding="utf-8"))["requirements"]}
    assert req["CAL-007"]["kind"] == "OPEN"


def test_migration_is_idempotent():
    p = _run(CONF / "tools" / "migrate_contract_2_0.py", "--check")
    assert p.returncode == 0, p.stdout + p.stderr


def test_editing_a_vector_without_bumping_the_version_is_detected(tmp_path):
    work = tmp_path / "conformance"
    for name in ("spec", "vectors", "baselines", "decisions", "tools"):
        shutil.copytree(CONF / name, work / name)
    for name in ("CHANGELOG.md", "contract.json"):
        shutil.copy(CONF / name, work / name)
    assert _run(work / "tools" / "contract.py", "verify", cwd=work).returncode == 0
    vp = work / "vectors" / "errors.json"
    d = json.loads(vp.read_text(encoding="utf-8"))
    d["vectors"][0]["note"] = (d["vectors"][0].get("note") or "") + " tampered"
    vp.write_text(json.dumps(d, indent=1), encoding="utf-8")
    p = _run(work / "tools" / "contract.py", "verify", cwd=work)
    assert p.returncode == 1 and "contract.json is stale" in p.stdout


def test_a_released_contract_is_immutable(tmp_path):
    work = tmp_path / "conformance"
    for name in ("spec", "vectors", "baselines", "decisions", "tools"):
        shutil.copytree(CONF / name, work / name)
    for name in ("CHANGELOG.md",):
        shutil.copy(CONF / name, work / name)
    assert _run(work / "tools" / "contract.py", "build", "--release", cwd=work).returncode == 0
    vp = work / "vectors" / "errors.json"
    d = json.loads(vp.read_text(encoding="utf-8"))
    d["vectors"][0]["note"] = "changed after release"
    vp.write_text(json.dumps(d, indent=1), encoding="utf-8")
    assert _run(work / "tools" / "contract.py", "build", cwd=work).returncode == 0  # a draft rebuild is allowed...
    p = _run(work / "tools" / "contract.py", "verify", cwd=work)
    assert p.returncode == 1 and "was modified: bump the version" in p.stdout  # ...but the released copy is not

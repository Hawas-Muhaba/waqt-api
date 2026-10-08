"""Conformance-document drift guards (audit findings: stale requirement count; ERR-004 MUST without a normative vector)."""
import json
import subprocess
import sys
from pathlib import Path

CONF = Path(__file__).resolve().parent.parent / "conformance"


def test_conformance_md_requirement_count_is_generated_and_current():
    p = subprocess.run([sys.executable, str(CONF / "tools" / "sync_doc_counts.py"), "--check"], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    n = len(json.loads((CONF / "spec" / "requirements.json").read_text(encoding="utf-8"))["requirements"])
    assert f"{n} requirement IDs" in (CONF / "spec" / "CONFORMANCE.md").read_text(encoding="utf-8")


def test_err004_gap_is_explicitly_tracked_not_hidden_or_weakened():
    """ERR-004 stays MUST/normative (the contract is NOT weakened). Its missing normative vector is tracked by an open
    question; if a normative vector is added later this test fails, prompting removal of the tracking entry."""
    reqs = {r["id"]: r for r in json.loads((CONF / "spec" / "requirements.json").read_text(encoding="utf-8"))["requirements"]}
    assert reqs["ERR-004"]["kind"] == "MUST" and reqs["ERR-004"]["status"] == "normative"
    questions = json.loads((CONF / "spec" / "open-questions.json").read_text(encoding="utf-8"))["questions"]
    tracking = [q for q in questions if "ERR-004" in q["topic"] and q["status"] != "resolved"]
    assert tracking, "ERR-004 has no normative vector and must be tracked by an unresolved question"
    normative = 0
    for f in (CONF / "vectors").glob("*.json"):
        doc = json.loads(f.read_text(encoding="utf-8"))
        for v in doc.get("vectors", []):
            if "ERR-004" in v.get("requirements", []) and v.get("tier", doc.get("tier")) in ("exact", "tolerance"):
                normative += 1
    assert normative == 0, "ERR-004 now has normative vectors: close the tracking question and update this test"

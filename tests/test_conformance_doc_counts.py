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


def test_err004_is_normative_with_explicit_ranges_and_exact_vectors():
    """DR-0011 closed the ERR-004 gap: MUST, normative, ranges stated in the title, no unresolved tracking question, and normative
    vectors for the valid boundaries, the invalid boundaries, zero, negatives, NaN, infinity and non-numeric input."""
    reqs = {r["id"]: r for r in json.loads((CONF / "spec" / "requirements.json").read_text(encoding="utf-8"))["requirements"]}
    assert reqs["ERR-004"]["kind"] == "MUST" and reqs["ERR-004"]["status"] == "normative" and reqs["ERR-004"]["decision"] == "DR-0011"
    assert "0 < value <= 90" in reqs["ERR-004"]["title"] and "NaN" in reqs["ERR-004"]["title"]
    questions = json.loads((CONF / "spec" / "open-questions.json").read_text(encoding="utf-8"))["questions"]
    assert not [q for q in questions if "ERR-004" in q["topic"] and q["status"] != "resolved"]
    ids = set()
    for f in (CONF / "vectors").glob("*.json"):
        doc = json.loads(f.read_text(encoding="utf-8"))
        for v in doc.get("vectors", []):
            if "ERR-004" in v.get("requirements", []) and v.get("tier", doc.get("tier")) in ("exact", "tolerance"):
                ids.add(v["id"])
    for needle in ("fajr-95", "fajr-90.0001", "fajr-zero", "fajr-negative", "fajr-nan", "fajr-infinity", "fajr-neg-infinity", "fajr-non-numeric-string",
                   "isha-zero", "isha-90.0001", "isha-nan", "asr-zero", "asr-negative", "asr-nan", "asr-infinity", "asr-non-numeric-string",
                   "profile-valid/fajr-90", "profile-valid/isha-90", "profile-valid/asr-0.0001", "profile-valid/fajr-0.0001"):
        assert any(needle in i for i in ids), needle
    assert len(ids) >= 30

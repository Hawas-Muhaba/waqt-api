#!/usr/bin/env python3
"""Build and verify the versioned conformance-contract manifest (conformance/VERSIONING.md).

    python3 tools/contract.py build             # write contract.json (a DRAFT: "released": false)
    python3 tools/contract.py build --release   # also write the immutable releases/contract-<version>.json
    python3 tools/contract.py verify            # exit 1 on any problem; warnings never fail
    python3 tools/contract.py show              # one-line summary (used by the harness report)

Standard library only. The contract hash covers requirements, vectors, the unresolved-question registry and the
COP; it deliberately does NOT cover baselines/known-failures.json (status, not contract), which is hashed
separately so a report can show both. Manifest paths use POSIX separators and text hashes normalize line endings so
Windows and POSIX checkouts compute the same contract.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

CONF = Path(__file__).resolve().parent.parent
REQ = CONF / "spec" / "requirements.json"
REG = CONF / "spec" / "open-questions.json"
COP = CONF / "spec" / "COP.md"
KNOWN = CONF / "baselines" / "known-failures.json"
MANIFEST = CONF / "contract.json"
RELEASES = CONF / "releases"
NORMATIVE_TIERS = ("exact", "tolerance")
STATUSES = ("resolved", "deferred", "unresolved-by-design")


def sha256(p: Path) -> str:
    # Contract files are text; normalize checkout line endings for stable hashes on Windows and POSIX.
    content = p.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(content).hexdigest()


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def contract_files() -> list[Path]:
    return [REQ, REG, COP] + sorted((CONF / "vectors").glob("*.json"))


def _entries(doc):
    return list(doc.get("vectors", [])) + list(doc.get("metamorphic", []))


def compute() -> dict:
    req = load(REQ)
    files = {}
    for p in contract_files():
        rel = p.relative_to(CONF).as_posix()
        info = {"sha256": sha256(p)}
        if p.parent.name == "vectors":
            d = load(p)
            tiers: dict[str, int] = {}
            for v in d.get("vectors", []):
                t = v.get("tier", d.get("tier", "?"))
                tiers[t] = tiers.get(t, 0) + 1
            info["vectors"] = len(d.get("vectors", []))
            info["metamorphic"] = len(d.get("metamorphic", []))
            info["tiers"] = tiers
        files[rel] = info
    h = hashlib.sha256()
    for rel in sorted(files):
        h.update(f"{rel}:{files[rel]['sha256']}\n".encode())
    reg = load(REG)
    counts = {s: sum(1 for q in reg["questions"] if q["status"] == s) for s in STATUSES}
    kf = load(KNOWN) if KNOWN.exists() else {}
    return {
        "contract_version": req["contract_version"],
        "cop_version": req["cop_version"],
        "contract_sha256": h.hexdigest(),
        "files": files,
        "requirements": {
            "total": len(req["requirements"]),
            "must": sum(1 for r in req["requirements"] if r["kind"] == "MUST"),
            "open": sum(1 for r in req["requirements"] if r["kind"] != "MUST"),
        },
        "questions": {"total": len(reg["questions"]), **counts},
        "status": {
            "known_failures_sha256": sha256(KNOWN) if KNOWN.exists() else None,
            "reference_known_failures": len(kf.get("reference", {}).get("vectors", [])),
            "independent_known_failures": len(kf.get("independent", [])),
        },
    }


def unenforced_musts() -> list[str]:
    """MUST requirements with no vector in an exact/tolerance tier: declared but not enforced. Never hidden."""
    req = load(REQ)
    enforced: set[str] = set()
    for p in sorted((CONF / "vectors").glob("*.json")):
        d = load(p)
        for v in d.get("vectors", []):
            if v.get("tier", d.get("tier")) in NORMATIVE_TIERS:
                enforced.update(v.get("requirements", []))
        for m in d.get("metamorphic", []):
            enforced.update(m.get("requirements", []))
    return sorted(r["id"] for r in req["requirements"] if r["kind"] == "MUST" and r["id"] not in enforced)


def verify() -> tuple[list[str], list[str]]:
    problems: list[str] = []
    warnings: list[str] = []
    req = load(REQ)
    ids = {r["id"] for r in req["requirements"]}
    version = req["contract_version"]
    if len(ids) != len(req["requirements"]):
        problems.append("duplicate requirement ids")
    # 1. vector -> requirement references
    for p in sorted((CONF / "vectors").glob("*.json")):
        d = load(p)
        for v in _entries(d):
            for r in v.get("requirements", []):
                if r not in ids:
                    problems.append(f"{p.name}: {v.get('id')} cites unknown requirement {r}")
    # 2. decision records exist
    for r in req["requirements"]:
        dec = r.get("decision", "")
        for m in re.findall(r"DR-\d{4}", dec):
            if not (CONF / "decisions" / f"{m}.md").exists():
                problems.append(f"{r['id']} cites missing decision record {m}")
    reg = load(REG)
    for q in reg["questions"]:
        if q["status"] not in STATUSES:
            problems.append(f"{q['id']}: invalid status {q['status']!r}")
        if q["status"] == "resolved":
            m = re.findall(r"DR-\d{4}", q.get("decision") or "")
            if not m or not all((CONF / "decisions" / f"{x}.md").exists() for x in m):
                problems.append(f"{q['id']}: resolved without an existing decision record")
        if q.get("requirement") and q["requirement"] not in ids:
            problems.append(f"{q['id']}: unknown requirement {q['requirement']}")
    # 3. changelog, COP version, known-failures naming
    cl = (CONF / "CHANGELOG.md").read_text(encoding="utf-8")
    if not re.search(r"^## " + re.escape(version) + r"\b", cl, re.M):
        problems.append(f"CHANGELOG.md has no entry for {version}")
    m = re.search(r"COP\) v([\d.]+)", COP.read_text(encoding="utf-8"))
    if not m or m.group(1) != req["cop_version"]:
        problems.append(f"COP.md version {m.group(1) if m else '?'} != requirements.json cop_version {req['cop_version']}")
    if KNOWN.exists() and load(KNOWN).get("contract_version") != version:
        problems.append("known-failures.json does not name the current contract version")
    # 4. manifest matches files; a released version is immutable
    cur = compute()
    if MANIFEST.exists():
        man = load(MANIFEST)
        if man.get("contract_sha256") != cur["contract_sha256"] or man.get("contract_version") != version:
            problems.append("contract.json is stale: run `python3 tools/contract.py build`")
    else:
        problems.append("contract.json is missing: run `python3 tools/contract.py build`")
    rel = RELEASES / f"contract-{version}.json"
    if rel.exists() and load(rel).get("contract_sha256") != cur["contract_sha256"]:
        problems.append(f"released contract {version} was modified: bump the version instead (VERSIONING.md section 4)")
    # 5. visibility (warnings only)
    for rid in unenforced_musts():
        warnings.append(f"{rid} is MUST but has no normative vector (declared, not enforced)")
    deferred = [q["id"] for q in reg["questions"] if q["status"] != "resolved"]
    warnings.append(f"{len(deferred)} unresolved question(s): {', '.join(deferred)}")
    return problems, warnings


def build(release: bool) -> None:
    m = compute()
    m["released"] = bool(release)
    MANIFEST.write_text(json.dumps(m, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {MANIFEST.relative_to(CONF)} (contract {m['contract_version']}, sha256 {m['contract_sha256'][:12]}, released={m['released']})")
    if release:
        RELEASES.mkdir(exist_ok=True)
        rel = RELEASES / f"contract-{m['contract_version']}.json"
        if rel.exists() and load(rel)["contract_sha256"] != m["contract_sha256"]:
            sys.exit(f"refusing to overwrite released {rel.name}: files changed, bump the version")
        rel.write_text(json.dumps(m, indent=1) + "\n", encoding="utf-8")
        print(f"wrote {rel.relative_to(CONF)} (immutable)")


def summary() -> dict:
    """What the harness embeds in every report."""
    cur = compute()
    reg = load(REG)
    man_ok = MANIFEST.exists() and load(MANIFEST).get("contract_sha256") == cur["contract_sha256"]
    return {
        "contract_version": cur["contract_version"],
        "contract_sha256": cur["contract_sha256"],
        "manifest_matches_files": bool(man_ok),
        "released": bool(MANIFEST.exists() and load(MANIFEST).get("released")),
        "cop_version": cur["cop_version"],
        "questions": cur["questions"],
        "unresolved": [{"id": q["id"], "status": q["status"], "topic": q["topic"]} for q in reg["questions"] if q["status"] != "resolved"],
        "unenforced_musts": unenforced_musts(),
        "known_failures_sha256": cur["status"]["known_failures_sha256"],
    }


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "verify"
    if cmd == "build":
        build("--release" in argv)
        return 0
    if cmd == "show":
        print(json.dumps(summary(), indent=1))
        return 0
    problems, warnings = verify()
    for w in warnings:
        print("warning:", w)
    for p in problems:
        print("PROBLEM:", p)
    print("contract verify:", "FAILED" if problems else "ok", f"({len(problems)} problem(s), {len(warnings)} warning(s))")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

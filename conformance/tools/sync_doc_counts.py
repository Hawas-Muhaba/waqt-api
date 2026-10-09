#!/usr/bin/env python3
"""Keep generated counts in conformance/spec/CONFORMANCE.md equal to requirements.json (no hand-typed numbers).

    python3 tools/sync_doc_counts.py          # rewrite the marked region
    python3 tools/sync_doc_counts.py --check  # exit 1 if the document is stale (used by tests)

The document is NOT part of the contract hash (tools/contract.py hashes requirements, vectors, open questions, COP),
so regenerating it never invalidates contract.json. Standard library only.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

CONF = Path(__file__).resolve().parent.parent
DOC = CONF / "spec" / "CONFORMANCE.md"
REQ = CONF / "spec" / "requirements.json"
PATTERN = re.compile(r"<!-- generated:requirement-count -->.*?<!-- /generated -->", re.S)


def expected() -> str:
    reqs = json.loads(REQ.read_text(encoding="utf-8"))["requirements"]
    kinds = Counter(r["kind"] for r in reqs)
    detail = ", ".join(f"{n} {k}" for k, n in sorted(kinds.items(), key=lambda kv: -kv[1]))
    return f"<!-- generated:requirement-count -->{len(reqs)} requirement IDs ({detail})<!-- /generated -->"


def main(argv: list[str]) -> int:
    text = DOC.read_text(encoding="utf-8")
    if not PATTERN.search(text):
        print("no generated:requirement-count marker in CONFORMANCE.md", file=sys.stderr)
        return 1
    new = PATTERN.sub(lambda _m: expected(), text)
    if "--check" in argv:
        if new != text:
            print("CONFORMANCE.md requirement count is stale: run python3 tools/sync_doc_counts.py", file=sys.stderr)
            return 1
        print("CONFORMANCE.md counts are current")
        return 0
    DOC.write_text(new, encoding="utf-8")
    print("updated:", expected())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

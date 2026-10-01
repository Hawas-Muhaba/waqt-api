#!/usr/bin/env python3
"""Sprint 14: prove an API change is ADDITIVE with respect to committed conformance vectors.

For every vector in sdks/vectors/sdk_conformance_vectors.json, the live app's current response must
CONTAIN the recorded one: every recorded key still present with an equal value (recursively; lists keep
their length and order), with only two permitted differences -- `meta.generated_at` (volatile) and
`meta.api_version` (which is supposed to move). Anything the new response adds is listed, not hidden.

Exit 0 = nothing the vectors pinned has changed or disappeared.
Run BEFORE regenerating the vectors:   python verification/vector_additivity_check.py [vectors.json]
"""
from __future__ import annotations
import json, sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


#: Lists a new API version may legitimately APPEND to (a catalog gaining an entry). Everything else
#: must keep its length. Append-only: the old items must be an unchanged prefix.
APPEND_ONLY = {"data.providers"}


def contains(old, new, path, problems, added):
    path = path.lstrip(".")
    if isinstance(old, dict):
        if not isinstance(new, dict):
            problems.append(f"{path}: dict became {type(new).__name__}"); return
        for k, v in old.items():
            if path == "meta" and k in ("generated_at", "api_version"):
                continue
            if k not in new:
                problems.append(f"{path}.{k}: REMOVED"); continue
            contains(v, new[k], f"{path}.{k}", problems, added)
        for k in new:
            if k not in old:
                added[f"{path}.{k}"] += 1
    elif isinstance(old, list):
        grew_ok = path in APPEND_ONLY and isinstance(new, list) and len(new) > len(old)
        if not isinstance(new, list) or (len(old) != len(new) and not grew_ok):
            problems.append(f"{path}: list length/type changed"); return
        for a, b in zip(old, new):
            contains(a, b, f"{path}[]", problems, added)
        if grew_ok:
            added[f"{path}[] (+{len(new) - len(old)} appended entries: {[x.get('name') for x in new[len(old):]]})"] += 1
    elif old != new:
        problems.append(f"{path}: {old!r} -> {new!r}")


def main(argv):
    from fastapi.testclient import TestClient
    from waqt.api import app
    client = TestClient(app, raise_server_exceptions=False)
    f = Path(argv[1]) if len(argv) > 1 else ROOT / "sdks/vectors/sdk_conformance_vectors.json"
    vecs = json.loads(f.read_text())["vectors"]
    problems, added = [], Counter()
    for v in vecs:
        rq = v["request"]
        method = rq.get("method", "GET").upper()
        if method == "GET":
            r = client.get(rq["path"], params=rq.get("params"))
        else:
            r = client.post(rq["path"], json=rq.get("body"))
        p = []
        if r.status_code != v["status_code"]:
            p.append(f"status {v['status_code']} -> {r.status_code}")
        contains(v["response"], r.json(), "", p, added)
        # normalise the leading dot for readability
        problems += [f"[{v['id']}] {x}" for x in p]
    print(f"{len(vecs)} vectors checked against the live app")
    print("ADDED (new keys, never removed/changed):")
    for k, n in sorted(added.items()):
        print(f"  + {k}  (x{n})")
    if problems:
        print("\nPROBLEMS:"); [print("  - " + x) for x in problems]; return 1
    print("\nOK: no recorded value changed or disappeared.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

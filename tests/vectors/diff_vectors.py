"""Sprint 13: structural diff of two vector JSON files (path-wise, with
numeric / timestamp deltas).  Used to explain every difference between the
Sprint 12 stamped vectors and the Sprint 13 real regeneration.

Usage: python tests/vectors/diff_vectors.py OLD.json NEW.json [--summary]
"""
from __future__ import annotations
import json, sys
from datetime import datetime

def _ts(s):
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None

def walk(a, b, path, out):
    if type(a) != type(b):
        out.append((path, "type", a, b)); return
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a: out.append((f"{path}/{k}", "added", None, b[k]))
            elif k not in b: out.append((f"{path}/{k}", "removed", a[k], None))
            else: walk(a[k], b[k], f"{path}/{k}", out)
    elif isinstance(a, list):
        if len(a) != len(b): out.append((path, "length", len(a), len(b)))
        ida = all(isinstance(x, dict) and "id" in x for x in a + b)
        if ida:
            da = {x["id"]: x for x in a}; db = {x["id"]: x for x in b}
            for k in da.keys() | db.keys():
                if k not in da: out.append((f"{path}[id={k}]", "case-added", None, None))
                elif k not in db: out.append((f"{path}[id={k}]", "case-removed", None, None))
                else: walk(da[k], db[k], f"{path}[id={k}]", out)
        else:
            for i, (x, y) in enumerate(zip(a, b)): walk(x, y, f"{path}[{i}]", out)
    elif a != b:
        out.append((path, "value", a, b))

def delta(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return b - a
    if isinstance(a, str) and isinstance(b, str):
        ta, tb = _ts(a), _ts(b)
        if ta and tb and ta.tzinfo and tb.tzinfo:
            return (tb - ta).total_seconds()
    return None

def main():
    old = json.load(open(sys.argv[1])); new = json.load(open(sys.argv[2]))
    out = []; walk(old, new, "", out)
    summary = "--summary" in sys.argv
    print(f"{len(out)} differing leaf(s)")
    for p, kind, a, b in out:
        d = delta(a, b)
        if summary: continue
        print(f"{kind:12s} {p}\n    old={json.dumps(a)[:110]}\n    new={json.dumps(b)[:110]}" + (f"\n    delta={d:+.6f}" if d is not None else ""))
    return out

if __name__ == "__main__":
    main()

"""
tests/vectors/vector_stamp.py — Sprint 12: version stamp for portable vectors.

Every vector file records which *content version* it is and, if any expected
value depends on the solar engine, which computation identity generated it:

    "vector_set_version": "1.0",
    "astronomy_dependent": true,
    "generated_at_computation": {"engine": ..., "revision": ..., "accuracy_level": ...}

This is what lets a test (tests/test_vector_versioning.py, core/tests/) fail
when the engine revision moves but the vectors were not regenerated, and what
lets an independent implementation say "I conform to vector set 1.0 @ engine
revision 2" instead of "I passed some JSON".

Generators call `stamp()` as they write. `python tests/vectors/vector_stamp.py`
re-stamps the committed files WITHOUT regenerating them (verifying the body is
untouched) — used when the engine revision is unchanged but the stamp schema
is new, and refused when it is not (see `restamp_file`).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from waqt_core.versioning import VECTOR_SET_VERSION, computation_identity

STAMP_KEYS = ("vector_set_version", "astronomy_dependent", "generated_at_computation")

# file -> does any expected value depend on the solar engine?
ASTRONOMY_DEPENDENT = {
    "waqt_vectors.json": True,
    "scheduling_vectors.json": True,
    "calendar_interop_vectors.json": True,
    "institutional_vectors.json": False,   # frozen month tables; no solar dependence (Sprint 11 confirmed)
}


def stamp(doc: dict, *, astronomy_dependent: bool) -> dict:
    """Return a new dict: the stamp keys first (after any `spec`), body unchanged."""
    body = {k: v for k, v in doc.items() if k not in STAMP_KEYS}
    stamped = {
        "vector_set_version": VECTOR_SET_VERSION,
        "astronomy_dependent": astronomy_dependent,
        "generated_at_computation": computation_identity() if astronomy_dependent else None,
    }
    out: dict = {}
    inserted = False
    for k, v in body.items():
        out[k] = v
        if k == "spec":
            out.update(stamped)
            inserted = True
    if not inserted:
        out = {**stamped, **body}
    return out


def restamp_file(path: Path, *, astronomy_dependent: bool, indent: int = 2) -> None:
    doc = json.loads(path.read_text())
    old = doc.get("generated_at_computation")
    if old is not None and old.get("revision") != computation_identity()["revision"]:
        raise SystemExit(
            f"{path.name} was generated at engine revision {old.get('revision')!r} but the engine is at "
            f"{computation_identity()['revision']!r}: re-stamping would be a lie. Regenerate it."
        )
    new = stamp(doc, astronomy_dependent=astronomy_dependent)
    body_before = {k: v for k, v in doc.items() if k not in STAMP_KEYS}
    body_after = {k: v for k, v in new.items() if k not in STAMP_KEYS}
    assert body_before == body_after, "stamping must not change vector content"
    path.write_text(json.dumps(new, indent=indent, default=str) + "\n")


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    for name, dep in ASTRONOMY_DEPENDENT.items():
        p = here / name
        indent = 1 if name == "scheduling_vectors.json" else 2
        restamp_file(p, astronomy_dependent=dep, indent=indent)
        print("stamped", p.name)

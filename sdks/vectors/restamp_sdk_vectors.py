"""
sdks/vectors/restamp_sdk_vectors.py — Sprint 12.

The SDK conformance vectors are full recorded /v1/* responses. API 1.4.0 added
`computation.engine` / `.revision` and bumped `meta.api_version`. The proper
way to pick that up is to re-run generate_sdk_conformance_vectors.py against
the live app. This script exists for the case where the live app cannot be run
(the Sprint 12 build sandbox had no FastAPI): it applies exactly the two
deterministic transformations the new server code would have produced, using the
same `waqt_core.versioning.computation_identity()` the server uses.

    computation block:  gains `engine`, `revision`; `astronomy_engine` retained.
    meta.api_version:   "1.3.0" -> API_VERSION

Nothing else in any recorded response is touched, and it refuses to run if a
recorded block names a different engine than the code (that would mean the
recording came from a different engine and needs a real re-capture).

`tests/test_sdk_vectors_match_live_api.py` re-captures a sample from the live
app in CI and asserts equality, so a stamped file that disagrees with the real
server fails there.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "tests" / "vectors"))

from vector_stamp import stamp  # noqa: E402
from waqt_core.versioning import computation_identity  # noqa: E402

NEW_API_VERSION = "1.4.0"


def _fix(node):
    if isinstance(node, dict):
        if "astronomy_engine" in node and "accuracy_level" in node and "timescale_model" in node:
            ident = computation_identity()
            if node["astronomy_engine"] != ident["engine"]:
                raise SystemExit(f"recorded engine {node['astronomy_engine']!r} != code engine {ident['engine']!r}: re-capture")
            return {
                "engine": ident["engine"],
                "revision": ident["revision"],
                "accuracy_level": ident["accuracy_level"],
                "astronomy_engine": ident["engine"],
                "timescale_model": node["timescale_model"],
                "delta_t_seconds": node["delta_t_seconds"],
            }
        out = {}
        for k, v in node.items():
            if k == "api_version" and v in ("1.3.0", NEW_API_VERSION):
                out[k] = NEW_API_VERSION
            else:
                out[k] = _fix(v)
        return out
    if isinstance(node, list):
        return [_fix(x) for x in node]
    return node


def main() -> None:
    path = HERE / "sdk_conformance_vectors.json"
    doc = json.loads(path.read_text())
    fixed = _fix(doc)
    fixed = stamp(fixed, astronomy_dependent=True)
    path.write_text(json.dumps(fixed, indent=2) + "\n")
    print("restamped", path)


if __name__ == "__main__":
    main()

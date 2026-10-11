#!/usr/bin/env python3
"""Records the omitted-provider requests under the API 1.7.0 default (umm-al-qura) into
sdks/vectors/sdk_conformance_vectors_api_1_7.json.

These are the SAME eleven requests that sdk_conformance_vectors.json recorded under the pre-1.7.0 default. The
historical file is never touched (see verification/vector_migrations.py). Each new vector is a real response
from the live FastAPI app; nothing is hand-typed. Run:  python3 sdks/vectors/generate_api_1_7_default_provider_vectors.py
"""
from __future__ import annotations
import json, sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent
sys.path.insert(0, str(_HERE)); sys.path.insert(0, str(_ROOT)); sys.path.insert(0, str(_ROOT / "tests" / "vectors")); sys.path.insert(0, str(_ROOT / "verification"))

from generate_sdk_conformance_vectors import CASES, client  # noqa: E402
from vector_migrations import load_migration  # noqa: E402
from vector_stamp import stamp  # noqa: E402


def run() -> dict:
    mig = load_migration()
    by_id = {c["id"]: c for c in CASES}
    vectors = []
    for e in mig["entries"]:
        c = by_id[e["id"]]
        assert "calendar_provider" not in c["params"], "default-provider vectors must OMIT the provider"
        resp = client.request(c["method"], c["path"], params=c["params"])
        vectors.append({
            "id": e["new_vector_id"], "replaces_historical_id": e["id"],
            "description": c["description"] + " Provider omitted: API 1.7.0 default (umm-al-qura).",
            "request": {"method": c["method"], "path": c["path"], "params": c["params"]},
            "expected_provider": e["provider_after"],
            "status_code": resp.status_code, "response": resp.json(),
        })
    return {
        "spec": "waqt-api-sdk-conformance/1.0",
        "generated_by": "sdks/vectors/generate_api_1_7_default_provider_vectors.py",
        "governing_api_version": mig["new_vector_governing_api_version"],
        "default_calendar_provider": "umm-al-qura",
        "migration": mig["migration"],
        "note": "Real /v1/* responses recorded with calendar_provider OMITTED under API 1.7.0. The pre-1.7.0 recordings of the same requests remain in sdk_conformance_vectors.json (replayed with arithmetic-tabular made explicit).",
        "vectors": vectors,
    }


def main():
    report = stamp(run(), astronomy_dependent=True)
    out = _HERE / "sdk_conformance_vectors_api_1_7.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(report['vectors'])} vectors to {out}")


if __name__ == "__main__":
    main()

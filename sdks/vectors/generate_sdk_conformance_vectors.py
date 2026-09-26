#!/usr/bin/env python3
"""
sdks/vectors/generate_sdk_conformance_vectors.py

Generates sdk_conformance_vectors.json: a curated set of REAL `/v1/*` HTTP
responses (full envelope: meta/data/error), captured by calling the live
FastAPI app in-process (Starlette's TestClient -- an actual ASGI request/
response cycle, not a hand-built dict). Nothing in the output file is
hand-typed.

This is the "same public JSON vectors" the Sprint 9 brief asks both SDKs
to consume: the Python SDK's tests/test_conformance.py feeds each
`response` straight into `waqt_client.types.*.from_json` (the exact
parsing code the live client uses) and checks the result; the JS SDK's
test/conformance.test.mjs does the same against its own parser. Same
file, two independent parsers, same assertions about what the fields mean.

Run:  python3 sdks/vectors/generate_sdk_conformance_vectors.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent
sys.path.insert(0, str(_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from waqt.api import app  # noqa: E402

client = TestClient(app)

CASES = [
    {
        "id": "waqt-addis-normal",
        "method": "GET",
        "path": "/v1/waqt",
        "params": {"lat": 9.0192, "lon": 38.7525, "instant": "2026-09-19T15:42:00Z"},
        "description": "Full /v1/waqt result, ordinary instant, Addis Ababa.",
    },
    {
        "id": "waqt-polar-undefined",
        "method": "GET",
        "path": "/v1/waqt",
        "params": {"lat": 69.6492, "lon": 18.9553, "instant": "2026-06-21T12:00:00Z"},
        "description": "UNDEFINED status: Tromso midsummer, sun never sets.",
    },
    {
        "id": "waqt-hanafi-asr",
        "method": "GET",
        "path": "/v1/waqt",
        "params": {"lat": 21.4225, "lon": 39.8262, "instant": "2026-09-19T10:00:00Z", "asr_ratio": 2.0},
        "description": "Non-default astronomy profile (Hanafi Asr), Makkah.",
    },
    {
        "id": "day-addis",
        "method": "GET",
        "path": "/v1/day",
        "params": {"lat": 9.0192, "lon": 38.7525, "instant": "2026-09-19T15:42:00Z"},
        "description": "/v1/day subset shape.",
    },
    {
        "id": "events-addis",
        "method": "GET",
        "path": "/v1/events",
        "params": {"lat": 9.0192, "lon": 38.7525, "instant": "2026-09-19T15:42:00Z"},
        "description": "/v1/events subset shape.",
    },
    {
        "id": "hijri-ordinary",
        "method": "GET",
        "path": "/v1/hijri",
        "params": {"date": "2026-09-19"},
        "description": "Gregorian date -> Hijri date, default provider.",
    },
    {
        "id": "hijri-umm-al-qura",
        "method": "GET",
        "path": "/v1/hijri",
        "params": {"date": "2026-09-19", "calendar_provider": "umm-al-qura"},
        "description": "Gregorian date -> Hijri date, umm-al-qura provider.",
    },
    {
        "id": "calendar-providers",
        "method": "GET",
        "path": "/v1/calendar",
        "params": {},
        "description": "Provider discovery list.",
    },
    {
        "id": "location-addis",
        "method": "GET",
        "path": "/v1/location",
        "params": {"lat": 9.0192, "lon": 38.7525, "instant": "2026-09-19T15:42:00Z"},
        "description": "Timezone + local civil date lookup.",
    },
    {
        "id": "conversions-to-hijri",
        "method": "GET",
        "path": "/v1/conversions",
        "params": {"direction": "to-hijri", "date": "2026-09-19"},
        "description": "Bidirectional conversion utility, to-hijri.",
    },
    {
        "id": "conversions-to-gregorian",
        "method": "GET",
        "path": "/v1/conversions",
        "params": {"direction": "to-gregorian", "year": 1448, "month": 4, "day": 7},
        "description": "Bidirectional conversion utility, to-gregorian.",
    },
    {
        "id": "calendar-convert-instant",
        "method": "GET",
        "path": "/v1/calendar/convert",
        "params": {
            "direction": "instant-to-calendars",
            "instant": "2026-09-19T15:42:00Z",
            "lat": 9.0192, "lon": 38.7525,
        },
        "description": "Instant -> UTC/civil Gregorian + Waqt day/position.",
    },
    {
        "id": "calendar-convert-date-to-waqt",
        "method": "GET",
        "path": "/v1/calendar/convert",
        "params": {
            "direction": "gregorian-date-to-waqt",
            "date": "2026-09-20",
            "lat": 9.0192, "lon": 38.7525,
        },
        "description": "Gregorian civil date + location -> Waqt day.",
    },
    {
        "id": "boundary-crossing-both",
        "method": "GET",
        "path": "/v1/calendar/boundary-crossing",
        "params": {
            "start": "2026-09-19T00:00:00Z", "end": "2026-09-20T00:00:00Z",
            "lat": 9.0192, "lon": 38.7525,
        },
        "description": "Span crossing both civil midnight and Maghrib.",
    },
    {
        "id": "schedule-snapshot",
        "method": "GET",
        "path": "/v1/schedule/snapshot",
        "params": {"lat": 9.0192, "lon": 38.7525, "instant": "2026-09-19T15:42:00Z"},
        "description": "Scheduling snapshot for an instant.",
    },
    {
        "id": "schedule-span",
        "method": "GET",
        "path": "/v1/schedule/span",
        "params": {
            "lat": 9.0192, "lon": 38.7525,
            "start": "2026-09-19T00:00:00Z", "end": "2026-09-21T00:00:00Z",
        },
        "description": "Scheduling span classification.",
    },
    {
        "id": "institutional-week",
        "method": "GET",
        "path": "/v1/institutional/week",
        "params": {"lat": 9.0192, "lon": 38.7525, "instant": "2026-09-19T15:42:00Z"},
        "description": "Institutional week containing an instant.",
    },
    {
        "id": "institutional-profile",
        "method": "GET",
        "path": "/v1/institutional/profile",
        "params": {},
        "description": "Default institutional profile.",
    },
    {
        "id": "error-invalid-instant",
        "method": "GET",
        "path": "/v1/waqt",
        "params": {"lat": 9.0192, "lon": 38.7525, "instant": "not-a-date"},
        "description": "Error envelope: INVALID_INSTANT, 400.",
    },
    {
        "id": "error-invalid-span",
        "method": "GET",
        "path": "/v1/calendar/boundary-crossing",
        "params": {
            "start": "2026-09-20T00:00:00Z", "end": "2026-09-19T00:00:00Z",
            "lat": 9.0192, "lon": 38.7525,
        },
        "description": "Error envelope: INVALID_SPAN, 400 (end before start).",
    },
    {
        "id": "error-validation",
        "method": "GET",
        "path": "/v1/waqt",
        "params": {"lat": 999, "lon": 38.7525},
        "description": "Error envelope: VALIDATION_ERROR, 422 (lat out of range).",
    },
]


def run() -> dict:
    vectors = []
    for case in CASES:
        resp = client.request(case["method"], case["path"], params=case["params"])
        vectors.append({
            "id": case["id"],
            "description": case["description"],
            "request": {"method": case["method"], "path": case["path"], "params": case["params"]},
            "status_code": resp.status_code,
            "response": resp.json(),
        })
    return {
        "spec": "waqt-api-sdk-conformance/1.0",
        "generated_by": "sdks/vectors/generate_sdk_conformance_vectors.py",
        "note": (
            "Every 'response' here is a real /v1/* HTTP response captured from the live "
            "FastAPI app (Starlette TestClient), full envelope included. Both the Python "
            "SDK (sdks/python/tests/test_conformance.py) and the JS SDK "
            "(sdks/js/test/conformance.test.mjs) parse these same responses with their own "
            "parsing code and assert the same facts about the parsed result -- this is what "
            "'both SDKs implement the same Waqt API contract' means operationally."
        ),
        "vectors": vectors,
    }


def main():
    report = run()
    out_path = _HERE / "sdk_conformance_vectors.json"
    out_path.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Wrote {len(report['vectors'])} vectors to {out_path}")


if __name__ == "__main__":
    main()

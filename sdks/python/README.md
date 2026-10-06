# waqt-client (Python)

Official thin Python SDK for the [Waqt API](../../docs/API.md) — a
Makkah-anchored, Maghrib-to-Maghrib civil time and Hijri calendar API.

```
Waqt Specification
       |
   HTTP / JSON
       |
  waqt_client        <-- this package: ergonomic types + functions
       |                  over the wire contract, nothing more
Your application
```

**This is a remote API client, not a local reimplementation of Waqt's
rules.** Every value it returns came from a live `/v1/*` HTTP response.
See "Local vs server computation" below.

## Install

```bash
pip install -e sdks/python          # from a checkout, editable
# or, once published:
pip install waqt-client
```

Requires Python >= 3.9. Single runtime dependency: `httpx`.

## Quick start

```python
from waqt_client import WaqtClient

with WaqtClient(base_url="https://your-waqt-deployment.example.com") as client:
    resp = client.get_waqt(lat=9.0192, lon=38.7525)
    print(resp.status)                 # "OK"
    print(resp.hijri.display)          # "7 Rabi al-Thani 1448 AH"
    print(resp.waqt.display)           # "Waqt 00:19:21"
    print(resp.event("maghrib").instant)
```

Async:

```python
import asyncio
from waqt_client import AsyncWaqtClient

async def main():
    async with AsyncWaqtClient(base_url="...") as client:
        resp = await client.get_waqt(lat=9.0192, lon=38.7525)
        print(resp.hijri.display)

asyncio.run(main())
```

## Configuration

```python
from waqt_client import WaqtClient, WaqtClientConfig

config = WaqtClientConfig(
    base_url="https://your-deployment.example.com",
    timeout_seconds=5.0,
    default_calendar_provider="umm-al-qura",   # applied unless a call overrides it
    default_asr_shadow_ratio=2.0,              # Hanafi, applied unless overridden
    on_version_mismatch="warn",                # "ignore" | "warn" | "raise"
)
client = WaqtClient(config=config)
```

Every typed method also accepts the endpoint's own query parameters
directly as keyword arguments (see docs/API.md for the full list per
endpoint) — a per-call argument always overrides a config default.

## Error handling

```python
from waqt_client import WaqtApiError, WaqtTransportError

try:
    client.get_waqt(lat=999, lon=0)
except WaqtApiError as e:
    print(e.code, e.message, e.details)   # "VALIDATION_ERROR", ..., {"errors": [...]}
except WaqtTransportError as e:
    print("network/parse problem:", e)
```

`WaqtApiError.code` is exactly the `error.code` value documented in
docs/API.md (`INVALID_INSTANT`, `CALENDAR_DATE_UNRESOLVABLE`,
`INVALID_HIJRI_DATE`, `UNKNOWN_TIMEZONE`, `OUT_OF_RANGE`,
`VALIDATION_ERROR`, ...) — never a generic HTTP-status-only exception.
Codes are strings, not a closed enum, so new server codes remain
available without an SDK release.

## What's covered

Typed methods for every `/v1/*` endpoint as of API version 1.6.0:
`/v1/waqt`, `/v1/day`, `/v1/events`, `/v1/hijri`, `/v1/calendar`,
`/v1/location`, `/v1/conversions`, `/v1/calendar/convert`,
`/v1/calendar/boundary-crossing`, `/v1/schedule/{snapshot,span,resolve}`,
`/v1/institutional/{week,fiscal-year,academic-year,profile,*/resolve}`.

For anything not yet wrapped, `client.request(method, path, params=...,
json=...)` is the same envelope-aware call every typed method is built
on — it raises the same `WaqtApiError`, returns the same unwrapped `data`
dict, and is never blocked on a new SDK release.

API 1.6.0 / conformance contract 2.0.0 corrects the Waqt-day label to
the civil date of its closing Maghrib and defines `next_event` by
occurrence, including the previous solar day's Isha. The vector set is
2.0; the SDK preserves these responses and new error codes as-is.

## Local vs server computation

This package is a **remote Waqt API client**. It does not compute a
Maghrib instant, a Hijri date, or a scheduling result on its own — every
number comes from the server. A **local Waqt computation library** (no
network round-trip, the astronomical/calendar engine embedded directly)
is a distinct, separately-specified component this SDK deliberately does
not pretend to be. See `docs/SDK.md`.

## Conformance

`tests/test_conformance.py` parses `sdks/vectors/sdk_conformance_vectors.json`
— real, captured `/v1/*` HTTP responses (success and error) — through this
SDK's own type/envelope parsing and checks the result. The JavaScript SDK
(`sdks/js/`) parses the exact same file with its own, independent parser.

## Development

```bash
cd sdks/python
pip install -e ".[dev]"
pytest -q
```

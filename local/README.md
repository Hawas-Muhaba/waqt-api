# waqt-local

The embeddable, **no-server** Waqt computation library. Sprint 10's
answer to the architectural gap Sprint 9 named and deliberately left
open ("What was intentionally not built" in `SPRINT-9-REPORT.md`).

```
                    Waqt Specification
                           │
             ┌─────────────┴─────────────┐
             │                           │
       Local computation             HTTP API
             │                           │
       waqt_local (this package)   Waqt Server (waqt.api)
                                         │
                              ┌──────────┴──────────┐
                              │                     │
                         Python SDK          JS/TS SDK
                       (waqt_client, remote)  (waqt-client, remote)
```

## What this is — and is not

- **Is**: a thin, in-process wrapper. Every function in `waqt_local`
  calls straight into `waqt.core` / `waqt.solar` / `waqt.semantics` /
  `waqt.hijri` / `waqt.scheduling` / `waqt.institutional` /
  `waqt.calendar_interop` — the exact same computation the HTTP server
  (`waqt.api`) is built on — and shapes the result into the same dict
  shape the matching `/v1/*` endpoint's `data` field has.
- **Is not** `waqt_client` (the Sprint 9 remote SDKs). `waqt_client`'s
  every value comes from a live HTTP response; `waqt_local`'s every
  value comes from a direct Python call. No network, no `httpx`, no
  server process, ever.
- **Is not** a second implementation of Waqt's temporal/astronomical
  rules. The only code here that isn't a direct call-through is
  presentation shaping (units, null behavior — see `formatting.py`'s
  module docstring), verified against the server's own shaping by
  `tests/test_local_vs_server_equivalence.py`.

## Install

This package is not yet published as a standalone PyPI distribution,
because the `waqt` core package (`waqt/` at the repository root) is
not itself split out as an independently installable distribution —
today it is only ever run from a checkout of this repository (the
HTTP server is also only ever run that way: `uvicorn waqt.api:app`
from the repo root). `waqt-local` inherits that same constraint rather
than duplicating `waqt`'s code into its own package. Splitting a
`waqt-core` distribution out from the application/API layer so that
both `waqt-local` and `waqt.api` depend on it as a normal PyPI
dependency is a natural Sprint 11 candidate — see this sprint's report.

For now:

```bash
git clone https://github.com/waqt-project/waqt-api
cd waqt-api
pip install -e local/            # installs waqt_local
# waqt_local imports `waqt` directly; run from the repo root, or put
# the repo root on PYTHONPATH, exactly as waqt.api itself requires.
```

## Use

```python
import waqt_local

result = waqt_local.waqt(lat=9.0192, lon=38.7525)
print(result["hijri"]["display"], result["waqt"]["display"])

# Scheduling — the same operation-JSON format the HTTP API and the
# conformance vectors use (docs/SCHEDULING.md §8), resolved in-process:
result = waqt_local.schedule_resolve({
    "location": {"lat": 9.0192, "lon": 38.7525},
    "anchor": "2026-09-19T15:42:00Z",
    "operation": {
        "op": "resolve_interval",
        "interval": {
            "type": "interval",
            "start": {"type": "event", "name": "maghrib", "day": 0},
            "end": {"type": "event", "name": "isha", "day": 0},
        },
    },
})
```

A caller mistake raises a `waqt_local.errors.WaqtLocalError` subclass
(`ValidationError`, `InvalidRuleError`, `InvalidCalendarRuleError`, ...)
— named identically to the HTTP API's `ErrorCode` values, but as
exception classes rather than an error envelope, since there is no
transport here to put an envelope around. Undefined astronomy (polar
day/night) is never an exception — it is a normal `status` value in
the returned dict, exactly as on the HTTP side.

## Typed scheduling/institutional requests

`waqt_local.schedule_resolve`, `institutional_fiscal_year_resolve`, and
`institutional_academic_year_resolve` accept either a plain dict (the
wire JSON shape) or any object exposing a `.to_json()` method that
returns that shape — which is exactly the duck type the Python SDK's
new `waqt_client.requests` typed request builders satisfy (see
`docs/SDK.md`). The two modules are independent (this package has no
dependency on `waqt_client`, and vice versa — see `docs/LOCAL.md`
"Why typed requests aren't a shared package yet"), but a caller who
already built a typed request object for the SDK can hand the same
object straight to `waqt_local` — see `tests/test_typed_request_duck_typing.py`.

## Conformance

`tests/` runs this library directly against the same public
conformance vectors (`tests/vectors/*.json` at the repo root) the
Python/JS SDKs and Python/JS core suites already use — see
`docs/LOCAL.md` for the extended conformance-vector diagram this
sprint establishes, and `tests/test_local_vs_server_equivalence.py`
for a live, field-by-field cross-check against a real running
`waqt.api` instance.

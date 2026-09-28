# Local computation — `waqt-local`

Sprint 10's answer to the gap Sprint 9 named and deliberately left open:
a Waqt computation surface that works **without an HTTP server**.

## Architecture

```
                    Waqt Specification
                           │
             ┌─────────────┴─────────────┐
             │                           │
       Local computation             HTTP API
             │                           │
       Local Waqt library          Waqt Server
       (local/waqt_local)          (waqt.api)
                                         │
                              ┌──────────┴──────────┐
                              │                     │
                         Python SDK          JS/TS SDK
                       (waqt_client, remote)  (waqt-client, remote)
```

`waqt_local` and `waqt.api` are **siblings**, not one built on the
other. Both call directly into the same computation package
(`waqt_core.core`, `waqt_core.solar`, `waqt_core.semantics`,
`waqt_core.hijri`, `waqt_core.scheduling`, `waqt_core.institutional`,
`waqt_core.calendar_interop` — the `waqt-core` distribution since Sprint 11;
`waqt.core` etc. remain as aliases to the same module objects);
neither is layered on top of the other, and `waqt_local` has zero
dependency on FastAPI or `waqt.api`. `waqt_client` (the remote SDKs)
sits below the HTTP API only, and has zero dependency on `waqt` or
`waqt_local` — it only ever sees JSON over the wire.

## What's genuinely shared, and what's deliberately duplicated

**Shared (not duplicated):** every temporal/astronomical/calendar
computation. `waqt_local.facade.waqt(...)` calls `waqt_core.core.compute_waqt` (== `waqt.core.compute_waqt`)
directly — the exact function `waqt.api.waqt_endpoint` also calls. There
is exactly one implementation of "what time is Waqt right now" in this
codebase; `waqt_local` does not introduce a second one, and could not
disagree with the HTTP server about it even if it tried, because it
calls the same code.

**Deliberately duplicated (a few dozen lines, total):** value
*presentation* — turning a `timedelta` into `{"display": "...", "seconds": ...}`,
a `HijriDate` into its wire dict, resolving a `calendar_provider` name
string into a provider instance. `waqt.api.common` / `waqt.api.providers`
do this for the HTTP layer; `waqt_local.formatting` / `waqt_local.providers`
do the same thing independently, so that `waqt_local` never needs
FastAPI installed. `tests/test_local_vs_server_equivalence.py` (in
`local/tests/`) exists precisely because "the two presentation layers
happen to produce identical output" is a claim worth checking by machine,
not by two people reading two files and agreeing they look the same —
it drives a real, in-process `waqt.api` FastAPI app (via
`httpx.ASGITransport`, no socket) and a real `waqt_local` call for the
same input, and asserts the two response bodies are equal, field by
field, for every endpoint that has a local equivalent.

## Why typed requests aren't a shared package (yet)

`waqt_local.schedule_resolve` / `institutional_fiscal_year_resolve` /
`institutional_academic_year_resolve` accept either a plain `dict` (the
wire JSON shape) or any object with a `.to_json()` method. The Python
SDK's new `waqt_client.requests` typed builders (docs/SDK.md) satisfy
that same duck type — a caller can build a request once and hand it to
either — but the two modules do not import each other: `waqt_client`
must stay dependency-free of `waqt`/`waqt_local` (it is a client for
*any* server speaking the wire protocol, not just this checkout), and
`waqt_local` has no reason to depend on an HTTP-client package. A third,
shared `waqt-requests` package that both import is the natural
Sprint 11 candidate if this duplication becomes painful in practice —
today it is two independent ~350-line modules kept honest by
`local/tests/test_errors_and_typed_requests.py`'s duck-typing test and
by both being checked against the same server-side wire format
(`waqt.scheduling.model`, `waqt.scheduling.ops`, `waqt.institutional.rules`)
in their own test suites.

## Conformance

The public conformance-vector pattern Sprint 9 established
(`tests/vectors/*.json`, consumed independently by the Python core
suite, the JS core suite via the SDK, and both SDKs' own conformance
tests) now has a fourth, local-computation consumer:

```
                 Public Conformance Vectors
                 (tests/vectors/*.json)
                           │
          ┌────────────────┼────────────────┬────────────────┐
          │                │                │                │
    Python core          JS core         Python/JS       Local Python
    (tests/)         (sdks/js tests)   SDK conformance    computation
                                        (sdks/vectors)   (local/tests/)
          └────────────────┴────────────────┴────────────────┘
                                     │
                              Same contract
```

`local/tests/test_waqt_vectors_conformance.py`,
`test_scheduling_vectors_conformance.py`,
`test_institutional_vectors_conformance.py`, and
`test_calendar_interop_vectors_conformance.py` each drive
`waqt_local`'s public functions against the same vector files, rather
than reaching into `waqt.core`/`waqt.scheduling` directly — so a
regression in `waqt_local`'s own facade/formatting layer (not just in
`waqt`'s computation) would be caught here too.

## Distribution

`waqt-local` is not yet an independently installable PyPI package,
because the `waqt` core package (`waqt/` at the repository root) isn't
split out as its own distribution — see `local/README.md`'s "Install"
section for the full explanation and the Sprint 11 candidate this
points at (a `waqt-core` package that both `waqt.api` and `waqt_local`
would depend on normally). This is a real, named limitation, not an
oversight: Sprint 10's publishing goal was specifically the two
`waqt_client` SDKs (docs/RELEASING.md), which this sprint's report
addresses directly.

# api-consumer

Reference API consumer (Sprint 12, Goal A.3): a small program that proves
an external application can use Waqt over HTTP **without knowing the
internal package structure** — it imports neither `waqt_core`, `waqt_local`,
`waqt.api`, nor either SDK. Its only dependency is the Python standard
library (`urllib`, `json`), because that is the strongest form of the
claim: even a consumer with no `waqt-client` installed can use the API.

(For a real application, `sdks/python/waqt_client` or
`sdks/js/waqt-client` is the better choice — typed, retrying, versioned.
This program exists specifically to demonstrate the *floor*: the API needs
nothing but HTTP and JSON.)

## Run it

```
python -m api_consumer.cli --base-url http://localhost:8000 --lat 21.4225 --lon 39.8262
```

Prints the current Waqt reading, the next event, and the server's
computation/version metadata, then exits 0. Non-zero exit and a one-line
message on any HTTP, network, or unexpected-shape error.

## What "without knowing the internal package structure" means here

`api_consumer/waqt_api.py` is a minimal, hand-written HTTP client against
the *documented* contract only (`docs/API.md`'s response envelope:
`{"status": "ok"|"error", "data": ...}` / `{"status": "error", "error":
{...}}`, and the field names in each endpoint's response). It does not
import any Waqt package to get a request/response type, a route constant,
or a default parameter — everything it knows about the API it read from
`docs/API.md`, the same document an outside integrator would read.
`tests/test_no_internal_imports.py` enforces this by parsing the package's
own source.

## Tests

Two layers, because this sandbox has no live server to test against
end-to-end (see `SPRINT-12-REPORT.md`):

- `tests/test_no_internal_imports.py` — structural: no `waqt*` import
  anywhere in `api_consumer/`.
- `tests/test_against_fake_server.py` — behavioural: a `http.server`-based
  fake that serves the *exact* JSON shapes `waqt/api/waqt_endpoint.py` and
  `waqt/api/version_endpoint.py` produce (copied from real `waqt_local`
  output recorded elsewhere in this sprint), started on a local port, real
  HTTP over a real socket. This is not a mock of `api_consumer` — it is a
  mock of the *server*, so `api_consumer`'s own HTTP/JSON handling is
  exercised for real.

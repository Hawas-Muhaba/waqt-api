# Sprint 9 Report — SDKs & Language Bindings + Parallel Milestone A

## Summary

Sprint 9 delivers the two official thin SDKs the roadmap called for
(`sdks/python/` — package `waqt-client`; `sdks/js/waqt-client/` — package
`waqt-client`), a shared conformance vectors file both SDKs' test suites
parse independently, and — run in parallel per the brief's explicit
instruction — Parallel Milestone A: an Independent Astronomical Reference
(`independent-astronomy/`) that shares no code with `waqt/solar.py` and
cross-validates against it across a 60-row geographic/seasonal matrix.

`waqt/`, `waqt/api/`, `consumers/js/`, and every other Sprint 1–8
deliverable are byte-for-byte unchanged (`md5sum`-verified before and
after this sprint's work — see below). 565 Python tests pass (472
pre-existing + 15 independent-astronomy + 78 Python SDK); 217 JavaScript
tests pass (184 pre-existing consumer tests + 33 SDK conformance/
integration tests).

```
waqt/core.py        af88c5fdc13e99390597598586db9d73   (before == after)
waqt/solar.py        8002b2fb03de49ba0784528b766cb3f2   (before == after)
waqt/semantics.py    bf92e76e58c2e25b0b74e51c8a6d1b7c   (before == after)
waqt/hijri.py        6215cc141d6fb03234144246a441b761   (before == after)
waqt/timescale.py    06860a6a7482fc0f1ba9fb892a89f90b   (before == after)
```

(Full `find waqt -name '*.py' | xargs md5sum` before/after diffed clean —
37 files, zero changes, zero additions/removals inside `waqt/`.)

## What was built

### 1. Python SDK — `sdks/python/` (`waqt-client`)

- `waqt_client/types.py` — typed representations for every shape the
  brief named: `WaqtResponse`, `AstronomicalEvent`, `WaqtPosition`,
  `HijriDate`, `GregorianRepresentation`/`InstantRepresentation`,
  `SchedulingResult`, `InstitutionalCalendarResult`, plus
  `Location`/`TimezoneInfo`/`Reading`/`AstronomyProfile`/
  `ComputationInfo`/`CalendarProviderInfo`/`ConversionResult`/
  `BoundaryCrossingResult`/`LocationInfo`. Every type keeps the original
  parsed JSON on `.raw` for forward compatibility.
- `waqt_client/client.py` (`WaqtClient`, sync, `httpx.Client`) and
  `waqt_client/async_client.py` (`AsyncWaqtClient`, `httpx.AsyncClient`)
  — typed methods for all 19 `GET`/`POST` `/v1/*` endpoints, sharing pure
  param-building (`_requests.py`) and envelope-unwrapping (`_envelope.py`)
  logic so the two classes can't drift apart.
- `waqt_client/errors.py` — `WaqtApiError` (`.code`/`.message`/
  `.details`/`.status_code`), `WaqtTransportError`, `WaqtVersionMismatch`.
- `waqt_client/config.py` — `WaqtClientConfig`: base URL, timeout,
  per-client provider/profile defaults, `on_version_mismatch` policy.
- 78 tests: `test_types.py` (parsing edge cases), `test_client_sync.py`
  and `test_client_async.py` (live integration against the real FastAPI
  app — a real bound socket for sync, `httpx.ASGITransport` for async),
  `test_errors_and_version.py`, and `test_conformance.py` (see §3).

### 2. JavaScript/TypeScript SDK — `sdks/js/waqt-client/` (`waqt-client`)

- `src/types.mjs` — the same typed representations as the Python side,
  as plain frozen objects + parse functions (the idiomatic shape for a
  thin JS SDK), typed for TypeScript consumers via JSDoc plus a
  hand-written `index.d.ts` — no build step; `tsconfig.json`
  (`checkJs: true`) type-checks the source directly.
- `src/client.mjs` (`WaqtClient`) — one async, promise-based client
  (`fetch`-based) covering the same 19 endpoints, with the same
  method-per-endpoint naming as the Python SDK (`getWaqt`/`get_waqt`,
  `scheduleSnapshot`/`schedule_snapshot`, ...). JS ships one client, not
  two, because `fetch`/Node's HTTP stack have no idiomatic *synchronous*
  form — a single async client **is** "synchronous/asynchronous requests
  where appropriate" for this language (see `README.md#why-async-only`
  for the full reasoning).
- `src/errors.mjs`, `src/config.mjs`, `src/envelope.mjs`,
  `src/requests.mjs` — direct mirrors of the Python SDK's modules.
- 33 tests (`node --test`): `test/conformance.test.mjs` (18, see §3) and
  `test/client.test.mjs` (15) — the latter spawns a real
  `python3 -m uvicorn waqt.api:app` subprocess and talks to it over an
  actual socket (`test-support/server.mjs`), not a mock.

### 3. Conformance — `sdks/vectors/`

`sdks/vectors/generate_sdk_conformance_vectors.py` calls the live
FastAPI app (Starlette `TestClient`) for 21 curated requests — 18
success responses covering every shape either SDK models, plus 3 error
envelopes (`INVALID_INSTANT` 400, `INVALID_SPAN` 400, `VALIDATION_ERROR`
422) — and writes the full, real HTTP responses (envelope included,
nothing hand-typed) to `sdks/vectors/sdk_conformance_vectors.json`.

Both SDKs' test suites parse this **same file** with their own,
independent parsing code and assert the same facts about the parsed
result — 18 assertions on the Python side, 18 on the JS side. This is
what "the Python and JavaScript SDKs implement the same Waqt API
contract" means operationally, per the brief's own distinction, rather
than merely "they both happen to call the server."

### 4. Local vs server computation

Both SDKs' READMEs and `docs/SDK.md` state plainly: these are **remote
API clients**. Neither computes a Maghrib instant, Hijri date, or
scheduling result on its own. A **local Waqt computation library** is
named as a distinct, not-yet-built component, exactly as the brief
specifies ("The latter can come later or be separately specified").

### 5. Parallel Milestone A — Independent Astronomical Reference

`independent-astronomy/independent_solar/` — see
`docs/INDEPENDENT-ASTRONOMY.md` for the full write-up. In short: a
second, from-scratch solar-event engine sharing no astronomy code with
`waqt/solar.py` (Meeus-style apparent position with explicit nutation/
aberration; event times solved via Greenwich Apparent Sidereal Time +
right ascension, never an equation of time). `compare.py` runs both
engines across 12 locations × 5 dates (60 rows, 360 event comparisons)
and writes real comparison vectors to
`independent-astronomy/vectors/independent_astronomy_comparison.json`.

Results: agreement within 21–49 seconds at the equator, tropics, and
mid-latitudes; an honestly-reported wider band (~7 minutes max) at high
latitude near the equinox — a real geometric effect (shallow sun path
amplifies small angle disagreements near the terminator at high
latitude) `docs/ASTRONOMY.md` already predicted in prose, now measured
against a second live implementation for the first time. No case of one
engine reporting `UNDEFINED` (polar day/night) while the other found a
numeric answer. 15 tests pass (`independent-astronomy/tests/`): 10
standalone astronomical sanity checks (equinox/solstice declination,
event ordering, polar day/night, Asr shadow-ratio comparison, elevation
effects, a structural check that `independent_solar` imports nothing
from `waqt`) and 5 comparison-agreement checks against the live
tolerance bands.

Per the brief: this milestone does **not** replace `waqt/solar.py` and
is not reachable from `/v1/*` — it "first prove[s]
agreement/disagreement transparently," which is what it does.
`docs/CALENDAR-INTEROP.md` §6 is updated from "tracked, not built" to
"built in Sprint 9," linking to the new doc.

## What was intentionally not built

- **A local (embeddable, no-network) Waqt computation library.** The
  brief explicitly allows this to come later or be separately specified;
  building it now would blur "thin, spec-driven SDK" with "second
  implementation of Waqt's rules," the exact thing the brief says the
  SDKs must not become.
- **Full typed request/response models for `/v1/schedule/resolve` and
  the two institutional `.../resolve` `POST` endpoints.** Their request
  bodies are richer than a `GET`'s query parameters and vary by
  operation type; both SDKs accept/return the raw JSON body for these
  three endpoints rather than guessing at a shape. See `docs/SDK.md`
  "Honest limitations."
- **Publishing either SDK to PyPI/npm.** Both install from the checkout
  (`pip install -e sdks/python`, `npm install ./sdks/js/waqt-client`).
  Packaging/release is a separate, deliberate step from SDK design.
- **Wiring Milestone A's independent engine into the HTTP API or either
  SDK.** The brief is explicit that it should not silently replace the
  existing engine; it remains a standalone, server-side cross-check.
- **A VSOP87/JPL-ephemeris ("Level A") check for either solar engine.**
  Milestone A demonstrates two independently-derived Level-B-grade
  algorithms converge on the same astronomy; it is not proof of
  sub-second absolute accuracy against a Level-A reference.
  `docs/ASTRONOMY.md`'s Level A row is still "Not implemented."

## Verification

```
$ find waqt -name '*.py' | sort | xargs md5sum   # before vs after this sprint: identical, 37 files

$ python3 -m pytest -q                            # from repo root
565 passed in 7.39s
  (472 pre-existing + 15 independent-astronomy + 78 Python SDK)

$ cd consumers/js && node --test                  # unchanged, pre-existing
184 passed

$ cd sdks/js/waqt-client && npm test               # node --test
33 passed
  (18 conformance + 15 live-server integration)

$ cd independent-astronomy && python3 compare.py
Max |diff| observed, by latitude band:
  equator      tolerance=  30s  observed_max=21.49  [OK]
  tropics      tolerance=  40s  observed_max=31.166  [OK]
  mid-lat-N    tolerance=  80s  observed_max=39.814  [OK]
  mid-lat-S    tolerance=  80s  observed_max=49.019  [OK]
  high-lat     tolerance= 500s  observed_max=435.733  [OK]
No UNDEFINED-status disagreements (polar day/night agreement: OK).
```

## Sprint 9 Definition of Done — checked against the brief

> Sprint 9 is complete when Waqt provides official thin Python and
> JavaScript/TypeScript SDKs implementing the documented v1.x HTTP/JSON
> contract, with typed representations, structured errors, configuration,
> serialization, documentation, and conformance tests against the public
> vectors.

Done — `sdks/python/`, `sdks/js/waqt-client/`, `docs/SDK.md`, both
READMEs, `sdks/vectors/sdk_conformance_vectors.json` plus both SDKs'
conformance test suites.

> SDK behavior must remain specification-driven and must not duplicate or
> silently alter Waqt's temporal/astronomical rules.

Verified structurally: `waqt/` is byte-for-byte unchanged, and neither
SDK computes anything — every returned value traces to a live `/v1/*`
HTTP response (see "Design decisions" in `docs/SDK.md` for why
`SchedulingResult`/`InstitutionalCalendarResult` stay deliberately
generic rather than re-deriving scheduling/institutional logic).

> In parallel, Independent Astronomical Reference Milestone A should
> produce an independently implemented solar-event calculation and a
> documented comparison against the existing reference engine.

Done — `independent-astronomy/`, `docs/INDEPENDENT-ASTRONOMY.md`, 60-row
comparison vectors, 15 passing tests, honest reporting of the one
wider-than-initially-assumed tolerance band (high latitude near
equinox) rather than a tuned-to-pass number.

> I would not require the independent astronomy implementation to replace
> the current engine in Sprint 9. It should first prove
> agreement/disagreement transparently.

Confirmed not wired into `waqt/api/` or either SDK; the full transparent
comparison — successes, the one honest disagreement, and why — is in
`docs/INDEPENDENT-ASTRONOMY.md`.

## Suggested Sprint 10 candidates

- Fully typed request bodies for `/v1/schedule/resolve` and the two
  institutional `.../resolve` endpoints, closing the one deliberate gap
  named in "What was intentionally not built."
- A local (embeddable) Waqt computation library, as the brief
  anticipated — likely Python first, built against the same conformance
  vectors this sprint's SDK work established the pattern for.
- Package and publish `waqt-client` to PyPI and npm for real.
- Extend Parallel Milestone A's comparison matrix with a Level-A
  (VSOP87 or JPL ephemeris) cross-check, closing the gap named in
  "What was intentionally not built."

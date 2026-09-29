# Versioning (Sprint 12 Goal D)

`waqt-core` now exists as a real distribution, consumed by `waqt-api`,
`waqt-local`, two SDKs, and (as of this sprint) three reference
applications. This document defines the relationship among the five things
that can each independently have a "version", so a bug report, a pinned
dependency, or a reproducibility question can say precisely which one it
means.

## 1. The five axes

| Axis | Lives in | Current value | Changes when |
|---|---|---|---|
| **waqt-core version** | `core/waqt_core/_version.py` (`waqt_core.__version__`) | `0.2.0` | Any change to `waqt-core`'s Python API or behavior — semver against that API. |
| **Astronomical engine revision** | `core/waqt_core/versioning.py` (`ENGINE_REVISION`) | `"2"` | Only when `solar.py`/`timescale.py`'s *output* changes — see §2. Independent of waqt-core's own version: waqt-core can gain new features (a new endpoint's worth of Python, say) without the engine's numbers moving, and conversely a waqt-core patch release can carry an engine revision bump if that's the only change in it. |
| **API version** | `waqt/api/common.py` (`API_VERSION`) | `1.4.0` | Any change to the HTTP contract (docs/API.md) — semver against that contract, additive-only within `/v1/`. |
| **SDK version** | `sdks/python/pyproject.toml`, `sdks/js/waqt-client/package.json` | Python `0.3.0`, JS `0.3.0` | Any change to the SDK's own public interface. Each SDK also tracks `MAX_KNOWN_API_VERSION` (`1.4.0`): the highest API version it has been tested against, checked at runtime — see `sdks/python/waqt_client/config.py`. |
| **Conformance-vector-set version** | `core/waqt_core/versioning.py` (`VECTOR_SET_VERSION`) | `1.0` | MAJOR when any vector's *expected value* changes (near-certainly because the engine revision moved); MINOR when cases are added with no existing expectation changed. |

A sixth thing that looks like a version but is not one: `waqt-cli`
(`apps/cli`, `0.1.0`) and `waqt-api-consumer` (`apps/api-consumer`, `0.1.0`)
have their own versions too, same rule as an SDK — they track their own
interface, not any of the five axes above.

## 2. Why the engine revision is separate from waqt-core's version

Sprint 11 changed `solar.py`'s output — by up to seven minutes at high
latitude — while `waqt-core` did not yet exist as a distribution and the
`astronomy_engine` string (`waqt-noaa-low-precision`) did not change. Two
responses computed before and after that fix, both saying
`"astronomy_engine": "waqt-noaa-low-precision"`, disagreed by minutes with
no way to tell from the response alone.

`ENGINE_REVISION` closes that gap: it is the smallest unit that must change
whenever the *numbers* a caller would get back could change, independent of
how much or how little of the surrounding Python changed. It is mechanically
enforced, not just documented — `waqt_core.versioning.engine_fingerprint()`
hashes the engine's output on a fixed probe grid, pinned per-revision in
`ENGINE_REVISIONS`, and `core/tests/test_engine_revision.py` fails if the
fingerprint and the declared revision disagree. See that module's docstring
for the full mechanism.

`waqt-core`'s own semver, by contrast, is about its Python API: adding a
function is a MINOR bump whether or not it touches `solar.py`, and touching
`solar.py`'s internals without changing any public output is not required to
bump anything at all (though in practice a `solar.py` change serious enough
to warrant a revision bump usually warrants a waqt-core version bump too,
by convention rather than by rule).

## 3. How the axes move together

```
waqt-core 0.1.0 ── engine revision "1" (retroactive label; Sprints 1-10, pre-waqt-core)
     │
     ▼ (Sprint 11: solar.py bugfixes, package born)
waqt-core 0.1.0 ── engine revision "2"
     │
     ▼ (Sprint 12: versioning module, /v1/version, computation.engine/.revision added)
waqt-core 0.2.0 ── engine revision "2" (unchanged: no solar.py output changed this sprint)
     │
     ├── waqt-api 1.3.0 → 1.4.0   (additive: computation.engine/.revision, GET /v1/version)
     ├── waqt-local 0.2.0 → 0.3.0  (mirrors the API's additive change; requires waqt-core>=0.2.0,<0.3)
     ├── SDK (py) 0.2.0 → 0.3.0    (ComputationInfo.engine/.revision, get_version(); MAX_KNOWN_API_VERSION → 1.4.0)
     ├── SDK (js) 0.2.0 → 0.3.0    (same, JS side)
     └── conformance vectors 1.0   (first versioned set; stamped with engine revision "2")
```

The general rule the diagram illustrates: an engine revision bump forces a
waqt-core version bump and a conformance-vector-set MAJOR bump (the
vectors' expected values are now wrong for the new engine), and *may*
propagate further (API/waqt-local/SDKs) only if it changes what they
return — which it always does, since they all echo `computation.revision`
verbatim. A waqt-core version bump does not necessarily imply an engine
revision bump (Sprint 12 is the example: 0.1.0 → 0.2.0 with no revision
change). An API version bump does not imply either of the above (Sprint 9's
SDK work, for instance, could bump the API without touching the engine).

## 4. How a caller finds out what they're talking to

`GET /v1/version` (`waqt.api.version_endpoint`, API >= 1.4.0) and
`waqt_local.version()` both return every axis they own, built by the same
`waqt_core.versioning.version_report()`:

```json
{
  "waqt_core_version": "0.2.0",
  "spec": "waqt-core/0.1",
  "api_version": "1.4.0",
  "waqt_local_version": null,
  "computation": {"engine": "waqt-noaa-low-precision", "revision": "2", "accuracy_level": "B"},
  "engine_revision_history": {"1": {...}, "2": {...}},
  "conformance_vectors": {"vector_set_version": "1.0", "generated_at_engine_revision": "2"}
}
```

`waqt_local_version` is `null` from the server (an HTTP API has no
`waqt-local` layer) and `api_version` is `null` from `waqt_local.version()`
(no HTTP layer to have one) — each caller reports only the axes it owns; see
`version_report`'s docstring. SDK versions are deliberately never included:
a client's own version is not a property of the server, and each SDK
already knows its own (`waqt_client.__version__` / the JS package's
`VERSION` export).

`waqt-cli`'s `waqt version` and `waqt-api-consumer`'s output both surface
this same report (locally via `waqt_local.version()`, over HTTP via
`GET /v1/version` respectively) plus their own package version, so a bug
report from either can quote one block that identifies every layer
involved.

## 5. Conformance vectors: what the stamp means and doesn't

Every vector file (`tests/vectors/*.json`, `sdks/vectors/sdk_conformance_vectors.json`)
carries:

```json
"vector_set_version": "1.0",
"astronomy_dependent": true,
"generated_at_computation": {"engine": "waqt-noaa-low-precision", "revision": "2", "accuracy_level": "B"}
```

`astronomy_dependent: false` (only `institutional_vectors.json`: frozen
month tables with no solar dependence) means `generated_at_computation` is
`null` and the file's expected values cannot go stale from an engine
revision bump. For every other file, `core/tests/test_engine_revision.py`
asserts the stamped revision equals the running engine's — an engine bump
with the vectors not regenerated fails there, not silently at runtime. See
`tests/vectors/vector_stamp.py` for the stamping mechanism and
`sdks/vectors/restamp_sdk_vectors.py` for the one sprint-specific exception
(this sandbox could not run the live FastAPI app to re-record the SDK
vectors, so that file's `computation` blocks were updated by
transformation instead of re-capture — see `SPRINT-12-REPORT.md`).

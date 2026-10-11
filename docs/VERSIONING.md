# Versioning (Sprint 12 Goal D; audited and corrected in Sprint 13 Goal F)

`waqt-core` now exists as a real distribution, consumed by `waqt-api`,
`waqt-local`, two SDKs, and (as of this sprint) three reference
applications. This document defines the relationship among the five things
that can each independently have a "version", so a bug report, a pinned
dependency, or a reproducibility question can say precisely which one it
means.

## 1. The five axes

| Axis | Lives in | Current value | Changes when |
|---|---|---|---|
| **waqt-core version** | `core/waqt_core/_version.py` (`waqt_core.__version__`) | `0.5.0` | Any change to `waqt-core`'s Python API or behavior — semver against that API. |
| **Astronomical engine revision** | `core/waqt_core/versioning.py` (`ENGINE_REVISION`) | `"2"` | Only when `solar.py`/`timescale.py`'s *output* changes — see §2. Independent of waqt-core's own version: waqt-core can gain new features (a new endpoint's worth of Python, say) without the engine's numbers moving, and conversely a waqt-core patch release can carry an engine revision bump if that's the only change in it. |
| **API version** | `waqt/api/common.py` (`API_VERSION`) | `1.7.0` | Any change to the HTTP contract (docs/API.md) — semver against that contract; response shapes remain stable within `/v1/`, and behavior changes are explicitly documented/versioned. |
| **SDK version** | `sdks/python/pyproject.toml`, `sdks/js/waqt-client/package.json` | Python `0.3.1`, JS `0.3.1` | Any change to the SDK's own public interface. Each SDK also tracks `MAX_KNOWN_API_VERSION` (`1.7.0`): the highest API version it has been tested against, checked at runtime — see `sdks/python/waqt_client/config.py`. |
| **Conformance-vector-set version** | `core/waqt_core/versioning.py` (`VECTOR_SET_VERSION`) | `2.0` | MAJOR when any vector's *expected value* changes for an input that is still present (near-certainly because the engine revision moved); MINOR when cases are added or replaced with no such change. `1.1` (Sprint 13) replaced one case whose expected value was not reproducible across tz-database releases; engine revision unchanged. |

Two more things look like versions and are easy to conflate with the axes
above (Sprint 13 audit):

- The **`waqt-api` distribution version** (`pyproject.toml` at the repo root,
  currently `0.5.0`) is *not* the **API version** (`1.7.0`, the HTTP
  contract). The package can ship a fix without the contract moving, and the
  contract can gain an additive field in the same release as any package
  version. `GET /v1/version` reports the contract (`api_version`), never the
  package version. `waqt-local` (`0.6.0`) likewise has its own version,
  reported as `waqt_local_version` only by `waqt_local.version()`.
- `tests/test_version_consistency.py` enforces, mechanically, that each of
  these has its own literal source (nothing is computed from another), that
  package metadata equals the in-code version, that each changelog's newest
  entry is the current version, that the values in this file and
  `docs/PACKAGING.md` are current, and that every vector file is stamped with
  the running vector-set version and engine identity.

A further thing that looks like a version but is not one: `waqt-cli`
(`apps/cli`, `0.2.0`) and `waqt-api-consumer` (`apps/api-consumer`, `0.1.0`)
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
     │
     ▼ (Sprint 13: first real regeneration; verification + evidence sprint)
waqt-core 0.2.1 ── engine revision "2" (unchanged; solar.py fingerprint identical)
     ├── waqt-api package 0.2.0, API contract 1.4.0   (unchanged)
     ├── waqt-local 0.3.0, SDKs 0.3.0 / 0.3.0        (unchanged)
     └── conformance vectors 1.0 → 1.1  (one case replaced: non-leap-century-1900 moved from
                                          Addis Ababa to London; no astronomy value changed)

Sprint 14 (live integrations & production hardening):

waqt-core 0.3.0 ── engine revision "2" (unchanged: solar.py/timescale.py byte-identical to Sprint 13)
     ├── waqt-api package 0.3.0, API contract 1.4.0 → 1.5.0   (additive: hijri.source/.provenance,
     │                                   calendar_provider=aladhan, data.calendar_error, per-event
     │                                   representations, integrations in /v1/health + /v1/version,
     │                                   429 RATE_LIMITED)
     ├── waqt-local 0.3.0 → 0.4.0   (mirrors the API additions; requires waqt-core>=0.3.0,<0.4)
     └── SDKs 0.3.0 → 0.3.1 / 0.3.0 → 0.3.1   (HijriDate.source/.provenance, WaqtResponse.calendar_error; MAX_KNOWN_API_VERSION → 1.5.0)
```
Sprint 16 (conformance contract 2.0.0; defects DIS-001/002/003 resolved):

```
waqt-core 0.3.0 → 0.4.0 ── engine revision "2" (unchanged: the fingerprint covers solar.compute_day_events only)
     ├── waqt-api package 0.3.0 → 0.4.0, API contract 1.5.0 → 1.6.0
     │        (additive: INVALID_HIJRI_DATE, UNKNOWN_TIMEZONE, OUT_OF_RANGE;
     │         corrected behaviour: day label = civil date of the closing Maghrib instant, next_event by occurrence)
     ├── waqt-local 0.4.0 → 0.5.0   (mirrors the three error codes; requires waqt-core>=0.4.0,<0.5)
     ├── SDKs 0.3.1 / 0.3.1         (unchanged; MAX_KNOWN_API_VERSION stays 1.5.0 <= 1.6.0)
     ├── vector set 1.1 → 2.0       (MAJOR: expected values changed for unchanged inputs --
     │                               frozen kiritimati-date-line label, two recorded next_event values)
     └── conformance contract 1.0.0 → 2.0.0   (conformance/VERSIONING.md: a narrowed accepted-code set is breaking)
```
Option B (default calendar provider `umm-al-qura`; owner decision, DR-0009 / DR-0010):

```
waqt-core 0.4.0 → 0.5.0 ── engine revision "2" (unchanged: no solar output changed)
     ├── waqt-api package 0.4.0 → 0.5.0, API contract 1.7.0 (unchanged: the 1.7.0 default change landed earlier, see
     │        migrations/API-1.7.0-default-provider.md; this release only makes the API read the default from waqt-core
     │        and fixes /v1/calendar/convert returning 500 outside 1700..2300; requires waqt-core>=0.5.0,<0.6)
     ├── waqt-local 0.5.0 → 0.6.0   (default follows waqt-core; mirrors the additive blocks; requires waqt-core>=0.5.0,<0.6)
     ├── waqt-cli 0.1.1 → 0.2.0     (--provider default follows waqt-local; requires waqt-local>=0.6.0,<0.7)
     ├── SDKs 0.3.1 / 0.3.1, api-consumer 0.1.0   (unchanged: HTTP only; they omit the provider unless told)
     ├── vector set 2.0             (unchanged: no expected value changed)
     └── conformance contract 2.0.0 (draft, unreleased) + CAL-012: omitted provider = umm-al-qura (CCP-0001)
```
The API default and waqt-core's default are one definition (`waqt_core.calendar_providers.default`);
`tests/test_default_provider_single_source.py` fails if any layer re-types it.

Sprint 13 is the example of the *smallest* movement: a value that `waqt-core`
reports changed (patch bump), while the engine revision, the HTTP contract and every
other package stayed put. Nothing is inferred from anything else.

The general rule the diagram illustrates: an engine revision bump forces a
waqt-core version bump and a conformance-vector-set MAJOR bump (the
vectors' expected values are now wrong for the new engine), and *may*
propagate further (API/waqt-local/SDKs) only if it changes what they
return — which it always does, since they all echo `computation.revision`
verbatim. A waqt-core version bump does not necessarily imply an engine
revision bump (Sprint 12 is the example: 0.1.0 → 0.2.0 with no revision
change; Sprint 13's 0.2.0 → 0.2.1 is another). An API version bump does not imply either of the above (Sprint 9's
SDK work, for instance, could bump the API without touching the engine).

## 4. How a caller finds out what they're talking to

`GET /v1/version` (`waqt.api.version_endpoint`, API >= 1.4.0) and
`waqt_local.version()` both return every axis they own, built by the same
`waqt_core.versioning.version_report()`:

```json
{
  "waqt_core_version": "0.4.0",
  "spec": "waqt-core/0.1",
  "api_version": "1.7.0",
  "waqt_local_version": null,
  "computation": {"engine": "waqt-noaa-low-precision", "revision": "2", "accuracy_level": "B"},
  "engine_revision_history": {"1": {...}, "2": {...}},
  "conformance_vectors": {"vector_set_version": "2.0", "generated_at_engine_revision": "2"}
}
```

API contract 1.6.0 → 1.7.0 (intentional behavior change; no field removed or renamed):
the default `calendar_provider` on provider-aware HTTP endpoints changes from
`arithmetic-tabular` to `umm-al-qura`; either provider remains explicitly selectable.
Additive: responses that did not name the provider they used now carry
`calendar_provider: {name, version}` (institutional week / fiscal-year / academic-year,
and `/v1/conversions`). The full record, with examples, risks and the disposition of the
eleven changed recordings, is [`migrations/API-1.7.0-default-provider.md`](migrations/API-1.7.0-default-provider.md).
The Python and JavaScript SDKs now record API 1.7.0 as their maximum tested version.

**Policy for provider defaults (ratified in [DR-0009](../conformance/decisions/DR-0009.md) by Dr. Salim Muhammed Redi, recorded 2026-10-10).**
The `/v1` guarantee is about *response shapes* and *explicitly selected* behavior: a request that names
`calendar_provider` is reproducible across versions. The provider used when the parameter is **omitted** is
a project default and may change only by a decision of the project owners, in a new API version, together
with (a) a migration record under `docs/migrations/`, (b) versioned vectors (historical recordings are never
rewritten; a declared migration replays them under their historical provider), and (c) instructions for
preserving the previous results. Callers that need stability pin `calendar_provider`. A change of default
is never made to make a test pass.

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
"vector_set_version": "2.0",
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
`sdks/vectors/restamp_sdk_vectors.py` for the Sprint 12 exception: that sprint could not run
FastAPI, so the SDK vectors' `computation` blocks were updated by transformation. **Sprint 13
superseded that**: every file, including `sdk_conformance_vectors.json`, was regenerated from the
real engine and the real FastAPI app, and diffed against the Sprint 12 versions
(`tests/vectors/diff_vectors.py`). The only differences were the `vector_set_version` stamp,
`generated_at` timestamps, and the one replaced calendar-interop case. The restamp script is now
historical and should not be used for a normal revision bump; regenerate instead.

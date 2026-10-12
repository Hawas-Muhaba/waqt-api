# Changelog — waqt-client (Python)

This project uses [Semantic Versioning](https://semver.org/). The SDK's
own version number is independent of the Waqt HTTP API's `api_version`
(see `waqt_client/config.py`'s `MIN_SUPPORTED_API_VERSION` /
`SUPPORTED_API_MAJOR_VERSION`, and docs/RELEASING.md's "Compatibility
policy") — this sprint deliberately does not introduce automatic
major-version synchronization between the two, since nothing in the
Waqt specification requires it.

## 0.3.1 — Sprint 14

**Added** (API 1.5.0, all optional/defaulted, so existing code is unaffected): `HijriDate.source`,
`HijriDate.provenance`, `HijriDate.is_fallback`, `WaqtResponse.calendar_error`. Against a pre-1.5.0
server they are `None`. `MAX_KNOWN_API_VERSION` → `1.8.0`; the current 0.3.1 SDK suite is verified against API 1.8.0.

## 0.3.0 — Sprint 12

### Added
- `ComputationInfo.engine` and `.revision` (+ `.identity`): the computation
  reproducibility identity introduced in API 1.4.0. `astronomy_engine` is
  kept with the same value. Against a pre-1.4.0 server `engine` falls back
  to `astronomy_engine` and `revision` is `None` — the SDK never invents a
  revision.
- `WaqtClient.get_version()` / `AsyncWaqtClient.get_version()` → `VersionInfo`
  (`GET /v1/version`).
- `MAX_KNOWN_API_VERSION` is now `1.4.0`.

### Changed
- None. Existing signatures and return types are unchanged; the new
  `ComputationInfo` fields have defaults, so direct construction is unaffected.

## 0.2.0 — Sprint 10

### Added
- `waqt_client.requests`: typed, `.to_json()`-able request builders for
  the three endpoints that previously took only a raw `dict`:
  `POST /v1/schedule/resolve`, `POST /v1/institutional/fiscal-year/resolve`,
  `POST /v1/institutional/academic-year/resolve`. Every documented
  `v1.x` endpoint now has a typed representation in this SDK.
- Package metadata for distribution: classifiers, `py.typed` marker,
  supported-Python-version declaration (`>=3.9`), release procedure and
  compatibility policy (docs/RELEASING.md), clean-install smoke test.

### Changed
- None. Every Sprint 9 method signature and return type is unchanged.
  Passing a plain `dict` to `schedule_resolve` /
  `institutional_fiscal_year_resolve` / `institutional_academic_year_resolve`
  behaves exactly as it did in 0.1.0 — the typed builders are additive.

## 0.1.0 — Sprint 9

Initial release: full read-side (`GET`) coverage of `/v1/*`, sync and
async clients, response envelope handling, conformance-vector-verified
parsing. Not published to PyPI (checkout-only install).

# Changelog — waqt-client (JavaScript/TypeScript)

[Semantic Versioning](https://semver.org/). This SDK's version is
independent of the Waqt HTTP API's `api_version` — see
docs/RELEASING.md's "Compatibility policy".

## 0.3.1 — Sprint 14

### Added
- `HijriDate.source` / `.provenance` / `.isFallback` and `WaqtResponse.calendarError` (API 1.5.0);
  `null`/`false` against an older server. `MAX_KNOWN_API_VERSION` → `1.8.0`; the current 0.3.1 SDK suite is verified against API 1.8.0.

## 0.3.0 — Sprint 12

### Added
- `ComputationInfo.engine` / `.revision`: the reproducibility identity from
  API 1.4.0. `astronomyEngine` is kept with the same value; against an older
  server `engine` falls back to it and `revision` is `null`.
- `client.getVersion()` → `VersionInfo` (`GET /v1/version`), with types in
  `index.d.ts`.
- `MAX_KNOWN_API_VERSION` is now `1.4.0`.

### Changed
- None; additive only.

## 0.2.0 — Sprint 10

### Added
- `requests_types.mjs` (exported as `requests` from the package root):
  typed, `toJSON()`-able request builders for the three endpoints that
  previously took only a plain object: `POST /v1/schedule/resolve`,
  `POST /v1/institutional/fiscal-year/resolve`,
  `POST /v1/institutional/academic-year/resolve`. Every documented
  `v1.x` endpoint now has a typed representation in this SDK.
- `index.d.ts` type declarations for the above.
- Package metadata for distribution: `files`, `engines.node>=18`
  (unchanged, now enforced by a clean-install test), release procedure
  and compatibility policy (docs/RELEASING.md), clean-install smoke test.

### Changed
- None. Every Sprint 9 method signature is unchanged. Passing a plain
  object to `scheduleResolve` / `institutionalFiscalYearResolve` /
  `institutionalAcademicYearResolve` behaves exactly as it did in
  0.1.0 — the typed builders are additive.

## 0.1.0 — Sprint 9

Initial release: full read-side (`GET`) coverage of `/v1/*`, promise-
based client, response envelope handling, conformance-vector-verified
parsing. Not published to npm (checkout-only install).

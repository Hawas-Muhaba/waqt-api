# Changelog — waqt-local

Sprint 13 made **no change** to `waqt-local` (no release): its `computation` block and `version()`
are thin readers of `waqt-core`, so the vector-set label change in `waqt-core` 0.2.1 flows through
without any `waqt-local` edit. Its version therefore stays `0.3.0`.

## 0.3.0 — Sprint 12

**Added**: `waqt_local.version()` — the same report `GET /v1/version` returns, built by
`waqt_core.versioning.version_report()`, so an embedded library and a server cannot describe
themselves differently (`api_version` is `null` here: there is no HTTP layer; `waqt_local_version`
is this package's own version).
**Changed (additive)**: every `computation` block now carries `engine`, `revision` and
`accuracy_level`; `astronomy_engine` is kept as a deprecated alias with the identical value.
Requires `waqt-core>=0.2.0,<0.3`.

## 0.2.0 — Sprint 11

**Changed**: `waqt_local` now imports its computation directly from
`waqt-core` (`waqt_core.core`, `waqt_core.hijri`, `waqt_core.scheduling`,
`waqt_core.institutional`, `waqt_core.calendar_interop`,
`waqt_core.calendar_providers`, `waqt_core.semantics`,
`waqt_core.timescale`, `waqt_core.timezone_provider`) instead of from
`waqt.*`, and declares `waqt-core` as a real `pyproject.toml`
dependency (previously `dependencies = []` — `waqt_local` relied on an
undeclared, checkout-only coupling to the combined `waqt/` package; see
`docs/LOCAL.md`'s "Why typed requests aren't a shared package yet" /
Sprint 10's named gap). No behavior change: `waqt_core.core.compute_waqt`
is the exact same function `waqt.core.compute_waqt` aliases to (see
`SPRINT-11-REPORT.md` Sec 1), so every value `waqt_local` returns is
computed identically to before. `waqt_local` no longer needs the `waqt`
distribution (and therefore FastAPI) installed at all to run — only
`waqt-core`.

## 0.1.0 — Sprint 10

Initial release. See `SPRINT-10-REPORT.md` Sec 1.

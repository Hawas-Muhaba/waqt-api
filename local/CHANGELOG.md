# Changelog — waqt-local

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

# Changelog — waqt-local

## 0.6.0 — Option B (default calendar provider)

**Changed (behaviour change)**: the default `calendar_provider` of every function (`waqt`, `hijri`, `convert`,
`represent_instant`, `waqt_day_for_gregorian_date`, scheduling, institutional, `institutional_default_profile`) is now
**`umm-al-qura`** (was `arithmetic-tabular`), read from `waqt-core` (`waqt_local.DEFAULT_CALENDAR_PROVIDER`), so it is
always identical to the HTTP API default (API 1.7.0). To keep previous results pass `calendar_provider="arithmetic-tabular"`.
The default institutional profile is named `demo-umm-al-qura` accordingly.

**Added** (mirrors API 1.7.0): `calendar_provider {name, version}` on `convert` and on the institutional week / fiscal-year /
academic-year results; `waqt.calendar_error` when the Hijri label is unavailable (for example outside 1700..2300) in
`represent_instant` / `waqt_day_for_gregorian_date`.

**Fixed**: `represent_instant` raised `AttributeError` instead of returning the Waqt day with an empty Hijri label for an
instant outside umm-al-qura's range (needs `waqt-core` 0.5.0).

**Requires** `waqt-core>=0.5.0,<0.6`.

## 0.5.0 — Sprint 16

**Added** (mirrors API 1.6.0): `UnknownTimezoneError` (`UNKNOWN_TIMEZONE`), `InvalidHijriDateError`
(`INVALID_HIJRI_DATE`), `OutOfRangeError` (`OUT_OF_RANGE`). Requires `waqt-core` 0.4.x, which also corrects the
day label (DIS-001) and `next_event` (EVT-007), so local and server keep returning identical payloads.

## 0.4.0 — Sprint 14

**Added** (mirrors API 1.5.0, so `waqt_local` and the server keep returning identical payloads):
`hijri.source` / `hijri.provenance`, `data.calendar_error`, `data.event_representations[]`, and the
`network` / `single_date_only` keys in `list_calendar_providers()`.
**Changed**: requires `waqt-core>=0.3.0,<0.4` (was `>=0.2.0,<0.3`).
**Deliberately not added**: the `aladhan` provider. An embedded, offline library should not make
network calls on its own; its catalog stays at the four local providers, and the equivalence test
(`local/tests/test_local_vs_server_equivalence.py`) states that one permitted difference explicitly.

---

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

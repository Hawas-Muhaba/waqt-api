# Changelog — waqt-cli

## 0.3.0 — API 1.8.0 / conformance 2.0.0

**Changed:** CLI input validation follows `waqt-local` 0.7.0 and `waqt-core` 0.6.0; invalid profile values receive a clear validation error. Requires `waqt-local>=0.7.0,<0.8`.

## 0.2.0 — Option B (default calendar provider)

**Changed (behaviour change)**: `--provider` now defaults to **`umm-al-qura`** (was `arithmetic-tabular`), taken from
`waqt-local`/`waqt-core`, so the CLI, the offline library and the HTTP API (1.7.0) share one default. For example
`waqt convert --hijri 1448-4-15` now prints 2026-09-26 (was 2026-09-28). To keep previous results pass
`--provider arithmetic-tabular`. `waqt convert --instant ...` for an instant outside 1700..2300 no longer crashes with the
default provider: the Waqt day is printed and the Hijri label is empty.

**Requires** `waqt-local>=0.6.0,<0.7`.

## 0.1.1

Earlier releases (see git history); this file starts at 0.2.0.

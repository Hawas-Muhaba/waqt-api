# Changelog — waqt-cli

## Unreleased

**Fixed (DR-0012)**: `waqt convert` / `now` / `events` crashed with a TypeError for a Gregorian date or instant outside the calendar provider's range; they now print the Waqt day and `Hijri: unavailable (calendar_error: ...)`. **Changed (DR-0011)**: invalid angles / ratio are rejected with a clear message. Package version not bumped.

## 0.2.0 — Option B (default calendar provider)

**Changed (behaviour change)**: `--provider` now defaults to **`umm-al-qura`** (was `arithmetic-tabular`), taken from
`waqt-local`/`waqt-core`, so the CLI, the offline library and the HTTP API (1.7.0) share one default. For example
`waqt convert --hijri 1448-4-15` now prints 2026-09-26 (was 2026-09-28). To keep previous results pass
`--provider arithmetic-tabular`. `waqt convert --instant ...` for an instant outside 1700..2300 no longer crashes with the
default provider: the Waqt day is printed and the Hijri label is empty.

**Requires** `waqt-local>=0.6.0,<0.7`.

## 0.1.1

Earlier releases (see git history); this file starts at 0.2.0.

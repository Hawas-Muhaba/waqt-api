# waqt-cli

Reference command-line application for Waqt (Sprint 12, Goal A.1). Runs
**entirely locally** — no network, no server — on top of `waqt-local`
(which wraps `waqt-core`). It contains no astronomy, calendar, or scheduling
logic of its own; `tests/test_no_second_implementation.py` enforces that
structurally.

## Install

```
pip install -e core/ -e local/ -e apps/cli/
```

## Usage

```
waqt now --lat 9.0192 --lon 38.7525
waqt events --lat 9.0192 --lon 38.7525 --instant 2026-09-28T12:00:00Z
waqt convert --gregorian 2026-09-28
waqt convert --hijri 1448-04-15
waqt convert --instant 2026-09-28T12:00:00Z --lat 9.0192 --lon 38.7525
waqt schedule reminder --event maghrib --minutes-before 30 --lat 9.0192 --lon 38.7525
waqt schedule window --from fajr --to sunrise --lat 9.0192 --lon 38.7525
waqt schedule until --event asr --lat 9.0192 --lon 38.7525
waqt schedule rule my_rule.json --lat 9.0192 --lon 38.7525   # raw docs/SCHEDULING.md §8 operation
waqt providers
waqt version
```

Add `--json` before the subcommand to get the exact `waqt_local` payload
(includes the full `computation` block) instead of formatted text.

Every location command accepts `--elevation`, `--timezone` (IANA override),
`--fajr-angle`, `--isha-angle`, `--asr-ratio`, and `--provider`
(`arithmetic-tabular` default, or `umm-al-qura`, `declared`,
`local-observation` — see `waqt providers`).

## Why a CLI belongs in Sprint 12

Sprints 1–11 built the computation (`waqt-core`), the server (`waqt-api`),
the embeddable library (`waqt-local`), and two SDKs — no genuinely
user-facing consumer yet used any of them end to end. This is the first.
It is deliberately thin: argument parsing and text formatting in
`waqt_cli/render.py`, dispatch in `waqt_cli/main.py`, and a single import
seam (`waqt_cli/backend.py`) to `waqt_local`. Every fact printed —
Maghrib boundaries, Hijri dates, event instants, Waqt readings,
`computation.engine`/`revision`/`accuracy_level` — is exactly what
`waqt_local` returned, unmodified in `--json` mode.

## Tests

```
cd apps/cli && pytest
```

`test_cli.py` exercises every subcommand against the real `waqt_local` (never
mocked) and checks both the formatted text and (for `now`) that `--json`
output is byte-for-byte the same dict `waqt_local.waqt()` returns directly.
`test_no_second_implementation.py` parses the package's own source and fails
if it imports anything besides `waqt_local`/`waqt_core.__version__`/stdlib,
or contains vocabulary (`julian_century`, `declination`, the Hijri epoch
constant, ...) that would suggest a second computation had crept in.

One provider, `umm-al-qura`, needs the optional `ephem` dependency; this
repository's own CI installs it, but it was not available in the sandbox
this sprint was built in, so that one code path is exercised only as far as
"the CLI reaches `waqt_local` and reports a missing-dependency failure
cleanly" rather than for correct output. See `SPRINT-12-REPORT.md`.

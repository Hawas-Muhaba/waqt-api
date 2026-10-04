# Waqt formal conformance suite (Sprint 15; contract 2.0.0 in Sprint 16)

A portable specification of Waqt's observable behaviour, a language-neutral harness, **626 vectors + 43 metamorphic checks**
(exact counts in `reports/`), and a clean-room second implementation — built to find out whether Waqt can be
implemented, and verified, from the written specification alone.

```
./run.sh                                  # unit tests + both implementations -> reports/conformance-report.md
python3 harness/waqt_conform.py --adapter "node independent/src/cli.mjs" --label mine     # any adapter, any language
python3 harness/differential.py --n 200 --seed 15                                           # random differential run vs DE421
python3 tools/contract.py verify                                                              # contract manifest + cross-references (Sprint 16)
# build_vectors.py / import_legacy.py / build_requirements.py produced the 1.0.0 baseline and are retired: see GOVERNANCE.md
WAQT_RUN_CONFORMANCE=1 pytest ../tests/test_conformance_suite.py                            # as a regression gate
```

| path | what |
|---|---|
| `spec/CONFORMANCE.md` | conformance levels, vector tiers, accuracy bands, reporting, implementer checklist |
| `spec/COP.md` | the adapter protocol and every operation's input/output |
| `spec/requirements.json` | 71 requirement IDs (`MUST` / `OPEN`), each with `since` / `status` / `decision` |
| `GOVERNANCE.md`, `VERSIONING.md`, `CHANGELOG.md`, `MAINTAINERS.md` | **Sprint 16:** how the contract changes, how it is versioned, what is breaking, how conventions stay configurable |
| `decisions/`, `proposals/` | decision records (DR-0001..) and the proposal template |
| `spec/open-questions.json` | machine-readable registry of every question and its status; unresolved ones are printed in every report |
| `contract.json` | the versioned manifest (hash of requirements + vectors + registry + COP) |
| `spec/OPEN-QUESTIONS.md` | where the written spec is silent or ambiguous (found by implementing it) |
| `DISAGREEMENTS.md` | register of every reference/independent disagreement, classified |
| `vectors/` | `legacy-*` (Sprint 5–8 vectors adopted verbatim), `day-model` (DE421 oracle), `calendar-*`, `provider-failure`, `errors`, `scheduling-live`, `open-questions`, `metamorphic` |
| `harness/` | `waqt_conform.py` (runner + report), `differential.py` |
| `adapters/reference_adapter.py` | binds the Python reference to COP |
| `independent/` | the independent implementation (Node, zero dependencies) |
| `baselines/known-failures.json` | the reference's documented failures; CI fails on any new one |
| `reports/` | generated reports (committed so the Sprint 15 numbers are inspectable) |

Adding your own implementation: write an adapter that speaks COP (see `independent/src/cli.mjs`, ~20 lines
on top of the operations) and run `waqt_conform.py`. The report's per-requirement table tells you exactly which
requirements you pass; `spec/CONFORMANCE.md` §7 explains how to classify a failure.

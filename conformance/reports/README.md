# Reports

| file | what | contract | trust |
|---|---|---|---|
| `conformance-report.*`, `differential-report.*`, `mutation-check.md` | Sprint 15 reports, **unchanged** | 1.0.0 (historical) | as stated there |
| `sprint16-independent.*` | independent implementation vs contract 2.0.0 | 2.0.0 | full run: 704 normative pass / 0 fail |
| `sprint16-reference-sandbox.*` | reference vs contract 2.0.0, **in a sandbox without PyEphem** | 2.0.0 | partial: see the banner; confirm in CI |

The differential report and the mutation check were **not** re-run in Sprint 16 (they need the oracle's Python
dependencies). Regenerate all of these in CI with `./run.sh`.

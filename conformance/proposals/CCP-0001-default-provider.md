# CCP-0001: Default calendar provider of the contract is `umm-al-qura`

- **Author / date:** change author on the instruction of the requester, 2026-10-10
- **Class (GOVERNANCE.md section 2):** breaking (an omitted provider changes meaning), folded into the unreleased 2.0.0 draft
- **Questions or defects touched:** opens OQ-CAL-1; fixes a crash (`AttributeError` / HTTP 500) when a default-provider Hijri label is unavailable
- **Conventions touched (section 6):** the Hijri calendar convention; stays configurable: every provider remains selectable per call

## Problem
API 1.7.0 defaults to `umm-al-qura` (DR-0009) but the COP was silent and both adapters defaulted to `arithmetic-tabular`, as did `waqt-core`.

## Evidence
See DR-0010. Reproduce: `cd conformance && sh run.sh` (708 / 711 normative passes, 0 failures); `python tools/contract.py verify`.

## Proposed text
`spec/COP.md` section "Default calendar provider (CAL-012)"; `spec/requirements.json` CAL-012.

## Proposed vectors (ids, tiers)
`calendar-default.json`: 5 `hijri.*` (copies of normative CAL-005 vectors, provider omitted) and 2 DAY-004 label vectors, all `exact`. `open-questions.json`: 2 `open` vectors for OQ-CAL-1. Three DAY-004 vectors in `day-model.json` get an explicit `calendar.provider`; expected values unchanged.

## Forced-consensus test (section 5)
1. fact or convention? Convention (which calendar a project defaults to).
2. other conventions still reachable? Yes, by naming the provider.
3. more than one implementation / external reference? Two implementations agree on every normative vector; the official Umm al-Qura new-year dates are the external reference. They **disagree** outside the supported range (OQ-CAL-1), so that part is not forced.
4. would we propose this if the report were already clean? Yes: one project, one default.

## Migration note (breaking changes only)
Callers that relied on the implicit arithmetic-tabular default name it explicitly (`docs/migrations/API-1.7.0-default-provider.md`). Vectors that assert a Hijri value under another provider must name it.

## Review
Reviewer: **none (independent-implementation reviewer role unfilled)**. Outcome: pending. Dissent: none recorded.

# Contributing to Waqt

Waqt welcomes qualified experts and contributors — astronomers, Hijri-calendar scholars, standards engineers and
independent implementers especially. Ideas, proposals and questions: **waqtapi@gmail.com**.

## How changes are made
- The specification changes only through the process in [`conformance/GOVERNANCE.md`](conformance/GOVERNANCE.md):
  proposal → evidence → review → decision record → change (requirements, vectors and prose together, with a changelog entry).
- Decision records live in [`conformance/decisions/`](conformance/decisions/). A record is **accepted** only when a named maintainer
  ratifies it; at the time of writing DR-0001 to DR-0009 record ratification by the Maintainer named in `conformance/MAINTAINERS.md`, and the contract is still an unreleased draft.
- Open questions are tracked in `conformance/spec/open-questions.json`. Do not weaken a requirement to make a check pass.

## Code and tests
- Python: `pip install -e ./core -e . -e ./local`, then `python -m pytest tests/` (run `apps/*/tests` directories separately).
- Web: `cd apps/web/tools && npm install && python3 build_pages.py && npm run build:css`; tests are in `apps/web/tests`
  (`pytest apps/web/tests`, and `npm test` inside `apps/web/tests/js`).
- Waqt computes; applications display. Do not re-implement astronomy or calendar logic in an application.

## Never commit secrets
No tokens, API keys or credentials in code, configuration, documentation, fixtures or links.

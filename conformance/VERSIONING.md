# Versioning the conformance contract

The contract is versioned `MAJOR.MINOR.PATCH` and is **independent** of every other version axis in the project
(`docs/VERSIONING.md`): the package versions, the HTTP API version, the engine revision, the project's
"vector set" version and the COP version. Contract 2.0.0 is the first version that declares itself; Sprint 15's
state is retroactively 1.0.0.

## 1. What is versioned

| Part | File | In the contract hash? |
|---|---|---|
| Requirements | `spec/requirements.json` | yes |
| Vectors (all tiers) | `vectors/*.json` | yes |
| Unresolved-question registry | `spec/open-questions.json` | yes |
| Protocol | `spec/COP.md` (its own `COP` version) | yes |
| Known failures of the reference | `baselines/known-failures.json` | **no** (status, not contract); hashed separately in `contract.json` |
| Reports, decision records, proposals | `reports/`, `decisions/`, `proposals/` | no |

## 2. Bump rules

The classes and what is *breaking* are defined once, in `GOVERNANCE.md` section 2. In short:

| Change | Bump |
|---|---|
| Breaking (an implementation that conformed could now fail; accepted outcomes narrowed; expected value changed; requirement strengthened/removed/renumbered) | MAJOR |
| Promotion of an `open` question contradicting an answer a known implementation chose | MAJOR |
| Additive, or promotion no known implementation contradicts, or a band widened with a record | MINOR |
| Erratum (vector contradicted its requirement), tags, notes, new `informative`/`open` vectors | PATCH |
| Editorial | none |

**Worked example, 2.0.0.** `err/tz-unknown` accepted three codes (`VALIDATION_ERROR`, `UNKNOWN_TIMEZONE`,
`INVALID_TIMEZONE`) and now accepts one. The independent implementation returned `VALIDATION_ERROR` and had to be
changed. An accepted set was narrowed, so the release is MAJOR, however small the edit looks.

## 3. Conformance claims

A claim is always "conforms to contract X.Y.Z" and quotes the manifest hash (`contract.json`). A claim against an
older version remains a true statement about that version; it is never retroactively false. Reports print the
contract version, the hash and whether the files on disk still match it.

## 4. Release procedure

1. All CCPs for the release are closed; each has a decision record (ratified, or marked PENDING).
2. Requirements, vectors, prose and registry are consistent. `tools/contract.py verify` reports no problem.
3. `python3 tools/contract.py build` writes `contract.json` and an immutable copy
   `releases/contract-<version>.json`. **A released manifest is never rewritten**: `verify` fails if the files
   change while the version stays the same.
4. Run both implementations through the harness; commit the reports.
5. `baselines/known-failures.json` is updated *after* step 4, with a DIS id and decision record for every entry.
6. `CHANGELOG.md` has an entry for the version, listing every requirement and vector change and the decision
   records behind it, and says what is breaking.
7. Tag the repository `conformance-X.Y.Z`.

## 5. What `tools/contract.py verify` checks

- the manifest matches the files on disk, and a released manifest for this version is unchanged;
- every vector's requirement ids exist, and every requirement and decision it cites exists;
- every `resolved` question names an existing decision record;
- every `MUST` requirement with **no normative vector** is listed (declared but not enforced), never hidden;
- `CHANGELOG.md` mentions the current version; `known-failures.json` names the current contract.

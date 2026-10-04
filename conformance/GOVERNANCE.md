# Governance of the conformance contract

The *conformance contract* is the set of things an implementation is measured against:
`spec/requirements.json`, `vectors/*.json`, the normative sections of `docs/`, the COP (`spec/COP.md`) and the
registry of unresolved questions (`spec/open-questions.json`). `baselines/known-failures.json` is not part of the
contract; it records the *status* of the reference against it.

This document says who may change the contract, how, how disagreement is recorded, what counts as breaking, and
how religious and regional conventions stay configurable. It is deliberately short enough to apply.

## 1. Principles

1. **Written requirements govern; vectors illustrate.** A rule that exists only as vector behaviour is a defect in
   the specification (Sprint 15 measured 8 such rules in scheduling alone). A vector that contradicts its
   requirement is an *erratum*, not a new rule.
2. **A clean report is not a goal.** Never settle a question merely so the report shows fewer open items
   (section 5).
3. **Facts are normative; conventions are configurable.** (section 6)
4. **Every change leaves a trail:** proposal, decision record, changelog entry, new manifest.

## 2. What counts as what

| Class | Examples | Version bump | Needs a decision record |
|---|---|---|---|
| **Editorial** | typo, link, clearer wording that changes no outcome | none (PATCH if released) | no |
| **Erratum** | a vector's expected value contradicts the written requirement | PATCH | yes |
| **Additive** | new requirement or vectors for previously unspecified behaviour; new `informative`/`open` vectors; new unresolved question; a band *widened* with justification | MINOR | yes |
| **Promotion** | an `open` question settled and its vectors made normative | MINOR if no known implementation chose the other answer, otherwise MAJOR | yes |
| **Breaking** | see below | MAJOR | yes, plus a migration note |

**A change is breaking** if an implementation that conformed to the previous contract version could fail, or
change its reported verdict, without having changed. Concretely, any of:

- a normative (`exact`/`tolerance`) vector's expected value changes for an unchanged input;
- the set of accepted outcomes of a normative vector is **narrowed** (for example three accepted error codes
  become one);
- a tolerance band is narrowed;
- a requirement is strengthened, removed or renumbered;
- a COP operation, field or error code is removed or changes meaning;
- a promoted rule contradicts an answer a known implementation had chosen while the question was open.

Widening an accepted set or band is *not* breaking, but it loosens the contract and therefore needs a decision
record explaining why the looser contract is still meaningful.

## 3. How a change is made

1. **Propose.** Anyone opens `proposals/CCP-NNNN-<slug>.md` from `proposals/TEMPLATE.md`: the question, the
   evidence, the proposed text, the proposed vectors, the class from section 2, and which conventions it touches
   (section 6).
2. **Evidence.** A promotion needs measurements from **two independent implementations**, or an explicit
   statement of why only one exists. State what was *not* measured. "Both implementations agree" is weak evidence
   when both made the same unstated choice (Sprint 15 marked these *Shared*).
3. **Review.** At least one reviewer who is not the author. A CCP that changes vectors also needs the
   independent-implementation reviewer (MAINTAINERS.md). A proposal stays open at least 7 days unless the
   maintainer records an urgency reason.
4. **Decide.** Write `decisions/DR-NNNN.md` from `decisions/TEMPLATE.md`. Dissent is recorded in the record, in the
   dissenter's words, and is not deleted when it loses. A record is `Accepted` only when a named maintainer has
   ratified it; until then it says `Ratification: PENDING`.
5. **Change.** Edit the requirement, vectors and prose together; update the registry; add the entry to
   `CHANGELOG.md`.
6. **Release.** Follow `VERSIONING.md` section 4. `tools/contract.py verify` must pass.

Decision records are append-only: a later record supersedes an earlier one.

## 4. When sources disagree

- Requirement text versus vector: the text governs; fix the vector as an erratum (PATCH) with a record.
- Prose in `docs/` versus requirement title: this is a blocking inconsistency. Do not release; reconcile.
- Reference versus requirement: a **defect of the reference**. It is listed in `baselines/known-failures.json`
  with its DIS id, explained in `DISAGREEMENTS.md`, and the gate fails if it is hidden.
- Independent implementation versus requirement: a defect of the independent implementation, same treatment.
- Reference versus independent implementation, requirement silent: that is a **specification question**. It goes
  in the registry as unresolved. Neither implementation is declared right.

## 5. Disagreements and the rule against forced consensus

`DISAGREEMENTS.md` records every place where implementations differ or a result is decided by something other
than the specification, with a class: DEFECT-REF, DEFECT-IND, SPEC-Q, CONFIG, NUMERIC. Each entry must be
reproducible from a vector id or a report.

**Forced-consensus test.** Before promoting an open question, answer these. If any answer is "no", the question
stays open:

1. Is the answer a mathematical, astronomical or protocol fact, rather than a choice between conventions?
2. If it is a convention, does the proposal keep the other conventions reachable by configuration (section 6)?
3. Is there evidence from more than one implementation or an external reference?
4. Would the proposal still be made if the conformance report were already clean?

A question may be promoted to a **configuration point** instead of a single answer: the specification then fixes
what each named option means, not which is right.

Unresolved questions are **always printed** in the conformance report (count, ids, status). They are never removed
to shorten a report. An unresolved question carries one of three statuses:

| Status | Meaning |
|---|---|
| `deferred` | real, not yet scheduled; no position taken |
| `unresolved-by-design` | deliberately left open because the answer is institutional or religious, not technical |
| `resolved` | settled by a decision record; kept in the registry for traceability |

## 6. Religious, institutional and regional conventions

A choice is a *convention* when reasonable authorities differ on it. For these:

1. The choice must be a **named parameter, profile or provider**, never a constant in code.
2. The specification states the **default** and labels it "default", not "ruling". It fixes the *meaning* of each
   named option so results are reproducible; it does not say which option is correct.
3. A new option is a **new name** (a new provider id, a new profile value). Changing what an existing name means
   is a breaking change and needs a record.
4. Conformance vectors test that a named option means what it says. They do not test a preference.
5. If a convention cannot be reproduced from a written rule (for example an official table), the correct tool is
   a `declared` source fed from that authority, not a claim that the rule reproduces it.

Currently configurable by this rule: Fajr and Isha angles, the Asr shadow ratio, the calendar provider
(`arithmetic-tabular`, `umm-al-qura`, `declared`, `local-observation`, `aladhan`) and the high-latitude policy.
Currently *unresolved* by this rule: the Umm al-Qura computational conventions (OQ-UAQ-2) and the choice among
tabular patterns (OQ-TAB-3).

Mathematical and protocol facts, which are not conventions and may be normative: the civil-date label rule
(DR-0001), the occurrence semantics of `next_event` (DR-0003), the Asr declination convention (DR-0004), error
codes and their meaning.

## 7. Known failures

Every entry in `baselines/known-failures.json` needs a DIS id, a decision record or an open proposal, and an
entry in `DISAGREEMENTS.md`. The gate (`tests/test_conformance_suite.py`) fails on any normative failure that is
not listed, and on any listed failure that now passes, so the file cannot rot silently. At contract 2.0.0 the
file is empty.

## 8. Changing this document

This file is part of the contract's process, not its content. Changes need a decision record and take effect from
the next contract release.

# Waqt Conformance Specification v1.0

> Status: Sprint 15. Companion documents: [`COP.md`](COP.md) (the protocol), [`requirements.json`](requirements.json)
> (63 requirement IDs), [`OPEN-QUESTIONS.md`](OPEN-QUESTIONS.md), and [`../DISAGREEMENTS.md`](../DISAGREEMENTS.md).

## 1. What conformance means here

An implementation **conforms to Waqt** if, for every vector in the normative tiers, the adapter's answer
satisfies the vector, and every metamorphic relation holds. Conformance is a statement about *observable
behaviour* on the operations of COP; it does not depend on language, framework, or algorithm.

The suite exists to answer one question: **can the Waqt semantics be implemented from the written
specification alone?** It is therefore built so that it can *fail the specification*, not only an
implementation: wherever two readings of the text are defensible, the vector is tiered `open` and the
disagreement is recorded rather than silently resolved in favour of the first implementation.

## 2. Sources of expected values

Every vector states its `basis`:

| basis | meaning | trust |
|---|---|---|
| `spec` | derived by hand from the written specification | as good as the text |
| `closed-form` | computed by an independent closed-form formula (e.g. JDN arithmetic, Python `calendar`) | exact |
| `oracle` | JPL DE421 via Skyfield — a third party to **both** implementations | within oracle accuracy (< 0.2 s for the Sun) |
| `recorded` | the reference's own answer; used **only** for `informative`/`open` vectors | self-consistency, not truth |

No normative astronomy vector is derived from either implementation under test.

## 3. Requirement kinds

* `MUST` — normative; the written specification determines the answer.
* `OPEN` — the specification does **not** determine the answer. Vectors carry a *proposed* answer and are
  tier `open`: divergence is reported, never counted as failure. Each is catalogued in `OPEN-QUESTIONS.md`.

## 4. Vector tiers

| tier | decides conformance? | comparison |
|---|---|---|
| `exact` | yes | every expected leaf must match; instants compared to the microsecond |
| `tolerance` | yes | instants/numbers within the vector's declared band (§5) |
| `open` | no | reported as *diverges* |
| `informative` | no | provider-/data-dependent (e.g. Umm al-Qura month starts); reported with the agreement rate |

**Metamorphic checks** (`vectors/metamorphic.json`) assert relations between several calls and are
normative. They are the only place the *half-open* boundary semantics can be tested without knowing the
exact Maghrib instant in advance:

| kind | relations |
|---|---|
| `tiling` | an instant equal to the opening Maghrib is in this day at position 0; one unit earlier is in the previous day whose close equals this open; likewise at the closing Maghrib; length = close − open; position = instant − open; each event's reading = instant − open; closing Maghrib reading = length; Isha reading > length; the weekday label changes at Maghrib, not at civil midnight |
| `instant-invariance` | every instant inside a day yields identical day bounds and events |
| `profile-isolation` | changing the Fajr angle / Isha angle / Asr ratio moves only that event and never the day bounds |
| `provider-isolation` | changing the calendar provider changes only the Hijri label |
| `elevation-isolation` | elevation moves sunrise earlier and Maghrib later and nothing else |

## 5. Astronomy accuracy bands

The written spec states event *definitions* (`docs/ASTRONOMY.md`) but no accuracy requirement beyond
"agreement with a high-precision ephemeris". The bands below are the Sprint 15 proposal; they were chosen
from the project's own published accuracy statements (Level A "sub-10-second", high-latitude ~55–120 s) and
**not** tuned to either implementation's measured error.

| event | \|lat\| ≤ 45° | 45–55° | 55–60° | > 60° |
|---|---|---|---|---|
| sunrise, Maghrib, Dhuhr, Asr | 5 s | 5 s | 5 s | 20 s |
| Fajr, Isha | 10 s | 30 s | 30 s | 120 s |

Derived quantities (`day.length_seconds`, `position.seconds`, readings) are allowed the sum of the bands of
the instants they are differences of. Event **existence** (defined vs undefined) must agree with the oracle
except within `OPEN` requirement UND-004 (grazing events a few arc-minutes from the threshold).

## 6. Reporting

`harness/waqt_conform.py` writes, for every run:

* `reports/<name>.json` — every vector with verdict, tier, requirement IDs, first differences;
* `reports/<name>.md` — implementations, per-tier counts, **per-requirement status table**, failing
  normative vectors with expected/actual, and open/informative divergences.

A requirement's status is `PASS` (all its normative vectors pass), `FAIL`, `OPEN-ONLY` (only open or
informative evidence exists) or `NO-DATA`. The report never hides `n.a.`: a vector an adapter cannot run is
counted separately and is not a pass.

Reproduce with:

```
python3 conformance/harness/waqt_conform.py \
   --adapter "python3 conformance/adapters/reference_adapter.py" --label reference \
   --adapter "node conformance/independent/src/cli.mjs"          --label independent
```

## 7. Implementing Waqt independently — a checklist

1. Read `docs/SEMANTICS.md`, `TIME-MODEL.md`, `CALENDARS.md`, `SCHEDULING.md` — and **not** `waqt-core`.
2. Write an adapter that speaks COP (a few hundred lines; see `independent/src/cli.mjs`).
3. Run `waqt_conform.py` and read the per-requirement table.
4. For every failure decide: *your defect*, *the reference's defect*, or *the specification is ambiguous*.
   File the third kind in `OPEN-QUESTIONS.md` — those are the project's most valuable output.
5. Declare `shares_code_with_reference` truthfully in your descriptor.

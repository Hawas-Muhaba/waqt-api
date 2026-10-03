# Sprint 15 — Formal Conformance & Independent Implementation

**Base:** `waqt-api.rar` (Sprint 14 tree). **Nature of the sprint:** nothing in `waqt-core`, `waqt-api`, the SDKs or the frozen
Sprint 5–8 vector files was modified. Sprint 15 *adds* a portable conformance specification, a language-neutral harness, 700+
vectors, and a clean-room second implementation, then uses them to ask whether Waqt can be implemented from its written
specification. Engine revision, accuracy level, vector set and API contract are unchanged.

Environment: Python 3.12, Node 22.22, ephem 4.2.1, skyfield 1.55 + DE421 (as the oracle), pytest 9.1.1. Single CPU core. Sandbox clock 2026-10-02/03.

> **Headline.** From the written specification (plus the frozen vectors) a second implementation reached **0 normative failures
> on 663 vectors and 43 metamorphic relations**. The same suite finds **three genuine defects in the reference** and **26 places
> where the specification is silent or ambiguous** — six of which both implementations resolved identically *without the text
> requiring it*, which no cross-check can ever detect. The most important finding is not a number: the reference **labels the
> Waqt day with the wrong weekday and Hijri date at four of 24 sampled places** (§3.1).

## 0. Result at a glance

| Suite | before | after |
|---|---|---|
| core | 354 passed | **354 passed** (unchanged) |
| root (API, packaging, …) — as measured here | 562 passed, 1 skipped¹ | **562 passed**, 3 skipped (1 as before¹ + 2 new, env-gated) |
| independent implementation unit tests (`node --test`) | — | **13 passed** (incl. all 116 frozen scheduling vectors in table mode) |
| `tests/test_conformance_suite.py` (new regression gate, `WAQT_RUN_CONFORMANCE=1`) | — | **2 passed** (~40 s) |
| conformance suite: independent implementation | — | **663 normative pass / 0 fail**, 43/43 metamorphic |
| conformance suite: reference | — | **632 normative pass / 28 fail**, 43/43 metamorphic — all 28 explained by 3 defects (§3) |
| DE421 differential run (200 random cases + 141-point latitude sweep) | — | independent 0 disagreements; reference 21/200 label disagreements, 0 timing/existence |
| mutation check of the suite | — | see §5 |

¹ `tests/test_api_consumer_against_live_api.py` skips because `api_consumer` is not importable in this environment; the Sprint 14
report's "564" counts it. All other root tests pass.

Per-requirement status (63 requirements: 56 `MUST`, 7 `OPEN`): **independent 55 PASS / 8 OPEN-ONLY / 0 FAIL;
reference 51 PASS / 8 OPEN-ONLY / 4 FAIL** (`CAL-004`, `DAY-004`, `DAY-007`, `ERR-002`).

## 1. The six objectives

| # | Objective | Delivered | Where |
|---|---|---|---|
| 1 | Formalise the conformance suite | Protocol (COP v1.0: adapter I/O, 13 operations, error vocabulary, wire conventions, instant precision), conformance levels, vector tiers (`exact / tolerance / open / informative`), accuracy bands, 63 requirement IDs | `conformance/spec/` |
| 2 | Independent implementation | Zero-dependency Node.js, 1.5 kLoC: VSOP87D Sun, ELP-truncated Moon, scan-and-bisect event solver, µs-integer instants, ICU zones, own scheduling/institutional/provider-model code. No import of `waqt-core`, `waqt`, or `consumers/js` | `conformance/independent/` |
| 3 | Cross-implementation vectors | day boundaries (metamorphic tiling at 8 places), Hijri providers (tabular 16 dates + all 30 year-lengths, UAQ 4 anchors + 41-year sweep, declared/local/aladhan), high-latitude & undefined (11 latitudes × 3 dates), scheduling (116 table + 17 live + 7 defaults), calendar conversion, institutional (40), interop (21), provider failure (25) | `conformance/vectors/` |
| 4 | Semantic edge cases | closing Maghrib (reading = length, tiling), events after midnight (Reykjavik June), Waqt positions vs instants (µs-exact probes + invariance), provider failure (circuit, Retry-After cap, stale-if-error, window, 3-soft-failure) | `metamorphic.json`, `provider-failure.json`, `day-model.json` |
| 5 | Reproducible reporting | `waqt_conform.py` → JSON + Markdown with a per-requirement PASS/FAIL/OPEN-ONLY/NO-DATA table, per-tier counts, first differences for each failing vector; `./run.sh`; CI workflow; pytest gate; seeded differential tool | `harness/`, `reports/`, `run.sh`, `.github/workflows/conformance.yml` |
| 6 | Document disagreements | Register of 14 entries classified DEFECT-REF / SPEC-Q / CONFIG / NUMERIC, plus 26 open questions with the choice each implementation made | `conformance/DISAGREEMENTS.md`, `spec/OPEN-QUESTIONS.md` |

**The key boundary** ("do not make a second copy of the same architecture") is addressed in the design table in
`conformance/independent/README.md`: different astronomy method, different event-solving paradigm (scan-and-bisect vs closed
form), different time representation (integer µs), different zone database, different day-bracketing logic (by Maghrib *instants*,
not civil dates), a `DaySource` abstraction under scheduling, and a *model* — not a transport — for remote providers.
Whether that independence is *sufficient* is a judgement §4 tries to make with evidence rather than assertion.

## 2. What was built

```
conformance/
  spec/            CONFORMANCE.md  COP.md  OPEN-QUESTIONS.md  requirements.json
  DISAGREEMENTS.md  README.md  run.sh
  harness/         waqt_conform.py (runner+report)  differential.py (seeded DE421 differential + latitude sweep)
  adapters/        reference_adapter.py             (the only file touching reference internals)
  independent/     src/ (astro, calendar, day model, scheduling, institutional, interop, COP dispatcher)  test/  README.md
  vectors/         legacy-* (187 adopted)  day-model  calendar-*  provider-failure  errors  scheduling-live  scheduling-defaults  open-questions  gregorian-time  metamorphic
  tools/           build_vectors.py  import_legacy.py  requirements_catalog.py  build_requirements.py  mutation_check.py
  baselines/       known-failures.json
  reports/         conformance-report.{md,json}  differential-report.{md,json}  mutation-check.md
tests/test_conformance_suite.py     .github/workflows/conformance.yml     (README.md: 1 paragraph)
```

Every vector records its **basis**: `spec` (hand-derived), `closed-form` (JDN arithmetic / Python `calendar`), `oracle` (JPL DE421 via
Skyfield — a third party to both implementations) or `recorded` (the reference's own answer, allowed **only** for `open`/`informative`
vectors). No normative astronomy vector is derived from either implementation under test. The 187 legacy vectors are adopted unchanged
(one has two disputed label fields removed, see §3.1).

### Metamorphic checks (new idea in this sprint)
Half-open day semantics cannot be vector-tested across engines with independent astronomy, because two engines disagree about *where*
Maghrib is by 0.1–1 s. So the harness asks each implementation for its own `open`/`close` and then probes ±1 µs around them:
tiling, position = instant − open, reading = instant − open, closing-Maghrib reading = length, Isha reading > length, weekday flips at
Maghrib not at midnight, parameter isolation (Fajr/Isha/Asr change only their event; elevation moves only sunrise/Maghrib; provider
changes only the label), instant invariance, and calendar self-consistency (12 contiguous months of 29/30 days, round-trip). 43 checks.

## 3. Findings

### 3.1 Reference defects (documented, **not** fixed — see §6)
1. **DIS-001 — wrong day label at the date line and for after-midnight sunsets.** The reference labels a Waqt day with the date of its
   closing Maghrib in *longitude-based solar time*, not the civil date the spec (SEMANTICS §3, CALENDAR-INTEROP §1) requires.
   `gregorian-date-to-waqt` resolves **Sunday** 2026-09-20 at Kiritimati to a day that closes on 2026-09-20 yet labels it `1448-04-06 /
   as-Sabt`. The label is identical with `timezone=UTC`, which is how the cause was isolated. Affected in the 24-place sample:
   Kiritimati, Apia, Chatham, Reykjavik (June) — **21 of 200 random draws**. Unaffected places (Addis Ababa, Makkah, London, New York…)
   are why 14 sprints never saw it. The reference is also internally inconsistent: its own interop endpoint returns the day closing on
   the right civil date with the previous date's label. *Needs a maintainer ruling*: fix the reference (recommended) or amend the spec.
2. **DIS-002 — `to-gregorian` silently normalises a non-existent Hijri day.** `1448-02-30` (Safar has 29 days) → `2026-08-15`, i.e. 1
   Rabi al-Awwal; year 0 → `0621-07-30`. The institutional layer is protected (it validates by round-trip); the raw conversion is not.
3. **DIS-003 — unknown IANA zone → HTTP 500 `INTERNAL_ERROR`.** A client mistake presented as a server fault.

### 3.2 Specification gaps found by implementing it (`spec/OPEN-QUESTIONS.md`, 26 entries)
* **Scheduling lives partly in the vectors.** Written from `SCHEDULING.md` alone, the engine passed **108/116** frozen vectors at first
  contact. All 8 failures were prose gaps (the `inclusive` flag on `next_event`; default slot of `event_position`; `duration_seconds =
  null` on `NO_VALID_WINDOW`; `maghrib_boundaries: []` on `WINDOW_UNDEFINED`; which undefined slots are "relevant"; stepping *through* an
  undefined day), not algorithmic errors.
* **Shared assumptions — the dangerous class.** Both implementations (and the oracle) make the same unstated choice for: the
  tabular leap pattern (OQ-TAB-1), the declination used for Asr (OQ-ASR-1; measured to move Asr by **up to 5.9 s** — more than the
  proposed 5 s band), the whole-day-undefined rule (OQ-DAY-3), circuit/outbound-budget details (OQ-PRV-2/3), and Asr below the
  horizon (OQ-ASR-2). Cross-implementation agreement is *not* evidence about these.
* **API.md vs SCHEDULING.md disagree on `next_event`** (listing vs occurrence): right after Maghrib the reference's `/v1/waqt` skips
  tonight's Isha (OQ-EVT-1).
* Umm al-Qura: the written chain rule is enough to reproduce the four documented anchors and **490 of 492 reference month starts**
  (1420–1460). The two exceptions are evenings where the Moon sets **6.8 s and 3.7 s before the Sun** — DE421 gives the same margins,
  so no tolerance can resolve them; the rule would need to fix limb, refraction and observer-elevation conventions (OQ-UAQ-2). The
  chain's origin is irrelevant: 6-, 12-, 24-, 48- and 96-month burn-ins give identical starts for all 492 months.

### 3.3 Accuracy, measured against DE421 (200 random place/instant draws)
| | median | p95 | max |
|---|---|---|---|
| independent day-boundary error | 0.09 s | 0.13 s | 0.17 s |
| reference day-boundary error | 1.10 s | 3.20 s | 4.26 s |

The reference passes all 180 tolerance-tier vectors (it is inside the proposed bands) — the ~1 s systematic offset is documented
behaviour, and is the reason exact-boundary legacy vectors cannot be compared across engines (they are `informative`; DAY-002/003 are
tested metamorphically instead).

### 3.4 Defects in my own work that the suite caught (so you can calibrate trust)
* The first adapter-level run had the independent implementation at 31 normative failures: **22** were my own wiring bug (the AlAdhan
  scenario op returned the Hijri date in the `date` field), **9** were errors in my hand-written vectors (wrong weekday for
  2000-02-29/1600-02-29; a garbled fiscal-year-end formula; the Julian-vs-Gregorian epoch of year 622; an invariance probe that crossed
  Maghrib). I fixed vectors by recomputing them from independent oracles (Python `calendar`, JDN closed form), not by editing them to
  match either implementation.
* Reference adapter bugs of mine (dropped `elevation_m`, wrong `AcademicYear` attributes, wrong boundary-API arguments, error-code
  passthrough) initially looked like 36 extra reference "failures"; each was traced and fixed before the numbers above were taken.
* My day model initially **labelled by transit date**; the Reykjavik oracle case (Maghrib at 00:04 next civil day) exposed that, and
  also a bracketing bug for instants between local midnight and a post-midnight Maghrib. Both fixed; both now guarded by vectors.
* The 141-point latitude sweep showed a disagreement of **mine** (Asr at 67°N on 21 Dec, where the target altitude is degenerate). I
  changed the implementation *after* seeing the oracle/reference answer; that is recorded as OQ-ASR-2 rather than hidden.

## 4. How independent is "independent"? (read before citing it)
**Real:** no shared code; different language, astronomy theory, solver, time representation, zone database, day-bracketing logic.
Expected values for astronomy come from DE421. The two engines disagree with each other by 0.1–4 s in exactly the way their
different accuracy predicts, and the independent one agrees with DE421 to 0.2 s — it is not a re-skin of the reference.

**Not independent, and why it matters:**
* The same agent (me) wrote the harness, the reference adapter, the vectors and the independent implementation in one session. A human
  second team would not have seen the reference adapter's output shapes.
* To build the reference adapter I **read** parts of `waqt-core` (public entry points; the AlAdhan provider's transport interface and
  constants; month names and error codes via black-box probes). The Waqt-day model, astronomy, calendars and scheduling were written
  without consulting reference source; the **remote-provider model was written after seeing the reference provider's constants**, so
  `PRV-*` agreement is weak evidence.
* The scheduling engine's last 8 behaviours were learned from the frozen vectors, which are part of the specification but were
  generated by the reference.
* Node is the only second runtime available; a Go/Rust/Java port is the natural next test of language-level independence.
* Zone lookup from coordinates is not implemented (every location case carries an IANA zone).

## 5. Verifying the verifier
**Mutation check** (`tools/mutation_check.py`, `reports/mutation-check.md`): 14 single-rule breakages of the independent
implementation, each of which the suite must catch.

**14 of 14 mutants caught.**

| mutation | expected to violate | outcome | failing normative vectors |
|---|---|---|---|
| day interval closed at the opening Maghrib (<= becomes <) | DAY-002 | **CAUGHT** | 8 |
| label = transit date instead of civil date of the closing Maghrib instant | DAY-004 | **CAUGHT** | 4 |
| label date taken in UTC instead of the location's IANA zone | DAY-007 | **CAUGHT** | 12 |
| elevation dip ignored | EVT-006 | **CAUGHT** | 7 |
| Isha angle used for Fajr | EVT-005 | **CAUGHT** | 116 |
| Asr shadow ratio ignored | EVT-001 | **CAUGHT** | 9 |
| tabular epoch off by one day | CAL-001 | **CAUGHT** | 186 |
| stale-if-error disabled | PRV-004 | **CAUGHT** | 1 |
| circuit breaker never opens | PRV-005 | **CAUGHT** | 2 |
| Retry-After not capped | PRV-005 | **CAUGHT** | 1 |
| override fires on every date | CAL-008 | **CAUGHT** | 2 |
| polar day guessed (undefined Maghrib replaced by transit+6h) | UND-001 | **CAUGHT** | 35 |
| scheduling: window end treated as inclusive by default | SCH-002 | **CAUGHT** | 2 |
| fixed 86400 s day length reported | DAY-006 | **CAUGHT** | 123 |

**Differential run** (`harness/differential.py --n 200 --seed 15`, reproducible): independent: 0 disagreements with DE421; reference:
only the label defect. **Latitude sweep:** 0 of 141 (45°–68°N, three dates) where either implementation's set of defined events
differs from the oracle — after the Asr change in §3.4.

**Earlier mutation (found a gap, fixed):** the first mutation run let two mutants survive — "label date taken in UTC" was only
partly covered (the suite now has 12 vectors that catch it) and "default `end_inclusive`" was never exercised because every legacy
vector sets it explicitly (7 `scheduling-defaults` vectors added). Non-default astronomy profiles (Hanafi Asr, ISNA 15°, Egyptian
19.5°) were also absent from the day-model vectors until the mutation run showed "Asr ratio ignored" was caught only incidentally.

## 6. Behaviours you did not ask for (review these)
1. **Reference defects are documented, not fixed.** Each changes observable behaviour; DIS-001 also contradicts a frozen Sprint 5 vector.
   `baselines/known-failures.json` + the pytest gate make the failures visible and make a future *fix* a deliberate event (the gate
   fails with "update the baseline" when a known failure starts passing).
2. **The adopted copy of the legacy `kiritimati-date-line` vector has its `hijri`/`weekday` fields removed** (noted in the vector); the
   originals in `tests/vectors/` are untouched.
3. **Gate behind an env var.** `tests/test_conformance_suite.py` needs `WAQT_RUN_CONFORMANCE=1` (the root suite runs `slow` tests by
   default and this adds ~40 s plus a Node dependency). CI sets it.
4. New CI workflow `.github/workflows/conformance.yml`; one paragraph in `README.md`; one line in `.gitignore`.
5. Umm al-Qura range in the independent implementation was widened from 1900–2100 to 1700–2300 so that it does not manufacture
   disagreements outside a range the spec never defines.
6. **Proposed accuracy bands** (CONFORMANCE §5) are mine. They were taken from the project's published statements, not tuned to either
   implementation, but they are a proposal.
7. **Working-tree note.** Several files in your upload already differ from `git HEAD` (`SPRINT-14-REPORT.md`, two
   `independent-astronomy/vectors/*.json`, `verification/results/live_stack_check.json`, and `*.egg-info/PKG-INFO` files). I verified
   the first four are byte-identical to the archive and left them. My `pip install -r requirements.txt` had rewritten six
   `*.egg-info` files; those were restored from the archive.

## 7. Known limitations (honest list)
1. Language independence is partial (Node ↔ Python; no third runtime). `consumers/js` is also JavaScript though shares no code.
2. Independence in process is partial (§4). A human team would be a stronger test.
3. `waqt.compute` cannot be probed at the microsecond through the reference's `/v1/waqt` (it truncates instants to seconds); the
   harness probes ±1 second for implementations that declare `instant_precision_us`, and says so. µs-exact half-open behaviour is
   demonstrated by the independent implementation and (via legacy tests) by the library, not by the HTTP surface.
4. Umm al-Qura here is the *written rule*, not the official Saudi table; 2/492 month starts differ from the reference for numerical
   reasons that no tolerance resolves.
5. Accuracy bands are proposals; Asr's low-latitude convention sensitivity (5.9 s) is larger than the 5 s band.
6. Coordinate→time-zone lookup, `aladhan` network behaviour, and the HTTP/SDK/web layers are out of conformance scope.
7. The differential run samples 24 places × 3 years; it is a search, not a proof. `UND-004` (grazing events within minutes of a
   threshold) has no normative vectors by design.
8. The oracle itself (Skyfield + DE421) is trusted; the repo's Sprint 12/13 work established it, I did not re-validate it beyond a
   9-epoch Sun and 7-epoch Moon spot-check (≤0.5″ and ≤10″).

## 8. Definition of Done
| | |
|---|---|
| **Formal conformance** | ☑ portable protocol ☑ requirement catalogue (63) ☑ tiers + accuracy bands ☑ reporting spec |
| **Independent implementation** | ☑ no shared computation code ☑ different method at every layer listed in §1 ☑ passes 116/116 frozen scheduling vectors in table mode ☑ passes 663/663 normative vectors |
| **Vectors** | ☑ day boundaries ☑ Hijri provider differences ☑ high-latitude/undefined ☑ scheduling ☑ calendar conversion ☑ institutional ☑ provider failure |
| **Edge semantics** | ☑ closing Maghrib ☑ events after midnight ☑ positions vs instants ☑ provider failure |
| **Reproducibility** | ☑ one command ☑ seeded differential ☑ CI workflow ☑ pytest gate ☑ reports committed |
| **Disagreements** | ☑ classified register ☑ open questions with proposed answers ☑ shared assumptions flagged |
| **No regression** | ☑ core 354 ☑ root 562 ☑ no existing file changed except README/.gitignore |

## 9. Suggested Sprint 16 (decisions needed)
1. **Rule on DIS-001** and fix the reference (and the frozen vector) — or amend the spec. Highest value, smallest change.
2. Fix DIS-002/003 (a round-trip check; a 400 for unknown zones).
3. Fold OQ-SCH-1…5 into `SCHEDULING.md`; resolve OQ-EVT-1 between API.md and SCHEDULING.md; name the tabular leap pattern and the Asr
   declination convention; decide the Umm al-Qura conventions (OQ-UAQ-2).
4. Publish microsecond instants from `/v1/waqt` (or document the truncation).
5. A third implementation by a different person in a different language, run against this suite *before* seeing the reports.
6. Promote the `open` vectors to `exact` as the questions are answered; each answer is one line in `OPEN-QUESTIONS.md` and one tier change.

## 10. Reproduce
```
cd conformance && ./run.sh                                   # unit tests + both implementations -> reports/conformance-report.md
python3 harness/differential.py --n 200 --seed 15            # DE421 differential + latitude sweep
python3 tools/mutation_check.py                              # mutation check of the suite
WAQT_RUN_CONFORMANCE=1 pytest tests/test_conformance_suite.py
```

# Independent JavaScript consumer

Zero dependencies, Node >= 18, **no code shared with the Python reference**. It validates:

- `tests/vectors/waqt_vectors.json` (Sprint 5): half-open day membership, day length, positions and `HH:MM:SS` display (no 24 h ceiling), event ordering, boundary tiling, Asr isolation, elevation, UNDEFINED shape.
- `tests/vectors/scheduling_vectors.json` (Sprint 6): a full re-implementation of the scheduling semantics over each vector's embedded day table.

It deliberately does **not** recompute sunrise/Maghrib from coordinates — that is the solar engine's job, and checking a table of its own answers would be circular.

```
npm test        # 133 tests
```

# AT/BT Display Convention — Feature Specification

**Status:** Experimental — optional presentation convention (not a normative Waqt standard).  
**Governance:** Proposed, not ratified. Treatment as experimental per section 6 of the implementation brief.  
**Location:** `core/waqt_core/display/at_bt/`  
**Public interface:** `waqt_core.display.at_bt` (Python); CLI `--at-bt` flag (opt-in).

---

## 1. Purpose

AT/BT is a human-friendly 12-hour presentation of the canonical Waqt clock reading.

- **BT** = Before Twelve (00:00 through 11:59)
- **AT** = After Twelve (12:00 through 23:59)

This is purely a display convention. It does not alter canonical Waqt times, instants, prayer events, schedules, or day boundaries.

---

## 2. Mapping — standard range (00:00–23:59)

| Canonical hour | Period | Display hour | Example canonical | Example display |
|---|---|---|---|---|
| 00 | BT | 12 | `00:00` | `12:00 BT` |
| 01–11 | BT | hour as-is | `01:00` | `1:00 BT` |
| 12 | AT | 12 | `12:00` | `12:00 AT` |
| 13–23 | AT | hour − 12 | `17:50` | `5:50 AT` |

**Rules:**
- Hours 00–11 map to **BT** (Before Twelve).
- Hours 12–23 map to **AT** (After Twelve).
- Display hour = `hour % 12`, except that remainder 0 displays as 12.
- Minutes are preserved exactly.
- The period marker is always `AT` or `BT`.
- The leading zero is omitted from the display hour (e.g. `1:00`, not `01:00`).

---

## 3. Values beyond 24 hours (extended Waqt-day range)

Waqt time may in principle extend beyond `24:00` (e.g., a Waqt day that extends past midnight UTC). The formatter handles extended values as follows:

- The canonical total hours are divided by 24 to produce a **day offset** and an **hour within that day**.
- The day offset is preserved and rendered explicitly in the display string.
- A canonical value of `24:00` (exactly one day offset) → `12:00 BT (+1 day)`.
- A canonical value of `25:30` → `1:30 BT (+1 day)`.
- Values with a non-zero day offset are never silently wrapped or clamped.

**Negative values** (e.g., `-01:30`) map backward by one day (day offset = -1) using Python's flooring division semantics.

The formatted string is **not** round-trip reversible for values with non-zero day offsets when only the display string is available; callers requiring round-trip fidelity must retain the canonical `canonical` field on the returned `AtBtTime` object.

---

## 4. Validation

The following are rejected with explicit `TypeError` or `ValueError`:

- Non-string, non-numeric, non-`time`, non-`timedelta`, non-dict values.
- Strings that do not match `[sign]H...H:MM[:SS]` with valid minute/second ranges.
- `float('inf')`, `float('nan')`, and other non-finite floats when passed directly.
- Dict values that do not contain a usable string field.

---

## 5. Determinism

The conversion is purely arithmetic and is deterministic across all calls. It is independent of locale, system time, timezone, and any Waqt computation state.

---

## 6. Canonical input preservation

The `AtBtTime.canonical` field stores the original input representation unchanged. The `format_at_bt()` function never modifies the original value.

---

## 7. API opt-in

### Python (`waqt_core.display.at_bt`)

```python
from waqt_core.display.at_bt import format_at_bt, parse_at_bt, AtBtTime

# Simple string formatting
format_at_bt("00:00")   # "12:00 BT"
format_at_bt("17:50")   # "5:50 AT"
format_at_bt("24:15")   # "12:15 BT (+1 day)"

# Structured access
r = parse_at_bt("13:00")
r.hour     # 1
r.minute   # 0
r.period   # "AT"
str(r)     # "1:00 AT"
```

### CLI (`waqt` command)

Pass `--at-bt` to `waqt now` to add an AT/BT line to the human-readable output. JSON output (`--json`) is unaffected.

```bash
waqt now --lat 9.0192 --lon 38.7525 --at-bt
```

---

## 8. Governance note

This feature is **experimental** for this release. It is not included in the Conformance Contract 2.0.0. It does not represent a normative Waqt Standard ruling. Ratification of AT/BT as an official display convention would require a separate governance decision (DR-xxxx, to be proposed).

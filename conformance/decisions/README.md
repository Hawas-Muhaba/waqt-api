# Decision records

One file per ruling on the conformance contract. A decision record is created whenever a requirement, vector tier or
known failure changes meaning (GOVERNANCE.md section 3). Records are append-only: a later record supersedes an
earlier one, it does not edit it.

| Record | Ruling | Closes |
|---|---|---|
| [DR-0001](DR-0001.md) | Day label: civil date of the closing Maghrib instant | OQ-DAY-1 (resolved), DIS-001 (fixed), consequence rule DAY-009 |
| [DR-0002](DR-0002.md) | Event assignment and undefined bounding Maghribs | OQ-DAY-2, OQ-DAY-3 (resolved) |
| [DR-0003](DR-0003.md) | `next_event` is by occurrence | OQ-EVT-1 (resolved) |
| [DR-0004](DR-0004.md) | Asr: declination convention and undefined rule | OQ-ASR-1, OQ-ASR-2 (resolved) |
| [DR-0005](DR-0005.md) | `arithmetic-tabular`: leap pattern and identity | OQ-TAB-1 (resolved), OQ-TAB-2 and OQ-TAB-3 (open) |
| [DR-0006](DR-0006.md) | Errors for non-existent Hijri dates and unknown time zones | OQ-ERR-2, OQ-ERR-3 (resolved), DIS-002 and DIS-003 (fixed) |
| [DR-0007](DR-0007.md) | Umm al-Qura: range, chain, and what stays unresolved | OQ-UAQ-1 and OQ-UAQ-3 (resolved), OQ-UAQ-2 (UNRESOLVED BY DESIGN) |
| [DR-0008](DR-0008.md) | Scheduling rules that lived only in vectors | OQ-SCH-1 to OQ-SCH-5 (resolved) |
| [DR-0009](DR-0009.md) | Default Hijri provider of the HTTP API is `umm-al-qura` (API 1.7.0) | none (API-level; no contract requirement) |
| [DR-0010](DR-0010.md) | Default calendar provider of the contract and of waqt-core is `umm-al-qura` | CAL-012 (ratification PENDING) |
| [DR-0011](DR-0011.md) | ERR-004: astronomy profile parameters are validated, with explicit ranges | ERR-004 (decided by owner instruction; ratification evidence NOT held) |
| [DR-0012](DR-0012.md) | Out-of-range calendar dates never fail a Waqt computation (CAL-013) | OQ-CAL-1 (resolved; ratification evidence NOT held) |
| [DR-0013](DR-0013.md) | API contract version 1.8.0 for the next release | none (API versioning; ratification evidence NOT held) |

# Mutation check of the conformance suite

Each row breaks one rule in a copy of the independent implementation and re-runs the relevant suites.

| mutation | expected to violate | outcome | failing normative vectors | requirements reported failing |
|---|---|---|---|---|
| day interval closed at the opening Maghrib (<= becomes <) | DAY-002 | **CAUGHT** | 8 | DAY-001, DAY-002, DAY-003, DAY-004, DAY-005, EVT-002, EVT-003 |
| label = transit date instead of civil date of the closing Maghrib instant | DAY-004 | **CAUGHT** | 4 | DAY-004, DAY-007 |
| label date taken in UTC instead of the location's IANA zone | DAY-007 | **CAUGHT** | 12 | DAY-004, DAY-007 |
| elevation dip ignored | EVT-006 | **CAUGHT** | 7 | AST-001, DAY-001, DAY-005, DAY-006, DAY-007, EVT-001, EVT-002, EVT-006 |
| Isha angle used for Fajr | EVT-005 | **CAUGHT** | 116 | AST-001, DAY-001, DAY-005, DAY-006, DAY-007, EVT-001, EVT-002, EVT-004 |
| Asr shadow ratio ignored | EVT-001 | **CAUGHT** | 9 | AST-001, DAY-001, DAY-005, DAY-006, DAY-007, EVT-001, EVT-002, EVT-005 |
| tabular epoch off by one day | CAL-001 | **CAUGHT** | 187 | CAL-001, CAL-003, CAL-008, DAY-004, DAY-007, DAY-009, INS-003, PRV-002 |
| stale-if-error disabled | PRV-004 | **CAUGHT** | 1 | PRV-004 |
| circuit breaker never opens | PRV-005 | **CAUGHT** | 2 | PRV-005 |
| Retry-After not capped | PRV-005 | **CAUGHT** | 1 | PRV-005 |
| override fires on every date | CAL-008 | **CAUGHT** | 2 | CAL-008 |
| polar day guessed (undefined Maghrib replaced by transit+6h) | UND-001 | **CAUGHT** | 35 | AST-001, DAY-001, DAY-002, DAY-003, DAY-004, DAY-005, DAY-006, DAY-007 |
| scheduling: window end treated as inclusive by default | SCH-002 | **CAUGHT** | 2 | SCH-002 |
| fixed 86400 s day length reported | DAY-006 | **CAUGHT** | 123 | AST-001, DAY-001, DAY-002, DAY-003, DAY-004, DAY-005, DAY-006, DAY-007 |

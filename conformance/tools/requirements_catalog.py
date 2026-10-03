"""Single source of truth for conformance requirement IDs.  `python3 tools/build_vectors.py` writes
spec/requirements.json from this list; vectors may only cite IDs defined here.

kind:  MUST      normative: an implementation that disagrees is non-conformant
       OPEN      the written specification does not determine the answer (see spec/OPEN-QUESTIONS.md)
"""

R = []


def req(rid, kind, title, section):
    R.append({"id": rid, "kind": kind, "title": title, "section": section})


# --- instants, dates, Gregorian
req("TIME-001", "MUST", "Instants carry an explicit UTC offset; non-UTC offsets are normalised to UTC", "SEMANTICS 1; CALENDAR-INTEROP 4")
req("TIME-002", "OPEN", "Offset-less ('naive') instants: rejected, or assumed to be UTC", "API 7 (instant: 'ISO 8601 UTC')")
req("TIME-003", "MUST", "Malformed or non-existent instants/dates are rejected with INVALID_INSTANT / INVALID_DATE", "API errors")
req("GREG-001", "MUST", "Proleptic Gregorian leap-year rule (4 / 100 / 400)", "CALENDAR-INTEROP 3")
req("GREG-002", "MUST", "Weekday naming: ISO number and Sunday-first Islamic names", "CALENDAR-INTEROP 3")
req("GREG-003", "MUST", "Days in month", "CALENDAR-INTEROP 3")
# --- Waqt day model
req("DAY-001", "MUST", "A Waqt day is the half-open interval [Maghrib(D), Maghrib(D+1))", "SEMANTICS 2")
req("DAY-002", "MUST", "At the exact opening Maghrib the new day has begun (position 00:00:00)", "SEMANTICS 2")
req("DAY-003", "MUST", "One microsecond before a Maghrib belongs to the previous day; days tile without gap or overlap", "SEMANTICS 2")
req("DAY-004", "MUST", "The day label (Hijri date, weekday) is that of the civil date on which the CLOSING Maghrib falls", "SEMANTICS 3; TIME-MODEL")
req("DAY-005", "MUST", "Position is elapsed SI time since the opening Maghrib and is not clamped at 24:00:00", "SEMANTICS 4")
req("DAY-006", "MUST", "Day length is the real interval, not 86400 s", "SEMANTICS 4; TIME-MODEL")
req("DAY-007", "MUST", "Civil dates use the location's IANA zone (date line, DST) — not UTC and not solar time", "CALENDAR-INTEROP 1")
req("DAY-008", "MUST", "The Waqt day depends only on the instant: all instants inside a day give the same day and events", "TIME-MODEL")
# --- events
req("EVT-001", "MUST", "Event definitions: Fajr/Isha angles, sunrise/Maghrib -0.8333 deg, Dhuhr transit, Asr shadow ratio (accuracy bands in CONFORMANCE 5)", "ASTRONOMY")
req("EVT-002", "MUST", "An event's reading is its instant minus the day's opening Maghrib", "TIME-MODEL; SEMANTICS 5")
req("EVT-003", "MUST", "The closing Maghrib is listed at the day length; Isha is listed beyond the day length", "SCHEDULING 3")
req("EVT-004", "MUST", "Events after local midnight stay in the day of their transit (never move to the next civil date)", "TASK Sprint 15 (4); SEMANTICS 5")
req("EVT-005", "MUST", "Fajr/Isha angle and Asr ratio change only their own event, never the day boundary", "TIME-MODEL")
req("EVT-006", "MUST", "Elevation (dip) shifts sunrise and Maghrib only", "ASTRONOMY (Elevation)")
req("EVT-007", "OPEN", "waqt.compute next_event: by OCCURRENCE (includes tonight's Isha) or only among the listed events", "SCHEDULING 5 vs API")
# --- undefined
req("UND-001", "MUST", "Polar day/night (no Maghrib): status UNDEFINED with a reason, never a guessed time", "SEMANTICS 8; ASTRONOMY")
req("UND-002", "MUST", "An event that does not occur is omitted, never approximated; other events remain defined", "SEMANTICS 8")
req("UND-003", "MUST", "Both implementations must agree on WHICH events exist away from the transition latitude", "ASTRONOMY (Edge cases)")
req("UND-004", "OPEN", "Existence of grazing events within a few arc-minutes of their threshold", "ASTRONOMY (Edge cases)")
# --- calendars
req("CAL-001", "MUST", "arithmetic-tabular conversion Gregorian -> Hijri (epoch JDN 1948440)", "CALENDARS")
req("CAL-002", "OPEN", "arithmetic-tabular leap-year pattern within the 30-year cycle", "CALENDARS")
req("CAL-003", "MUST", "arithmetic-tabular reverse conversion is exact and round-trips", "CALENDARS")
req("CAL-004", "MUST", "Non-existent Hijri dates are rejected (INVALID_HIJRI_DATE), never silently normalised", "CALENDARS; INSTITUTIONAL 2")
req("CAL-005", "MUST", "umm-al-qura reproduces the validated New Year dates (1438, 1440, 1441, 1447)", "CALENDARS")
req("CAL-006", "MUST", "umm-al-qura months have 29 or 30 days and Gregorian<->Hijri round-trips", "CALENDARS")
req("CAL-007", "OPEN", "umm-al-qura month boundaries away from the validated anchors (threshold-sensitive months)", "CALENDARS (What this is not)")
req("CAL-008", "MUST", "declared / local-observation override applies only on the exact label date; otherwise tabular", "CALENDARS")
req("CAL-009", "MUST", "Providers without a fixed rule reject reverse conversion (UNSUPPORTED_OPERATION)", "CALENDARS")
req("CAL-010", "MUST", "Swapping the calendar provider changes only the label, never an instant or position", "TIME-MODEL; SCHEDULING 10")
req("CAL-011", "OPEN", "umm-al-qura supported range and the error returned outside it", "CALENDARS")
# --- provider failure
req("PRV-001", "MUST", "Hard remote failures (timeout, network error, 429, 5xx) fall back to local umm-al-qura with the stable reason code", "LIVE-INTEGRATIONS")
req("PRV-002", "MUST", "Soft failures (4xx, malformed, date-mismatch, implausible) fall back with the stable reason code", "LIVE-INTEGRATIONS")
req("PRV-003", "MUST", "Dates outside 1900-01-01..2076-12-31 and a disabled provider never leave the process", "LIVE-INTEGRATIONS")
req("PRV-004", "MUST", "Cache hit within the TTL; stale-if-error up to 7 days, labelled remote-stale", "LIVE-INTEGRATIONS")
req("PRV-005", "MUST", "Circuit breaker after a hard failure; Retry-After honoured and capped", "LIVE-INTEGRATIONS")
req("PRV-006", "MUST", "The fallback result names the provider that actually produced it", "LIVE-INTEGRATIONS")
req("PRV-007", "OPEN", "Soft-failure counting and outbound budget details", "LIVE-INTEGRATIONS")
# --- scheduling
req("SCH-001", "MUST", "Point resolution: instant, anchor, event slots, next/prev occurrence, position, offset, fraction", "SCHEDULING 2-4")
req("SCH-002", "MUST", "Windows are half-open; unbounded ends; inside/before/after relation", "SCHEDULING 4")
req("SCH-003", "MUST", "Deadlines: pending / reached / passed with signed remaining seconds", "SCHEDULING 5")
req("SCH-004", "MUST", "Three undefined statuses; strict vs skip policy; evaluate reports unknown, not false", "SCHEDULING 6")
req("SCH-005", "MUST", "Span classification: strict-interior Maghrib crossing, civil midnight independent", "SCHEDULING 7")
req("SCH-006", "MUST", "event_position reports listed and containing positions; next_event/until/since", "SCHEDULING 3, 5")
req("SCH-007", "MUST", "Derived instants use integer microseconds with half-up rounding", "SCHEDULING 9")
req("SCH-008", "MUST", "Scheduling over LIVE astronomy agrees with the table-driven result within astronomy tolerance", "SCHEDULING 9")
# --- institutional
req("INS-001", "MUST", "Calendar rules: month_day, month_end, nth_weekday_of_month", "INSTITUTIONAL 2")
req("INS-002", "MUST", "Islamic week: seven consecutive days from a configurable first day", "INSTITUTIONAL 3")
req("INS-003", "MUST", "Fiscal year resolves start/end rules; end before start is rejected", "INSTITUTIONAL 4")
req("INS-004", "MUST", "Academic year: opening, closing, terms, holidays", "INSTITUTIONAL 5")
req("INS-005", "MUST", "Unresolvable rules fail with INVALID_CALENDAR_RULE", "INSTITUTIONAL 8")
# --- interop
req("INT-001", "MUST", "Instant representation: UTC and civil Gregorian views of one instant, plus Waqt position", "CALENDAR-INTEROP 1, 4")
req("INT-002", "MUST", "Gregorian date + place -> the Waqt day whose closing Maghrib falls on that date", "CALENDAR-INTEROP 1")
req("INT-003", "MUST", "Boundary crossing: civil midnight and Maghrib independent; strictly-interior rule", "CALENDAR-INTEROP 2")
# --- errors
req("ERR-001", "MUST", "Out-of-range latitude/longitude is rejected", "API errors")
req("ERR-002", "MUST", "Unknown IANA time zone is rejected", "API errors")
req("ERR-003", "MUST", "Unknown calendar provider is rejected", "API errors")
req("ERR-004", "MUST", "Non-physical astronomy profile parameters are rejected", "API errors")

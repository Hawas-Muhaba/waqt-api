"""
Generates tests/vectors/scheduling_vectors.json from the Python
reference implementation. NOT hand-typed: every `expected` block is
the engine's own answer, frozen. Re-run after any intentional change to
waqt/scheduling and review the diff; never hand-edit the JSON.

Usage: python3 tests/vectors/generate_scheduling_vectors.py

WHAT MAKES THESE VECTORS PORTABLE
---------------------------------
Each vector carries a `context.days` DAY TABLE: consecutive Waqt days
around the anchor, each with its opening/closing Maghrib and its six
events (or nulls), exactly as the Python solar engine produced them.
An implementation in another language does not need any astronomy: it
reads the table, applies the scheduling semantics in docs/SCHEDULING.md,
and must reproduce `expected` exactly. This tests precisely the layer
Sprint 6 added — temporal rules over event positions — and nothing
else. (Astronomical accuracy is the separate concern of
waqt_vectors.json and docs/ASTRONOMY.md.)

Non-normative fields: `description` and `reason` strings are prose for
humans and are excluded from comparison. Everything else is normative
and compared exactly, including floating-point durations (both sides
derive them from the same integer microseconds).
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from zoneinfo import ZoneInfo

from waqt.calendar_providers import UmmAlQuraProvider
from waqt.calendar_providers.registry import ExampleRegionalOffsetProvider
from waqt.core import AstronomyProfile, Location
from waqt.hijri import ArithmeticTabularProvider
from waqt.scheduling import SchedulingContext, SchedulingEngine, day_to_table_entry, run_operation

UTC = timezone.utc
MICRO = timedelta(microseconds=1)
TABLE_BACK, TABLE_FWD = 3, 9

ADDIS = (9.0192, 38.7525, "Africa/Addis_Ababa")
LONDON = (51.5074, -0.1278, "Europe/London")
TROMSO = (69.6492, 18.9553, "Europe/Oslo")


def iso(dt):
    return dt.astimezone(UTC).isoformat()


def build_table(ctx, anchor):
    d0 = ctx.day_containing(anchor)
    back, cur = [], d0
    for _ in range(TABLE_BACK):
        if not cur.is_defined:
            break
        cur = ctx.neighbor(cur, -1)
        back.append(cur)
    fwd, cur = [], d0
    for _ in range(TABLE_FWD):
        if not cur.is_defined:
            break
        cur = ctx.neighbor(cur, 1)
        fwd.append(cur)
    days = list(reversed(back)) + [d0] + fwd
    return [day_to_table_entry(d, ctx) for d in days], len(back)


VECTORS = []


def add(vid, group, description, place, anchor, op, *, profile=None, provider=None, notes=None):
    lat, lon, tz = place
    profile = profile or AstronomyProfile()
    provider = provider or ArithmeticTabularProvider()
    ctx = SchedulingContext(Location(lat, lon), profile, provider)
    eng = SchedulingEngine(ctx)
    table, anchor_index = build_table(ctx, anchor)
    expected = run_operation(eng, anchor, op)

    # Every defined day the reference engine touched must be in the table,
    # otherwise the vector would not be reproducible from its own data.
    table_opens = {e["open"] for e in table if e["open"]}
    for d in ctx.known_days():
        assert iso(d.open) in table_opens, f"{vid}: engine used a day outside the table"

    offset = int(anchor.astimezone(ZoneInfo(tz)).utcoffset().total_seconds())
    VECTORS.append({
        "id": vid, "group": group, "description": description,
        **({"notes": notes} if notes else {}),
        "context": {
            "location": {"lat": lat, "lon": lon},
            "astronomy_profile": {"fajr_angle_deg": profile.fajr_angle_deg, "isha_angle_deg": profile.isha_angle_deg,
                                  "asr_shadow_ratio": profile.asr_shadow_ratio},
            "calendar_provider": provider.name,
            "civil_utc_offset_seconds": offset,
            "days": table, "anchor_index": anchor_index,
        },
        "anchor": iso(anchor),
        "operation": op,
        "expected": expected,
    })
    return eng, ctx


def ev(name, day=0):
    return {"type": "event", "name": name, "day": day}


def interval(start, end, si=True, ei=False):
    return {"type": "interval", "start": start, "end": end, "start_inclusive": si, "end_inclusive": ei}


def main():
    T0 = datetime(2026, 9, 19, 15, 42, tzinfo=UTC)
    ref_ctx = SchedulingContext(Location(ADDIS[0], ADDIS[1]))
    ref = SchedulingEngine(ref_ctx)

    def E(name, day=0, anchor=T0):
        return ref.resolve_point(__import__("waqt.scheduling", fromlist=["Event"]).Event(name, day), anchor).instant

    fajr, sunrise, maghrib, day_open = E("fajr"), E("sunrise"), E("maghrib"), E("day_start")
    isha = E("isha")

    # ---------------------------------------------------------------- points
    g = "points"
    for name in ("fajr", "maghrib", "isha", "day_start", "day_end"):
        add(f"point-event-{name}", g, f"Event({name}) on the anchor's Waqt day.", ADDIS, T0,
            {"op": "resolve_point", "point": ev(name)})
    add("point-event-previous-day", g, "Event(maghrib, -1): equals the anchor day's opening Maghrib.", ADDIS, T0,
        {"op": "resolve_point", "point": ev("maghrib", -1)})
    add("point-next-maghrib", g, "NextEvent(maghrib).", ADDIS, T0,
        {"op": "resolve_point", "point": {"type": "next_event", "name": "maghrib"}})
    add("point-prev-fajr", g, "PrevEvent(fajr).", ADDIS, T0,
        {"op": "resolve_point", "point": {"type": "prev_event", "name": "fajr"}})
    add("point-next-isha-just-after-maghrib", g,
        "Anchor 1 minute into the Waqt day: the next Isha is TONIGHT's (slot -1), not tomorrow's.", ADDIS,
        day_open + timedelta(minutes=1), {"op": "resolve_point", "point": {"type": "next_event", "name": "isha"}})
    add("point-next-maghrib-at-exact-maghrib-inclusive", g,
        "Anchor exactly at Maghrib; NextEvent is inclusive, so it is that very instant.", ADDIS, day_open,
        {"op": "resolve_point", "point": {"type": "next_event", "name": "maghrib"}})
    add("point-next-maghrib-at-exact-maghrib-exclusive", g,
        "Same anchor, inclusive=false: the following Maghrib, a full day later.", ADDIS, day_open,
        {"op": "resolve_point", "point": {"type": "next_event", "name": "maghrib", "inclusive": False}})
    add("point-prev-maghrib-at-exact-maghrib-inclusive", g,
        "PrevEvent(maghrib) at the exact Maghrib instant is that instant.", ADDIS, day_open,
        {"op": "resolve_point", "point": {"type": "prev_event", "name": "maghrib"}})
    add("point-position-one-hour", g, "Position(3600): one SI hour after the opening Maghrib.", ADDIS, T0,
        {"op": "resolve_point", "point": {"type": "position", "seconds": 3600}})
    add("point-position-beyond-day-length", g, "Position past the day's length is legal and flagged within_day=false.",
        ADDIS, T0, {"op": "resolve_point", "point": {"type": "position", "seconds": 90000}})
    add("point-offset-30-minutes-before-maghrib", g, "Offset sugar: minutes.", ADDIS, T0,
        {"op": "resolve_point", "point": {"type": "offset", "base": {"type": "next_event", "name": "maghrib"}, "minutes": -30}})
    add("point-offset-2-waqt-hours-after-prev-maghrib", g, "Offset sugar: waqt_hours (== SI hours).", ADDIS, T0,
        {"op": "resolve_point", "point": {"type": "offset", "base": {"type": "prev_event", "name": "maghrib"}, "waqt_hours": 2}})
    add("point-offset-fractional-seconds", g, "Half-up rounding to integer microseconds: 0.0000005 s -> 1 us.", ADDIS, T0,
        {"op": "resolve_point", "point": {"type": "offset", "base": {"type": "anchor"}, "seconds": 0.0000005}})
    add("point-fraction-last-third-of-night", g,
        "Fraction(2/3) between Maghrib and next Fajr. Which events bound 'night' is the CALLER's decision.", ADDIS, T0,
        {"op": "resolve_point", "point": {"type": "fraction", "start": ev("maghrib"), "end": ev("fajr", 1), "fraction": 2 / 3}})
    add("point-fraction-half", g, "Fraction(0.5): midpoint, exercising integer-microsecond half-up rounding.", ADDIS, T0,
        {"op": "resolve_point", "point": {"type": "fraction", "start": ev("fajr"), "end": ev("maghrib"), "fraction": 0.5}})
    add("point-absolute-instant", g, "Instant: basis absolute_instant.", ADDIS, T0,
        {"op": "resolve_point", "point": {"type": "instant", "value": "2026-09-19T20:00:00Z"}})
    add("point-derived-depends-on-two-bases", g, "Fraction of an Instant and an Event: rule_derived, depends on both.", ADDIS, T0,
        {"op": "resolve_point", "point": {"type": "fraction", "start": {"type": "instant", "value": iso(T0)}, "end": ev("dhuhr"), "fraction": 0.25}})

    # --------------------------------------------------------------- windows
    g = "windows"
    add("window-fajr-to-sunrise", g, "between(Fajr, Sunrise).", ADDIS, T0, {"op": "resolve_interval", "interval": interval(ev("fajr"), ev("sunrise"))})
    add("window-maghrib-to-isha", g, "between(Maghrib, Isha): straddles the Waqt-day boundary by construction.", ADDIS, T0,
        {"op": "resolve_interval", "interval": interval(ev("maghrib"), ev("isha"))})
    add("window-waqt-day", g, "[Maghrib(D), Maghrib(D+1)) as day_start..day_end.", ADDIS, T0,
        {"op": "resolve_interval", "interval": interval(ev("day_start"), ev("day_end"))})
    add("window-waqt-day-via-previous-maghrib", g, "Same window as maghrib(-1)..maghrib(0): identical instants.", ADDIS, T0,
        {"op": "resolve_interval", "interval": interval(ev("maghrib", -1), ev("maghrib", 0))})
    add("window-before-next-maghrib", g, "Unbounded start: before(NextEvent(maghrib)).", ADDIS, T0,
        {"op": "resolve_interval", "interval": interval(None, {"type": "next_event", "name": "maghrib"})})
    add("window-after-fajr", g, "Unbounded end: after(Fajr).", ADDIS, T0, {"op": "resolve_interval", "interval": interval(ev("fajr"), None)})
    add("window-within-2-waqt-hours-of-maghrib", g, "[PrevMaghrib, PrevMaghrib + 2 Waqt hours).", ADDIS, T0,
        {"op": "resolve_interval", "interval": interval({"type": "prev_event", "name": "maghrib"},
                                                        {"type": "offset", "base": {"type": "prev_event", "name": "maghrib"}, "waqt_hours": 2})})
    add("window-until-next-maghrib", g, "[anchor, NextEvent(maghrib)).", ADDIS, T0,
        {"op": "resolve_interval", "interval": interval({"type": "anchor"}, {"type": "next_event", "name": "maghrib"})})
    add("window-inverted-is-no-valid-window", g, "Both endpoints exist, but sunrise..fajr is backwards.", ADDIS, T0,
        {"op": "resolve_interval", "interval": interval(ev("sunrise"), ev("fajr"))})
    add("window-empty-half-open-is-no-valid-window", g, "start == end with [start, end): empty.", ADDIS, T0,
        {"op": "resolve_interval", "interval": interval(ev("dhuhr"), ev("dhuhr"))})
    add("window-empty-but-closed-is-valid", g, "start == end with [start, end]: exactly one instant.", ADDIS, T0,
        {"op": "resolve_interval", "interval": interval(ev("dhuhr"), ev("dhuhr"), True, True)})

    # ------------------------------------------------------ evaluate / boundaries
    g = "evaluate"
    win = interval(ev("fajr"), ev("sunrise"))
    for label, t in [("just-before-start", fajr - MICRO), ("at-start", fajr), ("inside", fajr + timedelta(minutes=5)),
                     ("just-before-end", sunrise - MICRO), ("at-end", sunrise), ("after-end", sunrise + timedelta(seconds=1))]:
        add(f"eval-fajr-sunrise-{label}", g, f"between(Fajr, Sunrise), tested {label.replace('-', ' ')}.", ADDIS, T0,
            {"op": "evaluate", "interval": win, "instant": iso(t)})
    before_m = interval(None, {"type": "next_event", "name": "maghrib"})
    after_m = interval({"type": "next_event", "name": "maghrib"}, None)
    m_next = ref.resolve_point(__import__("waqt.scheduling", fromlist=["NextEvent"]).NextEvent("maghrib"), T0).instant
    for label, t in [("one-microsecond-before", m_next - MICRO), ("exactly-at", m_next), ("one-second-after", m_next + timedelta(seconds=1))]:
        add(f"eval-before-maghrib-{label}", g, f"before(Maghrib), tested {label}. At exactly Maghrib: NOT before.", ADDIS, T0,
            {"op": "evaluate", "interval": before_m, "instant": iso(t)})
        add(f"eval-after-maghrib-{label}", g, f"after(Maghrib), tested {label}. At exactly Maghrib: after holds.", ADDIS, T0,
            {"op": "evaluate", "interval": after_m, "instant": iso(t)})
    add("eval-closed-interval-honours-flags", g, "(Fajr, Sunrise] tested at Fajr (excluded) — start_inclusive=false.", ADDIS, T0,
        {"op": "evaluate", "interval": interval(ev("fajr"), ev("sunrise"), False, True), "instant": iso(fajr)})
    add("eval-maghrib-isha-at-maghrib-with-fixed-anchor", g,
        "At the exact Maghrib the anchor's day flips; a FIXED anchor (T0) keeps Event(maghrib) meaning 'tonight's'.", ADDIS, T0,
        {"op": "evaluate", "interval": interval(ev("maghrib"), ev("isha")), "instant": iso(m_next)})

    # ----------------------------------------------------------------- deadlines
    g = "deadlines"
    for label, dt in [("pending", -90), ("reached", 0), ("passed", 90)]:
        add(f"deadline-next-maghrib-{label}", g, f"Deadline = NextEvent(maghrib); now = deadline {dt:+d}s.", ADDIS, T0,
            {"op": "check_deadline", "point": {"type": "next_event", "name": "maghrib"}, "now": iso(m_next + timedelta(seconds=dt))})
    add("deadline-event-plus-duration", g, "Deadline = Fajr + 10 minutes (a caller-chosen margin, not a ruling).", ADDIS, T0,
        {"op": "check_deadline", "point": {"type": "offset", "base": ev("fajr"), "minutes": 10}})
    add("deadline-end-of-waqt-day", g, "Deadline = end of the Waqt day.", ADDIS, T0, {"op": "check_deadline", "point": ev("day_end")})
    add("deadline-waqt-position", g, "Deadline = a Waqt position (12 SI hours into the day).", ADDIS, T0,
        {"op": "check_deadline", "point": {"type": "position", "seconds": 43200}})

    # ------------------------------------------------------------ until / since
    g = "until-since"
    add("until-maghrib", g, "How long until Maghrib?", ADDIS, T0, {"op": "until", "name": "maghrib"})
    add("until-maghrib-at-the-exact-instant-is-zero", g, "Inclusive: 0 at the event itself.", ADDIS, day_open, {"op": "until", "name": "maghrib"})
    add("until-maghrib-one-second-after-jumps-a-day", g, "One second after Maghrib the next one is ~a day away.", ADDIS,
        day_open + timedelta(seconds=1), {"op": "until", "name": "maghrib"})
    add("since-fajr", g, "How long since Fajr?", ADDIS, E("dhuhr"), {"op": "since", "name": "fajr"})
    add("since-fajr-before-todays-fajr-looks-back-a-day", g, "At 00:30 into the day, the last Fajr is the previous day's.", ADDIS,
        day_open + timedelta(minutes=30), {"op": "since", "name": "fajr"})
    add("until-isha-right-after-maghrib", g, "Tonight's Isha, not tomorrow's.", ADDIS, day_open + timedelta(minutes=1), {"op": "until", "name": "isha"})
    add("since-isha-early-in-the-day", g, "At 30 min into the day the last Isha was yesterday's (slot -2).", ADDIS,
        day_open + timedelta(minutes=30), {"op": "since", "name": "isha"})
    add("since-isha-after-tonights-isha", g, "At 3 h into the day, tonight's Isha is the last one.", ADDIS,
        day_open + timedelta(hours=3), {"op": "since", "name": "isha"})

    # ------------------------------------------------------------- event position
    g = "positions"
    add("event-position-isha-next", g, "Isha reported on both clocks: listed (25:xx) and containing (01:xx).", ADDIS, T0,
        {"op": "event_position", "name": "isha"})
    add("event-position-isha-listed-day-0", g, "Explicit slot: Isha listed on the anchor's own day.", ADDIS, T0,
        {"op": "event_position", "name": "isha", "day": 0})
    add("event-position-fajr", g, "Fajr: listed and containing positions coincide.", ADDIS, T0, {"op": "event_position", "name": "fajr"})
    add("event-position-maghrib", g, "Maghrib: listed at day length, containing at 00:00:00 of the next day.", ADDIS, T0,
        {"op": "event_position", "name": "maghrib", "day": 0})
    add("day-bounds", g, "When does the Islamic day begin and end?", ADDIS, T0, {"op": "day_bounds"})
    add("next-event", g, "What is the next astronomical event?", ADDIS, T0, {"op": "next_event"})
    add("next-event-before-dawn", g, "Before Fajr: the next event is Fajr, in the day's own position terms.", ADDIS, day_open + timedelta(hours=5),
        {"op": "next_event"})

    # ------------------------------------------------------------- span / Maghrib
    g = "spans"
    d_close = E("day_end")
    d_open = day_open
    add("span-inside-one-day", g, "Entirely inside one Waqt day.", ADDIS, d_open + timedelta(hours=2),
        {"op": "classify_span", "start": iso(d_open + timedelta(hours=2)), "end": iso(d_open + timedelta(hours=5))})
    add("span-crosses-maghrib", g, "One hour either side of Maghrib.", ADDIS, d_close - timedelta(hours=1),
        {"op": "classify_span", "start": iso(d_close - timedelta(hours=1)), "end": iso(d_close + timedelta(hours=1))})
    add("span-ends-exactly-at-maghrib", g, "Half-open: ending AT Maghrib does not cross it.", ADDIS, d_close - timedelta(hours=1),
        {"op": "classify_span", "start": iso(d_close - timedelta(hours=1)), "end": iso(d_close)})
    add("span-starts-exactly-at-maghrib", g, "Starting AT Maghrib lies wholly in the day it opens.", ADDIS, d_close,
        {"op": "classify_span", "start": iso(d_close), "end": iso(d_close + timedelta(hours=3))})
    add("span-end-inclusive-at-maghrib-crosses", g, "Instant-pair reading (end_inclusive): ending AT Maghrib counts as reaching the next day.", ADDIS,
        d_close - timedelta(hours=1),
        {"op": "classify_span", "start": iso(d_close - timedelta(hours=1)), "end": iso(d_close), "end_inclusive": True})
    add("span-three-days", g, "Three Maghrib boundaries inside.", ADDIS, d_open + timedelta(hours=1),
        {"op": "classify_span", "start": iso(d_open + timedelta(hours=1)), "end": iso(d_open + timedelta(days=3, hours=1))})
    a, b = datetime(2026, 9, 19, 20, 30, tzinfo=UTC), datetime(2026, 9, 19, 21, 30, tzinfo=UTC)
    add("span-2330-to-0030-civil-midnight-but-no-maghrib", g,
        "23:30 -> 00:30 local (Addis, UTC+3). Crosses CIVIL midnight; is one Waqt day.", ADDIS, a,
        {"op": "classify_span", "start": iso(a), "end": iso(b)})
    a, b = datetime(2026, 9, 19, 14, 30, tzinfo=UTC), datetime(2026, 9, 19, 16, 30, tzinfo=UTC)
    add("span-1730-to-1930-maghrib-but-no-civil-midnight", g, "17:30 -> 19:30 local. Crosses Maghrib; not civil midnight.", ADDIS, a,
        {"op": "classify_span", "start": iso(a), "end": iso(b)})
    add("span-inverted-no-valid-window", g, "end before start.", ADDIS, T0,
        {"op": "classify_span", "start": iso(T0 + timedelta(hours=1)), "end": iso(T0)})
    add("span-empty-half-open-no-valid-window", g, "start == end, half-open: empty.", ADDIS, T0,
        {"op": "classify_span", "start": iso(T0), "end": iso(T0)})
    add("span-single-instant-closed-is-valid", g, "start == end with end_inclusive: one instant.", ADDIS, T0,
        {"op": "classify_span", "start": iso(T0), "end": iso(T0), "end_inclusive": True})

    # ----------------------------------------------------------------- undefined
    g = "undefined"
    JUNE = datetime(2026, 6, 21, 12, 0, tzinfo=UTC)
    add("undef-london-fajr-event-undefined", g, "London midsummer: Fajr's angle is never reached.", LONDON, JUNE,
        {"op": "resolve_point", "point": ev("fajr")})
    add("undef-london-isha-event-undefined", g, "London midsummer: Isha likewise.", LONDON, JUNE, {"op": "resolve_point", "point": ev("isha")})
    add("undef-london-maghrib-still-fine", g, "Same day, Maghrib is defined: undefined-ness is per event.", LONDON, JUNE,
        {"op": "resolve_point", "point": ev("maghrib")})
    add("undef-london-window-fajr-sunrise", g, "WINDOW_UNDEFINED: one endpoint missing, causes attached.", LONDON, JUNE,
        {"op": "resolve_interval", "interval": interval(ev("fajr"), ev("sunrise"))})
    add("undef-london-window-maghrib-isha", g, "WINDOW_UNDEFINED via Isha.", LONDON, JUNE,
        {"op": "resolve_interval", "interval": interval(ev("maghrib"), ev("isha"))})
    add("undef-london-window-both-endpoints-fine", g, "Sunrise..Maghrib is unaffected.", LONDON, JUNE,
        {"op": "resolve_interval", "interval": interval(ev("sunrise"), ev("maghrib"))})
    add("undef-london-evaluate-is-unknown-not-false", g, "inside is null when the window is undefined.", LONDON, JUNE,
        {"op": "evaluate", "interval": interval(ev("fajr"), ev("sunrise")), "instant": iso(JUNE)})
    add("undef-london-before-fajr-unknown", g, "before(Fajr) with Fajr undefined: unknown.", LONDON, JUNE,
        {"op": "evaluate", "interval": interval(None, ev("fajr")), "instant": iso(JUNE)})
    add("undef-london-strict-until-fajr", g, "Strict: no answer rather than a Fajr weeks away.", LONDON, JUNE, {"op": "until", "name": "fajr"})
    add("undef-london-skip-until-fajr-finds-nothing", g, "Skip policy that finds nothing in range says NO_OCCURRENCE_IN_RANGE.", LONDON, JUNE,
        {"op": "until", "name": "fajr", "on_undefined": "skip"})
    lon_eng = SchedulingEngine(SchedulingContext(Location(LONDON[0], LONDON[1])))
    for i in range(0, 60):
        t = datetime(2026, 7, 18, 12, tzinfo=UTC) + timedelta(days=i)
        if lon_eng.until("fajr", t).status == "EVENT_UNDEFINED" and lon_eng.until("fajr", t, "skip").status == "OK":
            add("undef-london-strict-until-fajr-late-july", g, "End of the high-latitude gap, strict: still undefined.", LONDON, t,
                {"op": "until", "name": "fajr"})
            add("undef-london-skip-until-fajr-late-july", g, "Same anchor, skip: a later day's Fajr, with the skipped slots REPORTED.", LONDON, t,
                {"op": "until", "name": "fajr", "on_undefined": "skip"})
            break
    else:
        raise SystemExit("no London skip date found")
    add("undef-london-next-event-lists-undefined", g, "next_event skips non-occurring events but reports them.", LONDON,
        datetime(2026, 6, 21, 1, tzinfo=UTC), {"op": "next_event"})
    add("undef-london-event-position-fajr", g, "event_position of an undefined event.", LONDON, JUNE, {"op": "event_position", "name": "fajr"})
    POLAR = datetime(2026, 6, 21, 12, tzinfo=UTC)
    add("undef-tromso-day-undefined-point", g, "Polar day: the whole Waqt day is undefined.", TROMSO, POLAR, {"op": "resolve_point", "point": ev("maghrib")})
    add("undef-tromso-instant-window-still-resolves", g, "Windows made only of instants need no astronomy.", TROMSO, POLAR,
        {"op": "resolve_interval", "interval": interval({"type": "instant", "value": "2026-06-21T09:00:00Z"}, {"type": "instant", "value": "2026-06-21T10:00:00Z"})})
    add("undef-tromso-day-bounds", g, "day_bounds on an undefined day.", TROMSO, POLAR, {"op": "day_bounds"})
    add("undef-tromso-span", g, "classify_span across an undefined day: WINDOW_UNDEFINED.", TROMSO, POLAR,
        {"op": "classify_span", "start": iso(POLAR), "end": iso(POLAR + timedelta(hours=1))})
    LAST = datetime(2026, 5, 17, 12, tzinfo=UTC)
    add("undef-tromso-step-into-undefined-day", g, "Last defined day; Event(maghrib, +1) ARRIVES at the undefined day.", TROMSO, LAST,
        {"op": "resolve_point", "point": ev("maghrib", 1)})
    add("undef-tromso-step-across-undefined-day", g, "Event(maghrib, +2) would have to step THROUGH it.", TROMSO, LAST,
        {"op": "resolve_point", "point": ev("maghrib", 2)})
    add("undef-tromso-span-into-undefined-day", g, "A span that runs from a defined day into the polar one.", TROMSO, LAST,
        {"op": "classify_span", "start": iso(LAST), "end": iso(LAST + timedelta(days=2))})

    # ------------------------------------------------- profile: only Asr moves
    g = "profile-asr"
    for pid, ratio in (("standard", 1.0), ("hanafi", 2.0)):
        pr = AstronomyProfile(asr_shadow_ratio=ratio)
        add(f"profile-asr-{pid}-asr-point", g, f"Asr under ratio {ratio}.", ADDIS, T0, {"op": "resolve_point", "point": ev("asr")}, profile=pr)
        add(f"profile-asr-{pid}-maghrib-isha-window", g, "A window not involving Asr.", ADDIS, T0,
            {"op": "resolve_interval", "interval": interval(ev("maghrib"), ev("isha"))}, profile=pr)
        add(f"profile-asr-{pid}-dhuhr-asr-window", g, "A window that does involve Asr.", ADDIS, T0,
            {"op": "resolve_interval", "interval": interval(ev("dhuhr"), ev("asr"))}, profile=pr)
        add(f"profile-asr-{pid}-day-bounds", g, "The day itself does not move.", ADDIS, T0, {"op": "day_bounds"}, profile=pr)

    # --------------------------------------------- calendar-provider substitution
    g = "calendar-substitution"
    base = ArithmeticTabularProvider()
    for pid, prov in (("arithmetic-tabular", base), ("umm-al-qura", UmmAlQuraProvider()),
                      ("regional-offset", ExampleRegionalOffsetProvider(wrapped=base, day_offset=1))):
        add(f"calendar-{pid}-window", g, f"between(Maghrib, Isha) under {pid}.", ADDIS, T0,
            {"op": "resolve_interval", "interval": interval(ev("maghrib"), ev("isha"))}, provider=prov)
        add(f"calendar-{pid}-span", g, f"classify_span across Maghrib under {pid}.", ADDIS, d_close - timedelta(hours=1),
            {"op": "classify_span", "start": iso(d_close - timedelta(hours=1)), "end": iso(d_close + timedelta(hours=1))}, provider=prov)
        add(f"calendar-{pid}-day-bounds", g, f"day_bounds under {pid} (the only place a label is copied through).", ADDIS, T0,
            {"op": "day_bounds"}, provider=prov)

    out = {
        "spec": "waqt-scheduling/0.1",
        "vector_format_version": "1.0",
        "generated_by": "waqt-python-reference (tests/vectors/generate_scheduling_vectors.py)",
        "note": (
            "Each vector's context.days is a DAY TABLE: the solar engine's output for consecutive Waqt days, frozen as data, "
            "so a consumer needs no astronomy. Compare `expected` exactly, ignoring only the non-normative prose fields "
            "`description` and `reason`. Instants are ISO 8601 UTC with up to microsecond precision; derived instants use "
            "integer microseconds with floor(x + 0.5) rounding. See docs/SCHEDULING.md section 9."
        ),
        "vectors": VECTORS,
    }
    path = Path(__file__).parent / "scheduling_vectors.json"
    path.write_text(json.dumps(out, indent=1) + "\n")
    print(f"Wrote {len(VECTORS)} vectors to {path} ({path.stat().st_size // 1024} KiB)")


if __name__ == "__main__":
    main()

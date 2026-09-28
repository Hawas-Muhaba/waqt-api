"""
Sprint 6 test suite — waqt.scheduling.

Organised around the sprint's test targets. Each section names the
brief item it proves. Where a test asserts something about the real
astronomy it uses a real place and date, never a stub.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest

from waqt.calendar_providers import UmmAlQuraProvider
from waqt.calendar_providers.registry import ExampleRegionalOffsetProvider
from waqt.core import AstronomyProfile, Location
from waqt.hijri import ArithmeticTabularProvider
from waqt.scheduling import (
    Anchor, Event, Fraction, Instant, Interval, NextEvent, Offset, Position, PrevEvent, RuleError, SchedulingContext,
    SchedulingEngine, Status, UndefinedPolicy, after, before, between, interval_from_dict, point_from_dict,
    until_next, waqt_hours, within, within_day,
)
from waqt.scheduling.model import DAY_SHIFT, EVENT_NAMES, from_micros, to_micros
from waqt.semantics import crosses_maghrib

UTC = timezone.utc
ADDIS = Location(9.0192, 38.7525)
LONDON = Location(51.5074, -0.1278)
T0 = datetime(2026, 9, 19, 15, 42, tzinfo=UTC)          # Addis, just after Maghrib
LONDON_JUNE = datetime(2026, 6, 21, 12, 0, tzinfo=UTC)  # Maghrib/sunrise defined; Fajr & Isha are not
TROMSO_LAST_DEFINED = datetime(2026, 5, 17, 12, 0, tzinfo=UTC)   # next Waqt day is polar-UNDEFINED


def engine(loc=ADDIS, **kw) -> SchedulingEngine:
    return SchedulingEngine(SchedulingContext(loc, **kw))


def at(eng, point, anchor=T0):
    r = eng.resolve_point(point, anchor)
    assert r.ok, (r.status, r.reason)
    return r.instant


# ---------------------------------------------------------------------------
# Foundations: the layer sits on Sprint 5's semantics without contradicting it
# ---------------------------------------------------------------------------

def test_event_refs_agree_with_semantics_layer():
    eng = engine()
    day = eng.ctx.day_containing(T0)
    for name in EVENT_NAMES:
        assert at(eng, Event(name)) == day.event(name).instant
    assert at(eng, Event("day_start")) == day.open
    assert at(eng, Event("day_end")) == day.close == at(eng, Event("maghrib"))


def test_days_tile_the_timeline():
    """Previous day's close == this day's open, for several steps either way."""
    eng = engine()
    d0 = eng.ctx.day_containing(T0)
    for k in range(-4, 5):
        a, b = eng.ctx.neighbor(d0, k), eng.ctx.neighbor(d0, k + 1)
        assert a.close == b.open


def test_previous_maghrib_slot_equals_this_days_start():
    eng = engine()
    assert at(eng, Event("maghrib", -1)) == at(eng, Event("day_start"))


@pytest.mark.parametrize("lat,lon", [(9.0, 38.7), (21.4, 39.8), (51.5, -0.13), (1.87, -157.43),
                                     (-33.9, 151.2), (35.7, 139.7), (-41.3, 174.8), (40.7, -74.0),
                                     (59.9, 10.7), (-1.3, 36.8), (1.4, 173.0), (-17.7, -149.4)])
def test_day_shift_invariant_holds_across_the_year(lat, lon):
    """The invariant Next/Prev search depends on, under the STRICT half-open rule:
    fajr/sunrise/dhuhr/asr fall inside their listed day; Maghrib (its closing
    boundary) and Isha fall in the NEXT day. Includes date-line places."""
    eng = engine(Location(lat, lon))
    for doy in range(0, 365, 9):
        t = datetime(2026, 1, 1, 12, tzinfo=UTC) + timedelta(days=doy)
        day = eng.ctx.day_containing(t)
        if not day.is_defined:
            continue
        nxt = eng.ctx.neighbor(day, 1)
        for name in EVENT_NAMES:
            try:
                inst = day.event(name).instant
            except Exception:
                continue
            if DAY_SHIFT.get(name, 0) == 0:
                assert day.open <= inst < day.close, (name, t)
            else:
                assert nxt.is_defined and nxt.open <= inst < nxt.close, (name, t)


# ---------------------------------------------------------------------------
# Brief item 1: temporal windows
# ---------------------------------------------------------------------------

def test_between_fajr_and_sunrise():
    eng = engine()
    w = eng.resolve_interval(between(Event("fajr"), Event("sunrise")), T0)
    assert w.ok
    assert w.start.instant == at(eng, Event("fajr")) and w.end.instant == at(eng, Event("sunrise"))
    assert 3000 < w.duration_seconds < 5000        # ~70 min at Addis in September
    assert w.start_inclusive and not w.end_inclusive


def test_between_maghrib_and_isha_straddles_the_waqt_day_boundary():
    """[Maghrib, Isha): Isha is in the day AFTER the one that lists it."""
    eng = engine()
    w = eng.resolve_interval(between(Event("maghrib"), Event("isha")), T0)
    assert w.ok and 3000 < w.duration_seconds < 6000
    span = eng.classify_span(w.start.instant, w.end.instant)
    assert span.same_waqt_day is True   # entirely inside the NEW day that Maghrib opens
    day0 = eng.ctx.day_containing(T0)
    assert w.start.instant == day0.close   # window begins exactly at day 0's closing Maghrib


def test_the_waqt_day_as_a_window_is_maghrib_to_maghrib():
    eng = engine()
    a = eng.resolve_interval(within_day(0), T0)
    b = eng.resolve_interval(between(Event("maghrib", -1), Event("maghrib", 0)), T0)
    assert a.ok and b.ok
    assert (a.start.instant, a.end.instant) == (b.start.instant, b.end.instant)
    day = eng.ctx.day_containing(T0)
    assert a.duration_seconds == (day.close - day.open).total_seconds()


def test_explicit_instant_windows_need_no_astronomy_at_all():
    eng = engine(Location(69.6492, 18.9553))   # polar, but nothing here touches events
    a, b = datetime(2026, 6, 21, 9, tzinfo=UTC), datetime(2026, 6, 21, 10, tzinfo=UTC)
    w = eng.resolve_interval(between(Instant(a), Instant(b)), LONDON_JUNE)
    assert w.ok and w.duration_seconds == 3600.0


# ---------------------------------------------------------------------------
# Brief items 2 & 3: deadlines and relative rules
# ---------------------------------------------------------------------------

def test_before_maghrib_predicate():
    eng = engine()
    m = at(eng, NextEvent("maghrib"))
    rule = before(NextEvent("maghrib"))
    assert eng.evaluate(rule, m - timedelta(seconds=1), anchor=T0).inside is True
    assert eng.evaluate(rule, m, anchor=T0).inside is False            # exact boundary: not before
    assert eng.evaluate(rule, m + timedelta(seconds=1), anchor=T0).inside is False


def test_after_maghrib_predicate_is_inclusive_at_the_boundary():
    eng = engine()
    m = at(eng, NextEvent("maghrib"))
    rule = after(NextEvent("maghrib"))
    assert eng.evaluate(rule, m - timedelta(microseconds=1), anchor=T0).inside is False
    assert eng.evaluate(rule, m, anchor=T0).inside is True             # at Maghrib, the new day has begun
    assert eng.evaluate(rule, m + timedelta(hours=1), anchor=T0).inside is True


def test_before_and_after_are_exact_complements():
    eng = engine()
    m = at(eng, NextEvent("maghrib"))
    for dt in (-3600, -1, 0, 1, 3600):
        t = m + timedelta(seconds=dt)
        b = eng.evaluate(before(NextEvent("maghrib")), t, anchor=T0).inside
        a = eng.evaluate(after(NextEvent("maghrib")), t, anchor=T0).inside
        assert a != b


def test_until_maghrib_duration():
    eng = engine()
    m = eng.until("maghrib", T0)
    assert m.status == Status.OK
    day = eng.ctx.day_containing(T0)
    assert m.seconds == (day.close - T0).total_seconds()
    assert m.target.basis == "astronomical_event"


def test_until_is_zero_at_the_exact_event_and_targets_the_next_one_after():
    eng = engine()
    mag = at(eng, Event("maghrib"))
    assert eng.until("maghrib", mag).seconds == 0.0                     # inclusive
    later = eng.until("maghrib", mag + timedelta(seconds=1))
    assert later.target.instant > mag and later.seconds > 86000          # next day's Maghrib


def test_since_fajr():
    eng = engine()
    t = at(eng, Event("dhuhr"))
    s = eng.since("fajr", t)
    assert s.status == Status.OK and s.seconds == (t - at(eng, Event("fajr"))).total_seconds()


def test_since_isha_looks_back_into_the_previous_listing():
    """At 00:30 into a Waqt day, the most recent Isha is the one listed on the PREVIOUS day."""
    eng = engine()
    day = eng.ctx.day_containing(T0)
    t = day.open + timedelta(minutes=30)      # before tonight's Isha -> last Isha was yesterday's
    s = eng.since("isha", t)
    assert s.status == Status.OK and 80000 < s.seconds < 86400
    t2 = day.open + timedelta(hours=3)        # after tonight's Isha
    assert eng.since("isha", t2).seconds < 3 * 3600


def test_until_next_isha_immediately_after_maghrib_is_tonights_not_tomorrows():
    eng = engine()
    day = eng.ctx.day_containing(T0)
    u = eng.until("isha", day.open + timedelta(minutes=1))
    assert 0 < u.seconds < 2 * 3600


def test_thirty_minutes_before_maghrib_and_two_hours_after():
    eng = engine()
    m = at(eng, NextEvent("maghrib"))
    p = eng.resolve_point(Offset(NextEvent("maghrib"), -1800), T0)
    q = eng.resolve_point(Offset(PrevEvent("maghrib"), waqt_hours(2)), T0)
    assert p.instant == m - timedelta(minutes=30)
    assert p.basis == "rule_derived" and p.depends_on == ("astronomical_event",)
    assert q.instant == at(eng, PrevEvent("maghrib")) + timedelta(hours=2)


def test_within_n_waqt_hours_after_an_event():
    eng = engine()
    rule = within(PrevEvent("maghrib"), waqt_hours(2))
    day = eng.ctx.day_containing(T0)
    w = eng.resolve_interval(rule, T0)
    assert w.duration_seconds == 7200.0 and w.start.instant == day.open
    assert eng.evaluate(rule, day.open + timedelta(hours=1, minutes=59), anchor=T0).inside is True
    assert eng.evaluate(rule, day.open + timedelta(hours=2), anchor=T0).inside is False


def test_until_next_maghrib_window_is_anchor_to_next_maghrib():
    eng = engine()
    w = eng.resolve_interval(until_next("maghrib"), T0)
    assert w.ok and w.start.instant == T0 and w.end.instant == at(eng, NextEvent("maghrib"))
    assert w.start.basis == "absolute_instant"


def test_position_point_is_seconds_after_opening_maghrib():
    eng = engine()
    day = eng.ctx.day_containing(T0)
    r = eng.resolve_point(Position(3600), T0)
    assert r.instant == day.open + timedelta(hours=1)
    assert r.basis == "waqt_position" and r.within_day is True
    beyond = eng.resolve_point(Position(day.close.timestamp() - day.open.timestamp() + 60), T0)
    assert beyond.ok and beyond.within_day is False          # legal (hours can pass 24), flagged, not rejected


def test_fraction_expresses_a_rule_without_the_library_defining_night():
    """'Last third of the night' as pure composition. Which events bound the
    night is the caller's decision — Fraction only does the arithmetic."""
    eng = engine()
    start, end = Event("maghrib"), Event("fajr", 1)
    p = eng.resolve_point(Fraction(start, end, 2 / 3), T0)
    a, b = at(eng, start), at(eng, end)
    assert p.ok and abs((p.instant - a).total_seconds() - (b - a).total_seconds() * 2 / 3) < 1e-5
    assert p.basis == "rule_derived"


def test_basis_classification_is_explicit_for_all_four_kinds():
    eng = engine()
    kinds = {
        "absolute_instant": Instant(T0),
        "astronomical_event": Event("dhuhr"),
        "waqt_position": Position(100),
        "rule_derived": Offset(Position(100), 5),
    }
    for expected, p in kinds.items():
        assert eng.resolve_point(p, T0).basis == expected
    d = eng.resolve_point(Fraction(Instant(T0), Event("dhuhr"), 0.5), T0)
    assert d.basis == "rule_derived" and set(d.depends_on) == {"absolute_instant", "astronomical_event"}


def test_deadline_states_pending_reached_passed():
    eng = engine()
    m = at(eng, NextEvent("maghrib"))
    p = NextEvent("maghrib")
    pending = eng.check_deadline(p, T0, now=m - timedelta(seconds=90))
    reached = eng.check_deadline(p, T0, now=m)
    passed = eng.check_deadline(p, T0, now=m + timedelta(seconds=90))
    assert (pending.state, pending.remaining_seconds) == ("pending", 90.0)
    assert (reached.state, reached.remaining_seconds) == ("reached", 0.0)
    assert (passed.state, passed.remaining_seconds) == ("passed", -90.0)


def test_deadline_end_of_waqt_day_and_event_plus_duration():
    eng = engine()
    end_of_day = eng.check_deadline(Event("day_end"), T0)
    plus = eng.check_deadline(Offset(Event("fajr"), 600), T0)
    assert end_of_day.state == "pending" and plus.state == "pending"
    assert plus.deadline.instant == at(eng, Event("fajr")) + timedelta(minutes=10)


# ---------------------------------------------------------------------------
# Brief item 4: scheduling across Maghrib
# ---------------------------------------------------------------------------

def _day(eng, t=T0):
    return eng.ctx.day_containing(t)


def test_span_entirely_inside_one_waqt_day():
    eng = engine()
    d = _day(eng)
    s = eng.classify_span(d.open + timedelta(hours=2), d.open + timedelta(hours=5))
    assert (s.status, s.same_waqt_day, s.crosses_maghrib, s.waqt_days_touched) == (Status.OK, True, False, 1)
    assert s.maghrib_boundaries == ()


def test_span_crossing_maghrib():
    eng = engine()
    d = _day(eng)
    s = eng.classify_span(d.close - timedelta(hours=1), d.close + timedelta(hours=1))
    assert s.crosses_maghrib and not s.same_waqt_day and s.waqt_days_touched == 2
    assert s.maghrib_boundaries == (d.close,)
    assert s.start_day["hijri_label"] != s.end_day["hijri_label"]   # the label changes at Maghrib, as designed


def test_span_ending_exactly_at_maghrib_does_not_cross():
    """Half-open: the span never includes its own end instant."""
    eng = engine()
    d = _day(eng)
    s = eng.classify_span(d.close - timedelta(hours=1), d.close)
    assert s.same_waqt_day is True and s.crosses_maghrib is False and s.maghrib_boundaries == ()


def test_span_starting_exactly_at_maghrib_lies_in_the_day_it_opens():
    eng = engine()
    d = _day(eng)
    s = eng.classify_span(d.close, d.close + timedelta(hours=3))
    assert s.same_waqt_day is True
    assert s.start_day["open"] == d.close.isoformat()


def test_end_inclusive_matches_the_instant_pair_crosses_maghrib():
    """`classify_span(end_inclusive=True)` is the instant-pair reading and must
    agree with Sprint 5's crosses_maghrib() — including the exact-boundary case."""
    eng = engine()
    d = _day(eng)
    for a, b in [
        (d.close - timedelta(hours=1), d.close),                       # b == Maghrib
        (d.close - timedelta(hours=1), d.close - timedelta(seconds=1)),
        (d.close, d.close + timedelta(hours=1)),                       # a == Maghrib
        (d.open + timedelta(hours=1), d.close + timedelta(hours=1)),
    ]:
        s = eng.classify_span(a, b, end_inclusive=True)
        assert s.crosses_maghrib == crosses_maghrib(a, b, ADDIS.lat, ADDIS.lon)


def test_span_over_several_days_lists_every_boundary():
    eng = engine()
    d = _day(eng)
    s = eng.classify_span(d.open + timedelta(hours=1), d.open + timedelta(days=3, hours=1))
    assert s.waqt_days_touched == 4 and len(s.maghrib_boundaries) == 3
    assert list(s.maghrib_boundaries) == sorted(s.maghrib_boundaries)


def test_civil_midnight_and_maghrib_are_independent_facts():
    """The brief's 23:30 -> 00:30 example. Civil midnight is NOT a Waqt boundary."""
    eng = engine()  # Addis, UTC+3: 23:30 local = 20:30Z
    a, b = datetime(2026, 9, 19, 20, 30, tzinfo=UTC), datetime(2026, 9, 19, 21, 30, tzinfo=UTC)
    s = eng.classify_span(a, b)
    assert s.crosses_civil_midnight is True and s.crosses_maghrib is False and s.same_waqt_day is True
    # ...and the converse: 17:30 -> 19:30 local straddles Maghrib but not civil midnight.
    a2, b2 = datetime(2026, 9, 19, 14, 30, tzinfo=UTC), datetime(2026, 9, 19, 16, 30, tzinfo=UTC)
    s2 = eng.classify_span(a2, b2)
    assert s2.crosses_maghrib is True and s2.crosses_civil_midnight is False


def test_span_no_valid_window_cases():
    eng = engine()
    assert eng.classify_span(T0 + timedelta(hours=1), T0).status == Status.NO_VALID_WINDOW
    assert eng.classify_span(T0, T0).status == Status.NO_VALID_WINDOW
    assert eng.classify_span(T0, T0, end_inclusive=True).status == Status.OK


def test_span_in_polar_undefined_day_is_window_undefined():
    eng = engine(Location(69.6492, 18.9553))
    s = eng.classify_span(datetime(2026, 6, 21, 12, tzinfo=UTC), datetime(2026, 6, 21, 13, tzinfo=UTC))
    assert s.status == Status.WINDOW_UNDEFINED and s.crosses_maghrib is None and s.reason


# ---------------------------------------------------------------------------
# Brief item: exact-boundary behaviour of windows
# ---------------------------------------------------------------------------

def test_half_open_window_membership_at_both_ends():
    eng = engine()
    rule = between(Event("fajr"), Event("sunrise"))
    f, sr = at(eng, Event("fajr")), at(eng, Event("sunrise"))
    assert eng.evaluate(rule, f - timedelta(microseconds=1)).inside is False
    assert eng.evaluate(rule, f).inside is True
    assert eng.evaluate(rule, sr - timedelta(microseconds=1)).inside is True
    assert eng.evaluate(rule, sr).inside is False
    assert eng.evaluate(rule, f - timedelta(seconds=5)).relation == "before_window"
    assert eng.evaluate(rule, sr + timedelta(seconds=5)).relation == "after_window"
    assert eng.evaluate(rule, f + timedelta(seconds=5)).relation == "inside"


def test_inclusivity_flags_are_honoured():
    eng = engine()
    closed = Interval(Event("fajr"), Event("sunrise"), start_inclusive=False, end_inclusive=True)
    f, sr = at(eng, Event("fajr")), at(eng, Event("sunrise"))
    assert eng.evaluate(closed, f).inside is False
    assert eng.evaluate(closed, sr).inside is True


def test_zero_length_window_validity_follows_inclusivity():
    eng = engine()
    p = Instant(T0)
    assert eng.resolve_interval(Interval(p, p), T0).status == Status.NO_VALID_WINDOW
    assert eng.resolve_interval(Interval(p, p, True, True), T0).status == Status.OK


def test_events_are_positions_the_window_is_positioned_on_the_grid_not_reshaped():
    """between(maghrib, isha) contains the day-boundary instant as its own start."""
    eng = engine()
    day = _day(eng)
    # Anchor is fixed to T0: were it left to default to the tested instant, then at the exact
    # Maghrib the anchor's day would flip to the NEW day and 'Event("maghrib")' would mean tomorrow's.
    assert eng.evaluate(between(Event("maghrib"), Event("isha")), day.close, anchor=T0).inside is True


# ---------------------------------------------------------------------------
# Brief item 5: undefined astronomy — explicit, distinct, never invented
# ---------------------------------------------------------------------------

def test_single_event_undefined_is_EVENT_UNDEFINED_and_never_a_guess():
    eng = engine(LONDON)
    for name in ("fajr", "isha"):
        r = eng.resolve_point(Event(name), LONDON_JUNE)
        assert r.status == Status.EVENT_UNDEFINED and r.instant is None
        assert r.cause == "EVENT_UNDEFINED_ON_DAY" and r.undefined_ref == f"{name}@day+0"
    assert eng.resolve_point(Event("maghrib"), LONDON_JUNE).ok       # same day, other events fine
    assert eng.resolve_point(Event("sunrise"), LONDON_JUNE).ok


def test_window_with_an_undefined_endpoint_is_WINDOW_UNDEFINED_with_causes():
    eng = engine(LONDON)
    w = eng.resolve_interval(between(Event("fajr"), Event("sunrise")), LONDON_JUNE)
    assert w.status == Status.WINDOW_UNDEFINED
    assert w.duration_seconds is None and w.end.ok and not w.start.ok
    assert [c.undefined_ref for c in w.causes] == ["fajr@day+0"]
    w2 = eng.resolve_interval(between(Event("maghrib"), Event("isha")), LONDON_JUNE)
    assert w2.status == Status.WINDOW_UNDEFINED and [c.undefined_ref for c in w2.causes] == ["isha@day+0"]


def test_both_endpoints_defined_but_inverted_is_NO_VALID_WINDOW():
    eng = engine()
    w = eng.resolve_interval(between(Event("sunrise"), Event("fajr")), T0)     # backwards
    assert w.status == Status.NO_VALID_WINDOW and w.start.ok and w.end.ok and w.causes == ()
    assert "before it starts" in w.reason


def test_the_three_statuses_are_distinct_values():
    assert len({Status.EVENT_UNDEFINED, Status.WINDOW_UNDEFINED, Status.NO_VALID_WINDOW, Status.OK}) == 4


def test_evaluate_reports_unknown_not_false_when_the_window_is_undefined():
    eng = engine(LONDON)
    ev = eng.evaluate(between(Event("fajr"), Event("sunrise")), LONDON_JUNE)
    assert ev.status == Status.WINDOW_UNDEFINED and ev.inside is None and ev.relation is None


def test_before_undefined_event_is_window_undefined_not_false():
    eng = engine(LONDON)
    ev = eng.evaluate(before(Event("fajr")), LONDON_JUNE)
    assert ev.status == Status.WINDOW_UNDEFINED and ev.inside is None


def test_strict_next_fajr_reports_undefined_rather_than_jumping_days():
    eng = engine(LONDON)
    u = eng.until("fajr", LONDON_JUNE)
    assert u.status == Status.EVENT_UNDEFINED and u.seconds is None


def test_skip_policy_is_opt_in_and_reports_what_it_skipped():
    """Find a London date where tonight-tomorrow's Fajr is undefined but one
    within the lookahead range is defined (the end of the 'white nights')."""
    eng = engine(LONDON)
    for i in range(0, 60):
        t = datetime(2026, 7, 18, 12, tzinfo=UTC) + timedelta(days=i)
        strict = eng.until("fajr", t)
        if strict.status == Status.EVENT_UNDEFINED:
            skip = eng.until("fajr", t, on_undefined=UndefinedPolicy.SKIP)
            if skip.status == Status.OK:
                assert skip.target.skipped, "skipped days must be reported, not hidden"
                assert skip.seconds > 3600
                return
    pytest.fail("expected a London date whose strict Fajr is undefined but skip finds one within range")


def test_skip_that_finds_nothing_in_range_says_so_instead_of_guessing():
    eng = engine(LONDON)
    r = eng.resolve_point(NextEvent("fajr", on_undefined=UndefinedPolicy.SKIP), LONDON_JUNE)   # midsummer: none for weeks
    assert r.status == Status.EVENT_UNDEFINED and r.cause == "NO_OCCURRENCE_IN_RANGE" and r.instant is None
    assert r.skipped or "skipped" in r.reason


def test_an_undefined_event_on_an_irrelevant_day_does_not_poison_the_answer():
    """When looking for the NEXT Fajr, an undefined Fajr on a day that is already
    over must not matter; this is what the slot-shift start point guarantees."""
    eng = engine(LONDON)
    # London around the point where Fajr becomes defined again: search until a day
    # exists where today's Fajr is defined but yesterday's was not.
    found = False
    for i in range(0, 60):
        t = datetime(2026, 7, 10, 22, tzinfo=UTC) + timedelta(days=i)   # after that day's Maghrib
        yesterday_fajr = eng.resolve_point(Event("fajr", -1), t)
        next_fajr = eng.until("fajr", t)
        if not yesterday_fajr.ok and next_fajr.status == Status.OK:
            found = True
            break
    assert found, "expected a date where yesterday's Fajr is undefined but the next Fajr is fine"


def test_polar_day_makes_day_relative_refs_DAY_UNDEFINED():
    eng = engine(Location(69.6492, 18.9553))
    r = eng.resolve_point(Event("maghrib"), datetime(2026, 6, 21, 12, tzinfo=UTC))
    assert r.status == Status.EVENT_UNDEFINED and r.cause == "DAY_UNDEFINED"
    db = eng.day_bounds(datetime(2026, 6, 21, 12, tzinfo=UTC))
    assert db.status == Status.EVENT_UNDEFINED and db.open is None and db.reason


def test_stepping_into_and_across_an_undefined_day():
    eng = engine(Location(69.6492, 18.9553))
    ok = eng.resolve_point(Event("day_start", 0), TROMSO_LAST_DEFINED)
    into = eng.resolve_point(Event("maghrib", 1), TROMSO_LAST_DEFINED)       # arrives AT the undefined day
    across = eng.resolve_point(Event("maghrib", 2), TROMSO_LAST_DEFINED)     # would have to step THROUGH it
    assert ok.ok
    assert into.status == across.status == Status.EVENT_UNDEFINED
    assert into.cause == "DAY_UNDEFINED" and across.cause == "DAY_UNDEFINED"


def test_next_event_reports_undefined_events_instead_of_dropping_them():
    eng = engine(LONDON)
    t = datetime(2026, 6, 21, 1, 0, tzinfo=UTC)
    n = eng.next_event(t)
    assert n.status == Status.OK and n.name in ("sunrise", "dhuhr", "asr", "maghrib")
    assert {u["name"] for u in n.undefined_events} >= {"fajr"}


# ---------------------------------------------------------------------------
# Brief item: profile changes only move their own event
# ---------------------------------------------------------------------------

def test_asr_profiles_change_only_asr_dependent_results():
    std = engine(profile=AstronomyProfile(asr_shadow_ratio=1.0))
    han = engine(profile=AstronomyProfile(asr_shadow_ratio=2.0))
    for name in ("fajr", "sunrise", "dhuhr", "maghrib", "isha", "day_start", "day_end"):
        assert at(std, Event(name)) == at(han, Event(name)), name
    assert at(han, Event("asr")) > at(std, Event("asr"))
    # Windows that don't touch Asr are byte-identical...
    for rule in (between(Event("fajr"), Event("sunrise")), between(Event("maghrib"), Event("isha")), within_day()):
        assert std.resolve_interval(rule, T0).to_dict() == han.resolve_interval(rule, T0).to_dict()
    # ...and one that does, differs.
    asr_window = between(Event("dhuhr"), Event("asr"))
    assert std.resolve_interval(asr_window, T0).duration_seconds != han.resolve_interval(asr_window, T0).duration_seconds
    # The day itself (hence any Waqt position) does not move:
    assert std.day_bounds(T0).open == han.day_bounds(T0).open


# ---------------------------------------------------------------------------
# Brief item 6: calendar-independent scheduling
# ---------------------------------------------------------------------------

def _battery(eng):
    rules = [between(Event("fajr"), Event("sunrise")), between(Event("maghrib"), Event("isha")), within_day(),
             before(NextEvent("maghrib")), within(PrevEvent("maghrib"), 7200)]
    out = [eng.resolve_interval(r, T0).to_dict() for r in rules]
    out.append(eng.classify_span(T0, T0 + timedelta(hours=14)).to_dict())
    out.append(eng.snapshot(T0)["next_event"].to_dict())
    out.append(eng.until("maghrib", T0).to_dict())
    return out


def _strip_labels(x):
    if isinstance(x, dict):
        return {k: _strip_labels(v) for k, v in x.items() if k != "hijri_label"}
    if isinstance(x, list):
        return [_strip_labels(v) for v in x]
    return x


def test_swapping_calendar_provider_changes_labels_but_no_scheduling_result():
    base = ArithmeticTabularProvider()
    providers = [base, UmmAlQuraProvider(), ExampleRegionalOffsetProvider(wrapped=base, day_offset=1)]
    results = [_battery(engine(calendar_provider=p)) for p in providers]
    labels = {engine(calendar_provider=p).day_bounds(T0).hijri_label for p in providers}
    assert len(labels) >= 2, "test is only meaningful if the providers actually disagree on the label"
    for r in results[1:]:
        assert _strip_labels(r) == _strip_labels(results[0])


def test_scheduling_source_never_reads_the_hijri_label():
    """Structural guard: the only place scheduling touches a Hijri label is the
    display helper. If a later change starts branching on it, this fails."""
    import pathlib
    import re
    root = pathlib.Path(__file__).resolve().parents[1] / "waqt" / "scheduling"
    uses = []
    for f in root.glob("*.py"):
        for i, line in enumerate(f.read_text().splitlines(), 1):
            code = line.split("#")[0]
            if re.search(r"hijri_date|\.hijri_label\(|hijri_label\s*[=!]=", code) and "def hijri_label" not in code \
                    and "return day.hijri_date.iso_like()" not in code:   # the display helper itself
                uses.append((f.name, i, line.strip()))
    allowed_files = {"context.py", "engine.py"}
    assert all(f in allowed_files for f, _, _ in uses), uses
    # engine.py may only forward the label into a result field, never compare or branch on it
    for f, i, line in uses:
        assert not re.search(r"\b(if|elif|while|assert)\b.*hijri", line), (f, i, line)


# ---------------------------------------------------------------------------
# The portable rule format
# ---------------------------------------------------------------------------

RULE_ROUNDTRIP = [
    between(Event("fajr"), Event("sunrise")),
    before(NextEvent("maghrib", on_undefined="skip")),
    within(PrevEvent("maghrib", inclusive=False), 7200),
    Interval(Fraction(Event("maghrib"), Event("fajr", 1), 2 / 3), Event("fajr", 1), True, True),
    Interval(Position(3600, 0), Offset(Event("isha"), -900)),
]


@pytest.mark.parametrize("rule", RULE_ROUNDTRIP)
def test_rule_dict_round_trip(rule):
    d = json.loads(json.dumps(rule.to_dict()))
    assert interval_from_dict(d) == rule


def test_offset_accepts_one_duration_unit_only():
    p = point_from_dict({"type": "offset", "base": {"type": "event", "name": "maghrib"}, "minutes": -30})
    assert p == Offset(Event("maghrib"), -1800)
    p = point_from_dict({"type": "offset", "base": {"type": "anchor"}, "waqt_hours": 2})
    assert p.seconds == 7200
    with pytest.raises(RuleError):
        point_from_dict({"type": "offset", "base": {"type": "anchor"}, "minutes": 1, "seconds": 60})
    with pytest.raises(RuleError):
        point_from_dict({"type": "offset", "base": {"type": "anchor"}})


@pytest.mark.parametrize("bad", [
    {"type": "event", "name": "witr"},
    {"type": "event", "name": "fajr", "day": "0"},
    {"type": "nonsense"},
    {"type": "next_event", "name": "day_start"},
    {"type": "next_event", "name": "fajr", "on_undefined": "guess"},
    {"type": "instant", "value": "yesterday"},
    {"type": "position", "seconds": "3600"},
    "fajr",
])
def test_malformed_rules_raise_rule_error(bad):
    with pytest.raises(RuleError):
        point_from_dict(bad)


def test_interval_needs_a_bound_and_nesting_is_capped():
    with pytest.raises(RuleError):
        Interval(None, None)
    deep = {"type": "anchor"}
    for _ in range(30):
        deep = {"type": "offset", "base": deep, "seconds": 1}
    with pytest.raises(RuleError):
        point_from_dict(deep)


def test_derived_arithmetic_is_exact_integer_microseconds():
    eng = engine()
    r = eng.resolve_point(Offset(Instant(datetime(2026, 1, 1, tzinfo=UTC)), 0.0000005), T0)   # 0.5 µs -> rounds half up to 1 µs
    assert to_micros(r.instant) - to_micros(datetime(2026, 1, 1, tzinfo=UTC)) == 1
    assert from_micros(to_micros(T0)) == T0


# ---------------------------------------------------------------------------
# Snapshot ("the programmable moment")
# ---------------------------------------------------------------------------

def test_snapshot_answers_the_standard_questions_consistently():
    eng = engine()
    snap = eng.snapshot(T0)
    day = snap["day"]
    assert day.status == Status.OK and day.position_display == "00:19:02"
    by = {e["name"]: e for e in snap["events"]}
    assert by["maghrib"]["next"].seconds == eng.until("maghrib", T0).seconds
    assert by["fajr"]["previous"].status == Status.OK
    ne = snap["next_event"]
    assert ne.name == "isha" and ne.seconds_until == by["isha"]["next"].seconds
    assert ne.position_display == "01:05:31"     # Isha's position in the day that CONTAINS it


def test_event_position_reports_both_readings_for_isha():
    eng = engine()
    p = eng.event_position("isha", T0)
    assert p.listed_position_display.startswith("25:")      # Sprint 5's listed-day reading
    assert p.containing_position_display.startswith("01:")  # the day that actually contains it
    assert p.containing_day_relative_to_listed == 1
    f = eng.event_position("fajr", T0)
    assert f.listed_position_display == f.containing_position_display and f.containing_day_relative_to_listed == 0


def test_day_bounds_answers_when_the_islamic_day_begins_and_ends():
    eng = engine()
    b = eng.day_bounds(T0)
    assert b.open == at(eng, Event("day_start")) and b.close == at(eng, Event("day_end"))
    assert b.length_seconds == (b.close - b.open).total_seconds()

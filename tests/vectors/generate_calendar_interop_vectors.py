"""
Generate tests/vectors/calendar_interop_vectors.json (Sprint 8).

Same posture as generate_vectors.py / generate_institutional_vectors.py:
every number in the output file is COMPUTED by the Python reference
implementation, never hand-typed. The JS consumer
(consumers/js/src/calendar_interop.mjs) does not recompute Maghrib —
it is handed the astronomy this script already produced (a "day
table" or a set of boundary instants, per vector) and independently
re-derives everything else: Gregorian civil dates, leap years,
weekdays, and the civil-midnight/Maghrib boundary-crossing rule
itself. That is exactly what a real, independent consumer of Waqt's
calendar-interoperability contract would receive and do.

Run: python3 tests/vectors/generate_calendar_interop_vectors.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vector_stamp import stamp  # noqa: E402  (Sprint 12: vector-set version + engine-revision stamp)

from waqt import calendar_interop as ci
from waqt.calendar_providers import ArithmeticTabularProvider, DeclaredProvider
from waqt.core import Location
from waqt.hijri import HijriDate
from waqt.timescale import DEFAULT_TIMESCALE_PROVIDER as TS
from waqt.timezone_provider import DEFAULT_TIMEZONE_PROVIDER as TZ

OUT_PATH = os.path.join(os.path.dirname(__file__), "calendar_interop_vectors.json")

ARITH = ArithmeticTabularProvider()

LOCATIONS = {
    "addis_ababa": Location(lat=9.0084, lon=38.7575, elevation_m=2355),
    "kiritimati": Location(lat=1.87, lon=-157.4, elevation_m=3),      # date-line, UTC+14
    "dibrugarh": Location(lat=27.48, lon=94.90, elevation_m=108),      # single-zone India, tz vs solar time diverge ~50 min
}


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def utc_offset_seconds(loc: Location, near: datetime) -> int:
    tzname = TZ.timezone_name_for(loc.lat, loc.lon)
    from zoneinfo import ZoneInfo
    return int(near.astimezone(ZoneInfo(tzname)).utcoffset().total_seconds())


# ---------------------------------------------------------------------------
# Group 1: instant_representation
# ---------------------------------------------------------------------------

def build_instant_vector(vector_id, description, instant, loc_key):
    loc = LOCATIONS[loc_key]
    rep = ci.represent_instant(instant, loc, ARITH, tz_provider=TZ, timescale=TS)
    body = rep.to_dict()
    context = {
        "location": {"lat": loc.lat, "lon": loc.lon, "elevation_m": loc.elevation_m},
        "timezone_name": TZ.timezone_name_for(loc.lat, loc.lon),
        "utc_offset_seconds": utc_offset_seconds(loc, instant),
    }
    if body["waqt"]:
        context["waqt_day"] = {
            "maghrib_open": body["waqt"]["day_open_maghrib"],
            "maghrib_close": body["waqt"]["day_close_maghrib"],
            "hijri": body["waqt"]["hijri"],
            "weekday": body["waqt"]["weekday"],
        }
    else:
        context["waqt_day"] = None
    return {
        "id": vector_id,
        "description": description,
        "op": "represent_instant",
        "instant": iso(instant),
        "context": context,
        "expected": {
            "gregorian_utc": body["gregorian_utc"],
            "gregorian_civil": body["gregorian_civil"],
            "waqt_status": body["waqt_status"],
            "waqt_position_seconds": round(rep.waqt_position_seconds, 3) if rep.waqt_position_seconds is not None else None,
        },
    }


def instant_representation_vectors():
    vectors = []

    # ordinary Gregorian/Waqt conversion
    vectors.append(build_instant_vector(
        "ordinary-conversion-addis",
        "An ordinary midday instant converts cleanly to both a UTC/civil Gregorian date and a Waqt day.",
        datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc), "addis_ababa",
    ))

    # leap-year Gregorian dates
    vectors.append(build_instant_vector(
        "leap-year-feb-29",
        "2028 is a leap year; Feb 29 exists and is_leap_year is true for both Gregorian renderings.",
        datetime(2028, 2, 29, 10, 0, 0, tzinfo=timezone.utc), "addis_ababa",
    ))
    vectors.append(build_instant_vector(
        "non-leap-century-1900",
        "1900 is divisible by 100 but not 400: NOT a leap year, per the standard Gregorian rule.",
        datetime(1900, 2, 28, 10, 0, 0, tzinfo=timezone.utc), "addis_ababa",
    ))
    vectors.append(build_instant_vector(
        "leap-century-2000",
        "2000 is divisible by 400: IS a leap year, per the standard Gregorian rule.",
        datetime(2000, 2, 29, 10, 0, 0, tzinfo=timezone.utc), "addis_ababa",
    ))

    # date-line location
    vectors.append(build_instant_vector(
        "date-line-kiritimati",
        "Kiritimati (UTC+14) civil date is far ahead of UTC; the Waqt day and Gregorian-civil date must both reflect the local, not UTC, calendar date.",
        datetime(2026, 6, 15, 20, 0, 0, tzinfo=timezone.utc), "kiritimati",
    ))

    # location where timezone and solar time differ substantially
    vectors.append(build_instant_vector(
        "timezone-vs-solar-dibrugarh",
        "Dibrugarh (NE India) uses Asia/Kolkata (UTC+5:30) despite sitting near 95 deg E, where solar time runs roughly 50 minutes ahead of the civil clock; Waqt's Maghrib bracketing uses true solar geometry regardless of the political offset.",
        datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc), "dibrugarh",
    ))

    # Waqt date whose Gregorian representation differs from the intuitive civil date:
    # shortly after local midnight but before Maghrib, the Waqt day is still the
    # PREVIOUS Maghrib's day, which closes (Hijri/weekday-label date) on a Gregorian
    # date one day later than the civil date the wall clock is currently showing.
    addis = LOCATIONS["addis_ababa"]
    probe_day = ci.waqt_day_for_gregorian_date(date(2026, 3, 2), addis, ARITH, tz_provider=TZ, timescale=TS)
    just_after_midnight = probe_day.open + timedelta(hours=6)  # well after local midnight, well before Maghrib
    vectors.append(build_instant_vector(
        "waqt-date-differs-from-civil-date",
        "Shortly after local civil midnight but before Maghrib, the current Waqt day's Gregorian close-date is one day AHEAD of the Gregorian civil date the wall clock shows right now -- these are not the same 'today'.",
        just_after_midnight, "addis_ababa",
    ))

    # exact Maghrib / one second before / one second after
    exact = probe_day.close
    vectors.append(build_instant_vector(
        "exact-maghrib",
        "The instant exactly AT Maghrib belongs to the NEW day it opens (half-open [open, close) convention): position_seconds == 0.",
        exact, "addis_ababa",
    ))
    vectors.append(build_instant_vector(
        "one-second-before-maghrib",
        "One second before Maghrib still belongs to the OLD day, at its very last second.",
        exact - timedelta(seconds=1), "addis_ababa",
    ))
    vectors.append(build_instant_vector(
        "one-second-after-maghrib",
        "One second after Maghrib belongs to the NEW day, one second into it.",
        exact + timedelta(seconds=1), "addis_ababa",
    ))

    # provider changes affecting Hijri labels but not the underlying instant
    t = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
    rep_arith = ci.represent_instant(t, addis, ARITH, tz_provider=TZ, timescale=TS)
    rep_declared = ci.represent_instant(t, addis, declared_with_override(), tz_provider=TZ, timescale=TS)
    vectors.append({
        "id": "provider-change-affects-hijri-label-only",
        "description": (
            "Switching the Hijri calendar provider changes the reported Hijri label "
            "but MUST NOT change the underlying instant, the Gregorian date, or the "
            "Waqt day's Maghrib boundaries -- those come from astronomy, not the "
            "calendar provider."
        ),
        "op": "provider_invariance",
        "instant": iso(t),
        "context": {
            "location": {"lat": addis.lat, "lon": addis.lon, "elevation_m": addis.elevation_m},
        },
        "expected": {
            "gregorian_utc_same": True,
            "maghrib_open_same": True,
            "maghrib_close_same": True,
            "hijri_arithmetic_tabular": rep_arith.to_dict()["waqt"]["hijri"],
            "hijri_declared": rep_declared.to_dict()["waqt"]["hijri"],
            "gregorian_utc": rep_arith.to_dict()["gregorian_utc"],
            "maghrib_open": rep_arith.to_dict()["waqt"]["day_open_maghrib"],
            "maghrib_close": rep_arith.to_dict()["waqt"]["day_close_maghrib"],
        },
    })

    return vectors


# small helper: a `declared` provider instance carrying one explicit override,
# built the same way waqt/api/providers.py already builds one for a request.
def declared_with_override():
    override_date = date(2026, 3, 1)
    hd = HijriDate(1447, 9, 13, provider="declared", version="manual-v1", source_note="test override")
    return DeclaredProvider(overrides={override_date: hd}, fallback=ARITH)


# ---------------------------------------------------------------------------
# Group 2: gregorian_date_to_waqt
# ---------------------------------------------------------------------------

def build_date_vector(vector_id, description, g, loc_key):
    loc = LOCATIONS[loc_key]
    day = ci.waqt_day_for_gregorian_date(g, loc, ARITH, tz_provider=TZ, timescale=TS)
    offset = utc_offset_seconds(loc, day.close)
    return {
        "id": vector_id,
        "description": description,
        "op": "gregorian_date_to_waqt_day",
        "date": g.isoformat(),
        "context": {
            "location": {"lat": loc.lat, "lon": loc.lon, "elevation_m": loc.elevation_m},
            "utc_offset_seconds": offset,
            "candidate_day": {
                "maghrib_open": iso(day.open),
                "maghrib_close": iso(day.close),
                "hijri": {"display": str(day.hijri_date), "date": day.hijri_date.iso_like()},
                "weekday": day.weekday,
            },
        },
        "expected": {"resolved": True, "close_civil_date": g.isoformat()},
    }


def gregorian_date_to_waqt_vectors():
    vectors = [
        build_date_vector(
            "ordinary-date-addis",
            "An ordinary Gregorian civil date resolves to the Waqt day whose closing Maghrib falls on it.",
            date(2026, 3, 1), "addis_ababa",
        ),
        build_date_vector(
            "leap-year-date-addis",
            "Feb 29 of a leap year resolves to a Waqt day exactly as any other date does.",
            date(2028, 2, 29), "addis_ababa",
        ),
        build_date_vector(
            "date-line-date-kiritimati",
            "A civil date at a UTC+14 date-line location still resolves correctly using that location's own real offset.",
            date(2026, 6, 15), "kiritimati",
        ),
    ]
    return vectors


# ---------------------------------------------------------------------------
# Group 3: boundary_crossing
# ---------------------------------------------------------------------------

def build_boundary_vector(vector_id, description, start, end, loc_key):
    loc = LOCATIONS[loc_key]
    crossing = ci.classify_boundary_crossing(start, end, loc, tz_provider=TZ, timescale=TS)
    return {
        "id": vector_id,
        "description": description,
        "op": "boundary_crossing",
        "start": iso(start),
        "end": iso(end),
        "context": {
            "location": {"lat": loc.lat, "lon": loc.lon, "elevation_m": loc.elevation_m},
            "utc_offset_seconds": utc_offset_seconds(loc, start),
            "maghrib_boundaries_near": [iso(m) for m in crossing.maghrib_boundaries],
        },
        "expected": {
            "crosses_civil_midnight": crossing.crosses_civil_midnight,
            "crosses_maghrib": crossing.crosses_maghrib,
            "start_civil_date": crossing.start_civil_date.isoformat(),
            "end_civil_date": crossing.end_civil_date.isoformat(),
        },
    }


def boundary_crossing_vectors():
    addis = LOCATIONS["addis_ababa"]
    day = ci.waqt_day_for_gregorian_date(date(2026, 3, 1), addis, ARITH, tz_provider=TZ, timescale=TS)
    maghrib = day.close

    from zoneinfo import ZoneInfo
    tzname = TZ.timezone_name_for(addis.lat, addis.lon)
    # local civil midnight of the civil date the Maghrib instant falls on
    civil_date_of_maghrib = TZ.local_date(maghrib, addis.lat, addis.lon)
    next_civil_midnight_local = datetime(
        civil_date_of_maghrib.year, civil_date_of_maghrib.month, civil_date_of_maghrib.day,
        0, 0, 0, tzinfo=ZoneInfo(tzname),
    ) + timedelta(days=1)
    civil_midnight = next_civil_midnight_local.astimezone(timezone.utc)

    vectors = []

    vectors.append(build_boundary_vector(
        "maghrib-only",
        "A short span straddling Maghrib but staying within the same civil calendar date crosses Maghrib but not civil midnight.",
        maghrib - timedelta(hours=1), maghrib + timedelta(hours=1), "addis_ababa",
    ))

    vectors.append(build_boundary_vector(
        "civil-midnight-only",
        "A short span straddling civil midnight, well clear of Maghrib on both sides, crosses civil midnight but not Maghrib.",
        civil_midnight - timedelta(hours=1), civil_midnight + timedelta(hours=1), "addis_ababa",
    ))

    early = min(maghrib, civil_midnight) - timedelta(hours=2)
    late = max(maghrib, civil_midnight) + timedelta(hours=2)
    vectors.append(build_boundary_vector(
        "both-boundaries",
        "A wide span covering both Maghrib and the following civil midnight crosses both boundaries.",
        early, late, "addis_ababa",
    ))

    neither_start = maghrib + timedelta(hours=2)
    neither_end = neither_start + timedelta(minutes=30)
    vectors.append(build_boundary_vector(
        "neither-boundary",
        "A short span entirely between Maghrib and the next civil midnight (or vice versa) crosses neither boundary.",
        neither_start, neither_end, "addis_ababa",
    ))

    # exact civil midnight edge cases: span starting exactly at civil midnight
    # (stays in the day midnight opens -- does NOT count as crossing) vs a span
    # that reaches just past it (does).
    vectors.append(build_boundary_vector(
        "starts-exactly-at-civil-midnight",
        "A span that STARTS exactly at civil midnight lies wholly within the date midnight opens: half-open spans exclude their own start-adjacent boundary only from the 'crossed' count, per the interior (start < B < end) rule.",
        civil_midnight, civil_midnight + timedelta(hours=1), "addis_ababa",
    ))
    vectors.append(build_boundary_vector(
        "ends-exactly-at-civil-midnight",
        "A span that ENDS exactly at civil midnight never reaches it (half-open exclusion of the end instant): does not count as crossing.",
        civil_midnight - timedelta(hours=1), civil_midnight, "addis_ababa",
    ))
    vectors.append(build_boundary_vector(
        "ends-exactly-at-maghrib",
        "A span that ENDS exactly at Maghrib never reaches it: does not count as crossing Maghrib.",
        maghrib - timedelta(hours=1), maghrib, "addis_ababa",
    ))
    vectors.append(build_boundary_vector(
        "starts-exactly-at-maghrib",
        "A span that STARTS exactly at Maghrib lies wholly within the day Maghrib opens: does not count as crossing.",
        maghrib, maghrib + timedelta(hours=1), "addis_ababa",
    ))

    return vectors


def main():
    doc = {
        "$schema_note": (
            "Sprint 8 conformance vectors for waqt.calendar_interop. Every "
            "astronomy value (Maghrib instants, Hijri labels) here was "
            "computed once by the Python reference implementation. "
            "consumers/js/src/calendar_interop.mjs must reproduce every "
            "'expected' field using only the 'context' given -- it never "
            "recomputes Maghrib from coordinates."
        ),
        "instant_representation": instant_representation_vectors(),
        "gregorian_date_to_waqt_day": gregorian_date_to_waqt_vectors(),
        "boundary_crossing": boundary_crossing_vectors(),
    }
    doc = stamp(doc, astronomy_dependent=True)
    with open(OUT_PATH, "w") as f:
        json.dump(doc, f, indent=2, default=str)
        f.write("\n")
    total = sum(len(v) for k, v in doc.items() if isinstance(v, list))
    print(f"Wrote {OUT_PATH} with {total} vectors.")


if __name__ == "__main__":
    main()

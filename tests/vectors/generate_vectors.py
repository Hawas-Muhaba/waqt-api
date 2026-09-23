"""
Generates tests/vectors/waqt_vectors.json by running the Python
reference implementation. NOT hand-typed — every expected value in
the output file is Waqt's own computed answer, frozen at generation
time. Re-run this after any change to waqt/core.py, waqt/solar.py, or
waqt/semantics.py that's meant to change behavior; a diff in the
output is exactly the signal that behavior changed.

Usage: python3 tests/vectors/generate_vectors.py
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from waqt.core import AstronomyProfile, Location, compute_waqt
from waqt.hijri import ArithmeticTabularProvider
from waqt.semantics import waqt_day_from_result

PROVIDER = ArithmeticTabularProvider()


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat() if dt is not None else None


def build_vector(vector_id, description, lat, lon, instant, elevation_m=0.0, profile=None, notes=None):
    profile = profile or AstronomyProfile()
    r = compute_waqt(instant, Location(lat, lon, elevation_m), PROVIDER, profile)

    vector = {
        "id": vector_id,
        "description": description,
        "input": {
            "location": {"lat": lat, "lon": lon, "elevation_m": elevation_m},
            "instant": iso(instant),
            "calendar_provider": "arithmetic-tabular",
            "astronomy_profile": {
                "fajr_angle_deg": profile.fajr_angle_deg,
                "isha_angle_deg": profile.isha_angle_deg,
                "asr_shadow_ratio": profile.asr_shadow_ratio,
            },
        },
        "expected": {
            "status": r.status,
            "undefined_reason": r.undefined_reason,
        },
    }
    if notes:
        vector["notes"] = notes

    if r.status == "OK":
        day = waqt_day_from_result(r)
        pos = day.position_of(instant)
        vector["expected"].update({
            "hijri_date": r.hijri_date.iso_like(),
            "weekday": r.weekday,
            "day": {
                "maghrib_open": iso(r.day_start_maghrib),
                "maghrib_close": iso(r.day_end_maghrib),
                "length_si_seconds": round(r.day_length_si_seconds, 3),
            },
            "waqt_position": {
                "hour": pos.hour, "minute": pos.minute, "second": pos.second,
                "display": pos.display, "total_seconds": round(pos.total_seconds, 3),
            },
            "events": {
                e.name: {
                    "instant": iso(e.instant),
                    "position_display": e.position.display,
                    "position_total_seconds": round(e.position.total_seconds, 3),
                }
                for e in day.events()
            },
        })
    return vector


def main():
    vectors = []

    # 1. Normal instant, well inside a day, low latitude.
    vectors.append(build_vector(
        "addis-normal-instant", "Ordinary instant, Addis Ababa, shortly after Maghrib.",
        9.0192, 38.7525, datetime(2026, 9, 19, 15, 42, tzinfo=timezone.utc),
    ))

    # 2. Exact Maghrib instant -> position must be exactly 00:00:00.
    r_ref = compute_waqt(datetime(2026, 9, 19, 15, 42, tzinfo=timezone.utc), Location(9.0192, 38.7525), PROVIDER)
    vectors.append(build_vector(
        "addis-exact-maghrib-boundary",
        "Instant equal to Maghrib itself -- must read exactly 00:00:00, per the half-open [Maghrib(D), Maghrib(D+1)) rule.",
        9.0192, 38.7525, r_ref.day_start_maghrib,
        notes="waqt_position.display MUST be '00:00:00' and total_seconds MUST be 0.0.",
    ))

    # 3. One second before Maghrib -> previous day, near 24:00.
    vectors.append(build_vector(
        "addis-one-second-before-maghrib",
        "One second before Maghrib -- belongs to the PREVIOUS Waqt day, reading near its own day length.",
        9.0192, 38.7525, r_ref.day_start_maghrib - timedelta(seconds=1),
        notes="This instant's Waqt day is the one that CLOSES at addis-exact-maghrib-boundary's Maghrib.",
    ))

    # 4. Makkah, equinox-ish.
    vectors.append(build_vector(
        "makkah-equinox", "Makkah itself, near the September equinox.",
        21.4225, 39.8262, datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc),
    ))

    # 5. High latitude, day runs LONG -> position can exceed 24:00:00.
    # First find the day's actual boundaries, then place the demonstration
    # instant inside the (86400s, day_length] window so hour=24 actually shows.
    probe = compute_waqt(datetime(2026, 2, 15, 12, 0, tzinfo=timezone.utc), Location(51.5074, -0.1278), PROVIDER)
    assert probe.day_length_si_seconds > 86400, "chosen date no longer produces a long day -- re-pick one"
    long_day_instant = probe.day_start_maghrib + timedelta(seconds=86450)  # inside (86400, day_length)
    vectors.append(build_vector(
        "london-long-day-near-24h-boundary",
        "London in February: this day runs slightly OVER 24:00:00. Instant chosen inside the (86400s, day_length) window so the reading is past 24:00:00.",
        51.5074, -0.1278, long_day_instant,
        notes="day.length_si_seconds > 86400 and waqt_position.hour == 24, demonstrating a reading past the nominal 24-hour mark.",
    ))

    # 6. Polar day -> UNDEFINED, no position/events at all.
    vectors.append(build_vector(
        "tromso-midsummer-undefined",
        "Tromso, Norway, midsummer: polar day. Maghrib does not occur. Must be UNDEFINED, never a guessed time.",
        69.6492, 18.9553, datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc),
    ))

    # 7. International Date Line stress case.
    vectors.append(build_vector(
        "kiritimati-date-line",
        "Kiritimati, Kiribati: civil offset UTC+14 is ~24.5h from natural solar time -- the hardest real-world date-line case.",
        1.8721, -157.4278, datetime(2026, 9, 19, 23, 0, tzinfo=timezone.utc),
    ))

    # 8/9. Same instant, two Asr conventions -- everything else must match.
    vectors.append(build_vector(
        "addis-asr-standard", "Addis Ababa, standard (Shafi'i) Asr convention, shadow ratio 1.0.",
        9.0192, 38.7525, datetime(2026, 9, 19, 15, 42, tzinfo=timezone.utc),
        profile=AstronomyProfile(fajr_angle_deg=18.0, isha_angle_deg=17.0, asr_shadow_ratio=1.0),
        notes="Compare against addis-asr-hanafi: every field must match except events.asr.",
    ))
    vectors.append(build_vector(
        "addis-asr-hanafi", "Addis Ababa, Hanafi Asr convention, shadow ratio 2.0.",
        9.0192, 38.7525, datetime(2026, 9, 19, 15, 42, tzinfo=timezone.utc),
        profile=AstronomyProfile(fajr_angle_deg=18.0, isha_angle_deg=17.0, asr_shadow_ratio=2.0),
        notes="Compare against addis-asr-standard: every field must match except events.asr.",
    ))

    # 10. Elevation changes Maghrib.
    vectors.append(build_vector(
        "addis-elevation-2400m",
        "Addis Ababa at its real elevation (~2400m) -- Maghrib should be several minutes later than sea level.",
        9.0192, 38.7525, datetime(2026, 9, 19, 15, 42, tzinfo=timezone.utc),
        elevation_m=2400.0,
        notes="Compare day.maghrib_close against addis-normal-instant (elevation 0) -- should differ by several minutes.",
    ))

    out = {
        "spec": "waqt-core/0.1",
        "vector_format_version": "1.0",
        "generated_by": "waqt-python-reference (tests/vectors/generate_vectors.py)",
        "generated_at": iso(datetime.now(timezone.utc)),
        "note": (
            "Every 'expected' value here was computed by running the Waqt Python "
            "reference implementation itself, not hand-typed. An independent "
            "implementation in another language is expected to reproduce these "
            "values within the tolerances documented in docs/ASTRONOMY.md "
            "(Level B: ~20-120s depending on latitude for solar events; exact "
            "for Waqt-position arithmetic and day-boundary logic, which are pure "
            "calendar math with no astronomical uncertainty once Maghrib/Fajr/etc "
            "are known)."
        ),
        "vectors": vectors,
    }

    out_path = Path(__file__).parent / "waqt_vectors.json"
    out_path.write_text(json.dumps(out, indent=2) + "\n")
    print(f"Wrote {len(vectors)} vectors to {out_path}")


if __name__ == "__main__":
    main()

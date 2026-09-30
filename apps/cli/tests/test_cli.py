"""Reference-CLI tests: run the real argument parser and dispatch against the
real `waqt_local` (never mocked) and check the printed text / --json output."""

from __future__ import annotations

import io
import json

import pytest

from waqt_cli.main import run

ADDIS = ["--lat", "9.0192", "--lon", "38.7525"]
INSTANT = ["--instant", "2026-09-28T12:00:00Z"]


def call(*argv):
    out = io.StringIO()
    err = io.StringIO()
    import sys as _sys

    old_err = _sys.stderr
    _sys.stderr = err
    try:
        code = run(list(argv), out=out)
    finally:
        _sys.stderr = old_err
    return code, out.getvalue(), err.getvalue()


def test_now_reports_waqt_clock_and_metadata():
    code, out, _err = call("now", *ADDIS, *INSTANT)
    assert code == 0
    assert "Waqt clock" in out and "Hijri" in out
    assert "waqt-noaa-low-precision r2" in out
    assert "waqt-core   : " in out


def test_now_json_round_trips_and_matches_waqt_local_directly():
    import waqt_local

    code, out, _err = call("--json", "now", *ADDIS, *INSTANT)
    assert code == 0
    cli_data = json.loads(out)
    direct = waqt_local.waqt(lat=9.0192, lon=38.7525, instant="2026-09-28T12:00:00Z")
    assert cli_data == direct, "the CLI must not alter what waqt_local returned"


def test_events_lists_all_six_and_marks_next():
    code, out, _err = call("events", *ADDIS, *INSTANT)
    assert code == 0
    for name in ("Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha"):
        assert name in out
    assert "<- next" in out


def test_convert_gregorian_to_hijri_no_location():
    code, out, _err = call("convert", "--gregorian", "2026-09-28")
    assert code == 0 and "Rabi al-Thani 1448" in out


def test_convert_hijri_to_gregorian():
    code, out, _err = call("convert", "--hijri", "1448-4-15")
    assert code == 0 and "2026-09-28" in out


def test_convert_instant_to_all_calendars_needs_no_flags_beyond_instant():
    code, out, _err = call("convert", "--instant", "2026-09-28T12:00:00Z", *ADDIS)
    assert code == 0
    assert "UTC       :" in out and "civil     :" in out and "Waqt      :" in out


def test_umm_al_qura_provider_is_listed_and_selectable_by_name():
    # Sprint 13: `ephem` is a real dependency of waqt-core, so umm-al-qura must now produce output.
    _, providers_out, _err = call("--json", "providers")
    names = [p["name"] for p in json.loads(providers_out)["providers"]]
    assert "umm-al-qura" in names
    code, out, err = call("--json", "convert", "--gregorian", "2026-09-28", "--provider", "umm-al-qura")
    assert code == 0, err
    assert "Traceback" not in err and "umm-al-qura" in out


def test_schedule_reminder_before_and_after_are_mutually_exclusive():
    code, out, _err = call("schedule", "reminder", "--event", "maghrib", *ADDIS, *INSTANT)
    assert code != 0  # SystemExit path: neither --minutes-before nor --minutes-after given


def test_schedule_reminder_minutes_before_maghrib():
    code, out, _err = call("schedule", "reminder", "--event", "maghrib", "--minutes-before", "30", *ADDIS, *INSTANT)
    assert code == 0 and "resolve_point" in out and "status    : OK" in out


def test_schedule_window_fajr_to_sunrise_matches_events_timeline():
    _, ev, _err = call("--json", "events", *ADDIS, *INSTANT)
    events = {e["name"]: e for e in json.loads(ev)["events"]}
    code, out, _err = call("--json", "schedule", "window", "--from", "fajr", "--to", "sunrise", *ADDIS, *INSTANT)
    result = json.loads(out)["result"]
    assert result["start"]["instant"] == events["fajr"]["instant"]
    assert result["end"]["instant"] == events["sunrise"]["instant"]


def test_schedule_until_asr():
    code, out, _err = call("schedule", "until", "--event", "asr", *ADDIS, *INSTANT)
    assert code == 0 and "seconds   :" in out


def test_schedule_rule_reads_raw_operation_json(tmp_path):
    p = tmp_path / "op.json"
    p.write_text(json.dumps({"operation": {"op": "day_bounds"}}))
    code, out, _err = call("schedule", "rule", str(p), *ADDIS, *INSTANT)
    assert code == 0 and "day_bounds" in out


def test_providers_lists_all_four():
    code, out, _err = call("providers")
    assert code == 0
    for name in ("arithmetic-tabular", "umm-al-qura", "declared", "local-observation"):
        assert name in out


def test_version_reports_every_axis():
    code, out, _err = call("version")
    assert code == 0
    assert "waqt-cli" in out and "waqt-core" in out and "engine" in out and "vector set" in out


def test_undefined_polar_day_is_reported_not_crashed():
    code, out, _err = call("now", "--lat", "89.9", "--lon", "0", "--instant", "2026-06-21T00:00:00Z")
    assert code == 0
    assert "undefined" in out.lower()


def test_bad_gregorian_date_exits_nonzero():
    code, out, _err = call("convert", "--gregorian", "not-a-date")
    assert code != 0


def test_json_flag_is_global_not_per_subcommand():
    code, out, _err = call("--json", "providers")
    data = json.loads(out)
    assert "providers" in data

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


def test_convert_hijri_to_gregorian_default_provider_is_umm_al_qura():
    code, out, _err = call("convert", "--hijri", "1448-4-15")                          # --provider omitted: API 1.7.0 default
    assert code == 0 and "2026-09-26" in out
    code2, out2, _ = call("convert", "--hijri", "1448-4-15", "--provider", "umm-al-qura")
    assert code2 == 0 and "2026-09-26" in out2


def test_convert_hijri_to_gregorian_arithmetic_tabular_still_selectable():
    code, out, _err = call("convert", "--hijri", "1448-4-15", "--provider", "arithmetic-tabular")
    assert code == 0 and "2026-09-28" in out                                           # the pre-1.7.0 default result


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


def test_provider_flag_default_is_the_single_waqt_core_default():
    import waqt_local
    from waqt_core.calendar_providers import DEFAULT_CALENDAR_PROVIDER
    from waqt_cli import main as m
    ap = m.build_parser() if hasattr(m, "build_parser") else None
    code, out, _ = call("convert", "--hijri", "1448-4-15")
    assert waqt_local.DEFAULT_CALENDAR_PROVIDER == DEFAULT_CALENDAR_PROVIDER == "umm-al-qura" and code == 0 and "2026-09-26" in out


# ---- ERR-004 / CAL-013 (DR-0011, DR-0012) -----------------------------------------------------------------------------
@pytest.mark.parametrize("flag,value", [("--fajr-angle", "95"), ("--fajr-angle", "nan"), ("--isha-angle", "0"), ("--asr-ratio", "0")])
def test_invalid_profile_is_rejected_with_a_clear_message(flag, value):
    code, out, err = call("now", *ADDIS, "--timezone", "Africa/Addis_Ababa", *INSTANT, flag, value)
    assert code != 0 and "must be a finite number" in (out + err)


@pytest.mark.parametrize("date", ["1699-12-31", "2301-01-01"])
def test_out_of_range_gregorian_date_prints_the_waqt_day_instead_of_crashing(date):
    code, out, err = call("convert", "--gregorian", date, *ADDIS, "--timezone", "Africa/Addis_Ababa")
    assert code == 0 and "Traceback" not in (out + err) and "TypeError" not in (out + err)
    assert "unavailable" in out and "calendar_error" in out and date in out


def test_out_of_range_instant_prints_the_waqt_clock_and_a_calendar_notice():
    code, out, err = call("now", *ADDIS, "--timezone", "Africa/Addis_Ababa", "--instant", "1699-12-31T12:00:00Z")
    assert code == 0 and "Waqt clock" in out and "unavailable" in out


def test_now_at_bt_flag_is_opt_in():
    code_default, out_default, _ = call("now", *ADDIS, "--timezone", "Africa/Addis_Ababa", *INSTANT)
    assert code_default == 0
    assert "AT/BT" not in out_default

    code_flag, out_flag, _ = call("now", *ADDIS, "--timezone", "Africa/Addis_Ababa", *INSTANT, "--at-bt")
    assert code_flag == 0
    assert "AT/BT       :" in out_flag
    assert "BT" in out_flag or "AT" in out_flag


def test_now_at_bt_json_flag_leaves_json_unaltered():
    code_json_default, out_json_default, _ = call("--json", "now", *ADDIS, "--timezone", "Africa/Addis_Ababa", *INSTANT)
    code_json_atbt, out_json_atbt, _ = call("--json", "now", *ADDIS, "--timezone", "Africa/Addis_Ababa", *INSTANT, "--at-bt")
    assert code_json_default == 0 and code_json_atbt == 0
    assert json.loads(out_json_default) == json.loads(out_json_atbt)


"""waqt — reference CLI. Argument parsing and dispatch; no Waqt semantics."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional, Sequence

from . import backend, render
from ._version import __version__

EVENTS = ["fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha"]


class CliUsageError(Exception):
    """A usage problem the CLI itself detected (not from waqt_local)."""


def _core_version() -> str:
    from waqt_core import __version__ as v  # version string only, for display

    return v


def _loc(p: argparse.ArgumentParser) -> None:
    p.add_argument("--lat", type=float, required=True, help="latitude, degrees (north +)")
    p.add_argument("--lon", type=float, required=True, help="longitude, degrees (east +)")
    p.add_argument("--elevation", type=float, default=0.0, help="metres above sea level (default 0)")
    p.add_argument("--timezone", default=None, help="IANA timezone override (default: resolved from lat/lon)")


def _profile(p: argparse.ArgumentParser) -> None:
    p.add_argument("--fajr-angle", type=float, default=18.0)
    p.add_argument("--isha-angle", type=float, default=17.0)
    p.add_argument("--asr-ratio", type=float, default=1.0, help="1 = Shafi'i/Maliki/Hanbali, 2 = Hanafi")


def _provider(p: argparse.ArgumentParser) -> None:
    p.add_argument("--provider", default="umm-al-qura",
                   help="Hijri calendar provider (see `waqt providers`; default umm-al-qura)")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="waqt", description="Reference Waqt CLI: local, offline, no server.")
    ap.add_argument("--version", action="version", version=f"waqt-cli {__version__}")
    ap.add_argument("--json", action="store_true", help="print the raw waqt_local result as JSON (metadata included)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("now", help="the Waqt clock, Hijri date and next event for a place")
    _loc(s); _profile(s); _provider(s)
    s.add_argument("--instant", default=None, help="ISO 8601 (default: now)")

    s = sub.add_parser("events", help="the prayer/event timeline for the Waqt day containing an instant")
    _loc(s); _profile(s); _provider(s)
    s.add_argument("--instant", default=None)

    s = sub.add_parser("convert", help="Gregorian <-> Hijri <-> Waqt")
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--gregorian", metavar="YYYY-MM-DD", help="Gregorian date -> Hijri (no location) or Waqt day (with --lat/--lon)")
    g.add_argument("--hijri", metavar="YYYY-MM-DD", help="Hijri date (year-month-day) -> Gregorian")
    g.add_argument("--instant", metavar="ISO", help="an instant -> every representation (needs --lat/--lon for Waqt)")
    s.add_argument("--lat", type=float); s.add_argument("--lon", type=float)
    s.add_argument("--elevation", type=float, default=0.0); s.add_argument("--timezone", default=None)
    _profile(s); _provider(s)

    s = sub.add_parser("schedule", help="scheduling on the Waqt day (reminders, windows, time-until)")
    ssub = s.add_subparsers(dest="schedule_cmd", required=True)
    r = ssub.add_parser("reminder", help="an instant N minutes before/after the next occurrence of an event")
    r.add_argument("--event", choices=EVENTS, required=True)
    r.add_argument("--minutes-before", type=float, default=None)
    r.add_argument("--minutes-after", type=float, default=None)
    w = ssub.add_parser("window", help="the interval between two events of the Waqt day")
    w.add_argument("--from", dest="from_event", choices=EVENTS, required=True)
    w.add_argument("--to", dest="to_event", choices=EVENTS, required=True)
    w.add_argument("--day", type=int, default=0, help="Waqt-day offset (default 0 = the day containing --instant)")
    u = ssub.add_parser("until", help="seconds until the next occurrence of an event")
    u.add_argument("--event", choices=EVENTS, required=True)
    raw = ssub.add_parser("rule", help="run a raw scheduling operation from a JSON file (or - for stdin); see docs/SCHEDULING.md")
    raw.add_argument("file")
    for sp in (r, w, u, raw):
        _loc(sp); _profile(sp); _provider(sp)
        sp.add_argument("--instant", default=None, help="anchor instant (default: now)")

    sub.add_parser("providers", help="list Hijri calendar providers")
    sub.add_parser("version", help="every version axis of this installation (waqt-core, engine revision, ...)")
    return ap


def _resolve_request(a, operation: dict) -> dict:
    return {
        "location": {"lat": a.lat, "lon": a.lon, "elevation_m": a.elevation},
        "profile": {"fajr_angle_deg": a.fajr_angle, "isha_angle_deg": a.isha_angle, "asr_shadow_ratio": a.asr_ratio},
        "calendar_provider": a.provider,
        "timezone_override": a.timezone,
        "anchor": a.instant,
        "operation": operation,
    }


def _schedule_operation(a) -> dict:
    """Map a friendly subcommand onto the documented scheduling operation JSON
    (docs/SCHEDULING.md §8). Pure translation; the engine gives the answer."""
    if a.schedule_cmd == "reminder":
        if (a.minutes_before is None) == (a.minutes_after is None):
            raise CliUsageError("waqt schedule reminder: give exactly one of --minutes-before / --minutes-after")
        minutes = -a.minutes_before if a.minutes_before is not None else a.minutes_after
        return {"op": "resolve_point", "point": {"type": "offset", "minutes": minutes,
                                                 "base": {"type": "next_event", "name": a.event}}}
    if a.schedule_cmd == "window":
        ev = lambda n: {"type": "event", "name": n, "day": a.day}  # noqa: E731
        return {"op": "resolve_interval", "interval": {"type": "interval", "start": ev(a.from_event), "end": ev(a.to_event),
                                                       "start_inclusive": True, "end_inclusive": False}}
    if a.schedule_cmd == "until":
        return {"op": "until", "name": a.event}
    src = sys.stdin.read() if a.file == "-" else open(a.file, encoding="utf-8").read()
    op = json.loads(src)
    return op.get("operation", op)


def run(argv: Optional[Sequence[str]] = None, out=None) -> int:
    out = out or sys.stdout
    a = build_parser().parse_args(argv)
    lib = backend.lib
    core_v = _core_version()

    def emit(data: dict, text: str) -> None:
        print(json.dumps(data, indent=2, ensure_ascii=False) if a.json else text, file=out)

    try:
        if a.cmd in ("now", "events"):
            data = lib.waqt(lat=a.lat, lon=a.lon, elevation_m=a.elevation, instant=a.instant, timezone_override=a.timezone,
                            fajr_angle=a.fajr_angle, isha_angle=a.isha_angle, asr_ratio=a.asr_ratio, calendar_provider=a.provider)
            emit(data, (render.render_now if a.cmd == "now" else render.render_events)(data, core_v))
        elif a.cmd == "convert":
            have_loc = a.lat is not None and a.lon is not None
            common = dict(calendar_provider=a.provider)
            if a.hijri:
                y, m, d = (int(x) for x in a.hijri.split("-"))
                data = lib.convert("to-gregorian", year=y, month=m, day=d, **common)
            elif a.gregorian and not have_loc:
                data = lib.convert("to-hijri", date=a.gregorian, **common)
            elif a.gregorian:
                data = lib.waqt_day_for_gregorian_date(date=a.gregorian, lat=a.lat, lon=a.lon, elevation_m=a.elevation,
                                                       timezone_override=a.timezone, fajr_angle=a.fajr_angle,
                                                       isha_angle=a.isha_angle, asr_ratio=a.asr_ratio, **common)
            else:
                data = lib.represent_instant(instant=a.instant, lat=a.lat, lon=a.lon, elevation_m=a.elevation,
                                             timezone_override=a.timezone, fajr_angle=a.fajr_angle,
                                             isha_angle=a.isha_angle, asr_ratio=a.asr_ratio, **common)
            emit(data, render.render_convert(data, core_v))
        elif a.cmd == "schedule":
            data = lib.schedule_resolve(_resolve_request(a, _schedule_operation(a)))
            emit(data, render.render_schedule(data, core_v))
        elif a.cmd == "providers":
            data = lib.list_calendar_providers()
            emit(data, "\n".join(f"{p['name']:<22} reverse={'yes' if p['supports_reverse_conversion'] else 'no '}  {p['description'][:80]}"
                                 for p in data["providers"]))
        elif a.cmd == "version":
            data = lib.version()
            data = {**data, "waqt_cli_version": __version__}
            c = data["computation"]
            emit(data, "\n".join([
                f"waqt-cli        {__version__}",
                f"waqt-local      {data['waqt_local_version']}",
                f"waqt-core       {data['waqt_core_version']}",
                f"engine          {c['engine']}  revision {c['revision']}  accuracy {c['accuracy_level']}",
                f"vector set      {data['conformance_vectors']['vector_set_version']} (generated at engine revision "
                f"{data['conformance_vectors']['generated_at_engine_revision']})",
            ]))
        return 0
    except (backend.WaqtLocalError, CliUsageError, ValueError, OSError) as e:
        print(f"waqt: {e}", file=sys.stderr)
        return 2
    except Exception as e:  # pragma: no cover - last resort so a dependency
        # error (e.g. a Hijri provider needing an optional astronomy dependency that is not
        # installed here) is a
        # clean CLI error, not a Python traceback in the user's terminal.
        print(f"waqt: {type(e).__name__}: {e}", file=sys.stderr)
        return 3


def entrypoint() -> None:
    sys.exit(run())


if __name__ == "__main__":
    entrypoint()

"""Presentation only: turn dicts produced by waqt_local into text.

Nothing here decides *when* anything happens. Times are converted from the ISO
instants Waqt returned into the civil timezone Waqt also returned (`timezone.name`),
which is display formatting, not a computation of Waqt semantics.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

EVENT_LABEL = {
    "fajr": "Fajr", "sunrise": "Sunrise", "dhuhr": "Dhuhr",
    "asr": "Asr", "maghrib": "Maghrib", "isha": "Isha",
}


def local_hhmmss(iso: Optional[str], tz_name: Optional[str]) -> str:
    if not iso:
        return "—"
    dt = datetime.fromisoformat(iso)
    if tz_name:
        try:
            dt = dt.astimezone(ZoneInfo(tz_name))
        except Exception:
            pass
    return dt.strftime("%H:%M:%S")


def hms(seconds: Optional[float]) -> str:
    if seconds is None:
        return "—"
    s = int(abs(seconds))
    return f"{'-' if seconds < 0 else ''}{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def metadata_lines(comp: Optional[dict], hijri: Optional[dict], core_version: str) -> list:
    """The computation/provider metadata every command prints (or, with --json,
    leaves inside the payload). One place, so no command can forget it."""
    lines = []
    if comp:
        dt = comp.get("delta_t_seconds")
        lines.append(
            f"computation : {comp.get('engine')} r{comp.get('revision')} · accuracy {comp.get('accuracy_level')}"
            f" · timescale {comp.get('timescale_model')}" + (f" (ΔT {dt:g} s)" if dt is not None else "")
        )
    if hijri and hijri.get("provider"):
        p = hijri["provider"]
        lines.append(f"hijri       : provider {p.get('name')} ({p.get('version')})")
    lines.append(f"waqt-core   : {core_version}")
    return lines


def render_now(data: dict, core_version: str) -> str:
    tz = (data.get("timezone") or {}).get("name")
    out = []
    if data.get("status") != "OK":
        out.append(f"Waqt day undefined here/now: {data.get('undefined_reason')}")
        out += metadata_lines(data.get("computation"), None, core_version)
        return "\n".join(out)
    h = data["hijri"]
    out.append(f"Waqt clock  : {data['waqt']['display']}   ({data['weekday']})")
    out.append(f"Hijri       : {h['display']}")
    out.append(f"timezone    : {tz}")
    out.append(f"day opened  : {local_hhmmss(data['day']['maghrib_open'], tz)} local (Maghrib)")
    out.append(f"day closes  : {local_hhmmss(data['day']['maghrib_close'], tz)} local (Maghrib)")
    if data.get("day", {}).get("note"):
        out.append(f"note        : {data['day']['note']}")
    ne = data.get("next_event")
    if ne:
        out.append(f"next event  : {EVENT_LABEL.get(ne['name'], ne['name'])} at {local_hhmmss(ne['instant'], tz)} "
                   f"(in {ne['countdown']['display']})")
    out.append("")
    out += metadata_lines(data.get("computation"), h, core_version)
    return "\n".join(out)


def render_events(data: dict, core_version: str) -> str:
    tz = (data.get("timezone") or {}).get("name")
    out = [f"{'event':<9} {'local':<9} {'waqt':<10} status"]
    now = None
    for ev in data.get("events", []):
        marker = "  <- next" if data.get("next_event") and data["next_event"]["name"] == ev["name"] else ""
        if ev.get("instant") is None:
            out.append(f"{EVENT_LABEL.get(ev['name'], ev['name']):<9} {'—':<9} {'—':<10} does not occur")
            continue
        out.append(f"{EVENT_LABEL.get(ev['name'], ev['name']):<9} {local_hhmmss(ev['instant'], tz):<9} "
                   f"{ev['reading']['display']:<10} ok{marker}")
    out.append("")
    if data.get("hijri"):
        out.append(f"Hijri {data['hijri']['display']} · timezone {tz}")
    out += metadata_lines(data.get("computation"), data.get("hijri"), core_version)
    return "\n".join(out)


def render_convert(data: dict, core_version: str) -> str:
    d = data.get("direction")
    out = []
    if d == "to-hijri":
        h = data["output"]["hijri"]
        out.append(f"{data['input']['gregorian_date']}  ->  {h['display']}  [{h['date']}]")
        out += metadata_lines(None, h, core_version)
    elif d == "to-gregorian":
        out.append(f"{data['input']['hijri']}  ->  {data['output']['gregorian_date']} ({data['output']['weekday']})")
        out.append(f"waqt-core   : {core_version}")
    elif d == "instant-to-calendars":
        g, c = data["gregorian"]["utc"], data["gregorian"]["civil"]
        out.append(f"UTC       : {g['date']} {g['time_of_day']}")
        out.append(f"civil     : {c['date']} {c['time_of_day']}  ({c['timezone_name']})")
        w = data["waqt"]
        if w["status"] == "OK":
            day = w["day"]
            out.append(f"Hijri     : {day['hijri']['display']}   ({day['weekday']})")
            out.append(f"Waqt      : {hms(day['position_seconds'])} into the day")
        else:
            out.append(f"Waqt      : undefined ({w.get('undefined_reason')})")
        out.append("")
        h = (w.get("day") or {}).get("hijri") if w["status"] == "OK" else None
        out += metadata_lines(data.get("computation"), h, core_version)
    elif d == "gregorian-date-to-waqt":
        w = data["waqt"]
        if w["status"] == "OK":
            out.append(f"{data['source']['date']}  ->  Hijri {w['hijri']['display']} ({w['weekday']})")
            out.append(f"Waqt day  : {local_hhmmss(w['day']['maghrib_open'], data['timezone']['name'])} local  ->  "
                       f"{local_hhmmss(w['day']['maghrib_close'], data['timezone']['name'])} local "
                       f"({hms(w['day']['length_si_seconds'])})")
        else:
            out.append(f"{data['source']['date']}  ->  undefined ({w.get('undefined_reason')})")
        out.append("")
        out += metadata_lines(data.get("computation"), w.get("hijri"), core_version)
    else:
        out.append(str(data))
    return "\n".join(out)


def render_schedule(data: dict, core_version: str) -> str:
    out = [f"operation : {data.get('operation')}", f"anchor    : {data.get('anchor')}"]
    res = data.get("result") or {}
    for k in ("status", "instant", "seconds", "start", "end", "inside", "reason", "description"):
        if k in res and res[k] is not None:
            out.append(f"{k:<9} : {res[k] if not isinstance(res[k], dict) else res[k].get('instant', res[k])}")
    out.append("")
    out += metadata_lines(data.get("computation"), None, core_version)
    return "\n".join(out)

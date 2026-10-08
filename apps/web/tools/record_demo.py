#!/usr/bin/env python3
"""Record assets/js/demo-data.js from a RUNNING Waqt API (real responses, values unmodified).

    uvicorn waqt.api:app --port 8000 &   python3 tools/record_demo.py [http://localhost:8000]

The sample is used only as the clearly-labelled, frozen demonstration fallback. It also records the extra requests the
Experience Lab needs to be occurrence-aware (tonight's Isha, which /v1/waqt `events` omits because it lists each event's
NEXT occurrence)."""
import json, sys, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
INSTANT = "2026-10-08T09:00:00Z"
Q = dict(lat=9.0192, lon=38.7525, calendar_provider="umm-al-qura")

def get(**extra):
    url = f"{BASE}/v1/waqt?" + urllib.parse.urlencode({**Q, **extra})
    return url, json.load(urllib.request.urlopen(url))

url, body = get(instant=INSTANT)
d = body["data"]
keep = {k: d[k] for k in ("status", "instant", "location", "timezone", "undefined_reason", "day", "hijri", "calendar_error", "weekday", "waqt", "events", "event_representations", "next_event", "computation")}
opened = datetime.fromisoformat(d["day"]["maghrib_open"]) + timedelta(seconds=1)
_, first = get(instant=opened.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"))
ne = first["data"]["next_event"]
_, at = get(instant=ne["instant"])
out = {
    "label": "Recorded sample — NOT live data",
    "source": "GET " + url.replace(BASE, ""),
    "api_version": body["meta"]["api_version"],
    "recorded": INSTANT[:10] + " (local run of this repository's API)",
    "data": keep,
    "own_day_isha": {"next_event_after_open": ne, "reading_at_event": at["data"]["waqt"]["reading"]},
}
js = ("/* Recorded sample of a real GET /v1/waqt response (values unmodified), used ONLY as the clearly-labelled\n"
      "   demonstration fallback when the live API is unreachable. It is frozen: demo mode never ticks, so it cannot\n"
      "   be mistaken for a live clock. Regenerate with tools/record_demo.py. */\n"
      "window.WAQT_DEMO = " + json.dumps(out, indent=1) + ";\n")
open("assets/js/demo-data.js", "w", encoding="utf-8").write(js)
print("recorded", d["hijri"]["display"], d["hijri"]["provider"]["name"], "| tonight's", ne["name"], ne["instant"])

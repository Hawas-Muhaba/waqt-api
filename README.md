# Waqt — Stage 1 reference implementation

Reference implementation of the **Waqt Core Time Model v0.1**: Makkah
reference, day boundary, the fixed hour, and event positions. Nothing
else — see `SCOPE.md` for exactly what that means and what's deferred.

```
waqt/
  solar.py   — solar event engine (sunrise, sunset, transit, Fajr, Asr, Isha)
  hijri.py   — calendar provider interface + one reference provider
  core.py    — the Core Time Model itself (day boundary, hour, events)
  api.py     — HTTP surface: GET /v1/waqt
tests/
  test_core.py — validates the claims made in SCOPE.md, not just runs them once
SCOPE.md     — what's implemented, what isn't, and known limitations (read this first)
```

## Quickstart

```bash
pip install -r requirements.txt
uvicorn waqt.api:app --reload --port 8000
curl "http://localhost:8000/v1/waqt?lat=9.0192&lon=38.7525"
```

## Verify

```bash
python3 -m pytest tests/ -v
```

## Example response

```json
{
  "status": "OK",
  "hijri": { "date": "1448-04-08", "display": "8 Rabi al-Thani 1448 AH",
             "weekday": "al-Ithnayn", "provider": "arithmetic-tabular" },
  "day": { "maghrib_open": "...", "maghrib_close": "...",
           "length_si_seconds": 86363.9,
           "note": "Day is shorter than 24:00:00 today; ..." },
  "waqt": { "reading": "04:06:08", "display": "Waqt 04:06:08" },
  "events": [
    { "name": "fajr", "instant": "...", "reading": "10:42:41" },
    { "name": "sunrise", "instant": "...", "reading": "11:52:16" },
    { "name": "dhuhr", "instant": "...", "reading": "17:56:02" },
    { "name": "asr", "instant": "...", "reading": "21:09:27" },
    { "name": "maghrib", "instant": "...", "reading": "23:59:23" },
    { "name": "isha", "instant": "...", "reading": "25:04:53" }
  ],
  "next_event": { "name": "fajr", "instant": "...", "countdown": "06:36:33" }
}
```

Read `SCOPE.md` before using this for anything beyond development and review.

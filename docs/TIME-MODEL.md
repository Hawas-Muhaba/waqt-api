# The Waqt Time Model

This explains *why* the numbers in the API look the way they do. If you just want the field-by-field contract, see [`API.md`](API.md). If you want the original design reasoning in full, see the project's `waqt-core-time-model-v0.1.md` and the critique/proposal documents it grew out of — this page is the short version aimed at someone consuming the API, not designing it.

## The day starts at Maghrib, not midnight

A Waqt day runs from one sunset to the next: `[Maghrib(D), Maghrib(D+1))`. This is not a metaphor — it is the literal boundary the API uses to decide which Gregorian date a Hijri date is reported against (see `API.md` §8, "the one gotcha").

One direct consequence: **the weekday changes at Maghrib**, not at Gregorian midnight. Jumu'ah (Friday) begins at Maghrib on what a Gregorian calendar calls Thursday evening — which is traditionally correct (*laylat al-Jumu'ah* is Thursday night), not a bug.

## The hour is real, and resets at Maghrib

Earlier drafts of this project considered a *variable*-length hour (splitting daylight into 12 unequal parts, the classical Islamic clock). The shipped model rejected that: an hour in the Waqt API is an ordinary SI hour — 60 real minutes, 60 real seconds — counted from the moment of that day's opening Maghrib, and reset to zero at the next one.

This is why `waqt.reading.seconds` in `/v1/waqt` is just elapsed seconds since Maghrib, and why you can safely do arithmetic on it.

## The day is not exactly 24 hours

Because Maghrib itself drifts slightly earlier or later each day (with latitude and season), the interval `[Maghrib(D), Maghrib(D+1))` is **not** exactly 86,400 seconds — typically within a few minutes of it, more at high latitude. `day.length_si_seconds` in `/v1/day` and `/v1/waqt` reports the real value.

One visible effect: on a day that runs slightly long, `waqt.reading.display` can briefly read past `24:00:00` in the minutes before the next Maghrib. This is shown deliberately, not clipped — it's true, and a reading past `24:00:00` is itself informative ("Maghrib is close").

## Events are positions, not boundaries

Fajr, sunrise, Dhuhr, Asr, and Isha do **not** define the day's structure — only Maghrib does. Each event is just an instant, reported as a position on that day's hour grid (`events[].reading`). This is a deliberate design choice with one big practical payoff: **changing `fajr_angle`, `isha_angle`, or `asr_ratio` only ever moves that one event's own reading.** It cannot change what the clock reads at any other moment, and it cannot change the day boundary. If you want proof rather than a description: `tests/test_calendar_providers.py::test_swapping_calendar_provider_does_not_change_astronomy` and the equivalent astronomy-profile tests in `tests/test_core.py` assert exactly this, and pass.

## Makkah computes the calendar, not the clock

The Hijri *date* is computed once, globally, using Makkah's own Maghrib as the reference point for evaluating month-length rules (see `CALENDARS.md`). It has no bearing on your local clock reading, your local Maghrib time, or your local day boundary — those are always computed at *your* coordinates. Two people in different countries can be on different Waqt-day clock readings right now while agreeing on today's Hijri date, and vice versa.

## Everything is a projection over an ordinary UTC instant

Underneath all of the above, every computation starts from a plain UTC timestamp. Nothing in Waqt invents a new absolute time standard — it's a *rendering* of an ordinary instant into Islamic terms, for a given place. This is why every endpoint accepts (or defaults) a UTC `instant`, and why comparing, sorting, or storing by the Waqt reading itself is never a good idea — always do that on the underlying instant, and use Waqt's readings for display.

## AT/BT — an optional 12-hour presentation layer (experimental)

The core clock is always a 24 h+ counter from Maghrib. The AT/BT layer (`waqt_core.display.at_bt`, opt-in via `waqt-cli --at-bt`) maps that into a more familiar 12-hour vocabulary without touching the underlying model:

- **BT (Before Twelve):** hours 00–11 after Maghrib. The period from Maghrib to just before the midpoint of the day.
- **AT (After Twelve):** hours 12–23 (and beyond, on a long day). The period from the midpoint onward.

A reading of `14:30:00` displays as `AT 02:30:00`. A reading of `25:00:00` (past-24 on a long day) displays as `AT 13:00:00 +1 day`.

This convention is **display-only and experimental** — it is not normative Waqt Standard and is not part of the conformance contract. It has no effect on any computed instant, event time, or day boundary. `waqt_core.display.at_bt.format_at_bt(display_string)` converts any `HH:MM:SS` Waqt reading to its AT/BT form.

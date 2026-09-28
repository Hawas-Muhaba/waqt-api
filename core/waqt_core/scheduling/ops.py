"""
waqt.scheduling.ops — the operation dispatcher.

One JSON-shaped request format used by three different callers, so they
cannot drift apart:

  * POST /v1/schedule/resolve       (the HTTP API)
  * tests/vectors/scheduling_vectors.json  (portable conformance vectors)
  * any Python caller that wants to drive the engine from data

    {"op": "resolve_point",    "point": {...}}
    {"op": "resolve_interval", "interval": {...}}
    {"op": "evaluate",         "interval": {...}, "instant": "..."}
    {"op": "check_deadline",   "point": {...}, "now": "..."}          # now optional
    {"op": "until" | "since",  "name": "maghrib", "on_undefined": "strict"|"skip"}
    {"op": "next_event"}
    {"op": "event_position",   "name": "isha", "day": null | int}
    {"op": "day_bounds"}
    {"op": "classify_span",    "start": "...", "end": "...", "end_inclusive": false}

`instant` (until/since/next_event/day_bounds/evaluate) defaults to the
anchor. Every op returns the result's `to_dict()` — the normative
output shape the conformance vectors freeze.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .engine import SchedulingEngine
from .model import RuleError, UndefinedPolicy, interval_from_dict, parse_instant, point_from_dict

OPS = ("resolve_point", "resolve_interval", "evaluate", "check_deadline", "until", "since",
       "next_event", "event_position", "day_bounds", "classify_span")


def _req(op: dict, key: str) -> Any:
    if key not in op:
        raise RuleError(f"operation {op.get('op')!r}: missing required field {key!r}")
    return op[key]


def run_operation(engine: SchedulingEngine, anchor: datetime, op: Any, round_seconds: bool = False) -> dict:
    if not isinstance(op, dict) or "op" not in op:
        raise RuleError("An operation must be a JSON object with an `op` field")
    kind = op["op"]
    inst = parse_instant(op["instant"]) if op.get("instant") is not None else anchor

    if kind == "resolve_point":
        r = engine.resolve_point(point_from_dict(_req(op, "point")), anchor)
    elif kind == "resolve_interval":
        r = engine.resolve_interval(interval_from_dict(_req(op, "interval")), anchor)
    elif kind == "evaluate":
        r = engine.evaluate(interval_from_dict(_req(op, "interval")), parse_instant(_req(op, "instant")), anchor=anchor)
    elif kind == "check_deadline":
        now = parse_instant(op["now"]) if op.get("now") is not None else None
        r = engine.check_deadline(point_from_dict(_req(op, "point")), anchor, now)
    elif kind in ("until", "since"):
        policy = op.get("on_undefined", UndefinedPolicy.STRICT)
        if policy not in (UndefinedPolicy.STRICT, UndefinedPolicy.SKIP):
            raise RuleError("`on_undefined` must be 'strict' or 'skip'")
        name = _req(op, "name")
        if name not in ("fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha"):
            raise RuleError(f"Unknown event {name!r}")
        r = (engine.until if kind == "until" else engine.since)(name, inst, policy)
    elif kind == "next_event":
        r = engine.next_event(inst)
    elif kind == "event_position":
        day = op.get("day")
        if day is not None and (isinstance(day, bool) or not isinstance(day, int)):
            raise RuleError("`day` must be an integer or null")
        name = _req(op, "name")
        if name not in ("fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha"):
            raise RuleError(f"Unknown event {name!r}")
        r = engine.event_position(name, anchor, day)
    elif kind == "day_bounds":
        r = engine.day_bounds(inst)
    elif kind == "classify_span":
        end_inclusive = op.get("end_inclusive", False)
        if not isinstance(end_inclusive, bool):
            raise RuleError("`end_inclusive` must be a boolean")
        r = engine.classify_span(parse_instant(_req(op, "start")), parse_instant(_req(op, "end")), end_inclusive)
    else:
        raise RuleError(f"Unknown op {kind!r}. Known: {list(OPS)}")
    return r.to_dict(round_seconds)

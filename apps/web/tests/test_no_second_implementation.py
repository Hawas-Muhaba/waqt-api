"""Structural guard for apps/web/index.html (Sprint 12 Goal A.2), the same
rule as apps/cli: 'consume Waqt, not reimplement it.' A static page has no
import graph to check, so this inspects the inline <script> text directly
for vocabulary that would mean the page is computing Waqt facts itself
rather than reading them out of an API response.

Plain-Python/no-browser: cannot execute the page's JS or open a real
browser in this environment. tests/manual_smoke.md is the checklist for a
human (or a headless-browser CI job) to run this for real.
"""

from __future__ import annotations

import re
from pathlib import Path

PAGE = Path(__file__).resolve().parent.parent / "index.html"

# Constants/vocabulary that belong to waqt-core, never to a consumer.
BANNED = [
    "18.0", "17.0",          # default Fajr/Isha angles (the page must send angles to
                              # the server if it ever exposes them, never assume them)
    "1948440",                # arithmetic-tabular Hijri epoch (JDN)
    "julian_century", "declination", "equation_of_time", "delta_t_seconds =",
    "solveHourAngle", "computeWaqt(", "waqt-noaa",  # must never be hard-coded; only ever read from a response
]

# A GET to these paths is the whole point; nothing else network-facing is expected.
ALLOWED_API_PATHS = {"/v1/waqt", "/v1/events", "/v1/calendar", "/v1/version"}


def _script() -> str:
    html = PAGE.read_text()
    m = re.search(r'<script>\s*"use strict";(.*?)</script>', html, re.S)
    assert m, "expected an inline <script> with \"use strict\";"
    return m.group(1)


def test_page_exists_and_is_self_contained():
    html = PAGE.read_text()
    # no external script/style hosts: dependency-free per the roadmap brief
    assert "<script src=" not in html
    assert not re.search(r'<link[^>]+stylesheet[^>]+http', html)


def test_no_astronomy_or_calendar_vocabulary_in_script():
    script = _script()
    for bad in BANNED:
        assert bad not in script, f"index.html contains {bad!r}: looks like a second computation, not display"


def test_every_fetched_path_is_a_known_waqt_endpoint():
    script = _script()
    paths = set(re.findall(r'getJSON\(\s*"([^"]+)"', script))
    assert paths, "expected at least one getJSON(...) call"
    assert paths <= ALLOWED_API_PATHS, f"unexpected endpoint(s): {paths - ALLOWED_API_PATHS}"
    assert "/v1/waqt" in paths, "the combined endpoint should back the main view"


def test_clock_tick_only_adds_elapsed_wallclock_time_to_a_server_reading():
    """The one 'derived' number in the page (the ticking clock between polls)
    must be `serverSeconds + elapsed`, not a recomputation from an instant."""
    script = _script()
    m = re.search(r"function tick\(\)\s*\{(.*?)\n\}", script, re.S)
    assert m
    body = m.group(1)
    assert "clockAnchor.serverSeconds" in body
    assert "Date.now()" in body
    # must not import/construct a solar-position computation
    for bad in ("Math.sin", "Math.cos", "getSolar", "computeEvents"):
        assert bad not in body


def test_reads_computation_fields_verbatim_not_relabelled():
    script = _script()
    assert "c.engine" in script and "c.revision" in script and "c.accuracy_level" in script
    assert "waqt.computation" in script or "c = waqt" in script or "waqtData.computation" in script


def test_no_hardcoded_localStorage_of_waqt_state():
    """Only the API base URL (a UI preference) may be persisted; no computed
    Waqt fact (a reading, a date, an event instant) may be cached locally."""
    script = _script()
    assert re.search(r'localStorage\.(?:setItem|getItem)\(\s*LS_KEY\b', script), (
        "expected localStorage access via the LS_KEY constant"
    )
    m = re.search(r'LS_KEY\s*=\s*"([^"]+)"', script)
    assert m and m.group(1) == "waqt:apiBase"
    # and no *other* localStorage key anywhere (a computed Waqt fact getting cached)
    other_literal_keys = [k for k in re.findall(r'localStorage\.(?:setItem|getItem)\(\s*"([^"]+)"', script)]
    assert other_literal_keys == []

"""The API default and every lower-level default are ONE value, defined once in waqt-core.

waqt-core (library), the HTTP API, the offline facade `waqt_local`, the `waqt` CLI and Waqt Web must agree, and the
conformance contract and the independent implementation must describe the same default.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

import waqt_local
import waqt.api.providers as api_providers
from waqt.api import app
from waqt_core.calendar_providers import DEFAULT_CALENDAR_PROVIDER as CORE_DEFAULT, default_calendar_provider
from waqt_core.calendar_providers import default as core_default_module

ROOT = Path(__file__).resolve().parent.parent
c = TestClient(app, raise_server_exceptions=False)


def test_core_api_local_and_cli_share_one_default_value():
    assert CORE_DEFAULT == "umm-al-qura"
    assert api_providers.DEFAULT_CALENDAR_PROVIDER == waqt_local.DEFAULT_CALENDAR_PROVIDER == CORE_DEFAULT
    import waqt_local.providers as lp
    assert lp.DEFAULT_CALENDAR_PROVIDER is CORE_DEFAULT is api_providers.DEFAULT_CALENDAR_PROVIDER   # imported, not re-typed
    cli = (ROOT / "apps/cli/waqt_cli/main.py").read_text(encoding="utf-8")                  # runtime check: apps/cli/tests
    assert "default=backend.lib.DEFAULT_CALENDAR_PROVIDER" in cli and "arithmetic-tabular\"," not in cli


def test_no_module_re_types_the_default_literal():
    """The literal may be DEFINED once (core). Everywhere else it must be imported."""
    defs = []
    for pat in ("waqt/api/providers.py", "local/waqt_local/providers.py", "local/waqt_local/facade.py", "apps/cli/waqt_cli/main.py"):
        text = (ROOT / pat).read_text(encoding="utf-8")
        defs += [pat for m in re.finditer(r'DEFAULT_CALENDAR_PROVIDER\s*=\s*"[^"]+"', text)]
    assert defs == [], f"default re-typed instead of imported: {defs}"
    assert re.search(r'^DEFAULT_CALENDAR_PROVIDER = "umm-al-qura"$', (ROOT / "core/waqt_core/calendar_providers/default.py").read_text(encoding="utf-8"), re.M)


def test_core_default_instance_and_api_omitted_provider_name_the_same_provider():
    assert default_calendar_provider().name == c.get("/v1/hijri", params={"date": "2026-09-19"}).json()["data"]["hijri"]["provider"]["name"]
    assert core_default_module.DEFAULT_CALENDAR_PROVIDER == CORE_DEFAULT


def test_waqt_web_config_requests_the_core_default():
    cfg = (ROOT / "apps/web/assets/js/config.js").read_text(encoding="utf-8")
    assert re.search(r'defaultProvider:\s*"%s"' % re.escape(CORE_DEFAULT), cfg)


def test_independent_implementation_and_adapters_default_to_the_core_default():
    for rel in ("conformance/independent/src/ops.mjs", "conformance/independent/src/institutional.mjs", "conformance/independent/src/waqtday.mjs",
                "conformance/adapters/reference_adapter.py"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "'arithmetic-tabular'" not in text and '"arithmetic-tabular"' not in text.replace('"arithmetic-tabular" in', ""), f"{rel} still hard-codes the old default"


# ---- regression: an instant outside umm-al-qura's range must not 500 (the default made this reachable) ----------
def test_calendar_convert_out_of_range_instant_is_200_with_empty_label_and_reason_not_500():
    base = {"lat": 9.0192, "lon": 38.7525}
    for params in ({"direction": "instant-to-calendars", "instant": "1650-09-19T15:42:00Z", **base},
                   {"direction": "gregorian-date-to-waqt", "date": "1650-09-19", **base}):
        r = c.get("/v1/calendar/convert", params=params)
        assert r.status_code == 200, r.text
        w = r.json()["data"]["waqt"]
        h = w.get("hijri") if "hijri" in w else w["day"]["hijri"]
        err = w.get("calendar_error") or w["day"].get("calendar_error")
        assert h is None and "CalendarOutOfRange" in err
        assert w.get("calendar_error_code") == "OUT_OF_RANGE" or w["day"].get("calendar_error_code") == "OUT_OF_RANGE"
        ref = c.get("/v1/calendar/convert", params={**params, "calendar_provider": "arithmetic-tabular"})
        rw = ref.json()["data"]["waqt"]
        assert ref.status_code == 200 and (rw.get("hijri") or rw["day"]["hijri"]) is not None
        assert rw.get("calendar_error") is None and rw.get("calendar_error_code") is None
        assert rw.get("day", {}).get("calendar_error") is None and rw.get("day", {}).get("calendar_error_code") is None


def test_local_facade_matches_the_server_for_an_out_of_range_instant():
    inst = "1650-09-19T15:42:00Z"
    srv = c.get("/v1/calendar/convert", params={"direction": "instant-to-calendars", "instant": inst, "lat": 9.0192, "lon": 38.7525}).json()["data"]
    loc = waqt_local.represent_instant(instant=inst, lat=9.0192, lon=38.7525)
    assert loc["waqt"] == srv["waqt"]

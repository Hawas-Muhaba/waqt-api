"""Sprint 14 -- the AlAdhan provider can NEVER affect astronomical computation.

Three independent guarantees, each tested separately:
  1. STRUCTURAL   no astronomy module imports the provider; nothing in waqt_core but the
                  provider itself can touch the network.
  2. BEHAVIOURAL  events / day boundaries / readings are identical -- exactly, not
                  approximately -- under every provider and every provider failure mode,
                  for normal, high-latitude and polar inputs.
  3. CONTAINMENT  even a calendar provider that raises cannot take the events down with it.
"""
from __future__ import annotations

import ast
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

import waqt_core
from waqt_core.calendar_providers import AlAdhanHijriProvider, UmmAlQuraProvider
from waqt_core.calendar_providers.aladhan import TransportError, TransportResponse
from waqt_core.core import AstronomyProfile, Location, compute_waqt
from waqt_core.hijri import ArithmeticTabularProvider, HijriDate
from waqt_core.timezone_provider import ManualTimezoneProvider

PKG = Path(waqt_core.__file__).parent

# ---------------------------------------------------------------- 1. structural

ASTRONOMY_MODULES = ["solar.py", "timescale.py", "versioning.py", "core.py", "hijri.py"]
NETWORK_MODULES = {"urllib", "urllib.request", "http", "http.client", "socket", "ssl", "requests", "httpx", "aiohttp"}


def _imports(path: Path) -> set[str]:
    out = set()
    for n in ast.walk(ast.parse(path.read_text())):
        if isinstance(n, ast.Import):
            out |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            out.add(("." * n.level) + (n.module or ""))
            out |= {("." * n.level) + (n.module or "") + "." + a.name for a in n.names}
    return out


@pytest.mark.parametrize("mod", ASTRONOMY_MODULES)
def test_astronomy_modules_do_not_import_the_live_provider(mod):
    assert not any("aladhan" in i for i in _imports(PKG / mod)), f"{mod} must not depend on aladhan"


def test_only_the_provider_module_may_import_network_libraries():
    offenders = {}
    for f in PKG.rglob("*.py"):
        bad = {i for i in _imports(f) if i.split(".")[0] in {m.split(".")[0] for m in NETWORK_MODULES}}
        if bad and f.name != "aladhan.py":
            offenders[str(f.relative_to(PKG))] = bad
    assert offenders == {}


def test_aladhan_module_imports_nothing_from_the_astronomy_engine():
    imps = _imports(PKG / "calendar_providers" / "aladhan.py")
    assert not any(x.endswith(("solar", "timescale", "versioning", "core")) for x in imps)


def test_engine_revision_is_unchanged_by_sprint_14():
    from waqt_core.versioning import ENGINE_REVISION
    assert str(ENGINE_REVISION) == "2"


# -------------------------------------------------------------- 2. behavioural

CASES = {
    "normal-addis":        (9.0192, 38.7525, "2026-09-30T09:00:00Z"),
    "high-lat-reykjavik":  (64.15, -21.94, "2026-06-21T12:00:00Z"),   # OK, but Fajr/Isha have no instant
    "polar-tromso-summer": (69.65, 18.96, "2026-06-21T12:00:00Z"),    # UNDEFINED
    "polar-svalbard-dec":  (78.22, 15.63, "2026-12-21T12:00:00Z"),    # UNDEFINED
    "north-pole":          (90.0, 0.0, "2026-06-21T12:00:00Z"),       # UNDEFINED
}


def _astro_fingerprint(r) -> str:
    """Everything astronomical about a result, serialised exactly (repr of floats/datetimes)."""
    return json.dumps({
        "status": r.status, "undefined_reason": r.undefined_reason,
        "events": [(e.name, repr(e.instant)) for e in (r.events or [])],
        "day": (repr(r.day_start_maghrib), repr(r.day_end_maghrib), repr(r.day_length_si_seconds)),
        "hour_reading": r.hour_reading, "hour_length_note": r.hour_length_note,
        "next": (r.next_event.name, repr(r.next_event.instant)) if r.next_event else None,
        "timescale": (r.timescale_model, repr(r.delta_t_seconds)), "tz": r.timezone_name,
    }, sort_keys=True)


def _compute(case, provider):
    lat, lon, t = CASES[case]
    return compute_waqt(datetime.fromisoformat(t.replace("Z", "+00:00")), Location(lat=lat, lon=lon),
                        provider, AstronomyProfile(), tz_provider=ManualTimezoneProvider("UTC"))


def _aladhan(resp_fn, **kw):
    kw.setdefault("fallback", ArithmeticTabularProvider())
    return AlAdhanHijriProvider(transport=lambda u, t, m: resp_fn(u), **kw)


def _ok_body(offset):
    def fn(url):
        dd, mm, yy = url.split("/gToH/")[1].split("?")[0].split("-")
        from datetime import date
        h = ArithmeticTabularProvider().from_gregorian(date(int(yy), int(mm), int(dd)))
        return TransportResponse(200, json.dumps({"code": 200, "data": {
            "hijri": {"day": str(h.day + offset), "month": {"number": h.month}, "year": str(h.year)},
            "gregorian": {"date": f"{dd}-{mm}-{yy}"}}}).encode())
    return fn


def _down(url):
    return TransportError("down")


def _boom(url):
    raise RuntimeError("transport bug")


PROVIDERS = {
    "arithmetic": lambda: ArithmeticTabularProvider(),
    "umm-al-qura": lambda: UmmAlQuraProvider(),
    "aladhan-agrees": lambda: _aladhan(_ok_body(0)),
    "aladhan-disagrees-by-2": lambda: _aladhan(_ok_body(2)),
    "aladhan-down": lambda: _aladhan(_down),
    "aladhan-raising-transport": lambda: _aladhan(_boom),
    "aladhan-garbage": lambda: _aladhan(lambda u: TransportResponse(200, b"{")),
    "aladhan-disabled": lambda: _aladhan(_ok_body(0), enabled=False),
}


@pytest.mark.parametrize("case", sorted(CASES))
def test_astronomy_is_byte_identical_under_every_provider_and_failure_mode(case):
    prints = {name: _astro_fingerprint(_compute(case, make())) for name, make in PROVIDERS.items()}
    assert len(set(prints.values())) == 1, {k: v for k, v in prints.items()}


def test_high_latitude_case_really_has_missing_events_and_polar_really_is_undefined():
    hl = _compute("high-lat-reykjavik", ArithmeticTabularProvider())
    assert hl.status == "OK" and any(e.instant is None for e in hl.events)
    for c in ("polar-tromso-summer", "polar-svalbard-dec", "north-pole"):
        assert _compute(c, ArithmeticTabularProvider()).status == "UNDEFINED"


def test_polar_undefined_never_even_asks_the_remote_service():
    calls = []
    p = _aladhan(lambda u: calls.append(u) or _ok_body(0)(u))
    r = _compute("north-pole", p)
    assert r.status == "UNDEFINED" and r.hijri_date is None and calls == []


def test_normal_and_high_latitude_do_consult_the_provider_exactly_once_per_result():
    for case in ("normal-addis", "high-lat-reykjavik"):
        calls = []
        p = _aladhan(lambda u: calls.append(u) or _ok_body(0)(u))
        r = _compute(case, p)
        assert len(calls) == 1 and r.hijri_date.source == "remote"


def test_hijri_label_changes_but_astronomy_does_not():
    a = _compute("normal-addis", _aladhan(_ok_body(0)))
    b = _compute("normal-addis", _aladhan(_ok_body(2)))
    assert a.hijri_date.day != b.hijri_date.day
    assert _astro_fingerprint(a) == _astro_fingerprint(b)


# ------------------------------------------------------------- 3. containment

class RaisingProvider:
    name, version = "raising", "1"
    def from_gregorian(self, d):
        raise ValueError("calendar exploded")


@pytest.mark.parametrize("case", ["normal-addis", "high-lat-reykjavik"])
def test_a_raising_calendar_provider_cannot_take_the_events_down(case):
    base = _astro_fingerprint(_compute(case, ArithmeticTabularProvider()))
    r = _compute(case, RaisingProvider())
    assert r.hijri_date is None and r.calendar_error == "ValueError: calendar exploded"
    assert _astro_fingerprint(r) == base


def test_calendar_error_is_none_on_the_happy_path():
    assert _compute("normal-addis", ArithmeticTabularProvider()).calendar_error is None


def test_umm_al_qura_outside_its_ephemeris_no_longer_destroys_the_result():
    # Sprint 13 returned an INTERNAL_ERROR for this; the events are now still computed.
    r = compute_waqt(datetime(1500, 1, 1, 12, tzinfo=timezone.utc), Location(lat=9.0192, lon=38.7525),
                     UmmAlQuraProvider(), AstronomyProfile(), tz_provider=ManualTimezoneProvider("UTC"))
    assert r.status in ("OK", "UNDEFINED")
    if r.status == "OK":
        assert r.hijri_date is None and r.calendar_error and r.events

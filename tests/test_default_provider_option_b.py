"""Option B (API 1.7.0): the default Hijri calendar provider is umm-al-qura.

Pins, for EVERY provider-aware endpoint: omitted -> umm-al-qura, explicit umm-al-qura, explicit arithmetic-tabular,
invalid identifier -> documented error, the response names the provider actually used, determinism, and that the
provider choice never moves canonical Waqt time. Also: historical vectors stay reproducible under their declared
provider (verification/vector_migrations.py) and the 1.7.0 vectors describe the new default.
"""
from __future__ import annotations
import copy, json, re, sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "verification"))
from expected_versions import api_version_matches, documented_api_version  # noqa: E402
from vector_migrations import load_migration, effective_params  # noqa: E402
from waqt.api import app  # noqa: E402
from waqt.api.providers import DEFAULT_CALENDAR_PROVIDER  # noqa: E402

c = TestClient(app, raise_server_exceptions=False)
UQ, AT = "umm-al-qura", "arithmetic-tabular"
A = {"lat": 9.0192, "lon": 38.7525}
T = "2026-09-19T15:42:00Z"
LOC = {"lat": 9.0192, "lon": 38.7525}
FY = {"hijri_year": 1448, "start_rule": {"type": "month_day", "month": 1, "day": 1}, "end_rule": {"type": "month_end", "month": 12}}
AY = {"hijri_year": 1448, "opening_rule": {"type": "month_day", "month": 1, "day": 1}, "closing_rule": {"type": "month_end", "month": 12}}

# (id, method, path, params-or-body). Every route whose OpenAPI declares a calendar_provider (GET query) or whose body honours it.
PROVIDER_AWARE = [
    ("waqt", "GET", "/v1/waqt", {**A, "instant": T}),
    ("hijri", "GET", "/v1/hijri", {"date": "2026-09-19"}),
    ("conversions-to-hijri", "GET", "/v1/conversions", {"direction": "to-hijri", "date": "2026-09-19"}),
    ("conversions-to-gregorian", "GET", "/v1/conversions", {"direction": "to-gregorian", "year": 1448, "month": 4, "day": 7}),
    ("calendar-convert-instant", "GET", "/v1/calendar/convert", {"direction": "instant-to-calendars", "instant": T, **A}),
    ("calendar-convert-date", "GET", "/v1/calendar/convert", {"direction": "gregorian-date-to-waqt", "date": "2026-09-20", **A}),
    ("schedule-snapshot", "GET", "/v1/schedule/snapshot", {**A, "instant": T}),
    ("schedule-span", "GET", "/v1/schedule/span", {**A, "start": "2026-09-19T00:00:00Z", "end": "2026-09-21T00:00:00Z"}),
    ("schedule-resolve", "POST", "/v1/schedule/resolve", {"location": LOC, "anchor": T, "operation": {"op": "day_bounds"}}),
    ("institutional-week", "GET", "/v1/institutional/week", {**A, "instant": T}),
    ("institutional-fiscal-year", "GET", "/v1/institutional/fiscal-year", {"hijri_year": 1448}),
    ("institutional-fiscal-year-resolve", "POST", "/v1/institutional/fiscal-year/resolve", FY),
    ("institutional-academic-year", "GET", "/v1/institutional/academic-year", {"hijri_year": 1448}),
    ("institutional-academic-year-resolve", "POST", "/v1/institutional/academic-year/resolve", AY),
    ("institutional-profile", "GET", "/v1/institutional/profile", {}),
]
IDS = [p[0] for p in PROVIDER_AWARE]
NO_PROVIDER = [("day", "/v1/day", {**A, "instant": T}), ("events", "/v1/events", {**A, "instant": T}),
               ("location", "/v1/location", {**A, "instant": T}),
               ("boundary-crossing", "/v1/calendar/boundary-crossing", {"start": "2026-09-19T00:00:00Z", "end": "2026-09-20T00:00:00Z", **A})]


def call(method, path, payload, provider=None):
    """provider=None -> the key is OMITTED (not sent as null/empty)."""
    payload = copy.deepcopy(payload)
    if method == "GET":
        if provider is not None:
            payload["calendar_provider"] = provider
        return c.get(path, params=payload)
    if provider is not None:
        payload["calendar_provider"] = provider
    return c.post(path, json=payload)


def names(o, acc=None):
    """Every provider NAME a response states (calendar_provider.name / hijri.provider[.name])."""
    acc = set() if acc is None else acc
    if isinstance(o, dict):
        for k, v in o.items():
            if k in ("calendar_provider", "provider"):
                if isinstance(v, dict) and "name" in v:
                    acc.add(v["name"])
                elif isinstance(v, str):
                    acc.add(v)
            names(v, acc)
    elif isinstance(o, list):
        for x in o:
            names(x, acc)
    return acc


def strip_hijri(o):
    """Remove Hijri labels and provider identity; what remains is the canonical temporal content."""
    drop = {"hijri", "hijri_label", "calendar_provider", "provider"}
    if isinstance(o, dict):
        return {k: strip_hijri(v) for k, v in o.items() if k not in drop and k != "generated_at"}
    if isinstance(o, list):
        return [strip_hijri(x) for x in o]
    return o


def vol(o):
    o = copy.deepcopy(o)
    o["meta"].pop("generated_at", None)
    return o


def test_default_constant_is_umm_al_qura():
    assert DEFAULT_CALENDAR_PROVIDER == UQ


def test_every_provider_aware_route_is_in_the_matrix():
    """A new endpoint that gains `calendar_provider` must be added here -- the matrix may not silently go stale."""
    spec = c.get("/openapi.json").json()["paths"]
    declared = {p for p, ops in spec.items() for op in ops.values() if any(x["name"] == "calendar_provider" for x in op.get("parameters", []))}
    declared |= {"/v1/schedule/resolve", "/v1/institutional/fiscal-year/resolve", "/v1/institutional/academic-year/resolve"}  # body-driven
    assert declared == {p[2] for p in PROVIDER_AWARE}
    for p in spec:  # ...and the ones deliberately without a provider really have none
        if p in {x[1] for x in NO_PROVIDER}:
            assert all(x["name"] != "calendar_provider" for op in spec[p].values() for x in op.get("parameters", []))
    for _id, m, path, _ in PROVIDER_AWARE:
        if m == "GET" and path != "/v1/institutional/week":
            if path in spec:
                for op in spec[path].values():
                    for prm in op.get("parameters", []):
                        if prm["name"] == "calendar_provider":
                            assert prm["schema"]["default"] == UQ, path


@pytest.mark.parametrize("eid,method,path,payload", PROVIDER_AWARE, ids=IDS)
def test_omitted_provider_selects_umm_al_qura_and_response_names_it(eid, method, path, payload):
    r = call(method, path, payload)
    assert r.status_code == 200, r.text
    assert names(r.json()["data"]) == {UQ}, f"{path} did not identify the provider it used"


@pytest.mark.parametrize("eid,method,path,payload", PROVIDER_AWARE, ids=IDS)
def test_explicit_umm_al_qura_equals_omitted(eid, method, path, payload):
    a, b = call(method, path, payload), call(method, path, payload, UQ)
    assert b.status_code == 200 and names(b.json()["data"]) == {UQ}
    assert vol(a.json()) == vol(b.json())


@pytest.mark.parametrize("eid,method,path,payload", PROVIDER_AWARE, ids=IDS)
def test_explicit_arithmetic_tabular_is_still_selectable_and_named(eid, method, path, payload):
    r = call(method, path, payload, AT)
    assert r.status_code == 200, r.text
    assert names(r.json()["data"]) == {AT}
    assert r.json()["data"] != call(method, path, payload, UQ).json()["data"]   # the two providers are observably different here


@pytest.mark.parametrize("eid,method,path,payload", PROVIDER_AWARE, ids=IDS)
def test_invalid_provider_identifier_is_the_documented_validation_error(eid, method, path, payload):
    r = call(method, path, payload, "gregorian-ish")
    b = r.json()
    assert r.status_code == 400 and b["error"]["code"] == "UNKNOWN_CALENDAR_PROVIDER"
    assert b["error"]["details"]["received"] == "gregorian-ish" and UQ in b["error"]["details"]["available"] and AT in b["error"]["details"]["available"]


@pytest.mark.parametrize("eid,method,path,payload", PROVIDER_AWARE, ids=IDS)
def test_deterministic_for_a_fixed_request(eid, method, path, payload):
    assert vol(call(method, path, payload).json()) == vol(call(method, path, payload).json())


def test_providers_disagree_on_the_label_for_the_reference_date():
    """Documented example (docs/CALENDARS.md): 2026-09-19 is 8 Rabi al-Thani 1448 under umm-al-qura, 6 under arithmetic-tabular."""
    got = lambda p: c.get("/v1/hijri", params={"date": "2026-09-19", **({"calendar_provider": p} if p else {})}).json()["data"]["hijri"]
    assert (got(None)["date"], got(UQ)["date"], got(AT)["date"]) == ("1448-04-08", "1448-04-08", "1448-04-06")


# ---- canonical Waqt time is independent of the Hijri provider -------------------------------------------------
GRID = [(9.0192, 38.7525, "2026-09-19T15:42:00Z"), (9.0192, 38.7525, "2026-09-19T15:10:00Z"),   # either side of Maghrib
        (21.4225, 39.8262, "2026-09-19T10:00:00Z"), (51.5074, -0.1278, "2026-03-29T00:30:00Z"),
        (-6.2088, 106.8456, "2026-12-31T22:00:00Z"), (1.5, -157.4, "2026-09-19T05:00:00Z"), (64.1466, -21.9426, "2026-06-21T12:00:00Z")]


@pytest.mark.parametrize("lat,lon,t", GRID)
@pytest.mark.parametrize("path", ["/v1/waqt", "/v1/day", "/v1/events", "/v1/schedule/snapshot"])
def test_default_change_cannot_silently_change_canonical_waqt_time(path, lat, lon, t):
    q = {"lat": lat, "lon": lon, "instant": t}
    base = c.get(path, params=q)
    uq, at = (c.get(path, params={**q, "calendar_provider": p}) for p in (UQ, AT)) if path in ("/v1/waqt", "/v1/schedule/snapshot") else (base, base)
    assert base.status_code == uq.status_code == at.status_code
    assert strip_hijri(base.json()["data"]) == strip_hijri(uq.json()["data"]) == strip_hijri(at.json()["data"])


@pytest.mark.parametrize("path", ["/v1/day", "/v1/events", "/v1/location", "/v1/calendar/boundary-crossing"])
def test_endpoints_without_a_provider_stay_provider_free_and_unchanged(path):
    q = next(x[2] for x in NO_PROVIDER if x[1] == path)
    r = c.get(path, params=q)
    assert r.status_code == 200 and names(r.json()["data"]) == set()
    assert vol(r.json()) == vol(c.get(path, params={**q, "calendar_provider": AT}).json())   # extra param ignored: no behaviour depends on it


def test_schedule_and_institutional_labels_follow_the_selected_provider_consistently():
    for eid, m, path, payload in PROVIDER_AWARE:
        if not (eid.startswith("schedule") or eid.startswith("institutional")):
            continue
        d_def, d_uq, d_at = (call(m, path, payload, p).json()["data"] for p in (None, UQ, AT))
        assert names(d_def) == names(d_uq) == {UQ} and names(d_at) == {AT}, eid
    wk = lambda p: c.get("/v1/institutional/week", params={**A, "instant": T, **({"calendar_provider": p} if p else {})}).json()["data"]
    assert [d["hijri_label"] for d in wk(None)["days"]] == [d["hijri_label"] for d in wk(UQ)["days"]]
    assert [d["hijri_label"] for d in wk(None)["days"]] != [d["hijri_label"] for d in wk(AT)["days"]]
    assert strip_hijri(wk(None)) == strip_hijri(wk(AT))   # the week's canonical content (bounds, Jumu'ah index, days) does not depend on the provider
    prof = lambda p: c.get("/v1/institutional/profile", params={"calendar_provider": p} if p else {}).json()["data"]["profile"]
    assert prof(None)["name"] == "demo-umm-al-qura" and prof(AT)["name"] == "demo-arithmetic-tabular"


# ---- versions -------------------------------------------------------------------------------------------------
def test_version_checker_accepts_only_the_documented_version_and_rejects_others():
    doc = documented_api_version()
    assert api_version_matches(doc) and not api_version_matches("1.6.0") and not api_version_matches("9.9.9") and not api_version_matches(None)
    assert api_version_matches("1.6.0", "1.6.0")   # historical checks must name the historical version explicitly


def test_reported_api_version_equals_documented_version_on_every_surface():
    doc = documented_api_version()
    assert c.get("/v1/health").json()["api_version"] == doc
    assert c.get("/v1/version").json()["data"]["api_version"] == doc
    assert c.get("/v1/waqt", params={**A, "instant": T}).json()["meta"]["api_version"] == doc
    assert c.get("/v1/waqt", params={"lat": 999, "lon": 0}).json()["meta"]["api_version"] == doc  # error envelopes too


# ---- historical fixtures and the migration --------------------------------------------------------------------
HIST = json.loads((ROOT / "sdks/vectors/sdk_conformance_vectors.json").read_text(encoding="utf-8"))["vectors"]
MIG = load_migration()


def contains(old, new):
    if isinstance(old, dict):
        return isinstance(new, dict) and all(k in new and contains(v, new[k]) for k, v in old.items())
    if isinstance(old, list):
        return isinstance(new, list) and len(old) == len(new) and all(contains(a, b) for a, b in zip(old, new))
    return old == new


def replay(v, params):
    rq = v["request"]
    return c.get(rq["path"], params=params)


def strip_meta(body):
    body = copy.deepcopy(body)
    body["meta"].pop("generated_at", None); body["meta"].pop("api_version", None)
    return body


@pytest.mark.parametrize("entry", MIG["entries"], ids=[e["id"] for e in MIG["entries"]])
def test_historical_vector_is_reproducible_under_its_declared_provider(entry):
    v = next(x for x in HIST if x["id"] == entry["id"])
    assert "calendar_provider" not in (v["request"].get("params") or {}) and entry["provider_before"] == MIG["replay_provider"] == AT
    assert v["response"]["data"] is not None and names(v["response"]["data"]) <= {AT}, "historical recording must itself be arithmetic-tabular"
    r = replay(v, effective_params(v, MIG))
    assert r.status_code == v["status_code"] and contains(strip_meta(v["response"]), strip_meta(r.json()))


@pytest.mark.parametrize("entry", MIG["entries"], ids=[e["id"] for e in MIG["entries"]])
def test_without_the_migration_the_same_recording_really_differs(entry):
    """No over-broad migration: every listed vector must actually change under the new default, or it does not belong here."""
    v = next(x for x in HIST if x["id"] == entry["id"])
    r = replay(v, v["request"].get("params"))
    assert not contains(strip_meta(v["response"]), strip_meta(r.json()))


def test_every_other_historical_vector_still_matches_the_live_app_without_any_migration():
    listed = set(MIG["_by_id"])
    for v in HIST:
        if v["id"] in listed:
            continue
        r = replay(v, v["request"].get("params"))
        assert r.status_code == v["status_code"] and contains(strip_meta(v["response"]), strip_meta(r.json())), v["id"]


def test_migration_refuses_to_touch_a_vector_that_already_names_a_provider():
    v = next(x for x in HIST if x["id"] == "hijri-umm-al-qura")
    bad = {**MIG, "_by_id": {**MIG["_by_id"], "hijri-umm-al-qura": {}}}
    with pytest.raises(ValueError):
        effective_params(v, bad)


def test_historical_file_is_not_rewritten_it_is_still_the_pre_1_7_recording():
    hijri = next(x for x in HIST if x["id"] == "hijri-ordinary")["response"]["data"]["hijri"]
    assert hijri["date"] == "1448-04-06" and hijri["provider"]["name"] == AT


def test_new_vectors_describe_the_new_default_and_match_the_live_app():
    nv = json.loads((ROOT / MIG["new_vector_file"]).read_text(encoding="utf-8"))
    assert nv["governing_api_version"] == "1.7.0" and nv["default_calendar_provider"] == UQ and len(nv["vectors"]) == len(MIG["entries"])
    for v in nv["vectors"]:
        assert "calendar_provider" not in (v["request"].get("params") or {}), v["id"]
        assert names(v["response"]["data"]) == {UQ} and v["expected_provider"] == UQ
        r = c.get(v["request"]["path"], params=v["request"].get("params"))
        assert r.status_code == v["status_code"] and strip_meta(r.json()) == strip_meta(v["response"]), v["id"]


@pytest.mark.parametrize("entry", MIG["entries"], ids=[e["id"] for e in MIG["entries"]])
def test_old_and_new_recordings_differ_only_in_provider_dependent_fields(entry):
    old = next(x for x in HIST if x["id"] == entry["id"])
    new = next(x for x in json.loads((ROOT / MIG["new_vector_file"]).read_text(encoding="utf-8"))["vectors"] if x["id"] == entry["new_vector_id"])
    if entry["id"] == "conversions-to-gregorian":
        assert old["response"]["data"]["output"]["gregorian_date"] == "2026-09-20" and new["response"]["data"]["output"]["gregorian_date"] == "2026-09-18"
        return
    if entry["id"] == "institutional-profile":
        assert old["response"]["data"]["profile"]["name"] == "demo-arithmetic-tabular" and new["response"]["data"]["profile"]["name"] == "demo-umm-al-qura"
        return
    assert strip_hijri(old["response"]["data"]) == strip_hijri(new["response"]["data"]), "canonical (non-Hijri) content changed"


# ---- Waqt Web --------------------------------------------------------------------------------------------------
WEB = ROOT / "apps" / "web"


def test_web_requests_umm_al_qura_explicitly_and_has_no_hardcoded_hijri_date_or_day_offset():
    cfg = (WEB / "assets/js/config.js").read_text(encoding="utf-8")
    assert re.search(r'defaultProvider:\s*"umm-al-qura"', cfg)
    assert "The API default is arithmetic-tabular" not in cfg, "stale comment: the API default is umm-al-qura since 1.7.0"
    js = "".join(p.read_text(encoding="utf-8") for p in (WEB / "assets/js").rglob("*.js") if p.name != "demo-data.js")
    assert not re.search(r"\b14[0-9]{2}-\d{2}-\d{2}\b", js), "a literal Hijri date in web code"
    assert not re.search(r"hijri[^\n;]{0,40}[+-]\s*[12]\b", js, re.I), "a manual Hijri day offset"


def test_demo_fallback_sample_names_the_provider_it_was_recorded_with():
    demo = (WEB / "assets/js/demo-data.js").read_text(encoding="utf-8")
    assert "calendar_provider=umm-al-qura" in demo and '"provider": "umm-al-qura"' in demo and "NOT live data" in demo

#!/usr/bin/env python3
"""Sprint 13 Goal A/B: exercise the REAL uvicorn+FastAPI server over real HTTP.

Checks: /v1/version, /v1/health, CORS (off by default, on with WAQT_CORS_ORIGINS,
preflight), validation/error envelopes, and live-API <-> committed-vector
conformance for waqt_vectors.json and sdk_conformance_vectors.json.
No stubs, no TestClient: sockets only.   Run: python verification/live_stack_check.py
"""
from __future__ import annotations
import json, os, socket, subprocess, sys, time, urllib.request, urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = []

def rec(name, ok, detail=""):
    RESULTS.append({"check": name, "ok": bool(ok), "detail": detail})
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))

def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p

def start(env_extra):
    port = free_port()
    env = {**os.environ, **env_extra}
    env.pop("WAQT_CORS_ORIGINS", None) if "WAQT_CORS_ORIGINS" not in env_extra else None
    p = subprocess.Popen([sys.executable, "-m", "uvicorn", "waqt.api:app", "--port", str(port), "--log-level", "error"],
                         cwd=ROOT, env=env)
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/health", timeout=1); return p, port
        except Exception: time.sleep(0.1)
    p.kill(); raise RuntimeError("server did not start")

def get(port, path, headers=None, method="GET"):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r: return r.status, dict(r.headers), json.loads(r.read() or b"null") if method != "OPTIONS" else None
    except urllib.error.HTTPError as e:
        raw = e.read(); return e.code, dict(e.headers), (json.loads(raw) if raw else None)

def strip_volatile(o):
    if isinstance(o, dict): return {k: strip_volatile(v) for k, v in o.items() if k not in ("generated_at", "api_version", "label_date")}
    if isinstance(o, list): return [strip_volatile(x) for x in o]
    return o

def sprint14_checks(rec_fn):
    """Sprint 14: live Hijri provider, provenance, fallback, health/version, rate limiting, CORS -- real uvicorn
    + real HTTP to a local fake AlAdhan (the real service is not reachable from CI). The API's outbound
    calls use the real urllib transport."""
    try:
        from verification.fake_aladhan import FakeAlAdhan
    except ImportError:
        sys.path.insert(0, str(ROOT / "verification"))
        from fake_aladhan import FakeAlAdhan  # pyrefly: ignore [missing-import]
    fake = FakeAlAdhan().start()
    p, port = start({"WAQT_CORS_ORIGINS": "http://localhost:8080", "WAQT_ALADHAN_BASE_URL": fake.base_url,
                     "WAQT_RATE_LIMIT": "40/minute"})
    q = "/v1/waqt?lat=9.0192&lon=38.7525&instant=2026-09-30T09:00:00Z&timezone_override=Africa/Addis_Ababa"
    O = {"Origin": "http://localhost:8080"}
    try:
        st, h, b = get(port, q + "&calendar_provider=aladhan", O); hj = b["data"]["hijri"]
        rec_fn("S14 aladhan remote: source=remote, provider identity + provenance", st == 200 and hj["source"] == "remote" and hj["provider"]["name"] == "aladhan"
               and hj["provenance"]["cache"] == "miss" and hj["provenance"]["cross_check"] is not None, f"{hj['source']} {hj['provider']['version']}")
        n = len(fake.calls)
        st, h, b = get(port, q + "&calendar_provider=aladhan");
        rec_fn("S14 second request served from the 12h cache (no extra upstream call)", b["data"]["hijri"]["provenance"]["cache"] == "hit" and len(fake.calls) == n, f"upstream calls={len(fake.calls)}")
        base = get(port, q + "&calendar_provider=arithmetic-tabular")[2]["data"]
        live = b["data"]
        strip = lambda d: {k: v for k, v in d.items() if k not in ("hijri", "calendar_error", "event_representations")}
        rec_fn("S14 astronomy identical: aladhan vs arithmetic-tabular (real HTTP)", strip(base) == strip(live))
        fake.mode = "500"; q2 = q.replace("2026-09-30", "2026-10-02")
        st, h, b = get(port, q2 + "&calendar_provider=aladhan", O); hj = b["data"]["hijri"]
        rec_fn("S14 upstream 500 -> 200, source=local-fallback, provider=umm-al-qura, reason visible, CORS ok",
               st == 200 and hj["source"] == "local-fallback" and hj["provider"]["name"] == "umm-al-qura"
               and hj["provenance"]["fallback_reason"] == "upstream-server-error" and {k.lower(): v for k, v in h.items()}.get("access-control-allow-origin") == "http://localhost:8080")
        st, h, b = get(port, "/v1/health")
        i = b["integrations"]["hijri_aladhan"]
        rec_fn("S14 /v1/health: status ok while degraded; circuit open; no network involved", st == 200 and b["status"] == "ok" and b["api_version"] == "1.6.0" and i["circuit"] == "open" and i["last_failure_reason"] == "upstream-server-error")
        st, h, b = get(port, "/v1/version"); d = b["data"]
        rec_fn("S14 /v1/version: API 1.6.0, integrations listed, affects_astronomy=false", d["api_version"] == "1.6.0" and "aladhan" in d["integrations"]["calendar_providers"] and d["integrations"]["affects_astronomy"] is False)
        st, h, b = get(port, "/v1/waqt?lat=90&lon=0&instant=2026-06-21T12:00:00Z&calendar_provider=aladhan")
        rec_fn("S14 polar: UNDEFINED, hijri null, no events, still HTTP 200", st == 200 and b["data"]["status"] == "UNDEFINED" and b["data"]["hijri"] is None and b["data"]["events"] == [])
        st, h, b = get(port, "/v1/waqt?lat=64.15&lon=-21.94&instant=2026-06-21T12:00:00Z&timezone_override=Atlantic/Reykjavik&calendar_provider=arithmetic-tabular")
        rec_fn("S14 high latitude: OK with Fajr/Isha instants null", st == 200 and b["data"]["status"] == "OK" and sorted(e["name"] for e in b["data"]["events"] if e["instant"] is None) == ["fajr", "isha"])
        st, h, b = get(port, "/v1/waqt?lat=91&lon=0&calendar_provider=aladhan"); rec_fn("S14 invalid coordinates -> 422 envelope", st == 422 and b["error"]["code"] == "VALIDATION_ERROR")
        st, h, b = get(port, "/v1/hijri?date=2026-02-30&calendar_provider=aladhan"); rec_fn("S14 invalid date -> 400 INVALID_DATE", st == 400 and b["error"]["code"] == "INVALID_DATE")
        # rate limit: 40/min. Burn the budget, then expect 429 + Retry-After + CORS header; /v1/health stays exempt.
        codes = []
        for _ in range(60):
            st, h, b = get(port, "/v1/version", O); codes.append(st)
            if st == 429: break
        hl = {k.lower(): v for k, v in h.items()}
        rec_fn("S14 rate limit: 429 RATE_LIMITED with Retry-After and CORS headers", codes[-1] == 429 and b["error"]["code"] == "RATE_LIMITED"
               and int(hl["retry-after"]) >= 1 and hl.get("access-control-allow-origin") == "http://localhost:8080", f"429 after {len(codes) - 1} requests")
        st, h, b = get(port, "/v1/health"); rec_fn("S14 /v1/health exempt from rate limiting", st == 200)
    finally:
        p.terminate(); p.wait(); fake.stop()


def main():
    try:
        from core.waqt_core.versioning import version_report, computation_identity, VECTOR_SET_VERSION
    except ImportError:
        sys.path.insert(0, str(ROOT / "core"))
        from waqt_core.versioning import version_report, computation_identity, VECTOR_SET_VERSION  # pyrefly: ignore [missing-import]
    # ---------- server 1: default (no CORS) ----------
    p, port = start({})
    try:
        st, h, b = get(port, "/v1/version")
        rec("GET /v1/version 200 + envelope", st == 200 and b["error"] is None and set(b) == {"meta", "data", "error"})
        d = b["data"]
        rec("/v1/version computation == waqt_core.versioning", d["computation"] == computation_identity(), json.dumps(d["computation"]))
        rec("/v1/version axes independent (core/api/vectors/engine)",
            (d["waqt_core_version"], d["api_version"], d["computation"]["revision"], d["conformance_vectors"]["vector_set_version"]) ==
            (version_report(api_version=d["api_version"])["waqt_core_version"], d["api_version"], "2", VECTOR_SET_VERSION),
            f"core={d['waqt_core_version']} api={d['api_version']} rev={d['computation']['revision']} vec={d['conformance_vectors']['vector_set_version']}")
        rec("/v1/version waqt_local_version null from server", d["waqt_local_version"] is None)
        st, h, b = get(port, "/v1/health"); rec("GET /v1/health", st == 200 and b["computation"]["revision"] == "2")
        # CORS default: absent
        st, h, b = get(port, "/v1/waqt?lat=9&lon=38", {"Origin": "http://localhost:8080"})
        rec("CORS default: no Access-Control-* header", st == 200 and not any(k.lower().startswith("access-control") for k in h))
        # validation / errors through real pydantic/fastapi
        for path, want in [("/v1/waqt?lat=abc&lon=38", "VALIDATION_ERROR"), ("/v1/waqt?lat=95&lon=38", "VALIDATION_ERROR"),
                           ("/v1/waqt?lat=9&lon=38&instant=nonsense", "INVALID_INSTANT"), ("/v1/waqt", "VALIDATION_ERROR")]:
            st, h, b = get(port, path)
            rec(f"error path {path}", st >= 400 and b and b["error"] and b["error"]["code"] == want and b["data"] is None,
                f"HTTP {st} code={(b or {}).get('error', {}).get('code') if b else None}")
        st, h, b = get(port, "/v1/nope"); rec("unknown route -> 404", st == 404, f"HTTP {st}")
        # live API <-> waqt_vectors.json
        vec = json.load(open(ROOT / "tests/vectors/waqt_vectors.json"))
        rec("waqt_vectors stamp == running engine", vec["generated_at_computation"] == computation_identity() and vec["vector_set_version"] == VECTOR_SET_VERSION)
        # live API <-> sdk conformance vectors (whole envelope minus generated_at)
        sv = json.load(open(ROOT / "sdks/vectors/sdk_conformance_vectors.json"))
        bad = []
        from urllib.parse import urlencode
        for v in sv["vectors"]:
            rq = v["request"]
            q = ("?" + urlencode(rq["params"], doseq=True)) if rq.get("params") else ""
            st, h, b = get(port, rq["path"] + q)
            if st != v["status_code"] or strip_volatile(b) != strip_volatile(v["response"]): bad.append(v["id"])
        rec(f"live API == sdk_conformance_vectors ({len(sv['vectors'])} vectors, real HTTP)", not bad, "mismatch: " + ",".join(bad) if bad else "all identical")
    finally:
        p.terminate(); p.wait()
    # ---------- server 2: CORS opt-in ----------
    p, port = start({"WAQT_CORS_ORIGINS": "http://localhost:8080"})
    try:
        st, h, b = get(port, "/v1/waqt?lat=9&lon=38", {"Origin": "http://localhost:8080"})
        hl = {k.lower(): v for k, v in h.items()}
        rec("CORS opt-in: allowed origin echoed", hl.get("access-control-allow-origin") == "http://localhost:8080", hl.get("access-control-allow-origin", ""))
        st, h, b = get(port, "/v1/waqt?lat=9&lon=38", {"Origin": "http://evil.example"})
        hl = {k.lower(): v for k, v in h.items()}
        rec("CORS opt-in: disallowed origin not echoed", "access-control-allow-origin" not in hl)
        req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/waqt", method="OPTIONS",
              headers={"Origin": "http://localhost:8080", "Access-Control-Request-Method": "GET"})
        with urllib.request.urlopen(req) as r:
            hl = {k.lower(): v for k, v in r.headers.items()}; rec("CORS preflight OPTIONS 200", r.status == 200 and hl.get("access-control-allow-origin") == "http://localhost:8080")
        st, h, b = get(port, "/v1/waqt?lat=abc&lon=1", {"Origin": "http://localhost:8080"})
        hl = {k.lower(): v for k, v in h.items()}
        rec("CORS headers present on error responses too", st >= 400 and hl.get("access-control-allow-origin") == "http://localhost:8080")
    finally:
        p.terminate(); p.wait()
    sprint14_checks(rec_fn=rec)
    out = ROOT / "verification/results/live_stack_check.json"; out.parent.mkdir(parents=True, exist_ok=True)
    json.dump({"results": RESULTS, "all_ok": all(r["ok"] for r in RESULTS)}, open(out, "w"), indent=1)
    print(f"\n{sum(r['ok'] for r in RESULTS)}/{len(RESULTS)} passed")
    return 0 if all(r["ok"] for r in RESULTS) else 1

if __name__ == "__main__":
    sys.exit(main())

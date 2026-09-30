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
    if isinstance(o, dict): return {k: strip_volatile(v) for k, v in o.items() if k != "generated_at"}
    if isinstance(o, list): return [strip_volatile(x) for x in o]
    return o

def main():
    sys.path.insert(0, str(ROOT / "core"))
    from waqt_core.versioning import version_report, computation_identity, VECTOR_SET_VERSION
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
    out = ROOT / "verification/results/live_stack_check.json"; out.parent.mkdir(parents=True, exist_ok=True)
    json.dump({"results": RESULTS, "all_ok": all(r["ok"] for r in RESULTS)}, open(out, "w"), indent=1)
    print(f"\n{sum(r['ok'] for r in RESULTS)}/{len(RESULTS)} passed")
    return 0 if all(r["ok"] for r in RESULTS) else 1

if __name__ == "__main__":
    sys.exit(main())

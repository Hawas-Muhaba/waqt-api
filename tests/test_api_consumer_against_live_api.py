"""Sprint 13: apps/api-consumer against the REAL waqt.api app served by uvicorn on a real socket
(the fake-server test in apps/api-consumer/tests only proves the HTTP/JSON handling)."""
from __future__ import annotations
import json, os, shutil, socket, subprocess, sys, time, urllib.request
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
pytest.importorskip("fastapi"); pytest.importorskip("uvicorn")
api_consumer = pytest.importorskip("api_consumer.waqt_api")

@pytest.fixture(scope="module")
def base():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    p = subprocess.Popen([sys.executable, "-m", "uvicorn", "waqt.api:app", "--port", str(port), "--log-level", "error"], cwd=ROOT)
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try: urllib.request.urlopen(url + "/v1/health", timeout=1); break
        except Exception: time.sleep(0.1)
    else: p.kill(); pytest.fail("server did not start")
    yield url
    p.terminate(); p.wait()

def test_get_waqt_and_version_from_real_api(base):
    from waqt_core.versioning import computation_identity, VECTOR_SET_VERSION
    c = api_consumer.WaqtApiClient(base)
    w = c.get_waqt(9.0192, 38.7525, instant="2026-09-28T12:00:00Z")
    assert w["status"] == "OK" and w["computation"]["revision"] == computation_identity()["revision"]
    v = c.get_version()
    assert v["api_version"] == "1.6.0" and v["conformance_vectors"]["vector_set_version"] == VECTOR_SET_VERSION

def test_error_and_polar_from_real_api(base):
    c = api_consumer.WaqtApiClient(base)
    with pytest.raises(api_consumer.WaqtApiError) as ei: c.get_waqt(999, 38.7525)
    assert ei.value.code == "VALIDATION_ERROR"
    assert c.get_waqt(78.2232, 15.6469, instant="2026-06-21T12:00:00Z")["status"] == "UNDEFINED"

def test_installed_console_script_against_real_api(base):
    exe = shutil.which("waqt-api-consumer")
    if not exe: pytest.skip("waqt-api-consumer not installed")
    r = subprocess.run([exe, "--base-url", base, "--lat", "9.0192", "--lon", "38.7525", "--instant", "2026-09-28T12:00:00Z"], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    assert "Waqt clock" in r.stdout and "waqt-noaa-low-precision r2" in r.stdout

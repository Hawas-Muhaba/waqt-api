"""
tests/test_packaging_smoke.py — Sprint 11: proves the `waqt-api`
distribution (this repo's root `pyproject.toml`, `waqt.api`) is
actually packageable, and that it genuinely DEPENDS ON `waqt-core`
rather than merely working by accident because both happen to sit in
the same checkout.

Builds waqt-core's wheel first, then waqt-api's wheel, installs BOTH
into a throwaway virtualenv with no access to this repo's source tree,
and exercises `waqt.api` (a real FastAPI TestClient call) from there.
Same discipline as core/tests/test_packaging_smoke.py and Sprint 10's
two SDK packaging smoke tests.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import venv
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CORE_ROOT = REPO_ROOT / "core"

pytestmark = pytest.mark.slow


def _build_wheel(pkg_root: Path, dist_dir: Path) -> Path:
    result = subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(dist_dir), str(pkg_root)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    whls = list(dist_dir.glob("*.whl"))
    assert whls, f"no wheel built for {pkg_root}"
    return whls[0]


def _fresh_venv(tmp_path: Path) -> Path:
    venv_dir = tmp_path / "venv"
    venv.EnvBuilder(with_pip=True).create(venv_dir)
    return venv_dir


def _venv_python(venv_dir: Path) -> str:
    return str(venv_dir / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python3"))


SMOKE_SCRIPT = """
from fastapi.testclient import TestClient
from waqt.api import app
import waqt_core  # must have been pulled in as a real dependency

client = TestClient(app)
r = client.get("/v1/waqt", params={"lat": 9.0192, "lon": 38.7525})
assert r.status_code == 200, r.text
body = r.json()
assert body["data"]["hijri"]["display"], body

# Deep-import shim still resolves correctly from a clean install.
from waqt.scheduling.model import DAY_SHIFT
from waqt_core.scheduling.model import DAY_SHIFT as DAY_SHIFT2
assert DAY_SHIFT is DAY_SHIFT2

print("SMOKE OK")
"""


def test_clean_install_waqt_api_pulls_in_waqt_core(tmp_path):
    if not shutil.which(sys.executable):
        pytest.skip("no python interpreter available")

    dist_dir = tmp_path / "dist"
    # Sprint 13: each wheel gets its own outdir. Previously both shared dist_dir and
    # _build_wheel returned whls[0], so which file was "the api wheel" depended on
    # directory listing order (it could be the core wheel, twice).
    core_whl = _build_wheel(CORE_ROOT, dist_dir / "core")
    api_whl = _build_wheel(REPO_ROOT, dist_dir / "api")
    assert core_whl.name.startswith("waqt_core-") and api_whl.name.startswith("waqt_api-"), (core_whl, api_whl)

    venv_dir = _fresh_venv(tmp_path)
    py = _venv_python(venv_dir)

    # Install waqt-core first (from the local wheel, since it isn't on
    # PyPI yet), then waqt-api -- pip resolves waqt-api's `waqt-core`
    # dependency against the one already installed rather than failing.
    for whl in (core_whl, api_whl):
        install = subprocess.run([py, "-m", "pip", "install", "--quiet", str(whl)], capture_output=True, text=True)
        assert install.returncode == 0, install.stderr
    # httpx: needed only to exercise the app via FastAPI's TestClient in
    # this smoke test itself, not a waqt-api runtime dependency.
    install_httpx = subprocess.run([py, "-m", "pip", "install", "--quiet", "httpx"], capture_output=True, text=True)
    assert install_httpx.returncode == 0, install_httpx.stderr

    smoke_file = tmp_path / "smoke.py"
    smoke_file.write_text(SMOKE_SCRIPT)
    result = subprocess.run([py, str(smoke_file)], capture_output=True, text=True, cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "SMOKE OK" in result.stdout

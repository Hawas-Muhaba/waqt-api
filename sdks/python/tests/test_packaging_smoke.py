"""
tests/test_packaging_smoke.py — proves waqt-client is actually
packageable and installable on its own, isolated from this checkout:
builds both the wheel and the sdist with `python -m build`, installs
each into a throwaway virtualenv (no access to this repo's source tree
or its editable install), and imports/exercises the package there.

Slow (spawns a venv + build + pip install per test) and network-free
(installs a local artifact, not from PyPI) -- closes the "clean-install
package tests" item in Sprint 10's Required tests list.  Actually
publishing to PyPI is a separate, credentialed, human step (see
docs/RELEASING.md); this test proves the artifact PyPI would receive
is correct without requiring network egress to pypi.org's upload API.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import venv
from pathlib import Path

import pytest

PKG_ROOT = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.slow


def _build_artifacts(tmp_path: Path) -> Path:
    dist_dir = tmp_path / "dist"
    subprocess.run(
        [sys.executable, "-m", "build", "--outdir", str(dist_dir), str(PKG_ROOT)],
        check=True, capture_output=True, text=True,
    )
    artifacts = list(dist_dir.glob("*"))
    assert any(a.suffix == ".whl" for a in artifacts), artifacts
    assert any(a.name.endswith(".tar.gz") for a in artifacts), artifacts
    return dist_dir


def _fresh_venv(tmp_path: Path) -> Path:
    venv_dir = tmp_path / "venv"
    venv.EnvBuilder(with_pip=True).create(venv_dir)
    return venv_dir


def _venv_python(venv_dir: Path) -> str:
    return str(venv_dir / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python3"))


SMOKE_SCRIPT = """
import waqt_client
from waqt_client import requests as R, WaqtClient, AsyncWaqtClient

assert waqt_client.__version__ == "__EXPECTED_VERSION__", waqt_client.__version__

req = R.ScheduleResolveRequest(lat=9.0192, lon=38.7525, operation=R.NextEventOp())
body = req.to_json()
assert body == {"location": {"lat": 9.0192, "lon": 38.7525, "elevation_m": 0.0}, "operation": {"op": "next_event"}}, body

# The package must not accidentally require the `waqt` core package or
# any test-only dependency -- only httpx.
import httpx  # noqa: F401
try:
    import waqt  # noqa: F401
    raise SystemExit("waqt-client must not depend on the waqt core package")
except ImportError:
    pass

print("SMOKE OK")
"""


@pytest.mark.parametrize("artifact_kind", ["whl", "tar.gz"])
def test_clean_install_from_built_artifact(tmp_path, artifact_kind):
    if not shutil.which(sys.executable):
        pytest.skip("no python interpreter available")

    dist_dir = _build_artifacts(tmp_path)
    matches = [a for a in dist_dir.glob("*") if a.name.endswith(artifact_kind)]
    assert matches, f"no {artifact_kind} artifact built"
    artifact = matches[0]

    venv_dir = _fresh_venv(tmp_path)
    py = _venv_python(venv_dir)

    install = subprocess.run([py, "-m", "pip", "install", "--quiet", str(artifact)], capture_output=True, text=True)
    assert install.returncode == 0, install.stderr

    smoke_file = tmp_path / "smoke.py"
    import re
    sdk_version = re.search(r'__version__\s*=\s*"([^"]+)"', (PKG_ROOT / "waqt_client" / "_version.py").read_text(encoding="utf-8")).group(1)   # never a literal: it would go stale on every bump
    smoke_file.write_text(SMOKE_SCRIPT.replace("__EXPECTED_VERSION__", sdk_version))
    result = subprocess.run([py, str(smoke_file)], capture_output=True, text=True, cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "SMOKE OK" in result.stdout

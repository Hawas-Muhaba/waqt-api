"""
core/tests/test_packaging_smoke.py — proves waqt-core is actually
packageable and installable on its own, isolated from this checkout:
builds both the wheel and the sdist with `python -m build`, installs
each into a throwaway virtualenv with no access to this repo's source
tree or its editable install, and imports/exercises the package there.

This is Sprint 11's "clean-install tests" requirement for Goal A --
same discipline Sprint 10 established for the two SDKs
(sdks/python/tests/test_packaging_smoke.py,
sdks/js/waqt-client/test/packaging_smoke.test.mjs), applied here to
the newly-extracted computation package. The smoke script additionally
asserts the built package does NOT pull in FastAPI, `waqt`, or
`waqt_local` -- the concrete "waqt-core has zero dependency on the
application layer" check.

Slow (spawns a venv + build + pip install per test) and network-free
(installs a local artifact, not from PyPI).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import venv
from pathlib import Path

import pytest

PKG_ROOT = Path(__file__).resolve().parent.parent  # core/

pytestmark = pytest.mark.slow


def _build_artifacts(tmp_path: Path) -> Path:
    dist_dir = tmp_path / "dist"
    result = subprocess.run(
        [sys.executable, "-m", "build", "--outdir", str(dist_dir), str(PKG_ROOT)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
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
import waqt_core
from waqt_core.core import AstronomyProfile, Location, compute_waqt
from waqt_core.hijri import ArithmeticTabularProvider
from datetime import datetime, timezone

assert waqt_core.__version__ == "0.1.0", waqt_core.__version__

result = compute_waqt(
    datetime(2026, 9, 19, 15, 42, tzinfo=timezone.utc),
    Location(9.0192, 38.7525, 0.0),
    ArithmeticTabularProvider(),
    AstronomyProfile(),
)
assert result.status == "OK", result.status

# Deep imports must work exactly as they do via the `waqt` shim.
from waqt_core.scheduling.model import DAY_SHIFT  # noqa: F401
from waqt_core.institutional.rules import MonthDay  # noqa: F401
from waqt_core.calendar_providers.registry import default_registry  # noqa: F401

# waqt-core must not depend on the application layer or FastAPI.
for forbidden in ("fastapi", "waqt", "waqt_local"):
    try:
        __import__(forbidden)
        raise SystemExit(f"waqt-core must not depend on {forbidden!r}")
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

    # waqt-core's only real dependencies: ephem, timezonefinder.
    install = subprocess.run([py, "-m", "pip", "install", "--quiet", str(artifact)], capture_output=True, text=True)
    assert install.returncode == 0, install.stderr

    smoke_file = tmp_path / "smoke.py"
    smoke_file.write_text(SMOKE_SCRIPT)
    # cwd is tmp_path, NOT this checkout -- proves no accidental reliance
    # on the repo layout (sys.path, relative imports of sibling packages).
    result = subprocess.run([py, str(smoke_file)], capture_output=True, text=True, cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "SMOKE OK" in result.stdout

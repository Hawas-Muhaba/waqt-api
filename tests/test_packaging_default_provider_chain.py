"""Clean-install check of the whole dependency chain waqt-core -> waqt-local -> waqt-cli and waqt-core -> waqt-api (Option B).

Builds the four wheels, installs them into a throwaway virtualenv that cannot see this checkout, then proves from the
INSTALLED packages that: the versions are the ones in the source tree, `pip check` is clean (every pin is satisfiable), the
default Hijri provider is one value in every layer and is `umm-al-qura`, the `waqt` command honours it, and an explicit
`arithmetic-tabular` still gives the previous result. Also: the wheels' metadata carries the pins the changelogs promise.
"""
from __future__ import annotations

import re
import subprocess
import sys
import venv
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.slow
PKGS = {"core": ROOT / "core", "api": ROOT, "local": ROOT / "local", "cli": ROOT / "apps" / "cli"}
VERSION_FILES = {"core": ("core/waqt_core/_version.py", "waqt_core"), "local": ("local/waqt_local/_version.py", "waqt_local"), "cli": ("apps/cli/waqt_cli/_version.py", "waqt_cli")}


def src_version(rel: str) -> str:
    return re.search(r'__version__\s*=\s*"([^"]+)"', (ROOT / rel).read_text(encoding="utf-8")).group(1)


def build(pkg: Path, out: Path) -> Path:
    r = subprocess.run([sys.executable, "-m", "build", "--wheel", "--outdir", str(out), str(pkg)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-1500:] + r.stderr[-1500:]
    (whl,) = list(out.glob("*.whl"))
    return whl


def requires(whl: Path) -> list[str]:
    with zipfile.ZipFile(whl) as z:
        meta = next(n for n in z.namelist() if n.endswith(".dist-info/METADATA"))
        return [l.split(": ", 1)[1] for l in z.read(meta).decode().splitlines() if l.startswith("Requires-Dist:")]


def test_clean_install_of_the_whole_chain(tmp_path):
    whls = {k: build(p, tmp_path / "dist" / k) for k, p in PKGS.items()}
    core_v, local_v, cli_v = (src_version(VERSION_FILES[k][0]) for k in ("core", "local", "cli"))

    # the pins every changelog promises, read from the BUILT wheels
    assert any(r.startswith("waqt-core") and f">={core_v}" in r and "<0.8" in r for r in requires(whls["api"]))
    assert any(r.startswith("waqt-core") and f">={core_v}" in r and "<0.8" in r for r in requires(whls["local"]))
    assert any(r.startswith("waqt-local") and f">={local_v}" in r and "<0.8" in r for r in requires(whls["cli"]))

    vdir = tmp_path / "venv"
    venv.EnvBuilder(with_pip=True).create(vdir)
    py = str(vdir / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python3"))
    bindir = vdir / ("Scripts" if sys.platform == "win32" else "bin")
    # one pip call: pip must resolve core for api/local and local for cli from the given wheels, not from the checkout
    r = subprocess.run([py, "-m", "pip", "install", "--quiet", *[str(whls[k]) for k in ("core", "api", "local", "cli")], "httpx"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-2000:]
    chk = subprocess.run([py, "-m", "pip", "check"], capture_output=True, text=True)
    assert chk.returncode == 0, chk.stdout + chk.stderr

    script = tmp_path / "check.py"
    script.write_text(f'''
import importlib.metadata as md, waqt_core, waqt_local, waqt_cli
from fastapi.testclient import TestClient
from waqt.api import app
import waqt.api.providers as ap, waqt_local.providers as lp
from waqt_core.calendar_providers import DEFAULT_CALENDAR_PROVIDER as D, default_calendar_provider
assert (md.version("waqt-core"), md.version("waqt-local"), md.version("waqt-cli")) == ("{core_v}", "{local_v}", "{cli_v}"), "installed versions"
assert waqt_core.__version__ == "{core_v}" and waqt_local.__version__ == "{local_v}" and waqt_cli.__version__ == "{cli_v}"
assert D == "umm-al-qura" == waqt_local.DEFAULT_CALENDAR_PROVIDER == ap.DEFAULT_CALENDAR_PROVIDER and lp.DEFAULT_CALENDAR_PROVIDER is D is ap.DEFAULT_CALENDAR_PROVIDER
assert default_calendar_provider().name == D
c = TestClient(app)
h = lambda **p: c.get("/v1/hijri", params={{"date": "2026-09-19", **p}}).json()["data"]["hijri"]
assert (h()["date"], h()["provider"]["name"]) == ("1448-04-08", "umm-al-qura") and h(calendar_provider="arithmetic-tabular")["date"] == "1448-04-06"
assert waqt_local.hijri(date="2026-09-19")["hijri"]["provider"]["name"] == "umm-al-qura"
r = c.get("/v1/calendar/convert", params=dict(direction="instant-to-calendars", instant="1650-09-19T15:42:00Z", lat=9.0192, lon=38.7525))
assert r.status_code == 200 and r.json()["data"]["waqt"]["day"]["hijri"] is None, r.text[:300]
print("CHAIN OK")
''')
    res = subprocess.run([py, str(script)], capture_output=True, text=True, cwd=tmp_path)
    assert res.returncode == 0 and "CHAIN OK" in res.stdout, res.stdout[-1500:] + res.stderr[-2500:]

    cli = str(bindir / ("waqt.exe" if sys.platform == "win32" else "waqt"))
    run = lambda *a: subprocess.run([cli, *a], capture_output=True, text=True, cwd=tmp_path)
    d, a, v = run("convert", "--hijri", "1448-4-15"), run("convert", "--hijri", "1448-4-15", "--provider", "arithmetic-tabular"), run("version")
    assert d.returncode == 0 and "2026-09-26" in d.stdout, d.stdout + d.stderr          # default: umm-al-qura
    assert a.returncode == 0 and "2026-09-28" in a.stdout, a.stdout + a.stderr          # explicit: the previous result
    assert v.returncode == 0 and cli_v in v.stdout and local_v in v.stdout and core_v in v.stdout, v.stdout + v.stderr
    assert run("--version").stdout.strip() == f"waqt-cli {cli_v}"

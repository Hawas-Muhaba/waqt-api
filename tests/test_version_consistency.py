"""Sprint 13 Goal F: mechanical audit of the six version axes (docs/VERSIONING.md).

Rules enforced:
  * every axis has its OWN literal source -- none is computed from another;
  * each package's pyproject/package.json agrees with its in-code version;
  * each changelog's newest heading is that package's current version;
  * docs (VERSIONING.md, PACKAGING.md) quote the current values;
  * every vector file is stamped with the running VECTOR_SET_VERSION / engine identity.
"""
from __future__ import annotations
import json, re
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
def read(p): return (ROOT / p).read_text(encoding="utf-8")
def lit(pattern, text): 
    m = re.search(pattern, text); assert m, pattern; return m.group(1)
def toml_version(p): return lit(r'(?m)^version\s*=\s*"([^"]+)"', read(p))
def first_heading(p): return lit(r'(?m)^## (\d+\.\d+\.\d+)', read(p))

CORE = lit(r'__version__\s*=\s*"([^"]+)"', read("core/waqt_core/_version.py"))
LOCAL = lit(r'__version__\s*=\s*"([^"]+)"', read("local/waqt_local/_version.py"))
SDK_PY = lit(r'__version__\s*=\s*"([^"]+)"', read("sdks/python/waqt_client/_version.py"))
SDK_JS = json.loads(read("sdks/js/waqt-client/package.json"))["version"]
API_CONTRACT = lit(r'(?m)^API_VERSION\s*=\s*"([^"]+)"', read("waqt/api/common.py"))
API_PKG = toml_version("pyproject.toml")

def test_package_metadata_matches_in_code_versions():
    assert toml_version("core/pyproject.toml") == CORE
    assert toml_version("local/pyproject.toml") == LOCAL
    assert toml_version("sdks/python/pyproject.toml") == SDK_PY
    assert lit(r'export const VERSION\s*=\s*"([^"]+)"', read("sdks/js/waqt-client/src/index.mjs")) == SDK_JS

def test_changelog_top_entry_is_current_version():
    assert first_heading("core/CHANGELOG.md") == CORE
    assert first_heading("local/CHANGELOG.md") == LOCAL
    assert first_heading("sdks/python/CHANGELOG.md") == SDK_PY
    assert first_heading("sdks/js/waqt-client/CHANGELOG.md") == SDK_JS

def test_axes_are_distinct_literals_not_derived():
    # the API contract version and the waqt-api *package* version are different things
    src = read("waqt/api/common.py")
    assert re.search(r'(?m)^API_VERSION\s*=\s*"\d+\.\d+\.\d+"', src), "API_VERSION must be its own literal"
    assert "__version__" not in lit(r'(?m)^(API_VERSION\s*=.*)$', src), "API version must not be derived from a package version"
    vs = read("core/waqt_core/versioning.py")
    assert re.search(r'(?m)^VECTOR_SET_VERSION\s*=\s*"\d+\.\d+"', vs)
    assert re.search(r'(?m)^ENGINE_REVISION\s*=\s*"\d+"', vs)
    for f in ("sdks/python/waqt_client/config.py", "sdks/js/waqt-client/src/config.mjs"):
        assert re.search(r'MAX_KNOWN_API_VERSION\s*=\s*"\d+\.\d+\.\d+"', read(f)), f

def test_root_package_depends_on_a_core_range_that_contains_core():
    from packaging.version import Version
    m = re.search(r'"waqt-core>=([\d.]+),<([\d.]+)"', read("pyproject.toml")); assert m
    assert Version(m.group(1)) <= Version(CORE) < Version(m.group(2))
    m = re.search(r'"waqt-core>=([\d.]+),<([\d.]+)"', read("local/pyproject.toml")); assert m
    assert Version(m.group(1)) <= Version(CORE) < Version(m.group(2))

def test_docs_quote_current_values():
    v = read("docs/VERSIONING.md")
    from waqt_core.versioning import ENGINE_REVISION, VECTOR_SET_VERSION
    row = lambda name: next(l for l in v.splitlines() if l.startswith(f"| **{name}"))
    assert f"`{CORE}`" in row("waqt-core version")
    assert f'`"{ENGINE_REVISION}"`' in row("Astronomical engine revision")
    assert f"`{API_CONTRACT}`" in row("API version")
    assert f"`{VECTOR_SET_VERSION}`" in row("Conformance-vector-set version")
    assert f"Python `{SDK_PY}`" in row("SDK version") and f"JS `{SDK_JS}`" in row("SDK version")
    pk = read("docs/PACKAGING.md")
    assert f"`waqt-core` {CORE}" in pk and f"`waqt-local` {LOCAL}" in pk and f"`waqt-api` {API_PKG}" in pk

def test_every_vector_file_is_stamped_with_running_versions():
    from waqt_core.versioning import VECTOR_SET_VERSION, computation_identity
    files = list((ROOT / "tests/vectors").glob("*_vectors.json")) + [ROOT / "sdks/vectors/sdk_conformance_vectors.json"]
    assert len(files) == 5
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        assert d["vector_set_version"] == VECTOR_SET_VERSION, f.name
        if d["astronomy_dependent"]:
            assert d["generated_at_computation"] == computation_identity(), f.name
        else:
            assert d["generated_at_computation"] is None, f.name

def test_sdk_max_known_api_version_is_not_above_the_api_it_was_tested_against():
    from packaging.version import Version
    py = lit(r'MAX_KNOWN_API_VERSION\s*=\s*"([^"]+)"', read("sdks/python/waqt_client/config.py"))
    js = lit(r'MAX_KNOWN_API_VERSION\s*=\s*"([^"]+)"', read("sdks/js/waqt-client/src/config.mjs"))
    assert py == js and Version(py) <= Version(API_CONTRACT)

"""Contract-aware expected API version for verification scripts.

The expected value is read from the DOCUMENTED version (the `API version` row of docs/VERSIONING.md),
not from `waqt.api.common.API_VERSION`. A server that reports a different version than the one the project
documents therefore FAILS the check; asserting the code against itself would pass vacuously.
tests/test_version_consistency.py separately pins the documented value to the in-code literal.

Historical-release assertions must NOT use this helper; they should name the historical version explicitly.
"""
from __future__ import annotations
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_ROW = re.compile(r"^\|\s*\*\*API version\*\*\s*\|[^|]*\|\s*`(\d+\.\d+\.\d+)`\s*\|", re.M)


def documented_api_version(root: Path = ROOT) -> str:
    text = (root / "docs" / "VERSIONING.md").read_text(encoding="utf-8")
    m = _ROW.search(text)
    if not m:
        raise RuntimeError("docs/VERSIONING.md has no parseable `API version` row")
    return m.group(1)


def api_version_matches(actual, expected: str | None = None) -> bool:
    """Strict equality with the documented version (or an explicitly given historical one)."""
    return isinstance(actual, str) and actual == (expected or documented_api_version())

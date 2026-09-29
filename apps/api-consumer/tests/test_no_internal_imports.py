"""Structural guard (Sprint 12 Goal A.3): api_consumer must not import any
Waqt package — that is the whole demonstration. Only its own module and the
standard library are allowed."""

import ast
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent / "api_consumer"
BANNED_PREFIXES = ("waqt_core", "waqt_local", "waqt", "waqt_client")


def _imports(path: Path):
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield a.name
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module
        elif isinstance(node, ast.ImportFrom) and node.level > 0:
            yield None  # relative import within api_consumer itself; fine


def test_no_waqt_package_is_ever_imported():
    for f in PKG.rglob("*.py"):
        for name in _imports(f):
            if name is None:
                continue
            top = name.split(".")[0]
            assert top not in BANNED_PREFIXES, (
                f"{f.relative_to(PKG.parent)} imports {name!r}: api_consumer must reach the "
                "API over HTTP only, never a Waqt package (that is Goal A.3's whole point)"
            )


def test_only_stdlib_is_imported():
    stdlib = set(sys.stdlib_module_names) if hasattr(sys, "stdlib_module_names") else set()
    for f in PKG.rglob("*.py"):
        for name in _imports(f):
            if name is None:
                continue
            top = name.split(".")[0]
            assert top in stdlib, f"{f.relative_to(PKG.parent)} imports non-stdlib {name!r}"

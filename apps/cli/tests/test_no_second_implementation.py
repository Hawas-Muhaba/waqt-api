"""Structural guard for the roadmap's rule (Sprint 12 Goal A): 'the
applications should consume Waqt, not create a second implementation of its
semantics.' `waqt_cli` may import `waqt_local` and the stdlib, and nothing
that computes astronomy, calendars, or scheduling on its own."""

import ast
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent / "waqt_cli"
# `waqt_core` is allowed for exactly one purpose: reading `waqt_core.__version__`
# to print it (see waqt_cli/main.py:_core_version). Enforced below by checking
# the *names bound from* waqt_core, not just that the module is imported.
ALLOWED_TOP_LEVEL = {"waqt_local", "waqt_core", "waqt_cli"}
ALLOWED_WAQT_CORE_NAMES = {"__version__"}
# Substrings that would indicate the CLI is computing astronomy/calendar facts
# itself, rather than reading fields waqt_local already named that way.
# `delta_t` is excluded: `comp.get("delta_t_seconds")` in render.py reads a
# field name waqt_local chose, it does not compute a Delta T value.
BANNED_SUBSTRINGS = ("ephem", "julian_century", "declination", "hijri_epoch", "1948440")


def _imports(path: Path):
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield a.name.split(".")[0], None
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            top = node.module.split(".")[0]
            for a in node.names:
                yield top, a.name


def test_only_imports_waqt_local_and_stdlib():
    import sys

    stdlib = set(sys.stdlib_module_names) if hasattr(sys, "stdlib_module_names") else set()
    for f in PKG.rglob("*.py"):
        for top, member in _imports(f):
            assert top in ALLOWED_TOP_LEVEL or top in stdlib or top == "__future__", (
                f"{f.relative_to(PKG.parent)} imports {top!r}: the CLI must consume waqt_local, "
                "not a new dependency that could compute Waqt semantics itself"
            )
            if top == "waqt_core" and member is not None:
                assert member in ALLOWED_WAQT_CORE_NAMES, (
                    f"{f.relative_to(PKG.parent)} imports waqt_core.{member}: only "
                    f"{ALLOWED_WAQT_CORE_NAMES} may be read directly from waqt_core"
                )


def test_no_astronomy_or_calendar_vocabulary_in_source():
    for f in PKG.rglob("*.py"):
        text = f.read_text().lower()
        for bad in BANNED_SUBSTRINGS:
            assert bad not in text, f"{f}: contains {bad!r} — looks like a second computation, not a CLI concern"

"""
Sprint 11 — the concrete "no duplicated computation" check.

`waqt/__init__.py` aliases `waqt.core`, `waqt.hijri`, `waqt.scheduling`
(and its submodules), `waqt.institutional` (and its submodules),
`waqt.calendar_providers` (and its submodules), `waqt.semantics`,
`waqt.solar`, `waqt.timescale`, `waqt.timezone_provider`, and
`waqt.calendar_interop` to the *same module objects* as their
`waqt_core` counterparts, via `sys.modules`, rather than importing a
second copy. This test asserts that identity directly — for the
modules themselves, for a representative function/class from each, and
for deep submodule imports (`waqt.scheduling.model`, etc.) — so a
future change that accidentally reintroduces a second implementation
(e.g. a stray physical `waqt/core.py` file shadowing the alias) fails
loudly here rather than silently drifting.

This requires both `waqt-core` (this package) and `waqt` (the HTTP API
package, `pip install -e .` from the repo root) to be installed; it is
skipped if `waqt` is not importable, since `waqt-core` itself has no
dependency on `waqt` and must be fully testable without it (see the
other files in this directory).
"""

from __future__ import annotations

import pytest

waqt = pytest.importorskip("waqt", reason="waqt (the HTTP API package) is not installed; waqt-core's own tests don't require it")

import waqt_core
import waqt_core.calendar_interop
import waqt_core.calendar_providers
import waqt_core.calendar_providers.local_observation
import waqt_core.calendar_providers.registry
import waqt_core.calendar_providers.umm_al_qura
import waqt_core.core
import waqt_core.hijri
import waqt_core.institutional
import waqt_core.institutional.academic_year
import waqt_core.institutional.binding
import waqt_core.institutional.fiscal_year
import waqt_core.institutional.profile
import waqt_core.institutional.rules
import waqt_core.institutional.week
import waqt_core.scheduling
import waqt_core.scheduling.context
import waqt_core.scheduling.engine
import waqt_core.scheduling.model
import waqt_core.scheduling.ops
import waqt_core.semantics
import waqt_core.solar
import waqt_core.timescale
import waqt_core.timezone_provider


MODULE_PAIRS = [
    ("waqt.core", waqt_core.core),
    ("waqt.hijri", waqt_core.hijri),
    ("waqt.semantics", waqt_core.semantics),
    ("waqt.solar", waqt_core.solar),
    ("waqt.timescale", waqt_core.timescale),
    ("waqt.timezone_provider", waqt_core.timezone_provider),
    ("waqt.calendar_interop", waqt_core.calendar_interop),
    ("waqt.calendar_providers", waqt_core.calendar_providers),
    ("waqt.calendar_providers.local_observation", waqt_core.calendar_providers.local_observation),
    ("waqt.calendar_providers.registry", waqt_core.calendar_providers.registry),
    ("waqt.calendar_providers.umm_al_qura", waqt_core.calendar_providers.umm_al_qura),
    ("waqt.institutional", waqt_core.institutional),
    ("waqt.institutional.academic_year", waqt_core.institutional.academic_year),
    ("waqt.institutional.binding", waqt_core.institutional.binding),
    ("waqt.institutional.fiscal_year", waqt_core.institutional.fiscal_year),
    ("waqt.institutional.profile", waqt_core.institutional.profile),
    ("waqt.institutional.rules", waqt_core.institutional.rules),
    ("waqt.institutional.week", waqt_core.institutional.week),
    ("waqt.scheduling", waqt_core.scheduling),
    ("waqt.scheduling.context", waqt_core.scheduling.context),
    ("waqt.scheduling.engine", waqt_core.scheduling.engine),
    ("waqt.scheduling.model", waqt_core.scheduling.model),
    ("waqt.scheduling.ops", waqt_core.scheduling.ops),
]


@pytest.mark.parametrize("dotted_name,expected_module", MODULE_PAIRS, ids=[p[0] for p in MODULE_PAIRS])
def test_waqt_module_is_the_same_object_as_waqt_core_module(dotted_name, expected_module):
    import importlib

    actual_module = importlib.import_module(dotted_name)
    assert actual_module is expected_module, (
        f"{dotted_name} is a DIFFERENT module object than its waqt_core "
        "counterpart -- this means the code is now duplicated, not aliased."
    )


def test_deep_import_statement_resolves_to_the_same_object():
    """The literal import forms real call sites use, not just importlib."""
    from waqt.scheduling.model import DAY_SHIFT as via_waqt
    from waqt_core.scheduling.model import DAY_SHIFT as via_core

    assert via_waqt is via_core


def test_representative_symbols_are_identical_across_both_names():
    from waqt.core import compute_waqt as via_waqt
    from waqt_core.core import compute_waqt as via_core

    assert via_waqt is via_core

    from waqt.institutional.rules import MonthDay as via_waqt_rule
    from waqt_core.institutional.rules import MonthDay as via_core_rule

    assert via_waqt_rule is via_core_rule

    from waqt.calendar_providers.registry import default_registry as via_waqt_reg
    from waqt_core.calendar_providers.registry import default_registry as via_core_reg

    assert via_waqt_reg is via_core_reg


def test_waqt_package_attribute_access_also_aliases():
    """`import waqt; waqt.core` (attribute access, no submodule import
    statement) also resolves to the same object -- waqt/__init__.py
    binds these as package attributes too, not just sys.modules keys."""
    assert waqt.core is waqt_core.core
    assert waqt.scheduling is waqt_core.scheduling
    assert waqt.institutional is waqt_core.institutional

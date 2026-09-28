"""
waqt -- the HTTP API / application layer for the Waqt Islamic Civil Time
and Calendar Standard.

As of Sprint 11, the computation layer this package is built on
(astronomy, Hijri calendars, scheduling, institutional calendars) lives
in the independently distributable `waqt-core` package (import name
`waqt_core`; see `core/README.md`). This package depends on it as a
normal Python dependency (declared in this repo's root
`pyproject.toml`) and contains only `waqt.api`, the FastAPI application
built on top.

Backward compatibility: `waqt.core`, `waqt.hijri`, `waqt.semantics`,
`waqt.solar`, `waqt.timescale`, `waqt.timezone_provider`,
`waqt.calendar_interop`, `waqt.calendar_providers` (and its submodules),
`waqt.institutional` (and its submodules), and `waqt.scheduling` (and
its submodules) all remain importable under their original names,
including deep imports such as `from waqt.scheduling.model import
DAY_SHIFT`. This is not a second copy: the code below registers each
name in `sys.modules` as an alias to the *same module object* that
`import waqt_core...` would give you, before anything in `waqt.api` (or
any other consumer) imports them. `waqt.core.compute_waqt is
waqt_core.core.compute_waqt` -- see `core/tests/test_shim_identity.py`
and this sprint's report (Sec 1) for the concrete verification. There is
exactly one implementation of every Waqt computation in this
repository, reachable under two package names.
"""

from __future__ import annotations

import sys as _sys

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

_ALIASES = {
    "waqt.core": waqt_core.core,
    "waqt.hijri": waqt_core.hijri,
    "waqt.semantics": waqt_core.semantics,
    "waqt.solar": waqt_core.solar,
    "waqt.timescale": waqt_core.timescale,
    "waqt.timezone_provider": waqt_core.timezone_provider,
    "waqt.calendar_interop": waqt_core.calendar_interop,
    "waqt.calendar_providers": waqt_core.calendar_providers,
    "waqt.calendar_providers.local_observation": waqt_core.calendar_providers.local_observation,
    "waqt.calendar_providers.registry": waqt_core.calendar_providers.registry,
    "waqt.calendar_providers.umm_al_qura": waqt_core.calendar_providers.umm_al_qura,
    "waqt.institutional": waqt_core.institutional,
    "waqt.institutional.academic_year": waqt_core.institutional.academic_year,
    "waqt.institutional.binding": waqt_core.institutional.binding,
    "waqt.institutional.fiscal_year": waqt_core.institutional.fiscal_year,
    "waqt.institutional.profile": waqt_core.institutional.profile,
    "waqt.institutional.rules": waqt_core.institutional.rules,
    "waqt.institutional.week": waqt_core.institutional.week,
    "waqt.scheduling": waqt_core.scheduling,
    "waqt.scheduling.context": waqt_core.scheduling.context,
    "waqt.scheduling.engine": waqt_core.scheduling.engine,
    "waqt.scheduling.model": waqt_core.scheduling.model,
    "waqt.scheduling.ops": waqt_core.scheduling.ops,
}
_sys.modules.update(_ALIASES)

# Also bind as attributes of this package, so `import waqt; waqt.core`
# works without a separate `import waqt.core` statement, matching how
# these names behaved when they were real submodules here.
core = waqt_core.core
hijri = waqt_core.hijri
semantics = waqt_core.semantics
solar = waqt_core.solar
timescale = waqt_core.timescale
timezone_provider = waqt_core.timezone_provider
calendar_interop = waqt_core.calendar_interop
calendar_providers = waqt_core.calendar_providers
institutional = waqt_core.institutional
scheduling = waqt_core.scheduling

del _sys, _ALIASES

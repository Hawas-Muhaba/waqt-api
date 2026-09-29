"""waqt-cli — reference command-line consumer of Waqt (Sprint 12).

This package contains NO Waqt semantics. Every fact it prints (Maghrib
boundaries, Hijri dates, Waqt readings, event instants, scheduling results,
computation identity) comes out of `waqt_local`, which calls `waqt_core`.
What lives here is argument parsing and presentation only. The one rule that
keeps that true, enforced by `tests/test_no_second_implementation.py`: this
package may import `waqt_local` and the standard library, and nothing else.
"""

from ._version import __version__

__all__ = ["__version__"]

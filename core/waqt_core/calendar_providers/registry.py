"""
waqt.calendar_providers.registry — a lookup table by provider name, and
a worked example of the "Custom" category.

The sprint brief lists "Custom" as one of the provider categories.
There is no single algorithm called "Custom" — the point is that
*anyone* can write a class satisfying `HijriProvider` (name, version,
from_gregorian) and plug it in, without touching waqt/core.py or
waqt/solar.py at all. `ExampleRegionalOffsetProvider` below exists to
prove that claim rather than just assert it: it's a deliberately
trivial provider (wraps another one and shifts by a fixed number of
days, simulating a hypothetical regional variant), written entirely
in this file, that the registry accepts exactly like any built-in one.

LAZY INITIALISATION NOTE
------------------------
`DEFAULT_REGISTRY` is populated lazily (on first access) rather than
at import time. `UmmAlQuraProvider()` triggers an ephem calculation
in its constructor; building it at module import time meant the entire
waqt package paid that cost on every cold start before the first
request. The lazy singleton avoids that.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from ..hijri import ArithmeticTabularProvider, HijriDate, HijriProvider
from .umm_al_qura import UmmAlQuraProvider


class CalendarProviderRegistry:
    """A name -> HijriProvider lookup. Exists so callers (e.g. the API
    layer) can offer a provider by name without knowing which module it
    lives in or how it's constructed."""

    def __init__(self):
        self._providers: dict[str, HijriProvider] = {}

    def register(self, provider: HijriProvider) -> None:
        self._providers[provider.name] = provider

    def get(self, name: str) -> Optional[HijriProvider]:
        return self._providers.get(name)

    def names(self) -> list[str]:
        return sorted(self._providers.keys())


@dataclass
class ExampleRegionalOffsetProvider:
    """Worked example of a third-party "Custom" provider — NOT a real
    calendar authority. Wraps another provider and shifts the reported
    day by a fixed offset, as a stand-in for "some regional convention
    starts the month a day earlier/later than the wrapped provider."

    This class touches nothing in waqt/core.py or waqt/solar.py, and
    core.py never needed to change to accept it — that's the point.
    See tests/test_calendar_providers.py::test_custom_provider_plugs_in_untouched.
    """

    wrapped: HijriProvider
    day_offset: int
    name: str = "example-regional-offset"
    version: str = "demo-v1"

    def from_gregorian(self, d: date) -> HijriDate:
        base = self.wrapped.from_gregorian(d + timedelta(days=self.day_offset))
        return HijriDate(
            year=base.year, month=base.month, day=base.day,
            provider=self.name, version=f"{self.version}+wraps({self.wrapped.name})",
        )


def default_registry() -> CalendarProviderRegistry:
    """The registry pre-populated with every stateless built-in
    provider (i.e. ones that need no per-deployment configuration like
    override dictionaries — DeclaredProvider and LocalObservationProvider
    are constructed by the caller instead, since they need data)."""
    reg = CalendarProviderRegistry()
    reg.register(ArithmeticTabularProvider())
    reg.register(UmmAlQuraProvider())
    return reg


# Lazy singleton — avoids running the ephem constructor at import time.
_default_registry: Optional[CalendarProviderRegistry] = None


def _get_default_registry() -> CalendarProviderRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = default_registry()
    return _default_registry


# Module-level attribute for backwards compatibility with code that
# imports DEFAULT_REGISTRY directly — it is built on first access.
class _LazyRegistry:
    """Proxy that builds the registry on first attribute access."""
    def __getattr__(self, name: str):
        return getattr(_get_default_registry(), name)

    def get(self, name: str) -> Optional[HijriProvider]:
        return _get_default_registry().get(name)

    def names(self) -> list[str]:
        return _get_default_registry().names()

    def register(self, provider: HijriProvider) -> None:
        _get_default_registry().register(provider)


DEFAULT_REGISTRY = _LazyRegistry()

"""The ONE definition of waqt-core's default Hijri calendar provider.

Option B (API 1.7.0 / waqt-core 0.5.0): the default is `umm-al-qura`. The HTTP API (`waqt.api.providers`), the offline
facade (`waqt_local`), the CLI and every core function that needs a provider when the caller passes none read it from
HERE, so the API default and this lower-level default cannot drift apart (tests/test_default_provider_single_source.py).

It labels days only. Waqt days, event instants, positions and countdowns do not depend on the provider, so changing the
default never moves canonical Waqt time. It is a deliberate project default, not a claim that every community follows
one calendar convention; any other provider stays selectable by passing it explicitly.

Note the range: `umm-al-qura` supports 1700-01-01..2300-12-31 (CAL-011). Core callers working outside that range must
pass a provider explicitly (for example `ArithmeticTabularProvider()`).
"""
from __future__ import annotations

from typing import Optional

from ..hijri import HijriProvider

DEFAULT_CALENDAR_PROVIDER = "umm-al-qura"

_instance: Optional[HijriProvider] = None


def default_calendar_provider() -> HijriProvider:
    """The default provider instance (built lazily: umm-al-qura constructs an `ephem` observer)."""
    global _instance
    if _instance is None:
        from .umm_al_qura import UmmAlQuraProvider

        provider = UmmAlQuraProvider()
        if provider.name != DEFAULT_CALENDAR_PROVIDER:   # the constant and the class must name the same provider
            raise RuntimeError(f"DEFAULT_CALENDAR_PROVIDER={DEFAULT_CALENDAR_PROVIDER!r} but the provider is {provider.name!r}")
        _instance = provider
    return _instance

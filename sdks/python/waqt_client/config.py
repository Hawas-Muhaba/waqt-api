"""
waqt_client.config — client configuration and version negotiation.

`waqt-client` is versioned to track the `/v1` HTTP contract's own major
version (see docs/API.md's `API_VERSION`), not tied 1:1 to it. This SDK
declares the range of server `api_version`s it was built against;
`WaqtClientConfig.on_version_mismatch` decides what happens when a server
reports something outside that range.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal, Optional

# The `/v1/*` API_VERSION range this SDK release was built and tested
# against (see waqt/api/common.py's own API_VERSION = "1.4.0"; Sprint 12
# added computation.engine/revision and /v1/version, additively). Additive server-side
# minor/patch bumps within the same major version are expected to stay
# compatible with a thin, spec-driven SDK like this one.
SUPPORTED_API_MAJOR_VERSION = 1
MIN_SUPPORTED_API_VERSION = "1.0.0"
MAX_KNOWN_API_VERSION = "1.8.0"

DEFAULT_BASE_URL = "https://waqt-api.onrender.com"
DEFAULT_TIMEOUT_SECONDS = 10.0

VersionMismatchPolicy = Literal["ignore", "warn", "raise"]


@dataclass
class WaqtClientConfig:
    base_url: str = DEFAULT_BASE_URL
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS

    # Defaults applied to every call that accepts these parameters but
    # doesn't override them explicitly -- e.g. construct one client with
    # calendar_provider="umm-al-qura" instead of repeating it on every
    # method call. Any per-call argument still wins over these.
    default_calendar_provider: Optional[str] = None
    default_fajr_angle_deg: Optional[float] = None
    default_isha_angle_deg: Optional[float] = None
    default_asr_shadow_ratio: Optional[float] = None
    default_timezone_override: Optional[str] = None

    on_version_mismatch: VersionMismatchPolicy = "warn"

    # Extra headers merged into every request (e.g. a future API key).
    extra_headers: dict = field(default_factory=dict)

    user_agent: str = "waqt-client-python/0.1.0"

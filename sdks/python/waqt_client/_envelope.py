"""
waqt_client._envelope — turning a raw HTTP response into either
`data` (a dict) or a raised `WaqtApiError`/`WaqtTransportError`, plus the
version-negotiation check. Pure functions, no I/O, shared by both the
sync and async clients.
"""

from __future__ import annotations

import warnings
from typing import Optional

from .config import MAX_KNOWN_API_VERSION, MIN_SUPPORTED_API_VERSION, VersionMismatchPolicy
from .errors import WaqtApiError, WaqtTransportError, WaqtVersionMismatch


def _version_tuple(v: str) -> tuple:
    try:
        return tuple(int(p) for p in v.split(".")[:3])
    except ValueError:
        return (0, 0, 0)


def check_version(server_version: Optional[str], policy: VersionMismatchPolicy) -> None:
    if policy == "ignore" or not server_version:
        return
    lo = _version_tuple(MIN_SUPPORTED_API_VERSION)
    hi_major = _version_tuple(MAX_KNOWN_API_VERSION)[0]
    sv = _version_tuple(server_version)
    in_range = lo <= sv and sv[0] == hi_major
    if in_range:
        return
    supported = f">= {MIN_SUPPORTED_API_VERSION}, major version {hi_major}"
    if policy == "raise":
        raise WaqtVersionMismatch(server_version, supported)
    warnings.warn(
        f"waqt-client: server api_version {server_version!r} is outside this SDK's "
        f"tested range ({supported}). Responses may not parse as expected.",
        stacklevel=3,
    )


def unwrap(status_code: int, body: Optional[dict], version_policy: VersionMismatchPolicy) -> dict:
    """Given a parsed JSON body and status code, return `data` on
    success or raise the appropriate structured error."""
    if body is None or not isinstance(body, dict) or "meta" not in body:
        raise WaqtTransportError(
            f"Response (status {status_code}) did not match the documented Waqt API "
            f"envelope (expected an object with 'meta'/'data'/'error' keys)."
        )

    meta = body.get("meta") or {}
    check_version(meta.get("api_version"), version_policy)

    if status_code >= 400 or body.get("error") is not None:
        raise WaqtApiError.from_envelope(status_code, body)

    return body.get("data") or {}

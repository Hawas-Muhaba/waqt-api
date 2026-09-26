"""
waqt_client.errors — structured error handling.

Every non-2xx response from the Waqt API comes back in the documented
envelope (`{"meta": ..., "data": null, "error": {"code", "message",
"details"}}` — see docs/API.md and `waqt/api/__init__.py`'s exception
handlers, which guarantee this shape even for a 500 the server never
anticipated). `WaqtApiError` carries that structure through as real
attributes a caller can branch on (`except WaqtApiError as e: if e.code ==
"CALENDAR_DATE_UNRESOLVABLE"`), instead of forcing a caller to parse
`str(exc)`.
"""

from __future__ import annotations

from typing import Any, Optional


class WaqtError(Exception):
    """Base class for every error this SDK raises."""


class WaqtApiError(WaqtError):
    """The server answered with a structured error envelope."""

    def __init__(self, status_code: int, code: str, message: str, details: Optional[dict] = None):
        super().__init__(f"[{code}] {message}")
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}

    @classmethod
    def from_envelope(cls, status_code: int, body: dict) -> "WaqtApiError":
        err = body.get("error") or {}
        return cls(
            status_code=status_code,
            code=err.get("code", "UNKNOWN_ERROR"),
            message=err.get("message", "The API returned an error with no message."),
            details=err.get("details") or {},
        )


class WaqtTransportError(WaqtError):
    """A network-level failure (timeout, connection refused, DNS, TLS,
    ...), or a response that wasn't even valid JSON / didn't match the
    documented envelope at all. Distinct from `WaqtApiError` because
    there's no server-issued error code to branch on."""

    def __init__(self, message: str, cause: Optional[BaseException] = None):
        super().__init__(message)
        self.cause = cause


class WaqtVersionMismatch(WaqtError):
    """Raised (only if the client is configured to be strict about it --
    see `WaqtClientConfig.on_version_mismatch`) when the server's
    `meta.api_version` doesn't satisfy this SDK's declared supported
    range. The SDK is thin and spec-driven; it does not try to guess
    whether an unrecognized version is compatible."""

    def __init__(self, server_version: str, supported: str):
        super().__init__(
            f"Server API version {server_version!r} is outside this SDK's supported "
            f"range ({supported}). Upgrade/downgrade the SDK, or the server, to match."
        )
        self.server_version = server_version
        self.supported = supported

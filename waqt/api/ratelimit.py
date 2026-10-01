"""
waqt.api.ratelimit -- opt-in inbound rate limiting (Sprint 14).

    WAQT_RATE_LIMIT="120/minute"     # N/second | N/minute | N/hour ; unset/empty = off
    WAQT_TRUST_PROXY=1               # key on X-Forwarded-For instead of the socket peer (see below)
    WAQT_TRUSTED_PROXY_HOPS=1        # how many proxies in front of the app append to X-Forwarded-For (default 1)
    WAQT_RATE_LIMIT_EXEMPT="/v1/health"   # comma-separated path prefixes (default shown)

X-Forwarded-For is client-controllable: a proxy APPENDS the address it saw to whatever the client sent,
so the leftmost entries can be forged. With WAQT_TRUST_PROXY the key is the entry added by the
outermost TRUSTED proxy, i.e. counted from the RIGHT (`hops` entries from the end). Forged leading
entries therefore cannot be used to rotate identities. Do not enable this unless a proxy really
sits in front of the app and sets the header, otherwise the header is attacker-chosen.

Off by default, like CORS: a library/dev server should not throttle itself. The
deployment manifest (render.yaml) turns it on.

Algorithm: sliding window log per client key -- exact, simple, and bounded:
at most `max_clients` keys are tracked (least-recently-seen evicted) and at most
`limit` timestamps are kept per key. Single-process, in-memory: with several
worker processes each has its own budget (documented limitation; put a shared
limiter in front for a multi-node deployment).

Rejections are ordinary Waqt error envelopes (code RATE_LIMITED, HTTP 429) with
`Retry-After`, and every response carries X-RateLimit-Limit/Remaining/Reset.
Being pure ASGI and installed *inside* CORSMiddleware, a 429 still carries the
CORS headers, so a browser app can read it instead of seeing an opaque failure.
"""

from __future__ import annotations

import json
import math
import re
import time
from collections import OrderedDict, deque
from typing import Callable, Optional, Tuple

from .common import ErrorCode, error_body

_UNITS = {"second": 1, "minute": 60, "hour": 3600}


def parse_rate_limit(spec: Optional[str]) -> Optional[Tuple[int, int]]:
    """'120/minute' -> (120, 60). Empty/None -> None. Malformed -> ValueError (fail loudly at startup)."""
    if spec is None or not spec.strip():
        return None
    m = re.fullmatch(r"\s*(\d+)\s*/\s*(second|minute|hour)s?\s*", spec.strip().lower())
    if not m or int(m.group(1)) < 1:
        raise ValueError(f"WAQT_RATE_LIMIT must look like '120/minute' (second|minute|hour), got {spec!r}")
    return int(m.group(1)), _UNITS[m.group(2)]


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: int, max_clients: int = 10_000,
                 clock: Callable[[], float] = time.monotonic):
        self.limit, self.window, self.max_clients, self._clock = limit, window_seconds, max_clients, clock
        self._hits: "OrderedDict[str, deque]" = OrderedDict()

    def check(self, key: str) -> Tuple[bool, int, float]:
        """-> (allowed, remaining, seconds_until_a_slot_frees)"""
        now = self._clock()
        q = self._hits.get(key)
        if q is None:
            q = self._hits[key] = deque()
            while len(self._hits) > self.max_clients:
                self._hits.popitem(last=False)
        else:
            self._hits.move_to_end(key)
        while q and now - q[0] >= self.window:
            q.popleft()
        if len(q) >= self.limit:
            return False, 0, max(0.0, self.window - (now - q[0]))
        q.append(now)
        return True, self.limit - len(q), max(0.0, self.window - (now - q[0]))


class RateLimitMiddleware:
    def __init__(self, app, limit: int, window_seconds: int, trust_proxy: bool = False,
                 exempt_prefixes: Tuple[str, ...] = ("/v1/health",), limiter: Optional[SlidingWindowLimiter] = None,
                 proxy_hops: int = 1):
        self.app = app
        self.proxy_hops = max(1, int(proxy_hops))
        self.limiter = limiter or SlidingWindowLimiter(limit, window_seconds)
        self.trust_proxy, self.exempt = trust_proxy, tuple(exempt_prefixes)

    def _key(self, scope) -> str:
        if self.trust_proxy:
            for k, v in scope.get("headers", []):
                if k == b"x-forwarded-for":
                    parts = [x.strip() for x in v.decode("latin-1").split(",") if x.strip()]
                    if parts:
                        # rightmost-minus-(hops-1): the address the outermost trusted proxy recorded
                        return parts[-self.proxy_hops] if len(parts) >= self.proxy_hops else parts[0]
        client = scope.get("client")
        return client[0] if client else "unknown"

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] == "OPTIONS" or \
                any(scope["path"].startswith(p) for p in self.exempt):
            return await self.app(scope, receive, send)

        allowed, remaining, reset = self.limiter.check(self._key(scope))
        lim = [(b"x-ratelimit-limit", str(self.limiter.limit).encode()),
               (b"x-ratelimit-remaining", str(remaining).encode()),
               (b"x-ratelimit-reset", str(math.ceil(reset)).encode())]
        if allowed:
            async def send_with_headers(message):
                if message["type"] == "http.response.start":
                    message = {**message, "headers": list(message.get("headers", [])) + lim}
                await send(message)
            return await self.app(scope, receive, send_with_headers)

        retry = max(1, math.ceil(reset))
        body = json.dumps(error_body(
            ErrorCode.RATE_LIMITED,
            f"Rate limit of {self.limiter.limit} requests per {self.limiter.window}s exceeded.",
            {"limit": self.limiter.limit, "window_seconds": self.limiter.window,
             "retry_after_seconds": retry})).encode()
        await send({"type": "http.response.start", "status": 429,
                    "headers": [(b"content-type", b"application/json"),
                                (b"content-length", str(len(body)).encode()),
                                (b"retry-after", str(retry).encode())] + lim})
        await send({"type": "http.response.body", "body": body})

"""
waqt_core.calendar_providers.aladhan -- a LIVE Hijri date source (Sprint 14).

    HijriProvider
        |- ArithmeticTabular      (local, offline)
        |- UmmAlQura              (local, offline, astronomical approximation)
        |- Declared               (institution override)
        |- LocalObservation       (reported sighting)
        `- AlAdhanHijriProvider   (this module: remote, cached, with local fallback)

WHAT THIS IS
    Asks AlAdhan's public API (`GET {base}/gToH/DD-MM-YYYY`) for the Hijri date of
    a Gregorian date, caches the answer for 12 hours, and -- whenever the service
    cannot deliver -- answers from a local provider instead and SAYS SO.

WHAT THIS IS NOT
    * It is never a source of prayer/solar event times. Those come only from
      `waqt_core.solar`. This module imports nothing from `solar`/`timescale`, and
      `core/tests/test_aladhan_isolation.py` enforces that (import graph + byte
      equality of computed events under every failure mode).
    * It never raises. `from_gregorian` always returns a `HijriDate`; every failure
      is converted into a `local-fallback` result whose `provenance.fallback_reason`
      says why. It is also time-bounded (socket timeout + a bounded wait for the
      single-flight lock), because `compute_waqt` calls it inline.

PROVENANCE (HijriDate.source)
    remote          fresh from the service, or a cache hit younger than the TTL
    remote-stale    the service failed and a previously fetched value (older than
                    the TTL, younger than `max_stale_seconds`) is served instead
    local-fallback  nothing usable from the service; `provider` names the local
                    provider that actually produced the date

DISAGREEMENT IS VISIBLE
    On every successful remote answer the local reference provider is also asked
    (best effort) and the comparison is recorded in `provenance.cross_check`
    (`agrees`, `delta_days`). The remote value is what is returned; the local one
    is never silently substituted -- and never silently hidden either.

SAFETY RAILS (this is a public API's outbound call, so it must not be an amplifier)
    * bounded LRU cache (`max_cache_entries`) -- a date sweep cannot grow memory;
    * outbound token bucket (`max_requests_per_minute`);
    * circuit breaker: after a hard failure (network / timeout / 5xx / 429) no
      request is made for `failure_cooldown_seconds` (or the upstream Retry-After);
    * `min_date`/`max_date` window: dates outside it never leave the process;
    * response is size-capped, must echo the requested Gregorian date, must have
      in-range fields, and must lie within `max_plausible_delta_days` of the
      arithmetic-tabular calendar -- otherwise it is rejected as malformed;
    * redirects are refused; only http(s) base URLs are accepted.

The network layer is an injectable `transport` so tests never need the internet;
the default is a stdlib `urllib` transport (no new dependency).

UNVERIFIED AGAINST THE LIVE SERVICE: the response shape parsed here
(`data.hijri.{day, month.number, year, method}`, `data.gregorian.date`) is taken from
AlAdhan's published documentation and is exercised only against a local fake server
in this repository's CI. See SPRINT-14-REPORT.md.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Callable, Optional, Tuple
from urllib.parse import urlencode, urlsplit

from ..hijri import (
    ArithmeticTabularProvider,
    HijriDate,
    HijriProvenance,
    HijriProvider,
    _gregorian_to_jdn,
    _hijri_to_jdn,
)

PROVIDER_NAME = "aladhan"
PROVIDER_VERSION = "aladhan-gToH-v1"
DEFAULT_BASE_URL = "https://api.aladhan.com/v1"

#: Machine-readable reasons a remote answer was not used. Stable vocabulary.
FALLBACK_REASONS = (
    "disabled",                  # operator turned remote lookups off
    "date-outside-remote-window",
    "circuit-open",              # recent hard failure; not retrying yet
    "outbound-rate-limited",     # our own outbound budget is spent
    "busy",                      # another lookup held the single-flight lock too long
    "timeout",
    "network-error",
    "upstream-rate-limited",     # HTTP 429
    "upstream-server-error",     # HTTP 5xx
    "upstream-rejected",         # other HTTP 4xx
    "malformed-response",
    "date-mismatch",             # response answered a different Gregorian date
    "implausible-response",      # too far from the arithmetic calendar
    "internal-error",            # a bug in this module; still never propagated
)

_HARD_FAILURES = {"timeout", "network-error", "upstream-rate-limited", "upstream-server-error"}


# --------------------------------------------------------------------------
# Transport
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class TransportResponse:
    status: int
    body: bytes
    headers: dict = field(default_factory=dict)


class TransportTimeout(Exception):
    pass


class TransportError(Exception):
    pass


Transport = Callable[[str, float, int], TransportResponse]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):  # refuse: the endpoint is fixed by configuration
        return None


def urllib_transport(url: str, timeout: float, max_bytes: int) -> TransportResponse:
    """Default transport. GET, no redirects, body capped at `max_bytes`."""
    req = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": "waqt-core/aladhan-provider"}
    )
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(req, timeout=timeout) as resp:
            body = resp.read(max_bytes + 1)
            return TransportResponse(resp.status, body[: max_bytes + 1], dict(resp.headers.items()))
    except urllib.error.HTTPError as e:   # non-2xx is data, not an exception
        try:
            body = e.read(max_bytes + 1)
        except Exception:
            body = b""
        return TransportResponse(e.code, body, dict(e.headers.items()) if e.headers else {})
    except (TimeoutError, OSError) as e:
        if isinstance(e, TimeoutError) or "timed out" in str(e).lower():
            raise TransportTimeout(str(e)) from e
        raise TransportError(f"{type(e).__name__}: {e}") from e
    except urllib.error.URLError as e:  # pragma: no cover - URLError is an OSError subclass
        raise TransportError(str(e)) from e


class _Fail(Exception):
    def __init__(self, reason: str, detail: str = "", retry_after: Optional[float] = None):
        super().__init__(reason)
        self.reason, self.detail, self.retry_after = reason, detail, retry_after


@dataclass
class _Entry:
    year: int
    month: int
    day: int
    method: Optional[str]
    fetched_mono: float
    fetched_wall: datetime
    cross_check: Optional[dict]


class AlAdhanHijriProvider:
    """See module docstring. Thread-safe; one instance is meant to be shared."""

    name = PROVIDER_NAME

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        method: Optional[str] = None,
        enabled: bool = True,
        transport: Optional[Transport] = None,
        fallback: Optional[HijriProvider] = None,
        fallback_factory: Optional[Callable[[], HijriProvider]] = None,
        cross_check: bool = True,
        timeout_seconds: float = 3.0,
        max_response_bytes: int = 65536,
        cache_ttl_seconds: int = 12 * 3600,
        max_stale_seconds: int = 7 * 24 * 3600,
        max_cache_entries: int = 4096,
        failure_cooldown_seconds: float = 30.0,
        max_retry_after_seconds: float = 600.0,
        max_requests_per_minute: int = 30,
        min_date: date = date(1900, 1, 1),
        max_date: date = date(2076, 12, 31),
        max_plausible_delta_days: int = 3,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        parts = urlsplit(base_url)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ValueError(f"base_url must be an http(s) URL, got {base_url!r}")
        self._base = base_url.rstrip("/")
        self._method = method
        self.enabled = enabled
        self._transport = transport or urllib_transport
        self._fallback = fallback
        self._fallback_factory = fallback_factory
        self._cross_check = cross_check
        self._timeout = float(timeout_seconds)
        self._max_bytes = int(max_response_bytes)
        self._ttl = int(cache_ttl_seconds)
        self._max_stale = int(max_stale_seconds)
        self._max_entries = int(max_cache_entries)
        self._cooldown = float(failure_cooldown_seconds)
        self._max_retry_after = float(max_retry_after_seconds)
        self._rpm = int(max_requests_per_minute)
        self._min_date, self._max_date = min_date, max_date
        self._max_delta = int(max_plausible_delta_days)
        self._clock, self._wall = clock, wall_clock

        self._lock = threading.Lock()          # guards everything below
        self._flight = threading.Lock()        # single-flight around the network call
        self._cache: "OrderedDict[Tuple[date, Optional[str]], _Entry]" = OrderedDict()
        self._open_until = 0.0
        self._soft_failures = 0
        self._tokens = float(self._rpm)
        self._tokens_at = self._clock()
        self._stats = {"remote_ok": 0, "cache_hit": 0, "fallback": 0, "stale": 0,
                       "requests": 0, "last_success": None, "last_failure": None,
                       "last_failure_reason": None}
        self._tabular = ArithmeticTabularProvider()
        self._resolved_fallback: Optional[HijriProvider] = fallback

    # ---- identity ---------------------------------------------------------

    @property
    def version(self) -> str:
        return PROVIDER_VERSION + (f"+method={self._method}" if self._method else "")

    # ---- public API -------------------------------------------------------

    def from_gregorian(self, d: date) -> HijriDate:
        try:
            return self._resolve(d)
        except Exception as e:  # the contract: never raise
            return self._fallback_date(d, "internal-error", f"{type(e).__name__}: {e}")

    def status(self) -> dict:
        """Cheap, network-free operational snapshot for /v1/health and /v1/version."""
        with self._lock:
            now = self._clock()
            return {
                "provider": self.name,
                "version": self.version,
                "enabled": self.enabled,
                "circuit": "open" if now < self._open_until else "closed",
                "circuit_retry_in_seconds": max(0.0, round(self._open_until - now, 1)),
                "cache_entries": len(self._cache),
                "cache_ttl_seconds": self._ttl,
                "fallback_provider": self._fallback_name(),
                **{k: v for k, v in self._stats.items()},
            }

    def clear_cache(self) -> None:
        with self._lock:
            self._cache.clear()

    def reset_circuit(self) -> None:
        with self._lock:
            self._open_until, self._soft_failures = 0.0, 0

    # ---- resolution -------------------------------------------------------

    def _resolve(self, d: date) -> HijriDate:
        if not self.enabled:
            return self._fallback_date(d, "disabled", "remote lookups are disabled by configuration")
        if not (self._min_date <= d <= self._max_date):
            return self._fallback_date(
                d, "date-outside-remote-window",
                f"remote window is {self._min_date.isoformat()}..{self._max_date.isoformat()}")

        key = (d, self._method)
        now = self._clock()
        with self._lock:
            entry = self._cache.get(key)
            if entry is not None and now - entry.fetched_mono < self._ttl:
                self._cache.move_to_end(key)
                self._stats["cache_hit"] += 1
                return self._from_entry(d, entry, "hit", "remote")

        # Cache miss or expired: try the network (single-flight, bounded wait).
        failure: Optional[_Fail] = None
        if not self._flight.acquire(timeout=self._timeout):
            failure = _Fail("busy", "another lookup held the lock past the timeout")
        else:
            try:
                with self._lock:   # re-check: a concurrent caller may have filled it
                    entry = self._cache.get(key)
                    if entry is not None and self._clock() - entry.fetched_mono < self._ttl:
                        self._stats["cache_hit"] += 1
                        return self._from_entry(d, entry, "hit", "remote")
                try:
                    fresh = self._fetch(d)
                    with self._lock:
                        self._soft_failures = 0
                        self._store(key, fresh)
                        self._stats["remote_ok"] += 1
                        self._stats["last_success"] = self._wall().isoformat()
                    return self._from_entry(d, fresh, "miss", "remote")
                except _Fail as f:
                    failure = f
                    self._record_failure(f)
            finally:
                self._flight.release()

        # Failure path: stale-if-error, then local fallback.
        with self._lock:
            entry = self._cache.get(key)
            if entry is not None and self._clock() - entry.fetched_mono < self._max_stale:
                self._stats["stale"] += 1
                return self._from_entry(d, entry, "stale", "remote-stale",
                                        reason=failure.reason, detail=failure.detail)
        return self._fallback_date(d, failure.reason, failure.detail)

    # ---- network ----------------------------------------------------------

    def _fetch(self, d: date) -> _Entry:
        with self._lock:
            now = self._clock()
            if now < self._open_until:
                raise _Fail("circuit-open", f"retry in {self._open_until - now:.0f}s")
            self._refill(now)
            if self._tokens < 1.0:
                raise _Fail("outbound-rate-limited", f"budget is {self._rpm} requests/minute")
            self._tokens -= 1.0
            self._stats["requests"] += 1

        gdate = d.strftime("%d-%m-%Y")
        url = f"{self._base}/gToH/{gdate}"
        if self._method:
            url += "?" + urlencode({"calendarMethod": self._method})
        try:
            resp = self._transport(url, self._timeout, self._max_bytes)
        except TransportTimeout as e:
            raise _Fail("timeout", f"no answer within {self._timeout}s") from e
        except TransportError as e:
            raise _Fail("network-error", str(e)[:200]) from e

        if resp.status == 429:
            raise _Fail("upstream-rate-limited", "HTTP 429", self._retry_after(resp))
        if resp.status >= 500:
            raise _Fail("upstream-server-error", f"HTTP {resp.status}", self._retry_after(resp))
        if resp.status != 200:
            raise _Fail("upstream-rejected", f"HTTP {resp.status}")
        if len(resp.body) > self._max_bytes:
            raise _Fail("malformed-response", "response exceeds size cap")

        y, m, day, method = self._parse(resp.body, gdate)
        self._plausibility(d, y, m, day)
        return _Entry(y, m, day, method, self._clock(), self._wall(), self._make_cross_check(d, y, m, day))

    @staticmethod
    def _retry_after(resp: TransportResponse) -> Optional[float]:
        for k, v in (resp.headers or {}).items():
            if k.lower() == "retry-after":
                try:
                    return max(0.0, float(v))
                except (TypeError, ValueError):
                    return None
        return None

    @staticmethod
    def _parse(body: bytes, gdate: str) -> Tuple[int, int, int, Optional[str]]:
        try:
            obj = json.loads(body.decode("utf-8"))
            if obj.get("code") not in (200, "200"):
                raise ValueError(f"code={obj.get('code')!r}")
            data = obj["data"]
            h = data["hijri"]
            y, m, day = int(h["year"]), int(h["month"]["number"]), int(h["day"])
            echoed = (data.get("gregorian") or {}).get("date")
            method = h.get("method") if isinstance(h.get("method"), str) else None
        except (ValueError, KeyError, TypeError, AttributeError, UnicodeDecodeError) as e:
            raise _Fail("malformed-response", f"{type(e).__name__}: {str(e)[:120]}") from e
        if echoed is not None and echoed != gdate:
            raise _Fail("date-mismatch", f"asked {gdate}, answered {echoed!r}")
        if not (1 <= y <= 1700 and 1 <= m <= 12 and 1 <= day <= 30):
            raise _Fail("malformed-response", f"out-of-range fields {y}-{m}-{day}")
        return y, m, day, method

    def _plausibility(self, d: date, y: int, m: int, day: int) -> None:
        """Reject an answer that is implausibly far from the arithmetic calendar.
        Real calendars differ from it by 1-2 days; a larger gap means garbage."""
        t = self._tabular.from_gregorian(d)
        delta = _hijri_to_jdn(y, m, day) - _hijri_to_jdn(t.year, t.month, t.day)
        if abs(delta) > self._max_delta:
            raise _Fail("implausible-response",
                        f"{abs(delta)} days from the arithmetic calendar (limit {self._max_delta})")

    # ---- bookkeeping ------------------------------------------------------

    def _refill(self, now: float) -> None:   # caller holds self._lock
        self._tokens = min(float(self._rpm), self._tokens + (now - self._tokens_at) * self._rpm / 60.0)
        self._tokens_at = now

    def _store(self, key, entry: _Entry) -> None:   # caller holds self._lock
        self._cache[key] = entry
        self._cache.move_to_end(key)
        while len(self._cache) > self._max_entries:
            self._cache.popitem(last=False)

    def _record_failure(self, f: _Fail) -> None:
        with self._lock:
            self._stats["last_failure"] = self._wall().isoformat()
            self._stats["last_failure_reason"] = f.reason
            if f.reason in ("circuit-open", "outbound-rate-limited"):
                return   # our own guards, not evidence about the service
            self._soft_failures += 1
            if f.reason in _HARD_FAILURES or self._soft_failures >= 3:
                cool = self._cooldown if f.retry_after is None else min(
                    max(f.retry_after, self._cooldown), self._max_retry_after)
                self._open_until = self._clock() + cool

    # ---- result construction ---------------------------------------------

    def _from_entry(self, d: date, e: _Entry, cache: str, source: str,
                    reason: Optional[str] = None, detail: Optional[str] = None) -> HijriDate:
        age = max(0.0, self._clock() - e.fetched_mono)
        prov = HijriProvenance(
            requested_provider=self.name, cache=cache,
            fetched_at=e.fetched_wall.replace(microsecond=0).isoformat(),
            age_seconds=round(age, 1), ttl_seconds=self._ttl, upstream_method=e.method,
            fallback_reason=reason, fallback_detail=detail, cross_check=e.cross_check)
        return HijriDate(e.year, e.month, e.day, provider=self.name, version=self.version,
                         source=source, provenance=prov)

    def _fallback_provider(self) -> HijriProvider:
        if self._resolved_fallback is None:
            if self._fallback_factory is not None:
                self._resolved_fallback = self._fallback_factory()
            else:
                from .umm_al_qura import UmmAlQuraProvider
                self._resolved_fallback = UmmAlQuraProvider()
        return self._resolved_fallback

    def _fallback_name(self) -> str:
        if self._resolved_fallback is not None:
            return self._resolved_fallback.name
        return "umm-al-qura" if self._fallback_factory is None else "(lazy)"

    def _fallback_date(self, d: date, reason: str, detail: str) -> HijriDate:
        with self._lock:
            self._stats["fallback"] += 1
        chain_note = None
        try:
            base = self._fallback_provider().from_gregorian(d)
        except Exception as e:   # the local provider can fail too (e.g. ephem range); last resort cannot
            chain_note = f"; {self._fallback_name()} failed ({type(e).__name__}), used arithmetic-tabular"
            base = self._tabular.from_gregorian(d)
        prov = HijriProvenance(
            requested_provider=self.name, fallback_reason=reason,
            fallback_detail=(detail + (chain_note or ""))[:300] or None)
        return HijriDate(base.year, base.month, base.day, provider=base.provider, version=base.version,
                         source_note=base.source_note, source="local-fallback", provenance=prov)

    def _make_cross_check(self, d: date, y: int, m: int, day: int) -> Optional[dict]:
        if not self._cross_check:
            return None
        try:
            local = self._fallback_provider().from_gregorian(d)
            delta = _hijri_to_jdn(y, m, day) - _hijri_to_jdn(local.year, local.month, local.day)
            return {"provider": local.provider, "version": local.version, "date": local.iso_like(),
                    "agrees": delta == 0, "delta_days": delta}
        except Exception as e:
            return {"provider": None, "agrees": None, "delta_days": None,
                    "unavailable": f"{type(e).__name__}"}


__all__ = ["AlAdhanHijriProvider", "TransportResponse", "TransportError", "TransportTimeout",
           "urllib_transport", "FALLBACK_REASONS", "PROVIDER_NAME", "PROVIDER_VERSION", "DEFAULT_BASE_URL"]

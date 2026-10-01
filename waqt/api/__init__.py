"""
waqt.api — the Waqt API v1 app.

Structured as a small package (not one file) because v1 has seven
endpoints (plus, since Sprint 6, three under /v1/schedule/) (see docs/API.md); each lives in its own module and shares
the contract defined in waqt.api.common. Import path is unchanged from
Sprint 1-3 — `waqt.api:app` and `from waqt.api import app` both still
work, since `app` is defined right here in the package's __init__.

Every error response, including ones this code never anticipated,
comes back in the same envelope as a success response (meta/data/error)
— see the exception handlers below. This closes a real gap from
Sprint 3: an uncaught exception deep in a provider (e.g. the old-date
ValueError inside UmmAlQuraProvider's ephem calls) used to surface as
a raw, unstructured 500. Now it's still a 500, but it's a 500 in the
documented shape, with a message a caller can actually branch on.
"""

from __future__ import annotations

import os

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse

from waqt_core.versioning import computation_identity

from .common import API_VERSION, ApiError, ErrorCode, error_body
from .waqt_endpoint import router as waqt_router
from .day_endpoint import router as day_router
from .events_endpoint import router as events_router
from .hijri_endpoint import router as hijri_router
from .calendar_endpoint import router as calendar_router
from .location_endpoint import router as location_router
from .conversions_endpoint import router as conversions_router
from .schedule_endpoint import router as schedule_router
from .institutional_endpoint import router as institutional_router
from .calendar_convert_endpoint import router as calendar_convert_router
from .version_endpoint import router as version_router
from .providers import aladhan_status
from .ratelimit import RateLimitMiddleware, parse_rate_limit


_ROUTERS = (waqt_router, day_router, events_router, hijri_router, calendar_router, location_router,
            conversions_router, schedule_router, institutional_router, calendar_convert_router, version_router)


def _env_origins():
    return [o.strip() for o in os.environ.get("WAQT_CORS_ORIGINS", "").split(",") if o.strip()]


def create_app(cors_origins=None, rate_limit=None, trust_proxy=None) -> FastAPI:
    """Build the app. Arguments default to the environment (WAQT_CORS_ORIGINS,
    WAQT_RATE_LIMIT, WAQT_TRUST_PROXY); passing them explicitly is how tests
    (and embedders) get differently-configured apps in one process.
    `rate_limit` is a spec string like "120/minute"; "" or None (and no env) = off."""
    application = FastAPI(
        title="Waqt API",
        version=API_VERSION,
        description=(
            "A Makkah-anchored, Maghrib-to-Maghrib civil time and Hijri calendar API. "
            "See /docs for interactive testing, and the project's docs/API.md, "
            "docs/TIME-MODEL.md, docs/ASTRONOMY.md, docs/CALENDARS.md, docs/SCHEDULING.md, "
            "docs/INSTITUTIONAL.md, docs/CALENDAR-INTEROP.md, docs/LIVE-INTEGRATIONS.md for the full contract."
        ),
    )
    for r in _ROUTERS:
        application.include_router(r)

    # Middleware order: the LAST one added is outermost. Rate limiting goes in first
    # (inner) and CORS last (outer) so that a 429 still carries CORS headers.
    spec = os.environ.get("WAQT_RATE_LIMIT") if rate_limit is None else rate_limit
    parsed = parse_rate_limit(spec)
    if parsed:
        trust = (os.environ.get("WAQT_TRUST_PROXY", "").lower() in ("1", "true", "yes")) if trust_proxy is None else trust_proxy
        exempt = tuple(p.strip() for p in os.environ.get("WAQT_RATE_LIMIT_EXEMPT", "/v1/health").split(",") if p.strip())
        try:
            hops = int(os.environ.get("WAQT_TRUSTED_PROXY_HOPS", "1"))
        except ValueError:
            hops = 1
        application.add_middleware(RateLimitMiddleware, limit=parsed[0], window_seconds=parsed[1],
                                   trust_proxy=trust, exempt_prefixes=exempt, proxy_hops=hops)

    # Sprint 12: OPT-IN cross-origin access. Off by default (no header is ever sent
    # unless the operator sets WAQT_CORS_ORIGINS), because a public time API should
    # not silently become embeddable from every origin.
    origins = _env_origins() if cors_origins is None else list(cors_origins)
    if origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["*"],
            expose_headers=["Retry-After", "X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
        )

    @application.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError):
        return JSONResponse(status_code=exc.status_code, content=error_body(exc.code, exc.message, exc.details))

    @application.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        # FastAPI/pydantic's own parameter validation (e.g. lat out of range, a required
        # param missing) -- reshaped into the same envelope as every other error.
        return JSONResponse(
            status_code=422,
            content=error_body(ErrorCode.VALIDATION_ERROR,
                               "One or more request parameters were invalid.",
                               {"errors": jsonable_encoder(exc.errors())}),
        )

    @application.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        # The backstop: anything not already an ApiError or a validation error still
        # comes back structured, never a bare traceback.
        return JSONResponse(
            status_code=500,
            content=error_body(ErrorCode.INTERNAL_ERROR,
                               "An unexpected error occurred while computing the result.",
                               {"exception_type": type(exc).__name__}),
        )

    @application.get("/", include_in_schema=False)
    def root():
        return RedirectResponse(url="/docs")

    @application.get("/v1/health")
    def health(response: Response):
        # Sprint 14: no network I/O here, ever. `integrations` is an in-memory snapshot
        # of the live Hijri provider's circuit/cache state, so a load balancer probing
        # this endpoint can never be slowed down (or rate limited) by an upstream outage.
        # Status stays "ok" while the astronomy engine can serve: a degraded Hijri
        # integration falls back locally and is reported here, not treated as downtime.
        response.headers["Cache-Control"] = "no-store"
        computation = computation_identity()
        integration = aladhan_status()
        if not integration["enabled"]:
            provider_health = "disabled"
        elif integration["circuit"] == "open" or (
            integration["last_failure"] and
            (not integration["last_success"] or integration["last_failure"] > integration["last_success"])
        ):
            provider_health = "degraded"
        elif integration["last_success"]:
            provider_health = "available"
        else:
            provider_health = "unknown"
        return {
            "status": "ok",
            "spec": "waqt-core/0.1",
            "api_version": API_VERSION,
            "computation": computation,
            "components": {
                "application": {"status": "available"},
                "computation": {"status": "available", **computation},
                "optional_providers": {"aladhan": {"status": provider_health}},
            },
            "integrations": {"hijri_aladhan": integration},
        }

    return application


app = create_app()

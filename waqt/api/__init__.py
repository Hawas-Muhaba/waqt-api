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

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
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

app = FastAPI(
    title="Waqt API",
    version=API_VERSION,
    description=(
        "A Makkah-anchored, Maghrib-to-Maghrib civil time and Hijri calendar API. "
        "See /docs for interactive testing, and the project's docs/API.md, "
        "docs/TIME-MODEL.md, docs/ASTRONOMY.md, docs/CALENDARS.md, docs/SCHEDULING.md, "
        "docs/INSTITUTIONAL.md, docs/CALENDAR-INTEROP.md for the full contract."
    ),
)

for r in (waqt_router, day_router, events_router, hijri_router, calendar_router, location_router,
          conversions_router, schedule_router, institutional_router, calendar_convert_router, version_router):
    app.include_router(r)

# Sprint 12: OPT-IN cross-origin access. Off by default (no header is ever sent
# unless the operator sets WAQT_CORS_ORIGINS), because a public time API should
# not silently become embeddable from every origin. The reference web app
# (apps/web) avoids needing this in development by serving /v1 same-origin.
_cors_origins = [o.strip() for o in os.environ.get("WAQT_CORS_ORIGINS", "").split(",") if o.strip()]
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )


@app.exception_handler(ApiError)
async def handle_api_error(request: Request, exc: ApiError):
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(exc.code, exc.message, exc.details),
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError):
    # FastAPI/pydantic's own parameter validation (e.g. lat out of
    # range, a required param missing) — reshaped into the same
    # envelope as every other error instead of its default format.
    return JSONResponse(
        status_code=422,
        content=error_body(
            ErrorCode.VALIDATION_ERROR,
            "One or more request parameters were invalid.",
            {"errors": exc.errors()},
        ),
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception):
    # The backstop: anything not already an ApiError or a validation
    # error still comes back structured, never a bare traceback.
    return JSONResponse(
        status_code=500,
        content=error_body(
            ErrorCode.INTERNAL_ERROR,
            "An unexpected error occurred while computing the result.",
            {"exception_type": type(exc).__name__},
        ),
    )


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.get("/v1/health")
def health():
    return {"status": "ok", "spec": "waqt-core/0.1", "api_version": API_VERSION,
            "computation": computation_identity()}

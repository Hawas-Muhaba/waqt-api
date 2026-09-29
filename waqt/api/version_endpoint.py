"""
waqt.api.version_endpoint — GET /v1/version   (API 1.4.0, additive)

One machine-readable answer to "exactly what is running here": waqt-core
version, engine + revision + accuracy level, API version, the conformance
vector set the server's engine revision corresponds to, and the engine
revision history. Exists so a client (or a reproducibility audit) does not
have to infer the computation revision from a response's `computation`
block, and so a consumer can check *before* trusting a number.

The payload is built by `waqt_core.versioning.version_report`, the same
function `waqt_local` uses, so the server and the embeddable library cannot
describe themselves differently. See docs/VERSIONING.md.
"""

from __future__ import annotations

from fastapi import APIRouter
from waqt_core.versioning import version_report

from .common import API_VERSION, CORE_SPEC_VERSION, success

router = APIRouter()


@router.get("/v1/version")
def get_version():
    return success(version_report(api_version=API_VERSION, spec_version=CORE_SPEC_VERSION))

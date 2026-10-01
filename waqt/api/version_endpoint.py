"""
waqt.api.version_endpoint — GET /v1/version   (API 1.4.0, additive; 1.5.0 adds `integrations`)

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

from fastapi import APIRouter, Response
from waqt_core.versioning import version_report

from .common import API_VERSION, CORE_SPEC_VERSION, success
from .providers import PROVIDER_CATALOG, aladhan_status

router = APIRouter()


@router.get("/v1/version")
def get_version(response: Response):
    response.headers["Cache-Control"] = "public, max-age=30"
    data = version_report(api_version=API_VERSION, spec_version=CORE_SPEC_VERSION)
    # Sprint 14: which *calendar* providers this server offers, and the identity of the one
    # that talks to the outside world. Added here, not in version_report, because it is a
    # property of this deployment (the embeddable library has no remote provider) and must
    # not make waqt_local and the server "describe themselves differently" about the engine.
    st = aladhan_status()
    data["integrations"] = {
        "calendar_providers": sorted(PROVIDER_CATALOG),
        "hijri_aladhan": {k: st[k] for k in ("provider", "version", "enabled", "cache_ttl_seconds",
                                              "fallback_provider")},
        "affects_astronomy": False,
    }
    return success(data)

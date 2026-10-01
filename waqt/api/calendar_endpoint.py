"""
waqt.api.calendar_endpoint — GET /v1/calendar

A static-ish discovery endpoint: what calendar providers exist, what
each promises, and whether each supports reverse (Hijri -> Gregorian)
conversion via /v1/conversions. Exists so a client can build a
provider picker without hardcoding the list from documentation.
"""

from __future__ import annotations

from fastapi import APIRouter

from .common import success
from .providers import PROVIDER_CATALOG

router = APIRouter()


@router.get("/v1/calendar")
def get_calendar_providers():
    data = {
        "providers": [
            {
                "name": name,
                "description": entry["description"],
                "requires_override": entry["requires_override"],
                "supports_reverse_conversion": entry["supports_reverse"],
                # Sprint 14 (additive): does answering need the outside world, and may it be
                # used where one request resolves many dates (schedule / institutional)?
                "network": entry.get("network", False),
                "single_date_only": entry.get("single_date_only", False),
            }
            for name, entry in PROVIDER_CATALOG.items()
        ]
    }
    return success(data)

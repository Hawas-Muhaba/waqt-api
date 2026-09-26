from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from waqt.api import app  # noqa: E402


@pytest.fixture
def asgi_transport():
    """An in-process ASGI transport over the real FastAPI app -- no
    socket, no subprocess, but a genuine HTTP request/response cycle
    through Starlette's routing, dependency injection, and exception
    handlers. Async-only (httpx.ASGITransport requirement)."""
    return httpx.ASGITransport(app=app)

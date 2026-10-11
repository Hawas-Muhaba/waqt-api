"""Versioned vector-migration mechanism (API 1.6.0 -> 1.7.0: default Hijri provider).

Historical recorded responses in sdks/vectors/sdk_conformance_vectors.json are IMMUTABLE evidence. Eleven of them
were recorded with the provider OMITTED, i.e. under the old default (arithmetic-tabular). They are not rewritten
and the additivity checker is not loosened. Instead a migration manifest declares, per vector id, the provider
those recordings were made under; verification replays exactly those requests with that provider made explicit.
A vector that is not listed in the manifest is still compared strictly against the live app's *current* behaviour.

The behaviour of the new default is pinned by a separate, newly recorded file named in the manifest
(`new_vector_file`), governed by the API version stated there.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIGRATION_PATH = ROOT / "verification" / "vector_migrations" / "api-1.6.0-to-1.7.0.json"


def load_migration(path: Path = MIGRATION_PATH) -> dict:
    m = json.loads(Path(path).read_text(encoding="utf-8"))
    m["_by_id"] = {e["id"]: e for e in m["entries"]}
    return m


def effective_params(vector: dict, migration: dict | None) -> dict | None:
    """Params to replay for a recorded vector. Listed vectors get the historical provider made explicit.
    Refuses (raises) if a listed vector already names a provider -- the manifest must describe omissions only."""
    params = dict(vector["request"].get("params") or {})
    if migration is None or vector["id"] not in migration["_by_id"]:
        return params or None
    if "calendar_provider" in params:
        raise ValueError(f"{vector['id']}: listed in the migration but already names a provider")
    params["calendar_provider"] = migration["replay_provider"]
    return params

"""
waqt_core.versioning -- the single source of truth for *which computation
produced a number*.

Sprint 11 changed the output times of `waqt_core.solar` by up to minutes
while the engine string (`waqt-noaa-low-precision`) stayed the same, so two
responses carrying identical `astronomy_engine` values could disagree. Sprint
12 closes that gap with an explicit **engine revision**:

    "computation": {
      "engine": "waqt-noaa-low-precision",
      "revision": "2",
      "accuracy_level": "B"
    }

`(engine, revision)` names a *behaviour*: the same inputs give the same
outputs (to the resolution of the public API, whole seconds) for every
release of every package that reports that pair. Everything that reports
computation identity -- `waqt.api`, `waqt_local`, the SDKs, the reference
applications, the conformance vectors -- takes it from here; nothing else
in the repository is allowed to spell the engine name or revision.

How the revision is kept honest
-------------------------------
A revision that a human must remember to bump is a revision that will be
forgotten. `engine_fingerprint()` runs the engine over a fixed probe grid
and hashes the result. `ENGINE_REVISIONS[current]["fingerprint"]` pins that
hash, and `core/tests/test_engine_revision.py` fails if the two differ. So:
change any output of `solar.py` / `timescale.py` and the test goes red until
you (1) bump `ENGINE_REVISION`, (2) add its entry below, (3) regenerate the
vectors, which are stamped with the revision they were generated under.

See docs/VERSIONING.md for the relationship among the five version axes.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from ._version import __version__ as CORE_VERSION

# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------

ENGINE_NAME = "waqt-noaa-low-precision"

#: Bumped whenever an output of the engine changes by more than the API's
#: 1-second presentation rounding could hide. A string, not a number:
#: revisions are labels to compare for equality, never to do arithmetic on.
ENGINE_REVISION = "2"

#: DECISION POINT, deliberately not changed in Sprint 12. The numeric
#: Level-A definition (sub-second-to-few-seconds vs a high-accuracy
#: ephemeris) appears to be met on the evidence gathered so far, but the
#: evidence is one VSOP87 reference plus a shared-series Level-B reference;
#: relabelling changes the public contract of every response. The criteria
#: for changing this value are written down in docs/ACCURACY-LEVEL-REVIEW.md
#: and asserted by core/tests/test_engine_revision.py, so it cannot move
#: silently.
ACCURACY_LEVEL = "B"

#: Revision history. `fingerprint` is only pinned for the *current* revision:
#: older behaviours are not reproducible from this source tree (r1 is
#: reachable only by checking out a Sprint <= 10 tag), and a fingerprint we
#: cannot recompute would be decoration, not evidence.
ENGINE_REVISIONS: dict = {
    "1": {
        "introduced": "Stage 1; DeltaT since Sprint 2",
        "core_versions": "pre-waqt-core (Sprints 1-10)",
        "summary": (
            "Original NOAA low-precision engine. Refinement epoch was 12 h off; "
            "declination/EoT were sampled at UT noon for transit and Asr; polar-threshold "
            "existence was decided from UT-noon declination. Up to ~7 min error at high "
            "latitude near an equinox (432 s vs Level A), ~20-48 s elsewhere."
        ),
        "fingerprint": None,
        "retroactive": True,
    },
    "2": {
        "introduced": "Sprint 11",
        "core_versions": "waqt-core 0.1.0 and later, until superseded",
        "summary": (
            "Sprint 11 corrections: refinement epoch, transit/Asr sampling instant, "
            "polar-threshold existence. Max |diff| vs Level A: 0.9-1.0 s (equator to "
            "mid-latitude), 3.6 s (high latitude)."
        ),
        "fingerprint": "6462a2646dd77dca6589076c8eda30e67045c45eed79bd2205ec90ed60b76c17",
        "retroactive": False,
    },
}

#: Version of the *content* of the portable conformance vectors (distinct from
#: each file's `vector_format_version`, which versions the JSON *schema*).
#: MAJOR: some expected value changed for an unchanged input (an engine
#: revision bump, or a semantic change). MINOR: cases added or replaced, with no
#: expected value changed for an input that is still present.
#: 1.0: first versioned set, generated at engine revision 2 (Sprint 12).
#: 1.1: Sprint 13 -- calendar_interop case "non-leap-century-1900" moved from
#:      Addis Ababa to London because its expected civil offset was a
#:      local-mean-time value that differs between tz database versions (i.e. it
#:      was not reproducible across environments). Engine revision unchanged (2).
VECTOR_SET_VERSION = "2.0"


def computation_identity() -> dict:
    """The reproducibility triple every computation-bearing response carries."""
    return {
        "engine": ENGINE_NAME,
        "revision": ENGINE_REVISION,
        "accuracy_level": ACCURACY_LEVEL,
    }


# ---------------------------------------------------------------------------
# Behavioural fingerprint
# ---------------------------------------------------------------------------

# Probe grid: chosen to touch every code path Sprint 11 had to fix (extreme
# longitudes, high latitude near an equinox, a polar-threshold day, elevation,
# both Asr conventions) rather than to be large. Changing this grid changes
# every fingerprint, so it is part of the pinned contract.
_PROBE_LOCATIONS = (
    (9.0192, 38.7525, 0.0),       # Addis Ababa
    (21.4225, 39.8262, 0.0),      # Makkah
    (-33.9249, 18.4241, 0.0),     # Cape Town
    (69.6492, 18.9553, 0.0),      # Tromso: high latitude
    (-54.8019, -68.3030, 0.0),    # Ushuaia: high latitude S
    (1.8721, -157.4278, 0.0),     # Kiritimati: extreme longitude
    (-18.1416, 178.4419, 0.0),    # Suva: extreme longitude, other side
    (9.0192, 38.7525, 2400.0),    # elevation path
)
_PROBE_DATES = (
    date(2026, 3, 20),
    date(2026, 6, 21),
    date(2026, 9, 19),
    date(2026, 12, 21),
)
_PROBE_PROFILES = (
    (18.0, 17.0, 1.0),
    (15.0, 15.0, 2.0),
)
_EVENTS = ("fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha")
_FINGERPRINT_RESOLUTION_MS = 10
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _ms_bucket(dt: Optional[datetime]) -> str:
    if dt is None:
        return "-"
    ms = (dt - _EPOCH) // timedelta(milliseconds=1)   # exact integer arithmetic, no float
    return str(ms // _FINGERPRINT_RESOLUTION_MS)


def engine_fingerprint() -> str:
    """SHA-256 over the engine's output on the fixed probe grid.

    Times are bucketed to 10 ms so a last-ulp difference between platform
    `libm`s cannot flip the hash; the smallest change that matters (any of
    Sprint 11's fixes moved outputs by whole seconds to minutes) is three
    orders of magnitude larger than the bucket.
    """
    from . import solar  # local import: keep `versioning` import-cheap

    h = hashlib.sha256()
    for lat, lon, elev in _PROBE_LOCATIONS:
        for d in _PROBE_DATES:
            for fajr, isha, asr in _PROBE_PROFILES:
                day = solar.compute_day_events(
                    d, lat, lon, elevation_m=elev,
                    fajr_angle_deg=fajr, isha_angle_deg=isha, asr_shadow_ratio=asr,
                )
                row = ",".join(_ms_bucket(getattr(day, e)) for e in _EVENTS)
                h.update(f"{lat}|{lon}|{elev}|{d.isoformat()}|{fajr}|{isha}|{asr}|{row}\n".encode())
    return h.hexdigest()


# ---------------------------------------------------------------------------
# The five axes, as one machine-readable document (GET /v1/version)
# ---------------------------------------------------------------------------

def version_report(
    *,
    api_version: Optional[str] = None,
    spec_version: Optional[str] = None,
    local_version: Optional[str] = None,
) -> dict:
    """All version axes in one place. Callers that know their own layer's
    version (the API, waqt-local) pass it in; `waqt-core` never imports them,
    so it cannot report a version it does not own."""
    return {
        "waqt_core_version": CORE_VERSION,
        "spec": spec_version,
        "api_version": api_version,
        "waqt_local_version": local_version,
        "computation": computation_identity(),
        "engine_revision_history": {
            rev: {k: v for k, v in info.items() if k != "fingerprint"}
            for rev, info in ENGINE_REVISIONS.items()
        },
        "conformance_vectors": {"vector_set_version": VECTOR_SET_VERSION,
                                "generated_at_engine_revision": ENGINE_REVISION},
        "notes": (
            "SDK versions are not reported here: a client's own version is not a property of "
            "the server. See docs/VERSIONING.md."
        ),
    }


__all__ = [
    "CORE_VERSION", "ENGINE_NAME", "ENGINE_REVISION", "ACCURACY_LEVEL",
    "ENGINE_REVISIONS", "VECTOR_SET_VERSION",
    "computation_identity", "engine_fingerprint", "version_report",
]

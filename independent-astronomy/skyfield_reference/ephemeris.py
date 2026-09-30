"""JPL DE421 as Skyfield vector functions.

The `de421` PyPI package ships JPL's DE421 in jplephem's legacy Chebyshev
format (not a NAIF .bsp; NAIF was not reachable when this was written).  The
numbers are JPL's; only the container differs.  Earth is derived from the
Earth-Moon barycentre and the geocentric Moon with the standard JPL relation
    r_earth = r_emb - r_moon / (1 + EMRAT)
"""
from __future__ import annotations
import numpy as np
from skyfield.vectorlib import VectorFunction

_KM_PER_AU = 149597870.700
_SEC_PER_DAY = 86400.0

_eph = None

def _ephemeris():
    global _eph
    if _eph is None:
        import de421
        from jplephem import Ephemeris
        _eph = Ephemeris(de421)
    return _eph

def _pv(name, tdb):
    p, v = _ephemeris().position_and_velocity(name, tdb)
    return p, v      # km, km/day (legacy jplephem Ephemeris convention)

class _Body(VectorFunction):
    center = 0                       # solar-system barycentre
    ephemeris = None                 # filled by load_bodies(): deflector lookup for .apparent()
    _NAMES = {10: "sun", 5: "jupiter", 6: "saturn"}   # NAIF barycentre codes -> DE421 names
    def __init__(self, target, vector_name):
        self.target = target
        self.vector_name = vector_name
    def _at(self, t):
        tdb = t.tdb
        if self.target in self._NAMES:
            p, v = _pv(self._NAMES[self.target], tdb)
        else:  # 399 Earth
            pe, ve = _pv("earthmoon", tdb)
            pm, vm = _pv("moon", tdb)
            k = 1.0 / (1.0 + float(_ephemeris().EMRAT))
            p, v = pe - pm * k, ve - vm * k
        return p / _KM_PER_AU, v / _KM_PER_AU, None, None   # legacy jplephem: km and km/DAY -> AU, AU/day

class _Lookup(dict):
    pass

def load_bodies():
    """(earth, sun) Skyfield vector functions backed by JPL DE421."""
    lookup = _Lookup({c: _Body(c, f"DE421 {n}") for c, n in _Body._NAMES.items()})
    lookup[399] = _Body(399, "DE421 Earth")
    _Body.ephemeris = lookup
    return lookup[399], lookup[10]

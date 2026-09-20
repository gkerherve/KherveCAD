"""Stones (Qt-free): pebbles, cobbles, flat skipping stones, broken
rocks, boulders, standing stones, flagstones, scatters and cairns, as
closed polyhedra at true size in mm.

One generator makes all of them. A stone is a subdivided octahedron
whose every vertex direction *u* is pushed out to a radius r(u):

    r(u) = ( r_ellipsoid^-p + sum_i (d_i / u.n_i)^-p )^(-1/p)

— the ellipsoid of the stone's three semi-axes joined, by a smooth
minimum of power *p*, to a few random **cutting planes** (n_i, d_i):
a low *p* gives round river pebbles, a high one sharp fractured facets
with real edges. A few sine ripples of the direction then roughen the
surface (two octaves for a weathered boulder). Every vertex keeps its
direction, so the surface is star-shaped and stays a closed 2-manifold
(no welding trouble); a flat base is a clamp of z, so a stone SITS on
z = 0 instead of balancing on a point.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math
import random

from .treegen import Mesh

#: kind -> shape recipe. axes: relative semi-axes (x, y, z) with a
#: random spread; planes: (count, distance range as a fraction of the
#: longest semi-axis); p: smooth-min power (low = round, high = sharp);
#: rough: (amplitude, ripples); base: flat-base depth (fraction of the
#: z semi-axis kept below the centre, 1 = none); level: subdivisions.
KINDS = {
    "pebble": dict(label="Pebble (smooth)", axes=(1.0, 0.72, 0.5),
                   spread=0.16, planes=(2, 0.82, 0.95), p=5, rough=(0.03, 3),
                   base=0.55, level=3),
    "cobble": dict(label="River cobble", axes=(1.0, 0.8, 0.55), spread=0.18,
                   planes=(3, 0.78, 0.95), p=6, rough=(0.045, 4),
                   base=0.6, level=3),
    "skipping": dict(label="Flat skipping stone", axes=(1.0, 0.85, 0.13),
                     spread=0.1, planes=(2, 0.85, 0.98), p=7,
                     rough=(0.02, 3), base=1.0, level=3),
    "angular": dict(label="Broken rock (angular)", axes=(1.0, 0.8, 0.65),
                    spread=0.2, planes=(10, 0.6, 0.86), p=16,
                    rough=(0.05, 5), base=0.7, level=3),
    "boulder": dict(label="Boulder (weathered)", axes=(1.0, 0.86, 0.7),
                    spread=0.16, planes=(5, 0.7, 0.92), p=5, rough=(0.08, 6),
                    base=0.65, level=4),
    "menhir": dict(label="Standing stone", axes=(0.3, 0.2, 1.0), spread=0.1,
                   planes=(6, 0.55, 0.85), p=9, rough=(0.05, 5), base=0.9,
                   level=3, taper=0.35),
    "flagstone": dict(label="Flagstone (paving slab)",
                      axes=(1.0, 0.85, 0.09), spread=0.08,
                      planes=(4, 0.8, 0.95), p=22, rough=(0.012, 4),
                      base=1.0, level=3),
}

#: colour name -> stone colour; "River mix" varies per stone
COLOURS = {
    "Granite grey": "#8b8a86", "Sandstone": "#c8a97c",
    "Limestone": "#d6cfc0", "Basalt": "#4a4a4c", "Slate": "#5d6470",
    "Marble": "#e9e6e0", "Red sandstone": "#a5654a", "Mossy green": "#6f7a5a",
    "River mix": "#8b8a86",
}
RIVER_MIX = ("#8b8a86", "#a29c90", "#6c6a67", "#b5a58a", "#7d766c",
             "#c9c0af", "#5f5c58", "#9a8f7d")


# -------------------------------------------------------------- vectors
def _unit(v):
    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1.0
    return (v[0] / n, v[1] / n, v[2] / n)


def _sphere(level):
    """Points and triangles (counter-clockwise seen from outside) of an
    octahedron subdivided *level* times, projected onto the unit
    sphere."""
    verts = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1),
             (0, 0, -1)]
    faces = [(0, 2, 4), (2, 1, 4), (1, 3, 4), (3, 0, 4),
             (2, 0, 5), (1, 2, 5), (3, 1, 5), (0, 3, 5)]
    verts = [tuple(map(float, v)) for v in verts]
    for _ in range(level):
        mids, out = {}, []

        def mid(a, b):
            key = (min(a, b), max(a, b))
            if key not in mids:
                mids[key] = len(verts)
                verts.append(_unit(tuple((verts[a][i] + verts[b][i]) / 2
                                         for i in range(3))))
            return mids[key]
        for a, b, c in faces:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            out += [(a, ab, ca), (ab, b, bc), (ca, bc, c), (ab, bc, ca)]
        faces = out
    return verts, faces


_SPHERES: dict = {}


def sphere(level):
    if level not in _SPHERES:
        _SPHERES[level] = _sphere(level)
    return _SPHERES[level]


# ---------------------------------------------------------------- stone
def stone(mesh: Mesh, rng: random.Random, kind: str, size: float,
          centre=(0.0, 0.0, 0.0), yaw=None, level=None, lift=True):
    """Add one closed stone of *kind* to *mesh*, its longest dimension
    about *size* mm, standing on z = centre z (its base). Returns its
    height, mm."""
    rec = KINDS[kind]
    half = size / 2.0
    sp = rec["spread"]
    ax = [half * a * (1 + rng.uniform(-sp, sp)) for a in rec["axes"]]
    count, dmin, dmax = rec["planes"]
    big = max(ax)
    planes = []
    for _ in range(count):
        n = _unit((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1)))
        if kind in ("skipping", "flagstone"):      # cut the rim, not faces
            n = _unit((n[0], n[1], n[2] * 0.15))
        planes.append((n, big * rng.uniform(dmin, dmax) *
                       (0.6 if kind in ("skipping", "flagstone") else 1.0)))
    p = float(rec["p"])
    amp, waves = rec["rough"]
    lv = level if level is not None else rec["level"]
    # ripples finer than the mesh has points for would only alias
    fmax = {0: 1.5, 1: 2.0, 2: 3.0, 3: 4.5, 4: 6.5}.get(lv, 6.5)
    ripples = [(_unit((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1))),
                min(rng.uniform(1.0, 2.2) * (1 + k * 0.55), fmax),
                rng.uniform(0, 2 * math.pi), amp / (1 + k * 0.7))
               for k in range(waves)]
    verts, tris = sphere(lv)
    if yaw is None:
        yaw = rng.uniform(0, 2 * math.pi)
    cy, sy = math.cos(yaw), math.sin(yaw)
    taper = rec.get("taper", 0.0)
    keep = rec["base"]
    pts = []
    for u in verts:
        ell = 1.0 / math.sqrt((u[0] / ax[0]) ** 2 + (u[1] / ax[1]) ** 2
                              + (u[2] / ax[2]) ** 2)
        acc = ell ** -p
        for n, d in planes:
            dot = u[0] * n[0] + u[1] * n[1] + u[2] * n[2]
            if dot > 0.02:
                acc += (d / dot) ** -p
        r = acc ** (-1.0 / p)
        wob = 0.0
        for w, f, ph, a in ripples:
            wob += a * math.sin(f * (u[0] * w[0] + u[1] * w[1]
                                     + u[2] * w[2]) * math.pi + ph)
        r *= 1.0 + wob
        x, y, z = u[0] * r, u[1] * r, u[2] * r
        if taper:                            # a menhir narrows towards the top
            k = 1.0 - taper * max(0.0, (z + ax[2]) / (2 * ax[2]))
            x, y = x * k, y * k
        pts.append((x, y, z))
    floor = -ax[2] * keep
    pts = [(x, y, max(z, floor)) for x, y, z in pts]
    low = min(p_[2] for p_ in pts) if lift else 0.0
    top = max(p_[2] for p_ in pts)
    out = [(centre[0] + x * cy - y * sy, centre[1] + x * sy + y * cy,
            centre[2] + z - low) for x, y, z in pts]
    mesh.piece(out, tris)
    return top - low


# ------------------------------------------------------------ scatters
def scatter(mesh_for, rng, count, area, sizes, kinds, avoid=0.9, level=None):
    """*count* stones dropped over a disc of diameter *area* mm without
    overlapping (rejection sampling on their footprints, drawn at
    subdivision *level* — small stones need few triangles), each of a
    random kind from *kinds* and a size from *sizes* (min, max), the
    small ones far commoner than the large. *mesh_for(i)* gives the
    Mesh stone *i* goes into. Returns how many were placed."""
    placed = []
    lo, hi = sizes
    for i in range(count):
        for _try in range(40):
            size = lo * (hi / lo) ** (rng.random() ** 2.2)
            rad = size * 0.5
            a = rng.uniform(0, 2 * math.pi)
            d = (area / 2 - rad) * math.sqrt(rng.random())
            if d < 0:
                continue
            x, y = d * math.cos(a), d * math.sin(a)
            if all((x - qx) ** 2 + (y - qy) ** 2 >=
                   ((rad + qr) * avoid) ** 2 for qx, qy, qr in placed):
                placed.append((x, y, rad))
                stone(mesh_for(i), rng, rng.choice(kinds), size, (x, y, 0.0),
                      level=level)
                break
    return len(placed)


def cairn(mesh, rng, size, n):
    """A balanced stack of *n* stones, the biggest below, each a little
    off-centre of the one under it."""
    z = 0.0
    x = y = 0.0
    for i in range(n):
        s = size * (1.0 - 0.6 * i / max(n, 1))
        h = stone(mesh, rng, "cobble" if i else "boulder", s, (x, y, z))
        z += h * 0.86                       # sunk in a little: they touch
        x += rng.uniform(-0.06, 0.06) * s
        y += rng.uniform(-0.06, 0.06) * s
    return z

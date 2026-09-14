"""A hair cap: a thick, curly skin grown over part of a surface.

Spheres are not hair. A cap takes the faces of its children that lie
in a region (a box, and not the ones looking towards the face), lifts
a copy of them outward by a thickness plus a smooth seeded bumpiness
— the lumps read as curls or waves at the chosen size — and closes
the copy back onto the original along the rim, so the result is one
closed solid that hugs the head. It is a shell turned outward, with
the noise doing what a wig does.

Pure geometry, Qt-free; bake.py bakes the ``hair_cap`` node like the
other computed meshes.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

CLEAR_CHOICES = ("none", "-y", "+y", "-x", "+x", "+z", "-z")
_DIRS = {"-y": (0, -1, 0), "+y": (0, 1, 0), "-x": (-1, 0, 0),
         "+x": (1, 0, 0), "+z": (0, 0, 1), "-z": (0, 0, -1)}


def _key(v):
    return (round(v[0], 5), round(v[1], 5), round(v[2], 5))


def _normal(tri):
    a, b, c = tri
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    n = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
    length = math.sqrt(n[0] * n[0] + n[1] * n[1] + n[2] * n[2])
    return (n[0] / length, n[1] / length, n[2] / length) \
        if length > 1e-15 else (0.0, 0.0, 0.0), length


def bumps(p, size: float, seed: int) -> float:
    """A smooth pseudo-random field in [-1, 1] with lumps about
    *size* across: a few sine waves in seeded directions."""
    if size <= 0:
        return 0.0
    k = 2.0 * math.pi / size
    total = 0.0
    for i in range(4):
        s = (seed * 7919 + i * 104729) % 360
        a, b = math.radians(s * 1.7), math.radians(s * 2.3 + 40)
        d = (math.cos(a) * math.cos(b), math.sin(a) * math.cos(b),
             math.sin(b))
        phase = (seed * 31 + i * 17) % 7
        total += math.sin(k * (p[0] * d[0] + p[1] * d[1] + p[2] * d[2])
                          * (1.0 + 0.3 * i) + phase)
    return total / 4.0


def select(tris, within=None, clear="none", clear_angle=60.0) -> list:
    """The faces a cap grows on: centre inside the *within* box
    (``[[x0, y0, z0], [x1, y1, z1]]``, or everything), not looking
    within *clear_angle* of the *clear* direction (the face, say)."""
    lo = hi = None
    if within and len(within) == 2 and all(len(r) == 3 for r in within):
        lo = [min(within[0][i], within[1][i]) for i in range(3)]
        hi = [max(within[0][i], within[1][i]) for i in range(3)]
    direction = _DIRS.get(clear)
    cos_clear = math.cos(math.radians(clear_angle))
    keep = []
    for tri in tris:
        if lo is not None:
            c = [(tri[0][i] + tri[1][i] + tri[2][i]) / 3.0 for i in range(3)]
            if any(c[i] < lo[i] or c[i] > hi[i] for i in range(3)):
                keep.append(False)
                continue
        if direction is not None:
            n, _l = _normal(tri)
            if n[0] * direction[0] + n[1] * direction[1] \
                    + n[2] * direction[2] > cos_clear:
                keep.append(False)
                continue
        keep.append(True)
    return keep


def cap(tris, thickness: float, noise: float = 0.0, curl: float = 25.0,
        seed: int = 1, within=None, clear="none",
        clear_angle: float = 60.0) -> list:
    """Counter-clockwise triangles of the closed cap over the selected
    faces of *tris*: an outer skin lifted by *thickness* plus *noise*
    times the bump field, the original faces as the inside, and a rim
    joining them."""
    if not tris or thickness <= 0:
        return []
    keep = select(tris, within, clear, clear_angle)
    kept = [tri for tri, k in zip(tris, keep) if k]
    if not kept:
        return []
    # vertex normals over the kept faces (area weighted)
    acc = {}
    for tri in kept:
        n, area = _normal(tri)
        for v in tri:
            a = acc.setdefault(_key(v), [0.0, 0.0, 0.0])
            a[0] += n[0] * area
            a[1] += n[1] * area
            a[2] += n[2] * area
    lifted = {}
    for k, n in acc.items():
        length = math.sqrt(n[0] * n[0] + n[1] * n[1] + n[2] * n[2])
        n = (n[0] / length, n[1] / length, n[2] / length) \
            if length > 1e-15 else (0.0, 0.0, 1.0)
        h = thickness + noise * bumps(k, curl, seed)
        h = max(h, 0.15 * thickness)          # never back through the head
        lifted[k] = (k[0] + n[0] * h, k[1] + n[1] * h, k[2] + n[2] * h)
    dropped_edges = set()
    for tri, k in zip(tris, keep):
        if k:
            continue
        keys = [_key(v) for v in tri]
        for j in range(3):
            dropped_edges.add((keys[j], keys[(j + 1) % 3]))
    kept_edges = set()
    for tri in kept:
        keys = [_key(v) for v in tri]
        for j in range(3):
            kept_edges.add((keys[j], keys[(j + 1) % 3]))
    out = []
    for tri in kept:
        # the rounded keys ARE the vertices from here on: neighbouring
        # faces of a tessellation can differ at the 1e-16 level, and a
        # closed cap needs its shared edges to match exactly
        keys = [_key(v) for v in tri]
        outer = tuple(lifted[k] for k in keys)
        out.append(outer)                                   # outward
        out.append((keys[2], keys[1], keys[0]))             # inside, reversed
        for k in range(3):
            a, b = keys[k], keys[(k + 1) % 3]
            ka, kb = a, b
            # a rim edge: the neighbour across it is not part of the cap
            if (kb, ka) not in kept_edges:
                a2, b2 = lifted[ka], lifted[kb]
                out.append((a, b, b2))
                out.append((a, b2, a2))
    return out

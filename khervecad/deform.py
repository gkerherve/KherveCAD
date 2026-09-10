"""Deformers and subdivision for the built-in mesh: bend, twist, taper,
lattice (free-form deformation) and Loop subdivision.

A curved limb, a twisted horn, a tapered finger, a squashed head: with
CSG each needs its own construction. A deformer takes whatever is
inside it and bends the *surface* — the way Blender's modifiers do —
so the parts are modelled straight and deformed afterwards.

A cube has twelve triangles; bending it needs many more. Every
deformer therefore first splits the long edges (`split_long_edges`),
deciding per EDGE, so the two triangles sharing an edge always split
it alike: no T-junctions, and the surface stays closed through the
deformation.

Pure geometry, Qt-free; bake.py turns the results into nodes.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

AXES = {"x": 0, "y": 1, "z": 2}

#: stop splitting edges past this many triangles
SPLIT_LIMIT = 250_000


def _extent(tris, axis):
    values = [v[axis] for tri in tris for v in tri]
    return min(values), max(values)


def _others(axis):
    """The other two axes, in right-handed order after *axis*."""
    return (axis + 1) % 3, (axis + 2) % 3


def _map(tris, f):
    """Apply f to every vertex once (shared vertices stay shared)."""
    done = {}
    out = []
    for tri in tris:
        mapped = []
        for v in tri:
            p = done.get(v)
            if p is None:
                p = done[v] = f(v)
            mapped.append(p)
        out.append(tuple(mapped))
    return out


# ---------------------------------------------------------- refinement

def split_long_edges(tris, max_len: float, passes: int = 12) -> list:
    """Split every edge longer than *max_len* at its midpoint until none
    is left (or SPLIT_LIMIT is reached). The decision belongs to the
    edge, so both of its triangles make it: the surface stays closed."""
    tris = [tuple(t) for t in tris]
    if max_len <= 0:
        return tris
    m2 = max_len * max_len

    def long(a, b):
        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2
                + (a[2] - b[2]) ** 2) > m2
    for _ in range(passes):
        mids = {}

        def mid(a, b):
            key = (a, b) if a <= b else (b, a)
            p = mids.get(key)
            if p is None:
                p = mids[key] = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2,
                                 (a[2] + b[2]) / 2)
            return p
        out = []
        changed = False
        for a, b, c in tris:
            la, lb, lc = long(a, b), long(b, c), long(c, a)
            count = la + lb + lc
            if count == 0:
                out.append((a, b, c))
                continue
            changed = True
            if count == 3:
                ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
                out += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
            elif count == 1:                  # turn the long edge to ab
                if lb:
                    a, b, c = b, c, a
                elif lc:
                    a, b, c = c, a, b
                ab = mid(a, b)
                out += [(a, ab, c), (ab, b, c)]
            else:                             # turn the short edge to ca
                if not la:
                    a, b, c = b, c, a
                elif not lb:
                    a, b, c = c, a, b
                ab, bc = mid(a, b), mid(b, c)
                out += [(b, bc, ab), (a, ab, bc), (a, bc, c)]
        tris = out
        if not changed or len(tris) > SPLIT_LIMIT:
            break
    return tris


# ----------------------------------------------------------- deformers

def bend(tris, axis: str, toward: str, angle: float) -> list:
    """Curl the mesh's *axis* extent into an arc of *angle* degrees,
    bending toward +*toward*. The base (lowest along *axis*) stays put
    and the mid-line keeps its length (Blender's simple-deform bend)."""
    ia, it = AXES[axis], AXES[toward]
    if ia == it or not tris:
        return list(tris)
    lo, hi = _extent(tris, ia)
    length = hi - lo
    theta = math.radians(angle)
    if length <= 0 or abs(theta) < 1e-9:
        return list(tris)
    tlo, thi = _extent(tris, it)
    centre = (tlo + thi) / 2
    radius = length / theta

    def f(v):
        s, u = v[ia] - lo, v[it] - centre
        phi = s / radius
        p = list(v)
        p[ia] = lo + (radius - u) * math.sin(phi)
        p[it] = centre + radius - (radius - u) * math.cos(phi)
        return tuple(p)
    return _map(tris, f)


def twist(tris, axis: str, angle: float) -> list:
    """Rotate each slice about the mesh's central *axis* line, from 0 at
    the base to *angle* degrees at the far end."""
    ia = AXES[axis]
    if not tris:
        return []
    lo, hi = _extent(tris, ia)
    length = hi - lo
    if length <= 0 or abs(angle) < 1e-12:
        return list(tris)
    i1, i2 = _others(ia)
    m1 = sum(_extent(tris, i1)) / 2
    m2 = sum(_extent(tris, i2)) / 2
    total = math.radians(angle)

    def f(v):
        a = total * (v[ia] - lo) / length
        c1, c2 = v[i1] - m1, v[i2] - m2
        p = list(v)
        p[i1] = m1 + c1 * math.cos(a) - c2 * math.sin(a)
        p[i2] = m2 + c1 * math.sin(a) + c2 * math.cos(a)
        return tuple(p)
    return _map(tris, f)


def taper(tris, axis: str, factor: float) -> list:
    """Scale each slice about the central *axis* line, from 1 at the
    base to *factor* at the far end."""
    ia = AXES[axis]
    if not tris:
        return []
    lo, hi = _extent(tris, ia)
    length = hi - lo
    if length <= 0:
        return list(tris)
    i1, i2 = _others(ia)
    m1 = sum(_extent(tris, i1)) / 2
    m2 = sum(_extent(tris, i2)) / 2

    def f(v):
        k = 1.0 + (factor - 1.0) * (v[ia] - lo) / length
        p = list(v)
        p[i1] = m1 + (v[i1] - m1) * k
        p[i2] = m2 + (v[i2] - m2) * k
        return tuple(p)
    return _map(tris, f)


#: lattice corners, in the order the offsets are given
LATTICE_CORNERS = [(i, j, k) for k in (0, 1) for j in (0, 1) for i in (0, 1)]


def lattice(tris, offsets) -> list:
    """Free-form deformation: move the 8 corners of the mesh's bounding
    box by *offsets* ([dx, dy, dz] each, x fastest, then y, then z) and
    carry every point along by trilinear interpolation."""
    if not tris:
        return []
    lo = [_extent(tris, a)[0] for a in range(3)]
    hi = [_extent(tris, a)[1] for a in range(3)]
    span = [hi[a] - lo[a] for a in range(3)]
    offs = [tuple(float(v) for v in row) for row in offsets]

    def f(v):
        t = [(v[a] - lo[a]) / span[a] if span[a] > 0 else 0.0
             for a in range(3)]
        d = [0.0, 0.0, 0.0]
        for (i, j, k), off in zip(LATTICE_CORNERS, offs):
            w = ((t[0] if i else 1 - t[0]) * (t[1] if j else 1 - t[1])
                 * (t[2] if k else 1 - t[2]))
            for a in range(3):
                d[a] += w * off[a]
        return (v[0] + d[0], v[1] + d[1], v[2] + d[2])
    return _map(tris, f)


# -------------------------------------------------------- subdivision

def _loop_once(tris) -> list:
    index, verts, faces = {}, [], []
    for tri in tris:
        face = []
        for v in tri:
            key = (round(v[0], 9), round(v[1], 9), round(v[2], 9))
            i = index.get(key)
            if i is None:
                i = index[key] = len(verts)
                verts.append(v)
            face.append(i)
        if len(set(face)) == 3:
            faces.append(face)
    opposite = {}
    neighbours = [set() for _ in verts]
    for a, b, c in faces:
        for u, w, o in ((a, b, c), (b, c, a), (c, a, b)):
            opposite.setdefault((u, w) if u < w else (w, u), []).append(o)
            neighbours[u].add(w)
            neighbours[w].add(u)
    rim = [[] for _ in verts]
    for (u, w), others in opposite.items():
        if len(others) == 1:
            rim[u].append(w)
            rim[w].append(u)
    moved = []
    for i, v in enumerate(verts):
        if rim[i]:                           # boundary: follow the rim
            if len(rim[i]) == 2:
                a, b = verts[rim[i][0]], verts[rim[i][1]]
                moved.append(tuple(0.75 * v[k] + 0.125 * (a[k] + b[k])
                                   for k in range(3)))
            else:
                moved.append(v)
            continue
        n = len(neighbours[i])
        if n < 3:
            moved.append(v)
            continue
        beta = (5 / 8 - (3 / 8 + 0.25 * math.cos(2 * math.pi / n)) ** 2) / n
        total = [sum(verts[j][k] for j in neighbours[i]) for k in range(3)]
        moved.append(tuple((1 - n * beta) * v[k] + beta * total[k]
                           for k in range(3)))
    edge_point = {}
    for (u, w), others in opposite.items():
        a, b = verts[u], verts[w]
        if len(others) == 2:
            c, d = verts[others[0]], verts[others[1]]
            edge_point[(u, w)] = tuple(0.375 * (a[k] + b[k])
                                       + 0.125 * (c[k] + d[k])
                                       for k in range(3))
        else:
            edge_point[(u, w)] = tuple((a[k] + b[k]) / 2 for k in range(3))

    def e(u, w):
        return edge_point[(u, w) if u < w else (w, u)]
    out = []
    for a, b, c in faces:
        ab, bc, ca = e(a, b), e(b, c), e(c, a)
        pa, pb, pc = moved[a], moved[b], moved[c]
        out += [(pa, ab, ca), (pb, bc, ab), (pc, ca, bc), (ab, bc, ca)]
    return out


def loop_subdivide(tris, levels: int) -> list:
    """Loop subdivision, *levels* times: each triangle becomes four and
    the surface relaxes toward a smooth limit — a coarse cage becomes
    an organic form. Winding is preserved."""
    for _ in range(max(int(levels), 0)):
        tris = _loop_once(tris)
    return tris

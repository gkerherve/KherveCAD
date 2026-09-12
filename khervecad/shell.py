"""Shell / hollow — Blender's Solidify, for printing (Qt-free).

"Make this part a hollow shell N mm thick." Every vertex of the part's
mesh is moved inward along its area-weighted vertex normal by the
wall thickness — with Solidify's even-thickness correction, so a wall
meeting at a corner keeps its thickness instead of thinning — and the
offset copy, faces reversed, becomes the inner surface. Optionally one
side is left open (a cup, a box lid, a case): the faces looking that
way are dropped from both surfaces and the two rims are bridged, so
the result is always one closed, outward solid.

The offset moves each vertex once, so it is exact for planar walls
and fair on curved ones; a wall thicker than the part's smallest
dimension would fold the inner surface through itself and is refused
by validation before it gets here.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

OPEN_CHOICES = ("none", "top", "bottom", "+x", "-x", "+y", "-y")

_DIRECTIONS = {
    "top": (0.0, 0.0, 1.0), "bottom": (0.0, 0.0, -1.0),
    "+x": (1.0, 0.0, 0.0), "-x": (-1.0, 0.0, 0.0),
    "+y": (0.0, 1.0, 0.0), "-y": (0.0, -1.0, 0.0),
}

#: the even-thickness correction is capped here: at a very sharp
#: corner 1/cos would send the vertex far away
MAX_STRETCH = 3.0


def _key(v):
    return (round(v[0], 5), round(v[1], 5), round(v[2], 5))


def _normal_area(tri):
    a, b, c = tri
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length < 1e-15:
        return (0.0, 0.0, 0.0), 0.0
    return (nx / length, ny / length, nz / length), length / 2.0


def _corner_angle(a, b, c) -> float:
    """The angle at *a* of triangle (a, b, c), radians."""
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    lu = math.sqrt(ux * ux + uy * uy + uz * uz)
    lv = math.sqrt(vx * vx + vy * vy + vz * vz)
    if lu < 1e-15 or lv < 1e-15:
        return 0.0
    cos = (ux * vx + uy * vy + uz * vz) / (lu * lv)
    return math.acos(max(-1.0, min(1.0, cos)))


def volume(tris) -> float:
    total = 0.0
    for a, b, c in tris:
        total += (a[0] * (b[1] * c[2] - b[2] * c[1])
                  - a[1] * (b[0] * c[2] - b[2] * c[0])
                  + a[2] * (b[0] * c[1] - b[1] * c[0]))
    return total / 6.0


def smallest_extent(tris) -> float:
    if not tris:
        return 0.0
    pts = [v for t in tris for v in t]
    return min(max(p[i] for p in pts) - min(p[i] for p in pts)
               for i in range(3))


def inner_surface(tris, thickness: float) -> list:
    """The offset copy of *tris*: vertices moved inward by *thickness*
    along their vertex normals (even-thickness corrected), faces
    reversed so they face into the cavity. Same order as *tris*."""
    faces = []
    by_vertex = {}                 # key -> [(face index, corner angle)]
    for i, tri in enumerate(tris):
        n, area = _normal_area(tri)
        faces.append((n, area))
        for k in range(3):
            a, b, c = tri[k], tri[(k + 1) % 3], tri[(k + 2) % 3]
            by_vertex.setdefault(_key(a), []).append(
                (i, _corner_angle(a, b, c)))
    moved = {}
    for key, owners in by_vertex.items():
        # weight each face's normal by its angle at the vertex: unlike
        # area weighting it does not depend on how the faces were
        # triangulated, so a box corner's normal is its diagonal
        sx = sy = sz = 0.0
        for i, angle in owners:
            n, _area = faces[i]
            sx += n[0] * angle
            sy += n[1] * angle
            sz += n[2] * angle
        length = math.sqrt(sx * sx + sy * sy + sz * sz)
        if length < 1e-15:
            moved[key] = key
            continue
        vn = (sx / length, sy / length, sz / length)
        # even thickness: the wall under each face must be `thickness`
        # thick, so the vertex moves 1/cos further along its normal
        stretch = 1.0
        for i, _angle in owners:
            n, area = faces[i]
            if area <= 0:
                continue
            cos = vn[0] * n[0] + vn[1] * n[1] + vn[2] * n[2]
            if cos > 1e-6:
                stretch = max(stretch, min(1.0 / cos, MAX_STRETCH))
        d = thickness * stretch
        moved[key] = (key[0] - vn[0] * d, key[1] - vn[1] * d,
                      key[2] - vn[2] * d)
    return [(moved[_key(c)], moved[_key(b)], moved[_key(a)])
            for a, b, c in tris]


def shell(tris, thickness: float, open: str = "none",
          open_angle: float = 30.0) -> list:
    """Counter-clockwise triangles of the hollow shell. Empty for an
    empty mesh; the solid itself when the wall would fold (no room)."""
    if not tris or thickness <= 0:
        return list(tris)
    direction = _DIRECTIONS.get(open)
    cos_open = math.cos(math.radians(open_angle))
    keep = []
    for tri in tris:
        n, _area = _normal_area(tri)
        keep.append(direction is None or
                    n[0] * direction[0] + n[1] * direction[1]
                    + n[2] * direction[2] < cos_open)
    if all(keep):
        inner = inner_surface(tris, thickness)
        cavity = -volume(inner)              # its faces point inward
        if cavity <= 1e-9 * max(volume(tris), 1.0) \
                or cavity >= volume(tris):
            return list(tris)                # folded: no cavity to make
        return list(tris) + inner
    if not any(keep):
        return list(tris)
    # the open faces go BEFORE the offset: a rim vertex then has no
    # face looking out of the opening, moves only sideways, and the
    # rim stays flat in the opening's plane at full wall thickness
    kept = [tri for tri, k in zip(tris, keep) if k]
    inner = inner_surface(kept, thickness)
    # rim: every edge a kept outer face shares with a dropped one, as
    # the kept face traverses it (a -> b); the rim quad runs b, a,
    # a', b' so each edge is traversed once each way and the surface
    # stays closed
    dropped_edges = set()
    for tri, k in zip(tris, keep):
        if k:
            continue
        keys = [_key(v) for v in tri]
        for j in range(3):
            dropped_edges.add((keys[j], keys[(j + 1) % 3]))
    out = []
    for i, tri in enumerate(kept):
        out.append(tri)
        out.append(inner[i])
        keys = [_key(v) for v in tri]
        inner_tri = inner[i]                 # (c', b', a') for (a, b, c)
        inner_of = {keys[0]: inner_tri[2], keys[1]: inner_tri[1],
                    keys[2]: inner_tri[0]}
        for k in range(3):
            a, b = tri[k], tri[(k + 1) % 3]
            ka, kb = keys[k], keys[(k + 1) % 3]
            if (kb, ka) in dropped_edges:    # the neighbour was dropped
                a2, b2 = inner_of[ka], inner_of[kb]
                out.append((b, a, a2))
                out.append((b, a2, b2))
    return out

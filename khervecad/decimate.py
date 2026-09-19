"""Decimate — fewer triangles, same shape (Blender's Decimate ▸ Collapse).

Two ways to ask, like Blender's modifier and a CAD tolerance:

* ``ratio`` — keep this fraction of the triangles (0.25 = a quarter);
* ``tolerance`` — mm: collapse whatever moves the surface less than this.

The reduction is **quadric edge collapse** (Garland & Heckbert 1997, the
algorithm behind Blender's ``BM_mesh_decimate_collapse``): every vertex
carries the sum of the squared-distance quadrics of the planes around it,
the edge whose collapse costs least goes first and its two ends merge at
the point that minimises their summed quadric. Two checks keep a closed
solid closed and printable — the **link condition** (the ends may share
only the two vertices opposite the edge, or the collapse pinches the
surface) and **no fold** (no face around the merged vertex may turn over).
Open borders are never collapsed, so an open scan keeps its outline.

With Manifold installed (csg.py) its ``simplify`` takes a big mesh
(`PREPASS_ABOVE`) the first steps — C++, milliseconds, but it keeps
volume less well — down to three times the target, and the Python
collapse finishes; a tolerance request is Manifold's alone. Qt-free.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import heapq
import math

#: the fewest triangles a closed solid can come down to (a tetrahedron)
MIN_TRIS = 4
#: a face around a collapse may not turn by more than this (cos)
FOLD_COS = 0.2
#: past this many triangles Manifold's simplify (C++) takes the first
#: steps — the Python collapse runs ~30k triangles a second
PREPASS_ABOVE = 20000
#: positions closer than this are one vertex when welding
_DIGITS = 6


def weld(tris):
    """(points, faces) from triangles, coincident corners shared."""
    index, points, faces = {}, [], []
    for tri in tris:
        ids = []
        for v in tri:
            key = (round(v[0], _DIGITS), round(v[1], _DIGITS),
                   round(v[2], _DIGITS))
            i = index.get(key)
            if i is None:
                i = index[key] = len(points)
                points.append((float(v[0]), float(v[1]), float(v[2])))
            ids.append(i)
        if len(set(ids)) == 3:
            faces.append(ids)
    return points, faces


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _normal(p, q, r):
    n = _cross(_sub(q, p), _sub(r, p))
    length = math.sqrt(n[0] * n[0] + n[1] * n[1] + n[2] * n[2])
    if length < 1e-18:
        return None
    return (n[0] / length, n[1] / length, n[2] / length)


def _plane_quadric(p, q, r):
    """The 10 unique entries of the plane's 4x4 quadric. Unweighted, so
    a vertex's error is a sum of squared distances in mm² and bounds
    the largest one — what a tolerance in mm can be compared with."""
    n = _cross(_sub(q, p), _sub(r, p))
    length = math.sqrt(n[0] * n[0] + n[1] * n[1] + n[2] * n[2])
    if length < 1e-18:
        return [0.0] * 10
    a, b, c = n[0] / length, n[1] / length, n[2] / length
    d = -(a * p[0] + b * p[1] + c * p[2])
    return [a * a, a * b, a * c, a * d, b * b, b * c, b * d,
            c * c, c * d, d * d]


def _error(q, v):
    x, y, z = v
    return (q[0] * x * x + 2 * q[1] * x * y + 2 * q[2] * x * z
            + 2 * q[3] * x + q[4] * y * y + 2 * q[5] * y * z
            + 2 * q[6] * y + q[7] * z * z + 2 * q[8] * z + q[9])


def _optimum(q, a, b):
    """The point minimising quadric *q* — the 3x3 solve, or the best of
    the ends and the midpoint when the system is (near) singular."""
    m = ((q[0], q[1], q[2]), (q[1], q[4], q[5]), (q[2], q[5], q[7]))
    det = (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
           - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
           + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))
    scale = abs(q[0]) + abs(q[4]) + abs(q[7])
    if abs(det) > 1e-9 * max(scale, 1e-12) ** 3:
        rhs = (-q[3], -q[6], -q[8])
        x = (rhs[0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
             - m[0][1] * (rhs[1] * m[2][2] - m[1][2] * rhs[2])
             + m[0][2] * (rhs[1] * m[2][1] - m[1][1] * rhs[2])) / det
        y = (m[0][0] * (rhs[1] * m[2][2] - m[1][2] * rhs[2])
             - rhs[0] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
             + m[0][2] * (m[1][0] * rhs[2] - rhs[1] * m[2][0])) / det
        z = (m[0][0] * (m[1][1] * rhs[2] - rhs[1] * m[2][1])
             - m[0][1] * (m[1][0] * rhs[2] - rhs[1] * m[2][0])
             + rhs[0] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])) / det
        # a solve far outside the edge is a near-singular artefact
        span = math.dist(a, b)
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2)
        if math.dist((x, y, z), mid) <= 2 * span + 1e-9:
            return (x, y, z)
    mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2)
    return min((a, b, mid), key=lambda v: _error(q, v))


def collapse(points, faces, target: int, max_cost: float = math.inf):
    """Quadric edge collapse of the welded mesh down to *target* faces
    (or as far as the checks allow), never paying more than *max_cost*
    (a sum of squared distances, mm²). Returns (points, faces)."""
    points = [tuple(p) for p in points]
    faces = [list(f) for f in faces]
    alive = [True] * len(faces)
    vfaces = [set() for _ in points]
    for fi, f in enumerate(faces):
        for v in f:
            vfaces[v].add(fi)
    quad = [[0.0] * 10 for _ in points]
    for f in faces:
        k = _plane_quadric(points[f[0]], points[f[1]], points[f[2]])
        for v in f:
            qv = quad[v]
            for i in range(10):
                qv[i] += k[i]
    version = [0] * len(points)
    removed = [False] * len(points)

    def edge_faces(a, b):
        return vfaces[a] & vfaces[b]

    def cost(a, b):
        q = [quad[a][i] + quad[b][i] for i in range(10)]
        v = _optimum(q, points[a], points[b])
        return max(_error(q, v), 0.0), v

    heap = []

    # an open border stays put: no collapse may move one of its vertices
    uses = {}
    for f in faces:
        for a, b in ((f[0], f[1]), (f[1], f[2]), (f[2], f[0])):
            key = (min(a, b), max(a, b))
            uses[key] = uses.get(key, 0) + 1
    border = {v for key, n in uses.items() if n != 2 for v in key}

    def push(a, b):
        if a > b:
            a, b = b, a
        if a in border or b in border or len(edge_faces(a, b)) != 2:
            return
        c, v = cost(a, b)
        heapq.heappush(heap, (c, a, b, version[a], version[b], v))

    seen = set()
    for f in faces:
        for a, b in ((f[0], f[1]), (f[1], f[2]), (f[2], f[0])):
            key = (min(a, b), max(a, b))
            if key not in seen:
                seen.add(key)
                push(*key)
    count = len(faces)

    def neighbours(v):
        out = set()
        for fi in vfaces[v]:
            out.update(faces[fi])
        out.discard(v)
        return out

    while heap and count > max(target, MIN_TRIS):
        c, a, b, va, vb, pos = heapq.heappop(heap)
        if c > max_cost:
            break
        if removed[a] or removed[b] or version[a] != va \
                or version[b] != vb:
            continue
        shared = edge_faces(a, b)
        if len(shared) != 2:
            continue
        # link condition: a and b may share only the two opposite corners
        opposite = {v for fi in shared for v in faces[fi]} - {a, b}
        if neighbours(a) & neighbours(b) != opposite:
            continue
        # no face that survives may turn over
        folds = False
        for v in (a, b):
            for fi in vfaces[v] - shared:
                f = faces[fi]
                before = _normal(*(points[i] for i in f))
                after = _normal(*((pos if i in (a, b) else points[i])
                                  for i in f))
                if before is None or after is None or (
                        before[0] * after[0] + before[1] * after[1]
                        + before[2] * after[2]) < FOLD_COS:
                    folds = True
                    break
            if folds:
                break
        if folds:
            continue
        # collapse b into a, a moved to pos
        for fi in shared:
            alive[fi] = False
            for v in faces[fi]:
                vfaces[v].discard(fi)
        count -= 2
        for fi in vfaces[b]:
            f = faces[fi]
            f[f.index(b)] = a
            vfaces[a].add(fi)
        vfaces[b] = set()
        removed[b] = True
        points[a] = pos
        quad[a] = [quad[a][i] + quad[b][i] for i in range(10)]
        # only a's edges change cost; a neighbour's other edges keep
        # theirs (their folds are checked again when they come up)
        version[a] += 1
        for n in neighbours(a):
            push(a, n)
    # compact
    remap, out_points = {}, []
    out_faces = []
    for fi, f in enumerate(faces):
        if not alive[fi]:
            continue
        row = []
        for v in f:
            if v not in remap:
                remap[v] = len(out_points)
                out_points.append(points[v])
            row.append(remap[v])
        out_faces.append(row)
    return out_points, out_faces


def triangles(points, faces):
    return [(points[a], points[b], points[c]) for a, b, c in faces]


def _manifold_pass(tris, target, tolerance):
    """Manifold's simplify: at *tolerance* when given, else at the
    largest tolerance whose result keeps at least *target* triangles.
    None when Manifold is missing or the mesh is not a closed solid."""
    from . import csg
    if not csg.available():
        return None
    solid = csg.to_manifold([(t, None, False) for t in tris], {})
    if solid is None:
        return None
    if tolerance > 0:
        return csg.to_triangles(solid.simplify(tolerance))
    lo, hi = solid.bounding_box()[:3], solid.bounding_box()[3:]
    top = 0.02 * math.dist(lo, hi)          # past a few % it misbehaves
    low, best = 0.0, None
    high = top
    for _ in range(12):
        mid = (low + high) / 2
        trial = solid.simplify(mid)
        if trial.num_tri() >= target:
            low, best = mid, trial
        else:
            high = mid
    return csg.to_triangles(best) if best is not None else None


def decimate(tris, ratio: float = 0.5, tolerance: float = 0.0):
    """The triangles of *tris* reduced — to *ratio* of their count, or
    within *tolerance* mm when that is > 0. CCW triangles in and out."""
    tris = list(tris)
    if not tris:
        return []
    if tolerance > 0:
        out = _manifold_pass(tris, 0, tolerance)
        if out is not None:
            return out
        # no Manifold: collapse while every step stays in tolerance
        points, faces = weld(tris)
        return triangles(*collapse(points, faces, MIN_TRIS,
                                   max_cost=tolerance * tolerance))
    ratio = min(max(float(ratio), 0.0), 1.0)
    if ratio >= 1.0:
        return tris
    target = max(MIN_TRIS, int(round(len(tris) * ratio)))
    if len(tris) > PREPASS_ABOVE:
        # Manifold's simplify is C++ but coarser: let it take a big mesh
        # only part of the way, and the quadric collapse finish
        first = _manifold_pass(tris, max(3 * target, PREPASS_ABOVE), 0.0)
        if first is not None:
            tris = first
    if len(tris) <= target:
        return tris
    points, faces = weld(tris)
    return triangles(*collapse(points, faces, target))


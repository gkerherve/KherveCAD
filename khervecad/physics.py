"""Drop & settle — parts fall, tip over and come to rest (gravity).

A small deterministic stand-in for a rigid-body simulator (Blender's
Bullet), enough for what a modeller asks of one: "put these on the
table", "stack the bricks", "lay the parts out on the print bed", "does
it stand up or fall over?".

For each part, lowest first:

1. **Settle** (optional): on the floor it tips like a real object — the
   support is the convex hull's lowest points; while the centre of mass
   lies outside that footprint the part ROLLS over the support edge
   nearest to it, by exactly the angle that brings the next hull vertex
   down to the floor, until the centre of mass is over the footprint
   (a cone rolls onto its side, a box stays, a leaning post falls).
2. **Drop**: it then falls straight down until it touches the floor or a
   part already placed — rays down from its vertices into those, and up
   from theirs into it (Manifold ray casts, csg.py), the shortest gap
   wins — so it rests ON them.

The result is one rigid move per part (a rotation about its centre of
mass, then a translation) that `apply` writes into the part's placement
params, so it stays an ordinary editable, undoable position. Qt-free.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from .ik import _mm, _t, euler_matrix, matrix_euler, rotation_between

#: at most this many rolls while settling
MAX_ROLLS = 24
EPS = 1e-6


def _hull_points(tris):
    from . import geom3d
    pts = list({tuple(round(c, 6) for c in v) for t in tris for v in t})
    if len(pts) < 4:
        return pts
    hull = geom3d.convex_hull(pts)
    return list({v for t in hull for v in t}) if hull else pts


def _rotate_about(p, r, c):
    d = [p[i] - c[i] for i in range(3)]
    q = [sum(r[i][k] * d[k] for k in range(3)) for i in range(3)]
    return [q[i] + c[i] for i in range(3)]


def _axis_rotation(axis, angle):
    x, y, z = axis
    ca, sa = math.cos(angle), math.sin(angle)
    return [[ca + x * x * (1 - ca), x * y * (1 - ca) - z * sa,
             x * z * (1 - ca) + y * sa],
            [y * x * (1 - ca) + z * sa, ca + y * y * (1 - ca),
             y * z * (1 - ca) - x * sa],
            [z * x * (1 - ca) - y * sa, z * y * (1 - ca) + x * sa,
             ca + z * z * (1 - ca)]]


def _hull2d(pts):
    pts = sorted(set(pts))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def settle(tris, tol=None):
    """(rotation 3x3 about the centre of mass, rolls) that tips *tris*
    onto a stable footing on a horizontal floor."""
    from . import analysis
    com = analysis.mass_properties(tris)["centroid"]
    hull = _hull_points(tris)
    ident = [[1.0, 0, 0], [0, 1.0, 0], [0, 0, 1.0]]
    if len(hull) < 4:
        return ident, 0
    size = max(max(p[i] for p in hull) - min(p[i] for p in hull)
               for i in range(3))
    tol = tol or 1e-4 * max(size, 1.0)
    rot = ident
    pts = hull
    rolls = 0
    for rolls in range(MAX_ROLLS + 1):
        floor = min(p[2] for p in pts)
        base = [p for p in pts if p[2] - floor <= tol]
        poly = _hull2d([(p[0], p[1]) for p in base])
        c2 = (com[0], com[1])
        if len(poly) >= 3 and _inside(c2, poly, tol):
            return rot, rolls
        # the support edge (or point) to roll over: nearest the COM
        if len(poly) >= 2:
            a, b = _nearest_edge(c2, poly)
        else:
            a = b = poly[0]
        pa = next(p for p in base if (p[0], p[1]) == a)
        pb = next(p for p in base if (p[0], p[1]) == b)
        if a == b:
            # a point: tip toward the COM about the horizontal axis; a COM
            # balanced exactly over the point is unstable — it tips +x
            d = (c2[0] - a[0], c2[1] - a[1])
            if math.hypot(*d) <= tol:
                d = (1.0, 0.0)
            ax = (-d[1], d[0], 0.0)
        else:
            ax = (pb[0] - pa[0], pb[1] - pa[1], 0.0)
        la = math.hypot(ax[0], ax[1])
        if la < 1e-12:
            return rot, rolls
        ax = (ax[0] / la, ax[1] / la, 0.0)
        # turn the side the COM hangs over DOWN (balanced exactly over a
        # line, it falls to the axis' left)
        out = (c2[0] - pa[0], c2[1] - pa[1])
        if ax[0] * out[1] - ax[1] * out[0] < -tol:
            ax = (-ax[0], -ax[1], 0.0)
        # smallest angle bringing another hull point down to the floor
        pivot = pa
        best = None
        for p in pts:
            d = [p[i] - pivot[i] for i in range(3)]
            along = d[0] * ax[0] + d[1] * ax[1]
            r = [d[0] - along * ax[0], d[1] - along * ax[1], d[2]]
            horiz = r[0] * (-ax[1]) + r[1] * ax[0]    # toward the COM side
            if math.hypot(horiz, r[2]) < tol:
                continue
            # angle (rolling toward -z on the COM side) until r[2] -> 0
            phi = math.atan2(r[2], horiz)
            if phi <= 1e-9:
                continue
            best = phi if best is None else min(best, phi)
        if best is None:
            return rot, rolls
        step = _axis_rotation(ax, -best)
        # check the direction: the COM side must go down
        test = _rotate_about([pivot[0] - ax[1], pivot[1] + ax[0],
                              pivot[2] + 1.0], step, pivot)
        if test[2] > pivot[2] + 1.0:
            step = _axis_rotation(ax, best)
        pts = [_rotate_about(p, step, pivot) for p in pts]
        com = _rotate_about(com, step, pivot)
        rot = _mm(step, rot)
    return rot, rolls


def _inside(p, poly, tol):
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        if (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) \
                < -tol:
            return False
    return True


def _nearest_edge(p, poly):
    best, pair = None, None
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        ab = (b[0] - a[0], b[1] - a[1])
        t = ((p[0] - a[0]) * ab[0] + (p[1] - a[1]) * ab[1]) / \
            (ab[0] ** 2 + ab[1] ** 2 or 1e-12)
        t = min(max(t, 0.0), 1.0)
        q = (a[0] + ab[0] * t, a[1] + ab[1] * t)
        # outside this edge's half-plane counts first
        side = ab[0] * (p[1] - a[1]) - ab[1] * (p[0] - a[0])
        d = math.dist(p, q) if side < 0 else math.dist(p, q) + 1e9
        if best is None or d < best:
            best, pair = d, (a, b)
    return pair


def _gap_down(tris, others, reach):
    """How far *tris* can fall before touching *others* (their
    triangles): rays down from its vertices, and up from theirs."""
    from . import csg
    if not others or not csg.available():
        return None
    below = csg.to_manifold([(t, None, False) for t in others], {})
    mine = csg.to_manifold([(t, None, False) for t in tris], {})
    best = None
    if below is not None:
        for v in {tuple(p) for t in tris for p in t}:
            hits = below.ray_cast(v, (v[0], v[1], v[2] - reach))
            if hits:
                d = hits[0].distance * reach
                best = d if best is None else min(best, d)
    if mine is not None:
        for v in {tuple(p) for t in others for p in t}:
            hits = mine.ray_cast(v, (v[0], v[1], v[2] + reach))
            if hits:
                d = hits[0].distance * reach
                best = d if best is None else min(best, d)
    return best


def drop(parts, floor=0.0, settle_parts=True, gap=0.0):
    """*parts* = [(key, world triangles)]. Returns {key: {"rotation":
    3x3 about "centre", "centre", "move": [dx, dy, dz], "rolls"}} with
    every part resting on the floor or on the ones below it."""
    from . import analysis
    order = sorted(parts, key=lambda kv: min(v[2] for t in kv[1]
                                             for v in t) if kv[1] else 0)
    placed = []
    out = {}
    for key, tris in order:
        if not tris:
            continue
        com = analysis.mass_properties(tris)["centroid"]
        rot = [[1.0, 0, 0], [0, 1.0, 0], [0, 0, 1.0]]
        rolls = 0
        if settle_parts:
            rot, rolls = settle(tris)
        moved = [tuple(tuple(_rotate_about(v, rot, com)) for v in t)
                 for t in tris]
        low = min(v[2] for t in moved for v in t)
        fall = low - (floor + gap)
        reach = max(fall, 0.0) + 1.0
        hit = _gap_down(moved, placed, reach + 1.0)
        if hit is not None and hit - gap < fall:
            fall = hit - gap
        dz = -fall
        final = [tuple((v[0], v[1], v[2] + dz) for v in t) for t in moved]
        placed.extend(final)
        out[key] = {"rotation": rot, "centre": com, "move": [0.0, 0.0, dz],
                    "rolls": rolls}
    return out


def placement(node, move, env=None):
    """New (x, y, z, rx, ry, rz) for a movable *node* (Group / Object /
    instance) after the world move {rotation, centre, move}: the move M
    is applied in world space, L' = A⁻¹ · M · A · L."""
    from .mesh import (ancestor_matrix, mat_mul, mat_translate,
                       node_matrix)
    rot = move["rotation"]
    c = move["centre"]
    d = move["move"]
    m = [[rot[i][0], rot[i][1], rot[i][2],
          c[i] - sum(rot[i][k] * c[k] for k in range(3)) + d[i]]
         for i in range(3)] + [[0.0, 0.0, 0.0, 1.0]]
    a = ancestor_matrix(node, env)
    a_inv = _invert(a)
    local = mat_mul(a_inv, mat_mul(m, mat_mul(a, node_matrix(node, env))))
    r = [[local[i][j] for j in range(3)] for i in range(3)]
    rx, ry, rz = matrix_euler(r)
    return (local[0][3], local[1][3], local[2][3], rx, ry, rz)


def _invert(m):
    """Inverse of a rigid-or-scaled affine 4x4."""
    r = [[m[i][j] for j in range(3)] for i in range(3)]
    det = (r[0][0] * (r[1][1] * r[2][2] - r[1][2] * r[2][1])
           - r[0][1] * (r[1][0] * r[2][2] - r[1][2] * r[2][0])
           + r[0][2] * (r[1][0] * r[2][1] - r[1][1] * r[2][0]))
    inv = [[(r[(j + 1) % 3][(i + 1) % 3] * r[(j + 2) % 3][(i + 2) % 3]
             - r[(j + 1) % 3][(i + 2) % 3] * r[(j + 2) % 3][(i + 1) % 3])
            / det for j in range(3)] for i in range(3)]
    t = [m[i][3] for i in range(3)]
    ti = [-sum(inv[i][k] * t[k] for k in range(3)) for i in range(3)]
    return [inv[0] + [ti[0]], inv[1] + [ti[1]], inv[2] + [ti[2]],
            [0.0, 0.0, 0.0, 1.0]]


def world_tris(node, env=None):
    """*node*'s triangles in world space (its ancestors applied)."""
    from . import mesh
    tris = mesh.tessellate(node)
    m = mesh.ancestor_matrix(node, env)
    return [tuple(tuple(mesh.mat_apply(m, v)) for v in t) for t in tris]


def apply(model, nodes, floor=0.0, settle_parts=True, gap=0.0, env=None):
    """Drop *nodes* (each made movable) and write their placements —
    one undo step per call. Returns a report per part."""
    from . import mates
    movable = [mates.ensure_part(model, n) for n in nodes]
    parts = [(str(n.id), world_tris(n, env)) for n in movable]
    moves = drop(parts, floor, settle_parts, gap)
    report = []
    for n in movable:
        mv = moves.get(str(n.id))
        if mv is None:
            continue
        x, y, z, rx, ry, rz = placement(n, mv, env)
        for key, value in (("x", x), ("y", y), ("z", z), ("rx", rx),
                           ("ry", ry), ("rz", rz)):
            model.set_param(n, key, round(value, 4))
        tilt = math.degrees(math.acos(max(-1.0, min(1.0,
                                                    mv["rotation"][2][2]))))
        report.append({"id": n.id, "name": n.name,
                       "fell": round(-mv["move"][2], 3),
                       "tipped_deg": round(tilt, 2),
                       "rolls": mv["rolls"]})
    return report

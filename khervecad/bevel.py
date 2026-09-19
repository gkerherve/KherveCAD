"""Bevel — every sharp edge rounded or chamfered (Blender's Bevel).

Where fillet.py rounds the edges a person clicks, the `bevel` wrapper
takes every crease sharper than ``angle`` — the convex ones, the
concave ones or both — like Blender's Bevel modifier with its angle
limit, and gives them Blender's controls:

* ``width`` — the rolling-ball radius (the setback along each face is
  width / tan(half the angle between the faces): width on a box edge);
* ``segments`` — steps across the bevel (1 = a flat chamfer);
* ``profile`` — the shape of the steps, Blender's superellipse: 0.5 a
  round, 0.25 a straight chamfer, towards 1 a square corner, below 0.25
  a cove. A section is C + (T_L - C)·cos^(2/e) θ + (T_R - C)·sin^(2/e) θ
  in the frame of the two tangent points (C = T_L + T_R - E), with
  e = 2^(1 + (profile - 0.5) / 0.25) — affine, so it stays tangent to both
  faces whatever their angle; e = 2 is drawn as the true circular arc.

**Corners** are what the fillet tool could not do: where three bevelled
edges of one kind meet, the slab between the three faces and their
planes offset by the width is cut away (added, for an inside corner)
minus the ball of that width tangent to all three — the rolling-ball
blend, since that ball lies inside each edge's round (its centre is on
every edge's axis), so the edge strips and the corner meet without a
step. Other profiles take the affine superellipsoid in the same slab —
for a chamfer that is the triangle Blender puts on a box corner, through
the new vertices on the three faces (x + y + z = 2w). A cove (profile
under 0.25) is not convex, so its corners are what the strips leave.

The booleans are Manifold's (csg.py): part minus the convex strips and
corners, plus the concave ones — so the preview is the real bevel and
the node bakes the result like the other deformers. Qt-free.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from . import fillet
from .fillet import (_add, _area2d, _cross, _dot, _mul, _mul_2d, _sub,
                     _unit, _unit_2d, _vkey)

EDGES = ("convex", "concave", "both")


def exponent(profile: float) -> float:
    """Blender's profile (0..1, 0.5 = round) as a superellipse power."""
    p = min(max(float(profile), 0.05), 0.95)
    return 2.0 ** (1.0 + (p - 0.5) / 0.25)


def _curve(n, e):
    """(f, g) weights of the superellipse from (1, 0) to (0, 1) in n
    steps: f^(e) + g^(e) = 1."""
    out = []
    for k in range(1, n):
        t = math.pi / 2 * k / n
        c, s = math.cos(t), math.sin(t)
        out.append((c ** (2.0 / e) if c > 0 else 0.0,
                    s ** (2.0 / e) if s > 0 else 0.0))
    return out


def section(edge, width: float, segments: int, e: float):
    """(u, v, points2d) like fillet.profile, with the superellipse."""
    t = edge.direction
    dl = _unit(_cross(edge.nl, t))
    dr = _unit(_cross(t, edge.nr))
    u = dl
    v = _unit(_cross(t, u))
    x_r, y_r = _dot(dr, u), _dot(dr, v)
    beta = math.acos(max(-1.0, min(1.0, _dot(dl, dr))))
    beta = max(beta, math.radians(1.0))
    s = width / math.tan(beta / 2.0)
    tl, tr = (s, 0.0), (s * x_r, s * y_r)
    n = max(int(segments), 1)
    pts = [(0.0, 0.0), tl]
    if abs(e - 2.0) < 1e-9:
        # the true rolling-ball arc (what the corner sphere matches)
        cx, cy = _mul_2d(_unit_2d((1.0 + x_r, y_r)),
                         width / math.sin(beta / 2.0))
        a0 = math.atan2(tl[1] - cy, tl[0] - cx)
        a1 = math.atan2(tr[1] - cy, tr[0] - cx)
        sweep = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
        for k in range(1, n):
            a = a0 + sweep * k / n
            pts.append((cx + width * math.cos(a), cy + width * math.sin(a)))
    else:
        cx, cy = tl[0] + tr[0], tl[1] + tr[1]
        ax, ay = tl[0] - cx, tl[1] - cy
        bx, by = tr[0] - cx, tr[1] - cy
        for f, g in _curve(n, e):
            pts.append((cx + ax * f + bx * g, cy + ay * f + by * g))
    pts.append(tr)
    if _area2d(pts) < 0:
        pts = [pts[0]] + pts[1:][::-1]
    m = len(pts)
    ox = sum(x for x, _y in pts) / m
    oy = sum(y for _x, y in pts) / m
    grow = 1.0 + fillet.GROW
    return u, v, [(ox + (x - ox) * grow, oy + (y - oy) * grow)
                  for x, y in pts]


def select(tris, angle: float, which: str):
    """The crease chains to bevel: every edge past *angle* degrees of
    the kind asked for, one chain per tangent-continuous run."""
    edges = fillet.crease_edges(tris, angle)
    # where exactly two creases of one kind meet (a pocket's rim turning
    # a corner, the third crease there concave) the run turns the corner
    # mitred; where three meet (a box corner) it stops for the corner
    count = {}
    for x in edges:
        for key in (_vkey(x.a), _vkey(x.b)):
            count[(key, x.convex)] = count.get((key, x.convex), 0) + 1
    runs, seen = [], set()
    for e in edges:
        if which == "convex" and not e.convex:
            continue
        if which == "concave" and e.convex:
            continue
        run = fillet.chain(
            edges, e, through=lambda key, k=e.convex:
            count.get((key, k), 0) == 2)
        key = frozenset(_vkey(p) for p in run["points"])
        if key in seen:
            continue
        seen.add(key)
        runs.append(run)
    return edges, runs


def _trim_ends(solid, run, runs, width):
    """A concave run's filler stopped one setback short of any end where
    bevelled convex creases meet it (a pocket's corner post under a
    bevelled rim): the fill would stand up through the rim's bevel.
    Blender puts a patch there; the fill ending where the bevel starts
    is the same corner to within the setback."""
    if run["closed"]:
        return solid
    convex_at = {_vkey(p) for r in runs if r["convex"]
                 for x in r["edges"] for p in (x.a, x.b)}
    ends = ((run["points"][0], _mul(run["edges"][0].direction, -1.0)),
            (run["points"][-1], run["edges"][-1].direction))
    for point, out in ends:
        if _vkey(point) not in convex_at:
            continue
        # keep n.x >= offset with n pointing back along the run
        n = _mul(out, -1.0)
        solid = solid.trim_by_plane(tuple(n), _dot(n, point) + width)
    return solid


def _solve3(rows, rhs):
    """x with rows · x = rhs (3x3, Cramer), or None when singular."""
    (a, b, c), (d, e, f), (g, h, i) = rows
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    if abs(det) < 1e-9:
        return None
    r0, r1, r2 = rhs
    return ((r0 * (e * i - f * h) - b * (r1 * i - f * r2)
             + c * (r1 * h - e * r2)) / det,
            (a * (r1 * i - f * r2) - r0 * (d * i - f * g)
             + c * (d * r2 - r1 * g)) / det,
            (a * (e * r2 - r1 * h) - b * (d * r2 - r1 * g)
             + r0 * (d * h - e * g)) / det)


def corners(edges, runs, width: float, segments: int, e: float):
    """Corner pieces, as (manifold, convex) pairs, where exactly three
    creases of one kind — all of them bevelled — meet at a vertex with
    three face planes."""
    import manifold3d as m
    chosen = {id(x) for run in runs for x in run["edges"]}
    chosen_keys = {(_vkey(x.a), _vkey(x.b)) for run in runs
                   for x in run["edges"]}
    at = {}
    for x in edges:
        for key in (_vkey(x.a), _vkey(x.b)):
            at.setdefault(key, []).append(x)
    out = []
    for key, creases in at.items():
        if len(creases) != 3:
            continue
        if not all(id(x) in chosen or (_vkey(x.a), _vkey(x.b)) in
                   chosen_keys or (_vkey(x.b), _vkey(x.a)) in chosen_keys
                   for x in creases):
            continue
        kinds = {x.convex for x in creases}
        if len(kinds) != 1:
            continue
        convex = kinds.pop()
        normals = []
        for x in creases:
            for n in (x.nl, x.nr):
                if all(_dot(n, k) < 0.9999 for k in normals):
                    normals.append(n)
        if len(normals) != 3:
            continue
        vtx = creases[0].a if _vkey(creases[0].a) == key else creases[0].b
        sign = -1.0 if convex else 1.0      # ball inside the solid, or out
        d0 = [_dot(n, vtx) for n in normals]
        centre = _solve3(normals, [d + sign * width for d in d0])
        if centre is None:
            continue
        corners8 = []
        for mask in range(8):
            rhs = [d0[i] + (sign * width if mask >> i & 1 else 0.0)
                   for i in range(3)]
            p = _solve3(normals, rhs)
            if p is None:
                break
            corners8.append(p)
        if len(corners8) != 8:
            continue
        # grown about the ball centre: the faces on the offset planes
        # stay put (grown past them it cut slivers off what stays), the
        # faces on the part's own planes clear them (no coplanar boolean)
        grow = 1.0 + 4 * fillet.GROW
        slab = m.Manifold.hull_points(
            [[centre[i] + (p[i] - centre[i]) * grow for i in range(3)]
             for p in corners8])
        n = max(int(segments), 1)
        if abs(e - 2.0) < 1e-9:
            ball = m.Manifold.sphere(width, 4 * n).translate(tuple(centre))
        else:
            ball = _superball(m, centre, corners8, e, n)
        piece = slab - ball
        if not piece.is_empty():
            out.append((piece, convex))
    return out


def _superball(m, centre, corners8, e, n):
    """The convex superellipsoid (e >= 1) centred on the slab's inner
    corner, its axes the slab's edges from there — the unit one mapped
    affinely, so on each slab face it is the edge strips' own profile."""
    c = centre
    # corner 7 (all offset planes) is the centre; clearing one bit moves
    # along one slab edge back to a face plane
    axes = [[corners8[7 ^ (1 << i)][k] - c[k] for k in range(3)]
            for i in range(3)]
    steps = max(2 * n, 8)
    pts = []
    for i in range(steps + 1):
        phi = math.pi / 2 * i / steps
        for j in range(steps + 1):
            th = math.pi / 2 * j / steps
            w = [math.cos(phi) * math.cos(th),
                 math.cos(phi) * math.sin(th), math.sin(phi)]
            w = [x ** (2.0 / e) if x > 1e-12 else 0.0 for x in w]
            for sx in (-1, 1):
                for sy in (-1, 1):
                    for sz in (-1, 1):
                        pts.append([c[k] + axes[0][k] * sx * w[0]
                                    + axes[1][k] * sy * w[1]
                                    + axes[2][k] * sz * w[2]
                                    for k in range(3)])
    return m.Manifold.hull_points(pts)


def bevel(tris, width=1.0, segments=4, profile=0.5, angle=30.0,
          which="convex"):
    """*tris* with its creases bevelled; None when Manifold is missing
    or the part is not a closed solid (the caller keeps the part)."""
    from . import csg
    if not csg.available() or not tris or width <= 0:
        return None
    base = csg.to_manifold([(t, None, False) for t in tris], {})
    if base is None:
        return None
    import manifold3d as m
    e = exponent(profile)
    edges, runs = select(tris, angle, which)
    cuts, adds = [], []
    for run in runs:
        body = fillet.strip(run, width, "round", segments,
                            section=lambda x: section(x, width, segments, e))
        if not body:
            continue
        solid = csg.to_manifold([(t, None, False) for t in body], {})
        if solid is None:
            continue
        if not run["convex"]:
            solid = _trim_ends(solid, run, runs, width)
        (cuts if run["convex"] else adds).append(solid)
    if e >= 1.0 - 1e-9:                  # a cove's ball is not convex
        for piece, convex in corners(edges, runs, width, segments, e):
            (cuts if convex else adds).append(piece)
    # fill first, then cut: a concave corner's filler ends at the top
    # face, and would otherwise rise through the rim's bevel beside it
    result = base
    if adds:
        result = m.Manifold.batch_boolean([result] + adds, m.OpType.Add)
    if cuts:
        result = m.Manifold.batch_boolean([result] + cuts,
                                          m.OpType.Subtract)
    if result.status() != m.Error.NoError:
        return None
    return csg.to_triangles(result)

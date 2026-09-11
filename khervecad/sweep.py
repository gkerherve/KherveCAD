"""Sweep geometry — a 2D profile driven along a 3D path (Qt-free).

Blender does this with a curve and a bevel object; OpenSCAD has no
equivalent at all (the usual idiom is a chain of hull()s, which
convexifies the profile). This module turns any 2D outline — a
rectangle, a circle, a polygon, text, several of them — into the solid
it sweeps out along a polyline path: pipes, handrails, cable runs,
springs, chain links.

- The path is densified by Catmull-Rom smoothing (like loft.py), so a
  few typed corners become a fair curve, and every given point stays
  on it.
- The profile rides a rotation-minimising frame (double-reflection
  method), so it never twists on its own; *twist* adds a deliberate
  turn over the length and *scale* narrows or widens it towards the
  end. A ring at a corner lies in the plane bisecting the two
  segments — a mitre, so square tubes turn crisply.
- The profile's own axes follow linear_extrude's convention: seen with
  the path coming towards you and Z up, profile x points right and
  profile y up (a vertical path maps x -> X, y -> Y exactly).
- *wall* > 0 hollows the sweep: an inner outline offset inwards by the
  wall thickness gets its own inward-facing walls, and the end caps
  become rings between the two. That is how a pipe is made without a
  2D difference (which the preview cannot cut).
- *closed* joins the last ring to the first (no caps) for a loop —
  an O-ring, a chain link, a closed handrail. The frame's holonomy
  round the loop is spread evenly so the seam matches.

Output is a list of counter-clockwise (outward) triangles for the
preview; bake.py welds them into an OpenSCAD polyhedron.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from .loft import _catmull, _cross, _dot, _scale, _sub, _unit

#: consecutive path points closer than this (mm) are one point — a
#: zero-length segment has no direction to frame a ring with
MERGE = 1e-6


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _dedupe(points):
    out = []
    for p in points:
        p = (float(p[0]), float(p[1]), float(p[2]))
        if not out or _dot(_sub(p, out[-1]), _sub(p, out[-1])) > MERGE ** 2:
            out.append(p)
    return out


def densify(points, smooth: int, closed: bool = False) -> list:
    """The path points with *smooth* Catmull-Rom steps per span; the
    given points always stay on the curve. A closed path wraps its
    neighbours round the loop instead of extrapolating the ends."""
    pts = _dedupe(points)
    if closed and len(pts) > 2 and \
            _dot(_sub(pts[0], pts[-1]), _sub(pts[0], pts[-1])) <= MERGE ** 2:
        pts.pop()                        # the loop was typed closed
    n = len(pts)
    if smooth <= 0 or n < 2:
        return pts
    out = []
    if closed:
        for k in range(n):
            p0, p1, p2, p3 = (pts[(k - 1) % n], pts[k], pts[(k + 1) % n],
                              pts[(k + 2) % n])
            for j in range(smooth + 1):
                out.append(tuple(_catmull(p0, p1, p2, p3,
                                          j / (smooth + 1))))
        return out
    first = tuple(2 * a - b for a, b in zip(pts[0], pts[1]))
    last = tuple(2 * a - b for a, b in zip(pts[-1], pts[-2]))
    ext = [first] + pts + [last]
    for k in range(n - 1):
        for j in range(smooth + 1):
            out.append(tuple(_catmull(ext[k], ext[k + 1], ext[k + 2],
                                      ext[k + 3], j / (smooth + 1))))
    out.append(pts[-1])
    return out


def _rotate_about(vec, axis, angle):
    """Rodrigues: *vec* turned by *angle* radians about unit *axis*."""
    c, s = math.cos(angle), math.sin(angle)
    k = _cross(axis, vec)
    d = _dot(axis, vec)
    return tuple(vec[i] * c + k[i] * s + axis[i] * d * (1 - c)
                 for i in range(3))


def frames(centres, closed: bool = False) -> tuple:
    """(tangents, u, v) at every centre: u is the profile's x axis, v
    its y axis, u x v = tangent. The frame is rotation-minimising along
    the path; a closed loop's mismatch at the seam is spread over the
    rings so the last joins the first."""
    n = len(centres)
    if closed:
        tangents = [_unit(_sub(centres[(i + 1) % n], centres[(i - 1) % n]))
                    for i in range(n)]
    else:
        tangents = [_unit(_sub(centres[min(i + 1, n - 1)],
                               centres[max(i - 1, 0)])) for i in range(n)]
    t0 = tangents[0]
    if abs(t0[2]) > 0.99:                  # vertical: x -> X, y -> Y
        u0 = _unit(_sub((1.0, 0.0, 0.0), _scale(t0, t0[0])))
    else:                                  # path towards you, Z up: x right
        u0 = _unit(_cross((0.0, 0.0, 1.0), t0))
    us = [u0]
    steps = list(range(n - 1)) + ([n - 1] if closed else [])
    for i in steps:
        j = (i + 1) % n
        u = us[-1]
        v1 = _sub(centres[j], centres[i])
        c1 = _dot(v1, v1)
        if c1 < 1e-18:
            rl, tl = u, tangents[i]
        else:
            rl = _sub(u, _scale(v1, 2.0 / c1 * _dot(v1, u)))
            tl = _sub(tangents[i], _scale(v1, 2.0 / c1 * _dot(v1, tangents[i])))
        v2 = _sub(tangents[j], tl)
        c2 = _dot(v2, v2)
        us.append(rl if c2 < 1e-18
                  else _sub(rl, _scale(v2, 2.0 / c2 * _dot(v2, rl))))
    if closed:
        # the frame carried round the loop lands turned by the path's
        # holonomy; undo it a little per ring so the seam lines up
        back = us.pop()
        angle = math.atan2(_dot(_cross(back, u0), t0), _dot(back, u0))
        us = [_rotate_about(u, tangents[i], angle * i / n)
              for i, u in enumerate(us)]
    us = [_unit(_sub(u, _scale(t, _dot(u, t)))) for u, t in zip(us, tangents)]
    vs = [_cross(t, u) for t, u in zip(tangents, us)]
    return tangents, us, vs


def _arc_fractions(centres, closed: bool) -> list:
    """Cumulative arc length of each centre as a fraction of the whole
    (the far end is 1 — for a closed loop, the seam)."""
    lengths = [0.0]
    for a, b in zip(centres, centres[1:]):
        d = _sub(b, a)
        lengths.append(lengths[-1] + math.sqrt(_dot(d, d)))
    total = lengths[-1]
    if closed:
        d = _sub(centres[0], centres[-1])
        total += math.sqrt(_dot(d, d))
    return [ln / total if total > 0 else 0.0 for ln in lengths]


def _area(outline) -> float:
    total = 0.0
    for i, (x1, y1) in enumerate(outline):
        x2, y2 = outline[(i + 1) % len(outline)]
        total += x1 * y2 - x2 * y1
    return total / 2.0


def _ccw(outline):
    pts = [(float(x), float(y)) for x, y in outline]
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts.pop()
    return pts if _area(pts) >= 0 else pts[::-1]


def _inner_outline(outline, wall):
    """The outline offset inwards by *wall*, or None when the wall
    swallows it (then the sweep is simply solid)."""
    from .mesh import offset_outline
    inner = offset_outline(outline, -abs(wall))
    if len(inner) != len(outline):
        return None
    area = _area(inner)
    if area <= 1e-9 or area >= _area(outline):
        return None
    return inner


def _triangulate(outline):
    from .mesh import triangulate
    return triangulate(outline)


def sweep(outlines, path, smooth: int = 3, twist: float = 0.0,
          scale: float = 1.0, wall: float = 0.0,
          closed: bool = False) -> list:
    """Counter-clockwise triangles of the solid the *outlines* (lists of
    (x, y), any winding) sweep out along *path* ([[x, y, z], ...]).
    Empty for fewer than two distinct points (three when closed)."""
    # smoothing multiplies points, so judge the path as typed: a
    # two-point "loop" has no inside to go round
    if len(densify(path, 0, closed)) < (3 if closed else 2):
        return []
    centres = densify(path, int(smooth), closed)
    n = len(centres)
    tangents, us, vs = frames(centres, closed)
    fractions = _arc_fractions(centres, closed)
    twist_rad = math.radians(float(twist))
    scale = float(scale)

    def ring(outline, i):
        f = fractions[i]
        s = 1.0 + (scale - 1.0) * f
        a = twist_rad * f
        ca, sa = math.cos(a), math.sin(a)
        c, u, v = centres[i], us[i], vs[i]
        pts = []
        for x, y in outline:
            px = (x * ca - y * sa) * s
            py = (x * sa + y * ca) * s
            pts.append(tuple(c[k] + px * u[k] + py * v[k] for k in range(3)))
        return pts

    tris = []

    def walls(outline, inward=False):
        """Side quads between consecutive rings of *outline*."""
        rings = [ring(outline, i) for i in range(n)]
        m = len(outline)
        spans = list(zip(rings, rings[1:]))
        if closed:
            spans.append((rings[-1], rings[0]))
        for lower, upper in spans:
            for k in range(m):
                k1 = (k + 1) % m
                a, b, c, d = lower[k], lower[k1], upper[k1], upper[k]
                if inward:
                    tris.append((a, c, b))
                    tris.append((a, d, c))
                else:
                    tris.append((a, b, c))
                    tris.append((a, c, d))
        return rings

    def cap(outer_ring, inner_ring, outline, inner, reverse):
        if inner is None:
            for a, b, c in _triangulate(outline):
                idx = [outline.index(p) for p in (a, b, c)]
                pa, pb, pc = (outer_ring[i] for i in idx)
                tris.append((pa, pc, pb) if reverse else (pa, pb, pc))
            return
        m = len(outline)
        for k in range(m):                 # a strip between the two loops
            k1 = (k + 1) % m
            o0, o1, i0, i1 = (outer_ring[k], outer_ring[k1],
                              inner_ring[k], inner_ring[k1])
            quad = ((o0, o1, i1), (o0, i1, i0))
            for a, b, c in quad:
                tris.append((a, c, b) if reverse else (a, b, c))

    for raw in outlines:
        outline = _ccw(raw)
        if len(outline) < 3:
            continue
        inner = _inner_outline(outline, wall) if wall and wall > 0 else None
        outer_rings = walls(outline)
        inner_rings = walls(inner, inward=True) if inner else None
        if not closed:
            cap(outer_rings[0], inner_rings[0] if inner else None,
                outline, inner, reverse=True)
            cap(outer_rings[-1], inner_rings[-1] if inner else None,
                outline, inner, reverse=False)
    return tris

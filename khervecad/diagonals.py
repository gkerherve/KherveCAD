# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""BOTH diagonals of a rectangle, as SolidWorks shows them (2026-11-16,
the user: "in wireframe each rectangle has one diagonal ... SolidWorks
shows the two, snapped to, and to where they cross — the centre"). The
one line the wireframe showed was only the seam between a face's two
triangles. Here every four-cornered flat face of the part and every
sketch rectangle gets its two diagonals as construction guides — drawn
dashed in the 3D wireframe and the 2D sketch — and a click snaps on
them and on their crossing.

Geometry is Qt-free: `face_quads(tris)` (world corners of the part's
four-cornered faces), `quad_of_segments(segs)` (a face outline in the
sketch plane that is one quad), `rect_corners(node)`, `diagonals(c)`
-> two segments, and `snap(p, quads, tol)`."""

import math


def _key(p):
    return tuple(round(float(c), 4) for c in p)


def face_quads(tris):
    """[[c0, c1, c2, c3]] — world corners, in order round the face — of
    every flat face made of exactly two triangles sharing an edge (a
    box's faces, an extruded rectangle's)."""
    if not tris:
        return []
    groups = {}
    for t in tris:
        a, b, c = (tuple(map(float, v)) for v in t[:3])
        ux, uy, uz = (b[i] - a[i] for i in range(3))
        vx, vy, vz = (c[i] - a[i] for i in range(3))
        n = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
        ln = math.sqrt(sum(x * x for x in n))
        if ln < 1e-12:
            continue
        n = tuple(x / ln for x in n)
        d = sum(n[i] * a[i] for i in range(3))
        k = (round(n[0], 3), round(n[1], 3), round(n[2], 3), round(d, 2))
        groups.setdefault(k, []).append((a, b, c))
    out = []
    for faces in groups.values():
        if len(faces) != 2:
            continue
        (a1, b1, c1), t2 = faces
        k1 = [_key(p) for p in (a1, b1, c1)]
        k2 = [_key(p) for p in t2]
        shared = [p for p in k1 if p in k2]
        if len(shared) != 2:
            continue
        lone1 = next(p for p in (a1, b1, c1) if _key(p) not in k2)
        lone2 = next(p for p in t2 if _key(p) not in k1)
        s0 = next(p for p in (a1, b1, c1) if _key(p) == shared[0])
        s1 = next(p for p in (a1, b1, c1) if _key(p) == shared[1])
        quad = [lone1, s0, lone2, s1]       # round the face
        if _rectangular(quad):
            out.append(quad)
    return out


def _rectangular(q, tol=1e-3):
    """Four corners whose diagonals cross at both their middles (a
    parallelogram) and are equal (a rectangle)."""
    a, b, c, d = q
    m1 = [(a[i] + c[i]) / 2 for i in range(len(a))]
    m2 = [(b[i] + d[i]) / 2 for i in range(len(a))]
    l1 = math.dist(a, c)
    l2 = math.dist(b, d)
    size = max(l1, l2, 1e-9)
    return math.dist(m1, m2) <= tol * size and abs(l1 - l2) <= tol * size


def diagonals(corners):
    """The two diagonals of four corners in order round the shape."""
    a, b, c, d = corners
    return [(tuple(a), tuple(c)), (tuple(b), tuple(d))]


def centre(corners):
    n = len(corners[0])
    return tuple(sum(p[i] for p in corners) / 4.0 for i in range(n))


def rect_corners(node):
    """(x, y) corners of a sketch rectangle (or a four-point polygon
    that is one), in its own params frame; None for anything else."""
    p = node.params
    try:
        if node.type == "rect":
            x, y = float(p.get("x", 0)), float(p.get("y", 0))
            w, h = float(p.get("width", 0)), float(p.get("height", 0))
            if p.get("center"):
                x, y = x - w / 2, y - h / 2
            if abs(w) < 1e-9 or abs(h) < 1e-9:
                return None
            return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        if node.type == "polygon":
            pts = [(float(q[0]), float(q[1])) for q in p.get("points") or []]
            if len(pts) == 4 and not p.get("paths") and _rectangular(pts):
                ox, oy = float(p.get("x", 0)), float(p.get("y", 0))
                return [(x + ox, y + oy) for x, y in pts]
    except (TypeError, ValueError):
        return None
    return None


def quad_of_segments(segs, tol=1e-4):
    """The four corners, in order, when *segs* (2D) are exactly one
    rectangle's four sides; else None."""
    if not segs or len(segs) < 4:
        return None
    ends = {}
    for a, b in segs:
        for p in (a, b):
            k = (round(p[0], 3), round(p[1], 3))
            ends[k] = ends.get(k, 0) + 1
    corners = []
    for a, b in segs:
        for p in (a, b):
            k = (round(p[0], 3), round(p[1], 3))
            if k not in [(round(c[0], 3), round(c[1], 3)) for c in corners]:
                corners.append((float(p[0]), float(p[1])))
    # collinear pieces of one side join: keep the turning points only
    turning = []
    n = len(corners)
    for c in corners:
        nb = [q for a, b in segs for q in ((b,) if _same(a, c) else
                                           (a,) if _same(b, c) else ())]
        if len(nb) != 2:
            return None
        u = (nb[0][0] - c[0], nb[0][1] - c[1])
        v = (nb[1][0] - c[0], nb[1][1] - c[1])
        if abs(u[0] * v[1] - u[1] * v[0]) > tol * (math.hypot(*u) *
                                                   math.hypot(*v) or 1):
            turning.append(c)
    if len(turning) != 4 or n < 4:
        return None
    cx = sum(p[0] for p in turning) / 4
    cy = sum(p[1] for p in turning) / 4
    turning.sort(key=lambda p: math.atan2(p[1] - cy, p[0] - cx))
    return turning if _rectangular(turning) else None


def _same(p, q):
    return abs(p[0] - q[0]) < 1e-6 and abs(p[1] - q[1]) < 1e-6


def _on_segment(px, py, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 < 1e-12 else max(0.0, min(1.0, ((px - a[0]) * dx +
                                                  (py - a[1]) * dy) / L2))
    return a[0] + dx * t, a[1] + dy * t


def snap(p, quads, point_tol, line_tol):
    """((x, y), kind) — the centre of a quad within *point_tol*, else
    the nearest point ON a diagonal within *line_tol*; else None."""
    best = None
    for q in quads:
        c = centre(q)
        d = math.hypot(c[0] - p[0], c[1] - p[1])
        if d <= point_tol and (best is None or d < best[0]):
            best = (d, (c[0], c[1]), "centre")
    if best is not None:
        return best[1], best[2]
    for q in quads:
        for a, b in diagonals(q):
            x, y = _on_segment(p[0], p[1], a, b)
            d = math.hypot(x - p[0], y - p[1])
            if d <= line_tol and (best is None or d < best[0]):
                best = (d, (x, y), "diagonal")
    return (best[1], best[2]) if best else None

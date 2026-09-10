"""3D convex hull for the built-in tessellator.

OpenSCAD's `hull()` is exact; the pure-Python preview had no 3D hull
at all and drew a hull as the union of its children. The organic
primitives are hulls by definition — a capsule is the hull of two
spheres, a rounded box the hull of eight — so they need the real
thing to preview as what they are.

Quickhull with conflict lists: every point still outside the hull is
filed under exactly one face it can see, the face with the farthest
point grows next, and only the points of the faces it replaces are
re-filed. Qt-free.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


class _Face:
    __slots__ = ("v", "n", "off", "out", "alive")

    def __init__(self, v, n, off):
        self.v = v              # three point indices, counter-clockwise
        self.n = n              # unit outward normal
        self.off = off          # n . x for any x on the face
        self.out = []           # indices of the points it can see
        self.alive = True


def convex_hull(points) -> list:
    """Triangles ``((x, y, z), (x, y, z), (x, y, z))`` of the convex
    hull of *points*, wound counter-clockwise seen from outside.

    Returns ``[]`` for fewer than four points that span a volume
    (collinear, coplanar or coincident input has no 3D hull)."""
    pts = list({(float(p[0]), float(p[1]), float(p[2])) for p in points})
    if len(pts) < 4:
        return []
    span = max(max(p[i] for p in pts) - min(p[i] for p in pts)
               for i in range(3))
    if span <= 0.0:
        return []
    eps = span * 1e-9

    # --- a starting tetrahedron from well-spread extreme points
    extremes = []
    for i in range(3):
        extremes.append(min(range(len(pts)), key=lambda k: pts[k][i]))
        extremes.append(max(range(len(pts)), key=lambda k: pts[k][i]))

    def d2(i, j):
        d = _sub(pts[i], pts[j])
        return _dot(d, d)
    ia, ib = max(((i, j) for i in extremes for j in extremes),
                 key=lambda ij: d2(*ij))
    if d2(ia, ib) <= eps * eps:
        return []
    ab = _sub(pts[ib], pts[ia])

    def off_line(k):
        c = _cross(ab, _sub(pts[k], pts[ia]))
        return _dot(c, c)
    ic = max(range(len(pts)), key=off_line)
    normal = _cross(ab, _sub(pts[ic], pts[ia]))
    nlen = math.sqrt(_dot(normal, normal))
    if nlen <= eps * span:
        return []                                  # all on one line
    id_ = max(range(len(pts)),
              key=lambda k: abs(_dot(normal, _sub(pts[k], pts[ia]))))
    if abs(_dot(normal, _sub(pts[id_], pts[ia]))) <= eps * nlen:
        return []                                  # all in one plane

    def make(i, j, k):
        p = pts[i]
        n = _cross(_sub(pts[j], p), _sub(pts[k], p))
        length = math.sqrt(_dot(n, n)) or 1.0
        n = (n[0] / length, n[1] / length, n[2] / length)
        return _Face((i, j, k), n, _dot(n, p))

    edges = {}                  # directed edge (u, w) -> face owning it

    def link(face):
        i, j, k = face.v
        edges[(i, j)] = edges[(j, k)] = edges[(k, i)] = face

    faces = []
    simplex = (ia, ib, ic, id_)
    for skip in range(4):
        tri = [simplex[m] for m in range(4) if m != skip]
        face = make(*tri)
        if _dot(face.n, pts[simplex[skip]]) - face.off > 0.0:
            face = make(tri[0], tri[2], tri[1])     # the 4th is behind
        faces.append(face)
        link(face)

    # --- file every other point under a face that sees it
    for k in range(len(pts)):
        if k in simplex:
            continue
        p = pts[k]
        for face in faces:
            if _dot(face.n, p) - face.off > eps:
                face.out.append(k)
                break

    stack = [f for f in faces if f.out]
    while stack:
        face = stack.pop()
        if not face.alive or not face.out:
            continue
        eye = max(face.out, key=lambda k: _dot(face.n, pts[k]) - face.off)
        ep = pts[eye]
        # every face the eye can see, and the horizon ringing them
        visible = {face}
        queue = [face]
        horizon = []
        while queue:
            g = queue.pop()
            i, j, k = g.v
            for u, w in ((i, j), (j, k), (k, i)):
                h = edges.get((w, u))
                if h is None or h in visible:
                    continue
                if _dot(h.n, ep) - h.off > eps:
                    visible.add(h)
                    queue.append(h)
                else:
                    horizon.append((u, w))
        orphans = []
        for g in visible:
            g.alive = False
            orphans.extend(g.out)
            i, j, k = g.v
            for e in ((i, j), (j, k), (k, i)):
                if edges.get(e) is g:
                    del edges[e]
        fresh = []
        for u, w in horizon:        # the cone from the horizon to the eye
            nf = make(u, w, eye)
            link(nf)
            fresh.append(nf)
        for k in orphans:
            if k == eye:
                continue
            p = pts[k]
            for nf in fresh:
                if _dot(nf.n, p) - nf.off > eps:
                    nf.out.append(k)
                    break
        faces.extend(fresh)
        stack.extend(nf for nf in fresh if nf.out)
    return [(pts[f.v[0]], pts[f.v[1]], pts[f.v[2]])
            for f in faces if f.alive]

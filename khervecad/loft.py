"""Loft: a smooth tube through a list of sections — the sweep behind
limbs, tails, horns, handles and fingers.

A section is ``[x, y, z, w, h]``: a centre and the two radii of an
elliptical cross-section (w across, h up). The centres are joined by
a Catmull-Rom spline, so the path bends smoothly through them instead
of kinking; the radii ride the same spline. Each ring sits in a
**rotation-minimising frame** (double reflection, Wang et al. 2008),
so the tube never twists on its own, and the ends close flat or as
rounded domes.

The ``kcad_loft`` OpenSCAD module (bake.HELPERS) runs these very
formulas in OpenSCAD's language, so the exact render is computed from
the node's parameters — expressions and loop variables included — and
this module is only the preview's copy. Keep the two in step; the
engine test compares them.

Pure geometry and Qt-free.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

#: smallest radius a ring may shrink to (a zero radius folds the tube)
MIN_RADIUS = 1e-3


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _scale(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _unit(v):
    length = math.sqrt(_dot(v, v))
    return _scale(v, 1.0 / length) if length > 1e-12 else (0.0, 0.0, 1.0)


def _catmull(p0, p1, p2, p3, t):
    t2 = t * t
    t3 = t2 * t
    return [0.5 * (2 * p1[i] + (p2[i] - p0[i]) * t
                   + (2 * p0[i] - 5 * p1[i] + 4 * p2[i] - p3[i]) * t2
                   + (3 * p1[i] - p0[i] - 3 * p2[i] + p3[i]) * t3)
            for i in range(len(p1))]


def path(sections, smooth: int) -> list:
    """The sections densified by *smooth* Catmull-Rom steps per span
    (0 keeps them as given). The given sections are always on the
    path: t = 0 of every span lands exactly on one."""
    s = [[float(v) for v in row] for row in sections]
    n = len(s)
    if smooth <= 0 or n < 2:
        return s
    first = [2 * a - b for a, b in zip(s[0], s[1])]
    last = [2 * a - b for a, b in zip(s[-1], s[-2])]
    ext = [first] + s + [last]
    out = []
    for k in range(n - 1):
        for j in range(smooth + 1):
            out.append(_catmull(ext[k], ext[k + 1], ext[k + 2], ext[k + 3],
                                j / (smooth + 1)))
    out.append(s[-1])
    return out


def frames(centres) -> tuple:
    """(tangents, normals, binormals) along *centres*: a rotation-
    minimising frame, started with the normal nearest world +Z (or +X
    for a path that starts vertical)."""
    n = len(centres)
    tangents = [_unit(_sub(centres[min(i + 1, n - 1)],
                           centres[max(i - 1, 0)])) for i in range(n)]
    t0 = tangents[0]
    ref = (1.0, 0.0, 0.0) if abs(t0[2]) > 0.99 else (0.0, 0.0, 1.0)
    normals = [_unit(_sub(ref, _scale(t0, _dot(ref, t0))))]
    for i in range(n - 1):
        nrm = normals[-1]
        v1 = _sub(centres[i + 1], centres[i])
        c1 = _dot(v1, v1)
        if c1 < 1e-18:
            rl, tl = nrm, tangents[i]
        else:
            rl = _sub(nrm, _scale(v1, 2.0 / c1 * _dot(v1, nrm)))
            tl = _sub(tangents[i],
                      _scale(v1, 2.0 / c1 * _dot(v1, tangents[i])))
        v2 = _sub(tangents[i + 1], tl)
        c2 = _dot(v2, v2)
        normals.append(rl if c2 < 1e-18
                       else _sub(rl, _scale(v2, 2.0 / c2 * _dot(v2, rl))))
    binormals = [_cross(t, nn) for t, nn in zip(tangents, normals)]
    return tangents, normals, binormals


def loft(sections, sides: int = 24, smooth: int = 3,
         caps: str = "round") -> tuple:
    """``(points, faces)`` of the lofted tube, faces as triangles in
    OpenSCAD's order (clockwise seen from outside). ``([], [])`` for
    fewer than two sections."""
    s = path(sections, int(smooth))
    if len(s) < 2:
        return [], []
    # floor(x + 0.5), not round(): Python rounds halves to even and
    # OpenSCAD away from zero, and the two must agree ring for ring
    count = max(int(math.floor(float(sides) + 0.5)), 3)
    centres = [tuple(row[:3]) for row in s]
    tangents, normals, binormals = frames(centres)
    angles = [2 * math.pi * k / count for k in range(count)]

    def ring(c, nrm, bin_, w, h):
        return [tuple(c[i] + w * math.cos(a) * bin_[i]
                      + h * math.sin(a) * nrm[i] for i in range(3))
                for a in angles]

    def radii(row):
        return max(row[3], MIN_RADIUS), max(row[4], MIN_RADIUS)
    domed = caps != "flat"
    steps = max(2, int(math.floor(count / 4 + 0.5)))  # dome rings/end
    rings = []
    w, h = radii(s[0])
    depth = (w + h) / 2
    if domed:
        start = tuple(centres[0][i] - tangents[0][i] * depth
                      for i in range(3))
        for j in range(steps - 1, 0, -1):
            phi = (math.pi / 2) * j / steps
            c = tuple(centres[0][i] - tangents[0][i] * depth * math.sin(phi)
                      for i in range(3))
            rings.append(ring(c, normals[0], binormals[0],
                              w * math.cos(phi), h * math.cos(phi)))
    else:
        start = centres[0]
    for i, row in enumerate(s):
        w, h = radii(row)
        rings.append(ring(centres[i], normals[i], binormals[i], w, h))
    w, h = radii(s[-1])
    depth = (w + h) / 2
    if domed:
        for j in range(1, steps):
            phi = (math.pi / 2) * j / steps
            c = tuple(centres[-1][i] + tangents[-1][i] * depth
                      * math.sin(phi) for i in range(3))
            rings.append(ring(c, normals[-1], binormals[-1],
                              w * math.cos(phi), h * math.cos(phi)))
        end = tuple(centres[-1][i] + tangents[-1][i] * depth
                    for i in range(3))
    else:
        end = centres[-1]
    points = [start] + [p for r in rings for p in r] + [end]
    last = len(points) - 1
    faces = []
    for r in range(len(rings) - 1):
        a0, b0 = 1 + r * count, 1 + (r + 1) * count
        for k in range(count):
            k1 = (k + 1) % count
            faces.append([a0 + k, a0 + k1, b0 + k1])
            faces.append([a0 + k, b0 + k1, b0 + k])
    first_ring, last_ring = 1, 1 + (len(rings) - 1) * count
    for k in range(count):
        k1 = (k + 1) % count
        faces.append([0, first_ring + k1, first_ring + k])
        faces.append([last, last_ring + k, last_ring + k1])
    return points, faces


def triangles(points, faces) -> list:
    """OpenSCAD-ordered faces as counter-clockwise (outward) triangles
    for the built-in preview."""
    return [(points[a], points[c], points[b]) for a, b, c in faces]

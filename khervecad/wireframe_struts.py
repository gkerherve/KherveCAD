"""Wireframe — a part's edges as printable struts (Blender's Wireframe).

The `wireframe` wrapper turns the edges of its children into round bars
of ``thickness`` mm with a ball at every corner, all unioned into one
closed solid: lamp shades, cages, geodesic domes, lightweight lattices,
a low-poly animal as a wire sculpture. Put a Decimate (fewer, longer
edges) or a Remesh (even ones) inside it to choose the pattern.

Only real edges become struts: two triangles meeting flatter than
``angle`` degrees share a diagonal that is just triangulation (a cube's
face is two triangles), so it is skipped — 0 keeps every edge.

The struts are Manifold cylinders placed along each edge and the whole
lattice one batch union (csg.py), so it is exact in the preview and
bakes like the other deformers. Qt-free.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

#: a lattice with more struts than this is refused (validation says so)
MAX_STRUTS = 20000


def edges(tris, angle: float = 1.0):
    """Distinct edges of *tris* ((a, b) points) whose two faces meet at
    more than *angle* degrees; border edges always count."""
    from .decimate import weld
    points, faces = weld(tris)
    normals = []
    for f in faces:
        a, b, c = (points[i] for i in f)
        u = [b[k] - a[k] for k in range(3)]
        v = [c[k] - a[k] for k in range(3)]
        n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2],
             u[0] * v[1] - u[1] * v[0]]
        length = math.sqrt(sum(x * x for x in n)) or 1.0
        normals.append([x / length for x in n])
    owners = {}
    for fi, f in enumerate(faces):
        for a, b in ((f[0], f[1]), (f[1], f[2]), (f[2], f[0])):
            owners.setdefault((min(a, b), max(a, b)), []).append(fi)
    cos_limit = math.cos(math.radians(max(float(angle), 0.0)))
    out = []
    for (a, b), fs in owners.items():
        if len(fs) == 2 and angle > 0:
            na, nb = normals[fs[0]], normals[fs[1]]
            if sum(x * y for x, y in zip(na, nb)) > cos_limit:
                continue
        out.append((points[a], points[b]))
    return out


def _frame(d):
    """A rotation (3 columns) taking +Z to unit *d*."""
    x, y, z = d
    ref = (1.0, 0.0, 0.0) if abs(x) < 0.9 else (0.0, 1.0, 0.0)
    u = (ref[1] * z - ref[2] * y, ref[2] * x - ref[0] * z,
         ref[0] * y - ref[1] * x)
    lu = math.sqrt(sum(c * c for c in u))
    u = tuple(c / lu for c in u)
    v = (y * u[2] - z * u[1], z * u[0] - x * u[2], x * u[1] - y * u[0])
    return u, v, d


def wireframe(tris, thickness=1.0, sides=6, angle=1.0, joints=True):
    """Triangles of the lattice, or None without Manifold."""
    from . import csg
    if not csg.available() or not tris or thickness <= 0:
        return None
    import manifold3d as m
    r = float(thickness) / 2.0
    n = max(int(sides), 3)
    runs = edges(tris, angle)
    if not runs:
        return []
    pieces = []
    corners = set()
    for i, (a, b) in enumerate(runs):
        length = math.dist(a, b)
        if length < 1e-9:
            continue
        d = tuple((b[k] - a[k]) / length for k in range(3))
        u, v, w = _frame(d)
        # a hair of variation per strut: identical struts meeting round a
        # symmetric vertex (a sphere's pole) cross at the very same points
        # and the union keeps pinched, coincident vertices there
        ri = r * (1.0 + 1e-3 * ((i * 7919) % 17) / 17.0)
        bar = m.Manifold.cylinder(length, ri, ri, n)
        mat = [[u[0], v[0], w[0], a[0]], [u[1], v[1], w[1], a[1]],
               [u[2], v[2], w[2], a[2]]]
        pieces.append(bar.transform(mat))
        corners.add(tuple(round(c, 6) for c in a))
        corners.add(tuple(round(c, 6) for c in b))
    if joints:
        # the faceted ball must CONTAIN every strut's end cap (a rim
        # poking out leaves coincident vertices where struts meet)
        seg = max(n, 12)
        ball = m.Manifold.sphere(r * 1.12 / math.cos(math.pi / seg), seg)
        pieces.extend(ball.translate(c) for c in corners)
    solid = m.Manifold.batch_boolean(pieces, m.OpType.Add)
    return weld_tiny(csg.to_triangles(solid))


def weld_tiny(tris, digits: int = 4):
    """Vertices closer than 10^-digits mm made one, collapsed triangles
    dropped: where many struts cross, the union leaves edges of a
    thousandth of a micron that the program's 4-digit points (and any
    watertight check) would weld into doubled edges anyway."""
    index, out = {}, []
    for tri in tris:
        keys = []
        for v in tri:
            k = (round(v[0], digits), round(v[1], digits),
                 round(v[2], digits))
            keys.append(index.setdefault(k, k))
        if len(set(keys)) == 3:
            out.append(tuple(keys))
    return out

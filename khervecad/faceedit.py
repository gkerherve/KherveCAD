"""Direct face editing — push/pull, inset and the knife (Qt-free).

SolidWorks' and SketchUp's push/pull, Blender's Inset and Bisect, on any
part — the gap the roadmap called "direct face push/pull":

* `push_pull` — each row ``[x, y, z, distance, inset]`` names a FLAT
  face by a point on it (in the children's own frame; probe_surface or a
  click gives one) and moves it: the face's whole coplanar region is
  extruded ``distance`` mm out along its normal (added) or, negative,
  cut that deep into the part — a boss, a pocket, a taller wall, a
  thinner plate. ``inset`` > 0 first shrinks the region by that much
  (Blender's Inset): a pocket that leaves a rim, a raised panel.
* `bisect` — the part cut by a plane (a point and a normal): keep the
  side the normal points to, the other, or both, pulled ``gap`` apart.

The face is found as geometry, not an index — the triangle nearest the
point, grown over every connected triangle in the same plane — so it
survives the part being edited, like a fillet's edges. The region's
outlines go into a Manifold CrossSection (holes stay holes), are
offset for the inset, extruded, and unioned or subtracted (csg.py).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

#: two triangles are one face when their normals agree this closely
FLAT_COS = 0.99999
KEEPS = ("above", "below", "both")


def _normal(tri):
    a, b, c = tri
    u = [b[i] - a[i] for i in range(3)]
    v = [c[i] - a[i] for i in range(3)]
    n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2],
         u[0] * v[1] - u[1] * v[0]]
    length = math.sqrt(sum(x * x for x in n))
    return None if length < 1e-15 else [x / length for x in n]


def face_region(tris, point, tol=None):
    """(triangle indices, normal, plane offset) of the flat face of
    *tris* at *point*, or None when no triangle is near it."""
    import numpy as np
    from .shrinkwrap import Target, closest_on_triangles
    if not tris:
        return None
    t = np.asarray(tris, dtype=np.float64)
    p = np.asarray(point, dtype=np.float64).reshape(1, 3)
    q = closest_on_triangles(p, t[:, 0], t[:, 1], t[:, 2])[0]
    d = np.linalg.norm(q - p[0], axis=1)
    size = float(np.ptp(t.reshape(-1, 3), axis=0).max()) or 1.0
    tol = tol if tol is not None else 0.02 * size + 0.5
    normals = [_normal(tri) for tri in tris]
    order = [i for i in np.argsort(d) if d[i] <= tol and normals[i]]
    if not order:
        return None
    seed = order[0]
    n = normals[seed]
    off = sum(n[k] * tris[seed][0][k] for k in range(3))
    eps = 1e-6 * size + 1e-9
    keyed = {}
    for i, tri in enumerate(tris):
        for a, b in ((0, 1), (1, 2), (2, 0)):
            key = tuple(sorted((tuple(round(c, 6) for c in tri[a]),
                                tuple(round(c, 6) for c in tri[b]))))
            keyed.setdefault(key, []).append(i)
    region, stack = {seed}, [seed]
    while stack:
        i = stack.pop()
        tri = tris[i]
        for a, b in ((0, 1), (1, 2), (2, 0)):
            key = tuple(sorted((tuple(round(c, 6) for c in tri[a]),
                                tuple(round(c, 6) for c in tri[b]))))
            for j in keyed.get(key, ()):
                if j in region or not normals[j]:
                    continue
                if sum(x * y for x, y in zip(normals[j], n)) < FLAT_COS:
                    continue
                if abs(sum(n[k] * tris[j][0][k] for k in range(3)) - off) \
                        > eps:
                    continue
                region.add(j)
                stack.append(j)
    return sorted(region), n, off


def _frame(n):
    ref = (1.0, 0.0, 0.0) if abs(n[0]) < 0.9 else (0.0, 1.0, 0.0)
    u = [ref[1] * n[2] - ref[2] * n[1], ref[2] * n[0] - ref[0] * n[2],
         ref[0] * n[1] - ref[1] * n[0]]
    lu = math.sqrt(sum(x * x for x in u))
    u = [x / lu for x in u]
    v = [n[1] * u[2] - n[2] * u[1], n[2] * u[0] - n[0] * u[2],
         n[0] * u[1] - n[1] * u[0]]
    return u, v


def region_section(tris, region, n, off):
    """The face region as a Manifold CrossSection in the plane frame
    (u, v, n), plus that frame."""
    import manifold3d as m
    u, v = _frame(n)
    polys = []
    for i in region:
        poly = [(sum(p[k] * u[k] for k in range(3)),
                 sum(p[k] * v[k] for k in range(3))) for p in tris[i]]
        area = ((poly[1][0] - poly[0][0]) * (poly[2][1] - poly[0][1])
                - (poly[1][1] - poly[0][1]) * (poly[2][0] - poly[0][0]))
        if area < 0:
            poly = poly[::-1]
        polys.append(poly)
    # the union of the region's triangles is the face (holes included)
    cs = m.CrossSection.batch_boolean(
        [m.CrossSection([p]) for p in polys], m.OpType.Add)
    return cs, (u, v, n, off)


def _place(solid, frame, base):
    """A solid built on z in the plane frame, put on the face plane at
    height *base* along the normal."""
    u, v, n, off = frame
    mat = [[u[0], v[0], n[0], n[0] * (off + base)],
           [u[1], v[1], n[1], n[1] * (off + base)],
           [u[2], v[2], n[2], n[2] * (off + base)]]
    return solid.transform(mat)


def push_pull(tris, rows):
    """*tris* with each row's face pushed (distance > 0) or pulled
    (< 0), IN ORDER — a row sees the result of the rows before it, so a
    boss just pulled out can be pulled again by its new top. Returns
    (triangles, [missing row indices]), or (None, []) without Manifold
    or a solid."""
    from . import csg
    if not csg.available():
        return None, []
    import manifold3d as m
    current = list(tris)
    solid = csg.to_manifold([(t, None, False) for t in current], {})
    if solid is None:
        return None, []
    missing = []
    for k, row in enumerate(rows):
        x, y, z, dist = (float(v) for v in row[:4])
        inset = float(row[4]) if len(row) > 4 else 0.0
        found = face_region(current, (x, y, z))
        if found is None:
            missing.append(k)
            continue
        if abs(dist) < 1e-9:
            continue
        region, n, off = found
        cs, frame = region_section(current, region, n, off)
        if inset > 0:
            cs = cs.offset(-inset, m.JoinType.Miter)
        if cs.is_empty():
            continue
        h = abs(dist)
        grow = 1e-3 * max(h, 1.0)
        slab = m.Manifold.extrude(cs, h + grow)
        if dist > 0:
            # starts a hair inside, so the union is not face-on-face
            solid = solid + _place(slab, frame, -grow)
        else:
            solid = solid - _place(slab, frame, -h)
        current = csg.to_triangles(solid)
    return current, missing


def bisect(tris, point, normal, keep="above", gap=0.0):
    """*tris* cut by the plane through *point* with *normal*; None
    without Manifold or a solid."""
    from . import csg
    if not csg.available():
        return None
    base = csg.to_manifold([(t, None, False) for t in tris], {})
    if base is None:
        return None
    ln = math.sqrt(sum(float(c) ** 2 for c in normal))
    if ln < 1e-12:
        return None
    n = [float(c) / ln for c in normal]
    off = sum(n[i] * float(point[i]) for i in range(3))
    above, below = base.split_by_plane(tuple(n), off)
    if keep == "above":
        out = above
    elif keep == "below":
        out = below
    else:
        half = float(gap) / 2.0
        out = above.translate(tuple(c * half for c in n)) + \
            below.translate(tuple(-c * half for c in n))
    return csg.to_triangles(out)

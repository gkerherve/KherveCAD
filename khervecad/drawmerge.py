"""Overlapping parts merged for the DRAWING only (Qt-free).

A Blueprint takes its lines from mesh edges. Two parts that pass
through each other — a port tube welded into a chamber wall, a branch
on a nipple — have no edge where their surfaces meet, so the drawing
showed only scraps of the meeting curve. Here a throw-away copy of the
triangles is split into solids, every group of solids that OVERLAP
(share volume) is unioned with Manifold, and the rest is left alone: the
meeting curves become real edges and the wall inside is gone. Parts that
only touch face to face (a bolted flange) keep their own outlines. The
model, its exports and its prints never see this.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from . import csg

#: shared volume (mm³) below which two solids only touch
MIN_OVERLAP = 1e-3
#: more solids than this are drawn as they are (pairwise tests)
MAX_SOLIDS = 400


def merged(tris):
    """(triangles, how many solids were joined). Falls back to *tris*
    unchanged without Manifold or when the mesh is not closed solids."""
    tris = list(tris or ())
    if not tris or not csg.available():
        return tris, 0
    try:
        return _merged(tris)
    except Exception:                                  # noqa: BLE001
        return tris, 0


def _merged(tris):
    import manifold3d as m
    palette = {}
    pieces = _pieces(tris, palette)
    if pieces is None or len(pieces) < 2 or len(pieces) > MAX_SOLIDS:
        return tris, 0
    boxes = [p.bounding_box() for p in pieces]
    parent = list(range(len(pieces)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(pieces)):
        for j in range(i + 1, len(pieces)):
            a, b = boxes[i], boxes[j]
            if any(a[k] > b[k + 3] or b[k] > a[k + 3] for k in range(3)):
                continue
            if find(i) == find(j):
                continue
            if (pieces[i] ^ pieces[j]).volume() > MIN_OVERLAP:
                parent[find(i)] = find(j)
    groups = {}
    for i in range(len(pieces)):
        groups.setdefault(find(i), []).append(pieces[i])
    joined = sum(len(g) for g in groups.values() if len(g) > 1)
    if not joined:
        return tris, 0
    out = []
    for g in groups.values():
        solid = g[0] if len(g) == 1 else \
            m.Manifold.batch_boolean(g, m.OpType.Add)
        out += csg.to_triangles(solid)
    return out, joined


def _pieces(tris, palette):
    """The separate closed solids of a triangle soup (each part's own,
    NOT unioned), or None."""
    import numpy as np
    import manifold3d as m
    n = len(tris)
    pos = np.asarray(tris, dtype=np.float64).reshape(n * 3, 3)
    keys = np.round(pos / csg.WELD).astype(np.int64)
    _u, first, inverse = np.unique(keys, axis=0, return_index=True,
                                   return_inverse=True)
    to = first[inverse.reshape(-1)].astype(np.uint64)
    frm = np.arange(n * 3, dtype=np.uint64)
    moved = to != frm
    mesh = m.Mesh64(vert_properties=pos,
                    tri_verts=np.arange(n * 3, dtype=np.uint64)
                    .reshape(n, 3),
                    merge_from_vert=frm[moved], merge_to_vert=to[moved])
    solid = m.Manifold(mesh)
    if solid.status() != m.Error.NoError or solid.is_empty():
        return None
    return solid.decompose()

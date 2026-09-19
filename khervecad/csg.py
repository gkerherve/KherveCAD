"""Exact mesh booleans for the built-in preview, through Manifold.

The preview used to draw a ``difference()`` as its uncut first operand
(and an intersection or minkowski the same way), so a bolt hole was
never there until OpenSCAD's render landed — and never at all without
the binary. Manifold (the same library OpenSCAD renders with, via its
``manifold3d`` Python bindings, Apache 2.0) cuts the preview's own
triangles in milliseconds, so the preview is right at once.

Colours ride along as vertex PROPERTIES: every corner carries its
row's colour index and selection flag, Manifold keeps them through the
boolean (a cut face takes the operand that made it), and the result's
triangles are read back into (triangle, colour, selected) rows.

Optional: without ``manifold3d`` (or when an operand is not a closed
solid — a flat 2D shape, an open imported scan) `boolean` returns None
and the tessellator falls back to the old approximation, remembering
the node in `FAILED` so the exact OpenSCAD render is still asked for.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

try:                                    # pragma: no cover - import guard
    import numpy as np
    import manifold3d as _m
except Exception:                       # pragma: no cover
    np = _m = None

#: node types this module computes exactly
HANDLED = frozenset({"difference", "intersection", "minkowski",
                     "fillet"})     # fillet.tess cuts its convex edges

#: node ids whose last boolean could not be computed (not a solid, no
#: Manifold) — they stay approximated and still want OpenSCAD's render
FAILED = set()

#: minkowski of two NON-convex operands costs the product of their face
#: counts; past this the preview keeps the first operand
MINKOWSKI_LIMIT = 400_000

#: positions closer than this (mm) are one vertex
WELD = 1e-6

ENABLED = _m is not None


def available() -> bool:
    return ENABLED and _m is not None


def to_manifold(rows, palette):
    """(triangle, colour, selected) rows -> one Manifold, the separate
    solids a group puts side by side (or overlapping) unioned — a mesh
    of two overlapping cubes is manifold edge-wise but not a solid.
    Returns None when the rows are not closed solids."""
    if not rows:
        return None
    n = len(rows)
    pos = np.empty((n * 3, 3), dtype=np.float64)
    props = np.empty((n * 3, 5), dtype=np.float64)
    k = 0
    for tri, colour, sel in rows:
        idx = palette.setdefault(colour, len(palette))
        flag = 1.0 if sel else 0.0
        for v in tri:
            pos[k] = v
            props[k, 3] = idx
            props[k, 4] = flag
            k += 1
    props[:, :3] = pos
    keys = np.round(pos / WELD).astype(np.int64)
    _u, first, inverse = np.unique(keys, axis=0, return_index=True,
                                   return_inverse=True)
    inverse = inverse.reshape(-1)
    to = first[inverse].astype(np.uint64)
    frm = np.arange(n * 3, dtype=np.uint64)
    moved = to != frm
    mesh = _m.Mesh64(vert_properties=props,
                     tri_verts=np.arange(n * 3, dtype=np.uint64)
                     .reshape(n, 3),
                     merge_from_vert=frm[moved], merge_to_vert=to[moved])
    solid = _m.Manifold(mesh)
    if solid.status() != _m.Error.NoError or solid.is_empty():
        return None
    pieces = solid.decompose()
    if len(pieces) > 1:
        solid = _m.Manifold.batch_boolean(pieces, _m.OpType.Add)
    return solid


def to_rows(solid, palette):
    """A Manifold back to (triangle, colour, selected) rows."""
    colours = [None] * len(palette)
    for colour, i in palette.items():
        colours[i] = colour
    out = solid.to_mesh64()
    props = np.asarray(out.vert_properties)
    tris = np.asarray(out.tri_verts)
    if not len(tris):
        return []
    pts = props[:, :3].tolist()
    cidx = np.rint(props[:, 3]).astype(int).tolist()
    sflag = (props[:, 4] > 0.5).tolist()
    last = len(colours) - 1
    rows = []
    for a, b, c in tris.tolist():
        ci = min(max(cidx[a], 0), last)
        rows.append(((tuple(pts[a]), tuple(pts[b]), tuple(pts[c])),
                     colours[ci], sflag[a]))
    return rows


def to_triangles(solid):
    """A Manifold's plain triangles (no colours)."""
    out = solid.to_mesh64()
    props = np.asarray(out.vert_properties)[:, :3].tolist()
    return [(tuple(props[a]), tuple(props[b]), tuple(props[c]))
            for a, b, c in np.asarray(out.tri_verts).tolist()]


def _convex(solid):
    hull = solid.hull()
    return abs(hull.volume() - solid.volume()) <= 1e-6 * max(
        hull.volume(), 1.0)


def boolean(op, operands):
    """*op* over the operands' rows (the first is the one kept, cut or
    grown). Returns the result rows, or None when it cannot be computed
    exactly (the caller then approximates)."""
    if not available() or op not in HANDLED or op == "fillet":
        return None
    palette = {}
    solids = []
    for i, rows in enumerate(operands):
        if not rows:
            if i == 0:
                return []
            continue                    # an empty tool removes nothing
        solid = to_manifold(rows, palette)
        if solid is None:
            return None
        solids.append(solid)
    if not solids:
        return []
    try:
        if op == "difference":
            result = _m.Manifold.batch_boolean(solids,
                                               _m.OpType.Subtract)
        elif op == "intersection":
            result = _m.Manifold.batch_boolean(solids,
                                               _m.OpType.Intersect)
        else:
            result = solids[0]
            for other in solids[1:]:
                if not (_convex(result) or _convex(other)) and \
                        result.num_tri() * other.num_tri() > \
                        MINKOWSKI_LIMIT:
                    return None
                result = result.minkowski_sum(other)
    except Exception:                   # pragma: no cover - library error
        return None
    if result.status() != _m.Error.NoError:
        return None
    return to_rows(result, palette)

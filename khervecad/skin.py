"""The `skin` node (Qt-free): a body grown round a stick skeleton —
Blender's Skin modifier, done as a smooth implicit surface.

``nodes`` rows ``[x, y, z, radius, parent]``: the skeleton's points with
the body's thickness there, each joined to its ``parent`` (a row index;
-1 for the root, or any row of its own branch). Every joint is a ROUND
CONE from the parent's sphere to the child's — a limb that tapers from
shoulder to wrist — and all of them are merged with a smooth minimum of
``smooth`` mm, so armpits, hips and the neck blend like flesh. One
closed surface comes out (marching tetrahedra over a grid ``detail``
cells across its longest side, sdf.mesh_values_np).

``pose`` rows ``[node, rx, ry, rz]`` turn everything beyond a node about
it (degrees, rotate([x, y, z]) order) BEFORE the body is grown, so a
posed skin is always a whole body — no weights, no stretching. The same
skeleton rigs it the other way round: rig_armature ``from_skin`` makes
one bone per joint (armature.bones_from_skin), for posing a skin that
has since been sculpted.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from . import bakedkit

NODE_LEN = 5
POSE_LEN = 4


def _parents(nodes):
    out = []
    for i, row in enumerate(nodes):
        try:
            p = int(round(float(row[4])))
        except (TypeError, ValueError, IndexError):
            p = -1
        out.append(p if 0 <= p < len(nodes) and p != i else -1)
    return out


def posed(nodes, pose):
    """The skeleton's points after *pose* (rows [node, rx, ry, rz])."""
    from . import armature
    parents = _parents(nodes)
    bones = {str(i): (str(parents[i]) if parents[i] >= 0 else "",
                      [float(v) for v in row[:3]],
                      [float(v) for v in row[:3]])
             for i, row in enumerate(nodes)}
    angles = {}
    for row in pose or []:
        try:
            angles[str(int(round(float(row[0]))))] = \
                [float(v) for v in row[1:4]]
        except (TypeError, ValueError, IndexError):
            continue
    if not angles:
        return [[float(v) for v in row[:3]] for row in nodes]
    mats = armature.bone_matrices(bones, angles)
    out = []
    for i, row in enumerate(nodes):
        p = [float(v) for v in row[:3]]
        if parents[i] < 0:
            out.append(p)
            continue
        m = mats[str(parents[i])]
        out.append([sum(m[r][k] * p[k] for k in range(3)) + m[r][3]
                    for r in range(3)])
    return out


def round_cone(pts, a, b, r1, r2):
    """Signed distance from (N, 3) *pts* to a round cone (iq's)."""
    import numpy as np
    a = np.asarray(a, dtype=float)
    ba = np.asarray(b, dtype=float) - a
    l2 = float(ba @ ba)
    if l2 < 1e-12:
        return np.linalg.norm(pts - a, axis=1) - max(r1, r2)
    rr = r1 - r2
    a2 = l2 - rr * rr
    il2 = 1.0 / l2
    pa = pts - a
    y = pa @ ba
    z = y - l2
    q = pa * l2 - np.outer(y, ba)
    x2 = np.einsum("ij,ij->i", q, q)
    y2 = y * y * l2
    z2 = z * z * l2
    k = np.sign(rr) * rr * rr * x2
    d_mid = (np.sqrt(np.maximum(x2 * a2 * il2, 0.0)) + y * rr) * il2 - r1
    d_end = np.sqrt(x2 + z2) * il2 - r2
    d_start = np.sqrt(x2 + y2) * il2 - r1
    return np.where(np.sign(z) * a2 * z2 > k, d_end,
                    np.where(np.sign(y) * a2 * y2 < k, d_start, d_mid))


def _smin(a, b, k):
    import numpy as np
    if k <= 0:
        return np.minimum(a, b)
    h = np.maximum(k - np.abs(a - b), 0.0) / k
    return np.minimum(a, b) - h * h * k * 0.25


def grow(nodes, pose=None, smooth=6.0, detail=80):
    """The closed body round the skeleton *nodes*."""
    import numpy as np
    from . import sdf
    if not nodes:
        return []
    pts = posed(nodes, pose)
    radii = [max(float(row[3]), 1e-3) for row in nodes]
    parents = _parents(nodes)
    pieces = [(pts[parents[i]], pts[i], radii[parents[i]], radii[i])
              for i in range(len(nodes)) if parents[i] >= 0]
    lone = [i for i in range(len(nodes)) if parents[i] < 0
            and i not in parents]
    pieces += [(pts[i], pts[i], radii[i], radii[i]) for i in lone]
    if not pieces:
        return []
    arr = np.asarray(pts)
    rmax = max(radii)
    pad = rmax + smooth + 1e-3
    lo, hi = arr.min(axis=0) - pad, arr.max(axis=0) + pad
    span = hi - lo
    cell = float(span.max()) / max(int(detail), 8)
    cells = np.ceil(span / cell).astype(int) + 1
    while cells.prod() > sdf.MAX_GRID_POINTS_NP:
        cell *= 1.25
        cells = np.ceil(span / cell).astype(int) + 1
    xs = lo[0] + np.arange(cells[0]) * cell
    ys = lo[1] + np.arange(cells[1]) * cell
    zs = lo[2] + np.arange(cells[2]) * cell
    vals = np.empty(len(xs) * len(ys) * len(zs))
    per = len(xs) * len(ys)
    gx, gy = np.meshgrid(xs, ys)
    plane = np.stack([gx.ravel(), gy.ravel(), np.zeros(per)], axis=1)
    reach = smooth + rmax
    for k, z in enumerate(zs):
        plane[:, 2] = z
        d = np.full(per, np.inf)
        for a, b, r1, r2 in pieces:
            if z < min(a[2], b[2]) - reach or z > max(a[2], b[2]) + reach:
                continue
            d = _smin(d, round_cone(plane, a, b, r1, r2), smooth) \
                if np.isfinite(d).any() else \
                round_cone(plane, a, b, r1, r2)
        vals[k * per:(k + 1) * per] = np.where(np.isfinite(d), d, reach)
    return sdf.mesh_values_np(vals, xs, ys, zs)


def _compute(node, env):
    nodes = bakedkit.rows(node, env, "nodes", NODE_LEN)
    pose = bakedkit.rows(node, env, "pose", POSE_LEN)
    return grow(nodes, pose, bakedkit.num(node, env, "smooth", 6.0),
                int(bakedkit.num(node, env, "detail", 80)))


def _check(node, env):
    rows = node.params.get("nodes") or []
    if len(rows) < 1:
        return "skin: give it a skeleton — rows [x, y, z, radius, parent]"
    for k, row in enumerate(rows):
        if not isinstance(row, list) or len(row) != NODE_LEN:
            return (f"skin point {k} needs {NODE_LEN} values: x, y, z, "
                    "radius, parent")
    nodes = bakedkit.rows(node, env, "nodes", NODE_LEN)
    if any(float(r[3]) <= 0 for r in nodes):
        return "skin: every radius must be more than 0"
    parents = _parents(nodes)
    for i in range(len(nodes)):
        seen, j = set(), i
        while j >= 0:
            if j in seen:
                return f"skin point {i} is its own ancestor"
            seen.add(j)
            j = parents[j]
    for k, row in enumerate(node.params.get("pose") or []):
        if not isinstance(row, list) or len(row) != POSE_LEN:
            return f"skin pose row {k} is [point, rx, ry, rz]"
    return None


KIT = bakedkit.make(
    "skin", "Skin (body round a skeleton)", "mdi.human-handsdown",
    dict(nodes=[[0.0, 0.0, 0.0, 10.0, -1], [0.0, 0.0, 40.0, 7.0, 0]],
         pose=[], smooth=6.0, detail=80),
    [("nodes", "Skeleton (point, radius, parent row; -1 = root)", "rows",
      ["X", "Y", "Z", "Radius", "Parent"], None),
     ("pose", "Pose (point, rx, ry, rz °)", "rows",
      ["Point", "rX", "rY", "rZ"], None),
     ("smooth", "Blend joints over (mm)", "float", 0.0, 1e4),
     ("detail", "Detail (cells across)", "int", 8, 400)],
    _compute, leaf=True, check=_check)

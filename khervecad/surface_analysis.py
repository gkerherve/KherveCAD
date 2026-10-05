"""Surface analysis on the part — Rhino's Draft Angle, Curvature and
Zebra, painted per face as heat maps (Analyse ▸ Heat Map). Qt-free.

* ``draft``     — how a face stands against the PULL direction (+Z, the
                  way a moulded part leaves its mould): green where it
                  has at least the wanted draft, yellow where it has
                  some but too little, red where it is vertical or
                  undercut (the mould would scrape or lock it), blue on
                  faces looking straight up or down.
* ``curvature`` — mean curvature: red where the surface bulges out,
                  blue where it dips in, green where it is flat; scaled
                  to the part's own range, so a gentle hull and a tight
                  fillet both show their pattern.
* ``zebra``     — black and white bands reflected off the surface. Where
                  the stripes run on unbroken across an edge the
                  surfaces meet smoothly; a kink or step in the stripes
                  is a crease the eye will catch on the real part.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

RED, YELLOW, GREEN, BLUE = "#e53935", "#fdd835", "#43a047", "#1e88e5"
WHITE, BLACK = "#f5f5f5", "#202020"
#: zebra stripes over a half turn of the reflected direction
STRIPES = 8


def _normals(tris):
    import numpy as np
    t = np.asarray(tris, dtype=float).reshape(-1, 3, 3)
    n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    area = np.linalg.norm(n, axis=1)
    unit = n / np.where(area > 1e-18, area, 1.0)[:, None]
    return t, unit, area / 2


def draft(tris, wanted: float = 2.0):
    """(colours, stats): the draft angle of every face against +Z."""
    import numpy as np
    if not tris:
        return [], {}
    _t, n, area = _normals(tris)
    # angle of the face from vertical: 0 = a vertical wall
    ang = np.degrees(np.arcsin(np.clip(n[:, 2], -1.0, 1.0)))
    out = []
    bad = 0.0
    for a, w in zip(ang, area):
        if abs(a) > 89.0:
            out.append(BLUE)
        elif a >= wanted or a <= -wanted:
            # up-facing faces leave the top mould half, down-facing the
            # bottom one — both are drafted
            out.append(GREEN)
        elif abs(a) > 0.25:
            out.append(YELLOW)
        else:
            out.append(RED)
            bad += w
    total = float(area.sum()) or 1.0
    return out, dict(kind="draft", draft=wanted,
                     no_draft_fraction=bad / total,
                     legend=f"green at least {wanted:g}° of draft, yellow "
                            f"less than {wanted:g}°, red vertical (no "
                            "draft), blue flat (facing up or down)")


def _welded(tris):
    import numpy as np
    t = np.asarray(tris, dtype=float).reshape(-1, 3)
    keys = np.round(t, 5)
    uniq, inverse = np.unique(keys, axis=0, return_inverse=True)
    return uniq, inverse.reshape(-1, 3)


def _smooth_face_normals(tris, crease=40.0):
    """Each face's normal as the mean of its corners' area-weighted
    vertex normals (corners shared with faces within *crease* degrees)
    — what a smooth surface's facets approximate; a flat facet normal
    turns zebra stripes into a chequerboard."""
    import numpy as np
    pts, faces = _welded(tris)
    fn = np.cross(pts[faces[:, 1]] - pts[faces[:, 0]],
                  pts[faces[:, 2]] - pts[faces[:, 0]])
    unit = fn / np.maximum(np.linalg.norm(fn, axis=1), 1e-18)[:, None]
    vn = np.zeros((len(pts), 3))
    for k in range(3):
        np.add.at(vn, faces[:, k], fn)
    vn /= np.maximum(np.linalg.norm(vn, axis=1), 1e-18)[:, None]
    cos = math.cos(math.radians(crease))
    out = np.zeros_like(unit)
    for k in range(3):
        corner = vn[faces[:, k]]
        ok = np.einsum("ij,ij->i", corner, unit) > cos
        out += np.where(ok[:, None], corner, unit)
    return out / np.maximum(np.linalg.norm(out, axis=1), 1e-18)[:, None]


def curvature(tris):
    """(colours, stats): mean curvature per face, by the umbrella
    operator — each vertex against the average of its neighbours, along
    the vertex normal — scaled to the part's own 90th percentile."""
    import numpy as np
    if not tris:
        return [], {}
    pts, faces = _welded(tris)
    nv = len(pts)
    fn = np.cross(pts[faces[:, 1]] - pts[faces[:, 0]],
                  pts[faces[:, 2]] - pts[faces[:, 0]])
    vn = np.zeros((nv, 3))
    for k in range(3):
        np.add.at(vn, faces[:, k], fn)
    vn /= np.maximum(np.linalg.norm(vn, axis=1), 1e-18)[:, None]
    nsum = np.zeros((nv, 3))
    count = np.zeros(nv)
    for a, b in ((0, 1), (1, 2), (2, 0), (1, 0), (2, 1), (0, 2)):
        np.add.at(nsum, faces[:, a], pts[faces[:, b]])
        np.add.at(count, faces[:, a], 1.0)
    lap = nsum / np.maximum(count, 1.0)[:, None] - pts
    edge = np.linalg.norm(pts[faces[:, 1]] - pts[faces[:, 0]], axis=1)
    h = float(np.median(edge)) or 1.0
    # signed: the neighbours' centre BELOW the vertex (against its
    # normal) is a bulge
    value = -np.einsum("ij,ij->i", lap, vn) / (h * h)
    per_face = value[faces].mean(axis=1)
    scale = float(np.percentile(np.abs(per_face), 90)) or 1.0
    out = []
    for v in per_face / scale:
        if v > 0.35:
            out.append(RED if v > 0.8 else "#ef9a9a")
        elif v < -0.35:
            out.append(BLUE if v < -0.8 else "#90caf9")
        else:
            out.append(GREEN)
    return out, dict(kind="curvature",
                     legend="red bulging out, blue dipping in, green "
                            "flat — relative to this part's own range")


def zebra(tris, stripes: int = STRIPES, view=(0.0, -1.0, 0.3)):
    """(colours, stats): black / white bands of a striped sky reflected
    in each face, seen from *view* (towards the eye)."""
    import numpy as np
    if not tris:
        return [], {}
    n = _smooth_face_normals(tris)
    v = np.asarray(view, dtype=float)
    v /= np.linalg.norm(v)
    r = 2 * np.einsum("ij,j->i", n, v)[:, None] * n - v   # reflected
    elevation = np.arcsin(np.clip(r[:, 2], -1, 1))         # -90..90°
    band = np.floor((elevation / math.pi + 0.5) * stripes * 2).astype(int)
    out = [WHITE if b % 2 == 0 else BLACK for b in band]
    return out, dict(kind="zebra", stripes=stripes,
                     legend="stripes that run on unbroken across a seam "
                            "mean the surfaces meet smoothly; a kink or "
                            "jump is a crease")

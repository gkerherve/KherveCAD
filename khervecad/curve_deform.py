"""SolidWorks' **Deform ▸ Curve to curve** (2026-11-15, the user's video
"Deform Feature in SolidWorks": a straight tapered rod, its centre line
the *initial curve*, is bent onto a drawn S-shaped *target curve*).

The node holds the bodies to deform (its children) and two curves as
rows of points in its own frame: ``initial`` and ``target``. Every
vertex of the bodies is expressed in the moving frame (tangent, normal,
binormal; parallel transport, so a straight rod keeps its roll) of the
initial curve at the point of the curve nearest it, then rebuilt on the
target curve at the same fraction of the curve's length — so the initial
curve's two ends land on the target's two ends, a body beyond an end
continues along that end's tangent, and a part of the body where the two
curves coincide stays where it is. Meshes are first refined along the
curve (``detail`` mm, 0 = automatic) so the bend is smooth.

Baked like the other kit wrappers: ``kcad_curve_deform(initial=,
target=, detail=, points=, faces=) { bodies }``.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

from . import bakedkit

_DEFAULTS = {"initial": [], "target": [], "detail": 0.0}
#: samples along each curve
SAMPLES = 400
#: cap on the refined mesh (triangles)
MAX_TRIS = 150_000


# ------------------------------------------------------------- curves

def _resample(points, n=SAMPLES):
    """(n + 1) points at equal arclength along the polyline, and its
    length."""
    import numpy as np
    p = np.asarray(points, float)
    seg = np.linalg.norm(np.diff(p, axis=0), axis=1)
    keep = np.concatenate([[True], seg > 1e-12])
    p = p[keep]
    seg = np.linalg.norm(np.diff(p, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    total = float(cum[-1])
    t = np.linspace(0.0, total, n + 1)
    out = np.stack([np.interp(t, cum, p[:, i]) for i in range(3)], axis=1)
    return out, total


def _frames(pts):
    """Tangent, normal, binormal at each sample (parallel transport)."""
    import numpy as np
    d = np.gradient(pts, axis=0, edge_order=2)
    T = d / np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-12)
    ref = np.array([0.0, 0.0, 1.0]) if abs(T[0][2]) < 0.9 \
        else np.array([0.0, 1.0, 0.0])
    N0 = ref - T[0] * float(ref @ T[0])
    N0 /= np.linalg.norm(N0)
    N = np.empty_like(T)
    N[0] = N0
    for i in range(1, len(T)):
        n = N[i - 1] - T[i] * float(N[i - 1] @ T[i])
        m = np.linalg.norm(n)
        N[i] = n / m if m > 1e-9 else N[i - 1]
    B = np.cross(T, N)
    return T, N, B


def _start_alignment(TP, NP, TQ, NQ):
    """The rotation that carries the initial frame onto the target's at
    their starts, as (R) with  R @ [T, N, B]_P = [T, N, B]_Q — the
    frames are made to agree there by turning the target's frames about
    its tangent so that the roll matches the minimal turn from P to Q.
    Returned as the angle (rad) to twist Q's normal about its tangent."""
    import numpy as np
    t0, t1 = TP[0], TQ[0]
    c = float(t0 @ t1)
    axis = np.cross(t0, t1)
    s = np.linalg.norm(axis)
    if s < 1e-9:
        n_img = NP[0] if c > 0 else NP[0]
    else:
        axis = axis / s
        ang = math.atan2(s, c)
        n = NP[0]
        n_img = (n * math.cos(ang) + np.cross(axis, n) * math.sin(ang)
                 + axis * float(axis @ n) * (1 - math.cos(ang)))
    # the angle from Q's own normal to the image, about Q's tangent
    a = float(np.cross(NQ[0], n_img) @ t1)
    b = float(NQ[0] @ n_img)
    return math.atan2(a, b)


def _twist(T, N, angle):
    """Frames turned by *angle* about the tangent."""
    import numpy as np
    c, s = math.cos(angle), math.sin(angle)
    N2 = N * c + np.cross(T, N) * s
    return N2, np.cross(T, N2)


def deform_points(verts, initial, target):
    """*verts* (n x 3) carried from the initial curve onto the target."""
    import numpy as np
    P, LP = _resample(initial)
    Q, LQ = _resample(target)
    if LP < 1e-9 or LQ < 1e-9:
        return np.asarray(verts, float)
    TP, NP, BP = _frames(P)
    TQ, NQ, BQ = _frames(Q)
    NQ, BQ = _twist(TQ, NQ, _start_alignment(TP, NP, TQ, NQ))
    K = len(P) - 1
    ds = LP / K
    dsq = LQ / K
    ratio = LQ / LP
    v = np.asarray(verts, float)
    out = np.empty_like(v)
    A = P[:-1]
    D = P[1:] - P[:-1]
    DD = np.maximum((D * D).sum(axis=1), 1e-18)
    chunk = max(1, 4_000_000 // (K + 1))
    for lo in range(0, len(v), chunk):
        x = v[lo:lo + chunk]
        # projection onto every segment (clamped, but open at the ends)
        u = ((x[:, None, :] - A[None]) * D[None]).sum(axis=2) / DD[None]
        uc = np.clip(u, 0.0, 1.0)
        uc[:, 0] = np.minimum(u[:, 0], 1.0)
        uc[:, -1] = np.maximum(u[:, -1], 0.0)
        foot = A[None] + uc[:, :, None] * D[None]
        dist = ((x[:, None, :] - foot) ** 2).sum(axis=2)
        k = dist.argmin(axis=1)
        idx = np.arange(len(x))
        uk = uc[idx, k]
        s = (k + uk) * ds                       # arclength, may be < 0 / > LP
        f = np.clip(s / ds, 0, K)
        i0 = np.minimum(f.astype(int), K - 1)
        w = (f - i0)[:, None]

        def at(arr):
            r = arr[i0] * (1 - w) + arr[i0 + 1] * w
            return r / np.maximum(np.linalg.norm(r, axis=1,
                                                 keepdims=True), 1e-12)
        T, N, B = at(TP), at(NP), at(BP)
        base = P[i0] * (1 - w) + P[i0 + 1] * w
        extra = (s - np.clip(s, 0, LP))[:, None]
        base = base + T * extra                 # past an end: its tangent
        d = x - base
        a, b, c = (d * T).sum(1), (d * N).sum(1), (d * B).sum(1)
        sq = s * ratio
        fq = np.clip(sq / dsq, 0, K)
        j0 = np.minimum(fq.astype(int), K - 1)
        wq = (fq - j0)[:, None]

        def atq(arr):
            r = arr[j0] * (1 - wq) + arr[j0 + 1] * wq
            return r / np.maximum(np.linalg.norm(r, axis=1,
                                                 keepdims=True), 1e-12)
        Tq, Nq, Bq = atq(TQ), atq(NQ), atq(BQ)
        pq = Q[j0] * (1 - wq) + Q[j0 + 1] * wq
        extq = (sq - np.clip(sq, 0, LQ))[:, None]
        pq = pq + Tq * extq
        out[lo:lo + chunk] = (pq + Tq * (a * ratio)[:, None]
                              + Nq * b[:, None] + Bq * c[:, None])
    return out


# --------------------------------------------------------------- node

def _rows(node, key):
    rows = []
    for r in node.params.get(key) or []:
        try:
            rows.append([float(r[0]), float(r[1]), float(r[2])])
        except (TypeError, ValueError, IndexError):
            continue
    return rows


def _compute(node, env):
    from . import deform
    tris = bakedkit.source_tris(node, env)
    init, targ = _rows(node, "initial"), _rows(node, "target")
    if not tris or len(init) < 2 or len(targ) < 2:
        return [tuple(t[:3]) for t in tris]
    _P, LP = _resample(init)
    detail = bakedkit.num(node, env, "detail", 0.0)
    if detail <= 0:
        detail = max(LP / 80.0, 0.4)
    tris = [tuple(t[:3]) for t in tris]
    for _ in range(6):
        fine = deform.split_long_edges(tris, detail)
        if len(fine) <= MAX_TRIS:
            break
        detail *= 1.6
    import numpy as np
    verts = {}
    for t in fine:
        for v in t:
            verts.setdefault(v, len(verts))
    keys = list(verts)
    moved = deform_points(np.array(keys, float), init, targ)
    pt = [tuple(float(c) for c in m) for m in moved]
    return [tuple(pt[verts[v]] for v in t) for t in fine]


def _check(node, env):
    if len(_rows(node, "initial")) < 2:
        return "Deform: the initial curve needs at least two points"
    if len(_rows(node, "target")) < 2:
        return "Deform: the target curve needs at least two points"
    return None


KIT = bakedkit.make(
    "curve_deform", "Deform (curve to curve)", "mdi.vector-curve", _DEFAULTS,
    [("initial", "Initial curve (points)", "rows", ["X", "Y", "Z"], None),
     ("target", "Target curve (points)", "rows", ["X", "Y", "Z"], None),
     ("detail", "Refine to (mm, 0 = automatic)", "float", 0.0, 1e6)],
    _compute, check=_check, inexact_ok=True)


# ------------------------------------------------- curves from sketches

def sketch_curve(nodes, steps=24):
    """One polyline (world coordinates) from sketch *nodes* — lines and
    open arcs chained end to end (a construction line counts). None when
    they do not form one chain."""
    from . import mesh, sketch_arc
    pieces = []
    for n in nodes:
        if n.type == "regions":
            continue
        if n.type != "line":
            continue
        pts2 = sketch_arc.node_points(n, steps=steps)
        m = mesh.ancestor_matrix(n)
        pieces.append([tuple(mesh.mat_apply(m, (x, y, 0.0)))
                       for x, y in pts2])
    if not pieces:
        return None
    return _chain(pieces)


def _chain(pieces, tol=1e-3):
    """Join point lists end to end into one polyline."""
    def near(a, b):
        return sum((p - q) ** 2 for p, q in zip(a, b)) <= tol * tol
    rest = [list(p) for p in pieces]
    chain = rest.pop(0)
    while rest:
        for i, p in enumerate(rest):
            if near(chain[-1], p[0]):
                chain += p[1:]
            elif near(chain[-1], p[-1]):
                chain += p[::-1][1:]
            elif near(chain[0], p[-1]):
                chain = p[:-1] + chain
            elif near(chain[0], p[0]):
                chain = p[::-1][:-1] + chain
            else:
                continue
            rest.pop(i)
            break
        else:
            return None
    return chain


def to_frame(points, node):
    """World *points* in the frame the children of *node* live in."""
    import numpy as np
    from . import mesh
    m = np.array(mesh.ancestor_matrix(node), float)
    inv = np.linalg.inv(m)
    return [[float(c) for c in (inv @ np.array([*p, 1.0]))[:3]]
            for p in points]


def orient(initial, target):
    """*target* turned round if its far end is the one nearest the start
    of *initial* (SolidWorks' curve direction)."""
    def d(a, b):
        return sum((x - y) ** 2 for x, y in zip(a, b))
    if d(initial[0], target[0]) > d(initial[0], target[-1]):
        return target[::-1]
    return target


def make(model, bodies, initial, target):
    """Wrap *bodies* in a Deform node holding the two curves (points in
    WORLD coordinates, as sketch_curve gives them). Returns the node."""
    node = model.wrap_nodes(list(bodies), "curve_deform")
    if node is None:
        return None
    init = [[round(c, 4) for c in p] for p in to_frame(initial, node)]
    targ = [[round(c, 4) for c in p] for p in
            orient(init, to_frame(target, node))]
    node.params.update(initial=init, target=targ)
    node.name = "Deform"
    model.node_changed.emit(node)
    return node

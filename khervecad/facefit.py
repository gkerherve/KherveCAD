"""Fitting a face to photographs: landmarks on the model are pulled to
where the same landmarks are in the pictures.

The human node's face is linear in its slider weights, so with the
landmark positions as a function of the weights, a photo's landmarks
(eye corners, nose tip, mouth corners, chin, ...) read off a reference
image on an axis plane become a small least-squares problem: choose
the weights, within their range, that project the model's landmarks
onto the picture's. What the sliders cannot reach — the residual — is
carried by the node's warp rows, a smooth field that moves each
landmark the rest of the way. This is how a generic head becomes a
particular person: FaceGen's approach, without a face database.

Pure numbers, Qt-free; the MCP tool and the human node do the rest.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

#: the sliders a fit adjusts unless told otherwise: the proportions a
#: photo pins down, not the fine surface detail
DEFAULT_SLIDERS = (
    "head-scale-horiz", "head-scale-vert", "head-scale-depth", "head-fat",
    "head-oval", "head-round", "head-square",
    "forehead-scale-vert", "forehead-temple",
    "eye-trans-side", "eye-trans-vert", "eye-scale",
    "nose-scale-horiz", "nose-scale-vert", "nose-scale-depth",
    "nose-trans-vert", "nose-width2", "nose-point-vert",
    "mouth-scale-horiz", "mouth-scale-vert", "mouth-trans-vert",
    "chin-height", "chin-width", "chin-prominent", "chin-jaw-drop",
    "cheek-volume", "cheek-bones", "neck-scale-horiz",
)


def _solve(a, b):
    n = len(a)
    m = [list(row) + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-12:
            continue
        m[col], m[piv] = m[piv], m[col]
        for r in range(n):
            if r != col and m[r][col]:
                k = m[r][col] / m[col][col]
                for c in range(col, n + 1):
                    m[r][c] -= k * m[col][c]
    return [m[i][n] / m[i][i] if abs(m[i][i]) > 1e-12 else 0.0
            for i in range(n)]


def least_squares(jac, residual, lam=0.3, lo=-1.0, hi=1.0, rounds=6):
    """Weights w minimising |J w + r|² + lam' |w|² with lo <= w <= hi
    (each a number or a list per weight): a ridge solve, then the
    weights that left the box are pinned there and the rest solved
    again (a few rounds settle it). *lam* is relative to the problem —
    it multiplies the mean diagonal of JᵀJ — so 0.3 means the same
    stiffness whatever the units."""
    n = len(jac[0]) if jac else 0
    if n == 0:
        return []
    m = len(jac)
    los = list(lo) if isinstance(lo, (list, tuple)) else [lo] * n
    his = list(hi) if isinstance(hi, (list, tuple)) else [hi] * n
    diag = [sum(jac[k][i] * jac[k][i] for k in range(m)) for i in range(n)]
    ridge = lam * (sum(diag) / n if n else 1.0) + 1e-9
    fixed = {}
    for _ in range(rounds):
        free = [i for i in range(n) if i not in fixed]
        if not free:
            break
        # residual with the fixed weights folded in
        r = [residual[k] + sum(jac[k][i] * v for i, v in fixed.items())
             for k in range(m)]
        a = [[sum(jac[k][i] * jac[k][j] for k in range(m))
              + (ridge if i == j else 0.0) for j in free] for i in free]
        b = [-sum(jac[k][i] * r[k] for k in range(m)) for i in free]
        sol = _solve(a, b)
        clipped = False
        for i, v in zip(free, sol):
            if v < los[i]:
                fixed[i] = los[i]
                clipped = True
            elif v > his[i]:
                fixed[i] = his[i]
                clipped = True
        if not clipped:
            w = dict(fixed)
            w.update(zip(free, sol))
            return [w[i] for i in range(n)]
    w = dict(fixed)
    for i in range(n):
        w.setdefault(i, 0.0)
    return [w[i] for i in range(n)]


def fit(project, sliders, lam=0.3, delta=1.0, bounds=None):
    """*project(weights)* -> residual vector (model minus observed, in
    mm) for a weight dict; the face is linear in its weights, so one
    difference per slider is the exact Jacobian. *bounds* maps a
    parameter to its (lo, hi) — a shape slider runs 0..1, an angle
    ±40 — else ±1; *delta* likewise (a number, or a dict per name).
    Returns ``(weights dict, rms before, rms after)``."""
    base = project({})
    m = len(base)
    if m == 0 or not sliders:
        return {}, _rms(base), _rms(base)
    bounds = bounds or {}
    jac_cols = []
    steps = []
    for name in sliders:
        step = delta.get(name, 1.0) if isinstance(delta, dict) else delta
        steps.append(step)
        col = project({name: step})
        jac_cols.append([(col[k] - base[k]) / step for k in range(m)])
    jac = [[jac_cols[i][k] for i in range(len(sliders))] for k in range(m)]
    lo = [bounds.get(name, (-1.0, 1.0))[0] for name in sliders]
    hi = [bounds.get(name, (-1.0, 1.0))[1] for name in sliders]
    w = least_squares(jac, base, lam, lo, hi)
    weights = {name: round(v, 4) for name, v in zip(sliders, w)
               if abs(v) > 1e-4}
    after = project(weights)
    return weights, _rms(base), _rms(after)


def _rms(r):
    return (sum(v * v for v in r) / len(r)) ** 0.5 if r else 0.0


def residual_warp(errors, min_move=0.5) -> list:
    """Warp rows ``[x, y, z, dx, dy, dz]`` (local frame) that carry
    each landmark at *errors* — ``[(local point, local displacement
    still needed)]`` — the rest of the way; tiny ones are dropped."""
    rows = []
    for point, move in errors:
        if sum(v * v for v in move) ** 0.5 < min_move:
            continue
        rows.append([round(v, 3) for v in point]
                    + [round(v, 3) for v in move])
    return rows

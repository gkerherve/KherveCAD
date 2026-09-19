"""Shrinkwrap — one mesh pressed onto another (Blender's Shrinkwrap).

The `shrinkwrap` wrapper's FIRST child is what moves; the rest is the
target. Every vertex of the first goes

* ``nearest`` — to the closest point of the target's surface, or
* ``project`` — along a ray (the vertex's own normal, or ±x/±y/±z) to
  the nearest place it meets the target; a ray that misses stays put,

then ``offset`` mm out along the target's normal there. ``keep`` says
which vertices move: ``all`` (on the surface), ``outside`` (only those
inside the target or nearer than the offset — a garment, a cap or a
decal that must never sink into the body under it) or ``inside``.

This is what the Kherve characters were missing: clothes, hair caps and
stickers built round a body sat a guessed distance off it, and a pose or
a sculpt stroke left them floating or buried.

Closest points come from a uniform grid of the target's triangles, each
cell's vertices searched ring by ring (a triangle outside ring r is at
least r cells away, so a hit that near is final) with Ericson's
closest-point-on-triangle vectorised in numpy. Inside/outside is ray
parity. Rays are Manifold's (csg.py, C++) when it is installed, numpy's
Möller-Trumbore otherwise. Qt-free.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

import numpy as np

MODES = ("nearest", "project")
AXES = ("normal", "+x", "-x", "+y", "-y", "+z", "-z", "x", "y", "z")
KEEPS = ("all", "outside", "inside")

#: target triangles per grid cell, on average
_PER_CELL = 4
#: a direction no mesh edge lies along (ray parity must not graze one)
_PARITY_DIR = np.array([0.5773, 0.5774, 0.5775]) / np.linalg.norm(
    [0.5773, 0.5774, 0.5775])


# ------------------------------------------------------ closest points

def closest_on_triangles(p, a, b, c):
    """Closest points of triangles (a, b, c) — arrays (T, 3) — to the
    points *p* (Q, 3): returns (Q, T, 3). Ericson, Real-Time Collision
    Detection 5.1.5, every Voronoi region as a mask."""
    p = p[:, None, :]
    a, b, c = a[None], b[None], c[None]
    ab, ac, ap = b - a, c - a, p - a
    d1 = np.einsum("qtk,qtk->qt", np.broadcast_to(ab, ap.shape), ap)
    d2 = np.einsum("qtk,qtk->qt", np.broadcast_to(ac, ap.shape), ap)
    bp = p - b
    d3 = np.einsum("qtk,qtk->qt", np.broadcast_to(ab, bp.shape), bp)
    d4 = np.einsum("qtk,qtk->qt", np.broadcast_to(ac, bp.shape), bp)
    cp = p - c
    d5 = np.einsum("qtk,qtk->qt", np.broadcast_to(ab, cp.shape), cp)
    d6 = np.einsum("qtk,qtk->qt", np.broadcast_to(ac, cp.shape), cp)
    va = d3 * d6 - d5 * d4
    vb = d5 * d2 - d1 * d6
    vc = d1 * d4 - d3 * d2
    with np.errstate(divide="ignore", invalid="ignore"):
        denom = va + vb + vc
        v = np.where(denom != 0, vb / denom, 0.0)
        w = np.where(denom != 0, vc / denom, 0.0)
        out = a + ab * v[..., None] + ac * w[..., None]
        t_bc = (d4 - d3) / ((d4 - d3) + (d5 - d6))
        m = (va <= 0) & ((d4 - d3) >= 0) & ((d5 - d6) >= 0)
        out = np.where(m[..., None], b + (c - b) * t_bc[..., None], out)
        t_ac = d2 / (d2 - d6)
        m = (vb <= 0) & (d2 >= 0) & (d6 <= 0)
        out = np.where(m[..., None], a + ac * t_ac[..., None], out)
        m = (d6 >= 0) & (d5 <= d6)
        out = np.where(m[..., None], np.broadcast_to(c, out.shape), out)
        t_ab = d1 / (d1 - d3)
        m = (vc <= 0) & (d1 >= 0) & (d3 <= 0)
        out = np.where(m[..., None], a + ab * t_ab[..., None], out)
        m = (d3 >= 0) & (d4 <= d3)
        out = np.where(m[..., None], np.broadcast_to(b, out.shape), out)
        m = (d1 <= 0) & (d2 <= 0)
        out = np.where(m[..., None], np.broadcast_to(a, out.shape), out)
    return out


class Target:
    """A target surface: its triangles, face normals, a grid for
    closest-point queries and a ray caster."""

    def __init__(self, tris):
        t = np.asarray(tris, dtype=np.float64).reshape(-1, 3, 3)
        self.a, self.b, self.c = t[:, 0], t[:, 1], t[:, 2]
        n = np.cross(self.b - self.a, self.c - self.a)
        length = np.linalg.norm(n, axis=1)
        keep = length > 1e-15
        self.a, self.b, self.c = self.a[keep], self.b[keep], self.c[keep]
        self.n = n[keep] / length[keep, None]
        self.tris = [tuple(map(tuple, row)) for row in
                     np.stack([self.a, self.b, self.c], axis=1)]
        lo = np.minimum(np.minimum(self.a, self.b), self.c)
        hi = np.maximum(np.maximum(self.a, self.b), self.c)
        self.lo, self.hi = lo.min(axis=0), hi.max(axis=0)
        span = np.maximum(self.hi - self.lo, 1e-9)
        cells = max(1.0, len(self.a) / _PER_CELL)
        self.size = float((span.prod() / cells) ** (1 / 3))
        self.size = max(self.size, float(span.max()) / 256, 1e-6)
        self.grid = {}
        c0 = np.floor((lo - self.lo) / self.size).astype(int)
        c1 = np.floor((hi - self.lo) / self.size).astype(int)
        for i, (u, w) in enumerate(zip(c0.tolist(), c1.tolist())):
            for x in range(u[0], w[0] + 1):
                for y in range(u[1], w[1] + 1):
                    for z in range(u[2], w[2] + 1):
                        self.grid.setdefault((x, y, z), []).append(i)
        self.extent = int(np.ceil((span / self.size).max())) + 2
        self._solid = None

    def _cells_at(self, centre, r):
        """Triangle ids in the shell of Chebyshev radius *r*."""
        cx, cy, cz = centre
        out = []
        for x in range(cx - r, cx + r + 1):
            for y in range(cy - r, cy + r + 1):
                edge = r in (abs(x - cx), abs(y - cy))
                for z in ((range(cz - r, cz + r + 1)) if edge
                          else (cz - r, cz + r)):
                    out.extend(self.grid.get((x, y, z), ()))
        return out

    def nearest(self, pts):
        """(closest points (Q, 3), triangle index (Q,)) for *pts*."""
        pts = np.asarray(pts, dtype=np.float64).reshape(-1, 3)
        cells = np.floor((pts - self.lo) / self.size).astype(int)
        best_d = np.full(len(pts), np.inf)
        best_q = np.zeros_like(pts)
        best_t = np.zeros(len(pts), dtype=int)
        groups = {}
        for i, cell in enumerate(map(tuple, cells.tolist())):
            groups.setdefault(cell, []).append(i)
        for cell, members in groups.items():
            members = np.array(members)
            seen = set()
            # a query far outside the grid starts where the grid begins
            gap = max(0, int(np.max(np.maximum(
                -np.array(cell), np.array(cell) - self.extent))))
            r = gap
            while True:
                cand = [t for t in self._cells_at(cell, r) if t not in seen]
                seen.update(cand)
                if cand:
                    cand = np.array(cand)
                    q = closest_on_triangles(pts[members], self.a[cand],
                                             self.b[cand], self.c[cand])
                    d = np.linalg.norm(q - pts[members][:, None], axis=2)
                    k = d.argmin(axis=1)
                    dk = d[np.arange(len(members)), k]
                    better = dk < best_d[members]
                    upd = members[better]
                    best_d[upd] = dk[better]
                    best_q[upd] = q[np.arange(len(members)), k][better]
                    best_t[upd] = cand[k[better]]
                # beyond ring r everything is at least r cells away
                if np.all(best_d[members] <= r * self.size) or \
                        r > self.extent + gap + 1:
                    break
                r += 1
        return best_q, best_t

    # ---------------------------------------------------------- rays

    def _manifold(self):
        from . import csg
        if self._solid is None and csg.available():
            self._solid = csg.to_manifold(
                [(t, None, False) for t in self.tris], {}) or False
        return self._solid or None

    def hits(self, origin, direction, reach):
        """[(distance, point, normal)] along the segment from *origin*
        for *reach* along the unit *direction*, nearest first."""
        o = np.asarray(origin, dtype=np.float64)
        d = np.asarray(direction, dtype=np.float64)
        solid = self._manifold()
        if solid is not None:
            end = o + d * reach
            # Manifold's distance is the fraction of the segment
            return [(h.distance * reach, np.asarray(h.position),
                     np.asarray(h.normal))
                    for h in solid.ray_cast(tuple(o), tuple(end))]
        return self._np_hits(o, d, reach)

    def _np_hits(self, o, d, reach):
        e1, e2 = self.b - self.a, self.c - self.a
        pv = np.cross(d, e2)
        det = np.einsum("tk,tk->t", e1, pv)
        ok = np.abs(det) > 1e-14
        inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
        tv = o - self.a
        u = np.einsum("tk,tk->t", tv, pv) * inv
        qv = np.cross(tv, e1)
        v = (qv @ d) * inv
        t = np.einsum("tk,tk->t", e2, qv) * inv
        m = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t >= 0) & \
            (t <= reach)
        out = [(float(t[i]), o + d * t[i], self.n[i])
               for i in np.nonzero(m)[0]]
        return sorted(out, key=lambda h: h[0])

    def inside(self, pts):
        """Ray parity per point (the target must be closed)."""
        reach = float(np.linalg.norm(self.hi - self.lo)) * 2 + 1.0
        out = []
        for p in np.asarray(pts, dtype=np.float64).reshape(-1, 3):
            count = len(self._dedupe(self.hits(p, _PARITY_DIR, reach)))
            out.append(count % 2 == 1)
        return np.array(out, dtype=bool)

    @staticmethod
    def _dedupe(hits):
        """One crossing where the ray passes an edge two faces share."""
        out = []
        for h in hits:
            if not out or abs(h[0] - out[-1][0]) > 1e-9:
                out.append(h)
        return out


# ---------------------------------------------------------- the wrap

def _vertex_normals(points, faces):
    acc = np.zeros_like(points)
    for f in faces:
        a, b, c = points[f[0]], points[f[1]], points[f[2]]
        n = np.cross(b - a, c - a)
        for v in f:
            acc[v] += n
    length = np.linalg.norm(acc, axis=1)
    length[length == 0] = 1.0
    return acc / length[:, None]


def _axis(axis):
    axis = str(axis)
    sign = -1.0 if axis.startswith("-") else 1.0
    key = axis.lstrip("+-")
    vec = {"x": (1, 0, 0), "y": (0, 1, 0), "z": (0, 0, 1)}.get(key)
    return None if vec is None else sign * np.array(vec, dtype=float), \
        not axis[:1] in "+-"


def shrinkwrap(tris, target_tris, mode="nearest", offset=0.0,
               keep="all", axis="normal"):
    """The triangles of *tris* with every vertex moved onto the target
    (see the module docstring). Vertices stay welded, so a closed mesh
    stays closed. CCW triangles in and out."""
    from .decimate import weld, triangles
    tris = list(tris)
    if not tris or not target_tris:
        return tris
    target = Target(target_tris)
    pts, faces = weld(tris)
    points = np.asarray(pts, dtype=np.float64)
    moved = points.copy()
    if mode == "project":
        normals = _vertex_normals(points, faces)
        reach = float(np.linalg.norm(target.hi - target.lo)
                      + np.linalg.norm(points.max(0) - points.min(0)))
        fixed, both = _axis(axis)
        for i, p in enumerate(points):
            d = fixed if fixed is not None else normals[i]
            dirs = (d, -d) if (both or fixed is None) else (d,)
            best = None
            for dv in dirs:
                found = target.hits(p, dv, reach)
                if found and (best is None or found[0][0] < best[0]):
                    best = found[0]
            if best is None:
                continue
            _dist, hit, normal = best
            moved[i] = np.asarray(hit) + offset * np.asarray(normal)
        if keep != "all":
            inside = target.inside(points)
            stay = ~inside if keep == "outside" else inside
            moved[stay] = points[stay]
    else:
        q, t = target.nearest(points)
        n = target.n[t]
        dest = q + offset * n if keep != "inside" else q - offset * n
        if keep == "all":
            moved = dest
        else:
            inside = target.inside(points)
            gap = np.einsum("qk,qk->q", points - q, n)
            if keep == "outside":
                move = inside | (gap < offset)
            else:
                move = ~inside | (gap > -offset)
            moved[move] = dest[move]
    return triangles([tuple(p) for p in moved.tolist()], faces)


def split(parts):
    """(wrapped rows, target rows) from a shrinkwrap's operands' meshes:
    the first operand moves, the rest is the target."""
    if not parts:
        return [], []
    return parts[0], [row for rows in parts[1:] for row in rows]


def distance_to(target_tris, pts) -> list:
    """Distance from each point to the target surface (tests, MCP)."""
    q, _t = Target(target_tris).nearest(pts)
    return [math.dist(a, b) for a, b in zip(np.asarray(pts).tolist(),
                                            q.tolist())]

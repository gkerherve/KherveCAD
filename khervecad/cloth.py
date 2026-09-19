"""Cloth — a sheet that drapes over what is under it (Blender's Cloth).

The `cloth` wrapper's FIRST child is the cloth as a flat 2D shape (a
square tablecloth, a round one, a cape's outline), laid out as ONE
sheet of ``detail`` mm triangles at z = ``height``; the rest are
colliders, drawn as they are. The sheet falls under gravity and settles
over them — a tablecloth over a table, a cape over shoulders, a sheet
over a sofa, a flag hanging from pinned corners — and is then given its
``thickness`` (both skins and the rim), a closed printable solid. (A
thin 3D plate would not do: its two skins meet only at the rim, and the
top one falls straight through the bottom.)

Position-based dynamics (Müller et al. 2007, what Blender's cloth and
most game cloth reduce to): Verlet steps under gravity with damping,
every edge kept at its rest length by `iterations` Jacobi passes (the
cloth stretches little but bends freely), vertices inside a ``pin`` box
held where they are, and collisions resolved as positions:

* the colliders are voxelised once by winding number
  (remesh.occupancy) and grown by ``offset`` — each step, a vertex's
  cell says in one numpy lookup whether it has come too close;
* only those vertices are moved to the nearest point of the colliders'
  surface + ``offset`` along its normal (shrinkwrap.Target), and lose
  most of their sliding speed (``friction``);
* ``floor`` adds the ground under the colliders' lowest point.

Vertices stay welded, so a closed plate stays closed. Baked like the
other deformers; steps and resolution bound the cost. Qt-free.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import numpy as np

#: mm / s², and the time step (s) — a step moves a free vertex g dt²
GRAVITY = 9810.0
DT = 1.0 / 60.0
DAMPING = 0.985
#: Laplacian passes smoothing the settled cloth
SMOOTH_PASSES = 3
#: the collider grid has at most this many cells
GRID_CELLS = 1_500_000


class Colliders:
    """Colliders as a grown occupancy grid plus their exact surface."""

    def __init__(self, tris, offset, floor=None):
        from .remesh import occupancy
        from .shrinkwrap import Target
        self.floor = floor
        self.offset = float(offset)
        self.band = 0.5          # mm of "still touching" (see resolve)
        self.target = Target(tris) if tris else None
        self.solid = None
        if tris:
            from . import csg
            if csg.available():
                self.solid = csg.to_manifold(
                    [(t, None, False) for t in tris], {})
        self.occ = None
        if not tris:
            return
        pts = np.asarray(tris, dtype=np.float64).reshape(-1, 3)
        lo, hi = pts.min(axis=0), pts.max(axis=0)
        grow = self.offset * 1.5 + 1e-6
        cell = max(self.offset / 2.0, 1e-3)
        while True:
            dims = tuple(int(np.ceil((hi[i] - lo[i] + 2 * grow) / cell)) + 2
                         for i in range(3))
            if dims[0] * dims[1] * dims[2] <= GRID_CELLS:
                break
            cell *= 1.3
        self.cell = cell
        self.lo = lo - grow - cell
        occ = occupancy(tris, self.lo, cell, dims)
        # grow by the offset: every cell within it of a solid one
        r = int(np.ceil(self.offset / cell)) + 1
        grown = occ.copy()
        for axis in range(3):
            base = grown.copy()
            for s in range(1, r + 1):
                grown |= np.roll(base, s, axis=axis)
                grown |= np.roll(base, -s, axis=axis)
        self.occ = grown
        self.dims = dims

    def close(self, p):
        """Mask of the vertices *p* (N, 3) that are in or near a
        collider."""
        near = np.zeros(len(p), dtype=bool)
        if self.occ is not None:
            idx = np.floor((p - self.lo) / self.cell).astype(np.int64)
            ok = np.all((idx >= 0) & (idx < np.array(self.dims)), axis=1)
            near[ok] = self.occ[idx[ok, 0], idx[ok, 1], idx[ok, 2]]
        if self.floor is not None:
            near |= p[:, 2] < self.floor + self.offset
        return near

    def _entry(self, a, b):
        """Where the path a -> b first enters the colliders: (point,
        normal), or None. The face a vertex came through is the one to
        put it back on; the NEAREST face threw a vertex that landed by a
        table's edge out sideways, and the cloth slid off."""
        if self.solid is None:
            return None
        d = b - a
        length = float(np.linalg.norm(d))
        if length < 1e-9:
            return None
        start = a - d / length * self.offset * 2
        reach = length + self.offset * 2
        hits = self.solid.ray_cast(tuple(start), tuple(start + d / length
                                                       * reach))
        for h in hits:
            n = np.asarray(h.normal)
            if np.dot(n, d) < 0:                 # entering, not leaving
                return np.asarray(h.position), n
        return None

    def resolve(self, p, mask, normal, depth, prev=None):
        """Move p[mask] out to the surface + offset — back along its own
        path when it came from outside (*prev*), else to the nearest
        point. Records, per vertex in contact, the surface normal and
        the deepest push-out this step (for friction). Returns the
        contact mask."""
        hit = np.zeros(len(p), dtype=bool)
        ids = np.nonzero(mask)[0]
        if len(ids) and self.target is not None:
            q, t = self.target.nearest(p[ids])
            n = self.target.n[t]
            if prev is not None and self.solid is not None:
                gap0 = np.einsum("ij,ij->i", p[ids] - q, n)
                for k in np.nonzero(gap0 < 0)[0]:
                    got = self._entry(prev[ids[k]], p[ids[k]])
                    if got is not None:
                        q[k], n[k] = got
            gap = np.einsum("ij,ij->i", p[ids] - q, n)
            bad = gap < self.offset
            sel = ids[bad]
            p[sel] = q[bad] + n[bad] * self.offset
            depth[sel] = np.maximum(depth[sel], self.offset - gap[bad])
            # resting ON the surface is contact too — with room for the
            # hair the constraints lift it by, or a resting vertex misses
            # its friction for a frame and the cloth creeps
            touch = gap < self.offset * 1.5 + self.band
            normal[ids[touch]] = n[touch]
            hit[ids[touch]] = True
        if self.floor is not None:
            level = self.floor + self.offset
            under = p[:, 2] < level
            depth[under] = np.maximum(depth[under], level - p[under, 2])
            p[under, 2] = level
            touch = p[:, 2] < level + self.offset * 0.5 + self.band
            normal[touch] = (0.0, 0.0, 1.0)
            hit |= touch
        return hit


def sheet(outlines, spacing, z):
    """(points, faces) of the 2D *outlines* (CCW solids, CW holes) as
    one triangulated sheet at height *z*: a grid of *spacing* mm, the
    triangles whose centre is inside kept, the boundary vertices moved
    onto the outline so a round cloth is round, not stepped."""
    from .mesh import _inside
    pts = [p for o in outlines for p in o]
    if not pts:
        return [], []
    lo = [min(p[i] for p in pts) for i in range(2)]
    hi = [max(p[i] for p in pts) for i in range(2)]
    h = max(float(spacing), 1e-3)
    nx = max(int(np.ceil((hi[0] - lo[0]) / h)), 1)
    ny = max(int(np.ceil((hi[1] - lo[1]) / h)), 1)
    hx, hy = (hi[0] - lo[0]) / nx, (hi[1] - lo[1]) / ny

    def inside(q):
        return sum(1 for o in outlines if _inside(q, o)) % 2 == 1
    faces = []
    for j in range(ny):
        for i in range(nx):
            a = i + (nx + 1) * j
            b, c, d = a + 1, a + nx + 2, a + nx + 1
            for tri in ((a, b, c), (a, c, d)):
                cx = sum(lo[0] + (v % (nx + 1)) * hx for v in tri) / 3
                cy = sum(lo[1] + (v // (nx + 1)) * hy for v in tri) / 3
                if inside((cx, cy)):
                    faces.append(list(tri))
    used = sorted({v for f in faces for v in f})
    remap = {v: k for k, v in enumerate(used)}
    points = [[lo[0] + (v % (nx + 1)) * hx, lo[1] + (v // (nx + 1)) * hy,
               float(z)] for v in used]
    faces = [[remap[v] for v in f] for f in faces]
    # boundary vertices onto the outline
    uses = {}
    for f in faces:
        for a, b in ((f[0], f[1]), (f[1], f[2]), (f[2], f[0])):
            uses[(min(a, b), max(a, b))] = uses.get((min(a, b), max(a, b)),
                                                    0) + 1
    border = {v for k, n in uses.items() if n == 1 for v in k}
    segs = [(o[i], o[(i + 1) % len(o)]) for o in outlines
            for i in range(len(o))]
    for v in border:
        p = points[v]
        best = None
        for a, b in segs:
            ab = (b[0] - a[0], b[1] - a[1])
            t = ((p[0] - a[0]) * ab[0] + (p[1] - a[1]) * ab[1]) / \
                (ab[0] ** 2 + ab[1] ** 2 or 1e-12)
            t = min(max(t, 0.0), 1.0)
            q = (a[0] + ab[0] * t, a[1] + ab[1] * t)
            d = (q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2
            if best is None or d < best[0]:
                best = (d, q)
        if best is not None and best[0] <= h * h:
            p[0], p[1] = best[1]
    return points, faces


def thicken(points, faces, thickness):
    """A closed solid from the sheet: each vertex split ± half the
    thickness along its normal, the two skins and the rim."""
    x = np.asarray(points, dtype=np.float64)
    f = np.asarray(faces, dtype=np.int64)
    n = np.zeros_like(x)
    fn = np.cross(x[f[:, 1]] - x[f[:, 0]], x[f[:, 2]] - x[f[:, 0]])
    for k in range(3):
        np.add.at(n, f[:, k], fn)
    ln = np.linalg.norm(n, axis=1)
    ln[ln < 1e-12] = 1.0
    n /= ln[:, None]
    top = x + n * thickness / 2
    bot = x - n * thickness / 2
    tris = []
    for a, b, c in f.tolist():
        tris.append((tuple(top[a]), tuple(top[b]), tuple(top[c])))
        tris.append((tuple(bot[a]), tuple(bot[c]), tuple(bot[b])))
    uses = {}
    for a, b, c in f.tolist():
        for u, w in ((a, b), (b, c), (c, a)):
            uses[(u, w)] = uses.get((u, w), 0) + 1
    for (u, w) in list(uses):
        if (w, u) not in uses:                 # a border edge, u -> w
            tu, tw, bu, bw = (tuple(top[u]), tuple(top[w]),
                              tuple(bot[u]), tuple(bot[w]))
            tris.append((tu, bu, bw))
            tris.append((tu, bw, tw))
    return tris


def colour_edges(e, n):
    """Edge index arrays, one per colour: a greedy edge colouring (no
    two edges of a colour share a vertex)."""
    used = [set() for _ in range(n)]
    colour = np.empty(len(e), dtype=np.int64)
    for i, (a, b) in enumerate(e.tolist()):
        c = 0
        while c in used[a] or c in used[b]:
            c += 1
        colour[i] = c
        used[a].add(c)
        used[b].add(c)
    return [np.nonzero(colour == c)[0] for c in range(int(colour.max()) + 1)]


def simulate(points, faces, collider_tris, steps=80, offset=1.0,
             iterations=8, friction=0.6, pins=None, floor=True):
    """The sheet (*points*, *faces*) after *steps* frames over the
    colliders: the moved points."""
    if not faces:
        return points
    x = np.asarray(points, dtype=np.float64)
    rest = x.copy()
    prev = x.copy()
    f = np.asarray(faces, dtype=np.int64)
    e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    e = np.unique(np.sort(e, axis=1), axis=0)
    length = np.linalg.norm(x[e[:, 1]] - x[e[:, 0]], axis=1)
    colours = colour_edges(e, len(x))
    pinned = np.zeros(len(x), dtype=bool)
    for box in pins or []:
        a, b = np.asarray(box[0], float), np.asarray(box[1], float)
        lo, hi = np.minimum(a, b), np.maximum(a, b)
        pinned |= np.all((x >= lo) & (x <= hi), axis=1)
    ground = None
    if floor:
        ground = (min(v[2] for t in collider_tris for v in t)
                  if collider_tris else float(x[:, 2].min()) - 1e6)
    col = Colliders(list(collider_tris), offset, ground)
    # "small steps" (Macklin et al. 2019): each frame is `iterations`
    # substeps of one constraint pass, not one step with many passes —
    # the stretch a long hanging sheet builds up falls with the square
    # of the substep (8 passes of one big step let it hang 2-6x long)
    sub = max(int(iterations), 1)
    h = DT / sub
    g = np.array([0.0, 0.0, -GRAVITY * h * h])
    damp = DAMPING ** (1.0 / sub)
    # no vertex travels more than half an edge (or the offset) a
    # substep: a sheet falling fast lands deep in a table, and pushing it
    # out to the NEAREST face then throws it off the side
    vmax = max(float(np.median(length)) * 0.5, float(offset))
    hit = np.zeros(len(x), dtype=bool)
    normal = np.zeros_like(x)
    depth = np.zeros(len(x))
    mu_s, mu_k = float(friction), float(friction) * 0.6
    free = (~pinned).astype(np.float64)
    for _ in range(int(steps)):
        start = x.copy()
        for k in range(sub):
            v = (x - prev) * damp + g
            speed = np.linalg.norm(v, axis=1)
            fast = speed > vmax
            v[fast] *= (vmax / speed[fast])[:, None]
            prev = x.copy()
            x = x + v
            x[pinned] = rest[pinned]
            # Gauss-Seidel by edge colour: no two edges of a colour share
            # a vertex, so each colour is solved exactly in one numpy pass
            for sel in colours:
                a, b = e[sel, 0], e[sel, 1]
                d = x[b] - x[a]
                cur = np.linalg.norm(d, axis=1)
                cur[cur < 1e-12] = 1e-12
                wa, wb = free[a], free[b]
                w = wa + wb
                w[w == 0] = 1.0
                c = ((cur - length[sel]) / cur / w)[:, None] * d
                x[a] += c * wa[:, None]
                x[b] -= c * wb[:, None]
            if k % 2 == 1 or k == sub - 1:
                hit |= col.resolve(x, col.close(x), normal, depth, start)
                x[pinned] = rest[pinned]
        # position-based friction (Macklin et al. 2014) over the frame:
        # a contact's sliding is cancelled while it is under mu_s times
        # the depth it was pushed out by (static — a tablecloth stays on
        # its table), else cut by mu_k times it (kinetic)
        ids = np.nonzero(hit)[0]
        if len(ids):
            dx = x[ids] - start[ids]
            n = normal[ids]
            tang = dx - np.einsum("ij,ij->i", dx, n)[:, None] * n
            tl = np.linalg.norm(tang, axis=1)
            d = np.maximum(depth[ids], GRAVITY * DT * DT)
            stick = tl < mu_s * d
            scale = np.where(stick, 1.0, np.minimum(
                mu_k * d / np.maximum(tl, 1e-12), 1.0))
            x[ids] -= tang * scale[:, None]
            prev[ids] -= tang * scale[:, None]
        hit[:] = False
        depth[:] = 0.0
        x[pinned] = rest[pinned]
    # settle the crumple: a few Laplacian passes on the resting cloth
    # (the solver keeps edge lengths, not smoothness, and folds come out
    # with facet-sized noise), each followed by the collisions again
    deg = np.bincount(e.ravel(), minlength=len(x)).astype(np.float64)
    deg[deg == 0] = 1.0
    for _ in range(SMOOTH_PASSES):
        acc = np.zeros_like(x)
        np.add.at(acc, e[:, 0], x[e[:, 1]])
        np.add.at(acc, e[:, 1], x[e[:, 0]])
        x = x + 0.5 * (acc / deg[:, None] - x) * free[:, None]
        col.resolve(x, col.close(x), normal, depth)
    return x.tolist()


def drape(outlines, collider_tris, lift=20.0, detail=5.0,
          thickness=1.0, steps=120, substeps=12, offset=0.5, friction=0.6,
          pins=None, floor=True):
    """The cloth solid: the sheet from *outlines* laid *lift* mm over
    the colliders' highest point, draped, thickened."""
    top = max((v[2] for t in collider_tris for v in t), default=0.0)
    points, faces = sheet(outlines, detail, top + float(lift))
    if not faces:
        return []
    # the sheet's surface must clear the colliders by half its thickness
    moved = simulate(points, faces, collider_tris, steps,
                     max(offset, 0.0) + thickness / 2.0, substeps,
                     friction=friction, pins=pins, floor=floor)
    return thicken(moved, faces, thickness)

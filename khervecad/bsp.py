"""BSP tree — a correct painter's order for the 3D preview.

The built-in viewer paints triangles back to front (no OpenGL, no
z-buffer). Sorting whole triangles by centroid depth breaks whenever a
large face meets a small feature sitting just in front of it: the big
triangle's centroid is often *nearer* the camera than the small one's,
so it is painted last and covers the feature (a pupil vanished into
the face of a head, an ear sank into its top). A binary space
partitioning tree fixes that: built once per mesh, it splits triangles
that straddle a partition plane, and a walk of the tree from any eye
position yields an order that is right for every polygon pair, not
just on average.

Partition planes are either a triangle's own plane or, when that would
cut too much or balance too badly, an axis-aligned plane through the
median of the set — a convex body (sphere, cylinder) peels one facet
per polygon plane and would otherwise degenerate into an O(n²) chain.

`build()` returns None when the mesh is too large to partition within
its budgets (time, or growth from splitting — thin curved petals can
shred into twenty pieces each); the viewer then falls back to the
centroid sort.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import time

#: a vertex this close to a plane (mm) lies on it
EPS = 1e-4

#: meshes above this many triangles are not partitioned (the build is
#: pure Python and must stay well under a frame's worth of time)
MAX_TRIS = 12000

#: seconds the build may take before giving up
TIME_BUDGET = 0.4

#: give up when splitting has grown the mesh past this many times its
#: input size — every piece is one more polygon to paint per frame.
#: A small model of colliding blocks legitimately splits a lot, so the
#: cap never bites under MIN_PIECES, and never allows past MAX_PIECES.
MAX_GROWTH = 4.0
MIN_PIECES = 8000
MAX_PIECES = 24000

#: splitter candidates tried per node — a poor splitter cuts many
#: triangles, and every cut adds polygons for the rest of the build
CANDIDATES = 8

#: a cut triangle costs this many units of imbalance in the score
SPLIT_PENALTY = 8

#: when the best polygon plane leaves this fraction of the set on one
#: side, an axis-aligned median plane is tried too (convex bodies)
UNBALANCED = 0.7

#: below this many triangles a node takes the first usable plane
SMALL = 4


class Node:
    __slots__ = ("nx", "ny", "nz", "d", "coplanar", "back", "front")

    def __init__(self, nx, ny, nz, d):
        self.nx, self.ny, self.nz, self.d = nx, ny, nz, d
        self.coplanar = []          # indices of triangles in this plane
        self.back = None
        self.front = None


class Tree:
    """`tris`/`colors` are the split mesh (a superset of the input,
    same per-face colour format); `order()` walks them back to front."""

    def __init__(self, root, tris, colors):
        self.root = root
        self.tris = tris
        self.colors = colors

    def order(self, eye, forward, ortho=False):
        """Triangle indices back to front as seen from *eye* (or, for
        an orthographic camera, looking along *forward*)."""
        out = []
        extend = out.extend
        ex, ey, ez = eye
        fx, fy, fz = forward
        # iterative in-order walk: a stack of (node, visited-flag)
        stack = [(self.root, False)]
        pop = stack.pop
        push = stack.append
        while stack:
            node, visited = pop()
            if node is None:
                continue
            if visited:
                extend(node.coplanar)
                continue
            if ortho:
                side = -(node.nx * fx + node.ny * fy + node.nz * fz)
            else:
                side = node.nx * ex + node.ny * ey + node.nz * ez - node.d
            # far subtree first, then the plane's own polygons (pushed
            # as the visited marker), then the near subtree on top
            if side >= 0.0:
                near, far = node.front, node.back
            else:
                near, far = node.back, node.front
            push((near, False))
            push((node, True))
            push((far, False))
        return out


def _plane(tri):
    a, b, c = tri
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    nx = uy * vz - uz * vy
    ny = uz * vx - ux * vz
    nz = ux * vy - uy * vx
    l2 = nx * nx + ny * ny + nz * nz
    if l2 < 1e-24:
        return None
    inv = l2 ** -0.5
    nx *= inv; ny *= inv; nz *= inv
    return nx, ny, nz, nx * a[0] + ny * a[1] + nz * a[2]


def _axis_plane(indices, tris):
    """An axis-aligned plane through the median centroid along the
    longest extent of the set — balanced by construction."""
    lo = [float("inf")] * 3
    hi = [float("-inf")] * 3
    cents = []
    for i in indices:
        a, b, c = tris[i]
        cents.append(((a[0] + b[0] + c[0]) / 3.0,
                      (a[1] + b[1] + c[1]) / 3.0,
                      (a[2] + b[2] + c[2]) / 3.0))
        for p in (a, b, c):
            for k in range(3):
                if p[k] < lo[k]:
                    lo[k] = p[k]
                if p[k] > hi[k]:
                    hi[k] = p[k]
    axis = max(range(3), key=lambda k: hi[k] - lo[k])
    if hi[axis] - lo[axis] < EPS * 10:
        return None
    coords = sorted(c[axis] for c in cents)
    d = coords[len(coords) // 2]
    n = [0.0, 0.0, 0.0]
    n[axis] = 1.0
    return n[0], n[1], n[2], d


def _classify(tri, nx, ny, nz, d):
    """(kind, distances): kind is 'co', 'front', 'back' or 'split'."""
    a, b, c = tri
    d0 = nx * a[0] + ny * a[1] + nz * a[2] - d
    d1 = nx * b[0] + ny * b[1] + nz * b[2] - d
    d2 = nx * c[0] + ny * c[1] + nz * c[2] - d
    if d0 <= EPS and d1 <= EPS and d2 <= EPS:
        if d0 >= -EPS and d1 >= -EPS and d2 >= -EPS:
            return "co", None
        return "back", None
    if d0 >= -EPS and d1 >= -EPS and d2 >= -EPS:
        return "front", None
    return "split", (d0, d1, d2)


def _score(plane, indices, tris):
    nx, ny, nz, d = plane
    splits = fr = bk = 0
    for i in indices:
        kind, _dists = _classify(tris[i], nx, ny, nz, d)
        if kind == "split":
            splits += 1
        elif kind == "front":
            fr += 1
        elif kind == "back":
            bk += 1
    return splits * SPLIT_PENALTY + abs(fr - bk), abs(fr - bk)


def _split(tri, dists):
    """Cut *tri* by the plane: (front_tris, back_tris), winding kept."""
    front, back = [], []
    for i in range(3):
        p, dp = tri[i], dists[i]
        q, dq = tri[(i + 1) % 3], dists[(i + 1) % 3]
        if dp >= -EPS:
            front.append(p)
        if dp <= EPS:
            back.append(p)
        if (dp > EPS and dq < -EPS) or (dp < -EPS and dq > EPS):
            t = dp / (dp - dq)
            m = (p[0] + (q[0] - p[0]) * t,
                 p[1] + (q[1] - p[1]) * t,
                 p[2] + (q[2] - p[2]) * t)
            front.append(m)
            back.append(m)
    return _fan(front), _fan(back)


def _fan(poly):
    return [(poly[0], poly[i], poly[i + 1]) for i in range(1, len(poly) - 1)]


def _choose_plane(indices, tris):
    """The partition plane for this set, or None when every triangle
    in it is degenerate."""
    if len(indices) <= SMALL:
        for i in indices:
            plane = _plane(tris[i])
            if plane is not None:
                return plane
        return None
    step = len(indices) / CANDIDATES
    best = None
    for k in range(CANDIDATES):
        plane = _plane(tris[indices[int(k * step)]])
        if plane is None:
            continue
        score, imbalance = _score(plane, indices, tris)
        if best is None or score < best[0]:
            best = (score, plane, imbalance)
    if best is None or best[2] > UNBALANCED * len(indices):
        # every facet plane of a convex body has all the others behind
        # it: peeling one per node is an O(n²) chain. A median plane
        # cuts a ring of facets but halves the set.
        axis = _axis_plane(indices, tris)
        if axis is not None:
            score, imbalance = _score(axis, indices, tris)
            if best is None or score < best[0]:
                best = (score, axis, imbalance)
    if best is not None:
        return best[1]
    for i in indices:                       # all candidates degenerate
        plane = _plane(tris[i])
        if plane is not None:
            return plane
    return None


def build(tris, colors=None, *, max_tris=MAX_TRIS, budget=TIME_BUDGET,
          max_growth=MAX_GROWTH):
    """Partition *tris* (per-face *colors* ride along). None when the
    mesh is empty, too big, or a budget ran out."""
    n = len(tris)
    if n == 0 or n > max_tris:
        return None
    deadline = time.monotonic() + budget
    limit = min(max(n * max_growth, MIN_PIECES), MAX_PIECES)
    out_tris = list(tris)
    out_colors = list(colors) if colors else None
    root = None
    # work items: (indices to partition, parent node, 'back'/'front').
    # Degenerate (collinear) triangles paint nothing, yet a plane would
    # split one into two degenerate pieces, and those again, until the
    # growth cap fired — leave them out from the start
    stack = [([i for i in range(n) if _plane(out_tris[i]) is not None],
              None, None)]
    while stack:
        if time.monotonic() > deadline or len(out_tris) > limit:
            return None
        indices, parent, slot = stack.pop()
        if not indices:
            continue
        plane = _choose_plane(indices, out_tris)
        if plane is None:                   # all degenerate: drop them
            continue
        nx, ny, nz, d = plane
        node = Node(nx, ny, nz, d)
        if parent is None:
            root = node
        elif slot == "back":
            parent.back = node
        else:
            parent.front = node
        front, back = [], []
        for i in indices:
            tri = out_tris[i]
            kind, dists = _classify(tri, nx, ny, nz, d)
            if kind == "co":
                node.coplanar.append(i)
            elif kind == "front":
                front.append(i)
            elif kind == "back":
                back.append(i)
            else:
                f_tris, b_tris = _split(tri, dists)
                color = out_colors[i] if out_colors else None
                # the first piece reuses the slot, the rest are appended
                first = True
                for group, target in ((f_tris, front), (b_tris, back)):
                    for piece in group:
                        if _plane(piece) is None:   # sliver too thin
                            continue
                        if first:
                            out_tris[i] = piece
                            target.append(i)
                            first = False
                        else:
                            out_tris.append(piece)
                            if out_colors is not None:
                                out_colors.append(color)
                            target.append(len(out_tris) - 1)
        stack.append((front, node, "front"))
        stack.append((back, node, "back"))
    if root is None:
        return None
    return Tree(root, out_tris, out_colors)

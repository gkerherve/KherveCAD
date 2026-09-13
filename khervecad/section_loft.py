"""Loft through sections — a solid whose cross-sections are ordinary 2D
shapes, corners and all (Qt-free).

The ``loft`` node joins elliptical rings, so everything it makes is
round; this one takes the node's 2D children as the sections, one per
height, and joins them in order — a car body (flat sides, a shoulder
crease, a flat hood), a boat hull, a bottle with flats, a wing.

- Sections with the same number of points are joined point to point,
  so every corner runs as a sharp edge along the solid. Sections with
  different counts are resampled to one count: points are spread over
  the edges in proportion to their length, and every original vertex is
  kept, so a corner never gets rounded off.
- Each ring is turned (a cyclic shift of its points) to line up with
  the ring before it, so the loft does not twist between sections.
- *smooth* adds Catmull-Rom rings between the sections (like the loft
  and the sweep): the given sections stay exactly where they are.
- The ends are capped with the first and last section, so the result
  is one closed solid, whichever way the heights run.

Output is a list of counter-clockwise (outward) triangles for the
preview; bake.py welds them into an OpenSCAD polyhedron.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from .loft import _catmull
from .sweep import _area, _ccw

#: sections with different point counts are resampled to at least this
#: many points (and at least twice the largest count)
MIN_POINTS = 48


def resample(outline, n: int) -> list:
    """*outline* with *n* points: every original vertex kept, the extra
    points spread over the edges in proportion to their length."""
    m = len(outline)
    if n <= m:
        return list(outline)
    lengths = [math.dist(outline[i], outline[(i + 1) % m]) for i in range(m)]
    total = sum(lengths) or 1.0
    extra = n - m
    raw = [extra * length / total for length in lengths]
    counts = [int(r) for r in raw]
    order = sorted(range(m), key=lambda i: raw[i] - counts[i], reverse=True)
    for i in order[:extra - sum(counts)]:
        counts[i] += 1
    out = []
    for i in range(m):
        a, b = outline[i], outline[(i + 1) % m]
        steps = counts[i] + 1
        for j in range(steps):
            t = j / steps
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out


def align(ring, ref) -> list:
    """*ring* shifted cyclically to lie closest to *ref* point by point,
    so consecutive sections join without a twist."""
    n = len(ring)
    stride = max(1, n // 32)

    def cost(shift):
        return sum((ring[(i + shift) % n][0] - ref[i][0]) ** 2
                   + (ring[(i + shift) % n][1] - ref[i][1]) ** 2
                   for i in range(0, n, stride))
    best = min(range(n), key=cost)
    return ring[best:] + ring[:best]


def _volume(tris) -> float:
    total = 0.0
    for a, b, c in tris:
        total += (a[0] * (b[1] * c[2] - b[2] * c[1])
                  - a[1] * (b[0] * c[2] - b[2] * c[0])
                  + a[2] * (b[0] * c[1] - b[1] * c[0]))
    return total / 6.0


def _smooth_stack(stack, smooth: int) -> list:
    """Catmull-Rom rings between the sections of *stack* (rings of 3D
    points, all the same length); the given rings stay in place."""
    if smooth <= 0 or len(stack) < 2:
        return stack
    n = len(stack)
    first = [tuple(2 * a - b for a, b in zip(p, q))
             for p, q in zip(stack[0], stack[1])]
    last = [tuple(2 * a - b for a, b in zip(p, q))
            for p, q in zip(stack[-1], stack[-2])]
    ext = [first] + stack + [last]
    out = []
    for k in range(n - 1):
        out.append(stack[k])
        for j in range(1, smooth + 1):
            t = j / (smooth + 1)
            out.append([tuple(_catmull(ext[k][i], ext[k + 1][i], ext[k + 2][i],
                                       ext[k + 3][i], t))
                        for i in range(len(stack[0]))])
    out.append(stack[-1])
    return out


def loft_sections(outlines, heights, smooth: int = 0) -> list:
    """Counter-clockwise triangles of the solid through *outlines* (lists
    of (x, y), any winding) placed at *heights* (z), in order. Empty for
    fewer than two usable sections."""
    pairs = [(_ccw(o), float(z)) for o, z in zip(outlines, heights)]
    pairs = [(o, z) for o, z in pairs if len(o) >= 3]
    if len(pairs) < 2:
        return []
    rings = [o for o, _z in pairs]
    counts = {len(r) for r in rings}
    if len(counts) > 1:
        n = max(MIN_POINTS, 2 * max(counts))
        rings = [resample(r, n) for r in rings]
    for i in range(1, len(rings)):
        rings[i] = align(rings[i], rings[i - 1])
    stack = [[(x, y, z) for x, y in ring] for ring, (_o, z) in zip(rings, pairs)]
    stack = _smooth_stack(stack, int(smooth))
    m = len(stack[0])
    tris = []
    for lower, upper in zip(stack, stack[1:]):
        for k in range(m):
            k1 = (k + 1) % m
            a, b, c, d = lower[k], lower[k1], upper[k1], upper[k]
            tris.append((a, b, c))
            tris.append((a, c, d))

    from .mesh import triangulate
    for ring3, top in ((stack[0], False), (stack[-1], True)):
        flat = [(p[0], p[1]) for p in ring3]
        index = {p: i for i, p in enumerate(flat)}
        for a, b, c in triangulate(flat):
            pa, pb, pc = (ring3[index[p]] for p in (a, b, c))
            tris.append((pa, pb, pc) if top else (pa, pc, pb))
    if _volume(tris) < 0:              # the heights run downwards
        tris = [(a, c, b) for a, b, c in tris]
    return tris


def child_sections(node, env) -> list:
    """One outline per visible child of *node*, in order: the child's
    largest outline (a section is one closed shape)."""
    from . import mesh
    env = dict(env)
    out = []
    for child in node.children:
        if child.type == "assign":
            mesh._apply_assign(child, env)
            continue
        if not child.visible:
            continue
        outlines = [o for o in mesh.collect_outlines(child, env) if len(o) >= 3]
        if outlines:
            out.append(max(outlines, key=lambda o: abs(_area(o))))
    return out

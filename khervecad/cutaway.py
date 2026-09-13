"""Cut through: the model sliced by a plane, one side taken away and the
cut face capped, so the inside of a part — its holes, walls, bores and
threads — can be seen in the 3D view (View ▸ Cut Through). Qt-free.

`clip` keeps the triangles on one side of the plane, splitting those
that straddle it (their winding kept, so the outside still faces out).
`caps` closes the opening: `section.cut` + `section.chain` give the cut's
outlines in the plane's (u, v), and `fill` tiles them by a trapezoid
sweep — even-odd, so holes stay open without bridging, and linear in
the outline size, where ear clipping went quadratic on a thread's
thousand-point section and could not follow a slider.

The cap faces the removed side (towards whoever is looking in), wears
`CAP_COLOR` in a matte finish — the CAD convention of a coloured
section — and together with the clipped surface makes a closed solid
again, so a mass check of what is shown still adds up.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import bisect

from . import section

AXES = {"x": 0, "y": 1, "z": 2}
#: the cut face's colour: (colour, alpha, material) as the preview reads it
CAP_COLOR = ("#c8553d", 1.0, "Matte")
#: (u x v) . axis for each plane: which way a counter-clockwise (u, v)
#: triangle faces along the axis
_ORIENT = {"x": 1.0, "y": -1.0, "z": 1.0}


def extent(tris, axis):
    """(low, high) of *tris* along *axis*, or None for no triangles."""
    k = AXES[axis]
    values = [p[k] for tri in tris for p in tri]
    return (min(values), max(values)) if values else None


def offset_at(tris, axis, position):
    """The plane's coordinate for *position* in [0, 1] of the extent."""
    span = extent(tris, axis)
    if span is None:
        return 0.0
    position = min(max(float(position), 0.0), 1.0)
    return span[0] + (span[1] - span[0]) * position


def clip(tris, colors, axis, offset, flip=False):
    """(triangles, colours) on the kept side of ``axis = offset`` — the
    low side, or the high side with *flip*. Straddling triangles are cut
    along the plane and fanned, keeping their winding."""
    k = AXES[axis]
    sign = -1.0 if flip else 1.0
    out, out_colors = [], []
    for index, tri in enumerate(tris):
        d = [sign * (p[k] - offset) for p in tri]
        color = colors[index] if colors else None
        if d[0] <= 0.0 and d[1] <= 0.0 and d[2] <= 0.0:
            out.append(tri)
            out_colors.append(color)
            continue
        if d[0] > 0.0 and d[1] > 0.0 and d[2] > 0.0:
            continue
        poly = []
        for i in range(3):
            p, q = tri[i], tri[(i + 1) % 3]
            dp, dq = d[i], d[(i + 1) % 3]
            if dp <= 0.0:
                poly.append(p)
            if (dp <= 0.0) != (dq <= 0.0):
                t = dp / (dp - dq)
                poly.append(tuple(p[j] + (q[j] - p[j]) * t for j in range(3)))
        for i in range(1, len(poly) - 1):
            out.append((poly[0], poly[i], poly[i + 1]))
            out_colors.append(color)
    return out, (out_colors if colors else None)


def fill(loops):
    """Triangles tiling the inside of closed *loops* [[(u, v), ...]] by
    the even-odd rule (holes stay open), counter-clockwise. A sweep over
    the vertices' v levels: between two levels no vertex interrupts the
    edges, so the crossing edges pair up into trapezoids."""
    edges = []
    for loop in loops:
        for a, b in zip(loop, loop[1:] + loop[:1]):
            if a[1] != b[1]:
                lo, hi = (a, b) if a[1] < b[1] else (b, a)
                edges.append((lo, hi))
    if not edges:
        return []
    edges.sort(key=lambda e: e[0][1])
    starts = [e[0][1] for e in edges]
    levels = sorted({p[1] for loop in loops for p in loop})
    active, added, tris = [], 0, []
    for y0, y1 in zip(levels, levels[1:]):
        if y1 - y0 < 1e-12:
            continue
        # edges starting at or below this slab join; spent ones leave
        stop = bisect.bisect_right(starts, y0)
        active.extend(edges[added:stop])
        added = max(added, stop)
        active = [e for e in active if e[1][1] > y0]
        xs = []
        for lo, hi in active:
            if lo[1] <= y0 and hi[1] >= y1:
                span = hi[1] - lo[1]
                x0 = lo[0] + (hi[0] - lo[0]) * (y0 - lo[1]) / span
                x1 = lo[0] + (hi[0] - lo[0]) * (y1 - lo[1]) / span
                xs.append(((x0 + x1) / 2.0, x0, x1))
        xs.sort()
        for (_m0, l0, l1), (_m1, r0, r1) in zip(xs[0::2], xs[1::2]):
            if r0 - l0 > 1e-12:
                tris.append(((l0, y0), (r0, y0), (r1, y1)))
            if r1 - l1 > 1e-12:
                tris.append(((l0, y0), (r1, y1), (l1, y1)))
    return tris


def caps(tris, axis, offset, flip=False):
    """Triangles closing the cut through *tris* at ``axis = offset``,
    facing the removed side. Outlines that do not close (a mesh that
    leaks at the plane) are left open rather than guessed."""
    k, (iu, iv), _names = section.PLANES[axis]
    loops = [pts for pts, closed in section.chain(
        section.cut(tris, axis, float(offset))) if closed and len(pts) >= 3]
    want = -1.0 if flip else 1.0             # the removed side's direction
    turn = _ORIENT[axis] != want

    def lift(p):
        v = [0.0, 0.0, 0.0]
        v[k], v[iu], v[iv] = float(offset), p[0], p[1]
        return tuple(v)
    out = []
    for a, b, c in fill(loops):
        tri = (lift(a), lift(b), lift(c))
        out.append((tri[0], tri[2], tri[1]) if turn else tri)
    return out


def apply(tris, colors, axis, position, flip=False):
    """The shown model: *tris* clipped at *position* (0..1 of the
    extent along *axis*) and capped. Returns (tris, colours or None,
    offset). Colours are only produced when the input had some or a
    cap was added (the cap is always coloured)."""
    offset = offset_at(tris, axis, position)
    kept, kept_colors = clip(tris, colors, axis, offset, flip)
    cap = caps(tris, axis, offset, flip)
    if not cap:
        return kept, kept_colors, offset
    base = kept_colors if kept_colors is not None else [None] * len(kept)
    return kept + cap, base + [CAP_COLOR] * len(cap), offset

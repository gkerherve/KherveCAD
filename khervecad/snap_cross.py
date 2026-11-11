"""Where sketch lines CROSS — snap points like ends, middles and centres
(2026-11-11, the user: "we can connect to middle, centre, but we need
to be able to connect to intersections too").

Qt-free. `crossings(groups)` takes one list of segments per shape (a
line, a circle's polygon, a rectangle's sides, the part's outline) and
returns the points where segments of DIFFERENT shapes cross or touch —
a shape crossing itself (a polygon's two sides at a corner) is not an
intersection, its corner is already a snap point. Points closer than
`MERGE` are one.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

MERGE = 1e-6
#: past this many segments in all, nothing is worked out (a dense mesh
#: outline would make every mouse move slow)
MAX_SEGMENTS = 4000
MAX_POINTS = 500


def _box(seg):
    (ax, ay), (bx, by) = seg
    return (min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))


def cross(a, b, c, d, eps=1e-12):
    """Where segment a-b meets segment c-d (ends included), or None."""
    rx, ry = b[0] - a[0], b[1] - a[1]
    sx, sy = d[0] - c[0], d[1] - c[1]
    den = rx * sy - ry * sx
    if abs(den) < eps:
        return None                      # parallel (or collinear)
    qx, qy = c[0] - a[0], c[1] - a[1]
    t = (qx * sy - qy * sx) / den
    u = (qx * ry - qy * rx) / den
    tol = 1e-9
    if -tol <= t <= 1 + tol and -tol <= u <= 1 + tol:
        return (a[0] + t * rx, a[1] + t * ry)
    return None


def crossings(groups):
    """[(x, y)] where segments of two different groups meet."""
    total = sum(len(g) for g in groups)
    if total > MAX_SEGMENTS or len(groups) < 2:
        return []
    boxes = [[(_box(s), s) for s in g if s[0] != s[1]] for g in groups]
    gbox = []
    for g in boxes:
        if not g:
            gbox.append(None)
            continue
        gbox.append((min(b[0] for b, _s in g), min(b[1] for b, _s in g),
                     max(b[2] for b, _s in g), max(b[3] for b, _s in g)))
    out = []
    for i in range(len(boxes)):
        if gbox[i] is None:
            continue
        for j in range(i + 1, len(boxes)):
            if gbox[j] is None or not _overlap(gbox[i], gbox[j]):
                continue
            for bi, si in boxes[i]:
                if not _overlap(bi, gbox[j]):
                    continue
                for bj, sj in boxes[j]:
                    if not _overlap(bi, bj):
                        continue
                    p = cross(si[0], si[1], sj[0], sj[1])
                    if p is None or any(abs(p[0] - q[0]) < MERGE and
                                        abs(p[1] - q[1]) < MERGE
                                        for q in out):
                        continue
                    out.append(p)
                    if len(out) >= MAX_POINTS:
                        return out
    return out


def _overlap(a, b, pad=1e-9):
    return a[0] <= b[2] + pad and b[0] <= a[2] + pad and \
        a[1] <= b[3] + pad and b[1] <= a[3] + pad

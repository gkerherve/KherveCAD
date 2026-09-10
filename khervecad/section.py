"""Planar cross-sections of a triangle mesh.

What the `section` MCP tool is built on: cut a mesh with an
axis-aligned plane and chain the cut into outlines — the view a
machinist reads a part from, and the one thing a shaded render cannot
show: how thick a wall is, whether a bore goes through, what is inside
a closed shell.

Every cut segment is oriented with the solid on its **left**, so outer
outlines run counter-clockwise and holes clockwise, and the signed
areas add up to the net material area with no nesting analysis.

Pure geometry and Qt-free, so it is tested without a window; `draw()`
imports Qt only when a picture is asked for.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

#: cut axis -> (its coordinate index, (u, v) indices, (u, v) names).
#: The picture is drawn u-right, v-up, which matches the Top (z), Front
#: (y) and Right (x) camera presets.
PLANES = {
    "x": (0, (1, 2), ("y", "z")),
    "y": (1, (0, 2), ("x", "z")),
    "z": (2, (0, 1), ("x", "y")),
}

#: points closer than this (mm) are the same outline vertex
_KEY_DIGITS = 7


def _crossing(p, q, dp, dq, iu, iv):
    """Where edge p-q meets the plane, in (u, v). The edge is taken in
    a canonical order so the two triangles sharing it compute the very
    same point — the outline then chains by exact match."""
    if p > q:
        p, q, dp, dq = q, p, dq, dp
    t = dp / (dp - dq)
    return (p[iu] + (q[iu] - p[iu]) * t, p[iv] + (q[iv] - p[iv]) * t)


def cut(tris, axis: str, offset: float) -> list:
    """Segments ``((u, v), (u, v))`` where the plane ``axis = offset``
    cuts *tris*, each oriented with the solid on its left."""
    k, (iu, iv), _names = PLANES[axis]
    segs = []
    for tri in tris:
        d = (tri[0][k] - offset, tri[1][k] - offset, tri[2][k] - offset)
        above = (d[0] >= 0.0, d[1] >= 0.0, d[2] >= 0.0)
        if above[0] == above[1] == above[2]:
            continue                      # wholly on one side (or in it)
        pts = [_crossing(tri[i], tri[(i + 1) % 3], d[i], d[(i + 1) % 3],
                         iu, iv)
               for i in range(3) if above[i] != above[(i + 1) % 3]]
        if len(pts) != 2:
            continue
        a, b = pts
        if abs(a[0] - b[0]) + abs(a[1] - b[1]) < 1e-12:
            continue
        # the face's outward normal, in the plane: the solid lies on
        # the side it points away from, so travel with it on the right
        (x0, y0, z0), (x1, y1, z1), (x2, y2, z2) = tri
        ux, uy, uz = x1 - x0, y1 - y0, z1 - z0
        vx, vy, vz = x2 - x0, y2 - y0, z2 - z0
        n = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
        tu, tv = -n[iv], n[iu]              # the normal turned 90° CCW
        if (b[0] - a[0]) * tu + (b[1] - a[1]) * tv < 0.0:
            a, b = b, a
        segs.append((a, b))
    return segs


def _key(p):
    return (round(p[0], _KEY_DIGITS), round(p[1], _KEY_DIGITS))


def chain(segs) -> list:
    """Join oriented segments end-to-start into outlines.

    Returns ``[(points, closed)]``. An outline that cannot close means
    the mesh has a gap on the plane (it is not watertight there)."""
    starts = {}
    for i, (a, _b) in enumerate(segs):
        starts.setdefault(_key(a), []).append(i)
    used = [False] * len(segs)
    out = []
    for i, (a, b) in enumerate(segs):
        if used[i]:
            continue
        used[i] = True
        first, cur = _key(a), _key(b)
        pts = [a, b]
        closed = False
        while True:
            if cur == first:
                closed = True
                pts.pop()                   # the start repeats: drop it
                break
            nxt = next((j for j in starts.get(cur, ()) if not used[j]),
                       None)
            if nxt is None:
                break
            used[nxt] = True
            pts.append(segs[nxt][1])
            cur = _key(segs[nxt][1])
        out.append((pts, closed))
    return out


def signed_area(pts) -> float:
    """Shoelace area: positive counter-clockwise (material), negative
    clockwise (a hole)."""
    total = 0.0
    for i, (x0, y0) in enumerate(pts):
        x1, y1 = pts[(i + 1) % len(pts)]
        total += x0 * y1 - x1 * y0
    return total / 2.0


def section(tris, axis: str, offset: float = None) -> dict:
    """The whole cut of *tris* by the plane ``axis = offset``.

    *offset* defaults to the middle of the mesh along *axis*. Returns
    the outlines (points in the plane's (u, v) mm), the net area in
    mm² (holes subtract), and the outline's extent."""
    if axis not in PLANES:
        raise ValueError(f"axis must be one of {', '.join(PLANES)}")
    k, _uv, names = PLANES[axis]
    if offset is None:
        vals = [v[k] for tri in tris for v in tri]
        offset = (min(vals) + max(vals)) / 2.0 if vals else 0.0
    outlines = []
    for pts, closed in chain(cut(tris, axis, float(offset))):
        area = signed_area(pts) if closed and len(pts) >= 3 else 0.0
        outlines.append({"points": pts, "closed": closed, "area": area})
    every = [p for o in outlines for p in o["points"]]
    bounds = None
    if every:
        us = [p[0] for p in every]
        vs = [p[1] for p in every]
        bounds = [min(us), min(vs), max(us), max(vs)]
    return {"axis": axis, "offset": float(offset), "plane": names,
            "outlines": outlines,
            "area": sum(o["area"] for o in outlines),
            "bounds": bounds}


def _nice_step(span: float, lines: int = 8) -> float:
    """A 1/2/5 x 10^n grid step giving about *lines* lines."""
    raw = max(span, 1e-9) / lines
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 5, 10):
        if raw <= m * mag:
            return m * mag
    return 10 * mag


def draw(sec: dict, width: int, height: int):
    """The section as a QImage: hatched material, outlines, a mm grid
    and a caption naming the plane — how a drawing's section view
    reads."""
    from PyQt5.QtCore import QPointF, QRectF, Qt
    from PyQt5.QtGui import (QBrush, QColor, QImage, QPainter,
                             QPainterPath, QPen)
    img = QImage(int(width), int(height), QImage.Format_ARGB32)
    img.fill(QColor("#f7f7f5"))
    painter = QPainter(img)
    painter.setRenderHint(QPainter.Antialiasing, True)
    u_name, v_name = sec["plane"]
    caption = (f"Section {sec['axis']} = {sec['offset']:g} mm   "
               f"({u_name} right, {v_name} up)")
    painter.setPen(QColor("#333333"))
    painter.drawText(QRectF(8, 4, width - 16, 20),
                     Qt.AlignLeft | Qt.AlignVCenter, caption)
    if not sec["bounds"]:
        painter.drawText(QRectF(0, 0, width, height), Qt.AlignCenter,
                         "The plane misses the model.")
        painter.end()
        return img
    u0, v0, u1, v1 = sec["bounds"]
    du, dv = max(u1 - u0, 1e-6), max(v1 - v0, 1e-6)
    margin, top = 30.0, 28.0
    scale = min((width - 2 * margin) / du,
                (height - top - 2 * margin) / dv)
    cx = margin + (width - 2 * margin - du * scale) / 2
    cy = top + margin + (height - top - 2 * margin - dv * scale) / 2

    def xy(p):
        return QPointF(cx + (p[0] - u0) * scale,
                       cy + (v1 - p[1]) * scale)

    step = _nice_step(max(du, dv))
    grid = QPen(QColor("#dcdcd8"))
    grid.setWidthF(0.6)
    painter.setPen(grid)
    font = painter.font()
    font.setPointSizeF(7.5)
    painter.setFont(font)
    g = math.floor(u0 / step) * step
    while g <= u1 + 1e-9:
        x = xy((g, v0)).x()
        painter.drawLine(QPointF(x, top + 4), QPointF(x, height - 14))
        painter.drawText(QPointF(x + 2, height - 3), f"{g:g}")
        g += step
    g = math.floor(v0 / step) * step
    while g <= v1 + 1e-9:
        y = xy((u0, g)).y()
        painter.drawLine(QPointF(4, y), QPointF(width - 4, y))
        painter.drawText(QPointF(4, y - 2), f"{g:g}")
        g += step
    path = QPainterPath()
    path.setFillRule(Qt.OddEvenFill)
    for outline in sec["outlines"]:
        pts = outline["points"]
        path.moveTo(xy(pts[0]))
        for p in pts[1:]:
            path.lineTo(xy(p))
        if outline["closed"]:
            path.closeSubpath()
    painter.fillPath(path, QColor("#9fb6cf"))
    painter.fillPath(path, QBrush(QColor("#4d6d91"), Qt.BDiagPattern))
    painter.setPen(QPen(QColor("#1f3550"), 1.4))
    painter.drawPath(path)
    open_pen = QPen(QColor("#d23c3c"), 2.0, Qt.DashLine)
    for outline in sec["outlines"]:
        if not outline["closed"]:           # a gap: the mesh leaks here
            painter.setPen(open_pen)
            pts = [xy(p) for p in outline["points"]]
            for a, b in zip(pts, pts[1:]):
                painter.drawLine(a, b)
    painter.end()
    return img

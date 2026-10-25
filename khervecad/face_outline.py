"""The face you sketch on, shown in the sketch (2026-10-25, the user: "when
we select the face we should see that face in the 2D view … the centre
of the circle, this is where we would like the cut to start").

`outline(tris, point, normal)` (Qt-free): the triangles lying in the
clicked face's plane and facing its way, their boundary edges (an edge
used by one of them only) — the face's outline, holes included.
`for_group(group, tris)` maps it into the face sketch's own frame
(`face_sketch.to_local`), which is the 2D view's frame while that
sketch is open; `snap_points` gives its corners, the middle of each
straight side and the centre of each round run (`drawing.find_circles`)
— SolidWorks' snaps on the face's edges.

The 2D view draws the outline grey under the sketch and snaps to those
points (`SketchScene.face_outline`); nothing is stored in the document.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

PLANE_TOL = 1e-3          # mm off the plane still on it
FACING = 0.999            # cos of the angle a triangle may tilt
SNAP_PX = 10


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _unit(v):
    n = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2) or 1.0
    return (v[0] / n, v[1] / n, v[2] / n)


def outline(tris, point, normal):
    """[((x, y, z), (x, y, z))] boundary edges of the face of *tris* in
    the plane through *point* square to *normal*."""
    n = _unit(normal)
    d0 = n[0] * point[0] + n[1] * point[1] + n[2] * point[2]
    size = 1.0
    for t in tris[:2000]:
        for v in t:
            size = max(size, abs(v[0]), abs(v[1]), abs(v[2]))
    tol = PLANE_TOL * size
    count = {}
    for t in tris:
        tn = _unit(_cross(_sub(t[1], t[0]), _sub(t[2], t[0])))
        if tn[0] * n[0] + tn[1] * n[1] + tn[2] * n[2] < FACING:
            continue
        if any(abs(v[0] * n[0] + v[1] * n[1] + v[2] * n[2] - d0) > tol
               for v in t):
            continue
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            ka = tuple(round(c, 4) for c in a)
            kb = tuple(round(c, 4) for c in b)
            key = (ka, kb) if ka <= kb else (kb, ka)
            count[key] = count.get(key, 0) + 1
    return [k for k, c in count.items() if c == 1]


def for_group(group, tris):
    """The clicked face's outline in *group*'s own 2D frame."""
    from . import face_sketch
    point = face_sketch.to_world(group, 0.0, 0.0)
    normal = face_sketch._normal_of(group)
    segs = []
    for a, b in outline(tris, point, normal):
        segs.append((face_sketch.to_local(group, a),
                     face_sketch.to_local(group, b)))
    return segs


def arcs(segs):
    """[((cx, cy), r)] of the round runs in the outline: along each loop,
    vertices that turn a little (a tessellated arc, between 0.3 and 40
    degrees) in a row; sharp corners and straight sides end a run."""
    from . import drawing
    out = []
    for points, _s, closed in drawing._chains(list(segs)):
        n = len(points)
        if n < 3:
            continue

        def turn(i):
            a, b, c = points[i - 1], points[i], points[(i + 1) % n]
            u = (b[0] - a[0], b[1] - a[1])
            v = (c[0] - b[0], c[1] - b[1])
            t = math.degrees(math.atan2(u[0] * v[1] - u[1] * v[0],
                                        u[0] * v[0] + u[1] * v[1]))
            return abs(t)
        rng = range(n) if closed else range(1, n - 1)
        bent = {i: 0.3 < turn(i) < 40.0 for i in rng}
        if closed and all(bent.values()):
            got = drawing.fit_circle(points)
            if got:
                out.append(got)
            continue
        # walk from a vertex that is not bent so runs never wrap halfway
        start = next((i for i in rng if not bent[i]), None)
        if start is None:
            continue
        order = [(start + k) % n for k in range(n)] if closed else list(rng)
        run = []
        for i in order + [start]:
            if bent.get(i):
                run.append(i)
                continue
            if len(run) >= 2:
                pts = [points[(run[0] - 1) % n]] + [points[j] for j in run] \
                    + [points[(run[-1] + 1) % n]]
                got = drawing.fit_circle(pts)
                if got and got[1] > 1e-6:
                    out.append(got)
            run = []
    return out


def snap_points(segs):
    """[(x, y, label)]: corners, side middles, arc centres."""
    pts = {}
    for a, b in segs:
        for p in (a, b):
            pts[(round(p[0], 3), round(p[1], 3))] = "corner"
    out = [(x, y, k) for (x, y), k in pts.items()]
    for (cx, cy), _r in arcs(segs):
        out.append((cx, cy, "centre"))
    for a, b in segs:
        if math.hypot(b[0] - a[0], b[1] - a[1]) > 5.0:   # a real side
            out.append(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, "middle"))
    return out


# =================================================================== Qt
def show(window, group, part):
    """Hand the face's outline to the 2D view for *group*'s sketch."""
    from . import meshedit_ui
    tris = None
    for node, t in meshedit_ui._parts(window):
        if node is part or _inside(part, node):
            tris = t
            break
    scene = window.view2d.scene()
    if not tris:
        scene.face_outline = None
        return []
    segs = for_group(group, tris)
    scene.face_outline = {"segments": segs, "points": snap_points(segs)}
    return segs


def _inside(node, outer):
    while node is not None:
        if node is outer:
            return True
        node = node.parent
    return False


def clear(window):
    scene = window.view2d.scene()
    scene.face_outline = None


def paint(scene, painter):
    """Grey outline + small marks on the centres (scene coordinates)."""
    from PyQt5.QtCore import QLineF, QPointF
    from PyQt5.QtGui import QColor, QPen
    info = getattr(scene, "face_outline", None)
    if not info:
        return
    pen = QPen(QColor(110, 120, 135), 0)
    pen.setCosmetic(True)
    pen.setWidthF(1.6)
    painter.save()
    painter.setPen(pen)
    for a, b in info["segments"]:
        painter.drawLine(QLineF(QPointF(*a), QPointF(*b)))
    mark = QPen(QColor(200, 60, 40), 0)
    mark.setCosmetic(True)
    mark.setWidthF(1.4)
    painter.setPen(mark)
    views = scene.views()
    k = 1.0 / (abs(views[0].transform().m11()) or 1.0) if views else 1.0
    for x, y, kind in info["points"]:
        if kind == "centre":
            s = 5 * k
            painter.drawLine(QLineF(x - s, y, x + s, y))
            painter.drawLine(QLineF(x, y - s, x, y + s))
    painter.restore()


def snap(scene, pos):
    """The outline point nearest *pos* within SNAP_PX, or None."""
    info = getattr(scene, "face_outline", None)
    if not info:
        return None
    views = scene.views()
    k = abs(views[0].transform().m11()) if views else 1.0
    best = None
    for x, y, _kind in info["points"]:
        d = math.hypot(pos.x() - x, pos.y() - y) * k
        if d <= SNAP_PX and (best is None or d < best[0]):
            best = (d, x, y)
    if best is None:
        return None
    from PyQt5.QtCore import QPointF
    return QPointF(best[1], best[2])

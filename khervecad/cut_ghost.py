"""The cut, seen (2026-10-25, the user: "if I click on a cut sketch I
should see the cut in red … any hole, any cut"). Selecting a Difference,
or anything in what it cuts away (a Cut sketch, its extrude, the slot),
draws the cutting tool see-through red over the 3D view — the volume
that is removed, otherwise invisible because it is gone. A View3D
overlay painter; the triangles are worked out when the selection
changes (`update`), never per frame.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

RED = (220, 40, 40)


def tool_roots(model, ids):
    """The subtractor subtrees to show for the selected node ids."""
    roots = []
    for node in model.root.walk():
        if node.id not in ids:
            continue
        if node.type == "difference":
            roots.extend(node.children[1:])
            continue
        probe = node
        while probe is not None and probe.parent is not None:
            parent = probe.parent
            if parent.type == "difference" and parent.children and \
                    parent.children[0] is not probe:
                roots.append(probe)
                break
            probe = parent
    out, seen = [], set()
    for r in roots:
        if id(r) not in seen:
            seen.add(id(r))
            out.append(r)
    return out


def update(window):
    """Work out the red triangles for the current selection."""
    from . import mesh
    ids = getattr(window, "_selected_ids", set())
    roots = tool_roots(window.model, ids) if ids else []
    tris = []
    if roots:
        scope = window._render_scope()[0]
        iso = scope if scope is not window.model.root else None
        try:
            with window._isolated_frame(iso):
                tris = mesh.selected_world_tris(
                    scope, {r.id for r in roots},
                    fn=window.model.effective_fn())
        except Exception:
            tris = []
    window._cut_ghost = tris
    window.view3d.update()


def paint(window, painter, project):
    from PyQt5.QtCore import QPointF, Qt
    from PyQt5.QtGui import QBrush, QColor, QPen, QPolygonF
    tris = getattr(window, "_cut_ghost", None)
    if not tris:
        return
    from PyQt5.QtGui import QPainterPath
    # ONE path, winding-filled once: overlapping triangles no longer
    # pile up into an opaque block that read as a boss standing up
    path = QPainterPath()
    path.setFillRule(Qt.WindingFill)
    for t in tris:
        pts = [project(v) for v in t]
        if None in pts:
            continue
        # all one way round on screen: a triangle and its reversed twin
        # would cancel in the winding fill and leave the wall empty
        (ax, ay), (bx, by), (cx, cy) = ((p[0], p[1]) for p in pts)
        if (bx - ax) * (cy - ay) - (cx - ax) * (by - ay) < 0:
            pts = [pts[0], pts[2], pts[1]]
        path.addPolygon(QPolygonF([QPointF(p[0], p[1]) for p in pts]))
        path.closeSubpath()
    painter.save()
    painter.setRenderHint(painter.Antialiasing, True)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(QColor(*RED, 45)))
    painter.drawPath(path.simplified())
    # its real edges (where faces fold), so it reads as a pocket
    pen = QPen(QColor(*RED, 230), 1.5)
    pen.setCosmetic(True)
    painter.setPen(pen)
    for a, b in _edges(tris):
        pa, pb = project(a), project(b)
        if pa is not None and pb is not None:
            painter.drawLine(QPointF(pa[0], pa[1]), QPointF(pb[0], pb[1]))
    painter.restore()


def _edges(tris, angle=30.0):
    """The fold edges of a mesh (faces meeting past *angle*) and its
    open borders — a cylinder's facets are not edges."""
    import math
    def key(v):
        return (round(v[0], 4), round(v[1], 4), round(v[2], 4))

    def normal(t):
        a, b, c = t
        u = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
        w = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
        n = (u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2],
             u[0] * w[1] - u[1] * w[0])
        L = math.sqrt(sum(x * x for x in n)) or 1.0
        return tuple(x / L for x in n)
    seen = {}
    unique, keys = [], set()
    for t in tris:
        # the same triangle twice (either way round) is ONE face: the
        # copies made fold "edges" across flat caps (the user's fan of
        # red lines)
        k = frozenset(key(v) for v in t)
        if len(k) == 3 and k not in keys:
            keys.add(k)
            unique.append(t)
    for t in unique:
        n = normal(t)
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            ka, kb = key(a), key(b)
            k = (ka, kb) if ka <= kb else (kb, ka)
            seen.setdefault(k, []).append((n, a, b))
    cos = math.cos(math.radians(angle))
    out = []
    for faces in seen.values():
        # (a selection pass can hand duplicate triangles over, some the
        # other way round: any two faces on the edge folding past the
        # angle — either way up — make it an edge)
        ns = [f[0] for f in faces]
        fold = len(ns) == 1 or any(
            abs(sum(x * y for x, y in zip(ns[i], ns[j]))) < cos
            for i in range(len(ns)) for j in range(i + 1, len(ns)))
        if fold:
            out.append((faces[0][1], faces[0][2]))
    return out

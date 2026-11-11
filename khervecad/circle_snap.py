"""Snapping a new circle like SolidWorks (2026-11-11, the user: "the
centre on the line, so it's not fixed to a point, it's fixed on the
centre line … snapped to centres and origin, but also to tangent of
circles").

- `on_curve(scene, pos)` — the nearest point ON a sketch line, arc or
  circle (centerlines too) within a few pixels: a first point placed
  there lands on it, and `sketch_touch.relate` then ties it with Point
  on curve, so it slides along that line;
- `tangent_radius(scene, centre, radius)` — the radius that makes a
  circle round *centre* touch another circle / arc (outside or inside)
  or a line, when the dragged radius is near it; the Circle tool snaps
  to it and `tie` adds the Tangent relation once the circle is made.

Everything works in scene coordinates (a shape in a turned frame is
mapped through it).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

SNAP_PX = 8.0


def _px(scene, pixels):
    from .polygon_draw import px_to_scene
    return px_to_scene(scene, pixels)


def curves(scene):
    """[(node, entity, ("seg", a, b) | ("arc", cx, cy, r, a0, sweep))]
    of the sketch's lines, arcs and circles, in scene coordinates."""
    from PyQt5.QtCore import QPointF
    from . import sketch_constrain_ui as scu, sketch_trim
    from .view2d import is_sketch_point
    from .view2d_edit import Frame
    out = []
    for item in scu._shape_items(scene):
        node = item.node
        if node.type == "circle" and is_sketch_point(node):
            continue
        cv = sketch_trim.curve_of(node)
        if cv is None:
            continue
        frame = item.parentItem()
        to_s = (lambda x, y, f=frame: f.mapToScene(QPointF(x, y))) \
            if isinstance(frame, Frame) else (lambda x, y: QPointF(x, y))
        if cv[0] == "seg":
            a, b = to_s(*cv[1]), to_s(*cv[2])
            out.append((node, "l", ("seg", (a.x(), a.y()), (b.x(), b.y()))))
        else:
            c = to_s(cv[1], cv[2])
            # (a frame turns and moves; it does not scale a sketch)
            out.append((node, "o", ("arc", c.x(), c.y(), cv[3], cv[4],
                                    cv[5])))
    return out


def on_curve(scene, pos, skip=None):
    """(QPointF, node, entity) — the point on a curve nearest *pos*
    within SNAP_PX, or None."""
    from PyQt5.QtCore import QPointF
    from . import sketch_trim
    tol = _px(scene, SNAP_PX)
    p = (pos.x(), pos.y())
    best = None
    for node, ent, cv in curves(scene):
        if node is skip:
            continue
        t = sketch_trim.t_of(cv, p)
        q = sketch_trim.point_at(cv, t)
        d = math.hypot(q[0] - p[0], q[1] - p[1])
        if d <= tol and (best is None or d < best[0]):
            best = (d, q, node, ent)
    if best is None:
        return None
    return QPointF(*best[1]), best[2], best[3]


def tangent_radius(scene, centre, radius, skip=None):
    """(radius, node, entity) the circle round *centre* would have to
    touch another curve, nearest *radius* within SNAP_PX, or None."""
    tol = _px(scene, SNAP_PX)
    c = (centre.x(), centre.y())
    best = None
    for node, ent, cv in curves(scene):
        if node is skip:
            continue
        if cv[0] == "seg":
            a, b = cv[1], cv[2]
            dx, dy = b[0] - a[0], b[1] - a[1]
            L = math.hypot(dx, dy)
            if L < 1e-12:
                continue
            cands = [abs((c[0] - a[0]) * dy - (c[1] - a[1]) * dx) / L]
        else:
            d = math.hypot(c[0] - cv[1], c[1] - cv[2])
            cands = [d + cv[3], abs(d - cv[3])]
        for r in cands:
            if r > 1e-9 and abs(r - radius) <= tol and \
                    (best is None or abs(r - radius) < best[0]):
                best = (abs(r - radius), r, node, ent)
    return None if best is None else best[1:]


def tie(model, circle, target):
    """The Tangent relation between the new *circle* and *target*
    (node, entity), when they share a sketch."""
    from . import sketch_constraints as sc
    if target is None:
        return
    node, ent = target
    parent = circle.parent
    if parent is None or node.parent is not parent:
        return
    try:
        sc.add(model, parent, "tangent", [sc.ref_of(parent, node, ent),
                                          sc.ref_of(parent, circle, "o")])
    except (ValueError, KeyError):
        pass

"""WIREFRAME on the 3D view's own toolbar (2026-10-29, the user, from
SolidCraft: sketches seen as wire lines on their planes among the parts).

Switched on, the parts are drawn in the Wireframe render style (their
edges) and every 2D sketch shape in view is drawn as its LINES on its own
plane — a line as a segment, a circle / rectangle / polygon as its
outline, construction dashed — over the parts, so the sketches that make
a part (and the ones still waiting to) read in 3D. Off, the style the
user had comes back. The same action sits in View ▸ Wireframe.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

SKETCH_INK = "#1f7ae0"
CONSTRUCTION_INK = "#7a8a99"


def action(window):
    act = getattr(window, "_wireframe_act", None)
    if act is not None:
        return act
    from PyQt5.QtWidgets import QAction
    from . import icons, language, tooltips
    tooltips.TIPS.setdefault("wireframe_bar", (
        "Wireframe",
        "Shows the parts as their edges and every sketch as its lines on "
        "its plane — what a part is made of, and the sketches still "
        "waiting to become one.",
        ["Click to switch it on; click again for the shaded parts."],
        "Pick a sketch's area in 3D (Extruded Boss / Cut) while it is on."))
    act = QAction(icons.icon("mdi.cube-outline"),
                  language.tr("Wireframe"), window)
    act.setCheckable(True)
    tooltips.apply(act, "wireframe_bar")
    act.toggled.connect(lambda on: set_on(window, on))
    window._wireframe_act = act
    return act


def is_on(window):
    return bool(getattr(window.view3d, "wireframe", False))


def set_on(window, on):
    view = window.view3d
    on = bool(on)
    if on == is_on(window):
        return
    view.wireframe = on
    if on:
        view._style_before_wire = view.style
        # see-through faces; the real EDGES are drawn by paint (the
        # Wireframe style drew every triangle — far too busy)
        view.style = "X-ray"              # not saved: a view switch
    else:
        view.style = getattr(view, "_style_before_wire", None) or \
            "Shaded"
    act = getattr(window, "_wireframe_act", None)
    if act is not None and act.isChecked() != on:
        act.blockSignals(True)
        act.setChecked(on)
        act.blockSignals(False)
    if not view._gl_active():
        view._start_bsp_build()
    view.update()


def _shapes(window):
    """(shape, 4x4 world matrix of its params frame) for every 2D shape
    in view."""
    from . import mesh
    from .model import SHAPE_2D
    root = window.model.root
    scope = window._render_scope()[0]
    iso = scope if scope is not root else None
    out = []

    def shown(node):
        probe = node
        while probe is not None and probe is not (iso or root):
            if not probe.visible and not (iso is not None and
                                          probe is iso):
                return False
            probe = probe.parent
        return True
    base = iso or root
    with window._isolated_frame(iso):
        for node in base.walk():
            if node.category != SHAPE_2D or not shown(node):
                continue
            if node.parent is not None and \
                    node.parent.category == SHAPE_2D:
                continue                   # a piece of a 2D boolean
            out.append((node, mesh.ancestor_matrix(node, {}, stop=iso)))
    return out


def _apply(m, p):
    return tuple(m[i][0] * p[0] + m[i][1] * p[1] + m[i][2] * p[2]
                 + m[i][3] for i in range(3))


def paint(window, painter, project):
    """Every sketch's lines, over the parts (an overlay painter)."""
    if not is_on(window):
        return
    from PyQt5.QtCore import QPointF, Qt
    from PyQt5.QtGui import QColor, QPen
    from . import mesh
    try:
        shapes = _shapes(window)
    except Exception:                       # never break the paint
        return
    painter.save()
    painter.setRenderHint(painter.Antialiasing, True)
    _paint_edges(window, painter, project)
    for node, m in shapes:
        construction = node.params.get("modifier") == "%"
        pen = QPen(QColor(CONSTRUCTION_INK if construction
                          else SKETCH_INK), 1.8)
        pen.setCosmetic(True)
        if construction:
            pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        try:
            if node.type == "line":
                p = node.params
                loops = [[(float(p["x1"]), float(p["y1"])),
                          (float(p["x2"]), float(p["y2"]))]]
                closed = False
            else:
                loops = mesh.node_outlines(node, {})
                closed = True
        except Exception:
            continue
        for loop in loops:
            pts = []
            for x, y in loop:
                q = project(_apply(m, (float(x), float(y), 0.0)))
                if q is None:
                    pts = []
                    break
                pts.append(QPointF(q[0], q[1]))
            if len(pts) < 2:
                continue
            if closed:
                pts.append(pts[0])
            for a, b in zip(pts, pts[1:]):
                painter.drawLine(a, b)
    painter.restore()


EDGE_INK = "#3a4048"


def _edges(view):
    """The part's real edges (creases + open borders) in world space,
    cached per mesh."""
    tris = getattr(view, "model_mesh", None) or getattr(view, "mesh", None)
    if not tris:
        return []
    key = (id(tris), len(tris))
    cache = getattr(view, "_wire_edges", None)
    if cache is not None and cache[0] == key:
        return cache[1]
    from . import shading
    try:
        info = shading.analyse([t[:3] for t in tris])
    except Exception:
        return []
    seen, out = set(), []
    for _face, pairs in info.creases.items():
        for p, q in pairs:
            k = (tuple(round(c, 4) for c in p), tuple(round(c, 4) for c in q))
            if k in seen or k[::-1] in seen:
                continue
            seen.add(k)
            out.append((p, q))
    view._wire_edges = (key, out)
    return out


def _paint_edges(window, painter, project):
    from PyQt5.QtCore import QPointF
    from PyQt5.QtGui import QColor, QPen
    pen = QPen(QColor(EDGE_INK), 1.3)
    pen.setCosmetic(True)
    painter.setPen(pen)
    for p, q in _edges(window.view3d):
        a, b = project(p), project(q)
        if a is None or b is None:
            continue
        painter.drawLine(QPointF(a[0], a[1]), QPointF(b[0], b[1]))

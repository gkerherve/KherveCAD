# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""Sketch shapes no feature uses yet, drawn in the 3D view as lines on
their plane (2026-11-12, the user's trimmed rectangle was invisible: a
loose sketch showed only its dimensions). SolidWorks shows an unused
sketch the same way. Construction shapes stay out; a used sketch is the
feature's (selection_sketch outlines it when selected).

Painted through View3D's ``overlay_painters``; the loops are worked out
once per model change.
"""

INK = (30, 90, 200)
#: at most this many shapes drawn
MAX_SHAPES = 300


def install(window):
    window._free_sketch_loops = None

    def stale(*_a):
        window._free_sketch_loops = None
    window.model.structure_changed.connect(stale)
    window.model.node_changed.connect(stale)
    window.view3d.overlay_painters.append(
        lambda painter, project: paint(window, painter, project))


def _loops(window):
    from . import sketch_regions
    loops = getattr(window, "_free_sketch_loops", None)
    scope = window._render_scope()[0]
    if loops is not None and loops[0] is scope:
        return loops[1]
    if scope is window.model.root:
        # the Main assembly: parts only (its Objects' sketches are theirs)
        window._free_sketch_loops = (scope, [])
        return []
    try:
        ids = [n.id for n in sketch_regions.free_shapes(window)
               if n.params.get("modifier") != "%"][:MAX_SHAPES]
        got = window._selection_outlines(ids) if ids else []
    except Exception:
        got = []
    window._free_sketch_loops = (scope, got)
    return got


def paint(window, painter, project):
    loops = _loops(window)
    if not loops:
        return
    from PyQt5.QtCore import QPointF, Qt
    from PyQt5.QtGui import QColor, QPen
    painter.save()
    try:
        pen = QPen(QColor(*INK), 1.6)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        for loop in loops:
            pts = [project(p) for p in loop]
            for a, b in zip(pts, pts[1:]):
                if a is not None and b is not None:
                    painter.drawLine(QPointF(a[0], a[1]),
                                     QPointF(b[0], b[1]))
    finally:
        painter.restore()

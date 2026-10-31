"""Every sketch's dimensions on the face you sketch on (2026-11-01, the
user: "select any face of the objects and see all the constraints — for
now it's only a contour"). While a face sketch is open, the other
sketches lying in that plane (the plate's, the block's, a rib's) show
their Smart Dimensions in grey, read-only, through sketch_dims3d's own
painter with a projection onto the face: world -> the sketch's frame,
anything off the plane dropped.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

#: mm off the face's plane still on it
PLANE_TOL = 1e-3
GREY = "#6f7f8f"


def _window(view):
    w = view.window()
    return w if hasattr(w, "_face_sketch") else None


def paint(view, painter):
    """Called from SketchView.drawForeground (scene coordinates).
    Returns the values drawn."""
    from PyQt5.QtCore import QPointF
    from . import face_sketch, sketch_dims3d
    window = _window(view)
    group = getattr(window, "_face_sketch", None) if window else None
    if group is None or group.parent is None:
        return []
    n = face_sketch._normal_of(group)
    o = face_sketch.to_world(group, 0.0, 0.0)

    def project(p):
        d = sum((p[i] - o[i]) * n[i] for i in range(3))
        if abs(d) > PLANE_TOL:
            return None
        lx, ly = face_sketch.to_local(group, p)
        q = view.mapFromScene(QPointF(lx, ly))
        return q.x(), q.y(), 0.0
    painter.save()
    painter.resetTransform()
    try:
        return sketch_dims3d.paint(window, painter, project, skip=[group],
                                   hits=False, occlude=False,
                                   colour=GREY) or []
    finally:
        painter.restore()

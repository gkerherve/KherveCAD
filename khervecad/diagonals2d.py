# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""The 2D sketch's half of diagonals.py: both diagonals of the face
sketched on (when it is a rectangle) and of every rectangle drawn,
dashed under the shapes, and snapped to — on a diagonal or at the
centre where they cross."""

#: pixels: a click this near the centre takes it, this near a diagonal
#: lands on it
POINT_PX = 9.0
LINE_PX = 6.0


def quads(scene):
    """Rectangles in SCENE coordinates."""
    from . import diagonals
    out = []
    info = getattr(scene, "face_outline", None) or {}
    q = diagonals.quad_of_segments(info.get("segments") or [])
    if q:
        out.append(q)
    for item in scene.items():
        node = getattr(item, "node", None)
        if node is None or not hasattr(item, "isVisible") or \
                not item.isVisible():
            continue
        corners = diagonals.rect_corners(node)
        if not corners:
            continue
        frame = item.parentItem()
        from PyQt5.QtCore import QPointF
        pts = []
        for x, y in corners:
            p = QPointF(x, y)
            if frame is not None:
                p = frame.mapToScene(p)
            pts.append((p.x(), p.y()))
        out.append(pts)
    return out


def _k(scene):
    views = scene.views()
    return abs(views[0].transform().m11()) if views else 1.0


def snap(scene, pos):
    """(QPointF, kind) on a diagonal or at a centre, else None."""
    from PyQt5.QtCore import QPointF
    from . import diagonals
    k = _k(scene) or 1.0
    got = diagonals.snap((pos.x(), pos.y()), quads(scene),
                         POINT_PX / k, LINE_PX / k)
    if got is None:
        return None
    (x, y), kind = got
    return QPointF(x, y), ("centre" if kind == "centre" else "on_line")


def paint(scene, painter):
    from PyQt5.QtCore import QPointF, Qt
    from PyQt5.QtGui import QColor, QPen
    from . import diagonals
    qs = quads(scene)
    if not qs:
        return
    k = _k(scene) or 1.0
    pen = QPen(QColor("#7a8a99"), 1.0, Qt.DashLine)
    pen.setCosmetic(True)
    painter.save()
    painter.setPen(pen)
    for q in qs:
        for a, b in diagonals.diagonals(q):
            painter.drawLine(QPointF(*a), QPointF(*b))
        c = diagonals.centre(q)
        s = 4.0 / k
        painter.drawLine(QPointF(c[0] - s, c[1]), QPointF(c[0] + s, c[1]))
        painter.drawLine(QPointF(c[0], c[1] - s), QPointF(c[0], c[1] + s))
    painter.restore()

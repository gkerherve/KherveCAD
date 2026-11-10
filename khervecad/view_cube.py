"""The 3D view's **view cube** (top right, like Fusion's ViewCube and
SolidWorks' triad): a small cube turned with the camera. A click on a
face (Front, Top, Right…) looks square on to it, on an edge between the
two faces, on a corner from that corner; a drag on the cube orbits the
view. View ▸ Hide / show ▸ View Cube (QSettings `render_view_cube`).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from PyQt5.QtCore import QPointF, Qt, QSettings
from PyQt5.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PyQt5.QtWidgets import QAction, QWidget

SIZE = 110            # the widget, px
MARGIN = 10           # from the view's top-right corner
CUBE = 33             # half the cube's side on screen, px
EDGE = 0.32           # an edge / corner band, as a fraction of the half side
DRAG_PX = 4

#: face normal -> (name, the face's two in-plane axes)
FACES = {
    (0, -1, 0): ("FRONT", (1, 0, 0), (0, 0, 1)),
    (0, 1, 0): ("BACK", (-1, 0, 0), (0, 0, 1)),
    (1, 0, 0): ("RIGHT", (0, 1, 0), (0, 0, 1)),
    (-1, 0, 0): ("LEFT", (0, -1, 0), (0, 0, 1)),
    (0, 0, 1): ("TOP", (1, 0, 0), (0, 1, 0)),
    (0, 0, -1): ("BOTTOM", (1, 0, 0), (0, -1, 0)),
}
AXIS = {0: QColor("#e0443e"), 1: QColor("#3fae49"), 2: QColor("#3d7be0")}


def angles(direction):
    """(yaw, pitch) of a camera looking FROM *direction* at the target —
    the inverse of `View3D._orientation` (eye = -forward)."""
    dx, dy, dz = direction
    n = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
    dx, dy, dz = dx / n, dy / n, dz / n
    pitch = math.degrees(math.asin(max(-1.0, min(1.0, dz))))
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return -90.0, 89.0 if dz > 0 else -89.0     # square on Top / Bottom
    return math.degrees(math.atan2(dy, dx)), max(-89.0, min(89.0, pitch))


def cells():
    """Every clickable patch: (direction, face normal, quad corners in
    cube units). Each face is 3 x 3: the middle the face, the sides its
    edges, the corners its corners — 26 directions in all."""
    out = []
    cuts = (-1.0, -1.0 + 2 * EDGE / 2, 1.0 - 2 * EDGE / 2, 1.0)
    for normal, (_name, u, v) in FACES.items():
        for i in range(3):
            for j in range(3):
                a0, a1 = cuts[i], cuts[i + 1]
                b0, b1 = cuts[j], cuts[j + 1]
                du, dv = i - 1, j - 1
                d = tuple(normal[k] + du * u[k] + dv * v[k] for k in range(3))

                def pt(a, b):
                    return tuple(normal[k] + a * u[k] + b * v[k]
                                 for k in range(3))
                out.append((d, normal, [pt(a0, b0), pt(a1, b0),
                                        pt(a1, b1), pt(a0, b1)]))
    return out


_CELLS = cells()


def go_to(view, direction):
    """Glide the camera to look from *direction*, framed; a click on the
    face already shown turns it a quarter, like the bar's view buttons."""
    from . import viewnav
    yaw, pitch = angles(direction)
    for name, (y0, p0) in view.VIEWS.items():
        if abs(y0 - yaw) < 0.01 and abs(p0 - pitch) < 0.01 or \
                (name in ("Top", "Bottom") and abs(p0 - pitch) < 0.01):
            viewnav.view_click(view, name)
            return
    back = getattr(view, "_kc_restore_projection", None)
    if back:
        view.projection = back
        view._kc_restore_projection = None
    start = dict(yaw=view.yaw, pitch=view.pitch, target=list(view.target),
                 distance=view.distance)
    view.yaw, view.pitch = yaw, pitch
    view.fit()
    goal = dict(yaw=view.yaw, pitch=view.pitch, target=list(view.target),
                distance=view.distance)
    view.yaw, view.pitch = start["yaw"], start["pitch"]
    view.target, view.distance = start["target"], start["distance"]
    from . import view_anim
    view_anim.glide_3d(view, goal)


class ViewCube(QWidget):
    """The cube itself, a child of the 3D view (it repaints with it)."""

    def __init__(self, view):
        super().__init__(view)
        self.view = view
        self.setFixedSize(SIZE, SIZE)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        self.hover = None
        self._press = None
        self._dragged = False
        view.installEventFilter(self)
        self.place()

    # ------------------------------------------------------------ geometry
    def _screen(self, p):
        right, up, _fwd = self.view._orientation()
        sx = sum(p[k] * right[k] for k in range(3))
        sy = sum(p[k] * up[k] for k in range(3))
        return QPointF(SIZE / 2 + CUBE * sx, SIZE / 2 - CUBE * sy)

    def _visible(self):
        """The cells facing the camera, back to front."""
        _r, _u, fwd = self.view._orientation()
        out = []
        for d, normal, quad in _CELLS:
            facing = -sum(normal[k] * fwd[k] for k in range(3))
            if facing > 1e-3:
                out.append((facing, d, normal, quad))
        out.sort(key=lambda c: c[0])
        return out

    def cell_at(self, pos):
        for _f, d, _n, quad in reversed(self._visible()):
            poly = QPolygonF([self._screen(p) for p in quad])
            if poly.containsPoint(QPointF(pos), Qt.OddEvenFill):
                return d
        return None

    # ------------------------------------------------------------- painting
    def paintEvent(self, event):
        from .style import tokens
        dark = QColor(tokens().get("window", "#ffffff")).lightness() < 128
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        base = QColor(70, 78, 90, 225) if dark else QColor(236, 239, 244, 235)
        line = QColor(150, 160, 175) if dark else QColor(120, 128, 140)
        ink = QColor(230, 234, 240) if dark else QColor(50, 56, 66)
        light = QColor(60, 140, 230, 200)
        _r, _u, fwd = self.view._orientation()
        for facing, d, normal, quad in self._visible():
            poly = QPolygonF([self._screen(pt) for pt in quad])
            shade = base.darker(int(100 + 22 * (1 - facing)))
            p.setPen(Qt.NoPen)
            p.setBrush(light if d == self.hover else shade)
            p.drawPolygon(poly)
        # face outlines and names
        p.setBrush(Qt.NoBrush)
        font = QFont()
        font.setPixelSize(10)
        font.setBold(True)
        p.setFont(font)
        for normal, (name, u, v) in FACES.items():
            facing = -sum(normal[k] * fwd[k] for k in range(3))
            if facing <= 1e-3:
                continue
            corners = [tuple(normal[k] + a * u[k] + b * v[k]
                             for k in range(3))
                       for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
            p.setPen(QPen(line, 1.2))
            p.drawPolygon(QPolygonF([self._screen(c) for c in corners]))
            if facing > 0.2:
                c = self._screen(normal)
                p.setPen(ink)
                p.save()
                p.translate(c)
                # the label lies on the face: map its u / v axes
                ua, va = self._screen(u), self._screen(v)
                o = QPointF(SIZE / 2, SIZE / 2)
                ux, uy = (ua.x() - o.x()) / CUBE, (ua.y() - o.y()) / CUBE
                vx, vy = (va.x() - o.x()) / CUBE, (va.y() - o.y()) / CUBE
                from PyQt5.QtGui import QTransform
                p.setTransform(QTransform(ux, uy, -vx, -vy, 0, 0), True)
                p.drawText(-30, -8, 60, 16, Qt.AlignCenter, name)
                p.restore()
        # axis triad at the cube's back-bottom-left corner
        origin = (-1.25, -1.25, -1.25)
        for axis in range(3):
            tip = list(origin)
            tip[axis] += 1.0
            p.setPen(QPen(AXIS[axis], 2))
            a, b = self._screen(origin), self._screen(tip)
            p.drawLine(a, b)
            p.drawText(QPointF(b.x() - 3, b.y() + 4), "XYZ"[axis])
        p.end()

    # ---------------------------------------------------------------- mouse
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._press = event.pos()
            self._last = event.pos()
            self._dragged = False
        event.accept()

    def mouseMoveEvent(self, event):
        if self._press is not None and event.buttons() & Qt.LeftButton:
            if (event.pos() - self._press).manhattanLength() > DRAG_PX:
                self._dragged = True
            if self._dragged:
                delta = event.pos() - self._last
                self._last = event.pos()
                view = self.view
                view.yaw = (view.yaw - delta.x() * 0.8) % 360.0
                view.pitch = max(-89.0, min(89.0,
                                            view.pitch + delta.y() * 0.8))
                view.update()
            return
        cell = self.cell_at(event.pos())
        if cell != self.hover:
            self.hover = cell
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._press is not None:
            if not self._dragged:
                cell = self.cell_at(event.pos())
                if cell is not None:
                    go_to(self.view, cell)
            self._press = None
        event.accept()

    def leaveEvent(self, event):
        self.hover = None
        self.update()

    # ------------------------------------------------------------ placement
    def place(self):
        view = self.view
        self.move(view.width() - SIZE - MARGIN, MARGIN)
        self.raise_()

    def eventFilter(self, obj, event):
        from PyQt5.QtCore import QEvent
        if obj is self.view and event.type() == QEvent.Resize:
            self.place()
        return False


def attach(view):
    """Put the cube on *view* (view.view_cube), shown as last chosen."""
    cube = ViewCube(view)
    view.view_cube = cube
    on = QSettings().value("render_view_cube", True, type=bool)
    cube.setVisible(on)
    return cube


def action(win):
    """The View Cube switch for the 3D bar's Hide / show menu."""
    from .language import tr
    act = QAction(tr("View Cube"), win)
    act.setCheckable(True)
    cube = getattr(win.view3d, "view_cube", None)
    act.setChecked(cube is not None and not cube.isHidden())

    def toggled(on):
        QSettings().setValue("render_view_cube", bool(on))
        if cube is not None:
            cube.setVisible(on)
    act.toggled.connect(toggled)
    return act

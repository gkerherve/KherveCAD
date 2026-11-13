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
CUBE = 29             # half the cube's side on screen, px
EDGE = 0.32           # an edge / corner band, as a fraction of the half side
DRAG_PX = 4
#: how much of the half side a die's rounded corner takes
ROUND = 0.34

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


def _mix(a, b, t):
    """Colour *a* -> *b* at *t* in 0..1."""
    t = max(0.0, min(1.0, t))
    return QColor(int(a.red() + (b.red() - a.red()) * t),
                  int(a.green() + (b.green() - a.green()) * t),
                  int(a.blue() + (b.blue() - a.blue()) * t),
                  int(a.alpha() + (b.alpha() - a.alpha()) * t))


def _convex_hull(points):
    """The convex hull of QPointFs as a QPolygonF (monotone chain)."""
    pts = sorted({(round(q.x(), 2), round(q.y(), 2)) for q in points})
    if len(pts) < 3:
        return QPolygonF([QPointF(x, y) for x, y in pts])

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for q in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], q) <= 0:
            lower.pop()
        lower.append(q)
    for q in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], q) <= 0:
            upper.pop()
        upper.append(q)
    return QPolygonF([QPointF(x, y) for x, y in lower[:-1] + upper[:-1]])


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
    def _face_path(self, normal, u, v):
        """The face as a rounded square on screen: each corner cut
        `ROUND` of the half side back along both edges and curved
        through the true corner, like a die's."""
        from PyQt5.QtGui import QPainterPath

        def pt(a, b):
            return self._screen(tuple(normal[k] + a * u[k] + b * v[k]
                                      for k in range(3)))
        cs = ((-1, -1), (1, -1), (1, 1), (-1, 1))

        def toward(i, j):            # from corner i, ROUND toward j
            (a, b), (c, d) = cs[i], cs[j]
            t = ROUND / 2.0          # (an edge is 2 half sides long)
            return pt(a + (c - a) * t, b + (d - b) * t)
        path = QPainterPath()
        path.moveTo(toward(0, 1))
        for k in range(1, 5):
            i = k % 4
            path.lineTo(toward(i, (i - 1) % 4))
            path.quadTo(pt(*cs[i]), toward(i, (i + 1) % 4))
        path.closeSubpath()
        return path

    def _light(self, normal):
        """0..1: how much the cube's own light (up, left, towards the
        eye) falls on a face."""
        right, up, fwd = self.view._orientation()
        light = [0.45 * up[k] - 0.35 * right[k] - 0.8 * fwd[k]
                 for k in range(3)]
        n = math.sqrt(sum(c * c for c in light)) or 1.0
        return max(0.0, sum(normal[k] * light[k] for k in range(3)) / n)

    def paintEvent(self, event):
        from PyQt5.QtGui import (QBrush, QLinearGradient, QPainterPath,
                                 QRadialGradient, QTransform)
        from .style import tokens
        dark = QColor(tokens().get("window", "#ffffff")).lightness() < 128
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if dark:
            hi, lo = QColor(118, 128, 142), QColor(58, 64, 74)
            ink, rim = QColor(236, 240, 246), QColor(255, 255, 255, 60)
            body = _mix(lo, hi, 0.35)
        else:
            hi, lo = QColor(255, 253, 247), QColor(214, 207, 192)
            ink, rim = QColor(70, 66, 60), QColor(255, 255, 255, 200)
            body = _mix(lo, hi, 0.45)
        light = QColor(47, 123, 216, 150)
        _r, _u, fwd = self.view._orientation()
        faces = []
        for normal, (name, u, v) in FACES.items():
            facing = -sum(normal[k] * fwd[k] for k in range(3))
            if facing > 1e-3:
                faces.append((facing, normal, name, u, v))
        faces.sort(key=lambda f: f[0])
        paths = [(f, self._face_path(f[1], f[3], f[4])) for f in faces]
        # a soft shadow under the die
        c = QPointF(SIZE / 2, SIZE / 2 + CUBE * 1.55)
        shadow = QRadialGradient(c, CUBE * 1.3)
        shadow.setColorAt(0.0, QColor(0, 0, 0, 70 if dark else 55))
        shadow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(shadow))
        p.save()
        p.translate(c)
        p.scale(1.0, 0.32)
        p.drawEllipse(QPointF(0, 0), CUBE * 1.3, CUBE * 1.3)
        p.restore()
        # the body: what shows between the rounded faces (the die's
        # rounded corners)
        hull = QPolygonF()
        pts = []
        for _f, path in paths:
            poly = path.toFillPolygon()
            pts += [poly.at(i) for i in range(poly.count())]
        if pts:
            hull = _convex_hull(pts)
            p.setBrush(body)
            p.drawPolygon(hull)
        font = QFont()
        font.setPixelSize(9)
        font.setBold(True)
        font.setLetterSpacing(QFont.PercentageSpacing, 104)
        p.setFont(font)
        for (facing, normal, name, u, v), path in paths:
            lit = 0.35 + 0.65 * self._light(normal)
            top = _mix(lo, hi, min(1.0, lit + 0.12))
            bottom = _mix(lo, hi, max(0.0, lit - 0.18))
            a = self._screen(tuple(normal[k] + v[k] for k in range(3)))
            b = self._screen(tuple(normal[k] - v[k] for k in range(3)))
            grad = QLinearGradient(a, b)
            grad.setColorAt(0.0, top)
            grad.setColorAt(1.0, bottom)
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(grad))
            p.drawPath(path)
            # the hovered patch, kept inside the rounded face
            if self.hover is not None:
                for d, n2, quad in _CELLS:
                    if n2 == normal and d == self.hover:
                        cell = QPainterPath()
                        cell.addPolygon(QPolygonF(
                            [self._screen(q) for q in quad]))
                        p.setBrush(light)
                        p.drawPath(cell.intersected(path))
            # a bright rim, like light caught on the die's edge
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(rim, 1.0))
            p.drawPath(path)
            if facing > 0.25:
                ink2 = QColor(ink)
                ink2.setAlphaF(min(1.0, 0.35 + facing))
                p.setPen(ink2)
                p.save()
                p.translate(self._screen(normal))
                # of the label's four quarter turns on the face, the one
                # whose baseline runs most to the right reads best
                o = QPointF(SIZE / 2, SIZE / 2)

                def screen_dir(w):
                    q = self._screen(w)
                    return (q.x() - o.x()) / CUBE, (q.y() - o.y()) / CUBE
                neg = lambda w: tuple(-c for c in w)  # noqa: E731
                turns = [(u, v), (v, neg(u)), (neg(u), neg(v)),
                         (neg(v), u)]
                bu, bv = max(turns, key=lambda t: screen_dir(t[0])[0])
                ux, uy = screen_dir(bu)
                vx, vy = screen_dir(bv)
                p.setTransform(QTransform(ux, uy, -vx, -vy, 0, 0), True)
                p.drawText(-30, -8, 60, 16, Qt.AlignCenter, name)
                p.restore()
        # a thin outline round the whole die
        if pts:
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(0, 0, 0, 70 if dark else 45), 1.0))
            p.drawPolygon(hull)
        # a small axis triad in the bottom-left corner, clear of the die
        # (at the die's own corner it was drawn across its faces)
        tri = QFont()
        tri.setPixelSize(9)
        tri.setBold(True)
        p.setFont(tri)
        right, up, fwd = self.view._orientation()
        o = QPointF(16, SIZE - 16)
        order = sorted(range(3), key=lambda k: fwd[k])   # far ones first
        for axis in reversed(order):
            dx, dy = 13 * right[axis], -13 * up[axis]
            tip = QPointF(o.x() + dx, o.y() + dy)
            p.setPen(QPen(AXIS[axis], 2, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(o, tip)
            p.drawText(QPointF(tip.x() + dx * 0.35 - 3,
                               tip.y() + dy * 0.35 + 4), "XYZ"[axis])
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

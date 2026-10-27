"""Sketch in 3D (2026-10-27, the user: "we need to be able to draw a
sketch in the 3D. For example, select a plane in 3D and it stays there,
and then make a rectangle").

A `View3D.edit_tool`. First a click chooses WHERE: a drawn plane (the
main Front / Top / Right planes or any reference Plane) or a flat face
of a part — whichever is nearest under the cursor. The camera does not
move. A face-sketch Group is made on it (the same Group Sketch on Face
makes, so Edit Sketch, the extrude arrow and the cuts all work), and
then the clicks draw ON the plane, in 3D:

- Rectangle (R): two corners;
- Circle (C): the centre, then a point on the rim;
- Line (L): click to click, chained; right-click / Enter ends a chain.

Points snap to the grid (the sketch grid size) in the plane's own axes;
Alt draws free. Esc / Done ends the tool and selects the sketch, ready
for Extruded Boss. A press that moves turns the model as always.
`plane_hit` and `local_of` are the geometry, testable without a mouse.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from . import language, refgeom

MODES = ("rect", "circle", "line")
MODE_KEYS = {"R": "rect", "C": "circle", "L": "line"}


def start(window, mode="rect"):
    from . import drag_feature, refgeom_ui
    view = window.view3d
    drag_feature.step_aside(view)
    if view.edit_tool is not None:
        try:
            view.edit_tool.cancel()
        except Exception:
            view.edit_tool = None
    tool = Sketch3DTool(window, mode)
    view.edit_tool = tool
    # the camera stays where the user aimed it: the first shape drawn
    # must not trigger the first-geometry Fit
    view.user_moved = True
    # a Plane or a face sketch already selected: draw on it at once
    for node in window.builder.active_tree().selected_nodes():
        if node.type == "ref_plane":
            tool.use_group(refgeom_ui.sketch_on(window, node,
                                                open_2d=False))
            break
        from .face_sketch import group_of
        group = group_of(node)
        if group is not None:
            tool.use_group(group)
            break
    if tool.group is None:
        window._ref_force_planes = True   # show them while picking
    tool.begin()
    return tool


def snap(v, step):
    return round(v / step) * step if step > 0 else v


def tidy(v):
    return round(float(v), 4) + 0.0


def rect_params(a, b):
    x0, x1 = sorted((a[0], b[0]))
    y0, y1 = sorted((a[1], b[1]))
    return dict(x=tidy(x0), y=tidy(y0), width=tidy(x1 - x0),
                height=tidy(y1 - y0))


def circle_params(c, p):
    return dict(x=tidy(c[0]), y=tidy(c[1]),
                radius=tidy(math.hypot(p[0] - c[0], p[1] - c[1])))


class Sketch3DTool:
    """See the module docstring."""

    def __init__(self, window, mode="rect"):
        self.window = window
        self.view = window.view3d
        self.mode = mode if mode in MODES else "rect"
        self.group = None             # the sketch Group, once chosen
        self.points = []              # the shape being drawn (local)
        self.hover = None             # local point under the cursor
        self.target = None            # plane / face under the cursor
        self._press = None
        self._bar = None
        self._drag = None             # (node, role) of a dragged point
        self.made = []

    # -- life -------------------------------------------------------
    def begin(self):
        from PyQt5.QtCore import Qt
        v = self.view
        v.setMouseTracking(True)
        v.setCursor(Qt.CrossCursor)
        v.setFocus(Qt.OtherFocusReason)
        self._make_bar()
        self._say()
        v.update()

    def _make_bar(self):
        from PyQt5.QtWidgets import QHBoxLayout, QPushButton, QWidget
        bar = self._bar = QWidget(self.view)
        bar.setObjectName("sketch3d_bar")
        bar.setStyleSheet(
            "#sketch3d_bar { background: rgba(255,255,255,235); border: "
            "1px solid #8a8a8a; border-radius: 5px; } QPushButton "
            "{ padding: 3px 9px; } QPushButton:checked { background: "
            "#3c78dc; color: white; }")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(6, 4, 6, 4)
        self._buttons = {}
        for mode, text in (("rect", "Rectangle (R)"),
                           ("circle", "Circle (C)"), ("line", "Line (L)")):
            b = QPushButton(language.tr(text), bar)
            b.setCheckable(True)
            b.setChecked(mode == self.mode)
            b.clicked.connect(lambda _=False, m=mode: self.set_mode(m))
            lay.addWidget(b)
            self._buttons[mode] = b
        done = QPushButton(language.tr("Done"), bar)
        done.clicked.connect(lambda _=False: self.finish())
        lay.addWidget(done)
        bar.adjustSize()
        bar.move(12, max(8, self.view.height() - bar.height() - 70))
        bar.show()

    def set_mode(self, mode):
        self.mode = mode
        self.points = []
        for m, b in getattr(self, "_buttons", {}).items():
            b.setChecked(m == mode)
        self._say()
        self.view.update()

    def _say(self):
        if self.group is None:
            text = ("Sketch in 3D: click a plane (Front, Top, Right or "
                    "your own) or a flat face of a part to draw on.")
        else:
            text = {"rect": "Rectangle: click two corners on the plane.",
                    "circle": "Circle: click the centre, then the rim.",
                    "line": "Line: click point to point; right-click or "
                            "Enter ends the chain."}[self.mode] + \
                " R / C / L switch, Alt draws off the grid, Esc ends."
        self.message(language.tr(text))

    def message(self, text, ms=0):
        try:
            self.window.statusBar().showMessage(text, ms)
        except Exception:                           # pragma: no cover
            pass

    def _end(self):
        self.window._ref_force_planes = False
        v = self.view
        if v.edit_tool is self:
            v.edit_tool = None
        if self._bar is not None:
            self._bar.hide()
            self._bar.deleteLater()
            self._bar = None
        v.setMouseTracking(False)
        v.unsetCursor()
        v.update()

    def cancel(self):
        self.finish()

    def finish(self):
        """End the tool; an empty sketch goes, a full one is selected."""
        self._end()
        g = self.group
        if g is None or g.parent is None:
            self.message(language.tr("Sketch in 3D ended."), 4000)
            return None
        if not g.children:
            self.window.model.remove_node(g)
            self.message(language.tr("Sketch in 3D ended (nothing drawn)."),
                         4000)
            return None
        try:
            self.window.builder.active_tree().select_nodes([g])
        except Exception:
            pass
        self.message(language.tr(
            "Sketch done — Extruded Boss (or drag its arrow) makes it "
            "solid."), 8000)
        return g

    # -- where ------------------------------------------------------
    def use_group(self, group):
        self.window._ref_force_planes = False     # picked: hide again
        self.group = group
        self.points = []
        self._say()

    def plane_hit(self, x, y):
        """(origin, normal, label, what) of the plane or flat face under
        the screen point, nearest first, or None."""
        from . import refgeom_ui
        from .curve_draw import Snapper
        from .sculpt_ui import screen_ray
        origin, d = screen_ray(self.view, x, y)
        best = None
        hit = refgeom_ui.plane_at(self.window, x, y)
        if hit is not None:
            label, o, n, _s, what, p = hit
            best = (math.dist(p, origin), o, n, label, what)
        mesh = getattr(self.view, "model_mesh", None) or self.view.mesh
        if mesh:
            snapper = getattr(self, "_snapper", None)
            if snapper is None or snapper.tris is not mesh:
                snapper = self._snapper = Snapper(mesh)
            got = snapper.hit(tuple(origin), tuple(d))
            if got is not None:
                p, n = got
                dist = math.dist(p, origin)
                if best is None or dist < best[0] - 1e-6:
                    best = (dist, [tidy(c) for c in p],
                            [tidy(c) for c in refgeom.unit(n)],
                            "face", None)
        return None if best is None else best[1:]

    def choose(self, x, y):
        from . import refgeom_ui
        got = self.plane_hit(x, y)
        if got is None:
            self.message(language.tr(
                "No plane or face there — aim at a drawn plane or a part."),
                4000)
            return None
        o, n, label, what = got
        if hasattr(what, "type"):
            group = refgeom_ui.sketch_on(self.window, what, open_2d=False)
        else:
            if isinstance(what, str):
                from . import plane_pick
                label = plane_pick.name_of(what)
            group = refgeom_ui.sketch_on(self.window, origin=o, normal=n,
                                         label=language.tr(label),
                                         open_2d=False)
        self.use_group(group)
        self.view.update()
        return group

    # -- drawing ----------------------------------------------------
    def _grid(self):
        scene = getattr(self.window, "scene", None)
        try:
            step = float(getattr(scene, "grid_size", 1.0))
        except (TypeError, ValueError):
            step = 1.0
        return step if step > 0 else 1.0

    def local_of(self, x, y, free=False):
        """The point on the sketch plane under the screen point, in the
        sketch's own (x, y), snapped to the grid unless *free*."""
        from .face_sketch import _normal_of, to_local, to_world
        from .sculpt_ui import screen_ray
        g = self.group
        origin, d = screen_ray(self.view, x, y)
        o = to_world(g, 0.0, 0.0)
        n = _normal_of(g)
        p = refgeom.ray_plane(list(origin), list(d), o, n)
        if p is None:
            return None
        lx, ly = to_local(g, p)
        if not free:
            step = self._grid()
            lx, ly = snap(lx, step), snap(ly, step)
        return (tidy(lx), tidy(ly))

    def place(self, pt):
        """A click at sketch point *pt*."""
        model = self.window.model
        self.points.append(pt)
        node = None
        if self.mode == "rect" and len(self.points) == 2:
            par = rect_params(*self.points)
            if par["width"] > 0 and par["height"] > 0:
                node = model.add_node("rect", par, parent=self.group)
            self.points = []
        elif self.mode == "circle" and len(self.points) == 2:
            par = circle_params(*self.points)
            if par["radius"] > 0:
                node = model.add_node("circle", par, parent=self.group)
            self.points = []
        elif self.mode == "line" and len(self.points) >= 2:
            a, b = self.points[-2], self.points[-1]
            if a != b:
                node = model.add_node("line", dict(
                    x1=a[0], y1=a[1], x2=b[0], y2=b[1], width=1.0),
                    parent=self.group)
            else:
                self.points = []
        if node is not None:
            self.made.append(node)
        self.view.update()
        return node

    # -- dragging a drawn point (the constraints follow live) -------
    def handles(self):
        """[(node, role, local point)] of the sketch's draggable points."""
        out = []
        g = self.group
        if g is None or g.parent is None:
            return out
        for n in g.children:
            p = n.params
            try:
                if n.type == "line":
                    out += [(n, "p1", (float(p["x1"]), float(p["y1"]))),
                            (n, "p2", (float(p["x2"]), float(p["y2"])))]
                elif n.type == "rect":
                    x, y = float(p["x"]), float(p["y"])
                    w, h = float(p["width"]), float(p["height"])
                    out += [(n, "c0", (x, y)), (n, "c1", (x + w, y)),
                            (n, "c2", (x + w, y + h)), (n, "c3", (x, y + h))]
                elif n.type == "circle":
                    x, y, r = (float(p["x"]), float(p["y"]),
                               float(p["radius"]))
                    out += [(n, "centre", (x, y)), (n, "rim", (x + r, y))]
            except (KeyError, TypeError, ValueError):
                continue                 # an expression: not draggable
        return out

    def handle_at(self, x, y, px=9.0):
        from .face_sketch import to_world
        from PyQt5.QtCore import QPointF
        del QPointF
        v = self.view
        eye, right, up, forward = v._camera()
        best = None
        for node, role, lp in self.handles():
            s = v._project(eye, right, up, forward,
                           to_world(self.group, lp[0], lp[1]))
            if s is None or s[2] <= 0:
                continue
            d = math.hypot(s[0] - x, s[1] - y)
            if d <= px and (best is None or d < best[0]):
                best = (d, node, role)
        return None if best is None else best[1:]

    def drag_to(self, node, role, pt):
        """Move one point of a drawn shape; the model's constraints
        re-solve at once (MainWindow._model_edited)."""
        p = node.params
        if node.type == "line":
            kx, ky = ("x1", "y1") if role == "p1" else ("x2", "y2")
            p[kx], p[ky] = pt
        elif node.type == "rect":
            x, y = float(p["x"]), float(p["y"])
            w, h = float(p["width"]), float(p["height"])
            corners = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
            fixed = corners[(int(role[1]) + 2) % 4]
            p.update(rect_params(fixed, pt))
        elif node.type == "circle":
            if role == "centre":
                p["x"], p["y"] = pt
            else:
                p["radius"] = tidy(max(math.hypot(
                    pt[0] - float(p["x"]), pt[1] - float(p["y"])), 0.01))
        self.window.model.node_changed.emit(node)
        self.view.update()

    # -- the view's hooks -----------------------------------------
    def wants_key(self, event):
        from PyQt5.QtCore import Qt
        if event.modifiers() & (Qt.ControlModifier | Qt.MetaModifier):
            return False
        return event.key() in (Qt.Key_Escape, Qt.Key_Return, Qt.Key_Enter,
                               Qt.Key_R, Qt.Key_C, Qt.Key_L)

    def key_press(self, event):
        from PyQt5.QtCore import Qt
        key = event.key()
        if key == Qt.Key_Escape:
            if self.points:
                self.points = []
                self.view.update()
            else:
                self.finish()
        elif key in (Qt.Key_Return, Qt.Key_Enter):
            if self.points:
                self.points = []
                self.view.update()
            else:
                self.finish()
        elif event.text().upper() in MODE_KEYS:
            self.set_mode(MODE_KEYS[event.text().upper()])
        else:
            return False
        return True

    def mouse_press(self, event):
        from PyQt5.QtCore import Qt
        if event.button() == Qt.RightButton:
            if self.points:
                self.points = []
                self.view.update()
            else:
                self.finish()
            return True
        if event.button() != Qt.LeftButton:
            return False
        if self.group is not None and not self.points:
            grab = self.handle_at(event.pos().x(), event.pos().y())
            if grab is not None:
                self._drag = grab
                return True
        self._press = (event.pos(), event.modifiers())
        return False                 # the view may start an orbit

    def mouse_release(self, event):
        from PyQt5.QtCore import Qt
        if self._drag is not None:
            self._drag = None
            return True
        press, self._press = self._press, None
        if press is None or event.button() != Qt.LeftButton:
            return False
        if (event.pos() - press[0]).manhattanLength() > 4:
            return False                    # it was an orbit
        self.click(event.pos().x(), event.pos().y(),
                   bool(press[1] & Qt.AltModifier))
        return True

    def click(self, x, y, free=False):
        if self.group is None:
            self.choose(x, y)
            return None
        pt = self.local_of(x, y, free)
        if pt is None:
            self.message(language.tr("That is off the sketch plane."), 3000)
            return None
        return self.place(pt)

    def mouse_move(self, event):
        from PyQt5.QtCore import Qt
        x, y = event.pos().x(), event.pos().y()
        if self._drag is not None:
            pt = self.local_of(x, y, bool(event.modifiers() &
                                          Qt.AltModifier))
            if pt is not None:
                self.drag_to(self._drag[0], self._drag[1], pt)
            return True
        if self._press is not None:
            return False
        if self.group is None:
            self.target = self.plane_hit(x, y)
        else:
            self.hover = self.local_of(
                x, y, bool(event.modifiers() & Qt.AltModifier))
        self.view.update()
        return False

    def wheel(self, event):
        return False

    # -- drawing on screen ----------------------------------------
    def paint(self, painter, project):
        from PyQt5.QtCore import QPointF, Qt
        from PyQt5.QtGui import QColor, QPen
        from .face_sketch import to_world
        if self.group is None:
            if self.target is not None:
                o, n, label, _w = self.target
                from . import refgeom_ui
                size = refgeom_ui._half(self.window)
                pts = [project(c) for c in
                       refgeom_ui.plane_corners(o, n, size)]
                if all(p is not None and p[2] > 0 for p in pts):
                    from PyQt5.QtGui import QPolygonF
                    painter.setPen(QPen(QColor(240, 140, 30), 2))
                    painter.setBrush(QColor(240, 140, 30, 60))
                    painter.drawPolygon(QPolygonF(
                        [QPointF(p[0], p[1]) for p in pts]))
            return
        g = self.group
        if g.parent is None:
            return

        def scr(lp):
            p = project(to_world(g, lp[0], lp[1]))
            return QPointF(p[0], p[1]) if p is not None and p[2] > 0 else None
        pen = QPen(QColor(240, 140, 30), 2)
        pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        h = self.hover
        if self.points and h is not None:
            a = self.points[-1]
            if self.mode == "rect":
                corners = [a, (h[0], a[1]), h, (a[0], h[1]), a]
                qs = [scr(c) for c in corners]
                if all(qs):
                    for i in range(4):
                        painter.drawLine(qs[i], qs[i + 1])
                w, ht = abs(h[0] - a[0]), abs(h[1] - a[1])
                if qs[2] is not None:
                    painter.drawText(qs[2] + QPointF(8, -8),
                                     f"{w:g} × {ht:g}")
            elif self.mode == "circle":
                r = math.hypot(h[0] - a[0], h[1] - a[1])
                ring = [scr((a[0] + r * math.cos(t * math.pi / 24),
                             a[1] + r * math.sin(t * math.pi / 24)))
                        for t in range(49)]
                if all(ring):
                    for i in range(48):
                        painter.drawLine(ring[i], ring[i + 1])
                q = scr(h)
                if q is not None:
                    painter.drawText(q + QPointF(8, -8), f"Ø{2 * r:g}")
            else:
                qa, qh = scr(a), scr(h)
                if qa and qh:
                    painter.drawLine(qa, qh)
                    painter.drawText(qh + QPointF(8, -8), f"{math.hypot(h[0] - a[0], h[1] - a[1]):g}")
        painter.setPen(QPen(QColor(33, 118, 199), 1.2))
        painter.setBrush(QColor(255, 255, 255))
        for _n, _r, lp in self.handles():       # draggable points
            q = scr(lp)
            if q is not None:
                painter.drawRect(int(q.x()) - 3, int(q.y()) - 3, 6, 6)
        painter.setBrush(Qt.NoBrush)
        if h is not None:
            q = scr(h)
            if q is not None:
                painter.setPen(QPen(QColor(240, 140, 30), 1.5))
                painter.drawEllipse(q, 4.0, 4.0)

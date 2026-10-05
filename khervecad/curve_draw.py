"""Draw a 3D curve by clicking — with object snaps and typed coordinates.

The Rhino way of putting a point exactly where it belongs, for people
who have never used Rhino:

* **Click** to place a point. The cursor SNAPS, and says what it
  snapped to in plain words next to a coloured marker:
  **Corner** (a vertex where faces meet), **Middle of edge**, **On
  edge**, **On surface**, **Start point** (closes the loop), or, in
  empty space, a point **on the ground grid** at the working height.
* **Shift** while moving lifts the point straight UP or DOWN from the
  last one (Rhino's "elevator"): the ground grid only reaches so far.
* **Type** coordinates at any time — just start typing ``10, 20, 5``
  (or ``@0, 0, 15`` for "15 above the last point") and press Enter.
* **Enter**, a double-click or a right-click finishes; **Backspace**
  takes the last point back; **C** closes the loop; **Esc** cancels.
  Hold **Alt** to switch snapping off. Dragging still orbits the view.

The finished curve is an ordinary `curve` node (curve3d.py), one undo
step, created where any new shape would be — inside the Object being
edited, or as a new Object in Main.

The geometry here — `Snapper` and `parse_coords` — needs no Qt, so the
tests drive it directly.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math
import re

#: screen pixels within which a snap catches
SNAP_PX = 12
#: faces meeting at more than this many degrees make a real edge (a
#: cylinder's facets do not)
CREASE_DEG = 25.0

#: (label, colour) of each snap kind, what the marker says
KINDS = {
    "start": ("Start point — click to close the loop", "#e8a33a"),
    "point": ("Your point", "#e8a33a"),
    "corner": ("Corner", "#d64545"),
    "mid": ("Middle of edge", "#3a8ee8"),
    "edge": ("On edge", "#3aa8a8"),
    "surface": ("On surface", "#47a447"),
    "grid": ("On the ground grid", "#9a7ad6"),
    "vertical": ("Straight up / down from the last point", "#9a7ad6"),
    "free": ("In the air (snapping off)", "#888888"),
}


# ================================================================ maths

def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _len(a):
    return math.sqrt(_dot(a, a))


def _key(v):
    return (round(v[0], 5), round(v[1], 5), round(v[2], 5))


def closest_on_segment(p, a, b):
    ab = _sub(b, a)
    d = _dot(ab, ab)
    t = 0.0 if d < 1e-18 else max(0.0, min(1.0, _dot(_sub(p, a), ab) / d))
    return (a[0] + ab[0] * t, a[1] + ab[1] * t, a[2] + ab[2] * t)


def ray_point_distance(origin, d, p):
    """Distance from point *p* to the ray (origin, unit d), and the ray
    parameter of the closest point."""
    t = _dot(_sub(p, origin), d)
    q = (origin[0] + d[0] * t, origin[1] + d[1] * t, origin[2] + d[2] * t)
    return _len(_sub(p, q)), t


def ray_segment_closest(origin, d, a, b):
    """The point on segment ab nearest the ray, and its distance to it."""
    u = _sub(b, a)
    w0 = _sub(a, origin)
    aa, bb, cc = _dot(u, u), _dot(u, d), _dot(d, d)
    dd, ee = _dot(u, w0), _dot(d, w0)
    den = aa * cc - bb * bb
    s = 0.0 if abs(den) < 1e-18 else (bb * ee - cc * dd) / den
    s = max(0.0, min(1.0, s))
    q = (a[0] + u[0] * s, a[1] + u[1] * s, a[2] + u[2] * s)
    dist, _t = ray_point_distance(origin, d, q)
    return q, dist


def ray_vertical_closest(origin, d, base):
    """Where the vertical line through *base* comes nearest the ray —
    the elevator: the point straight above or below *base*."""
    up = (0.0, 0.0, 1.0)
    w0 = _sub(base, origin)
    b = _dot(up, d)
    den = 1.0 - b * b
    if den < 1e-9:
        return None
    s = (b * _dot(d, w0) - _dot(up, w0)) / den
    return (base[0], base[1], base[2] + s)


def ray_plane_z(origin, d, z):
    if abs(d[2]) < 1e-9:
        return None
    t = (z - origin[2]) / d[2]
    if t <= 0:
        return None
    return (origin[0] + d[0] * t, origin[1] + d[1] * t, z)


def snap_grid(p, step):
    if step <= 0:
        return p
    return (round(p[0] / step) * step, round(p[1] / step) * step, p[2])


def tidy(v, digits=4):
    out = round(v, digits)
    return 0.0 if out == 0 else out


# ============================================================== snapper

class Snapper:
    """Snap targets of a triangle mesh: its crease edges and their
    corners — a box's 12 edges and 8 corners, not the diagonals of its
    faces, and not the facets of a cylinder's side."""

    def __init__(self, tris, crease_deg=CREASE_DEG):
        self.tris = [tuple(tuple(float(c) for c in v) for v in t)
                     for t in tris]
        self.edges = []          # [(a, b)] crease edges
        self.corners = []        # vertices on crease edges
        self._array = None
        self._build(math.cos(math.radians(crease_deg)))

    def _build(self, cos_limit):
        owners = {}
        normals = []
        for i, t in enumerate(self.tris):
            n = _cross(_sub(t[1], t[0]), _sub(t[2], t[0]))
            ln = _len(n)
            normals.append((n[0] / ln, n[1] / ln, n[2] / ln) if ln > 1e-18
                           else (0.0, 0.0, 0.0))
            keys = [_key(v) for v in t]
            for k in range(3):
                a, b = keys[k], keys[(k + 1) % 3]
                e = (a, b) if a < b else (b, a)
                owners.setdefault(e, []).append(i)
        corners = set()
        for (a, b), who in owners.items():
            if len(who) == 2:
                if _dot(normals[who[0]], normals[who[1]]) > cos_limit:
                    continue                      # smooth: no edge here
            self.edges.append((a, b))
            corners.add(a)
            corners.add(b)
        self.corners = sorted(corners)

    def hit(self, origin, d):
        """Nearest hit of the ray on the mesh: (point, normal) or None."""
        try:
            import numpy as np
        except ImportError:                       # pragma: no cover
            return self._hit_py(origin, d)
        if self._array is None:
            self._array = np.asarray(self.tris, dtype=float).reshape(-1, 3, 3) \
                if self.tris else np.zeros((0, 3, 3))
        from .sculpt_ui import ray_hit
        point, normal = ray_hit(self._array, origin, d)
        if point is None:
            return None
        return tuple(float(c) for c in point), tuple(float(c) for c in normal)

    def _hit_py(self, origin, d):                  # pragma: no cover
        best = None
        for t in self.tris:
            e1, e2 = _sub(t[1], t[0]), _sub(t[2], t[0])
            p = _cross(d, e2)
            det = _dot(e1, p)
            if abs(det) < 1e-12:
                continue
            s = _sub(origin, t[0])
            u = _dot(s, p) / det
            q = _cross(s, e1)
            v = _dot(d, q) / det
            k = _dot(e2, q) / det
            if u < 0 or v < 0 or u + v > 1 or k <= 1e-6:
                continue
            if best is None or k < best[0]:
                n = _cross(e1, e2)
                ln = _len(n) or 1.0
                best = (k, (n[0] / ln, n[1] / ln, n[2] / ln))
        if best is None:
            return None
        k, n = best
        return (origin[0] + d[0] * k, origin[1] + d[1] * k,
                origin[2] + d[2] * k), n

    def snap(self, origin, d, tol_at, points=(), elevation=0.0,
             grid=1.0, vertical_from=None, enabled=True):
        """(point, kind) for the ray (origin, unit d). *tol_at(p)* is the
        snap tolerance in world units at point p (pixels -> mm at its
        depth). *points* are the curve's own points so far."""
        if vertical_from is not None:
            q = ray_vertical_closest(origin, d, vertical_from)
            if q is not None:
                return q, "vertical"
        surf = self.hit(origin, d)
        depth_pt = surf[0] if surf else None
        if not enabled:
            if surf:
                return surf[0], "free"
            q = ray_plane_z(origin, d, elevation)
            return (q, "free") if q else (None, None)
        # the curve's own points first: closing a loop is the commonest
        for i, p in enumerate(points):
            dist, t = ray_point_distance(origin, d, p)
            if t > 0 and dist <= tol_at(p) and (
                    depth_pt is None or t <= _dot(_sub(depth_pt, origin), d)
                    + tol_at(p)):
                return p, ("start" if i == 0 and len(points) > 1
                           else "point")
        if surf is not None:
            hit, _normal = surf
            tol = tol_at(hit)
            near = tol * 6           # only targets near what is seen
            best = None
            for c in self.corners:
                if _len(_sub(c, hit)) > near:
                    continue
                dist, t = ray_point_distance(origin, d, c)
                if dist <= tol and (best is None or dist < best[0]):
                    best = (dist, c, "corner")
            if best:
                return best[1], best[2]
            for a, b in self.edges:
                if _len(_sub(closest_on_segment(hit, a, b), hit)) > near:
                    continue
                m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2,
                     (a[2] + b[2]) / 2)
                dist, _t = ray_point_distance(origin, d, m)
                if dist <= tol and (best is None or dist < best[0]):
                    best = (dist, m, "mid")
            if best:
                return best[1], best[2]
            for a, b in self.edges:
                if _len(_sub(closest_on_segment(hit, a, b), hit)) > near:
                    continue
                q, dist = ray_segment_closest(origin, d, a, b)
                if dist <= tol and (best is None or dist < best[0]):
                    best = (dist, q, "edge")
            if best:
                return best[1], best[2]
            return hit, "surface"
        q = ray_plane_z(origin, d, elevation)
        if q is None:
            return None, None
        return snap_grid(q, grid), "grid"


# ======================================================== typed points

_NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"


def parse_coords(text, last=None, elevation=0.0):
    """A typed point: "x, y, z", "x y z", "x, y" (z = working height),
    or relative to the last point with "@dx, dy, dz". Returns the point,
    or raises ValueError with a sentence saying what is wrong."""
    s = str(text).strip()
    relative = s.startswith("@")
    if relative:
        s = s[1:]
    nums = re.findall(_NUM, s)
    rest = re.sub(_NUM, "", s).replace(",", " ").replace(";", " ").strip()
    if rest or len(nums) not in (2, 3):
        raise ValueError(
            "Type two or three numbers, like 10, 20, 5 — or @0, 0, 15 "
            "to go 15 up from the last point.")
    vals = [float(n) for n in nums]
    if relative:
        if last is None:
            raise ValueError("There is no last point yet to measure "
                             "from — type a point without the @ first.")
        if len(vals) == 2:
            vals.append(0.0)
        return (last[0] + vals[0], last[1] + vals[1], last[2] + vals[2])
    if len(vals) == 2:
        vals.append(elevation)
    return tuple(vals)


# =============================================================== the tool

def start(window):
    """Begin drawing (Insert ▸ Draw 3D Curve). Returns the tool."""
    from PyQt5.QtWidgets import QMessageBox
    from . import language
    view = window.view3d
    if isinstance(view.edit_tool, CurveTool):
        view.edit_tool.cancel()
    if view.edit_tool is not None:
        QMessageBox.information(window, language.tr("Draw 3D curve"),
                                language.tr("Finish what the 3D view is "
                                            "doing first (Esc)."))
        return None
    tool = CurveTool(window)
    view.edit_tool = tool
    tool.begin()
    return tool


class CurveTool:
    """View3D.edit_tool for drawing one curve; see the module docstring
    for the keys. Whatever it declines (drags, the wheel) the view does
    as always, so the model can be turned round between clicks."""

    def __init__(self, window):
        self.window = window
        self.view = window.view3d
        self.points = []
        self.hover = None            # (point, kind)
        self.elevation = 0.0
        self.snapper = Snapper(self.view.mesh or [])
        self._press = None
        self._box = None

    # -- life -------------------------------------------------------------
    def begin(self):
        from PyQt5.QtCore import Qt
        from PyQt5.QtWidgets import QLineEdit
        from . import language
        v = self.view
        v.setMouseTracking(True)
        v.setCursor(Qt.CrossCursor)
        v.setFocus(Qt.OtherFocusReason)
        box = self._box = QLineEdit(v)
        box.setPlaceholderText(language.tr(
            "Type a point: x, y, z — or @dx, dy, dz from the last one — "
            "and press Enter"))
        box.setClearButtonEnabled(True)
        box.returnPressed.connect(self._typed)
        box.setStyleSheet("QLineEdit { background: rgba(255,255,255,235);"
                          " color: #202020; border: 1px solid #8a8a8a;"
                          " border-radius: 4px; padding: 3px 6px; }")
        self._place_box()
        box.show()
        self.message(language.tr(
            "Draw a 3D curve: click points (they snap to corners, edges "
            "and surfaces), or type x, y, z. Shift lifts straight up. "
            "Enter or right-click finishes, Backspace undoes a point, "
            "C closes the loop, Esc cancels."))
        v.update()

    def _place_box(self):
        if self._box is not None:
            w = min(520, self.view.width() - 24)
            self._box.setGeometry(12, self.view.height() - 72, w, 28)

    def message(self, text, ms=0):
        try:
            self.window.statusBar().showMessage(text, ms)
        except Exception:                          # pragma: no cover
            pass

    def _end(self):
        v = self.view
        if v.edit_tool is self:
            v.edit_tool = None
        if self._box is not None:
            self._box.deleteLater()
            self._box = None
        v.setMouseTracking(False)
        v.unsetCursor()
        v.update()

    def cancel(self):
        from . import language
        self._end()
        self.message(language.tr("Curve cancelled."), 4000)

    def finish(self, closed=False):
        from . import language
        pts = self.points
        if len(pts) < 2 or (closed and len(pts) < 3):
            self.message(language.tr(
                "A curve needs at least two points (three for a loop) — "
                "keep clicking, or Esc to cancel."), 5000)
            return None
        self._end()
        return create_curve(self.window, pts, closed)

    # -- snapping -----------------------------------------------------
    def _ray(self, x, y):
        from .sculpt_ui import screen_ray
        origin, d = screen_ray(self.view, x, y)
        return tuple(origin), tuple(d)

    def _tol(self, p):
        eye, right, up, forward = self.view._camera()
        depth = self.view._project(eye, right, up, forward, p)[2]
        return SNAP_PX * max(depth, 1e-6) / self.view._focal()

    def _grid(self):
        scene = getattr(self.window, "scene", None)
        step = getattr(scene, "grid_size", None)
        try:
            step = float(step)
        except (TypeError, ValueError):
            step = 1.0
        return step if step > 0 else 1.0

    def snap_at(self, x, y, modifiers=0):
        from PyQt5.QtCore import Qt
        origin, d = self._ray(x, y)
        vertical = self.points[-1] if (
            modifiers & Qt.ShiftModifier and self.points) else None
        free = bool(modifiers & Qt.AltModifier)
        if self.points:
            self.elevation = self.points[-1][2]
        return self.snapper.snap(origin, d, self._tol, self.points,
                                 self.elevation, self._grid(), vertical,
                                 not free)

    # -- the view's hooks ---------------------------------------------
    def wants_key(self, event):
        from PyQt5.QtCore import Qt
        if event.modifiers() & (Qt.ControlModifier | Qt.MetaModifier):
            return False
        return event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Escape,
                               Qt.Key_Backspace, Qt.Key_C) or \
            bool(re.match(r"[-+@\d.]", event.text() or ""))

    def key_press(self, event):
        from PyQt5.QtCore import Qt
        from . import language
        key = event.key()
        if key == Qt.Key_Escape:
            self.cancel()
        elif key in (Qt.Key_Return, Qt.Key_Enter):
            self.finish()
        elif key == Qt.Key_Backspace:
            if self.points:
                self.points.pop()
                self.message(language.tr("Took the last point back."), 3000)
        elif key == Qt.Key_C:
            self.finish(closed=True)
        elif re.match(r"[-+@\d.]", event.text() or "") and self._box:
            # typing starts a coordinate, wherever the focus was
            self._box.setFocus()
            self._box.insert(event.text())
        else:
            return False
        self.view.update()
        return True

    def mouse_press(self, event):
        from PyQt5.QtCore import Qt
        if event.button() == Qt.RightButton:
            self.finish()
            return True
        if event.button() != Qt.LeftButton:
            return False
        if event.type() == event.MouseButtonDblClick and \
                len(self.points) >= 2:
            self._press = None
            self.finish()
            return True
        self._press = (event.pos(), event.modifiers())
        return False              # let the view start an orbit, in case

    def mouse_release(self, event):
        from PyQt5.QtCore import Qt
        press, self._press = self._press, None
        if press is None or event.button() != Qt.LeftButton:
            return False
        moved = (event.pos() - press[0]).manhattanLength()
        if moved > 4:
            return False                     # it was an orbit
        self.click(event.pos().x(), event.pos().y(), press[1])
        return True

    def mouse_move(self, event):
        if self._press is not None:
            return False                     # orbiting
        p, kind = self.snap_at(event.pos().x(), event.pos().y(),
                               event.modifiers())
        self.hover = (p, kind) if p is not None else None
        self.view.update()
        return False

    def wheel(self, event):
        return False

    def click(self, x, y, modifiers=0):
        from . import language
        p, kind = self.snap_at(x, y, modifiers)
        if p is None:
            self.message(language.tr(
                "Nothing there to put a point on — aim at the model or "
                "the ground, or type the point."), 4000)
            return
        if kind == "start":
            self.finish(closed=True)
            return
        self.add_point(p, kind)

    def add_point(self, p, kind=""):
        from . import language
        p = tuple(tidy(c) for c in p)
        if self.points and _len(_sub(p, self.points[-1])) < 1e-6:
            return
        self.points.append(p)
        label = language.tr(KINDS.get(kind, ("", ""))[0]) if kind else ""
        self.message(language.tr(
            "Point {n}: {x}, {y}, {z}{how}. Keep clicking — Enter "
            "finishes.").format(n=len(self.points), x=p[0], y=p[1], z=p[2],
                                how=f" ({label})" if label else ""))
        self.view.update()

    def _typed(self):
        from . import language
        box = self._box
        try:
            p = parse_coords(box.text(), self.points[-1] if self.points
                             else None, self.elevation)
        except ValueError as exc:
            self.message(language.tr(str(exc)), 6000)
            return
        box.clear()
        self.view.setFocus()
        self.add_point(p)

    # -- drawing ------------------------------------------------------
    def paint(self, painter, project):
        from PyQt5.QtCore import QPointF, Qt
        from PyQt5.QtGui import QColor, QPen, QFont
        from . import curve3d, language
        self._place_box()
        pts = list(self.points)
        live = self.hover[0] if self.hover else None
        path = pts + ([live] if live is not None else [])
        if len(path) >= 2:
            dense = curve3d.polyline(path, "smooth", False, 8)
            scr = [project(p) for p in dense]
            pen = QPen(QColor("#e8a33a"), 2.5)
            painter.setPen(pen)
            for a, b in zip(scr, scr[1:]):
                if a[2] > 0 and b[2] > 0:
                    painter.drawLine(QPointF(a[0], a[1]), QPointF(b[0], b[1]))
        painter.setPen(QPen(QColor("#202020"), 1))
        painter.setBrush(QColor("#ffffff"))
        for i, p in enumerate(pts):
            s = project(p)
            if s[2] > 0:
                painter.drawEllipse(QPointF(s[0], s[1]), 4.5, 4.5)
        painter.setBrush(Qt.NoBrush)
        if self.hover:
            p, kind = self.hover
            s = project(p)
            if s[2] <= 0:
                return
            label, colour = KINDS.get(kind, ("", "#888"))
            col = QColor(colour)
            painter.setPen(QPen(col, 2))
            painter.setBrush(col.lighter(170))
            painter.drawRect(int(s[0]) - 5, int(s[1]) - 5, 10, 10)
            painter.setBrush(Qt.NoBrush)
            font = QFont(painter.font())
            font.setBold(True)
            painter.setFont(font)
            text = "{}   {}, {}, {}".format(
                language.tr(label), *(f"{tidy(c, 2):g}" for c in p))
            metrics = painter.fontMetrics()
            w = metrics.horizontalAdvance(text) + 12
            x, y = int(s[0]) + 12, int(s[1]) + 10
            painter.fillRect(x, y, w, metrics.height() + 6,
                             QColor(255, 255, 255, 225))
            painter.setPen(QPen(col.darker(140)))
            painter.drawText(x + 6, y + metrics.ascent() + 3, text)


def create_curve(window, points, closed=False):
    """The `curve` node from *points*, where new geometry goes: inside
    the Object being edited, else as a new Object in Main."""
    from . import language
    model = window.model
    parent = window.builder.isolated_component() if hasattr(
        window, "builder") else None
    node = model.add_node("curve", dict(
        points=[[tidy(c) for c in p] for p in points], closed=bool(closed),
        style="smooth", thickness=2.0, smooth=8), parent=parent)
    if parent is None and hasattr(window, "_geometry_created_in_main"):
        window._geometry_created_in_main(node)
    elif hasattr(window, "builder"):
        window.builder.object_tab.tree.select_nodes([node])
    window.statusBar().showMessage(language.tr(
        "Curve made through {n} points. Its points, smoothness and wire "
        "thickness are in Properties; right-click it ▸ Make a Sweep Along "
        "This Curve to give it a profile.").format(n=len(points)), 12000)
    return node

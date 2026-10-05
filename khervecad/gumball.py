"""The Gumball — Rhino's move / turn handles on the selected part, in the
3D view (View ▸ Gumball, Ctrl+Alt+G, or the button on the 3D bar).

Three arrows (X red, Y green, Z blue) and three rings round the
selected part's centre:

* **drag an arrow** to slide the part along that axis;
* **drag a ring** to turn the part about that axis, round its centre;
* hold **Ctrl** to snap — moves to the sketch grid, turns to 15°;
* a readout beside the cursor says how far, while you drag.

Anything else — a drag on the model or on empty space, the wheel — turns
and zooms the view as always, so the Gumball can stay on while you work.
Each drag is one undo step. What moves is the part's own placement (an
Object, an instance or a group; a bare shape is wrapped in a group
first), written through `physics.placement`, so a part inside a turned
assembly still slides along the WORLD axis you dragged.

The geometry — `axis_hit`, `ring_points`, `snap` — needs no Qt.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

#: the handles' length on screen, pixels
SIZE_PX = 90
#: how close a press must be to a handle, pixels
HIT_PX = 9
AXES = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
COLOURS = ("#e53935", "#43a047", "#1e88e5")
MOVABLE = ("union", "component", "reference")


def _seg_dist(p, a, b):
    ax, ay = b[0] - a[0], b[1] - a[1]
    d = ax * ax + ay * ay
    t = 0.0 if d < 1e-12 else max(0.0, min(1.0, ((p[0] - a[0]) * ax
                                                 + (p[1] - a[1]) * ay) / d))
    return math.hypot(p[0] - a[0] - ax * t, p[1] - a[1] - ay * t)


def ring_points(centre, axis, radius, n=48):
    """World points of the ring about *axis* through *centre*."""
    a = AXES[axis]
    u = AXES[(axis + 1) % 3]
    v = AXES[(axis + 2) % 3]
    out = []
    for i in range(n + 1):
        t = 2 * math.pi * i / n
        c, s = math.cos(t) * radius, math.sin(t) * radius
        out.append(tuple(centre[k] + c * u[k] + s * v[k] for k in range(3)))
    del a
    return out


def handle_at(x, y, centre_s, tips_s, rings_s):
    """("move" | "turn", axis) of the handle under screen (x, y), or
    None. Arrows win over rings where they cross."""
    best = None
    for axis, tip in enumerate(tips_s):
        d = _seg_dist((x, y), centre_s, tip)
        if d <= HIT_PX and (best is None or d < best[0]):
            best = (d, ("move", axis))
    if best:
        return best[1]
    for axis, pts in enumerate(rings_s):
        for a, b in zip(pts, pts[1:]):
            d = _seg_dist((x, y), a, b)
            if d <= HIT_PX and (best is None or d < best[0]):
                best = (d, ("turn", axis))
    return best[1] if best else None


def snap(value, step):
    return round(value / step) * step if step > 0 else value


def rotation(axis, degrees):
    a = math.radians(degrees)
    c, s = math.cos(a), math.sin(a)
    if axis == 0:
        return [[1, 0, 0], [0, c, -s], [0, s, c]]
    if axis == 1:
        return [[c, 0, s], [0, 1, 0], [-s, 0, c]]
    return [[c, -s, 0], [s, c, 0], [0, 0, 1]]


# =================================================================== Qt

def toggle(window, on=None):
    """View ▸ Gumball: switch it on or off (None flips)."""
    from . import language
    view = window.view3d
    current = isinstance(view.edit_tool, Gumball)
    on = (not current) if on is None else bool(on)
    if on and not current:
        if view.edit_tool is not None:
            window.statusBar().showMessage(language.tr(
                "Finish what the 3D view is doing first (Esc), then "
                "switch the Gumball on."), 6000)
            _sync(window, False)
            return False
        view.edit_tool = Gumball(window)
        view.setMouseTracking(True)
        window.statusBar().showMessage(language.tr(
            "Gumball on: select a part, then drag an arrow to slide it "
            "or a ring to turn it (Ctrl snaps). Dragging anywhere else "
            "still turns the view."), 10000)
    elif not on and current:
        view.edit_tool = None
        view.setMouseTracking(False)
        window.statusBar().showMessage(language.tr("Gumball off."), 3000)
    _sync(window, on)
    view.update()
    return on


def _sync(window, on):
    act = getattr(window, "_gumball_act", None)
    if act is not None and act.isChecked() != on:
        act.blockSignals(True)
        act.setChecked(on)
        act.blockSignals(False)


class Gumball:
    """View3D.edit_tool for the handles; declines everything that is not
    a press on a handle, so the view orbits as usual."""

    def __init__(self, window):
        self.window = window
        self.view = window.view3d
        self.drag = None             # the running drag
        self.hover = None            # handle under the mouse

    # -- what is selected ----------------------------------------------
    def target(self):
        tree = self.window.builder.active_tree()
        nodes = tree.selected_nodes()
        if len(nodes) != 1:
            return None
        node = nodes[0]
        probe = node
        while probe is not None and probe.parent is not None:
            if probe.type in MOVABLE:
                return probe
            probe = probe.parent
        return node if node.parent is not None else None

    def centre(self):
        tris = self.view.highlight_mesh or []
        pts = [v for t in tris for v in t]
        if not pts:
            return None
        lo = [min(p[k] for p in pts) for k in range(3)]
        hi = [max(p[k] for p in pts) for k in range(3)]
        return tuple((lo[k] + hi[k]) / 2 for k in range(3))

    def _project(self):
        v = self.view
        eye, right, up, forward = v._camera()
        return lambda p: v._project(eye, right, up, forward, p)

    def _length(self, centre, project):
        depth = project(centre)[2]
        return SIZE_PX * max(depth, 1e-6) / self.view._focal()

    def _screen(self):
        c = self.centre()
        if c is None or self.target() is None:
            return None
        project = self._project()
        length = self._length(c, project)
        cs = project(c)
        tips = [project(tuple(c[k] + AXES[a][k] * length for k in range(3)))
                for a in range(3)]
        rings = [[project(p) for p in ring_points(c, a, length * 0.75)]
                 for a in range(3)]
        return c, length, cs, tips, rings

    # -- the view's hooks ------------------------------------------------
    def wants_key(self, event):
        from PyQt5.QtCore import Qt
        return event.key() == Qt.Key_Escape and self.drag is not None

    def key_press(self, event):
        from PyQt5.QtCore import Qt
        if event.key() == Qt.Key_Escape and self.drag is not None:
            self._restore(self.drag)
            self.drag = None
            self.view.update()
            return True
        return False

    def mouse_press(self, event):
        from PyQt5.QtCore import Qt
        if event.button() != Qt.LeftButton:
            return False
        scr = self._screen()
        if scr is None:
            return False
        c, length, cs, tips, rings = scr
        handle = handle_at(event.pos().x(), event.pos().y(), cs[:2],
                           [t[:2] for t in tips],
                           [[p[:2] for p in r] for r in rings])
        if handle is None:
            return False
        from . import mates
        node = mates.ensure_part(self.window.model, self.target())
        start = {k: node.params.get(k, 0.0)
                 for k in ("x", "y", "z", "rx", "ry", "rz")}
        self.drag = dict(handle=handle, node=node, start=start, centre=c,
                         length=length, cs=cs[:2],
                         tip=tips[handle[1]][:2],
                         press=(event.pos().x(), event.pos().y()),
                         value=0.0)
        return True

    def mouse_move(self, event):
        from PyQt5.QtCore import Qt
        x, y = event.pos().x(), event.pos().y()
        d = self.drag
        if d is None:
            scr = self._screen()
            hover = None
            if scr is not None:
                _c, _l, cs, tips, rings = scr
                hover = handle_at(x, y, cs[:2], [t[:2] for t in tips],
                                  [[p[:2] for p in r] for r in rings])
            if hover != self.hover:
                self.hover = hover
                self.view.update()
            return False
        kind, axis = d["handle"]
        ctrl = bool(event.modifiers() & Qt.ControlModifier)
        if kind == "move":
            sx, sy = d["tip"][0] - d["cs"][0], d["tip"][1] - d["cs"][1]
            px = math.hypot(sx, sy) or 1.0
            along = ((x - d["press"][0]) * sx + (y - d["press"][1]) * sy) \
                / px
            value = along / px * d["length"]
            if ctrl:
                value = snap(value, self._grid())
        else:
            cx, cy = d["cs"]
            a0 = math.atan2(d["press"][1] - cy, d["press"][0] - cx)
            a1 = math.atan2(y - cy, x - cx)
            value = -math.degrees(math.atan2(math.sin(a1 - a0),
                                             math.cos(a1 - a0)))
            if self._axis_towards_eye(axis):
                value = -value
            if ctrl:
                value = snap(value, 15.0)
        d["value"] = value
        self._apply(d)
        return True

    def mouse_release(self, event):
        d, self.drag = self.drag, None
        if d is None:
            return False
        from . import language
        kind, axis = d["handle"]
        name = "XYZ"[axis]
        self.window.statusBar().showMessage(language.tr(
            "Moved {name} by {value:g}").format(
            name=name, value=round(d["value"], 3)) if kind == "move" else
            language.tr("Turned about {name} by {value:g}°").format(
                name=name, value=round(d["value"], 2)), 5000)
        self.view.update()
        return True

    def wheel(self, event):
        return False

    # -- applying ----------------------------------------------------
    def _grid(self):
        scene = getattr(self.window, "scene", None)
        try:
            return float(getattr(scene, "grid_size", 1.0)) or 1.0
        except (TypeError, ValueError):
            return 1.0

    def _axis_towards_eye(self, axis):
        _eye, _r, _u, forward = self.view._camera()
        return AXES[axis][0] * -forward[0] + AXES[axis][1] * -forward[1] \
            + AXES[axis][2] * -forward[2] > 0

    def _restore(self, d):
        model = self.window.model
        for k, v in d["start"].items():
            if d["node"].params.get(k, 0.0) != v:
                model.set_param(d["node"], k, v)

    def _apply(self, d):
        from . import physics
        node = d["node"]
        node.params.update(d["start"])     # measure from where it began
        kind, axis = d["handle"]
        if kind == "move":
            move = dict(rotation=[[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                        centre=[0.0, 0.0, 0.0],
                        move=[AXES[axis][k] * d["value"] for k in range(3)])
        else:
            move = dict(rotation=rotation(axis, d["value"]),
                        centre=list(d["centre"]), move=[0.0, 0.0, 0.0])
        x, y, z, rx, ry, rz = physics.placement(node, move)
        model = self.window.model
        values = dict(x=x, y=y, z=z, rx=rx, ry=ry, rz=rz)
        # one change, one redraw: set_param on the first key releases a
        # mate (the user has taken the part), the rest ride along
        first = True
        for key, value in values.items():
            value = round(value, 4) + 0.0
            if first:
                node.params.update({k: round(v, 4) + 0.0
                                    for k, v in values.items()})
                model.set_param(node, key, value)
                first = False

    # -- drawing -----------------------------------------------------
    def paint(self, painter, project):
        from PyQt5.QtCore import QPointF, Qt
        from PyQt5.QtGui import QColor, QPen, QPolygonF, QFont
        scr = self._screen()
        if scr is None:
            return
        c, length, cs, tips, rings = scr
        if cs[2] <= 0:
            return
        live = self.drag["handle"] if self.drag else self.hover
        painter.setRenderHint(painter.Antialiasing, True)
        for axis in range(3):
            col = QColor(COLOURS[axis])
            hot = live == ("turn", axis)
            pen = QPen(col.lighter(130) if hot else col, 3.5 if hot else 2)
            painter.setPen(pen)
            pts = [QPointF(p[0], p[1]) for p in rings[axis] if p[2] > 0]
            if len(pts) > 1:
                painter.drawPolyline(QPolygonF(pts))
        for axis in range(3):
            col = QColor(COLOURS[axis])
            hot = live == ("move", axis)
            tip = tips[axis]
            painter.setPen(QPen(col.lighter(130) if hot else col,
                                4.5 if hot else 3))
            painter.drawLine(QPointF(cs[0], cs[1]), QPointF(tip[0], tip[1]))
            dx, dy = tip[0] - cs[0], tip[1] - cs[1]
            ln = math.hypot(dx, dy) or 1.0
            ux, uy = dx / ln, dy / ln
            head = QPolygonF([
                QPointF(tip[0] + ux * 12, tip[1] + uy * 12),
                QPointF(tip[0] - uy * 6, tip[1] + ux * 6),
                QPointF(tip[0] + uy * 6, tip[1] - ux * 6)])
            painter.setBrush(col)
            painter.drawPolygon(head)
            painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor("#ffffff"), 1.5))
        painter.setBrush(QColor(40, 40, 40, 200))
        painter.drawEllipse(QPointF(cs[0], cs[1]), 5, 5)
        painter.setBrush(Qt.NoBrush)
        if self.drag:
            kind, axis = self.drag["handle"]
            text = (f"{'XYZ'[axis]}  {self.drag['value']:+.2f}" if
                    kind == "move" else
                    f"{'XYZ'[axis]}  {self.drag['value']:+.1f}°")
            font = QFont(painter.font())
            font.setBold(True)
            painter.setFont(font)
            m = painter.fontMetrics()
            w = m.horizontalAdvance(text) + 12
            painter.fillRect(int(cs[0]) + 14, int(cs[1]) - 30, w,
                             m.height() + 6, QColor(255, 255, 255, 225))
            painter.setPen(QColor(COLOURS[axis]).darker(130))
            painter.drawText(int(cs[0]) + 20, int(cs[1]) - 27 + m.ascent(),
                             text)

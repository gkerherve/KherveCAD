"""Extrude and revolve by DRAGGING in the 3D view (2026-10-21, the user:
"in SolidWorks / Fusion there is an arrow that comes up and we push it up
with the mouse ... and the rotational extrusion too").

After Linear extrude or Rotate extrude (or with one selected and Extrude
▸ Drag selected), the 3D view shows a handle on it:

* a **Linear extrude** gets an arrow on its top face, along its own +Z:
  drag it to pull the solid out — the height follows live;
* a **Rotate extrude** gets a curved arrow at the end of its sweep: drag
  it round to set the angle (up to 360°).

A readout beside the handle gives the height / angle; Ctrl snaps to the
sketch grid / 15°; Esc while dragging puts it back; a press anywhere else
turns the view as always, Esc (idle) or the Select button ends the tool.
It edits the node's own `height` / `angle`, so the program, undo and
every other view stay as they are. The geometry helpers are Qt-free.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

from .gumball import HIT_PX, _seg_dist, snap

KINDS = ("linear_extrude", "rotate_extrude")
SIZE_PX = 70
COLOUR = "#1e88e5"
MIN_HEIGHT = 0.01


def _num(v, default):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _apply(m, p):
    return tuple(sum(m[r][c] * p[c] for c in range(3)) + m[r][3]
                 for r in range(3))


def _apply_dir(m, d):
    return tuple(sum(m[r][c] * d[c] for c in range(3)) for r in range(3))


def frame(node, scope=None):
    """(matrix to the scope's frame, local tris of the node's content)."""
    from . import mesh
    m = mesh.ancestor_matrix(node, stop=scope)
    try:
        tris = mesh.tessellate(node)
    except Exception:
        tris = []
    return m, tris


def linear_handle(node, m, tris):
    """(base, axis, scale) in scope coordinates: base = the top face's
    centre, axis = the extrusion direction (unit), scale = scope mm per
    local mm along it."""
    pts = [p for t in tris for p in t]
    if not pts:
        return None
    cx = (min(p[0] for p in pts) + max(p[0] for p in pts)) / 2
    cy = (min(p[1] for p in pts) + max(p[1] for p in pts)) / 2
    top = max(p[2] for p in pts)
    base = _apply(m, (cx, cy, top))
    d = _apply_dir(m, (0.0, 0.0, 1.0))
    s = math.sqrt(sum(c * c for c in d)) or 1.0
    return base, tuple(c / s for c in d), s


def revolve_handle(node, m, tris):
    """(point, tangent, radius) at the END of the sweep, in scope
    coordinates; tangent = d point / d angle (per radian)."""
    pts = [p for t in tris for p in t]
    if not pts:
        return None
    r = max(math.hypot(p[0], p[1]) for p in pts)
    z = (min(p[2] for p in pts) + max(p[2] for p in pts)) / 2
    a = math.radians(_num(node.params.get("angle", 360.0), 360.0))
    p = _apply(m, (r * math.cos(a), r * math.sin(a), z))
    t = _apply_dir(m, (-r * math.sin(a), r * math.cos(a), 0.0))
    return p, t, r


# =================================================================== Qt

def start(window, node=None, quiet=False):
    """Switch the drag handles on (for *node*, else the selection)."""
    from . import language
    view = window.view3d
    if view.edit_tool is not None and not isinstance(view.edit_tool,
                                                     DragFeature):
        if not quiet:
            window.statusBar().showMessage(language.tr(
                "Finish what the 3D view is doing first (Esc)."), 5000)
        return None
    tool = DragFeature(window, node)
    if tool.target() is None:
        if not quiet:
            window.statusBar().showMessage(language.tr(
                "Select a Linear extrude or Rotate extrude (or the shape "
                "inside one) to drag it."), 6000)
        return None
    view.edit_tool = tool
    view.setMouseTracking(True)
    view.update()
    window.statusBar().showMessage(language.tr(
        "Drag the blue arrow to set the height (Ctrl snaps) — Esc or "
        "Select finishes."), 8000)
    return tool


def action(window):
    act = getattr(window, "_drag_feature_act", None)
    if act is not None:
        return act
    from PyQt5.QtWidgets import QAction
    from . import icons, language, toolbars, tooltips
    tooltips.TIPS.setdefault("drag_extrude", (
        "Drag extrude / revolve",
        "Shows an arrow on the selected Linear extrude (or a curved arrow "
        "on a Rotate extrude) in the 3D view — drag it to set the height "
        "or the angle, as in SolidWorks and Fusion.",
        ["Select an extrude, or the shape inside it.",
         "Click this, then drag the blue arrow in the 3D view.",
         "Ctrl snaps; Esc finishes."],
        "Linear extrude and Rotate extrude show the arrow by themselves."))
    act = QAction(icons.icon("mdi.arrow-expand-up"),
                  language.tr("Drag extrude"), window)
    act.setData("drag_extrude")
    toolbars.remember_glyph(act, "mdi.arrow-expand-up", "extrude")
    tooltips.apply(act, "drag_extrude")
    act.triggered.connect(lambda _=False: start(window))
    window._drag_feature_act = act
    return act


class DragFeature:
    """View3D.edit_tool: the extrude arrow / revolve arc."""

    def __init__(self, window, node=None):
        self.window = window
        self.view = window.view3d
        self.fixed = node
        self.drag = None
        self.hover = False

    def target(self):
        node = self.fixed
        if node is None or node.parent is None:
            nodes = self.window.builder.active_tree().selected_nodes()
            node = nodes[0] if len(nodes) == 1 else None
            self.fixed = None
        probe = node
        while probe is not None and probe.type not in KINDS:
            probe = probe.parent
        return probe

    def _scope(self):
        scope = self.window._render_scope()[0]
        return None if scope is None or scope is self.window.model.root \
            else scope

    def _project(self):
        v = self.view
        eye, right, up, forward = v._camera()
        return lambda p: v._project(eye, right, up, forward, p)

    def _screen(self):
        node = self.target()
        if node is None:
            return None
        m, tris = frame(node, self._scope())
        project = self._project()
        if node.type == "linear_extrude":
            got = linear_handle(node, m, tris)
            if got is None:
                return None
            base, axis, scale = got
            bs = project(base)
            length = SIZE_PX * max(bs[2], 1e-6) / self.view._focal()
            tip = project(tuple(base[k] + axis[k] * length
                                for k in range(3)))
            return dict(node=node, kind="linear", a=bs, b=tip,
                        length=length, scale=scale)
        got = revolve_handle(node, m, tris)
        if got is None:
            return None
        p, t, _r = got
        ps = project(p)
        # the screen tangent per radian, measured over a small step
        step = 0.05
        qs = project(tuple(p[k] + t[k] * step for k in range(3)))
        per = ((qs[0] - ps[0]) / step, (qs[1] - ps[1]) / step)
        norm = math.hypot(*per) or 1.0
        tip = (ps[0] + per[0] / norm * 40, ps[1] + per[1] / norm * 40,
               ps[2])
        return dict(node=node, kind="revolve", a=ps, b=tip, per=per)

    def _hit(self, x, y, scr):
        return _seg_dist((x, y), scr["a"][:2], scr["b"][:2]) <= HIT_PX + 3

    # -- the view's hooks ------------------------------------------------
    def wants_key(self, event):
        from PyQt5.QtCore import Qt
        return event.key() == Qt.Key_Escape

    def key_press(self, event):
        from PyQt5.QtCore import Qt
        if event.key() != Qt.Key_Escape:
            return False
        if self.drag is not None:
            self._set(self.drag["node"], self.drag["param"],
                      self.drag["start"])
            self.drag = None
        else:
            self.exit()
        self.view.update()
        return True

    def exit(self):
        if self.view.edit_tool is self:
            self.view.edit_tool = None
            self.view.setMouseTracking(False)
            self.view.update()

    def mouse_press(self, event):
        from PyQt5.QtCore import Qt
        if event.button() != Qt.LeftButton:
            return False
        scr = self._screen()
        if scr is None or not self._hit(event.pos().x(), event.pos().y(),
                                        scr):
            return False
        node = scr["node"]
        param = "height" if scr["kind"] == "linear" else "angle"
        start = _num(node.params.get(param, 10.0 if param == "height"
                                     else 360.0),
                     10.0 if param == "height" else 360.0)
        self.drag = dict(scr, param=param, start=start,
                         press=(event.pos().x(), event.pos().y()),
                         value=start)
        return True

    def mouse_move(self, event):
        from PyQt5.QtCore import Qt
        x, y = event.pos().x(), event.pos().y()
        d = self.drag
        if d is None:
            scr = self._screen()
            hover = bool(scr and self._hit(x, y, scr))
            if hover != self.hover:
                self.hover = hover
                self.view.update()
            return False
        ctrl = bool(event.modifiers() & Qt.ControlModifier)
        dx, dy = x - d["press"][0], y - d["press"][1]
        if d["kind"] == "linear":
            sx, sy = d["b"][0] - d["a"][0], d["b"][1] - d["a"][1]
            px = math.hypot(sx, sy) or 1.0
            world = (dx * sx + dy * sy) / px / px * d["length"]
            delta = world / d["scale"]
            if d["node"].params.get("center"):
                delta *= 2.0                # both ends move
            value = d["start"] + delta
            if ctrl:
                value = snap(value, self._grid())
            value = max(MIN_HEIGHT, value)
        else:
            per = d["per"]
            n2 = per[0] * per[0] + per[1] * per[1] or 1.0
            value = d["start"] + math.degrees((dx * per[0] + dy * per[1])
                                              / n2)
            if ctrl:
                value = snap(value, 15.0)
            value = max(1.0, min(360.0, value))
        d["value"] = round(value, 4)
        self._set(d["node"], d["param"], d["value"])
        return True

    def mouse_release(self, event):
        d, self.drag = self.drag, None
        if d is None:
            return False
        from . import language
        self.window.statusBar().showMessage(
            language.tr("Height {v:g} mm").format(v=d["value"])
            if d["param"] == "height" else
            language.tr("Angle {v:g}°").format(v=d["value"]), 5000)
        self.view.update()
        return True

    def wheel(self, event):
        return False

    def _grid(self):
        scene = getattr(self.window, "scene", None)
        try:
            return float(getattr(scene, "grid_size", 1.0)) or 1.0
        except (TypeError, ValueError):
            return 1.0

    def _set(self, node, param, value):
        self.window.model.set_param(node, param, value)

    # -- drawing -----------------------------------------------------
    def paint(self, painter, project):
        from PyQt5.QtCore import QPointF, Qt
        from PyQt5.QtGui import QColor, QFont, QPen, QPolygonF
        scr = self._screen()
        if scr is None or scr["a"][2] <= 0:
            return
        hot = self.hover or self.drag is not None
        col = QColor(COLOUR)
        painter.setRenderHint(painter.Antialiasing, True)
        a, b = scr["a"], scr["b"]
        painter.setPen(QPen(col.lighter(125) if hot else col,
                            4.5 if hot else 3))
        if scr["kind"] == "revolve":
            # a short arc ahead of the sweep's end
            per = scr["per"]
            n = math.hypot(*per) or 1.0
            ux, uy = per[0] / n, per[1] / n
            pts = [QPointF(a[0] + ux * 40 * f - uy * 6 * f * f,
                           a[1] + uy * 40 * f + ux * 6 * f * f)
                   for f in [i / 8 for i in range(9)]]
            painter.drawPolyline(QPolygonF(pts))
            tip, back = pts[-1], pts[-2]
        else:
            painter.drawLine(QPointF(a[0], a[1]), QPointF(b[0], b[1]))
            tip, back = QPointF(b[0], b[1]), QPointF(a[0], a[1])
        dx, dy = tip.x() - back.x(), tip.y() - back.y()
        ln = math.hypot(dx, dy) or 1.0
        ux, uy = dx / ln, dy / ln
        painter.setBrush(col)
        painter.drawPolygon(QPolygonF([
            QPointF(tip.x() + ux * 13, tip.y() + uy * 13),
            QPointF(tip.x() - uy * 7, tip.y() + ux * 7),
            QPointF(tip.x() + uy * 7, tip.y() - ux * 7)]))
        painter.setPen(QPen(QColor("#ffffff"), 1.5))
        painter.drawEllipse(QPointF(a[0], a[1]), 5, 5)
        painter.setBrush(Qt.NoBrush)
        node = scr["node"]
        if scr["kind"] == "linear":
            text = "%g mm" % round(_num(node.params.get("height"), 0), 3)
        else:
            text = "%g°" % round(_num(node.params.get("angle", 360), 360),
                                 2)
        font = QFont(painter.font())
        font.setBold(True)
        painter.setFont(font)
        fm = painter.fontMetrics()
        w = fm.horizontalAdvance(text) + 12
        x0, y0 = int(b[0]) + 16, int(b[1]) - 12
        painter.fillRect(x0, y0, w, fm.height() + 6,
                         QColor(255, 255, 255, 230))
        painter.setPen(col.darker(140))
        painter.drawText(x0 + 6, y0 + 3 + fm.ascent(), text)

"""Hand painting on the 3D view — Blender's Vertex Paint: a small panel
(colour, radius, strength, hardness, dabs or lines) puts a brush on the
view (View3D.edit_tool) over a vertex_paint node's part. A drag lays
dabs along the mouse — or, with Lines, one stroke between consecutive
points (stripes, war paint, a scar). The whole drag lands on release as
one set_param (one Ctrl+Z), in the part's own frame. A press off the
model still orbits; [ and ] size the brush.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtGui import QColor, QPen
from PyQt5.QtWidgets import (QCheckBox, QColorDialog, QDialog,
                             QDoubleSpinBox, QFormLayout, QHBoxLayout,
                             QLabel, QPushButton, QVBoxLayout)

from . import language, mesh
from .sculpt_ui import ray_hit, screen_ray

SPACING = 0.35


def world_tris(window, node):
    root = window._render_scope()[0]
    iso = root if root is not window.model.root else None
    with window._isolated_frame(iso):
        return mesh.selected_world_tris(root, {node.id},
                                        fn=window.model.effective_fn())


def paint_rows(window, node, specs):
    """Stroke rows in *node*'s frame from world specs (point, end, radius,
    rgb, strength, hardness)."""
    from .creature_mcp import _scope, to_local
    stop = _scope(window)
    rows = []
    for point, end, radius, rgb, strength, hardness in specs:
        p = to_local(node, [point], stop)[0]
        row = p + [round(float(radius), 3)] + [int(c) for c in rgb] + [
            round(float(strength), 3), round(float(hardness), 3)]
        if end is not None:
            row += to_local(node, [end], stop)[0]
        rows.append(row)
    return rows


class PaintTool:
    """The brush on the 3D view."""

    def __init__(self, panel):
        self.panel = panel
        self.view = panel.window_.view3d
        self._array = None
        self._stroke = None
        self._hover = None

    def reload(self, world):
        import numpy as np
        self._array = np.asarray(world, dtype=float) if world else None

    def hit(self, x, y):
        origin, d = screen_ray(self.view, x, y)
        return ray_hit(self._array, origin, d)

    def wants_key(self, event):
        if event.modifiers() & (Qt.ControlModifier | Qt.MetaModifier):
            return False
        return event.key() in (Qt.Key_BracketLeft, Qt.Key_BracketRight)

    def key_press(self, event):
        if event.key() == Qt.Key_BracketLeft:
            self.panel.radius.setValue(self.panel.radius.value() / 1.2)
        elif event.key() == Qt.Key_BracketRight:
            self.panel.radius.setValue(self.panel.radius.value() * 1.2)
        else:
            return False
        self.view.update()
        return True

    def mouse_press(self, event):
        if event.button() != Qt.LeftButton:
            return False
        point, _n = self.hit(event.pos().x(), event.pos().y())
        if point is None:
            return False
        self._stroke = [point]
        self.view.update()
        return True

    def mouse_move(self, event):
        point, normal = self.hit(event.pos().x(), event.pos().y())
        self._hover = (point, normal) if point is not None else None
        if self._stroke is None:
            self.view.update()
            return False
        if point is not None and math.dist(point, self._stroke[-1]) >= \
                SPACING * self.panel.radius.value():
            self._stroke.append(point)
        self.view.update()
        return True

    def mouse_release(self, event):
        pts, self._stroke = self._stroke, None
        if pts is None:
            return False
        self.panel.commit(pts)
        self.view.update()
        return True

    def wheel(self, event):
        return False

    def paint(self, painter, project):
        pen = QPen(QColor(self.panel.colour))
        pen.setWidthF(1.5)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        if self._hover is not None:
            point, normal = self._hover
            c = project(point)
            side = [0.0, 0.0, 1.0] if abs(normal[2]) < 0.9 else [1.0, 0, 0]
            t = [normal[1] * side[2] - normal[2] * side[1],
                 normal[2] * side[0] - normal[0] * side[2],
                 normal[0] * side[1] - normal[1] * side[0]]
            n = math.sqrt(sum(v * v for v in t)) or 1.0
            r = self.panel.radius.value()
            edge = project([point[k] + t[k] / n * r for k in range(3)])
            if c is not None and edge is not None:
                rad = math.hypot(edge[0] - c[0], edge[1] - c[1])
                painter.drawEllipse(QPointF(c[0], c[1]), rad, rad)
        if self._stroke:
            pts = [project(p) for p in self._stroke]
            pts = [p for p in pts if p is not None]
            for a, b in zip(pts, pts[1:]):
                painter.drawLine(QPointF(a[0], a[1]), QPointF(b[0], b[1]))

    def close(self):
        if self.view.edit_tool is self:
            self.view.edit_tool = None
        self.view.update()


class PaintPanel(QDialog):
    def __init__(self, window, node):
        super().__init__(window)
        tr = language.tr
        self.setWindowTitle(tr("Paint — {name}").format(name=node.name))
        self.setWindowFlag(Qt.Tool, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.window_, self.node = window, node
        self.colour = "#b01818"
        self.swatch = QPushButton()
        self.swatch.clicked.connect(self.pick_colour)
        self._show_colour()
        self.radius = QDoubleSpinBox()
        self.radius.setRange(0.05, 10000.0)
        self.radius.setValue(4.0)
        self.radius.setSuffix(" mm")
        self.strength = QDoubleSpinBox()
        self.strength.setRange(0.0, 1.0)
        self.strength.setSingleStep(0.1)
        self.strength.setValue(1.0)
        self.hardness = QDoubleSpinBox()
        self.hardness.setRange(0.0, 1.0)
        self.hardness.setSingleStep(0.1)
        self.hardness.setValue(0.5)
        self.lines = QCheckBox(tr("Lines (a stripe along the drag)"))
        form = QFormLayout()
        form.addRow(tr("Colour"), self.swatch)
        form.addRow(tr("Radius"), self.radius)
        form.addRow(tr("Strength"), self.strength)
        form.addRow(tr("Hardness"), self.hardness)
        form.addRow(self.lines)
        self.count = QLabel()
        undo = QPushButton(tr("Undo last stroke"))
        undo.clicked.connect(self.undo_last)
        done = QPushButton(tr("Done"))
        done.clicked.connect(self.close)
        row = QHBoxLayout()
        row.addWidget(undo)
        row.addStretch(1)
        row.addWidget(done)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(QLabel(tr("Drag over the part to paint; [ and ] "
                                "change the size; a press off the model "
                                "still orbits.")))
        lay.addWidget(self.count)
        lay.addLayout(row)
        self.tool = PaintTool(self)
        self._last = 0
        self._refresh()
        self.arm()

    def _show_colour(self):
        self.swatch.setStyleSheet(f"background: {self.colour}; "
                                  "min-height: 18px;")

    def pick_colour(self):
        c = QColorDialog.getColor(QColor(self.colour), self)
        if c.isValid():
            self.colour = c.name()
            self._show_colour()

    def arm(self):
        world = world_tris(self.window_, self.node)
        view = self.window_.view3d
        self.tool.reload(world)
        view.edit_tool = self.tool
        view.setMouseTracking(True)
        view.setFocus(Qt.OtherFocusReason)

    def commit(self, pts):
        q = QColor(self.colour)
        rgb = (q.red(), q.green(), q.blue())
        args = (self.radius.value(), rgb, self.strength.value(),
                self.hardness.value())
        if self.lines.isChecked() and len(pts) > 1:
            specs = [(a, b) + args for a, b in zip(pts, pts[1:])]
        else:
            specs = [(p, None) + args for p in pts]
        rows = paint_rows(self.window_, self.node, specs)
        old = [list(r) for r in (self.node.params.get("strokes") or [])]
        self._last = len(rows)
        self.window_.model.set_param(self.node, "strokes", old + rows)
        self._refresh()
        self.arm()

    def undo_last(self):
        rows = [list(r) for r in (self.node.params.get("strokes") or [])]
        if rows:
            self.window_.model.set_param(
                self.node, "strokes", rows[:-max(self._last, 1)])
            self._last = 1
        self._refresh()
        self.arm()

    def _refresh(self):
        self.count.setText(language.tr("{count} stroke(s)").format(
            count=len(self.node.params.get("strokes") or [])))

    def closeEvent(self, event):
        self.tool.close()
        super().closeEvent(event)


def start(window, node):
    """Open the paint panel for *node* (a vertex_paint)."""
    old = getattr(window, "_paint_panel", None)
    if old is not None:
        try:
            old.close()
        except RuntimeError:
            pass
    panel = PaintPanel(window, node)
    panel.show()
    window._paint_panel = panel
    return panel

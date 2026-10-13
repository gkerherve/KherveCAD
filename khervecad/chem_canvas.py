"""The Chemistry Builder's drawing: a `chem_scene.Scene` seen from any
side, where atoms are clicked to measure, add, bond, move and delete.

Orthographic and painted with QPainter (shaded balls far to near, bonds
in their atoms' two colours, the cell box dashed), so it works anywhere
the app does. The view is a plan (Top / Front / Side, the "2D" the user
asked for) or turned freely with the left mouse in the Rotate tool;
wheel zooms, middle mouse pans. Measurements stay on the drawing — a
distance on the line between its atoms, an angle at its vertex with an
arc, a torsion beside its middle bond — until cleared.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

from PyQt5.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import (QBrush, QColor, QFont, QPainter, QPainterPath,
                         QPen, QRadialGradient)
from PyQt5.QtWidgets import QWidget

from . import chem_scene as cs
from . import crystal as cr

#: (yaw, pitch) degrees of the named views
VIEWS = {"Top": (0.0, 90.0), "Front": (0.0, 0.0), "Side": (90.0, 0.0),
         "3D": (-35.0, 25.0)}
TOOLS = ("rotate", "select", "measure", "add", "bond", "move", "delete")
#: ball radius on screen: this × covalent radius
BALL = 0.42
PICK_PX = 6


class ChemCanvas(QWidget):
    """Draws a Scene and turns clicks into edits. Signals: `edited` (the
    scene changed — the builder records an undo step), `picked` (the
    selection changed), `measured` (dict from chem_scene.measure)."""

    edited = pyqtSignal()
    picked = pyqtSignal()
    measured = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = cs.Scene()
        self.yaw, self.pitch = VIEWS["3D"]
        self.zoom = 30.0                     # pixels per Å
        self.pan = QPointF(0, 0)
        self.tool = "rotate"
        self.element = "C"
        self.labels = False
        self.selection = []                  # atom indices, click order
        self.measures = []                   # (indices, result dict)
        self._drag = None
        self.setMinimumSize(420, 360)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.ClickFocus)
        self._hover = None
        self._centre = (0.0, 0.0, 0.0)
        self._moving = None

    # ------------------------------------------------------- state
    def set_scene(self, scene, fit=True):
        self.scene = scene
        self.selection = []
        self.measures = []
        if fit:
            self.fit()
        self.update()

    def set_view(self, name):
        self.yaw, self.pitch = VIEWS[name]
        self.update()

    def set_tool(self, tool):
        if tool not in TOOLS:
            raise ValueError(tool)
        self.tool = tool
        self.selection = []
        self.update()

    def fit(self):
        pts = [a[1:4] for a in self.scene.atoms]
        pts += [p for e in self.scene.edges for p in e]
        self.pan = QPointF(0, 0)
        if not pts:
            self.zoom = 30.0
            return
        c = [sum(p[i] for p in pts) / len(pts) for i in range(3)]
        span = max(math.dist(p, c) for p in pts) or 1.0
        self.zoom = 0.42 * min(self.width(), self.height()) / (span + 1.5)
        self._centre = c

    def clear_measures(self):
        self.measures = []
        self.update()

    # ----------------------------------------------------- projection
    def _basis(self):
        y, p = math.radians(self.yaw), math.radians(self.pitch)
        # right, up and towards-the-viewer unit vectors
        right = (math.cos(y), math.sin(y), 0.0)
        fwd = (-math.sin(y) * math.cos(p), math.cos(y) * math.cos(p),
               -math.sin(p))
        up = (right[1] * fwd[2] - right[2] * fwd[1],
              right[2] * fwd[0] - right[0] * fwd[2],
              right[0] * fwd[1] - right[1] * fwd[0])
        if self.pitch >= 89.9:               # straight down: y up the screen
            right, up, fwd = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0, 0, -1.0)
        return right, up, fwd

    def project(self, p):
        """(screen x, screen y, depth) of a point in Å; larger depth is
        nearer the viewer."""
        right, up, fwd = self._basis()
        c = getattr(self, "_centre", (0.0, 0.0, 0.0))
        q = [p[i] - c[i] for i in range(3)]
        sx = sum(q[i] * right[i] for i in range(3))
        sy = sum(q[i] * up[i] for i in range(3))
        sz = -sum(q[i] * fwd[i] for i in range(3))
        return (self.width() / 2 + self.pan.x() + sx * self.zoom,
                self.height() / 2 + self.pan.y() - sy * self.zoom, sz)

    def unproject(self, x, y, depth=0.0):
        """The point in Å under screen (x, y), *depth* Å towards the
        viewer from the centre plane."""
        right, up, fwd = self._basis()
        c = getattr(self, "_centre", (0.0, 0.0, 0.0))
        sx = (x - self.width() / 2 - self.pan.x()) / self.zoom
        sy = -(y - self.height() / 2 - self.pan.y()) / self.zoom
        return tuple(c[i] + sx * right[i] + sy * up[i] - depth * fwd[i]
                     for i in range(3))

    def radius_px(self, el):
        return max(3.0, BALL * cr.radius(el) * self.zoom) \
            if el in cr.ELEMENTS else 4.0

    def atom_at(self, x, y):
        best, bz = None, None
        for i, a in enumerate(self.scene.atoms):
            sx, sy, sz = self.project(a[1:4])
            if math.hypot(sx - x, sy - y) <= self.radius_px(a[0]) + PICK_PX:
                if bz is None or sz > bz:
                    best, bz = i, sz
        return best

    def bond_at(self, x, y):
        for b in self.scene.bonds:
            p = self.project(self.scene.atoms[b[0]][1:4])
            q = self.project(self.scene.atoms[b[1]][1:4])
            dx, dy = q[0] - p[0], q[1] - p[1]
            ln2 = dx * dx + dy * dy
            if ln2 < 1:
                continue
            t = max(0.0, min(1.0, ((x - p[0]) * dx + (y - p[1]) * dy) / ln2))
            if math.hypot(p[0] + t * dx - x, p[1] + t * dy - y) <= PICK_PX:
                return b
        return None

    # --------------------------------------------------------- mouse
    def mousePressEvent(self, ev):
        x, y = ev.x(), ev.y()
        self._drag = (ev.button(), x, y, self.yaw, self.pitch,
                      QPointF(self.pan))
        if ev.button() != Qt.LeftButton:
            return
        i = self.atom_at(x, y)
        tool = self.tool
        if tool == "select":
            if i is None:
                self.selection = []
            elif ev.modifiers() & Qt.ShiftModifier:
                if i in self.selection:
                    self.selection.remove(i)
                else:
                    self.selection.append(i)
            else:
                self.selection = [i]
            self.picked.emit()
        elif tool == "measure" and i is not None:
            if i in self.selection:
                return
            self.selection.append(i)
            if len(self.selection) >= 2:
                result = cs.measure(self.scene, self.selection)
                self.measured.emit(result)
                if len(self.selection) == 4:
                    self.measures.append((list(self.selection), result))
                    self.selection = []
            self.picked.emit()
        elif tool == "add":
            if i is not None:
                cs.place_bonded(self.scene, self.element, i)
            else:
                cs.add_atom(self.scene, self.element, self.unproject(x, y))
            self.edited.emit()
        elif tool == "bond" and i is not None:
            self.selection.append(i)
            if len(self.selection) == 2:
                cs.add_bond(self.scene, *self.selection)
                self.selection = []
                self.edited.emit()
            self.picked.emit()
        elif tool == "delete":
            if i is not None:
                cs.delete_atoms(self.scene, [i])
                self.measures = []
                self.edited.emit()
            else:
                b = self.bond_at(x, y)
                if b is not None:
                    cs.delete_bond(self.scene, b[0], b[1])
                    self.edited.emit()
        elif tool == "move" and i is not None:
            self._moving = (i, self.project(self.scene.atoms[i][1:4])[2])
        self.update()

    def mouseMoveEvent(self, ev):
        x, y = ev.x(), ev.y()
        hover = self.atom_at(x, y)
        if hover != self._hover:
            self._hover = hover
            self.update()
        if not self._drag:
            return
        button, x0, y0, yaw0, pitch0, pan0 = self._drag
        if button == Qt.MiddleButton or (
                button == Qt.LeftButton and ev.modifiers() & Qt.AltModifier):
            self.pan = QPointF(pan0.x() + x - x0, pan0.y() + y - y0)
        elif button == Qt.LeftButton and self.tool == "rotate":
            self.yaw = yaw0 + (x - x0) * 0.5
            self.pitch = max(-90.0, min(90.0, pitch0 + (y - y0) * 0.5))
        elif button == Qt.LeftButton and self.tool == "move" and \
                getattr(self, "_moving", None):
            i, _depth = self._moving
            # keep the atom's depth, follow the cursor in the view plane
            right, up, fwd = self._basis()
            c = getattr(self, "_centre", (0.0, 0.0, 0.0))
            p = self.scene.atoms[i][1:4]
            depth = -sum((p[k] - c[k]) * fwd[k] for k in range(3))
            cs.move_atom(self.scene, i, self.unproject(x, y, depth))
        self.update()

    def mouseReleaseEvent(self, ev):
        if getattr(self, "_moving", None):
            self._moving = None
            self.edited.emit()
        self._drag = None

    def wheelEvent(self, ev):
        f = 1.15 if ev.angleDelta().y() > 0 else 1 / 1.15
        self.zoom = max(2.0, min(400.0, self.zoom * f))
        self.update()

    # --------------------------------------------------------- paint
    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#fbfbfd"))
        scene = self.scene
        proj = [self.project(a[1:4]) for a in scene.atoms]
        # cell box
        pen = QPen(QColor("#8a94a6"), 1, Qt.DashLine)
        p.setPen(pen)
        for a, b in scene.edges:
            pa, pb = self.project(a), self.project(b)
            p.drawLine(QPointF(pa[0], pa[1]), QPointF(pb[0], pb[1]))
        # bonds and atoms far to near, a bond drawn with its nearer atom
        order = sorted(range(len(scene.atoms)), key=lambda i: proj[i][2])
        bonds_of = {}
        for b in scene.bonds:
            i, j = b[0], b[1]
            k = i if proj[i][2] <= proj[j][2] else j
            bonds_of.setdefault(k, []).append(b)
        sel = set(self.selection)
        for i in order:
            for b in bonds_of.get(i, ()):
                self._bond(p, proj, b)
            self._atom(p, i, proj[i], i in sel, i == self._hover)
        if self.labels:
            p.setPen(QColor("#1d2330"))
            p.setFont(QFont("Helvetica", 8))
            for i, a in enumerate(scene.atoms):
                p.drawText(QPointF(proj[i][0] + 4, proj[i][1] - 4),
                           f"{a[0]}{i + 1}")
        for idx, result in self.measures:
            self._measure(p, idx, result, QColor("#0b6e4f"))
        if len(self.selection) >= 2 and self.tool == "measure":
            self._measure(p, self.selection,
                          cs.measure(scene, self.selection),
                          QColor("#c2410c"))
        self._legend(p)
        p.end()

    def _bond(self, p, proj, b):
        i, j, order = b
        a, c = proj[i], proj[j]
        mid = QPointF((a[0] + c[0]) / 2, (a[1] + c[1]) / 2)
        w = max(1.5, 0.12 * self.zoom)
        dx, dy = c[0] - a[0], c[1] - a[1]
        ln = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / ln, dx / ln
        offs = [0.0] if int(order) <= 1 else (
            [-0.6, 0.6] if int(order) == 2 else [-1.0, 0.0, 1.0])
        for k, el in ((i, self.scene.atoms[i][0]),
                      (j, self.scene.atoms[j][0])):
            end = QPointF(proj[k][0], proj[k][1])
            pen = QPen(QColor(cr.colour(el)).darker(115), w,
                       Qt.SolidLine, Qt.RoundCap)
            p.setPen(pen)
            for o in offs:
                s = o * w * 1.4
                p.drawLine(QPointF(end.x() + nx * s, end.y() + ny * s),
                           QPointF(mid.x() + nx * s, mid.y() + ny * s))

    def _atom(self, p, i, pr, selected, hover):
        el = self.scene.atoms[i][0]
        r = self.radius_px(el)
        col = QColor(cr.colour(el) if el in cr.ELEMENTS else "#ff00ff")
        g = QRadialGradient(QPointF(pr[0] - r * 0.35, pr[1] - r * 0.35),
                            r * 1.3)
        g.setColorAt(0.0, col.lighter(170))
        g.setColorAt(0.5, col)
        g.setColorAt(1.0, col.darker(160))
        p.setBrush(QBrush(g))
        p.setPen(QPen(QColor("#ff8a00") if selected else
                      QColor("#3b82f6") if hover else col.darker(200),
                      3 if selected or hover else 0.6))
        p.drawEllipse(QPointF(pr[0], pr[1]), r, r)

    def _measure(self, p, idx, result, colour):
        proj = [self.project(self.scene.atoms[i][1:4]) for i in idx]
        pen = QPen(colour, 1.6, Qt.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        for a, b in zip(proj, proj[1:]):
            p.drawLine(QPointF(a[0], a[1]), QPointF(b[0], b[1]))
        if result["kind"] == "distance":
            at = QPointF((proj[0][0] + proj[1][0]) / 2,
                         (proj[0][1] + proj[1][1]) / 2)
            text = f"{result['value']:.3f} Å"
        elif result["kind"] == "angle":
            v = proj[1]
            at = QPointF(v[0], v[1])
            a1 = math.degrees(math.atan2(-(proj[0][1] - v[1]),
                                         proj[0][0] - v[0]))
            a2 = math.degrees(math.atan2(-(proj[2][1] - v[1]),
                                         proj[2][0] - v[0]))
            span = (a2 - a1 + 540) % 360 - 180
            rr = 22
            path = QPainterPath()
            path.arcMoveTo(QRectF(v[0] - rr, v[1] - rr, 2 * rr, 2 * rr), a1)
            path.arcTo(QRectF(v[0] - rr, v[1] - rr, 2 * rr, 2 * rr), a1, span)
            p.setPen(QPen(colour, 1.6))
            p.drawPath(path)
            text = f"{result['value']:.1f}°"
        else:
            at = QPointF((proj[1][0] + proj[2][0]) / 2,
                         (proj[1][1] + proj[2][1]) / 2)
            text = f"τ {result['value']:.1f}°"
        font = QFont("Helvetica", 10, QFont.Bold)
        p.setFont(font)
        box = p.fontMetrics().boundingRect(text)
        rect = QRectF(at.x() + 6, at.y() - box.height() - 4,
                      box.width() + 8, box.height() + 4)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 225))
        p.drawRoundedRect(rect, 3, 3)
        p.setPen(colour)
        p.drawText(rect, Qt.AlignCenter, text)

    def _legend(self, p):
        p.setPen(QColor("#5b6577"))
        p.setFont(QFont("Helvetica", 9))
        hint = {"rotate": "Drag to turn · wheel zooms · middle drag pans",
                "select": "Click an atom · Shift+click adds to the selection",
                "measure": "Click 2 atoms: distance · 3: angle · 4: torsion",
                "add": f"Click empty space for a {self.element} atom, an "
                       f"atom to bond a new {self.element} to it",
                "bond": "Click two atoms to bond them",
                "move": "Drag an atom across the view",
                "delete": "Click an atom or a bond to delete it"}[self.tool]
        p.drawText(QPointF(8, self.height() - 8), hint)
        if self._hover is not None and self._hover < len(self.scene.atoms):
            a = self.scene.atoms[self._hover]
            p.drawText(QPointF(8, 16),
                       f"{a[0]}{self._hover + 1}  ({a[1]:.2f}, {a[2]:.2f}, "
                       f"{a[3]:.2f}) Å")

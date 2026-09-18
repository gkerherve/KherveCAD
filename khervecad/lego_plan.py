"""The Lego Builder's plan: one level of the build seen from above.

A grid of stud cells (X to the right, Y up, like the Top view) at ONE
height — the level the panel's Z control picks, a plate apart. Each cell
shows what a new piece would meet there:

- a piece that starts on this level: its own colour, outlined;
- a piece from lower down that is still standing through this level:
  greyed and hatched — nothing can go there;
- the studs of a piece whose top is exactly this level: a stud circle in
  that piece's colour — somewhere to build on;
- empty ground (level 0) or empty air: plain, faintly tinted with the
  colour of the highest piece lower down.

Under the cursor the chosen piece is drawn where a click would put it,
green-edged when it fits and red when it does not. Left click places,
right click takes away the piece under the cursor; the wheel changes
level, R turns the piece. The widget only draws and reports clicks —
`LegoBuilder` (lego_builder.py) owns the build and the choices.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from PyQt5.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PyQt5.QtWidgets import QSizePolicy, QWidget

from . import lego_builder as lb
from .library_lego import COLORS

#: cells of empty margin round the build
MARGIN = 2
#: the smallest plan, in studs
MIN_CELLS = 16
BLOCKED = QColor("#8f8f8f")
EMPTY = QColor("#f3f3f1")
AIR = QColor("#e4e7ec")


def _hex(name):
    return QColor(COLORS.get(name, name if str(name).startswith("#")
                             else "#C91A09"))


class LegoPlan(QWidget):
    """The plan widget. *panel* gives `build`, `z()`, `footprint()`
    (nx, ny, h) and `colour_name()`."""

    clicked = pyqtSignal(int, int)          # place with the corner here
    hovered = pyqtSignal(object)            # the corner, or None
    erase = pyqtSignal(int, int)            # the cell under the cursor
    level_step = pyqtSignal(int)
    turn = pyqtSignal()

    def __init__(self, panel, parent=None):
        super().__init__(parent)
        self.panel = panel
        self.hover = None                   # (ci, cj) under the cursor
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumSize(360, 360)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    # --------------------------------------------------------- geometry
    def extent(self):
        """(i0, j0, i1, j1): the cells shown, the build plus a margin."""
        build = self.panel.build
        i0 = j0 = 0
        i1 = j1 = MIN_CELLS
        if build is not None:
            for p in lb.pieces(build):
                m, (pi, pj) = lb.meta(p), lb.grid(p)
                i0, j0 = min(i0, pi), min(j0, pj)
                i1, j1 = max(i1, pi + m["nx"]), max(j1, pj + m["ny"])
        return i0 - MARGIN, j0 - MARGIN, i1 + MARGIN, j1 + MARGIN

    def _frame(self):
        i0, j0, i1, j1 = self.extent()
        cols, rows = i1 - i0, j1 - j0
        cell = max(4.0, min((self.width() - 30) / cols,
                            (self.height() - 30) / rows))
        ox = (self.width() - cell * cols) / 2 + 8
        oy = (self.height() + cell * rows) / 2 - 8
        return i0, j0, i1, j1, cell, ox, oy

    def cell_rect(self, i, j, nx=1, ny=1, frame=None):
        i0, j0, _i1, _j1, cell, ox, oy = frame or self._frame()
        return QRectF(ox + (i - i0) * cell, oy - (j - j0 + ny) * cell,
                      nx * cell, ny * cell)

    def cell_at(self, pos):
        i0, j0, i1, j1, cell, ox, oy = self._frame()
        i = i0 + math.floor((pos.x() - ox) / cell)
        j = j0 + math.floor((oy - pos.y()) / cell)
        if i0 <= i < i1 and j0 <= j < j1:
            return i, j
        return None

    def corner_for(self, ci, cj):
        """Where the chosen piece's corner goes for the cell under the
        cursor: the piece centred on it, as the 3D click does."""
        nx, ny, _h = self.panel.footprint()
        return ci - (nx - 1) // 2, cj - (ny - 1) // 2

    # ----------------------------------------------------------- events
    def mouseMoveEvent(self, event):
        cell = self.cell_at(event.pos())
        if cell != self.hover:
            self.hover = cell
            self.update()
            self.hovered.emit(None if cell is None
                              else self.corner_for(*cell))

    def leaveEvent(self, event):
        self.hover = None
        self.update()
        self.hovered.emit(None)

    def mousePressEvent(self, event):
        cell = self.cell_at(event.pos())
        if cell is None:
            return
        if event.button() == Qt.RightButton:
            self.erase.emit(*cell)
        elif event.button() == Qt.LeftButton:
            self.clicked.emit(*self.corner_for(*cell))

    def wheelEvent(self, event):
        step = 1 if event.angleDelta().y() > 0 else -1
        self.level_step.emit(step)

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_R:
            self.turn.emit()
        elif key in (Qt.Key_PageUp, Qt.Key_Plus, Qt.Key_Up):
            self.level_step.emit(1)
        elif key in (Qt.Key_PageDown, Qt.Key_Minus, Qt.Key_Down):
            self.level_step.emit(-1)
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------ paint
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), self.palette().window())
        frame = self._frame()
        i0, j0, i1, j1, cell, ox, oy = frame
        build = self.panel.build
        z = self.panel.z()
        ground = lb.ground(build) if build is not None else 0.0
        filled, support = lb.layer(build, z) if build is not None \
            else ({}, {})
        on_ground = z <= ground + 1e-6
        under = lb.beneath(build, z) if build is not None else {}
        hatch = QBrush(QColor(255, 255, 255, 90), Qt.BDiagPattern)
        grid_pen = QPen(QColor(0, 0, 0, 40), 1)
        for i in range(i0, i1):
            for j in range(j0, j1):
                r = self.cell_rect(i, j, frame=frame)
                here = filled.get((i, j))
                if here is not None and not here[1]:
                    painter.fillRect(r, BLOCKED)
                    painter.fillRect(r, hatch)
                    continue
                if here is not None:
                    continue                # drawn whole, below
                below = support.get((i, j))
                if below is not None:
                    col = _hex(lb.meta(below)["colour"])
                    painter.fillRect(r, col.lighter(150))
                    painter.setPen(QPen(col.darker(130), 1))
                    painter.setBrush(col.lighter(115))
                    painter.drawEllipse(r.center(), cell * 0.3, cell * 0.3)
                    painter.setBrush(Qt.NoBrush)
                elif (i, j) in under:
                    # air over part of the build: its colour, faint, so
                    # the plan still reads where things are
                    col = _hex(lb.meta(under[(i, j)])["colour"])
                    painter.fillRect(r, AIR)
                    col.setAlpha(70)
                    painter.fillRect(r, col)
                else:
                    painter.fillRect(r, EMPTY if on_ground else AIR)
                painter.setPen(grid_pen)
                painter.drawRect(r)
        # the pieces that start on this level, whole
        seen = set()
        for piece, starts in filled.values():
            if not starts or id(piece) in seen:
                continue
            seen.add(id(piece))
            m, (pi, pj) = lb.meta(piece), lb.grid(piece)
            r = self.cell_rect(pi, pj, m["nx"], m["ny"], frame)
            col = _hex(m["colour"])
            painter.fillRect(r, col)
            painter.setPen(QPen(col.darker(160), 2))
            painter.drawRect(r.adjusted(1, 1, -1, -1))
            if r.width() > 40 and r.height() > 14:
                painter.setPen(QColor("white") if col.lightness() < 140
                               else QColor("black"))
                painter.setFont(QFont(self.font().family(), 8))
                painter.drawText(r, Qt.AlignCenter | Qt.TextWordWrap,
                                 m.get("part") or
                                 f"{m['kind']} {m['nx']}×{m['ny']}")
        self._paint_axes(painter, frame)
        self._paint_ghost(painter, frame, build, z)
        painter.end()

    def _paint_axes(self, painter, frame):
        i0, j0, i1, j1, cell, ox, oy = frame
        painter.setFont(QFont(self.font().family(), 7))
        painter.setPen(QColor(120, 120, 120))
        step = 4 if cell >= 10 else 8
        for i in range(i0, i1):
            if i % step == 0:
                r = self.cell_rect(i, j0, frame=frame)
                painter.drawText(QPointF(r.left() + 1, r.bottom() + 11),
                                 str(i))
        for j in range(j0, j1):
            if j % step == 0:
                r = self.cell_rect(i0, j, frame=frame)
                painter.drawText(QPointF(r.left() - 16, r.bottom() - 2),
                                 str(j))
        painter.setPen(QPen(QColor("#d62728"), 2))
        painter.drawText(QPointF(self.width() - 34, self.height() - 4),
                         "X →")
        painter.setPen(QPen(QColor("#2ca02c"), 2))
        painter.drawText(QPointF(4, 12), "Y ↑")

    def _paint_ghost(self, painter, frame, build, z):
        if self.hover is None:
            return
        nx, ny, h = self.panel.footprint()
        if self.panel.erasing():
            r = self.cell_rect(*self.hover, frame=frame)
            painter.setPen(QPen(QColor("#d62728"), 2))
            painter.drawLine(r.topLeft(), r.bottomRight())
            painter.drawLine(r.topRight(), r.bottomLeft())
            return
        i, j = self.corner_for(*self.hover)
        ok = True
        if build is not None:
            ok, _why = lb.can_place(build, i, j, nx, ny, z, h)
        r = self.cell_rect(i, j, nx, ny, frame)
        col = _hex(self.panel.colour_name())
        col.setAlpha(150)
        painter.fillRect(r, col)
        painter.setPen(QPen(QColor("#2ca02c") if ok else QColor("#d62728"),
                            3))
        painter.drawRect(r.adjusted(1, 1, -1, -1))
        # the front edge (-Y) of a turned Library piece, so its facing
        # reads on the plan
        front = self.panel.front_side()
        if front is not None:
            painter.setPen(QPen(QColor(0, 0, 0, 160), 3))
            a, b = {"-Y": (r.bottomLeft(), r.bottomRight()),
                    "+X": (r.topRight(), r.bottomRight()),
                    "+Y": (r.topLeft(), r.topRight()),
                    "-X": (r.topLeft(), r.bottomLeft())}[front]
            painter.drawLine(a, b)

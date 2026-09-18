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

What a left click does is the panel's TOOL (`LegoBuilder.tool`, picked
on its toolbar): Select a piece (outlined in blue, wherever it stands),
Move one by dragging it, Rotate one a quarter, Add the chosen piece —
drawn under the cursor, green-edged where it fits and red where it does
not — or Erase. A right click always takes away, the middle button (or
Space + drag) pans, the wheel zooms about the cursor and Shift + wheel
changes level. Keys: arrows move the selected piece a stud, Shift +
PgUp / PgDn lift it a plate, PgUp / PgDn change level, R turns, Delete
removes, Esc lets go. The widget only draws and reports — the panel
owns the build and every change.

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
MARGIN = 4
#: the smallest plan, in studs
MIN_CELLS = 16
ZOOM_MIN, ZOOM_MAX = 0.5, 12.0
BLOCKED = QColor("#8f8f8f")
EMPTY = QColor("#f3f3f1")
AIR = QColor("#e4e7ec")
SELECTED = QColor("#1f6fd6")


def _hex(name):
    return QColor(COLORS.get(name, name if str(name).startswith("#")
                             else "#C91A09"))


class LegoPlan(QWidget):
    """The plan widget. *panel* gives `build`, `selected`, `tool`, `z()`,
    `footprint()` (nx, ny, h), `colour_name()` and `front_side()`, and
    the methods the clicks call."""

    clicked = pyqtSignal(int, int)          # place with the corner here
    hovered = pyqtSignal(object)            # the corner, or None
    erase = pyqtSignal(int, int)            # the cell under the cursor
    level_step = pyqtSignal(int)
    turn = pyqtSignal()

    def __init__(self, panel, parent=None):
        super().__init__(parent)
        self.panel = panel
        self.hover = None                   # (ci, cj) under the cursor
        self.zoom = 1.0                     # 1 = the whole build fits
        self.pan = QPointF(0.0, 0.0)        # pixels
        self._panning = None                # last mouse position
        self._space = False
        self.drag_from = None               # Move tool: the cell pressed
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

    def _fit(self, zoom=None):
        """(cell, ox, oy) of the plan with no pan at *zoom*."""
        i0, j0, i1, j1 = self.extent()
        cols, rows = i1 - i0, j1 - j0
        fit = max(2.0, min((self.width() - 30) / cols,
                           (self.height() - 30) / rows))
        cell = fit * (self.zoom if zoom is None else zoom)
        return (cell, (self.width() - cell * cols) / 2 + 8,
                (self.height() + cell * rows) / 2 - 8)

    def _frame(self):
        i0, j0, i1, j1 = self.extent()
        cell, ox, oy = self._fit()
        return i0, j0, i1, j1, cell, ox + self.pan.x(), oy + self.pan.y()

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

    # ------------------------------------------------------------- view
    def zoom_by(self, factor, about=None):
        """Zoom by *factor* keeping the point *about* (the centre by
        default) where it is."""
        about = about or QPointF(self.width() / 2, self.height() / 2)
        i0, j0, _i1, _j1, cell, ox, oy = self._frame()
        u, v = (about.x() - ox) / cell, (oy - about.y()) / cell
        self.zoom = min(ZOOM_MAX, max(ZOOM_MIN, self.zoom * factor))
        cell2, ox2, oy2 = self._fit()
        self.pan = QPointF(about.x() - u * cell2 - ox2,
                           about.y() + v * cell2 - oy2)
        self.update()

    def fit_all(self):
        self.zoom = 1.0
        self.pan = QPointF(0.0, 0.0)
        self.update()

    # ----------------------------------------------------------- events
    def mouseMoveEvent(self, event):
        if self._panning is not None:
            d = event.pos() - self._panning
            self._panning = event.pos()
            self.pan += QPointF(d.x(), d.y())
            self.update()
            return
        cell = self.cell_at(event.pos())
        if cell != self.hover:
            self.hover = cell
            self.update()
            adding = self.panel.tool == "add"
            self.hovered.emit(self.corner_for(*cell)
                              if cell is not None and adding else None)

    def leaveEvent(self, event):
        self.hover = None
        self.update()
        self.hovered.emit(None)

    def mousePressEvent(self, event):
        self.setFocus()
        if event.button() == Qt.MiddleButton or (
                event.button() == Qt.LeftButton and self._space):
            self._panning = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            return
        cell = self.cell_at(event.pos())
        if cell is None:
            if event.button() == Qt.LeftButton:
                self.panel.select(None)
            return
        if event.button() == Qt.RightButton:
            self.erase.emit(*cell)
            return
        if event.button() != Qt.LeftButton:
            return
        tool = self.panel.tool
        if tool == "add":
            self.clicked.emit(*self.corner_for(*cell))
        elif tool == "erase":
            self.erase.emit(*cell)
        elif tool == "rotate":
            if self.panel.select_at(*cell) is not None:
                self.panel.rotate_selected()
        elif tool == "move":
            if self.panel.select_at(*cell) is not None:
                self.drag_from = cell
        else:
            self.panel.select_at(*cell)

    def mouseReleaseEvent(self, event):
        if self._panning is not None:
            self._panning = None
            self.unsetCursor()
            return
        if self.drag_from is not None:
            start, end = self.drag_from, self.hover
            self.drag_from = None
            if end is not None and end != start:
                self.panel.move_selected(end[0] - start[0],
                                         end[1] - start[1])
            self.update()

    def wheelEvent(self, event):
        up = event.angleDelta().y() > 0
        if event.modifiers() & Qt.ShiftModifier:
            self.level_step.emit(1 if up else -1)
        else:
            self.zoom_by(1.2 if up else 1 / 1.2, QPointF(event.pos()))

    def keyPressEvent(self, event):
        key, mods = event.key(), event.modifiers()
        shift = bool(mods & Qt.ShiftModifier)
        moves = {Qt.Key_Left: (-1, 0), Qt.Key_Right: (1, 0),
                 Qt.Key_Up: (0, 1), Qt.Key_Down: (0, -1)}
        if key == Qt.Key_Space and not event.isAutoRepeat():
            self._space = True
        elif key == Qt.Key_R:
            if self.panel.tool == "add" or self.panel.selected is None:
                self.turn.emit()
            else:
                self.panel.rotate_selected()
        elif key in moves and self.panel.selected is not None:
            self.panel.move_selected(*moves[key])
        elif key in (Qt.Key_PageUp, Qt.Key_PageDown):
            step = 1 if key == Qt.Key_PageUp else -1
            if shift and self.panel.selected is not None:
                self.panel.move_selected(0, 0, step)
            else:
                self.level_step.emit(step)
        elif key in (Qt.Key_Plus, Qt.Key_Equal):
            self.zoom_by(1.25)
        elif key == Qt.Key_Minus:
            self.zoom_by(0.8)
        elif key in (Qt.Key_Delete, Qt.Key_Backspace):
            self.panel.delete_selected()
        elif key == Qt.Key_Escape:
            self.panel.select(None)
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Space and not event.isAutoRepeat():
            self._space = False
        super().keyReleaseEvent(event)

    # ------------------------------------------------------------ paint
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), self.palette().window())
        frame = self._frame()
        i0, j0, i1, j1, cell, ox, oy = frame
        # only the cells on screen
        vi0 = max(i0, i0 + math.floor(-ox / cell))
        vi1 = min(i1, i0 + math.ceil((self.width() - ox) / cell))
        vj0 = max(j0, j0 + math.floor((oy - self.height()) / cell))
        vj1 = min(j1, j0 + math.ceil(oy / cell))
        build = self.panel.build
        z = self.panel.z()
        ground = lb.ground(build) if build is not None else 0.0
        filled, support = lb.layer(build, z) if build is not None \
            else ({}, {})
        on_ground = z <= ground + 1e-6
        under = lb.beneath(build, z) if build is not None else {}
        hatch = QBrush(QColor(255, 255, 255, 90), Qt.BDiagPattern)
        grid_pen = QPen(QColor(0, 0, 0, 40), 1)
        studs = cell >= 5
        for i in range(vi0, vi1):
            for j in range(vj0, vj1):
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
                    if studs:
                        painter.setPen(QPen(col.darker(130), 1))
                        painter.setBrush(col.lighter(115))
                        painter.drawEllipse(r.center(), cell * 0.3,
                                            cell * 0.3)
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
                if cell >= 4:
                    painter.setPen(grid_pen)
                    painter.drawRect(r)
        # the pieces that start on this level, whole
        seen = set()
        for piece, starts in filled.values():
            if not starts or id(piece) in seen:
                continue
            seen.add(id(piece))
            self._paint_piece(painter, frame, piece)
        self._paint_selection(painter, frame, z)
        self._paint_axes(painter, frame)
        if self.panel.tool == "add":
            self._paint_ghost(painter, frame, build, z)
        elif self.panel.tool == "erase" and self.hover is not None:
            r = self.cell_rect(*self.hover, frame=frame)
            painter.setPen(QPen(QColor("#d62728"), 2))
            painter.drawLine(r.topLeft(), r.bottomRight())
            painter.drawLine(r.topRight(), r.bottomLeft())
        painter.end()

    def _paint_piece(self, painter, frame, piece):
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

    def _paint_selection(self, painter, frame, z):
        piece = self.panel.selected
        if piece is None or self.panel.build is None \
                or piece not in lb.pieces(self.panel.build):
            return
        m, (pi, pj) = lb.meta(piece), lb.grid(piece)
        r = self.cell_rect(pi, pj, m["nx"], m["ny"], frame)
        pen = QPen(SELECTED, 3)
        if abs(float(piece.params.get("z", 0.0)) - z) > 1e-6:
            pen.setStyle(Qt.DashLine)        # it stands on another level
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(r.adjusted(-1, -1, 1, 1))
        if self.drag_from is not None and self.hover is not None:
            di = self.hover[0] - self.drag_from[0]
            dj = self.hover[1] - self.drag_from[1]
            ok = lb.can_place(self.panel.build, pi + di, pj + dj, m["nx"],
                              m["ny"], float(piece.params.get("z", 0.0)),
                              m["h"], ignore=piece)[0]
            g = self.cell_rect(pi + di, pj + dj, m["nx"], m["ny"], frame)
            col = _hex(m["colour"])
            col.setAlpha(150)
            painter.fillRect(g, col)
            painter.setPen(QPen(QColor("#2ca02c") if ok
                                else QColor("#d62728"), 3))
            painter.drawRect(g.adjusted(1, 1, -1, -1))

    def _paint_axes(self, painter, frame):
        i0, j0, i1, j1, cell, ox, oy = frame
        painter.setFont(QFont(self.font().family(), 7))
        painter.setPen(QColor(120, 120, 120))
        step = 4
        while cell * step < 28:
            step *= 2
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

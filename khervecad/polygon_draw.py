"""Drawing a polygon in the 2D view: what shows while it is being drawn
and every way to finish it (2026-10-19, the user: there should be an
"end" always shown and close by).

- a **bar** at the bottom of the sketch view while points are being
  placed — "Polygon · 4 points", **Finish** (from 3 points), **Undo
  point** and **Cancel** — so finishing never depends on knowing a key;
- the **first point** drawn as a ring that turns green when the cursor
  is on it with 3 points or more: clicking it closes the polygon, as in
  most CAD programs;
- a **right-click**, Enter or a double-click finish too; Backspace takes
  the last point back, Esc cancels.

The scene keeps the points (`SketchScene._poly_points`) and reports
every change through `polygon_changed`; this module draws and listens.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtCore import QEvent, QObject, QPointF, Qt
from PyQt5.QtGui import QColor, QPainterPath, QPen
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolButton

from . import icons, language

#: how near (pixels) a click must land on the first point to close
CLOSE_PX = 10.0
#: marker sizes (pixels)
VERTEX_PX = 3.0
RING_PX = 7.0
DRAFT = "#2176c7"
CLOSE = "#2e9a46"


def px_to_scene(scene, pixels):
    """*pixels* of the (first) view as scene units."""
    views = scene.views()
    scale = abs(views[0].transform().m11()) if views else 1.0
    return pixels / (scale or 1.0)


def near_first(scene, pos):
    """Is *pos* on the first point, with enough points to close?"""
    pts = scene._poly_points
    if len(pts) < 3:
        return False
    d = pos - pts[0]
    return (d.x() ** 2 + d.y() ** 2) ** 0.5 <= px_to_scene(scene, CLOSE_PX)


def draft_items(scene, cursor):
    """The rubber band, the vertices and the closing ring for the points
    so far and the cursor: [(QPainterPath, QPen, brush or None)]."""
    pts = scene._poly_points
    closing = near_first(scene, cursor)
    band = QPainterPath(pts[0])
    for p in pts[1:]:
        band.lineTo(p)
    band.lineTo(pts[0] if closing else cursor)
    line = QPen(QColor(CLOSE if closing else DRAFT))
    line.setCosmetic(True)
    line.setWidthF(1.6)
    out = [(band, line, None)]
    dots = QPainterPath()
    r = px_to_scene(scene, VERTEX_PX)
    for p in pts[1:]:
        dots.addEllipse(p, r, r)
    out.append((dots, line, QColor(DRAFT)))
    ring = QPainterPath()
    big = px_to_scene(scene, RING_PX * (1.4 if closing else 1.0))
    ring.addEllipse(pts[0], big, big)
    pen = QPen(QColor(CLOSE if len(pts) >= 3 else DRAFT))
    pen.setCosmetic(True)
    pen.setWidthF(2.0)
    fill = QColor(CLOSE)
    fill.setAlpha(110 if closing else 40)
    out.append((ring, pen, fill if len(pts) >= 3 else None))
    return out


class PolygonBar(QFrame):
    """Finish / Undo point / Cancel at the bottom of the sketch view,
    shown only while a polygon is being drawn."""

    def __init__(self, view):
        super().__init__(view.viewport())
        self.view = view
        self.setObjectName("polygonBar")
        self.setStyleSheet(
            "QFrame#polygonBar { background: rgba(32, 38, 46, 225);"
            " border-radius: 8px; }"
            "QLabel { color: #e8edf2; padding: 0 6px; }"
            "QToolButton { color: #ffffff; border: none; border-radius: 5px;"
            " padding: 4px 9px; background: rgba(255,255,255,30); }"
            "QToolButton:hover { background: rgba(255,255,255,60); }"
            "QToolButton:disabled { color: rgba(255,255,255,90); }"
            "QToolButton#finish { background: #2e9a46; font-weight: 700; }"
            "QToolButton#finish:hover { background: #37b052; }"
            "QToolButton#finish:disabled { background: rgba(46,154,70,90); }")
        row = QHBoxLayout(self)
        row.setContentsMargins(6, 4, 6, 4)
        row.setSpacing(5)
        self.label = QLabel(self)
        row.addWidget(self.label)
        self.finish = self._button("finish", "mdi.check", "Finish",
                                   "Close the polygon (also: click the "
                                   "first point, right-click or Enter)",
                                   lambda: view.scene().finish_polygon())
        self.undo = self._button("undo", "mdi.undo", "Undo point",
                                 "Take the last point back (Backspace)",
                                 lambda: view.scene().undo_polygon_point())
        self.cancel = self._button("cancel", "mdi.close", "Cancel",
                                   "Throw this polygon away (Esc)",
                                   lambda: view.scene().cancel_tool())
        for b in (self.finish, self.undo, self.cancel):
            row.addWidget(b)
        self.hide()
        view.scene().polygon_changed.connect(self.update_for)
        view.viewport().installEventFilter(self)

    def _button(self, name, glyph, text, tip, slot):
        b = QToolButton(self)
        b.setObjectName(name)
        b.setIcon(icons.icon(glyph, "#ffffff"))
        b.setText(language.tr(text))
        b.setToolTip(language.tr(tip))
        b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        b.setFocusPolicy(Qt.NoFocus)        # keys stay with the view
        b.clicked.connect(slot)
        return b

    def update_for(self, count):
        if count <= 0:
            self.hide()
            return
        self.label.setText(language.tr("Polygon · {n} points").format(
            n=count) if count != 1 else language.tr("Polygon · 1 point"))
        self.finish.setEnabled(count >= 3)
        self.finish.setToolTip(language.tr(
            "Close the polygon (also: click the first point, right-click "
            "or Enter)") if count >= 3 else language.tr(
            "A polygon needs at least 3 points"))
        self.adjustSize()
        self._place()
        self.show()
        self.raise_()

    def _place(self):
        vp = self.view.viewport()
        self.move(max(4, (vp.width() - self.width()) // 2),
                  max(4, vp.height() - self.height() - 14))

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Resize and self.isVisible():
            self._place()
        return False


class LineBar(PolygonBar):
    """The same bar for a chain of lines: Finish, Close shape (the last
    line back to the first point), Undo line, Cancel."""

    def __init__(self, view):
        super().__init__(view)
        view.scene().polygon_changed.disconnect(self.update_for)
        from . import sketch_line
        scene = view.scene()
        for b in (self.finish, self.undo, self.cancel):
            b.clicked.disconnect()
        self.finish.clicked.connect(lambda: sketch_line.end_chain(scene))
        self.undo.setText(language.tr("Undo line"))
        self.undo.setToolTip(language.tr("Take the last line back"))
        self.undo.clicked.connect(lambda: sketch_line.undo_line(scene))
        self.cancel.clicked.connect(lambda: sketch_line.end_chain(scene))
        self.cancel.setToolTip(language.tr("Stop drawing lines (Esc)"))
        self.finish.setToolTip(language.tr(
            "Stop here (also: Enter, Esc, double-click, right-click)"))
        self.close_btn = self._button(
            "close", "mdi.vector-polygon", "Close shape",
            "A last line back to the first point: a closed shape for "
            "Create Region", lambda: sketch_line.close_shape(scene))
        self.layout().insertWidget(2, self.close_btn)

    def update_for(self, count, active=True):
        if not active:
            self.hide()
            return
        self.label.setText(language.tr("Lines · {n}").format(n=count))
        self.finish.setEnabled(True)
        self.close_btn.setEnabled(count >= 2)
        self.undo.setEnabled(count >= 1)
        self.adjustSize()
        self._place()
        self.show()
        self.raise_()


def attach(view):
    """Give the sketch *view* its polygon bar (and the lines' one)."""
    view.polygon_bar = PolygonBar(view)
    view.line_bar = LineBar(view)
    return view.polygon_bar

"""Painted CAD-style icons for the extra sketch tools (sketch_tools.py)
and the sketch MODIFY / INSERT panels: centre rectangle, arcs, ellipse,
slot, spline, offset, import 2D drawing. Same unit square and palettes
as icons_cad.py; original drawings in the Fusion / SolidWorks look.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QPainterPath

from .icons_cad import draws


def _arc(cx, cy, r, a0, sweep, n=24):
    return [QPointF(cx + r * math.cos(math.radians(a0 + sweep * i / n)),
                    cy - r * math.sin(math.radians(a0 + sweep * i / n)))
            for i in range(n + 1)]


def _open(d, pts, width=0.07, color=None):
    path = QPainterPath(pts[0])
    for q in pts[1:]:
        path.lineTo(q)
    d.path(path, color=color or d.pal.sketch, width=width)


@draws("rect_center")
def _rect_center(d):
    pts = [QPointF(0.16, 0.28), QPointF(0.84, 0.28), QPointF(0.84, 0.74),
           QPointF(0.16, 0.74)]
    d.poly(pts, color=d.pal.sketch, width=0.07)
    c = QPointF(0.5, 0.51)
    d.line(c, pts[1], d.pal.edge, 0.035, [2, 2])
    d.dot(c, d.pal.edge, 0.06)
    d.dot(pts[1], d.pal.edge, 0.055)


@draws("arc_center")
def _arc_center(d):
    c = QPointF(0.3, 0.72)
    pts = _arc(0.3, 0.72, 0.52, 0, 90)
    _open(d, pts)
    d.line(c, pts[0], d.pal.edge, 0.035, [2, 2])
    d.line(c, pts[-1], d.pal.edge, 0.035, [2, 2])
    for q in (c, pts[0], pts[-1]):
        d.dot(q, d.pal.edge, 0.055)


@draws("arc_3pt")
def _arc_3pt(d):
    pts = _arc(0.5, 0.78, 0.4, 10, 160)
    _open(d, pts)
    for q in (pts[0], pts[len(pts) // 2], pts[-1]):
        d.dot(q, d.pal.edge, 0.055)


@draws("ellipse")
def _ellipse(d):
    c = QPointF(0.5, 0.52)
    d.p.setPen(d.pen(d.pal.sketch, 0.07))
    d.p.setBrush(Qt.NoBrush)
    d.p.drawEllipse(c, 0.38, 0.24)
    d.line(c, QPointF(0.88, 0.52), d.pal.edge, 0.035, [2, 2])
    d.line(c, QPointF(0.5, 0.28), d.pal.edge, 0.035, [2, 2])
    d.dot(c, d.pal.edge, 0.05)


@draws("slot")
def _slot(d):
    path = QPainterPath()
    path.addRoundedRect(QRectF(0.1, 0.34, 0.8, 0.34), 0.17, 0.17)
    d.path(path, color=d.pal.sketch, width=0.07)
    a, b = QPointF(0.27, 0.51), QPointF(0.73, 0.51)
    d.line(a, b, d.pal.edge, 0.035, [2, 2])
    d.dot(a, d.pal.edge, 0.05)
    d.dot(b, d.pal.edge, 0.05)


@draws("spline")
def _spline(d):
    path = QPainterPath(QPointF(0.12, 0.72))
    path.cubicTo(QPointF(0.3, 0.1), QPointF(0.55, 0.95),
                 QPointF(0.88, 0.28))
    d.path(path, color=d.pal.sketch, width=0.07)
    for q in ((0.12, 0.72), (0.4, 0.45), (0.65, 0.6), (0.88, 0.28)):
        d.dot(QPointF(*q), d.pal.edge, 0.05)


@draws("offset")
def _offset(d):
    inner = QPainterPath()
    inner.addRoundedRect(QRectF(0.3, 0.32, 0.4, 0.36), 0.04, 0.04)
    outer = QPainterPath()
    outer.addRoundedRect(QRectF(0.14, 0.16, 0.72, 0.68), 0.16, 0.16)
    d.path(outer, color=d.pal.sketch, width=0.065)
    d.path(inner, color=d.pal.edge, width=0.05)
    d.line(QPointF(0.7, 0.5), QPointF(0.86, 0.5), d.pal.edge, 0.035, [2, 2])


@draws("import_2d")
def _import_2d(d):
    page = [QPointF(0.2, 0.1), QPointF(0.66, 0.1), QPointF(0.8, 0.24),
            QPointF(0.8, 0.9), QPointF(0.2, 0.9)]
    d.poly(page, d.pal.paper, color=d.pal.edge, width=0.045)
    path = QPainterPath(QPointF(0.3, 0.7))
    path.cubicTo(QPointF(0.35, 0.3), QPointF(0.6, 0.85),
                 QPointF(0.7, 0.4))
    d.path(path, color=d.pal.sketch, width=0.06)

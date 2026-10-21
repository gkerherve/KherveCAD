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
    d.dot(c, d.pal.point, 0.06)
    d.dot(pts[1], d.pal.point, 0.055)


@draws("arc_center")
def _arc_center(d):
    c = QPointF(0.3, 0.72)
    pts = _arc(0.3, 0.72, 0.52, 0, 90)
    _open(d, pts)
    d.line(c, pts[0], d.pal.edge, 0.035, [2, 2])
    d.line(c, pts[-1], d.pal.edge, 0.035, [2, 2])
    for q in (c, pts[0], pts[-1]):
        d.dot(q, d.pal.point, 0.055)


@draws("arc_3pt")
def _arc_3pt(d):
    pts = _arc(0.5, 0.78, 0.4, 10, 160)
    _open(d, pts)
    for q in (pts[0], pts[len(pts) // 2], pts[-1]):
        d.dot(q, d.pal.point, 0.055)


@draws("ellipse")
def _ellipse(d):
    c = QPointF(0.5, 0.52)
    d.p.setPen(d.pen(d.pal.sketch, 0.07))
    d.p.setBrush(Qt.NoBrush)
    d.p.drawEllipse(c, 0.38, 0.24)
    d.line(c, QPointF(0.88, 0.52), d.pal.edge, 0.035, [2, 2])
    d.line(c, QPointF(0.5, 0.28), d.pal.edge, 0.035, [2, 2])
    d.dot(c, d.pal.point, 0.05)


@draws("slot")
def _slot(d):
    path = QPainterPath()
    path.addRoundedRect(QRectF(0.1, 0.34, 0.8, 0.34), 0.17, 0.17)
    d.path(path, color=d.pal.sketch, width=0.07)
    a, b = QPointF(0.27, 0.51), QPointF(0.73, 0.51)
    d.line(a, b, d.pal.edge, 0.035, [2, 2])
    d.dot(a, d.pal.point, 0.05)
    d.dot(b, d.pal.point, 0.05)


@draws("spline")
def _spline(d):
    path = QPainterPath(QPointF(0.12, 0.72))
    path.cubicTo(QPointF(0.3, 0.1), QPointF(0.55, 0.95),
                 QPointF(0.88, 0.28))
    d.path(path, color=d.pal.sketch, width=0.07)
    for q in ((0.12, 0.72), (0.4, 0.45), (0.65, 0.6), (0.88, 0.28)):
        d.dot(QPointF(*q), d.pal.point, 0.05)


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


# ---- the further CREATE tools (sketch_tools2.py, 2026-10-21) ----
def _circ(d, c, r, color=None, width=0.07, dash=None):
    d.p.setPen(d.pen(color or d.pal.sketch, width, dash))
    d.p.setBrush(Qt.NoBrush)
    d.p.drawEllipse(QPointF(*c), r, r)


@draws("construction_line")
def _construction_line(d):
    d.line(QPointF(0.1, 0.8), QPointF(0.9, 0.2), d.pal.edge, 0.06, [3, 2])
    d.dot(QPointF(0.1, 0.8), d.pal.point, 0.06)
    d.dot(QPointF(0.9, 0.2), d.pal.point, 0.06)


@draws("construction")
def _construction(d):
    d.line(QPointF(0.12, 0.84), QPointF(0.6, 0.36), d.pal.sketch, 0.07)
    d.line(QPointF(0.4, 0.64), QPointF(0.88, 0.16), d.pal.edge, 0.06,
           [3, 2])
    d.text(0.24, 0.32, "%", 0.24, d.pal.make)


@draws("point")
def _point(d):
    d.line(QPointF(0.5, 0.24), QPointF(0.5, 0.76), d.pal.edge, 0.035,
           [2, 2])
    d.line(QPointF(0.24, 0.5), QPointF(0.76, 0.5), d.pal.edge, 0.035,
           [2, 2])
    d.dot(QPointF(0.5, 0.5), d.pal.sketch, 0.11)


@draws("polyline")
def _polyline(d):
    pts = [QPointF(0.1, 0.82), QPointF(0.32, 0.3), QPointF(0.6, 0.66),
           QPointF(0.9, 0.18)]
    _open(d, pts)
    for q in pts:
        d.dot(q, d.pal.point, 0.05)


@draws("rect_3pt")
def _rect_3pt(d):
    pts = [QPointF(0.18, 0.62), QPointF(0.62, 0.2), QPointF(0.86, 0.46),
           QPointF(0.42, 0.88)]
    d.poly(pts, color=d.pal.sketch, width=0.07)
    for q in pts[:3]:
        d.dot(q, d.pal.point, 0.055)


@draws("circle_2pt")
def _circle_2pt(d):
    _circ(d, (0.5, 0.5), 0.36)
    a, b = QPointF(0.245, 0.755), QPointF(0.755, 0.245)
    d.line(a, b, d.pal.edge, 0.035, [2, 2])
    d.dot(a, d.pal.point, 0.055)
    d.dot(b, d.pal.point, 0.055)


@draws("circle_3pt")
def _circle_3pt(d):
    _circ(d, (0.5, 0.5), 0.36)
    for t in (100, 220, 340):
        a = math.radians(t)
        d.dot(QPointF(0.5 + 0.36 * math.cos(a), 0.5 - 0.36 * math.sin(a)),
              d.pal.edge, 0.055)


@draws("circle_tangent")
def _circle_tangent(d):
    tri = [QPointF(0.5, 0.08), QPointF(0.94, 0.86), QPointF(0.06, 0.86)]
    d.poly(tri, color=d.pal.edge, width=0.04)
    _circ(d, (0.5, 0.6), 0.26)


@draws("arc_tangent")
def _arc_tangent(d):
    d.line(QPointF(0.08, 0.78), QPointF(0.45, 0.78), d.pal.edge, 0.06)
    _open(d, _arc(0.45, 0.48, 0.3, -90, 180))
    d.dot(QPointF(0.45, 0.78), d.pal.point, 0.055)


@draws("poly_reg")
def _poly_reg(d):
    pts = [QPointF(0.5 + 0.38 * math.cos(math.radians(30 + 60 * i)),
                   0.5 - 0.38 * math.sin(math.radians(30 + 60 * i)))
           for i in range(6)]
    d.poly(pts, color=d.pal.sketch, width=0.07)
    d.dot(QPointF(0.5, 0.5), d.pal.point, 0.05)


@draws("bspline")
def _bspline(d):
    ctrl = [QPointF(0.1, 0.8), QPointF(0.3, 0.14), QPointF(0.7, 0.86),
            QPointF(0.9, 0.2)]
    for a, b in zip(ctrl, ctrl[1:]):
        d.line(a, b, d.pal.edge, 0.03, [2, 2])
    path = QPainterPath(QPointF(0.13, 0.7))
    path.cubicTo(QPointF(0.32, 0.3), QPointF(0.66, 0.72),
                 QPointF(0.87, 0.28))
    d.path(path, color=d.pal.sketch, width=0.07)
    for q in ctrl:
        d.dot(q, d.pal.point, 0.05)


@draws("conic")
def _conic(d):
    a, b, s = QPointF(0.1, 0.84), QPointF(0.9, 0.84), QPointF(0.5, 0.12)
    d.line(a, s, d.pal.edge, 0.03, [2, 2])
    d.line(s, b, d.pal.edge, 0.03, [2, 2])
    path = QPainterPath(a)
    path.quadTo(s, b)
    d.path(path, color=d.pal.sketch, width=0.07)
    d.dot(s, d.pal.make, 0.06)

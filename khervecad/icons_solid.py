"""Painted icons for the 3D solids: a shaded little object for each, lit
from the top left, so a sphere reads as a ball, a cylinder as a can
and a rounded box as a box with soft edges (the Material Design glyphs
they had were a disc, a stack of discs and a strip of film).

`icon(kind)` returns a QIcon holding the drawing at several pixel sizes
(sharp on a Retina screen); `KINDS` lists what is drawn. Everything is
vector QPainter work — no image files ship.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import (QBrush, QColor, QIcon, QLinearGradient, QPainter,
                         QPainterPath, QPen, QPixmap, QPolygonF,
                         QRadialGradient)

#: the body colour of every solid (a CAD blue) and its outline
BASE = QColor("#3d8ad6")
EDGE = QColor("#1d4f84")
SIZES = (16, 20, 24, 32, 40, 48, 64)


def _shade(color, k):
    """*color* lighter (k > 1) or darker (k < 1)."""
    return color.lighter(int(100 * k)) if k >= 1 else \
        color.darker(int(100 / k))


def _pen(s):
    pen = QPen(EDGE, max(0.9, s * 0.045))
    pen.setJoinStyle(Qt.RoundJoin)
    pen.setCapStyle(Qt.RoundCap)
    return pen


def _iso(s, rounded=False):
    """An isometric box: three faces, top lightest."""
    def run(p):
        c = s / 2.0
        w, h = s * 0.40, s * 0.22          # half width, top face half-depth
        top_y = s * 0.12
        bot_y = s * 0.88
        apex = QPointF(c, top_y)
        left = QPointF(c - w, top_y + h)
        right = QPointF(c + w, top_y + h)
        front = QPointF(c, top_y + 2 * h)
        top = QPolygonF([apex, right, front, left])
        lft = QPolygonF([left, front, QPointF(c, bot_y),
                         QPointF(c - w, bot_y - h)])
        rgt = QPolygonF([front, right, QPointF(c + w, bot_y - h),
                         QPointF(c, bot_y)])
        faces = ((top, _shade(BASE, 1.45)), (lft, _shade(BASE, 1.05)),
                 (rgt, _shade(BASE, 0.72)))
        if rounded:
            # the three shaded faces clipped to a silhouette with round
            # corners, the inner edges drawn soft: a box with eased edges
            r = s * 0.10
            hexagon = QPolygonF([apex, right, QPointF(c + w, bot_y - h),
                                 QPointF(c, bot_y),
                                 QPointF(c - w, bot_y - h), left])
            outline = _round_path(hexagon, r)
            p.save()
            p.setClipPath(outline)
            p.setPen(Qt.NoPen)
            for poly, col in faces:
                p.setBrush(col)
                p.drawPolygon(poly)
            soft = QPen(_shade(BASE, 1.7), max(1.2, s * 0.075))
            soft.setCapStyle(Qt.RoundCap)
            p.setPen(soft)
            p.drawLine(left, front)
            p.drawLine(front, right)
            dim = QPen(_shade(BASE, 0.9), max(1.0, s * 0.06))
            dim.setCapStyle(Qt.RoundCap)
            p.setPen(dim)
            p.drawLine(front, QPointF(c, bot_y))
            p.restore()
            p.setPen(_pen(s))
            p.setBrush(Qt.NoBrush)
            p.drawPath(outline)
            return
        p.setPen(_pen(s))
        for poly, col in faces:
            p.setBrush(col)
            p.drawPolygon(poly)
    return run


def _inset(poly, d):
    """*poly* shrunk by *d* towards its centroid (enough for convex
    icon faces)."""
    pts = [poly.at(i) for i in range(poly.count())]
    cx = sum(p.x() for p in pts) / len(pts)
    cy = sum(p.y() for p in pts) / len(pts)
    out = []
    for p in pts:
        dx, dy = p.x() - cx, p.y() - cy
        n = math.hypot(dx, dy) or 1.0
        out.append(QPointF(p.x() - dx / n * d, p.y() - dy / n * d))
    return QPolygonF(out)


def _round_path(poly, r):
    """A closed path round *poly* with every corner rounded by *r*."""
    pts = [poly.at(i) for i in range(poly.count())]
    n = len(pts)
    path = QPainterPath()
    for i in range(n):
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
        da = QPointF(a.x() - b.x(), a.y() - b.y())
        dc = QPointF(c.x() - b.x(), c.y() - b.y())
        la = math.hypot(da.x(), da.y()) or 1.0
        lc = math.hypot(dc.x(), dc.y()) or 1.0
        k = min(r, la / 2.0, lc / 2.0)
        p1 = QPointF(b.x() + da.x() / la * k, b.y() + da.y() / la * k)
        p2 = QPointF(b.x() + dc.x() / lc * k, b.y() + dc.y() / lc * k)
        if i == 0:
            path.moveTo(p1)
        else:
            path.lineTo(p1)
        path.quadTo(b, p2)
    path.closeSubpath()
    return path


def _sphere(s):
    def run(p):
        c = s / 2.0
        r = s * 0.40
        g = QRadialGradient(QPointF(c - r * 0.38, c - r * 0.42), r * 1.35)
        g.setColorAt(0.0, _shade(BASE, 1.9))
        g.setColorAt(0.35, _shade(BASE, 1.25))
        g.setColorAt(0.85, _shade(BASE, 0.75))
        g.setColorAt(1.0, _shade(BASE, 0.6))
        p.setPen(_pen(s))
        p.setBrush(QBrush(g))
        p.drawEllipse(QPointF(c, c), r, r)
    return run


def _ellipsoid(s):
    def run(p):
        c = s / 2.0
        rx, ry = s * 0.30, s * 0.42
        g = QRadialGradient(QPointF(c - rx * 0.35, c - ry * 0.45), ry * 1.3)
        g.setColorAt(0.0, _shade(BASE, 1.9))
        g.setColorAt(0.4, _shade(BASE, 1.2))
        g.setColorAt(1.0, _shade(BASE, 0.62))
        p.setPen(_pen(s))
        p.setBrush(QBrush(g))
        p.drawEllipse(QPointF(c, c), rx, ry)
    return run


def _side_gradient(x0, x1):
    g = QLinearGradient(QPointF(x0, 0), QPointF(x1, 0))
    g.setColorAt(0.0, _shade(BASE, 0.95))
    g.setColorAt(0.3, _shade(BASE, 1.45))
    g.setColorAt(0.75, _shade(BASE, 0.9))
    g.setColorAt(1.0, _shade(BASE, 0.62))
    return g


def _cylinder(s):
    def run(p):
        c = s / 2.0
        rx, ry = s * 0.33, s * 0.12
        top, bot = s * 0.20, s * 0.80
        body = QPainterPath()
        body.moveTo(c - rx, top)
        body.lineTo(c - rx, bot)
        body.arcTo(QRectF(c - rx, bot - ry, 2 * rx, 2 * ry), 180, 180)
        body.lineTo(c + rx, top)
        body.closeSubpath()
        p.setPen(_pen(s))
        p.setBrush(QBrush(_side_gradient(c - rx, c + rx)))
        p.drawPath(body)
        p.setBrush(_shade(BASE, 1.5))
        p.drawEllipse(QPointF(c, top), rx, ry)
    return run


def _capsule(s):
    def run(p):
        c = s / 2.0
        r = s * 0.20
        top, bot = s * 0.10 + r, s * 0.90 - r
        path = QPainterPath()
        path.addRoundedRect(QRectF(c - r, top - r, 2 * r, bot - top + 2 * r),
                            r, r)
        p.save()
        p.translate(c, c)
        p.rotate(35)
        p.translate(-c, -c)
        p.setPen(_pen(s))
        p.setBrush(QBrush(_side_gradient(c - r, c + r)))
        p.drawPath(path)
        hi = QPen(_shade(BASE, 1.9), max(0.8, s * 0.05))
        hi.setCapStyle(Qt.RoundCap)
        p.setPen(hi)
        p.drawLine(QPointF(c - r * 0.45, top), QPointF(c - r * 0.45,
                                                      bot - r * 0.2))
        p.restore()
    return run


def _loft(s):
    """A lofted body: two different sections (an ellipse below, a
    smaller circle above) joined by curved sides — a vase."""
    def run(p):
        c = s / 2.0
        top, bot = s * 0.18, s * 0.82
        rt, rb = s * 0.18, s * 0.34
        ryt, ryb = s * 0.07, s * 0.11
        body = QPainterPath()
        body.moveTo(c - rt, top)
        body.cubicTo(QPointF(c - rt * 0.6, s * 0.45),
                     QPointF(c - rb * 1.15, s * 0.55),
                     QPointF(c - rb, bot))
        body.arcTo(QRectF(c - rb, bot - ryb, 2 * rb, 2 * ryb), 180, 180)
        body.cubicTo(QPointF(c + rb * 1.15, s * 0.55),
                     QPointF(c + rt * 0.6, s * 0.45),
                     QPointF(c + rt, top))
        body.closeSubpath()
        p.setPen(_pen(s))
        p.setBrush(QBrush(_side_gradient(c - rb, c + rb)))
        p.drawPath(body)
        p.setBrush(_shade(BASE, 1.5))
        p.drawEllipse(QPointF(c, top), rt, ryt)
        # the section lines a loft is made from
        sec = QPen(_shade(BASE, 0.55), max(0.6, s * 0.025))
        sec.setDashPattern([2.0, 2.0])
        p.setPen(sec)
        p.setBrush(Qt.NoBrush)
        mid = s * 0.52
        rm = (rt + rb) / 2.0 * 0.92
        p.drawArc(QRectF(c - rm, mid - s * 0.06, 2 * rm, s * 0.12),
                  180 * 16, 180 * 16)
    return run


def _cone(s):
    def run(p):
        c = s / 2.0
        rx, ry = s * 0.34, s * 0.11
        top, bot = s * 0.12, s * 0.80
        body = QPainterPath()
        body.moveTo(c, top)
        body.lineTo(c - rx, bot)
        body.arcTo(QRectF(c - rx, bot - ry, 2 * rx, 2 * ry), 180, 180)
        body.closeSubpath()
        p.setPen(_pen(s))
        p.setBrush(QBrush(_side_gradient(c - rx, c + rx)))
        p.drawPath(body)
    return run


DRAWERS = {"cube": lambda s: _iso(s), "rounded_box": lambda s: _iso(s, True),
           "sphere": _sphere, "ellipsoid": _ellipsoid,
           "cylinder": _cylinder, "capsule": _capsule, "loft": _loft,
           "cone": _cone}
KINDS = tuple(DRAWERS)
_CACHE = {}


def pixmap(kind, size):
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing, True)
    DRAWERS[kind](float(size))(p)
    p.end()
    return pix


def icon(kind):
    """The painted icon for solid *kind*, or None when there is none."""
    if kind not in DRAWERS:
        return None
    got = _CACHE.get(kind)
    if got is None:
        got = QIcon()
        for size in SIZES:
            got.addPixmap(pixmap(kind, size))
        _CACHE[kind] = got
    return got

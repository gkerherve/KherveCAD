"""The rest of the painted CAD-style icons (icons_cad.py): deform and
sculpt, character, repeat and logic, Edit Mode, the engineering
documents and the analysis tools. Same unit square, same palettes.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import (QBrush, QColor, QLinearGradient, QPainterPath,
                         QPen, QPolygonF)

from .icons_cad import draws, shade


def _bar_path(d, centre_line, half):
    """A flat bar of half-width *half* (units) round a polyline of
    QPointF — the outline as a path."""
    left, right = [], []
    n = len(centre_line)
    for i, q in enumerate(centre_line):
        a = centre_line[max(i - 1, 0)]
        b = centre_line[min(i + 1, n - 1)]
        dx, dy = b.x() - a.x(), b.y() - a.y()
        m = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / m * half, dx / m * half
        left.append(QPointF(q.x() + nx, q.y() + ny))
        right.append(QPointF(q.x() - nx, q.y() - ny))
    path = QPainterPath(left[0])
    for q in left[1:] + right[::-1]:
        path.lineTo(q)
    path.closeSubpath()
    return path


def _body_fill(d, x0, y0, x1, y1, body=None):
    body = body or d.pal.body
    g = QLinearGradient(QPointF(x0, y0), QPointF(x1, y1))
    g.setColorAt(0.0, shade(body, 1.4))
    g.setColorAt(0.5, shade(body, 1.05))
    g.setColorAt(1.0, shade(body, 0.72))
    return QBrush(g)


# ================================================================ deform
@draws("blend")
def _blend(d):
    a = QPainterPath()
    a.addEllipse(QPointF(0.36, 0.56), 0.24, 0.24)
    b = QPainterPath()
    b.addEllipse(QPointF(0.66, 0.40), 0.20, 0.20)
    neck = QPainterPath()
    neck.addEllipse(QPointF(0.52, 0.48), 0.16, 0.12)
    d.path(a.united(b).united(neck), _body_fill(d, 0.1, 0.2, 0.9, 0.8))


@draws("bend")
def _bend(d):
    pts = [QPointF(0.18 + 0.64 * t, 0.78 - 0.55 * math.sin(math.pi * t))
           for t in [i / 16 for i in range(17)]]
    d.path(_bar_path(d, pts, 0.11), _body_fill(d, 0.2, 0.2, 0.8, 0.9))
    d.arrow(QPointF(0.5, 0.62), QPointF(0.5, 0.38), d.pal.make, 0.05, 0.1)


@draws("twist")
def _twist(d):
    for i in range(5):
        y = 0.80 - i * 0.15
        t = i / 4.0
        w = 0.30 * abs(math.cos(math.pi * t * 0.9))
        d.poly([QPointF(0.5 - w - 0.05, y), QPointF(0.5 + w + 0.05, y),
                QPointF(0.5 + w * 0.8 + 0.05, y - 0.13),
                QPointF(0.5 - w * 0.8 - 0.05, y - 0.13)],
               shade(d.pal.body, 1.3 - 0.12 * i), width=0.03)
    d.arc_arrow(QPointF(0.5, 0.16), 0.30, 0.08, 200, 520, d.pal.make,
                0.05, 0.1)


@draws("taper")
def _taper(d):
    d.solid([(-0.75, -0.75, 0), (0.75, -0.75, 0), (0.75, 0.75, 0),
             (-0.75, 0.75, 0)],
            [(-0.3, -0.3, 1.5), (0.3, -0.3, 1.5), (0.3, 0.3, 1.5),
             (-0.3, 0.3, 1.5)])


@draws("lattice")
def _lattice(d):
    d.box(-0.5, -0.5, 0.15, 1.0, 1.0, 0.7)
    corners = [(x, y, z) for x in (-0.8, 0.8) for y in (-0.8, 0.8)
               for z in (-0.1, 1.15)]
    for a in corners:
        for b in corners:
            if sum(1 for u, v in zip(a, b) if u != v) == 1 and a < b:
                d.line(d.P(*a), d.P(*b), d.pal.select, 0.03)
    for q in corners:
        d.dot(d.P(*q), d.pal.select, 0.04, d.pal.select)


@draws("subdivide")
def _subdivide(d):
    d.ball(QPointF(0.5, 0.52), 0.36)
    for t in (-0.18, 0.0, 0.18):
        d.p.setPen(d.pen(d.pal.edge, 0.025))
        d.p.setBrush(Qt.NoBrush)
        d.p.drawEllipse(QPointF(0.5, 0.52), abs(0.36 - abs(t) * 1.2)
                        if t else 0.36, 0.36)
        d.line(QPointF(0.14, 0.52 + t), QPointF(0.86, 0.52 + t),
               d.pal.edge, 0.025)


@draws("decimate")
def _decimate(d):
    pts = [QPointF(0.5 + 0.38 * math.cos(math.radians(a)),
                   0.52 + 0.38 * math.sin(math.radians(a)))
           for a in range(0, 360, 60)]
    c = QPointF(0.48, 0.50)
    for i in range(6):
        d.poly([c, pts[i], pts[(i + 1) % 6]],
               shade(d.pal.body, 1.35 - 0.1 * i), width=0.03)


@draws("remesh")
def _remesh(d):
    for i in range(3):
        for j in range(3):
            if (i, j) in ((0, 0), (2, 2)):
                continue
            d.box(-0.9 + 0.6 * i, -0.9 + 0.6 * j, 0, 0.6, 0.6, 0.6)


@draws("wireframe")
def _wireframe(d):
    corners = [(x, y, z) for x in (-0.7, 0.7) for y in (-0.7, 0.7)
               for z in (0, 1.2)]
    tube = d.pal.body if d.style == "SolidWorks" else d.pal.edge
    for a in corners:
        for b in corners:
            if sum(1 for u, v in zip(a, b) if u != v) == 1 and a < b:
                d.line(d.P(*a), d.P(*b), d.pal.edge, 0.09)
                d.line(d.P(*a), d.P(*b), shade(tube, 1.2), 0.05)


@draws("shell")
def _shell(d):
    d.box(-0.8, -0.8, 0, 1.6, 1.6, 0.9)
    t = 0.18
    d.poly([d.P(-0.8 + t, -0.8 + t, 0.9), d.P(0.8 - t, -0.8 + t, 0.9),
            d.P(0.8 - t, 0.8 - t, 0.9), d.P(-0.8 + t, 0.8 - t, 0.9)],
           shade(d.pal.body, 0.6))
    d.poly([d.P(-0.8 + t, -0.8 + t, 0.9), d.P(0.8 - t, -0.8 + t, 0.9),
            d.P(0.8 - t, -0.8 + t, 0.35), d.P(-0.8 + t, -0.8 + t, 0.35)],
           shade(d.pal.body, 0.82), width=0.025)


def _surface(d, bumps):
    path = QPainterPath(QPointF(0.08, 0.86))
    for i in range(41):
        x = 0.08 + 0.84 * i / 40
        path.lineTo(QPointF(x, 0.58 - bumps(x)))
    path.lineTo(QPointF(0.92, 0.86))
    path.closeSubpath()
    d.path(path, _body_fill(d, 0.1, 0.3, 0.9, 0.9))


@draws("sculpt")
def _sculpt(d):
    _surface(d, lambda x: 0.16 * math.exp(-((x - 0.42) / 0.14) ** 2))
    d.p.save()
    d.p.translate(0.66, 0.30)
    d.p.rotate(40)
    d.poly([QPointF(-0.05, -0.30), QPointF(0.05, -0.30),
            QPointF(0.05, 0.02), QPointF(-0.05, 0.02)], d.pal.make)
    d.poly([QPointF(-0.07, 0.02), QPointF(0.07, 0.02), QPointF(0.0, 0.14)],
           shade(d.pal.make, 0.7))
    d.p.restore()


@draws("displace")
def _displace(d):
    _surface(d, lambda x: 0.06 * math.sin(x * 38) + 0.04)


@draws("shrinkwrap")
def _shrinkwrap(d):
    d.ball(QPointF(0.5, 0.55), 0.26)
    d.p.setPen(d.pen(d.pal.select, 0.05, [2, 1.5]))
    d.p.setBrush(Qt.NoBrush)
    d.p.drawEllipse(QPointF(0.5, 0.55), 0.36, 0.36)
    for a in (45, 135, 225, 315):
        r = math.radians(a)
        d.arrow(QPointF(0.5 + 0.44 * math.cos(r), 0.55 + 0.44 * math.sin(r)),
                QPointF(0.5 + 0.30 * math.cos(r), 0.55 + 0.30 * math.sin(r)),
                d.pal.make, 0.035, 0.07)


# ============================================================= character
def _figure(d, colour=None, x=0.5):
    colour = colour or d.pal.body
    d.ball(QPointF(x, 0.20), 0.10, colour)
    body = QPainterPath()
    body.addRoundedRect(QRectF(x - 0.13, 0.32, 0.26, 0.32), 0.08, 0.08)
    d.path(body, _body_fill(d, x - 0.13, 0.3, x + 0.13, 0.7, colour))
    for dx in (-0.07, 0.07):
        d.line(QPointF(x + dx, 0.62), QPointF(x + dx * 1.3, 0.90),
               d.pal.edge, 0.09)
        d.line(QPointF(x + dx, 0.62), QPointF(x + dx * 1.3, 0.90),
               shade(colour, 0.9), 0.05)


@draws("symmetry")
def _symmetry(d):
    d.p.save()
    d.p.setClipRect(QRectF(0, 0, 0.5, 1))
    _figure(d)
    d.p.setClipRect(QRectF(0.5, 0, 0.5, 1))
    _figure(d, d.pal.paper)                 # the mirrored half, a ghost
    d.p.restore()
    d.line(QPointF(0.5, 0.04), QPointF(0.5, 0.96), d.pal.select, 0.045,
           [3, 2])


def _bones(d, pts, colour):
    for a, b in zip(pts, pts[1:]):
        dx, dy = b.x() - a.x(), b.y() - a.y()
        n = math.hypot(dx, dy) or 1.0
        w = 0.07
        mid = QPointF(a.x() + dx * 0.25, a.y() + dy * 0.25)
        d.poly([a, QPointF(mid.x() - dy / n * w, mid.y() + dx / n * w), b,
                QPointF(mid.x() + dy / n * w, mid.y() - dx / n * w)],
               colour, width=0.03)
    for q in pts:
        d.ball(q, 0.05, colour)


@draws("joint")
def _joint(d):
    _bones(d, [QPointF(0.18, 0.80), QPointF(0.50, 0.50)], d.pal.body)
    _bones(d, [QPointF(0.50, 0.50), QPointF(0.82, 0.30)], d.pal.body)
    d.ball(QPointF(0.50, 0.50), 0.09, d.pal.select)
    d.arc_arrow(QPointF(0.5, 0.5), 0.2, 0.2, 200, 300, d.pal.make, 0.04,
                0.08)


@draws("armature")
def _armature(d):
    c = d.pal.select
    _bones(d, [QPointF(0.5, 0.86), QPointF(0.5, 0.50), QPointF(0.5, 0.16)],
           shade(c, 1.4))
    _bones(d, [QPointF(0.5, 0.36), QPointF(0.20, 0.52)], shade(c, 1.4))
    _bones(d, [QPointF(0.5, 0.36), QPointF(0.80, 0.52)], shade(c, 1.4))


@draws("shape_keys")
def _shape_keys(d):
    d.ball(QPointF(0.30, 0.56), 0.20)
    blob = QPainterPath()
    blob.addEllipse(QPointF(0.72, 0.56), 0.16, 0.24)
    d.path(blob, _body_fill(d, 0.5, 0.3, 0.9, 0.8, d.pal.select))
    d.arrow(QPointF(0.42, 0.22), QPointF(0.66, 0.22), d.pal.make, 0.045,
            0.1)


def _brush(d, x, y, colour):
    d.p.save()
    d.p.translate(x, y)
    d.p.rotate(35)
    d.poly([QPointF(-0.04, -0.34), QPointF(0.04, -0.34),
            QPointF(0.04, -0.06), QPointF(-0.04, -0.06)],
           QColor("#a8764a"), width=0.03)
    d.poly([QPointF(-0.06, -0.06), QPointF(0.06, -0.06),
            QPointF(0.05, 0.06), QPointF(0.0, 0.12),
            QPointF(-0.05, 0.06)], colour, width=0.03)
    d.p.restore()


@draws("paint", "vertex_paint")
def _paint(d):
    d.ball(QPointF(0.40, 0.60), 0.28)
    stroke = QPainterPath(QPointF(0.20, 0.66))
    stroke.cubicTo(QPointF(0.32, 0.50), QPointF(0.44, 0.74),
                   QPointF(0.58, 0.56))
    pen = QPen(d.pal.make, d.w(0.09))
    pen.setCapStyle(Qt.RoundCap)
    d.p.setPen(pen)
    d.p.setBrush(Qt.NoBrush)
    d.p.drawPath(stroke)
    _brush(d, 0.74, 0.36, d.pal.make)


@draws("weathering")
def _weathering(d):
    d.box(-0.8, -0.8, 0, 1.6, 1.6, 0.9)
    for x, y, r in ((0.40, 0.30, 0.05), (0.56, 0.36, 0.035),
                    (0.30, 0.62, 0.05), (0.66, 0.66, 0.06),
                    (0.48, 0.74, 0.03)):
        d.disc(QPointF(x, y), r, QColor(110, 80, 50, 170))


@draws("hair_cap")
def _hair_cap(d):
    d.ball(QPointF(0.5, 0.58), 0.30, QColor("#f0c8a8"))
    cap = QPainterPath()
    cap.moveTo(QPointF(0.18, 0.56))
    cap.cubicTo(QPointF(0.16, 0.10), QPointF(0.84, 0.10),
                QPointF(0.82, 0.56))
    cap.cubicTo(QPointF(0.70, 0.40), QPointF(0.30, 0.40),
                QPointF(0.18, 0.56))
    d.path(cap, _body_fill(d, 0.2, 0.1, 0.8, 0.6, QColor("#7a4b2a")))


@draws("hair_strands")
def _hair_strands(d):
    d.ball(QPointF(0.5, 0.36), 0.24, QColor("#f0c8a8"))
    for i in range(7):
        x = 0.24 + i * 0.087
        strand = QPainterPath(QPointF(x, 0.30))
        strand.cubicTo(QPointF(x - 0.08, 0.55), QPointF(x + 0.06, 0.70),
                       QPointF(x - 0.03, 0.92))
        d.path(strand, color=QColor("#7a4b2a"), width=0.04)


@draws("cloth")
def _cloth(d):
    d.cyl(0, 0, 0, 0.45, 0.9)
    cloth = QPainterPath(QPointF(0.12, 0.30))
    cloth.lineTo(QPointF(0.88, 0.30))
    for i in range(7, -1, -1):
        x = 0.12 + i * 0.76 / 7
        cloth.lineTo(QPointF(x, 0.84 if i % 2 else 0.74))
    cloth.closeSubpath()
    d.path(cloth, _body_fill(d, 0.1, 0.3, 0.9, 0.8, d.pal.select))


# ================================================================= logic
@draws("for_loop")
def _for_loop(d):
    for i in range(3):
        d.box(-1.1 + i * 0.8, -0.3, 0, 0.5, 0.5, 0.5)
    d.arc_arrow(QPointF(0.5, 0.26), 0.30, 0.12, 180, 360 + 150,
                d.pal.make, 0.05, 0.1)


@draws("while_loop")
def _while_loop(d):
    d.arc_arrow(QPointF(0.5, 0.52), 0.30, 0.30, -60, 250, d.pal.make,
                0.07, 0.15)
    d.text(0.5, 0.62, "?", 0.30, d.pal.edge)


@draws("if_else")
def _if_else(d):
    diamond = [QPointF(0.5, 0.10), QPointF(0.78, 0.38), QPointF(0.5, 0.66),
               QPointF(0.22, 0.38)]
    d.poly(diamond, shade(d.pal.body, 1.2))
    d.line(QPointF(0.22, 0.38), QPointF(0.14, 0.38), d.pal.edge, 0.04)
    d.line(QPointF(0.78, 0.38), QPointF(0.86, 0.38), d.pal.edge, 0.04)
    d.arrow(QPointF(0.14, 0.38), QPointF(0.14, 0.90), d.pal.make, 0.045,
            0.1)
    d.arrow(QPointF(0.86, 0.38), QPointF(0.86, 0.90), d.pal.select, 0.045,
            0.1)


@draws("pattern")
def _pattern(d):
    for i in range(3):
        for j in range(3):
            d.cyl(-0.9 + i * 0.9, -0.9 + j * 0.9, 0, 0.26,
                  0.5 if (i, j) != (0, 0) else 0.5,
                  d.pal.body if (i, j) == (0, 0) else
                  shade(d.pal.select, 1.5))


@draws("scatter")
def _scatter(d):
    d.box(-0.9, -0.9, 0, 1.8, 1.8, 0.3)
    for x, y in ((-0.5, -0.4), (0.3, -0.6), (0.5, 0.3), (-0.3, 0.4),
                 (0.0, -0.05)):
        d.cone(x, y, 0.3, 0.17, 0.55, d.pal.make)


@draws("let")
def _let(d):
    d.text(0.5, 0.66, "x=", 0.40, d.pal.make)


# ============================================================ edit, docs
@draws("edit_mesh")
def _edit_mesh(d):
    d.box(-0.7, -0.7, 0, 1.4, 1.4, 1.1)
    for q in [(-0.7, 0.7, 0), (0.7, 0.7, 0), (0.7, -0.7, 0), (-0.7, -0.7,
                                                                1.1),
              (0.7, -0.7, 1.1), (-0.7, 0.7, 1.1), (0.7, 0.7, 1.1)]:
        d.dot(d.P(*q), d.pal.edge, 0.04, d.pal.edge)
    d.dot(d.P(0.7, -0.7, 1.1), d.pal.make, 0.06, d.pal.make)
    d.arrow(d.P(0.7, -0.7, 1.1), QPointF(0.92, 0.10), d.pal.make, 0.04,
            0.09)


def _sheet(d, colour):
    d.poly([QPointF(0.12, 0.14), QPointF(0.88, 0.14), QPointF(0.88, 0.86),
            QPointF(0.12, 0.86)], colour)


@draws("blueprint")
def _blueprint(d):
    blue = QColor("#2563a8") if d.style == "SolidWorks" else \
        QColor("#3c6e9e")
    _sheet(d, blue)
    w = QColor("#e8f1fb")
    d.poly([QPointF(0.22, 0.26), QPointF(0.48, 0.26), QPointF(0.48, 0.52),
            QPointF(0.22, 0.52)], color=w, width=0.03)
    d.poly([QPointF(0.56, 0.26), QPointF(0.78, 0.26), QPointF(0.78, 0.52),
            QPointF(0.56, 0.52)], color=w, width=0.03)
    d.p.setPen(d.pen(w, 0.03))
    d.p.setBrush(Qt.NoBrush)
    d.p.drawEllipse(QPointF(0.67, 0.39), 0.06, 0.06)
    d.poly([QPointF(0.56, 0.64), QPointF(0.84, 0.64), QPointF(0.84, 0.80),
            QPointF(0.56, 0.80)], color=w, width=0.03)
    d.line(QPointF(0.22, 0.62), QPointF(0.48, 0.62), w, 0.025)


@draws("bom")
def _bom(d):
    _sheet(d, d.pal.paper)
    for i in range(4):
        y = 0.28 + i * 0.16
        d.text(0.24, y + 0.04, str(i + 1), 0.09, d.pal.make)
        d.line(QPointF(0.34, y), QPointF(0.78, y), d.pal.edge, 0.035)


@draws("pid")
def _pid(d):
    d.line(QPointF(0.08, 0.66), QPointF(0.92, 0.66), d.pal.sketch, 0.05)
    d.poly([QPointF(0.38, 0.56), QPointF(0.38, 0.76), QPointF(0.56, 0.56),
            QPointF(0.56, 0.76)], d.pal.paper, width=0.04)
    d.line(QPointF(0.47, 0.66), QPointF(0.47, 0.42), d.pal.edge, 0.035)
    d.p.setPen(d.pen(d.pal.edge, 0.04))
    d.p.setBrush(d.pal.paper)
    d.p.drawEllipse(QPointF(0.47, 0.28), 0.13, 0.13)
    d.text(0.47, 0.33, "PI", 0.10, d.pal.edge)
    d.p.setBrush(shade(d.pal.body, 1.1))
    d.p.drawEllipse(QPointF(0.18, 0.66), 0.10, 0.10)


# ============================================================== analysis
@draws("mass_properties")
def _mass(d):
    d.box(-0.7, -0.7, 0, 1.4, 1.4, 1.0)
    c = d.P(0, 0, 0.5)
    d.p.setPen(d.pen(d.pal.edge, 0.03))
    d.p.setBrush(d.pal.paper)
    d.p.drawEllipse(c, 0.10, 0.10)
    d.p.setBrush(d.pal.edge)
    d.p.drawPie(QRectF(c.x() - 0.10, c.y() - 0.10, 0.2, 0.2), 0, 90 * 16)
    d.p.drawPie(QRectF(c.x() - 0.10, c.y() - 0.10, 0.2, 0.2), 180 * 16,
                90 * 16)


@draws("print_check")
def _print_check(d):
    d.box(-0.6, -0.6, 0, 1.2, 1.2, 0.7)
    d.poly([QPointF(0.62, 0.06), QPointF(0.84, 0.06), QPointF(0.84, 0.22),
            QPointF(0.78, 0.30), QPointF(0.68, 0.30), QPointF(0.62, 0.22)],
           QColor("#9aa4ad"))
    d.line(QPointF(0.73, 0.30), QPointF(0.73, 0.38), d.pal.make, 0.05)
    tick = QPainterPath(QPointF(0.10, 0.20))
    tick.lineTo(QPointF(0.20, 0.30))
    tick.lineTo(QPointF(0.38, 0.10))
    d.path(tick, color=QColor("#2e9a46"), width=0.07)


@draws("interference")
def _interference(d):
    d.box(-0.9, -0.3, 0, 1.0, 1.0, 0.8)
    d.box(-0.2, -0.9, 0.3, 1.0, 1.0, 0.8, shade(d.pal.select, 1.5))
    d.poly([d.P(-0.2, -0.3, 0.8), d.P(0.1, -0.3, 0.8), d.P(0.1, 0.1, 0.8),
            d.P(-0.2, 0.1, 0.8)], d.pal.cut, width=0.03)


@draws("cut_through")
def _cut_through(d):
    d.box(-0.8, -0.8, 0, 1.6, 0.8, 1.1)
    d.faces([([(-0.8, 0.0, 0), (0.8, 0.0, 0), (0.8, 0.0, 1.1),
               (-0.8, 0.0, 1.1)], 1.0)], d.pal.cut)
    d.poly([d.P(-1.0, 0.0, -0.2), d.P(1.0, 0.0, -0.2), d.P(1.0, 0.0, 1.4),
            d.P(-1.0, 0.0, 1.4)], color=d.pal.select, width=0.03)

"""Painted CAD-style toolbar icons for the Fusion and SolidWorks
Interface Styles (toolbar_style.py).

The classic bars use Material Design glyphs. A CAD program's icons are
little shaded parts instead — a block rising out of its sketch for
Extrude, a block with one edge rounded for Fillet — and that is what
these are: original drawings in each program's visual language, never
copies of its artwork.

- **Fusion** — light steel-grey bodies with dark outlines, ORANGE for
  the geometry a tool makes and BLUE for what it acts on.
- **SolidWorks** — YELLOW shaded solids with dark outlines, BLUE sketch
  profiles and arrows, red for what is cut away.

Everything is drawn in a unit square (`D`, with an isometric projection
`D.P(x, y, z)`) and rendered at several pixel sizes into a QIcon, so it
stays sharp on a Retina screen. `icon(key, style)` returns None for a
key nobody drew; `toolbar_style` then recolours the classic glyph in the
style's ink (`glyph_color`). The drawings for deform, character, logic,
documents and analysis tools live in icons_cad_more.py.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import (QBrush, QColor, QFont, QIcon, QLinearGradient,
                         QPainter, QPainterPath, QPen, QPicture, QPixmap,
                         QPolygonF,
                         QRadialGradient)

SIZES = (16, 20, 22, 24, 28, 32, 40, 48, 64)


class Palette:
    def __init__(self, body, edge, make, select, cut, sketch, paper,
                 folder, disk, ink):
        self.body = QColor(body)        # the part
        self.edge = QColor(edge)        # outlines
        self.make = QColor(make)        # what the tool makes / arrows
        self.select = QColor(select)    # what it acts on
        self.cut = QColor(cut)          # what is cut away
        self.sketch = QColor(sketch)    # sketch lines and profiles
        self.paper = QColor(paper)
        self.folder = QColor(folder)
        self.disk = QColor(disk)
        self.ink = QColor(ink)          # recoloured glyphs


PALETTES = {
    "Fusion": Palette(body="#c9d2db", edge="#45525e", make="#f08a24",
                      select="#0696d7", cut="#e2483d", sketch="#2f80c7",
                      paper="#ffffff", folder="#9fb1c2", disk="#5d6f80",
                      ink="#4e5d6b"),
    "SolidWorks": Palette(body="#f5c33b", edge="#505050", make="#2c62d0",
                          select="#18a6dc", cut="#d33a2c", sketch="#2c62d0",
                          paper="#ffffff", folder="#f2c14e",
                          disk="#2f63b8", ink="#3f4a57"),
}


def shade(color, k):
    """*color* lighter (k > 1) or darker (k < 1)."""
    return color.lighter(int(100 * k)) if k >= 1 else \
        color.darker(int(100 / k))


def _hull(points):
    pts = sorted(set((round(p.x(), 5), round(p.y(), 5)) for p in points))
    if len(pts) < 3:
        return [QPointF(*p) for p in pts]

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return [QPointF(*p) for p in lower[:-1] + upper[:-1]]


class D:
    """One icon being drawn: unit square, isometric helpers."""

    def __init__(self, painter, pal, size, style):
        self.p = painter
        self.pal = pal
        self.size = size
        self.style = style
        self.k = 0.27                   # iso scale
        self.cx, self.cy = 0.5, 0.56     # where (0, 0, 0) lands

    # ------------------------------------------------------ geometry
    def P(self, x, y, z=0.0):
        return QPointF(self.cx + (x - y) * 0.866 * self.k,
                       self.cy + ((x + y) * 0.5 - z) * self.k)

    def w(self, units):
        """A pen width in units, never thinner than a pixel."""
        return max(units, 0.9 / self.size)

    def pen(self, color=None, width=0.045, dash=None):
        pen = QPen(color if color is not None else self.pal.edge,
                   self.w(width))
        pen.setJoinStyle(Qt.RoundJoin)
        pen.setCapStyle(Qt.RoundCap)
        if dash:
            pen.setDashPattern(dash)
        return pen

    # ------------------------------------------------------- drawing
    def poly(self, pts, fill=None, edge=True, width=0.045, color=None):
        self.p.setPen(self.pen(color, width) if edge else Qt.NoPen)
        self.p.setBrush(fill if fill is not None else Qt.NoBrush)
        self.p.drawPolygon(QPolygonF(list(pts)))

    def line(self, a, b, color=None, width=0.045, dash=None):
        self.p.setPen(self.pen(color, width, dash))
        self.p.drawLine(a, b)

    def path(self, path, fill=None, color=None, width=0.045, dash=None):
        self.p.setPen(self.pen(color, width, dash) if width else Qt.NoPen)
        self.p.setBrush(fill if fill is not None else Qt.NoBrush)
        self.p.drawPath(path)

    def dot(self, pt, color=None, r=0.045, fill=None):
        self.p.setPen(self.pen(color or self.pal.edge, 0.03))
        self.p.setBrush(fill if fill is not None else self.pal.paper)
        self.p.drawRect(QRectF(pt.x() - r, pt.y() - r, 2 * r, 2 * r))

    def disc(self, pt, r, color):
        self.p.setPen(Qt.NoPen)
        self.p.setBrush(color)
        self.p.drawEllipse(pt, r, r)

    def arrow(self, a, b, color=None, width=0.07, head=0.15):
        color = color or self.pal.make
        dx, dy = b.x() - a.x(), b.y() - a.y()
        n = math.hypot(dx, dy) or 1.0
        ux, uy = dx / n, dy / n
        base = QPointF(b.x() - ux * head, b.y() - uy * head)
        self.line(a, base, color, width)
        wing = head * 0.62
        self.poly([b, QPointF(base.x() - uy * wing, base.y() + ux * wing),
                   QPointF(base.x() + uy * wing, base.y() - ux * wing)],
                  fill=color, color=shade(color, 0.7), width=0.02)

    def arc_arrow(self, c, rx, ry, a0, a1, color=None, width=0.065,
                  head=0.13):
        """An elliptical arc from angle a0 to a1 (degrees, screen y
        down) ending in an arrowhead."""
        color = color or self.pal.make
        steps = 24
        pts = [QPointF(c.x() + rx * math.cos(math.radians(a0 + (a1 - a0)
                                                         * i / steps)),
                       c.y() + ry * math.sin(math.radians(a0 + (a1 - a0)
                                                         * i / steps)))
               for i in range(steps + 1)]
        path = QPainterPath(pts[0])
        for q in pts[1:-3]:
            path.lineTo(q)
        self.path(path, color=color, width=width)
        self.arrow(pts[-4], pts[-1], color, width, head)

    def text(self, x, y, string, height, color=None, bold=True):
        """*string* with its baseline centre at (x, y), *height* units
        tall (drawn as outlines, so it scales with the icon)."""
        font = QFont()
        font.setPixelSize(100)
        font.setBold(bold)
        path = QPainterPath()
        path.addText(0, 0, font, string)
        r = path.boundingRect()
        k = height / max(r.height(), 1e-6)
        self.p.save()
        self.p.translate(x - r.width() * k / 2.0 - r.x() * k, y)
        self.p.scale(k, k)
        self.p.setPen(Qt.NoPen)
        self.p.setBrush(color or self.pal.edge)
        self.p.drawPath(path)
        self.p.restore()

    # -------------------------------------------------------- solids
    def faces(self, faces, body=None):
        body = body or self.pal.body
        for pts, k in faces:
            self.poly([self.P(*q) for q in pts], shade(body, k))

    def box(self, x, y, z, dx, dy, dz, body=None):
        """A block from (x, y, z) to (x+dx, y+dy, z+dz): top, +y (left,
        lit) and +x (right, shaded) faces."""
        X, Y, Z = x + dx, y + dy, z + dz
        self.faces([
            ([(x, Y, z), (X, Y, z), (X, Y, Z), (x, Y, Z)], 1.08),
            ([(X, y, z), (X, Y, z), (X, Y, Z), (X, y, Z)], 0.80),
            ([(x, y, Z), (X, y, Z), (X, Y, Z), (x, Y, Z)], 1.38)], body)

    def solid(self, bottom, top, body=None, top_k=1.4):
        """A convex solid between two outlines of 3D points (top may be
        one point — a cone): silhouette with a lit-from-the-left
        gradient, then the top face."""
        body = body or self.pal.body
        b = [self.P(*q) for q in bottom]
        t = [self.P(*q) for q in top]
        hull = _hull(b + t)
        xs = [q.x() for q in hull]
        g = QLinearGradient(QPointF(min(xs), 0), QPointF(max(xs), 0))
        g.setColorAt(0.0, shade(body, 1.0))
        g.setColorAt(0.3, shade(body, 1.3))
        g.setColorAt(0.8, shade(body, 0.85))
        g.setColorAt(1.0, shade(body, 0.68))
        self.poly(hull, QBrush(g))
        if len(t) > 2:
            self.poly(t, shade(body, top_k))

    def ring(self, x, y, z, r, n=28):
        return [(x + r * math.cos(2 * math.pi * i / n),
                 y + r * math.sin(2 * math.pi * i / n), z)
                for i in range(n)]

    def cyl(self, x, y, z, r, h, body=None):
        self.solid(self.ring(x, y, z, r), self.ring(x, y, z + h, r), body)

    def cone(self, x, y, z, r, h, body=None):
        self.solid(self.ring(x, y, z, r), [(x, y, z + h)], body)

    def ball(self, c, r, body=None):
        body = body or self.pal.body
        g = QRadialGradient(QPointF(c.x() - r * 0.4, c.y() - r * 0.4),
                            r * 1.4)
        g.setColorAt(0.0, shade(body, 1.7))
        g.setColorAt(0.45, shade(body, 1.1))
        g.setColorAt(1.0, shade(body, 0.62))
        self.p.setPen(self.pen())
        self.p.setBrush(QBrush(g))
        self.p.drawEllipse(c, r, r)

    def ground(self, pts2d, color=None, z=0.0, width=0.06, fill=None,
               dots=False):
        """A sketch outline lying on the plane z (iso)."""
        color = color or self.pal.sketch
        pts = [self.P(x, y, z) for x, y in pts2d]
        self.poly(pts, fill, color=color, width=width)
        if dots:
            for q in pts:
                self.dot(q, color, 0.035)


#: key -> drawing function(d); filled by @draws here and in
#: icons_cad_more
DRAW = {}


def draws(*keys):
    def register(fn):
        for key in keys:
            DRAW[key] = fn
        return fn
    return register


# ================================================================ sketch
@draws("select")
def _select(d):
    pts = [(0.30, 0.12), (0.30, 0.80), (0.45, 0.66), (0.57, 0.90),
           (0.68, 0.85), (0.56, 0.62), (0.76, 0.62)]
    d.poly([QPointF(*q) for q in pts], d.pal.paper, width=0.055)


@draws("line")
def _line(d):
    a, b = QPointF(0.18, 0.80), QPointF(0.82, 0.22)
    d.line(a, b, d.pal.sketch, 0.075)
    d.dot(a, d.pal.edge, 0.06)
    d.dot(b, d.pal.edge, 0.06)


@draws("rect")
def _rect(d):
    pts = [QPointF(0.16, 0.28), QPointF(0.84, 0.28), QPointF(0.84, 0.74),
           QPointF(0.16, 0.74)]
    d.poly(pts, color=d.pal.sketch, width=0.07)
    for q in pts:
        d.dot(q, d.pal.edge, 0.055)


@draws("circle")
def _circle(d):
    c = QPointF(0.5, 0.52)
    d.p.setPen(d.pen(d.pal.sketch, 0.07))
    d.p.setBrush(Qt.NoBrush)
    d.p.drawEllipse(c, 0.34, 0.34)
    d.line(c, QPointF(0.74, 0.28), d.pal.edge, 0.035, [2, 2])
    d.dot(c, d.pal.edge, 0.05)
    d.dot(QPointF(0.74, 0.28), d.pal.edge, 0.05)


@draws("polygon")
def _polygon(d):
    pts = [QPointF(0.5 + 0.36 * math.cos(math.radians(90 + 60 * i)),
                   0.52 - 0.36 * math.sin(math.radians(90 + 60 * i)))
           for i in range(6)]
    d.poly(pts, color=d.pal.sketch, width=0.07)
    for q in pts:
        d.dot(q, d.pal.edge, 0.05)


@draws("text")
def _text(d):
    d.text(0.5, 0.70, "A", 0.56, d.pal.edge)
    d.line(QPointF(0.14, 0.82), QPointF(0.86, 0.82), d.pal.sketch, 0.06)


@draws("measure")
def _measure(d):
    d.p.save()
    d.p.translate(0.5, 0.5)
    d.p.rotate(-35)
    body = d.pal.body if d.style == "SolidWorks" else QColor("#e8edf2")
    d.poly([QPointF(-0.42, -0.12), QPointF(0.42, -0.12),
            QPointF(0.42, 0.12), QPointF(-0.42, 0.12)], body)
    for i in range(9):
        x = -0.36 + i * 0.09
        d.line(QPointF(x, -0.12), QPointF(x, -0.12 + (0.11 if i % 2
                                                      else 0.17)),
               d.pal.edge, 0.03)
    d.p.restore()
    d.arrow(QPointF(0.30, 0.86), QPointF(0.86, 0.86), d.pal.select,
            0.05, 0.12)


@draws("dimension")
def _dimension(d):
    d.line(QPointF(0.16, 0.30), QPointF(0.16, 0.86), d.pal.edge, 0.035)
    d.line(QPointF(0.84, 0.30), QPointF(0.84, 0.86), d.pal.edge, 0.035)
    d.arrow(QPointF(0.5, 0.64), QPointF(0.18, 0.64), d.pal.sketch, 0.04,
            0.12)
    d.arrow(QPointF(0.5, 0.64), QPointF(0.82, 0.64), d.pal.sketch, 0.04,
            0.12)
    d.text(0.5, 0.52, "10", 0.28, d.pal.edge)


# ================================================================== file
@draws("new")
def _new(d):
    sheet = [QPointF(0.22, 0.10), QPointF(0.62, 0.10), QPointF(0.80, 0.28),
             QPointF(0.80, 0.90), QPointF(0.22, 0.90)]
    d.poly(sheet, d.pal.paper)
    d.poly([QPointF(0.62, 0.10), QPointF(0.62, 0.28), QPointF(0.80, 0.28)],
           shade(d.pal.paper, 0.85))
    star = QPainterPath()
    for i in range(10):
        r = 0.17 if i % 2 == 0 else 0.07
        a = math.radians(-90 + 36 * i)
        q = QPointF(0.30 + r * math.cos(a), 0.30 + r * math.sin(a))
        star.moveTo(q) if i == 0 else star.lineTo(q)
    star.closeSubpath()
    d.path(star, QColor("#f7b500"), shade(QColor("#f7b500"), 0.7), 0.025)


@draws("open")
def _open(d):
    f = d.pal.folder
    d.poly([QPointF(0.10, 0.22), QPointF(0.38, 0.22), QPointF(0.46, 0.32),
            QPointF(0.86, 0.32), QPointF(0.86, 0.82), QPointF(0.10, 0.82)],
           shade(f, 0.85))
    d.poly([QPointF(0.20, 0.44), QPointF(0.96, 0.44), QPointF(0.86, 0.82),
            QPointF(0.10, 0.82)], shade(f, 1.15))


@draws("save")
def _save(d):
    c = d.pal.disk
    d.poly([QPointF(0.14, 0.12), QPointF(0.76, 0.12), QPointF(0.88, 0.24),
            QPointF(0.88, 0.88), QPointF(0.14, 0.88)], c,
           color=shade(c, 0.6))
    d.poly([QPointF(0.28, 0.12), QPointF(0.70, 0.12), QPointF(0.70, 0.38),
            QPointF(0.28, 0.38)], QColor("#e6e9ec"), color=shade(c, 0.6),
           width=0.03)
    d.poly([QPointF(0.26, 0.56), QPointF(0.76, 0.56), QPointF(0.76, 0.88),
            QPointF(0.26, 0.88)], QColor("#ffffff"), color=shade(c, 0.6),
           width=0.03)


def _hook(d):
    """A redo arrow: a hook coming down from the left, curling over and
    pointing right."""
    color = d.pal.make if d.style == "SolidWorks" else d.pal.ink
    path = QPainterPath(QPointF(0.22, 0.82))
    path.cubicTo(QPointF(0.10, 0.40), QPointF(0.50, 0.22),
                 QPointF(0.70, 0.36))
    d.path(path, color=color, width=0.10)
    d.poly([QPointF(0.88, 0.48), QPointF(0.58, 0.52), QPointF(0.78, 0.20)],
           color, color=shade(color, 0.7), width=0.02)


@draws("undo")
def _undo(d):
    d.p.save()
    d.p.translate(1, 0)
    d.p.scale(-1, 1)
    _hook(d)
    d.p.restore()


@draws("redo")
def _redo(d):
    _hook(d)


@draws("vibe_model")
def _vibe(d):
    for cx, cy, r in ((0.42, 0.55, 0.30), (0.78, 0.22, 0.14),
                      (0.80, 0.78, 0.10)):
        star = QPainterPath()
        for i in range(8):
            rr = r if i % 2 == 0 else r * 0.28
            a = math.radians(-90 + 45 * i)
            q = QPointF(cx + rr * math.cos(a), cy + rr * math.sin(a))
            star.moveTo(q) if i == 0 else star.lineTo(q)
        star.closeSubpath()
        d.path(star, QColor("#f08a24"), shade(QColor("#f08a24"), 0.7),
               0.02)


# ======================================================= 3D solids (bar)
def _solid_icon(kind):
    def draw(d):
        from . import icons_solid
        d.p.save()
        d.p.scale(1.0 / d.size, 1.0 / d.size)        # pixels again
        icons_solid.paint(d.p, kind, d.size, d.pal.body, d.pal.edge)
        d.p.restore()
    return draw


for _kind in ("cube", "sphere", "cylinder", "capsule", "ellipsoid",
              "rounded_box", "loft", "cone"):
    DRAW[_kind] = _solid_icon(_kind)


# =============================================================== extrude
@draws("linear_extrude")
def _extrude(d):
    d.ground([(-0.9, -0.6), (0.7, -0.6), (0.7, 0.8), (-0.9, 0.8)],
             fill=shade(d.pal.sketch, 1.6))
    d.box(-0.6, -0.4, 0, 1.0, 1.0, 0.75)
    d.arrow(d.P(0.4, 0.6, 0.75), d.P(0.4, 0.6, 1.95), d.pal.make, 0.075)


@draws("rotate_extrude")
def _revolve(d):
    d.cyl(0, 0, -0.1, 0.85, 0.8)
    d.cyl(0, 0, -0.1, 0.35, 0.82, shade(d.pal.body, 0.7))
    d.line(d.P(0, 0, -0.6), d.P(0, 0, 1.4), d.pal.edge, 0.035, [3, 2])
    d.arc_arrow(d.P(0, 0, 1.15), 0.34, 0.12, 200, 520, d.pal.make, 0.06)


@draws("sweep")
def _sweep(d):
    pts = [(-1.1, 0.4, 0.0), (-0.4, 0.4, 0.1), (0.2, -0.1, 0.5),
           (0.6, -0.7, 1.2)]
    path = QPainterPath(d.P(*pts[0]))
    path.cubicTo(d.P(*pts[1]), d.P(*pts[2]), d.P(*pts[3]))
    tube = QPen(d.pal.edge, d.w(0.36))
    tube.setCapStyle(Qt.FlatCap)
    d.p.setPen(tube)
    d.p.setBrush(Qt.NoBrush)
    d.p.drawPath(path)
    tube.setColor(shade(d.pal.body, 1.05))
    tube.setWidthF(d.w(0.28))
    d.p.setPen(tube)
    d.p.drawPath(path)
    d.path(path, color=d.pal.make, width=0.035, dash=[3, 2])
    end = d.P(*pts[0])
    d.p.setPen(d.pen(d.pal.sketch, 0.06))
    d.p.setBrush(shade(d.pal.sketch, 1.7))
    d.p.drawEllipse(end, 0.08, 0.17)


@draws("section_loft")
def _loft(d):
    bottom = [(-0.75, -0.75, 0), (0.75, -0.75, 0), (0.75, 0.75, 0),
              (-0.75, 0.75, 0)]
    top = d.ring(0, 0, 1.3, 0.45)
    d.solid(bottom, top)
    d.ground([q[:2] for q in bottom], d.pal.sketch, 0, 0.06)
    d.p.setPen(d.pen(d.pal.sketch, 0.06))
    d.p.setBrush(Qt.NoBrush)
    d.p.drawPolygon(QPolygonF([d.P(*q) for q in top]))


# ============================================================= transform
def _block(d, x=-0.5, y=-0.5, z=0, s=1.0, body=None):
    d.box(x, y, z, s, s, s * 0.8, body)


@draws("translate")
def _move(d):
    _block(d, -0.55, -0.55, 0, 0.9)
    c = QPointF(0.70, 0.30)
    for dx, dy in ((0.2, 0), (-0.2, 0), (0, 0.2), (0, -0.2)):
        d.arrow(c, QPointF(c.x() + dx, c.y() + dy), d.pal.make, 0.05, 0.1)


@draws("rotate")
def _rotate(d):
    _block(d)
    d.arc_arrow(d.P(0, 0, 0.8), 0.40, 0.17, 160, 470, d.pal.make, 0.065)


@draws("scale")
def _scale(d):
    corners = [(x, y, z) for x in (-0.9, 0.9) for y in (-0.9, 0.9)
               for z in (0, 1.4)]
    for a in corners:
        for b in corners:
            if sum(1 for u, v in zip(a, b) if u != v) == 1 and a < b:
                d.line(d.P(*a), d.P(*b), d.pal.make, 0.035, [3, 2])
    d.box(-0.9, -0.9, 0, 0.8, 0.8, 0.62)
    d.arrow(d.P(-0.1, -0.1, 0.62), d.P(0.75, 0.75, 1.3), d.pal.make, 0.06)


@draws("mirror")
def _mirror(d):
    d.line(QPointF(0.5, 0.08), QPointF(0.5, 0.92), d.pal.select, 0.05,
           [3, 2])
    left = [QPointF(0.42, 0.25), QPointF(0.42, 0.80), QPointF(0.10, 0.80),
            QPointF(0.10, 0.55)]
    d.poly(left, shade(d.pal.body, 1.1))
    right = [QPointF(1 - q.x(), q.y()) for q in left]
    d.poly(right, d.pal.paper, color=d.pal.make, width=0.05)


@draws("resize")
def _resize(d):
    _block(d, -0.5, -0.5, 0, 1.0)
    d.arrow(d.P(-0.5, 0.75, 0), d.P(0.5, 0.75, 0), d.pal.make, 0.045, 0.11)
    d.arrow(d.P(0.5, 0.75, 0), d.P(-0.5, 0.75, 0), d.pal.make, 0.045, 0.11)
    d.arrow(d.P(0.75, 0.5, 0), d.P(0.75, 0.5, 0.8), d.pal.make, 0.045, 0.11)
    d.arrow(d.P(0.75, 0.5, 0.8), d.P(0.75, 0.5, 0), d.pal.make, 0.045, 0.11)


@draws("multmatrix")
def _matrix(d):
    d.faces([
        ([(-0.6, 0.6, 0), (0.6, 0.6, 0), (1.0, 0.6, 0.9), (-0.2, 0.6, 0.9)],
         1.08),
        ([(0.6, -0.6, 0), (0.6, 0.6, 0), (1.0, 0.6, 0.9), (1.0, -0.6, 0.9)],
         0.80),
        ([(-0.2, -0.6, 0.9), (1.0, -0.6, 0.9), (1.0, 0.6, 0.9),
          (-0.2, 0.6, 0.9)], 1.38)])
    d.text(0.24, 0.30, "[ ]", 0.22, d.pal.make)


# =============================================================== combine
@draws("union")
def _union(d):
    d.box(-0.9, -0.3, 0, 0.9, 0.9, 0.7)
    d.box(-0.1, -0.9, 0, 0.9, 0.9, 0.7)
    d.text(0.80, 0.30, "+", 0.30, d.pal.make)


@draws("difference")
def _difference(d):
    d.box(-0.8, -0.8, 0, 1.6, 1.6, 0.6)
    d.solid(d.ring(0, 0, 0.6, 0.45), d.ring(0, 0, 0.6, 0.45),
            shade(d.pal.body, 0.55), top_k=0.55)
    d.cyl(0.35, 0.35, 0.95, 0.4, 0.7, d.pal.cut)


@draws("intersection", "intersection_for")
def _intersection(d):
    d.p.setPen(d.pen(d.pal.edge, 0.04, [2, 2]))
    d.p.setBrush(Qt.NoBrush)
    d.p.drawEllipse(QPointF(0.38, 0.5), 0.27, 0.27)
    d.p.drawEllipse(QPointF(0.62, 0.5), 0.27, 0.27)
    lens = QPainterPath()
    a = QPainterPath()
    a.addEllipse(QPointF(0.38, 0.5), 0.27, 0.27)
    b = QPainterPath()
    b.addEllipse(QPointF(0.62, 0.5), 0.27, 0.27)
    lens = a.intersected(b)
    d.path(lens, d.pal.body, d.pal.edge, 0.05)


@draws("render")
def _render(d):
    _block(d, -0.6, -0.6, 0, 1.2)
    for t in (0.33, 0.66):
        d.line(d.P(-0.6 + 1.2 * t, -0.6, 0.96), d.P(-0.6 + 1.2 * t, 0.6,
                                                    0.96), d.pal.edge, 0.025)
        d.line(d.P(-0.6, -0.6 + 1.2 * t, 0.96), d.P(0.6, -0.6 + 1.2 * t,
                                                    0.96), d.pal.edge, 0.025)


# ================================================================ finish
def _rounded_block(d, r_edge, chamfer=False, color=None):
    """A block whose front-top edge (along y at x = X, z = Z) is
    rounded (or chamfered) by r, that edge picked out in *color*."""
    x, y, z, X, Y, Z = -0.7, -0.7, 0.0, 0.7, 0.7, 0.9
    r = r_edge
    if chamfer:
        arc = [(X - r, Z), (X, Z - r)]
    else:
        arc = [(X - r + r * math.sin(math.radians(a)),
                Z - r + r * math.cos(math.radians(a)))
               for a in range(0, 91, 15)]
    # +y side profile (lit), +x face, top face, then the round strip
    side = [(x, Y, z), (X, Y, z)] + [(px, Y, pz) for px, pz in
                                     reversed(arc)] + [(x, Y, Z)]
    d.faces([(side, 1.08)])
    d.faces([([(X, y, z), (X, Y, z), (X, Y, Z - r), (X, y, Z - r)],
              0.80)])
    d.faces([([(x, y, Z), (X - r, y, Z), (X - r, Y, Z), (x, Y, Z)], 1.38)])
    color = color or d.pal.select
    for (ax, az), (bx, bz) in zip(arc, arc[1:]):
        d.poly([d.P(ax, y, az), d.P(bx, y, bz), d.P(bx, Y, bz),
                d.P(ax, Y, az)], shade(color, 1.25), color=shade(color,
                                                                 0.7),
               width=0.02)


@draws("fillet")
def _fillet(d):
    _rounded_block(d, 0.45)


@draws("bevel")
def _bevel(d):
    _rounded_block(d, 0.45, chamfer=True)


@draws("push_pull")
def _push_pull(d):
    d.box(-0.8, -0.8, 0, 1.6, 1.6, 0.5)
    d.box(-0.4, -0.4, 0.5, 0.8, 0.8, 0.5, shade(d.pal.select, 1.4))
    d.arrow(d.P(0, 0, 1.0), d.P(0, 0, 1.9), d.pal.make, 0.07)


@draws("bisect")
def _bisect(d):
    d.box(-0.7, -0.7, 0, 1.4, 1.4, 0.45)
    d.box(-0.7, -0.7, 0.75, 1.4, 1.4, 0.45)
    d.poly([d.P(-0.95, -0.95, 0.6), d.P(0.95, -0.95, 0.6),
            d.P(0.95, 0.95, 0.6), d.P(-0.95, 0.95, 0.6)], QColor(d.pal.select.red(),
                                         d.pal.select.green(),
                                         d.pal.select.blue(), 90),
           color=d.pal.select, width=0.03)


@draws("hull")
def _hull_icon(d):
    a, b = QPointF(0.30, 0.62), QPointF(0.70, 0.36)
    hull = QPainterPath()
    hull.addEllipse(a, 0.18, 0.18)
    hull.addEllipse(b, 0.13, 0.13)
    band = QPainterPath()
    band.moveTo(QPointF(0.30 - 0.06, 0.62 - 0.17))
    band.lineTo(QPointF(0.70 - 0.045, 0.36 - 0.125))
    band.lineTo(QPointF(0.70 + 0.065, 0.36 + 0.11))
    band.lineTo(QPointF(0.30 + 0.09, 0.62 + 0.155))
    band.closeSubpath()
    shape = hull.united(band)
    d.path(shape, d.pal.body, d.pal.make, 0.05)
    d.disc(a, 0.05, d.pal.edge)
    d.disc(b, 0.04, d.pal.edge)


@draws("minkowski")
def _minkowski(d):
    rect = QPainterPath()
    rect.addRoundedRect(QRectF(0.12, 0.30, 0.56, 0.50), 0.12, 0.12)
    g = QLinearGradient(QPointF(0.12, 0.3), QPointF(0.68, 0.8))
    g.setColorAt(0, shade(d.pal.body, 1.35))
    g.setColorAt(1, shade(d.pal.body, 0.8))
    d.path(rect, QBrush(g))
    d.ball(QPointF(0.76, 0.28), 0.14, d.pal.select)


# ============================================================= assembly
@draws("snap_objects")
def _snap(d):
    d.box(-0.9, -0.2, 0, 0.8, 0.8, 0.5)
    d.box(0.1, -0.9, 0.9, 0.8, 0.8, 0.5, shade(d.pal.select, 1.5))
    d.arrow(d.P(0.5, -0.5, 0.9), d.P(-0.4, 0.2, 0.55), d.pal.make, 0.05,
            0.12)


# house_builder and the other builders: icons_cad_build.py


# ================================================================ render
def _blank_pixmap(size):
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    return pix


_CACHE = {}


#: how much of the square a drawing fills, and how far the fit may
#: grow or shrink it (a hand-placed drawing is near enough already)
FILL = 0.90
FIT_RANGE = (0.8, 1.45)


def _fit(key, size, style):
    """(scale, dx, dy) putting the drawing's ink in the middle of the
    square, FILL of it — measured once per key and style."""
    got = _FIT.get((key, style))
    if got is None:
        pic = QPicture()
        p = QPainter(pic)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.scale(1000, 1000)
        DRAW[key](D(p, PALETTES[style], 48, style))
        p.end()
        r = pic.boundingRect()
        if r.isEmpty():
            got = (1.0, 0.0, 0.0)
        else:
            x, y = r.x() / 1000.0, r.y() / 1000.0
            w, h = r.width() / 1000.0, r.height() / 1000.0
            k = min(FILL / max(w, 1e-6), FILL / max(h, 1e-6))
            k = min(max(k, FIT_RANGE[0]), FIT_RANGE[1])
            got = (k, 0.5 - (x + w / 2.0) * k, 0.5 - (y + h / 2.0) * k)
        _FIT[(key, style)] = got
    return got


_FIT = {}


def pixmap(key, size, style):
    pix = _blank_pixmap(size)
    k, dx, dy = _fit(key, size, style)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.scale(size, size)
    p.translate(dx, dy)
    p.scale(k, k)
    DRAW[key](D(p, PALETTES[style], size * k, style))
    p.end()
    return pix


def icon(key, style):
    """The painted *style* icon for toolbar *key*, or None."""
    from . import icons_cad_more, icons_cad_build, icons_cad_sketch  # noqa
    if style not in PALETTES or key not in DRAW:
        return None
    got = _CACHE.get((key, style))
    if got is None:
        got = QIcon()
        for size in SIZES:
            got.addPixmap(pixmap(key, size, style))
        _CACHE[(key, style)] = got
    return got


def glyph_color(style, family=None):
    """The ink a glyph nobody painted is recoloured in."""
    pal = PALETTES[style]
    if family in ("brand", "build"):
        return QColor("#f08a24").name()
    return pal.ink.name()

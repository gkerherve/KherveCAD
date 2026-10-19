"""Painted CAD-style icons for the builder windows (the ribbon's BUILD
tab): house, city, human, car, Lego, crystal, compound, chemistry.
Same unit square, palettes and iso helpers as icons_cad.py — little
shaded models in the Fusion / SolidWorks look, original drawings.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from PyQt5.QtCore import QPointF, QRectF
from PyQt5.QtGui import QBrush, QColor, QLinearGradient, QPainterPath

from .icons_cad import draws, shade

WALL = QColor("#e8dcc4")
ROOF = QColor("#c4553b")
GLASS = QColor("#8cc8ec")


def _gable(d, x, y, dx, dy, h, ridge, wall=WALL, roof=ROOF):
    """A house block with a gable roof along x."""
    d.box(x, y, 0, dx, dy, h, wall)
    X, Y, m = x + dx, y + dy, y + dy / 2.0
    d.faces([([(x, Y, h), (X, Y, h), (X, m, h + ridge),
               (x, m, h + ridge)], 1.15),
             ([(X, y, h), (X, Y, h), (X, m, h + ridge)], 0.85)], roof)
    d.faces([([(x - 0.02, y, h), (X, y, h), (X, m, h + ridge),
               (x - 0.02, m, h + ridge)], 1.35)], roof)


def _window(d, x, y0, y1, z0, z1):
    """A window on the +x face."""
    d.poly([d.P(x, y0, z0), d.P(x, y1, z0), d.P(x, y1, z1),
            d.P(x, y0, z1)], GLASS, width=0.025)


@draws("house_builder")
def _house(d):
    _gable(d, -0.8, -0.7, 1.6, 1.4, 0.8, 0.6)
    _window(d, 0.8, -0.5, -0.15, 0.35, 0.65)
    d.faces([([(0.8, 0.15, 0), (0.8, 0.45, 0), (0.8, 0.45, 0.55),
               (0.8, 0.15, 0.55)], 0.55)], QColor("#7a5230"))
    d.box(-0.5, 0.15, 1.0, 0.22, 0.22, 0.55, QColor("#9a5a44"))


@draws("city_builder")
def _city(d):
    tower = QColor("#b9c7d3")
    d.box(-0.9, 0.1, 0, 0.6, 0.6, 1.9, tower)
    for z in (0.4, 0.8, 1.2, 1.6):
        d.line(d.P(-0.3, 0.15, z), d.P(-0.3, 0.65, z), GLASS, 0.035)
    d.box(0.05, 0.2, 0, 0.55, 0.55, 1.2, shade(tower, 0.95))
    for z in (0.35, 0.7, 1.0):
        d.line(d.P(0.6, 0.25, z), d.P(0.6, 0.7, z), GLASS, 0.035)
    _gable(d, -0.2, -0.9, 0.8, 0.7, 0.45, 0.35)


@draws("human_builder")
def _human(d):
    skin = QColor("#e8b894")
    shirt = d.pal.select if d.style == "Fusion" else QColor("#2c62d0")
    legs = QColor("#46546a")
    for x in (0.42, 0.58):
        d.line(QPointF(x, 0.62), QPointF(x, 0.93), d.pal.edge, 0.12)
        d.line(QPointF(x, 0.62), QPointF(x, 0.92), legs, 0.075)
    for a, b in (((0.34, 0.38), (0.22, 0.62)), ((0.66, 0.38), (0.78, 0.62))):
        d.line(QPointF(*a), QPointF(*b), d.pal.edge, 0.11)
        d.line(QPointF(*a), QPointF(*b), shade(shirt, 1.2), 0.065)
    body = QPainterPath()
    body.addRoundedRect(QRectF(0.33, 0.31, 0.34, 0.36), 0.09, 0.09)
    g = QLinearGradient(QPointF(0.33, 0), QPointF(0.67, 0))
    g.setColorAt(0, shade(shirt, 1.35))
    g.setColorAt(1, shade(shirt, 0.8))
    d.path(body, QBrush(g))
    d.ball(QPointF(0.5, 0.17), 0.115, skin)


@draws("car_builder")
def _car(d):
    paint = QColor("#d8342c")
    body = QPainterPath(QPointF(0.06, 0.66))
    body.lineTo(0.08, 0.52)
    body.quadTo(0.14, 0.46, 0.28, 0.45)
    body.lineTo(0.38, 0.30)
    body.quadTo(0.42, 0.27, 0.50, 0.27)
    body.lineTo(0.66, 0.27)
    body.quadTo(0.72, 0.28, 0.78, 0.45)
    body.quadTo(0.93, 0.47, 0.95, 0.55)
    body.lineTo(0.95, 0.66)
    body.closeSubpath()
    g = QLinearGradient(QPointF(0, 0.27), QPointF(0, 0.66))
    g.setColorAt(0, shade(paint, 1.35))
    g.setColorAt(0.55, paint)
    g.setColorAt(1, shade(paint, 0.65))
    d.path(body, QBrush(g))
    glass = QPainterPath(QPointF(0.33, 0.44))
    glass.lineTo(0.41, 0.32)
    glass.lineTo(0.55, 0.32)
    glass.lineTo(0.55, 0.44)
    glass.closeSubpath()
    glass.moveTo(0.59, 0.44)
    glass.lineTo(0.59, 0.32)
    glass.lineTo(0.66, 0.32)
    glass.lineTo(0.72, 0.44)
    glass.closeSubpath()
    d.path(glass, GLASS, width=0.02)
    for x in (0.26, 0.76):
        d.ball(QPointF(x, 0.66), 0.105, QColor("#3a3f45"))
        d.disc(QPointF(x, 0.66), 0.045, QColor("#c9d0d6"))


@draws("lego_builder")
def _lego(d):
    def brick(x, y, z, nx, ny, colour):
        d.box(x, y, z, nx * 0.5, ny * 0.5, 0.6, colour)
        for i in range(nx):
            for j in range(ny):
                d.cyl(x + 0.25 + 0.5 * i, y + 0.25 + 0.5 * j, z + 0.6,
                      0.15, 0.14, colour)
    brick(-0.9, -0.5, 0, 4, 2, QColor("#2f6fd0"))
    brick(-0.4, -0.5, 0.6, 2, 2, QColor("#e3312b"))


@draws("crystal_builder")
def _crystal(d):
    s = 0.75
    corners = [(x, y, z) for x in (-s, s) for y in (-s, s)
               for z in (0, 2 * s)]
    back = [(-s, -s, 0), (-s, -s, 2 * s), (-s, s, 0), (s, -s, 0)]
    for a in back:              # the hidden edges first, thin
        for b in corners:
            if sum(p != q for p, q in zip(a, b)) == 1:
                d.line(d.P(*a), d.P(*b), shade(d.pal.edge, 1.6), 0.02)
    for a in corners:
        for b in corners:
            if a < b and sum(p != q for p, q in zip(a, b)) == 1 and \
                    a not in back[:1]:
                d.line(d.P(*a), d.P(*b), d.pal.edge, 0.035)
    atom = d.pal.make
    for c in corners:
        if c != (-s, -s, 0):
            d.ball(d.P(*c), 0.075, atom)
    d.ball(d.P(0, 0, s), 0.12, d.pal.select)


@draws("compound_builder")
def _compound(d):
    o = QPointF(0.5, 0.55)
    hs = [QPointF(0.5 + 0.34 * math.cos(math.radians(a)),
                  0.55 + 0.34 * math.sin(math.radians(a)))
          for a in (-90, 30, 150)]
    for h in hs:
        d.line(o, h, d.pal.edge, 0.09)
        d.line(o, h, QColor("#d9dde2"), 0.05)
    d.ball(o, 0.19, QColor("#3c3f44"))
    for h, colour in zip(hs, ("#e5322d", "#f2f4f6", "#2f80c7")):
        d.ball(h, 0.12, QColor(colour))


@draws("chemistry_builder")
def _chemistry(d):
    glass = QColor("#e6f2fa")
    liquid = QColor("#2fb37a") if d.style == "Fusion" else \
        QColor("#2c62d0")
    flask = QPainterPath(QPointF(0.42, 0.10))
    flask.lineTo(0.58, 0.10)
    flask.lineTo(0.58, 0.38)
    flask.lineTo(0.84, 0.84)
    flask.quadTo(0.86, 0.92, 0.78, 0.92)
    flask.lineTo(0.22, 0.92)
    flask.quadTo(0.14, 0.92, 0.16, 0.84)
    flask.lineTo(0.42, 0.38)
    flask.closeSubpath()
    d.path(flask, glass)
    fill = QPainterPath(QPointF(0.29, 0.62))
    fill.lineTo(0.71, 0.62)
    fill.lineTo(0.82, 0.84)
    fill.quadTo(0.84, 0.89, 0.78, 0.89)
    fill.lineTo(0.22, 0.89)
    fill.quadTo(0.16, 0.89, 0.18, 0.84)
    fill.closeSubpath()
    g = QLinearGradient(QPointF(0.2, 0), QPointF(0.8, 0))
    g.setColorAt(0, shade(liquid, 1.3))
    g.setColorAt(1, shade(liquid, 0.8))
    d.path(fill, QBrush(g), width=0)
    d.path(flask, None, width=0.045)
    d.line(QPointF(0.38, 0.10), QPointF(0.62, 0.10), d.pal.edge, 0.06)
    for x, y, r in ((0.40, 0.76, 0.035), (0.55, 0.70, 0.025),
                    (0.62, 0.80, 0.03)):
        d.disc(QPointF(x, y), r, shade(liquid, 1.7))


# ============================================================ browser tabs
# the left panel's tabs (interface_windows.style_panel): Main, Object,
# Collections, Variables, Code — small parts and documents, not glyphs

@draws("tab_main")
def _tab_main(d):
    """Main: an assembly tree — a box at the root, two parts below."""
    d.line(QPointF(0.26, 0.30), QPointF(0.26, 0.82), d.pal.edge, 0.04)
    for y in (0.55, 0.78):
        d.line(QPointF(0.26, y), QPointF(0.50, y), d.pal.edge, 0.04)
    d.cx, d.cy, d.k = 0.26, 0.24, 0.17
    d.box(-0.6, -0.6, -0.4, 1.2, 1.2, 0.8)
    d.cx, d.cy = 0.68, 0.53
    d.box(-0.6, -0.6, -0.4, 1.2, 1.2, 0.8, shade(d.pal.select, 1.5))
    d.cx, d.cy = 0.68, 0.80
    d.cyl(0, 0, -0.4, 0.6, 0.8, shade(d.pal.make, 1.2))


@draws("tab_object")
def _tab_object(d):
    """Object: one part, a block with a bore."""
    d.box(-0.9, -0.9, 0, 1.8, 1.8, 0.9)
    pts = [d.P(0.45 * math.cos(a), 0.45 * math.sin(a), 0.9)
           for a in [2 * math.pi * i / 24 for i in range(24)]]
    d.poly(pts, shade(d.pal.body, 0.55), width=0.035)


@draws("tab_collections")
def _tab_collections(d):
    """Collections: three stacked folders of parts."""
    for i, colour in enumerate((d.pal.folder, shade(d.pal.folder, 1.15),
                                d.pal.select)):
        x, y = 0.14 + 0.08 * i, 0.22 + 0.13 * i
        tab = QPainterPath(QPointF(x, y + 0.08))
        tab.lineTo(x, y)
        tab.lineTo(x + 0.22, y)
        tab.lineTo(x + 0.28, y + 0.06)
        tab.lineTo(x + 0.62, y + 0.06)
        tab.lineTo(x + 0.62, y + 0.42)
        tab.lineTo(x, y + 0.42)
        tab.closeSubpath()
        d.path(tab, shade(colour, 1.1), width=0.035)


@draws("tab_variables")
def _tab_variables(d):
    """Variables: a slider sheet — two sliders and an x."""
    sheet = QPainterPath()
    sheet.addRoundedRect(QRectF(0.10, 0.14, 0.80, 0.72), 0.08, 0.08)
    d.path(sheet, d.pal.paper, width=0.04)
    for y, at in ((0.40, 0.66), (0.66, 0.38)):
        d.line(QPointF(0.22, y), QPointF(0.78, y), d.pal.body, 0.06)
        d.line(QPointF(0.22, y), QPointF(at, y), d.pal.select, 0.06)
        d.ball(QPointF(at, y), 0.065, d.pal.make)
    d.text(0.24, 0.30, "x", 0.12, d.pal.edge)


@draws("tab_code")
def _tab_code(d):
    """Code: a .scad page with braces and coloured lines."""
    page = QPainterPath(QPointF(0.20, 0.08))
    page.lineTo(0.64, 0.08)
    page.lineTo(0.82, 0.26)
    page.lineTo(0.82, 0.92)
    page.lineTo(0.20, 0.92)
    page.closeSubpath()
    d.path(page, d.pal.paper, width=0.04)
    d.poly([QPointF(0.64, 0.08), QPointF(0.64, 0.26),
            QPointF(0.82, 0.26)], shade(d.pal.body, 0.9), width=0.03)
    for y, w, c in ((0.38, 0.38, d.pal.select), (0.52, 0.28, d.pal.make),
                    (0.66, 0.42, d.pal.sketch), (0.80, 0.22, d.pal.edge)):
        d.line(QPointF(0.30 + (0.06 if 0.5 < y < 0.75 else 0), y),
               QPointF(0.30 + w, y), c, 0.055)

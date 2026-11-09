"""Painted CAD-style icons for the ribbon's LIBRARY tab: one small
drawing per subject of the Library menu (fasteners, tools, vacuum,
gears, a motor, a board, a printer, a sofa, a tree, a planet…). Same
unit square, palettes and iso helpers as icons_cad.py; original
drawings. Subjects that have a builder reuse its drawing.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from PyQt5.QtCore import QPointF, QRectF
from PyQt5.QtGui import QColor, QPainterPath

from .icons_cad import DRAW, draws, shade

STEEL = QColor("#b8c2cc")
DARK = QColor("#3c434b")
WOOD = QColor("#b98a55")
GREEN = QColor("#4f9d4a")
RED = QColor("#d8342c")
BLUE = QColor("#2f6fd0")
WHITE = QColor("#f4f5f6")


def _same(key, other):
    """*key* wears the drawing of *other* (a builder's)."""
    def draw(d):
        from . import icons_cad_build  # noqa: F401  (the builders')
        fn = DRAW.get(other) or DRAW["lib_generic"]
        fn(d)
    DRAW[key] = draw


def _rrect(x, y, w, h, r):
    p = QPainterPath()
    p.addRoundedRect(QRectF(x, y, w, h), r, r)
    return p


@draws("lib_generic")
def _generic(d):
    """A crate of parts."""
    d.box(-0.85, -0.85, 0, 1.7, 1.7, 0.75, d.pal.folder)
    d.box(-0.5, -0.5, 0.75, 0.6, 0.6, 0.5, d.pal.body)
    d.cyl(0.35, 0.3, 0.75, 0.28, 0.6, d.pal.select)


@draws("lib_fasteners")
def _fasteners(d):
    """A hex bolt standing on its thread."""
    d.cyl(0, 0, 0, 0.26, 1.25, STEEL)
    for z in (0.15, 0.35, 0.55, 0.75):
        d.line(d.P(-0.26, 0.05, z), d.P(0.05, 0.26, z + 0.08),
               shade(STEEL, 0.6), 0.03)
    d.solid(d.ring(0, 0, 1.25, 0.62, 6), d.ring(0, 0, 1.62, 0.62, 6),
            shade(STEEL, 1.05))


@draws("lib_tools")
def _tools(d):
    """A hammer."""
    d.line(QPointF(0.22, 0.88), QPointF(0.60, 0.36), d.pal.edge, 0.13)
    d.line(QPointF(0.22, 0.88), QPointF(0.60, 0.36), WOOD, 0.085)
    head = [QPointF(0.38, 0.30), QPointF(0.74, 0.12), QPointF(0.84, 0.30),
            QPointF(0.72, 0.36), QPointF(0.70, 0.46), QPointF(0.50, 0.50)]
    d.poly(head, STEEL)


@draws("lib_vacuum")
def _vacuum(d):
    """A CF flange on its tube."""
    d.cyl(0, 0, 0, 0.45, 0.9, STEEL)
    d.cyl(0, 0, 0.9, 0.95, 0.28, shade(STEEL, 1.05))
    for i in range(8):
        a = 2 * math.pi * i / 8
        d.disc(d.P(0.74 * math.cos(a), 0.74 * math.sin(a), 1.18), 0.03,
               DARK)
    d.poly([d.P(*q) for q in d.ring(0, 0, 1.18, 0.4)], DARK, width=0.02)


def _gear(d, c, r, teeth, colour):
    pts = []
    for i in range(teeth * 4):
        a = 2 * math.pi * i / (teeth * 4)
        k = r * (1.0 if i % 4 in (0, 1) else 0.78)
        pts.append(QPointF(c.x() + k * math.cos(a), c.y() + k * math.sin(a)))
    d.poly(pts, colour, width=0.03)
    d.disc(c, r * 0.25, d.pal.paper)


@draws("lib_mechanisms")
def _mechanisms(d):
    """Two gears in mesh."""
    _gear(d, QPointF(0.36, 0.60), 0.30, 10, d.pal.body)
    _gear(d, QPointF(0.72, 0.34), 0.20, 7, d.pal.make)


@draws("lib_motors")
def _motors(d):
    """A stepper motor."""
    d.box(-0.7, -0.7, 0, 1.4, 1.4, 1.1, DARK)
    d.box(-0.7, -0.7, 1.1, 1.4, 1.4, 0.12, STEEL)
    d.cyl(0, 0, 1.22, 0.4, 0.1, STEEL)
    d.cyl(0, 0, 1.3, 0.13, 0.6, shade(STEEL, 1.1))


@draws("lib_electronics")
def _electronics(d):
    """A circuit board with a chip."""
    d.box(-1.0, -0.75, 0, 2.0, 1.5, 0.1, QColor("#2e8b57"))
    d.box(-0.35, -0.3, 0.1, 0.8, 0.6, 0.16, DARK)
    for x in (-0.25, -0.05, 0.15, 0.35):
        d.line(d.P(x, 0.3, 0.12), d.P(x, 0.5, 0.12), STEEL, 0.035)
    d.cyl(-0.72, 0.38, 0.1, 0.13, 0.3, QColor("#2f6fd0"))
    d.box(0.6, -0.6, 0.1, 0.3, 0.45, 0.22, STEEL)


@draws("lib_aircon")
def _aircon(d):
    """An outdoor unit: a case with its fan."""
    d.box(-1.0, -0.45, 0, 2.0, 0.9, 1.3, WHITE)
    c = d.P(0, 0.45, 0.65)
    ring = [d.P(0.5 * math.cos(a), 0.45, 0.65 + 0.5 * math.sin(a))
            for a in [2 * math.pi * i / 24 for i in range(24)]]
    d.poly(ring, DARK, width=0.03)
    for i in range(3):
        a = 2 * math.pi * i / 3
        d.line(c, d.P(0.42 * math.cos(a), 0.45, 0.65 + 0.42 * math.sin(a)),
               STEEL, 0.06)


@draws("lib_printing")
def _printing(d):
    """A 3D printer from the front: frame, bed, nozzle and a print."""
    orange = QColor("#f08a24")
    d.path(_rrect(0.10, 0.80, 0.80, 0.10, 0.02), DARK)
    for x in (0.14, 0.78):
        d.path(_rrect(x, 0.12, 0.08, 0.70, 0.01), orange)
    d.path(_rrect(0.12, 0.10, 0.76, 0.09, 0.01), orange)
    d.path(_rrect(0.20, 0.36, 0.60, 0.05, 0.01), STEEL)
    d.path(_rrect(0.44, 0.30, 0.16, 0.16, 0.02), DARK)
    d.poly([QPointF(0.48, 0.46), QPointF(0.56, 0.46), QPointF(0.52, 0.53)],
           STEEL, width=0.02)
    d.path(_rrect(0.26, 0.74, 0.48, 0.05, 0.01), STEEL)
    d.path(_rrect(0.40, 0.56, 0.24, 0.18, 0.01), d.pal.select)


@draws("lib_home")
def _home(d):
    """A sofa."""
    cloth = QColor("#7fa3cc")
    d.box(-0.9, -0.1, 0.25, 1.8, 0.35, 0.85, shade(cloth, 0.9))
    d.box(-0.9, -0.6, 0.1, 1.8, 0.85, 0.42, cloth)
    d.box(-1.05, -0.6, 0.1, 0.2, 0.85, 0.7, shade(cloth, 0.85))
    d.box(0.85, -0.6, 0.1, 0.2, 0.85, 0.7, shade(cloth, 0.85))


@draws("lib_sport")
def _sport(d):
    """A football."""
    c = QPointF(0.5, 0.52)
    d.ball(c, 0.40, WHITE)
    pent = [QPointF(c.x() + 0.15 * math.cos(math.radians(-90 + 72 * i)),
                    c.y() + 0.15 * math.sin(math.radians(-90 + 72 * i)))
            for i in range(5)]
    d.poly(pent, DARK, width=0.02)
    for i in range(5):
        a = math.radians(-90 + 72 * i)
        p = QPointF(c.x() + 0.15 * math.cos(a), c.y() + 0.15 * math.sin(a))
        q = QPointF(c.x() + 0.34 * math.cos(a), c.y() + 0.34 * math.sin(a))
        d.line(p, q, DARK, 0.03)


@draws("lib_nature")
def _nature(d):
    """A tree."""
    d.cyl(0, 0, 0, 0.16, 0.6, WOOD)
    d.cone(0, 0, 0.5, 0.8, 0.9, GREEN)
    d.cone(0, 0, 1.0, 0.6, 0.8, shade(GREEN, 1.1))
    d.cone(0, 0, 1.45, 0.4, 0.7, shade(GREEN, 1.2))


@draws("lib_surfaces")
def _surfaces(d):
    """A slab of atom layers."""
    for z, colour in ((0.0, "#8a97a6"), (0.45, "#c98f3b"),
                      (0.9, "#8a97a6")):
        d.box(-0.9, -0.9, z, 1.8, 1.8, 0.2, QColor(colour))
    for x in (-0.55, 0, 0.55):
        for y in (-0.55, 0, 0.55):
            d.ball(d.P(x, y, 1.18), 0.055, QColor("#e5322d"))


@draws("lib_solar")
def _solar(d):
    """The Sun, an orbit and a planet."""
    orbit = QPainterPath()
    orbit.addEllipse(QPointF(0.5, 0.52), 0.42, 0.20)
    d.path(orbit, color=shade(d.pal.edge, 1.5), width=0.025)
    d.ball(QPointF(0.5, 0.52), 0.17, QColor("#f5b82e"))
    d.ball(QPointF(0.86, 0.42), 0.085, BLUE)
    d.ball(QPointF(0.20, 0.64), 0.05, RED)


@draws("lib_technic")
def _technic(d):
    """A Technic beam with its pin holes."""
    d.path(_rrect(0.06, 0.38, 0.88, 0.26, 0.13), RED)
    for i in range(4):
        d.disc(QPointF(0.19 + 0.207 * i, 0.51), 0.07, d.pal.edge)
        d.disc(QPointF(0.19 + 0.207 * i, 0.51), 0.045, d.pal.paper)


@draws("lib_animals")
def _animals(d):
    """A paw print."""
    brown = QColor("#8a5a3c")
    pad = QPainterPath()
    pad.addEllipse(QPointF(0.5, 0.66), 0.20, 0.16)
    d.path(pad, brown, width=0.02)
    for x, y in ((0.24, 0.42), (0.40, 0.28), (0.60, 0.28), (0.76, 0.42)):
        toe = QPainterPath()
        toe.addEllipse(QPointF(x, y), 0.075, 0.095)
        d.path(toe, brown, width=0.02)


@draws("lib_monsters")
def _monsters(d):
    """A ghost."""
    body = QPainterPath(QPointF(0.20, 0.88))
    body.lineTo(0.20, 0.46)
    body.cubicTo(0.20, 0.02, 0.80, 0.02, 0.80, 0.46)
    body.lineTo(0.80, 0.88)
    body.lineTo(0.70, 0.78)
    body.lineTo(0.60, 0.88)
    body.lineTo(0.50, 0.78)
    body.lineTo(0.40, 0.88)
    body.lineTo(0.30, 0.78)
    body.closeSubpath()
    d.path(body, QColor("#b9a6e0"))
    for x in (0.38, 0.62):
        d.disc(QPointF(x, 0.44), 0.075, WHITE)
        d.disc(QPointF(x + 0.015, 0.45), 0.035, DARK)


@draws("lib_minecraft")
def _minecraft(d):
    """A grass block."""
    d.box(-0.8, -0.8, 0, 1.6, 1.6, 1.2, QColor("#8b5a2b"))
    d.box(-0.8, -0.8, 1.2, 1.6, 1.6, 0.35, GREEN)


@draws("lib_generative")
def _generative(d):
    """Voronoi cells."""
    cells = [[(0.10, 0.20), (0.42, 0.12), (0.50, 0.42), (0.24, 0.52)],
             [(0.46, 0.12), (0.88, 0.18), (0.80, 0.50), (0.54, 0.42)],
             [(0.12, 0.56), (0.48, 0.48), (0.52, 0.86), (0.18, 0.88)],
             [(0.54, 0.48), (0.84, 0.54), (0.90, 0.86), (0.56, 0.88)]]
    tints = (d.pal.body, d.pal.select, d.pal.make, d.pal.body)
    for cell, tint in zip(cells, tints):
        d.poly([QPointF(x, y) for x, y in cell], tint, width=0.035)


@draws("lib_games")
def _games(d):
    """A die."""
    d.box(-0.8, -0.8, 0, 1.6, 1.6, 1.6, WHITE)
    for x, y in ((-0.4, -0.4), (0, 0), (0.4, 0.4)):
        d.disc(d.P(x, y, 1.6), 0.055, DARK)
    for y, z in ((-0.4, 1.15), (0.4, 0.45)):
        d.disc(d.P(0.8, y, z), 0.05, DARK)
    for x, z in ((-0.4, 1.15), (0, 0.8), (0.4, 0.45), (-0.4, 0.45),
                 (0.4, 1.15)):
        d.disc(d.P(x, 0.8, z), 0.05, DARK)


@draws("lib_vehicles")
def _vehicles(d):
    """A lorry."""
    d.path(_rrect(0.06, 0.26, 0.56, 0.40, 0.02), BLUE)
    cab = QPainterPath(QPointF(0.64, 0.66))
    cab.lineTo(0.64, 0.38)
    cab.lineTo(0.80, 0.38)
    cab.lineTo(0.94, 0.52)
    cab.lineTo(0.94, 0.66)
    cab.closeSubpath()
    d.path(cab, RED)
    d.poly([QPointF(0.70, 0.42), QPointF(0.79, 0.42), QPointF(0.88, 0.52),
            QPointF(0.70, 0.52)], QColor("#bfe0f2"), width=0.02)
    for x in (0.22, 0.48, 0.80):
        d.disc(QPointF(x, 0.70), 0.085, DARK)
        d.disc(QPointF(x, 0.70), 0.035, STEEL)


@draws("lib_cards")
def _cards(d):
    """Two playing cards."""
    d.p.save()
    d.p.translate(0.40, 0.54)
    d.p.rotate(-14)
    d.path(_rrect(-0.22, -0.32, 0.44, 0.64, 0.05), WHITE)
    d.p.restore()
    d.p.save()
    d.p.translate(0.60, 0.52)
    d.p.rotate(10)
    d.path(_rrect(-0.22, -0.32, 0.44, 0.64, 0.05), WHITE)
    d.poly([QPointF(0, -0.15), QPointF(0.11, 0), QPointF(0, 0.15),
            QPointF(-0.11, 0)], RED, edge=False)
    d.p.restore()


@draws("lib_kitchen")
def _kitchen(d):
    """A mug."""
    handle = QPainterPath()
    handle.addEllipse(QPointF(0.76, 0.54), 0.13, 0.16)
    d.path(handle, color=d.pal.edge, width=0.10)
    d.path(handle, color=WHITE, width=0.055)
    d.cyl(0, 0, 0, 0.75, 1.5, WHITE)
    d.poly([d.P(*q) for q in d.ring(0, 0, 1.5, 0.6)], QColor("#6b4226"),
           width=0.02)


@draws("lib_music")
def _music(d):
    """Two joined notes."""
    for x in (0.30, 0.70):
        d.line(QPointF(x + 0.085, 0.74), QPointF(x + 0.085, 0.22),
               DARK, 0.05)
        head = QPainterPath()
        head.addEllipse(QPointF(x, 0.76), 0.11, 0.085)
        d.path(head, DARK, width=0.02)
    d.poly([QPointF(0.36, 0.16), QPointF(0.81, 0.10), QPointF(0.81, 0.24),
            QPointF(0.36, 0.30)], DARK, edge=False)


@draws("lib_art")
def _art(d):
    """A painter's palette."""
    blob = QPainterPath()
    blob.addEllipse(QPointF(0.5, 0.52), 0.42, 0.34)
    d.path(blob, WOOD)
    d.disc(QPointF(0.66, 0.66), 0.07, d.pal.paper)
    for (x, y), colour in zip(((0.26, 0.48), (0.40, 0.32), (0.60, 0.30),
                               (0.76, 0.42)),
                              ("#d8342c", "#f5b82e", "#4f9d4a", "#2f6fd0")):
        d.disc(QPointF(x, y), 0.065, QColor(colour))


@draws("lib_custom")
def _custom(d):
    """A part and a plus: your own."""
    d.box(-0.8, -0.6, 0, 1.2, 1.2, 1.0, d.pal.body)
    c = QPointF(0.76, 0.26)
    d.disc(c, 0.17, d.pal.make)
    d.line(QPointF(c.x() - 0.09, c.y()), QPointF(c.x() + 0.09, c.y()),
           d.pal.paper, 0.05)
    d.line(QPointF(c.x(), c.y() - 0.09), QPointF(c.x(), c.y() + 0.09),
           d.pal.paper, 0.05)


@draws("lib_mine")
def _mine(d):
    """A shelf of your own parts."""
    d.box(-0.9, -0.3, 0, 1.8, 0.6, 0.1, WOOD)
    d.box(-0.9, -0.3, 0.1, 0.1, 0.6, 1.3, WOOD)
    d.box(0.8, -0.3, 0.1, 0.1, 0.6, 1.3, WOOD)
    for x, h, colour in ((-0.72, 1.0, RED), (-0.44, 1.15, BLUE),
                         (-0.16, 0.9, GREEN), (0.12, 1.1, d.pal.make),
                         (0.40, 0.95, d.pal.select)):
        d.box(x, -0.2, 0.1, 0.24, 0.4, h, QColor(colour))


@draws("lib_scad")
def _scad(d):
    """A book of code."""
    d.box(-0.75, -0.55, 0, 1.5, 1.1, 0.35, d.pal.disk)
    d.box(-0.7, -0.5, 0.05, 1.45, 1.0, 0.25, WHITE)
    d.text(0.5, 0.36, "{ }", 0.26, d.pal.paper)


@draws("lib_learn")
def _learn(d):
    """An open book."""
    left = [QPointF(0.50, 0.30), QPointF(0.10, 0.22), QPointF(0.10, 0.74),
            QPointF(0.50, 0.84)]
    right = [QPointF(0.50, 0.30), QPointF(0.90, 0.22), QPointF(0.90, 0.74),
             QPointF(0.50, 0.84)]
    d.poly(left, WHITE)
    d.poly(right, shade(WHITE, 0.92))
    for y in (0.40, 0.52, 0.64):
        d.line(QPointF(0.18, y - 0.02), QPointF(0.44, y + 0.04),
               d.pal.sketch, 0.03)
        d.line(QPointF(0.56, y + 0.04), QPointF(0.82, y - 0.02),
               d.pal.sketch, 0.03)


@draws("lib_showcase")
def _showcase(d):
    """A star."""
    pts = []
    for i in range(10):
        a = math.radians(-90 + 36 * i)
        r = 0.42 if i % 2 == 0 else 0.18
        pts.append(QPointF(0.5 + r * math.cos(a), 0.52 + r * math.sin(a)))
    d.poly(pts, QColor("#f5b82e"))


# the subjects that have a builder wear its drawing
for _key, _other in (("lib_city", "city_builder"),
                     ("lib_chemistry", "chemistry_builder"),
                     ("lib_crystals", "crystal_builder"),
                     ("lib_molecules", "compound_builder"),
                     ("lib_lego", "lego_builder"),
                     ("lib_people", "human_builder"),
                     ("lib_cars", "car_builder"),
                     ("lib_shoes", "shoe_builder")):
    _same(_key, _other)

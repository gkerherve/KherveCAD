"""Painted CAD-style icons for the ribbon's newer commands (2026-10-20,
the user: "all the icons need to look like Fusion ... remade in a
Fusion-like style. The same for SolidWorks"): sketch shapes, mechanical
features, surfaces from curves, SubD, figures, assembly tools, imports,
document settings and the checks. Same unit square, palettes and iso
helpers as icons_cad.py; every drawing is original.

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


# ================================================================ helpers
def _q(x, y):
    return QPointF(x, y)


def _sheet(d, x0=0.14, y0=0.10, x1=0.80, y1=0.90, fold=0.16):
    """A page with a folded corner (files, code, imports)."""
    page = QPainterPath(_q(x0, y0))
    page.lineTo(x1 - fold, y0)
    page.lineTo(x1, y0 + fold)
    page.lineTo(x1, y1)
    page.lineTo(x0, y1)
    page.closeSubpath()
    d.path(page, d.pal.paper, width=0.04)
    d.poly([_q(x1 - fold, y0), _q(x1 - fold, y0 + fold), _q(x1, y0 + fold)],
           shade(d.pal.body, 0.9), width=0.03)


def _arrow_in(d, x=0.70, y0=0.30, y1=0.80):
    """An import arrow coming down into the page."""
    d.arrow(_q(x, y0), _q(x, y1), d.pal.make, 0.075, 0.16)


def _curve_path(points):
    path = QPainterPath(_q(*points[0]))
    for i in range(1, len(points) - 2, 3):
        path.cubicTo(_q(*points[i]), _q(*points[i + 1]), _q(*points[i + 2]))
    return path


def _sketch_line(d, path, width=0.065):
    d.path(path, None, color=d.pal.sketch, width=width)


def _node(d, x, y, r=0.045):
    d.dot(_q(x, y), d.pal.sketch, r)


# ================================================================ sketch
@draws("create_sketch")
def _create_sketch(d):
    """A sketch plane with a profile and a pencil."""
    plane = [d.P(-1, -1, 0), d.P(1, -1, 0), d.P(1, 1, 0), d.P(-1, 1, 0)]
    d.poly(plane, shade(d.pal.select, 1.75), color=d.pal.select, width=0.03)
    d.ground([(-0.6, -0.5), (0.4, -0.5), (0.4, 0.5), (-0.6, 0.5)],
             dots=True)
    pen = QPainterPath(_q(0.58, 0.62))
    pen.lineTo(_q(0.92, 0.18))
    pen.lineTo(_q(0.98, 0.24))
    pen.lineTo(_q(0.64, 0.68))
    pen.closeSubpath()
    d.path(pen, d.pal.make, width=0.03)
    d.poly([_q(0.58, 0.62), _q(0.64, 0.68), _q(0.55, 0.72)],
           d.pal.edge, width=0.02)


@draws("star")
def _star(d):
    pts = []
    for i in range(10):
        r = 0.42 if i % 2 == 0 else 0.18
        a = math.radians(-90 + 36 * i)
        pts.append(_q(0.5 + r * math.cos(a), 0.54 + r * math.sin(a)))
    d.poly(pts, shade(d.pal.sketch, 1.9), color=d.pal.sketch, width=0.055)
    for q in pts[::2]:
        _node(d, q.x(), q.y(), 0.035)


@draws("rounded_polygon")
def _rounded_polygon(d):
    path = QPainterPath()
    path.addRoundedRect(QRectF(0.12, 0.20, 0.76, 0.60), 0.16, 0.16)
    d.path(path, shade(d.pal.sketch, 1.9), color=d.pal.sketch, width=0.055)
    d.p.setPen(d.pen(d.pal.make, 0.03, [2, 2]))
    d.p.setBrush(QBrush())
    d.p.drawEllipse(QRectF(0.12, 0.20, 0.32, 0.32))
    d.line(_q(0.28, 0.36), _q(0.15, 0.27), d.pal.make, 0.035)


@draws("bezier_shape")
def _bezier(d):
    path = _curve_path([(0.15, 0.75), (0.10, 0.20), (0.55, 0.05),
                        (0.70, 0.40), (0.85, 0.75), (0.45, 0.95),
                        (0.15, 0.75)])
    d.path(path, shade(d.pal.sketch, 1.9), color=d.pal.sketch, width=0.055)
    for a, b in (((0.15, 0.75), (0.10, 0.20)), ((0.70, 0.40),
                                                (0.55, 0.05))):
        d.line(_q(*a), _q(*b), d.pal.make, 0.025)
        d.disc(_q(*b), 0.035, d.pal.make)
    _node(d, 0.15, 0.75)
    _node(d, 0.70, 0.40)


@draws("svg_path")
def _svg(d):
    _sheet(d)
    path = _curve_path([(0.24, 0.72), (0.30, 0.40), (0.50, 0.40),
                        (0.50, 0.58), (0.50, 0.76), (0.70, 0.76),
                        (0.70, 0.46)])
    _sketch_line(d, path, 0.06)
    d.text(0.46, 0.30, "SVG", 0.10, d.pal.make)


@draws("honeycomb")
def _honeycomb(d):
    r = 0.13
    for cx, cy in ((0.30, 0.34), (0.54, 0.34), (0.42, 0.55), (0.66, 0.55),
                   (0.30, 0.76), (0.54, 0.76), (0.18, 0.55)):
        pts = [_q(cx + r * math.cos(math.radians(30 + 60 * i)),
                  cy + r * math.sin(math.radians(30 + 60 * i)))
               for i in range(6)]
        d.poly(pts, shade(d.pal.sketch, 1.85), color=d.pal.sketch,
               width=0.04)


# ================================================================ solids
@draws("curve")
def _curve3d(d):
    pts = [(-1.0, 0.6, 0.0), (-0.3, 0.2, 0.9), (0.4, -0.3, 0.2),
           (1.0, -0.7, 1.0)]
    path = QPainterPath(d.P(*pts[0]))
    path.cubicTo(d.P(*pts[1]), d.P(*pts[2]), d.P(*pts[3]))
    d.path(path, None, color=d.pal.edge, width=0.13)
    d.path(path, None, color=d.pal.make, width=0.08)
    for q in (pts[0], pts[3]):
        d.ball(d.P(*q), 0.07, d.pal.select)


@draws("polyhedron_solid")
def _polyhedron(d):
    top = [(0.0, 0.0, 1.6)]
    ring = [(0.95 * math.cos(math.radians(a)), 0.95 * math.sin(math.radians(a)),
             0.6) for a in range(0, 360, 72)]
    bottom = [(0.0, 0.0, -0.4)]
    for i in range(5):
        a, b = ring[i], ring[(i + 1) % 5]
        mid = (a[0] + b[0]) - (a[1] + b[1])
        if a[0] + b[0] + a[1] + b[1] < -0.4:
            continue
        d.faces([([a, b, bottom[0]], 0.75 + 0.1 * mid)])
    for i in range(5):
        a, b = ring[i], ring[(i + 1) % 5]
        if a[0] + b[0] + a[1] + b[1] < -0.4:
            continue
        d.faces([([a, b, top[0]], 1.15 + 0.12 * ((a[0] + b[0]) -
                                                 (a[1] + b[1])))])


@draws("hole")
def _hole(d):
    d.box(-1, -1, 0, 2, 2, 0.8)
    ring = d.ring(0, 0, 0.8, 0.55)
    d.poly([d.P(*q) for q in ring], shade(d.pal.body, 0.55), width=0.03)
    inner = d.ring(0, 0, 0.8, 0.3)
    d.poly([d.P(*q) for q in inner], shade(d.pal.body, 0.35), width=0.03)
    d.arrow(d.P(0, 0, 2.0), d.P(0, 0, 1.0), d.pal.make, 0.06, 0.12)


@draws("thread")
def _thread(d):
    d.cyl(0, 0, 0, 0.45, 2.0)
    for i in range(6):
        z = 0.2 + i * 0.3
        a = d.P(-0.45, 0.45, z)
        b = d.P(0.45, -0.45, z + 0.15)
        d.line(a, b, shade(d.pal.body, 0.55), 0.05)
    d.cyl(0, 0, 2.0, 0.75, 0.35, d.pal.make)


@draws("gear")
def _gear(d):
    n, ro, ri = 10, 0.44, 0.34
    pts = []
    for i in range(n * 2):
        a = math.radians(i * 180.0 / n)
        r = ro if i % 2 == 0 else ri
        for da in (-0.09, 0.09):
            pts.append(_q(0.5 + r * math.cos(a + da), 0.5 + r * math.sin(a + da)))
    g = QLinearGradient(_q(0.1, 0.1), _q(0.9, 0.9))
    g.setColorAt(0, shade(d.pal.body, 1.35))
    g.setColorAt(1, shade(d.pal.body, 0.75))
    d.poly(pts, QBrush(g))
    d.p.setPen(d.pen())
    d.p.setBrush(d.pal.paper)
    d.p.drawEllipse(_q(0.5, 0.5), 0.12, 0.12)
    d.disc(_q(0.5, 0.5), 0.05, d.pal.make)


@draws("knurl")
def _knurl(d):
    d.cyl(0, 0, 0, 0.8, 1.8)
    mark = shade(d.pal.body, 0.55)
    for ti, th in enumerate(range(-10, 111, 24)):
        a = math.radians(th)
        for zi, z in enumerate((0.35, 0.75, 1.15, 1.55)):
            c = (0.8 * math.cos(a), 0.8 * math.sin(a), z + 0.1 * (ti % 2))
            for dz in (-0.14, 0.14):
                d.line(d.P(c[0] - 0.08 * math.sin(a), c[1] +
                           0.08 * math.cos(a), c[2] - dz),
                       d.P(c[0] + 0.08 * math.sin(a), c[1] -
                           0.08 * math.cos(a), c[2] + dz), mark, 0.025)
    d.poly([d.P(*q) for q in d.ring(0, 0, 1.8, 0.8)],
           shade(d.pal.body, 1.4), color=d.pal.make, width=0.04)


@draws("textured")
def _textured(d):
    d.box(-1, -1, 0, 2, 2, 0.4)
    for i in range(4):
        for j in range(4):
            d.cyl(-0.75 + 0.5 * i, -0.75 + 0.5 * j, 0.4, 0.14, 0.18,
                  d.pal.make)


@draws("sheet_metal")
def _sheet_metal(d):
    t = 0.12
    d.box(-1, -0.9, 0, 2, 1.8, t)
    d.box(0.88, -0.9, t, t, 1.8, 1.2, d.pal.make)
    d.box(-1, 0.78, t, 1.88, t, 0.9)


# ============================================================== surfaces
def _wave(x, z, amp=0.35):
    return z + amp * math.sin(math.pi * (x + 1))


def _rail(d, z, color, width=0.07, dy=0.0, y=-0.8):
    """A wavy curve running along x at depth y (+ dy)."""
    pts = [d.P(-1 + 0.1 * i, y + dy, _wave(-1 + 0.1 * i, z))
           for i in range(21)]
    path = QPainterPath(pts[0])
    for q in pts[1:]:
        path.lineTo(q)
    d.path(path, None, color=color, width=width)


def _skin(d, z0, z1, dy0=0.0, dy1=0.0, color=None, y0=-0.8, y1=0.8):
    """The surface between a front curve (y0, z0) and a back one."""
    color = color or d.pal.body
    front = [d.P(-1 + 0.1 * i, y0 + dy0, _wave(-1 + 0.1 * i, z0))
             for i in range(21)]
    back = [d.P(-1 + 0.1 * i, y1 + dy1, _wave(-1 + 0.1 * i, z1))
            for i in range(21)]
    g = QLinearGradient(front[0], front[-1])
    g.setColorAt(0, shade(color, 1.35))
    g.setColorAt(1, shade(color, 0.85))
    d.poly(front + back[::-1], QBrush(g), width=0.03)


@draws("srf_loft")
def _srf_loft(d):
    _skin(d, 0.0, 1.0)
    _rail(d, 0.0, d.pal.make)
    _rail(d, 1.0, d.pal.make, y=0.8)


@draws("srf_sweep")
def _srf_sweep(d):
    _skin(d, 0.2, 0.2)
    path = QPainterPath(d.P(-1, -0.8, _wave(-1, 0.2)))
    path.lineTo(d.P(-1, 0.8, _wave(-1, 0.2)))
    d.path(path, None, color=d.pal.select, width=0.08)
    _rail(d, 0.2, d.pal.make)


@draws("srf_sweep2")
def _srf_sweep2(d):
    _skin(d, 0.0, 0.6)
    _rail(d, 0.0, d.pal.make)
    _rail(d, 0.6, d.pal.make, y=0.8)
    path = QPainterPath(d.P(1, -0.8, _wave(1, 0.0)))
    path.lineTo(d.P(1, 0.8, _wave(1, 0.6)))
    d.path(path, None, color=d.pal.select, width=0.06)


@draws("srf_patch")
def _srf_patch(d):
    ring = [(math.cos(math.radians(a)) * (1 + 0.15 * math.sin(3 * math.radians(a))),
             math.sin(math.radians(a)), 0.4 + 0.3 * math.sin(2 * math.radians(a)))
            for a in range(0, 360, 15)]
    d.poly([d.P(*q) for q in ring], shade(d.pal.body, 1.25),
           color=d.pal.make, width=0.07)
    d.ball(d.P(0, 0, 0.9), 0.06, d.pal.select)


@draws("srf_revolve")
def _srf_revolve(d):
    d.solid(d.ring(0, 0, 0, 0.9), d.ring(0, 0, 1.6, 0.5))
    d.line(d.P(0, 0, -0.3), d.P(0, 0, 2.2), d.pal.select, 0.04)
    d.arc_arrow(d.P(0, 0, 2.0), 0.28, 0.1, 200, 520, d.pal.make, 0.05, 0.1)


@draws("srf_extrude")
def _srf_extrude(d):
    front = [d.P(-1 + 0.1 * i, 0, _wave(-1 + 0.1 * i, 0.0, 0.3))
             for i in range(21)]
    top = [d.P(-1 + 0.1 * i, 0, _wave(-1 + 0.1 * i, 1.3, 0.3))
           for i in range(21)]
    g = QLinearGradient(front[0], front[-1])
    g.setColorAt(0, shade(d.pal.body, 1.35))
    g.setColorAt(1, shade(d.pal.body, 0.85))
    d.poly(front + top[::-1], QBrush(g), width=0.03)
    path = QPainterPath(front[0])
    for q in front[1:]:
        path.lineTo(q)
    d.path(path, None, color=d.pal.select, width=0.07)
    d.arrow(d.P(1, 0, 0.1), d.P(1, 0, 1.9), d.pal.make, 0.06, 0.12)


@draws("draw_curve")
def _draw_curve(d):
    plane = [d.P(-1, -1, 0), d.P(1, -1, 0), d.P(1, 1, 0), d.P(-1, 1, 0)]
    d.poly(plane, shade(d.pal.body, 1.3), width=0.025)
    pts = [(-0.8, 0.6, 0.0), (-0.2, 0.0, 0.8), (0.4, -0.2, 0.3),
           (0.8, -0.7, 1.1)]
    for a, b in zip(pts, pts[1:]):
        d.line(d.P(*a), d.P(*b), d.pal.make, 0.06)
    for q in pts:
        d.dot(d.P(*q), d.pal.select, 0.05)


# ================================================================== form
def _cage_box(d, s=1.0, color=None):
    color = color or d.pal.select
    c = [(x, y, z) for x in (-s, s) for y in (-s, s) for z in (0, 2 * s)]
    for a in c:
        for b in c:
            if a < b and sum(p != q for p, q in zip(a, b)) == 1:
                d.line(d.P(*a), d.P(*b), color, 0.03)
    for q in c:
        d.dot(d.P(*q), color, 0.035)


@draws("subd_box")
def _subd_box(d):
    d.ball(d.P(0, 0, 0.9), 0.24, shade(d.pal.body, 1.05))
    _cage_box(d, 0.85)


@draws("subd_convert")
def _subd_convert(d):
    d.box(-1.6, -0.2, 0, 0.9, 0.9, 0.9)
    d.arrow(d.P(-0.4, 0.2, 0.5), d.P(0.4, -0.2, 0.5), d.pal.make, 0.05, 0.1)
    d.ball(d.P(1.0, -0.6, 0.6), 0.12, d.pal.body)


# ============================================================ character
@draws("human")
def _human_fig(d):
    skin = QColor("#e8b894")
    for x in (0.43, 0.57):
        d.line(_q(x, 0.60), _q(x, 0.93), d.pal.edge, 0.11)
        d.line(_q(x, 0.60), _q(x, 0.92), shade(skin, 0.95), 0.07)
    for a, b in (((0.35, 0.36), (0.22, 0.60)), ((0.65, 0.36), (0.78, 0.60))):
        d.line(_q(*a), _q(*b), d.pal.edge, 0.10)
        d.line(_q(*a), _q(*b), skin, 0.06)
    body = QPainterPath()
    body.addRoundedRect(QRectF(0.34, 0.30, 0.32, 0.34), 0.10, 0.10)
    d.path(body, skin)
    d.ball(_q(0.5, 0.17), 0.11, skin)


@draws("skin")
def _skin_fig(d):
    pts = [(0.5, 0.16), (0.5, 0.48), (0.30, 0.60), (0.70, 0.60),
           (0.40, 0.90), (0.60, 0.90)]
    body = QPainterPath()
    body.addRoundedRect(QRectF(0.28, 0.08, 0.44, 0.86), 0.2, 0.2)
    d.path(body, shade(d.pal.body, 1.2), width=0.03)
    for a, b in ((0, 1), (1, 2), (1, 3), (1, 4), (1, 5)):
        d.line(_q(*pts[a]), _q(*pts[b]), d.pal.make, 0.05)
    for q in pts:
        d.disc(_q(*q), 0.045, d.pal.select)


# ============================================================= assembly
@draws("new_object")
def _new_object(d):
    d.box(-0.9, -0.9, 0, 1.4, 1.4, 1.1)
    c = _q(0.80, 0.22)
    d.disc(c, 0.17, d.pal.make)
    d.line(_q(0.72, 0.22), _q(0.88, 0.22), d.pal.paper, 0.05)
    d.line(_q(0.80, 0.14), _q(0.80, 0.30), d.pal.paper, 0.05)


@draws("gumball")
def _gumball(d):
    o = d.P(0, 0, 0.5)
    d.arrow(o, d.P(1.5, 0, 0.5), QColor("#d6402f"), 0.06, 0.13)
    d.arrow(o, d.P(0, 1.5, 0.5), QColor("#3a9a3a"), 0.06, 0.13)
    d.arrow(o, d.P(0, 0, 2.0), QColor("#2f6fd0"), 0.06, 0.13)
    d.arc_arrow(o, 0.28, 0.14, 20, 160, d.pal.make, 0.045, 0.08)
    d.ball(o, 0.06, d.pal.paper)


@draws("explode")
def _explode(d):
    d.box(-0.7, -0.7, 0, 1.4, 1.4, 0.5)
    d.box(-0.7, -0.7, 1.1, 1.4, 1.4, 0.5, shade(d.pal.select, 1.5))
    d.line(d.P(0, 0, 0.55), d.P(0, 0, 1.05), d.pal.make, 0.04)
    d.arrow(d.P(0.9, -0.9, 0.7), d.P(0.9, -0.9, 1.5), d.pal.make, 0.05, 0.1)


@draws("animate")
def _animate(d):
    film = QPainterPath()
    film.addRoundedRect(QRectF(0.10, 0.22, 0.80, 0.56), 0.06, 0.06)
    d.path(film, shade(d.pal.body, 1.1))
    for i in range(5):
        x = 0.16 + i * 0.16
        d.p.setBrush(d.pal.edge)
        d.p.drawRect(QRectF(x, 0.25, 0.06, 0.05))
        d.p.drawRect(QRectF(x, 0.70, 0.06, 0.05))
    d.poly([_q(0.42, 0.38), _q(0.42, 0.62), _q(0.62, 0.50)], d.pal.make)


# ================================================================ insert
@draws("part_library")
def _part_library(d):
    for i, c in enumerate((d.pal.select, d.pal.make, d.pal.body)):
        x = -1.1 + 0.75 * i
        d.box(x, -0.4, 0, 0.6, 0.8, 1.6 - 0.25 * i, shade(c, 1.2))


@draws("import_scad")
def _import_scad(d):
    _sheet(d)
    d.text(0.42, 0.52, "{ }", 0.20, d.pal.select)
    _arrow_in(d, 0.42, 0.62, 0.86)


@draws("import_mesh")
def _import_mesh(d):
    tri = [d.P(-0.9, -0.9, 0), d.P(0.9, -0.9, 0), d.P(0, 0.6, 0),
           d.P(0, -0.3, 1.5)]
    d.poly([tri[0], tri[1], tri[3]], shade(d.pal.body, 0.9))
    d.poly([tri[1], tri[2], tri[3]], shade(d.pal.body, 1.2))
    for a, b in ((0, 3), (1, 3), (2, 3), (0, 1), (1, 2)):
        d.line(tri[a], tri[b], d.pal.edge, 0.03)
    d.arrow(_q(0.82, 0.02), _q(0.82, 0.40), d.pal.make, 0.06, 0.13)


@draws("import_cad")
def _import_cad(d):
    d.box(-0.9, -0.9, 0, 1.2, 1.2, 0.8)
    d.cyl(0.3, 0.3, 0.8, 0.4, 0.6, d.pal.select)
    d.text(0.24, 0.92, "STEP", 0.11, d.pal.edge)
    d.arrow(_q(0.84, 0.02), _q(0.84, 0.38), d.pal.make, 0.06, 0.13)


@draws("import_heightmap")
def _import_heightmap(d):
    pts = []
    for i in range(9):
        x = -1 + i * 0.25
        pts.append(d.P(x, -1, 0.5 + 0.4 * math.sin(i * 1.3)))
    pts += [d.P(1, 1, 0.3), d.P(-1, 1, 0.3)]
    d.poly(pts, shade(QColor("#7aa65a"), 1.1))
    d.box(-1, -1, -0.4, 2, 2, 0.4)


@draws("import_stack")
def _import_stack(d):
    for i in range(4):
        z = i * 0.35
        quad = [d.P(-1, -1, z), d.P(1, -1, z), d.P(1, 1, z), d.P(-1, 1, z)]
        d.poly(quad, shade(d.pal.select, 1.7 - 0.12 * i), width=0.03)
    d.ball(d.P(0, 0, 0.7), 0.12, d.pal.make)


@draws("import_glb")
def _import_glb(d):
    _human_fig(d)
    d.arc_arrow(_q(0.5, 0.5), 0.40, 0.12, 200, 340, d.pal.make, 0.04, 0.08)


@draws("ref_add")
def _ref_add(d):
    frame = QPainterPath()
    frame.addRoundedRect(QRectF(0.10, 0.18, 0.70, 0.56), 0.04, 0.04)
    d.path(frame, d.pal.paper)
    d.poly([_q(0.16, 0.68), _q(0.36, 0.42), _q(0.52, 0.58), _q(0.62, 0.48),
            _q(0.74, 0.68)], QColor("#7aa65a"), width=0.02)
    d.disc(_q(0.62, 0.32), 0.06, d.pal.make)
    d.disc(_q(0.82, 0.78), 0.14, d.pal.select)
    d.line(_q(0.76, 0.78), _q(0.88, 0.78), d.pal.paper, 0.04)
    d.line(_q(0.82, 0.72), _q(0.82, 0.84), d.pal.paper, 0.04)


@draws("ref_clear")
def _ref_clear(d):
    frame = QPainterPath()
    frame.addRoundedRect(QRectF(0.10, 0.18, 0.70, 0.56), 0.04, 0.04)
    d.path(frame, d.pal.paper)
    d.poly([_q(0.16, 0.68), _q(0.36, 0.42), _q(0.52, 0.58), _q(0.74, 0.68)],
           QColor("#7aa65a"), width=0.02)
    d.disc(_q(0.82, 0.78), 0.14, d.pal.cut)
    d.line(_q(0.76, 0.72), _q(0.88, 0.84), d.pal.paper, 0.04)
    d.line(_q(0.88, 0.72), _q(0.76, 0.84), d.pal.paper, 0.04)


@draws("code_files")
def _code_files(d):
    _sheet(d)
    for y, w, c in ((0.36, 0.34, d.pal.select), (0.50, 0.24, d.pal.make),
                    (0.64, 0.38, d.pal.sketch), (0.78, 0.20, d.pal.edge)):
        d.line(_q(0.26, y), _q(0.26 + w, y), c, 0.055)


# ============================================================== document
@draws("doc_units")
def _doc_units(d):
    rule = QPainterPath()
    rule.addRoundedRect(QRectF(0.06, 0.38, 0.88, 0.26), 0.03, 0.03)
    d.path(rule, shade(QColor("#f0c64a"), 1.05))
    for i in range(11):
        x = 0.12 + i * 0.076
        d.line(_q(x, 0.38), _q(x, 0.47 if i % 5 else 0.53), d.pal.edge, 0.02)
    d.text(0.5, 0.86, "mm", 0.13, d.pal.select)


@draws("doc_scale")
def _doc_scale(d):
    d.box(-1.2, -0.3, 0, 0.5, 0.5, 0.5)
    d.box(0.0, -0.9, 0, 1.2, 1.2, 1.2, shade(d.pal.select, 1.5))
    d.text(0.5, 0.18, "1 : N", 0.14, d.pal.make)


@draws("customizer")
def _customizer(d):
    panel = QPainterPath()
    panel.addRoundedRect(QRectF(0.10, 0.14, 0.80, 0.72), 0.06, 0.06)
    d.path(panel, d.pal.paper)
    for y, at in ((0.32, 0.66), (0.50, 0.34), (0.68, 0.54)):
        d.line(_q(0.20, y), _q(0.80, y), d.pal.body, 0.05)
        d.line(_q(0.20, y), _q(at, y), d.pal.select, 0.05)
        d.ball(_q(at, y), 0.055, d.pal.make)


# ================================================================ checks
@draws("heatmap")
def _heatmap(d):
    colours = ("#2f6fd0", "#2fb3b3", "#3a9a3a", "#e8c43a", "#e07b2f",
               "#d6402f")
    for i, c in enumerate(colours):
        z = i * 0.3
        d.box(-0.9, -0.9, z, 1.8, 1.8, 0.3, QColor(c))


@draws("sharp_edges")
def _sharp_edges(d):
    d.box(-0.9, -0.9, 0, 1.8, 1.8, 1.0)
    d.line(d.P(-0.9, 0.9, 1.0), d.P(0.9, 0.9, 1.0), d.pal.cut, 0.08)
    d.line(d.P(0.9, -0.9, 1.0), d.P(0.9, 0.9, 1.0), d.pal.cut, 0.08)
    d.line(d.P(0.9, 0.9, 0.0), d.P(0.9, 0.9, 1.0), d.pal.cut, 0.08)


@draws("fits")
def _fits(d):
    d.box(-1, -1, 0, 2, 2, 0.7)
    d.poly([d.P(*q) for q in d.ring(0, 0, 0.7, 0.55)],
           shade(d.pal.body, 0.45), width=0.03)
    d.cyl(0, 0, 0.7, 0.42, 1.2, d.pal.select)
    d.text(0.84, 0.22, "H7", 0.12, d.pal.make)


@draws("welds")
def _welds(d):
    d.box(-1, -0.9, 0, 2, 1.8, 0.25)
    d.box(-1, -0.12, 0.25, 2, 0.25, 1.2)
    for i in range(7):
        x = -0.9 + i * 0.3
        d.ball(d.P(x, 0.2, 0.3), 0.05, d.pal.make)


@draws("ref_compare")
def _ref_compare(d):
    frame = QPainterPath()
    frame.addRect(QRectF(0.10, 0.12, 0.80, 0.76))
    d.path(frame, shade(d.pal.select, 1.8), color=d.pal.select, width=0.03)
    d.cx, d.cy, d.k = 0.5, 0.62, 0.20
    d.box(-0.9, -0.9, 0, 1.8, 1.8, 1.2)
    d.p.setPen(d.pen(d.pal.make, 0.035, [2, 2]))
    d.p.setBrush(QBrush())
    d.p.drawRect(QRectF(0.24, 0.20, 0.52, 0.58))


@draws("dims_selection")
def _dims_selection(d):
    d.box(-0.9, -0.9, 0, 1.8, 1.8, 0.9, shade(d.pal.select, 1.4))
    d.arrow(d.P(-0.9, 1.3, 0), d.P(0.9, 1.3, 0), d.pal.make, 0.035, 0.1)
    d.arrow(d.P(0.9, 1.3, 0), d.P(-0.9, 1.3, 0), d.pal.make, 0.035, 0.1)


@draws("dims_clear")
def _dims_clear(d):
    d.arrow(_q(0.12, 0.40), _q(0.88, 0.40), d.pal.make, 0.04, 0.12)
    d.arrow(_q(0.88, 0.40), _q(0.12, 0.40), d.pal.make, 0.04, 0.12)
    d.disc(_q(0.72, 0.72), 0.17, d.pal.cut)
    d.line(_q(0.64, 0.64), _q(0.80, 0.80), d.pal.paper, 0.05)
    d.line(_q(0.80, 0.64), _q(0.64, 0.80), d.pal.paper, 0.05)

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


def _patch(d, f, nu=10, nv=6, body=None):
    """A shaded parametric surface f(u, v) -> (x, y, z), u, v in 0..1:
    quads painted far to near, lit like the iso solids (light from the
    upper left), thin seams in their own colour — a surface, not a
    ribbon."""
    # Fusion draws surfaces a steel blue-grey (its bodies are near white
    # and a light surface vanished); SolidWorks keeps its yellow
    body = body or (d.pal.body if d.style == "SolidWorks"
                    else QColor("#8fa9c2"))
    light = (-0.45, 0.35, 0.82)
    quads = []
    for i in range(nu):
        for j in range(nv):
            a = f(i / nu, j / nv)
            b = f((i + 1) / nu, j / nv)
            c = f((i + 1) / nu, (j + 1) / nv)
            e = f(i / nu, (j + 1) / nv)
            ux, uy, uz = (c[k] - a[k] for k in range(3))
            vx, vy, vz = (e[k] - b[k] for k in range(3))
            n = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
            ln = math.sqrt(sum(x * x for x in n)) or 1.0
            lit = abs(sum(n[k] * light[k] for k in range(3)) / ln)
            depth = sum(q[0] + q[1] - 0.3 * q[2] for q in (a, b, c, e))
            quads.append((depth, (a, b, c, e), 0.62 + 0.55 * lit))
    for _dep, pts, k in sorted(quads):
        colour = shade(body, k)
        d.poly([d.P(*q) for q in pts], colour, color=colour, width=0.012)


def _curve3(d, pts, colour, width=0.05):
    """A smooth curve through 3D points, edged so it reads."""
    path = QPainterPath(d.P(*pts[0]))
    for q in pts[1:]:
        path.lineTo(d.P(*q))
    d.path(path, None, color=shade(colour, 0.6), width=width + 0.02)
    d.path(path, None, color=colour, width=width)


def _section(x, v, lift=0.0, amp=0.45):
    """A wave across y at station x (v 0..1 along it)."""
    y = -0.9 + 1.8 * v
    return (x, y, lift + amp * math.sin(math.pi * v))


def _line_of(f, n=24):
    return [f(t / n) for t in range(n + 1)]


@draws("srf_loft")
def _srf_loft(d):
    """A skin through two different sections (orange)."""
    def f(u, v):
        x = -1.0 + 2.0 * u
        amp = 0.25 + 0.45 * u
        return _section(x, v, 0.15 * math.sin(math.pi * u), amp)
    _patch(d, f)
    _curve3(d, _line_of(lambda t: f(0, t)), d.pal.make)
    _curve3(d, _line_of(lambda t: f(1, t)), d.pal.make)


@draws("srf_sweep")
def _srf_sweep(d):
    """A profile (orange) swept along a rail (blue)."""
    def rail(u):
        return (-1.0 + 2.0 * u, 0.5 * math.sin(math.pi * u * 1.2) - 0.4,
                0.0)

    def f(u, v):
        x, y, z = rail(u)
        return (x, y + 0.9 * v, z + 0.7 * math.sin(math.pi * v))
    _patch(d, f)
    _curve3(d, _line_of(rail), d.pal.select)
    _curve3(d, _line_of(lambda t: f(0, t)), d.pal.make)


@draws("srf_sweep2")
def _srf_sweep2(d):
    """A profile carried between two rails (blue)."""
    def f(u, v):
        x = -1.0 + 2.0 * u
        y0 = -0.9 + 0.25 * math.sin(math.pi * u)
        y1 = 0.9 - 0.35 * math.sin(math.pi * u)
        return (x, y0 + (y1 - y0) * v,
                0.55 * math.sin(math.pi * v) * (0.6 + 0.4 * u))
    _patch(d, f)
    _curve3(d, _line_of(lambda t: f(t, 0)), d.pal.select)
    _curve3(d, _line_of(lambda t: f(t, 1)), d.pal.select)
    _curve3(d, _line_of(lambda t: f(0, t)), d.pal.make, 0.04)


@draws("srf_patch")
def _srf_patch(d):
    """A domed patch filling a closed boundary (orange)."""
    def f(u, v):
        a = 2 * math.pi * u
        r = v * (1.0 + 0.12 * math.sin(3 * a))
        return (r * math.cos(a), r * math.sin(a),
                0.75 * (1 - v * v) + 0.15 * math.sin(2 * a) * v)
    _patch(d, f, 24, 5)
    _curve3(d, _line_of(lambda t: f(t, 1), 40), d.pal.make)


@draws("srf_revolve")
def _srf_revolve(d):
    """A profile turned about its axis: a vase-like surface."""
    def r_of(v):
        return 0.55 + 0.35 * math.sin(math.pi * (0.2 + 0.9 * v))

    def f(u, v):
        a = 2 * math.pi * u
        r = r_of(v)
        return (r * math.cos(a), r * math.sin(a), 1.8 * v)
    _patch(d, f, 24, 6)
    _curve3(d, _line_of(lambda t: f(0.125, t)), d.pal.make)
    d.line(d.P(0, 0, -0.2), d.P(0, 0, 2.2), d.pal.select, 0.045)
    d.arc_arrow(d.P(0, 0, 2.1), 0.32, 0.12, 200, 520, d.pal.make, 0.05,
                0.1)


@draws("srf_extrude")
def _srf_extrude(d):
    """A curve (blue) pushed straight up into a surface."""
    def base(u):
        x = -1.0 + 2.0 * u
        return (x, 0.45 * math.sin(math.pi * 1.5 * u), 0.0)

    def f(u, v):
        x, y, _z = base(u)
        return (x, y, 1.4 * v)
    _patch(d, f, 12, 4)
    _curve3(d, _line_of(base), d.pal.select)
    d.arrow(d.P(1.15, 0, 0.3), d.P(1.15, 0, 1.9), d.pal.make, 0.07, 0.14)


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


# ============================================================= utilities
@draws("make2d")
def _make2d(d):
    _sheet(d, 0.30, 0.10, 0.92, 0.80)
    for a, b in (((0.42, 0.62), (0.80, 0.62)), ((0.42, 0.62), (0.42, 0.30)),
                 ((0.80, 0.62), (0.80, 0.42)), ((0.42, 0.30), (0.62, 0.30))):
        d.line(_q(*a), _q(*b), d.pal.edge, 0.035)
    d.cx, d.cy, d.k = 0.22, 0.78, 0.13
    d.box(-0.8, -0.8, 0, 1.6, 1.6, 1.0)


@draws("printables")
def _printables(d):
    d.box(-1, -1, 0, 2, 2, 0.25, shade(d.pal.body, 0.9))
    d.box(-0.5, -0.5, 0.25, 1.0, 1.0, 0.9, d.pal.make)
    nozzle = [d.P(0, 0, 2.3), d.P(0.25, -0.25, 2.0), d.P(0, 0, 1.4),
              d.P(-0.25, 0.25, 2.0)]
    d.poly(nozzle, shade(d.pal.body, 1.1))
    d.arrow(_q(0.86, 0.60), _q(0.86, 0.12), d.pal.select, 0.06, 0.14)


@draws("export_stl")
def _export_stl(d):
    """A triangulated block going out as a file."""
    d.box(-1, -1, 0, 1.6, 1.6, 1.2)
    for a, b in (((-1, 0.6, 0), (0.6, 0.6, 1.2)),
                 ((0.6, -1, 0), (0.6, 0.6, 1.2)),
                 ((-1, -1, 1.2), (0.6, 0.6, 1.2))):
        d.line(d.P(*a), d.P(*b), shade(d.pal.body, 0.55), 0.03)
    d.arrow(d.P(0.9, 0.9, 0.6), d.P(2.0, 2.0, 0.6), d.pal.make, 0.07, 0.15)


@draws("claude_connect")
def _claude_connect(d):
    d.disc(_q(0.34, 0.50), 0.22, d.pal.make)
    for i in range(8):
        a = math.radians(i * 45)
        d.line(_q(0.34 + 0.08 * math.cos(a), 0.50 + 0.08 * math.sin(a)),
               _q(0.34 + 0.19 * math.cos(a), 0.50 + 0.19 * math.sin(a)),
               d.pal.paper, 0.04)
    d.line(_q(0.56, 0.50), _q(0.72, 0.50), d.pal.edge, 0.05)
    d.cx, d.cy, d.k = 0.80, 0.56, 0.10
    d.box(-0.8, -0.8, 0, 1.6, 1.6, 1.2)


@draws("chatbox")
def _chatbox(d):
    bubble = QPainterPath()
    bubble.addRoundedRect(QRectF(0.08, 0.14, 0.84, 0.56), 0.14, 0.14)
    tail = QPainterPath(_q(0.26, 0.66))
    tail.lineTo(_q(0.20, 0.88))
    tail.lineTo(_q(0.44, 0.68))
    d.path(bubble.united(tail), d.pal.paper)
    for i, c in enumerate((d.pal.make, d.pal.select, d.pal.body)):
        d.disc(_q(0.32 + i * 0.18, 0.42), 0.05, c)


@draws("photo3d")
def _photo3d(d):
    cam = QPainterPath()
    cam.addRoundedRect(QRectF(0.06, 0.30, 0.50, 0.38), 0.06, 0.06)
    d.path(cam, shade(d.pal.body, 0.9))
    d.p.setPen(d.pen())
    d.p.setBrush(d.pal.paper)
    d.p.drawEllipse(_q(0.31, 0.49), 0.11, 0.11)
    d.arrow(_q(0.58, 0.49), _q(0.72, 0.49), d.pal.make, 0.045, 0.09)
    d.cx, d.cy, d.k = 0.84, 0.56, 0.09
    d.box(-0.8, -0.8, 0, 1.6, 1.6, 1.4, d.pal.select)


def _git(d, arrow=None):
    d.line(_q(0.30, 0.18), _q(0.30, 0.82), d.pal.edge, 0.06)
    d.line(_q(0.30, 0.55), _q(0.66, 0.34), d.pal.edge, 0.06)
    for x, y, c in ((0.30, 0.18, d.pal.select), (0.30, 0.82, d.pal.select),
                    (0.66, 0.30, d.pal.make)):
        d.p.setPen(d.pen())
        d.p.setBrush(c)
        d.p.drawEllipse(_q(x, y), 0.09, 0.09)
    if arrow == "up":
        d.arrow(_q(0.84, 0.86), _q(0.84, 0.50), d.pal.make, 0.05, 0.11)
    elif arrow == "down":
        d.arrow(_q(0.84, 0.50), _q(0.84, 0.86), d.pal.make, 0.05, 0.11)


@draws("git_commit")
def _git_commit(d):
    _git(d)
    d.disc(_q(0.80, 0.78), 0.12, d.pal.make)
    d.line(_q(0.74, 0.78), _q(0.86, 0.78), d.pal.paper, 0.035)
    d.line(_q(0.80, 0.72), _q(0.80, 0.84), d.pal.paper, 0.035)


@draws("git_push")
def _git_push(d):
    _git(d, "up")


@draws("git_pull")
def _git_pull(d):
    _git(d, "down")


@draws("git_remote")
def _git_remote(d):
    _git(d)
    cloud = QPainterPath()
    for x, y, r in ((0.74, 0.76, 0.10), (0.86, 0.72, 0.09), (0.80, 0.66, 0.09)):
        cloud.addEllipse(_q(x, y), r, r)
    d.path(cloud.simplified(), d.pal.paper, color=d.pal.select, width=0.035)


@draws("locate_openscad")
def _locate_openscad(d):
    d.cx, d.cy, d.k = 0.42, 0.50, 0.20
    d.box(-0.8, -0.8, 0, 1.6, 1.6, 1.2, QColor("#f5d33b"))
    d.p.setPen(d.pen(d.pal.edge, 0.06))
    d.p.setBrush(QBrush())
    d.p.drawEllipse(_q(0.66, 0.60), 0.17, 0.17)
    d.line(_q(0.78, 0.72), _q(0.94, 0.90), d.pal.edge, 0.08)


@draws("language")
def _language(d):
    d.p.setPen(d.pen(d.pal.select, 0.05))
    d.p.setBrush(shade(d.pal.select, 1.8))
    d.p.drawEllipse(_q(0.5, 0.5), 0.38, 0.38)
    d.p.setBrush(QBrush())
    d.p.drawEllipse(QRectF(0.34, 0.12, 0.32, 0.76))
    d.line(_q(0.12, 0.5), _q(0.88, 0.5), d.pal.select, 0.04)
    d.line(_q(0.20, 0.32), _q(0.80, 0.32), d.pal.select, 0.03)
    d.line(_q(0.20, 0.68), _q(0.80, 0.68), d.pal.select, 0.03)


# =============================================================== publish
def _out_arrow(d):
    d.arrow(_q(0.70, 0.62), _q(0.96, 0.36), d.pal.make, 0.07, 0.15)


@draws("export_cad")
def _export_cad(d):
    d.box(-1.0, -0.6, 0, 1.2, 1.2, 0.8)
    d.cyl(-0.4, 0.0, 0.8, 0.4, 0.6, d.pal.select)
    d.text(0.40, 0.95, "STEP", 0.12, d.pal.edge)
    _out_arrow(d)


@draws("export_scad")
def _export_scad(d):
    _sheet(d, 0.08, 0.10, 0.68, 0.90)
    d.text(0.38, 0.56, "{ }", 0.20, d.pal.select)
    _out_arrow(d)


@draws("export_glb")
def _export_glb(d):
    _human_fig(d)
    d.arrow(_q(0.74, 0.70), _q(0.98, 0.46), d.pal.make, 0.06, 0.13)


@draws("planetcraft")
def _planetcraft(d):
    g = QLinearGradient(_q(0.1, 0.1), _q(0.9, 0.9))
    g.setColorAt(0, QColor("#7cc576"))
    g.setColorAt(1, QColor("#2f7f4a"))
    d.p.setPen(d.pen(d.pal.edge, 0.04))
    d.p.setBrush(QBrush(g))
    d.p.drawEllipse(_q(0.46, 0.54), 0.36, 0.36)
    d.p.setBrush(QColor("#3d8fd6"))
    d.p.drawEllipse(_q(0.36, 0.62), 0.12, 0.08)
    d.cx, d.cy, d.k = 0.80, 0.30, 0.09
    d.box(-0.8, -0.8, 0, 1.6, 1.6, 1.6, d.pal.make)


@draws("export_png")
def _export_png(d):
    frame = QPainterPath()
    frame.addRoundedRect(QRectF(0.06, 0.16, 0.66, 0.58), 0.05, 0.05)
    d.path(frame, d.pal.paper)
    d.cx, d.cy, d.k = 0.39, 0.52, 0.12
    d.box(-0.8, -0.8, 0, 1.6, 1.6, 1.2)
    _out_arrow(d)


@draws("export_movie")
def _export_movie(d):
    _animate(d)


@draws("render_photo")
def _render_photo(d):
    d.cx, d.cy, d.k = 0.40, 0.66, 0.16
    d.p.setPen(d.pen(d.pal.edge, 0.02))
    d.p.setBrush(shade(d.pal.body, 0.8))
    d.p.drawEllipse(_q(0.40, 0.84), 0.30, 0.07)          # shadow
    d.ball(_q(0.40, 0.58), 0.24, d.pal.select)
    for a in range(0, 360, 45):
        r = math.radians(a)
        d.line(_q(0.80 + 0.07 * math.cos(r), 0.20 + 0.07 * math.sin(r)),
               _q(0.80 + 0.14 * math.cos(r), 0.20 + 0.14 * math.sin(r)),
               d.pal.make, 0.035)
    d.disc(_q(0.80, 0.20), 0.055, d.pal.make)

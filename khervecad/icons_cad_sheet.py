"""Painted icons for the SHEET METAL tab (2026-10-27, the user: "the
icons need to look like SolidWorks"): thin yellow sheets in iso, the
new flange / fold / hem in the style's 'make' colour (SolidWorks blue
arrows, Fusion orange), bend lines dashed, cuts red. Original drawings
on icons_cad's unit square and helpers.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from PyQt5.QtCore import QPointF
from PyQt5.QtGui import QPainterPath

from .icons_cad import draws, shade

T = 0.14                      # sheet thickness in icon units


def _plate(d, x=-1.0, y=-0.9, w=2.0, dp=1.8, z=0.0, body=None):
    d.box(x, y, z, w, dp, T, body)


def _wall(d, x, y, w, h, z=T, body=None):
    """An upright flange along x at depth y."""
    d.box(x, y, z, w, T, h, body)


def _wall_x(d, x, y, dp, h, z=T, body=None):
    """An upright flange along y at x."""
    d.box(x, y, z, T, dp, h, body)


def _bend_arc(d, y, z0, r, color, a0=180, a1=270, x0=-1.0, x1=1.0):
    """A bend's rounded corner seen along x: two arcs (ends of the
    strip)."""
    for x in (x0, x1):
        path = QPainterPath()
        for i in range(9):
            a = math.radians(a0 + (a1 - a0) * i / 8)
            q = d.P(x, y + r * math.cos(a), z0 + r * math.sin(a))
            if i == 0:
                path.moveTo(q)
            else:
                path.lineTo(q)
        d.path(path, None, color=color, width=0.05)


def _up(d, x, y, z0, z1):
    d.arrow(d.P(x, y, z0), d.P(x, y, z1), d.pal.make, 0.07, 0.15)


@draws("sm_base")
def _base(d):
    """Base Flange/Tab: a sketch profile and the plate grown from it."""
    _plate(d, -1, -0.9, 2, 1.8, 0)
    d.ground([(-0.7, -0.6), (0.7, -0.6), (0.7, 0.6), (-0.7, 0.6)],
             color=d.pal.make, z=T, width=0.06)
    _up(d, 0.0, 0.0, T, 0.85)


@draws("sm_convert")
def _convert(d):
    """Convert to Sheet Metal: a solid block becoming a bent sheet."""
    d.box(-1.0, -0.2, 0, 0.9, 1.1, 0.8, shade(d.pal.body, 0.85))
    d.arrow(d.P(-0.05, 0.3, 0.45), d.P(0.35, 0.3, 0.45), d.pal.make,
            0.06, 0.13)
    _plate(d, 0.3, -0.9, 0.8, 1.8, 0)
    _wall_x(d, 0.96, -0.9, 1.8, 0.8)


@draws("sm_flange", "sheet_metal_flange")
def _flange(d):
    """Edge Flange: a wall bent up off the plate's edge, the edge blue."""
    _plate(d)
    _wall(d, -1.0, 0.76, 2.0, 1.1, body=shade(d.pal.body, 1.1))
    d.line(d.P(-1, 0.9, T), d.P(1, 0.9, T), d.pal.select, 0.07)
    _up(d, 0.2, -0.2, T, 1.1)


@draws("sm_fold")
def _fold(d):
    """Fold (Sketched Bend): a line across the plate, one side up."""
    _plate(d, -1.0, -0.9, 1.0, 1.8, 0)
    d.box(0.0, -0.9, 0, T, 1.8, 1.0, shade(d.pal.body, 1.1))
    d.line(d.P(-0.05, -0.9, T + 0.01), d.P(-0.05, 0.9, T + 0.01),
           d.pal.make, 0.06, dash=[3, 2])
    d.arrow(d.P(-0.6, 0.0, T), d.P(-0.6, 0.0, 0.9), d.pal.make, 0.07,
            0.15)


@draws("sm_hem")
def _hem(d):
    """Hem: the edge folded right back over itself."""
    _plate(d, -1.0, -0.9, 2.0, 1.8, 0)
    _plate(d, -1.0, -0.9, 2.0, 0.7, 0.36, shade(d.pal.body, 1.15))
    _bend_arc(d, -0.9, 0.25, 0.25, d.pal.edge, 90, 270)


@draws("sm_path")
def _path(d):
    """Path Flange: a chain of flanges off an edge, its path blue."""
    _plate(d, -1.0, -0.9, 2.0, 1.8, 0)
    _wall(d, -1.0, 0.76, 2.0, 0.8, body=shade(d.pal.body, 1.1))
    d.box(-1.0, 0.0, 0.8 + T, 2.0, 0.9, T, shade(d.pal.body, 1.2))
    path = QPainterPath(d.P(1.0, 0.9, T))
    path.lineTo(d.P(1.0, 0.9, 0.95))
    path.lineTo(d.P(1.0, 0.0, 0.95))
    d.path(path, None, color=d.pal.make, width=0.07)
    d.dot(d.P(1.0, 0.9, 0.95), d.pal.make, 0.05)


@draws("sm_contour")
def _contour(d):
    """Contour Flange: a hat section grown from an open profile."""
    pts = [(0.9, 0.0), (0.45, 0.0), (0.45, 0.8), (-0.45, 0.8), (-0.45, 0.0),
           (-0.9, 0.0)]
    for (y0, z0), (y1, z1) in zip(pts, pts[1:]):
        if abs(z1 - z0) < 1e-9:
            d.box(-1.0, min(y0, y1), z0, 2.0, abs(y1 - y0), T,
                  shade(d.pal.body, 1.15 if z0 else 1.0))
        else:
            d.box(-1.0, y0, min(z0, z1), 2.0, T, abs(z1 - z0))
    path = QPainterPath(d.P(1.0, *pts[0]))
    for q in pts[1:]:
        path.lineTo(d.P(1.0, *q))
    d.path(path, None, color=d.pal.make, width=0.07)


@draws("sm_perforate")
def _perforate(d):
    """Perforate: a staggered field of holes in the sheet."""
    _plate(d)
    for j in range(4):
        for i in range(4):
            x = -0.7 + 0.42 * i + (0.21 if j % 2 else 0.0)
            y = -0.6 + 0.4 * j
            if x > 0.8:
                continue
            c = d.P(x, y, T)
            d.disc(c, 0.045, d.pal.cut)


@draws("sm_flat", "sm_flat_pattern")
def _flat(d):
    """Create Flat Pattern: the blank, its bend lines dashed."""
    pts = [(-0.4, -1.0), (0.4, -1.0), (0.4, -0.4), (1.0, -0.4), (1.0, 0.4),
           (0.4, 0.4), (0.4, 1.0), (-0.4, 1.0), (-0.4, 0.4), (-1.0, 0.4),
           (-1.0, -0.4), (-0.4, -0.4)]
    d.ground(pts, color=d.pal.edge, z=0, width=0.05,
             fill=shade(d.pal.body, 1.25))
    for a, b in (((-0.4, -0.4), (0.4, -0.4)), ((0.4, -0.4), (0.4, 0.4)),
                 ((0.4, 0.4), (-0.4, 0.4)), ((-0.4, 0.4), (-0.4, -0.4))):
        d.line(d.P(*a), d.P(*b), d.pal.make, 0.045, dash=[2, 2])


@draws("sm_unfold")
def _unfold(d):
    """Unfold: the wall swinging down flat (arrow outward)."""
    _plate(d, -1.0, -0.9, 2.0, 1.8, 0)
    _plate(d, -1.0, 0.9, 2.0, 0.9, 0, shade(d.pal.body, 1.15))
    d.box(-1.0, 0.76, T, 2.0, T, 0.6, shade(d.pal.body, 0.7))
    d.arc_arrow(d.P(0.2, 0.9, 0.55), 0.22, 0.2, 250, 20, d.pal.make,
                0.055, 0.12)


@draws("sm_refold")
def _refold(d):
    """Refold: the flat wall swinging back up."""
    _plate(d, -1.0, -0.9, 2.0, 1.8, 0)
    _wall(d, -1.0, 0.76, 2.0, 1.0, body=shade(d.pal.body, 1.1))
    d.arc_arrow(d.P(0.3, 1.3, 0.3), 0.22, 0.2, 20, 250, d.pal.make,
                0.055, 0.12)


@draws("sm_rules")
def _rules(d):
    """Sheet Metal Rules: a gauge plate with its thickness callipers."""
    _plate(d, -1.0, -0.6, 1.6, 1.4, 0)
    _wall(d, -1.0, 0.66, 1.6, 0.9)
    # a bend radius gauge and the thickness, in blue
    d.arc_arrow(d.P(0.6, -0.6, 0.0), 0.12, 0.12, 180, 360, d.pal.make,
                0.05, 0.09)
    d.text(0.5, 0.33, "R t", 0.2, d.pal.make)


def _page(d):
    page = QPainterPath(QPointF(0.18, 0.08))
    page.lineTo(0.68, 0.08)
    page.lineTo(0.86, 0.26)
    page.lineTo(0.86, 0.92)
    page.lineTo(0.18, 0.92)
    page.closeSubpath()
    d.path(page, d.pal.paper, width=0.04)


@draws("sm_dxf")
def _dxf(d):
    """Export Flat Pattern as DXF: the blank outline on a page."""
    _page(d)
    pts = [QPointF(0.38, 0.30), QPointF(0.56, 0.30), QPointF(0.56, 0.42),
           QPointF(0.72, 0.42), QPointF(0.72, 0.58), QPointF(0.56, 0.58),
           QPointF(0.56, 0.70), QPointF(0.38, 0.70), QPointF(0.38, 0.58),
           QPointF(0.28, 0.58), QPointF(0.28, 0.42), QPointF(0.38, 0.42)]
    d.poly(pts, shade(d.pal.body, 1.2), color=d.pal.edge, width=0.03)
    d.line(QPointF(0.38, 0.42), QPointF(0.56, 0.42), d.pal.make, 0.03,
           dash=[2, 2])
    d.line(QPointF(0.38, 0.58), QPointF(0.56, 0.58), d.pal.make, 0.03,
           dash=[2, 2])
    d.text(0.52, 0.88, "DXF", 0.14, d.pal.make)


@draws("sm_bend_table")
def _bend_table(d):
    """Export Bend Table: a page of rows with a bend symbol."""
    _page(d)
    for i in range(5):
        y = 0.34 + 0.11 * i
        d.line(QPointF(0.26, y), QPointF(0.78, y), d.pal.edge, 0.025)
    d.line(QPointF(0.44, 0.30), QPointF(0.44, 0.80), d.pal.edge, 0.025)
    path = QPainterPath(QPointF(0.24, 0.24))
    path.lineTo(0.24, 0.12)
    path.quadTo(0.24, 0.06, 0.32, 0.06)
    path.lineTo(0.44, 0.06)
    d.path(path, None, color=d.pal.make, width=0.05)

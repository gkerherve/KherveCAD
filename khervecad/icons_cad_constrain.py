"""Painted CAD-style icons for the sketch's CONSTRAIN panel
(sketch_constrain_ui.py): the geometry in sketch blue, the constraint
itself in the style's accent (Fusion orange, SolidWorks blue-on-yellow
marks). Original drawings on icons_cad.py's unit square.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from PyQt5.QtCore import QPointF, QRectF, Qt

from .icons_cad import draws

P = QPointF
W = 0.065


def _ln(d, a, b, w=W):
    d.line(P(*a), P(*b), d.pal.sketch, w)


def _mark(d, a, b, w=0.05):
    d.line(P(*a), P(*b), d.pal.make, w)


def _circle(d, c, r, color=None, w=W):
    d.p.setPen(d.pen(color or d.pal.sketch, w))
    d.p.setBrush(Qt.NoBrush)
    d.p.drawEllipse(P(*c), r, r)


def _dim(d, a, b, off=(0, -0.16)):
    """A dimension line between a and b, offset, with end ticks."""
    a2 = (a[0] + off[0], a[1] + off[1])
    b2 = (b[0] + off[0], b[1] + off[1])
    _mark(d, a, a2, 0.03)
    _mark(d, b, b2, 0.03)
    d.arrow(P(*((a2[0] + b2[0]) / 2, (a2[1] + b2[1]) / 2)), P(*a2),
            d.pal.make, 0.04, 0.1)
    d.arrow(P(*((a2[0] + b2[0]) / 2, (a2[1] + b2[1]) / 2)), P(*b2),
            d.pal.make, 0.04, 0.1)


@draws("con_coincident")
def _coincident(d):
    _ln(d, (0.12, 0.8), (0.5, 0.45))
    _ln(d, (0.5, 0.45), (0.88, 0.72))
    d.disc(P(0.5, 0.45), 0.1, d.pal.make)


@draws("con_horizontal")
def _horizontal(d):
    _ln(d, (0.12, 0.62), (0.88, 0.62))
    d.text(0.5, 0.44, "H", 0.3, d.pal.make)


@draws("con_vertical")
def _vertical(d):
    _ln(d, (0.36, 0.1), (0.36, 0.9))
    d.text(0.68, 0.62, "V", 0.3, d.pal.make)


@draws("con_parallel")
def _parallel(d):
    _ln(d, (0.12, 0.7), (0.62, 0.2))
    _ln(d, (0.38, 0.88), (0.88, 0.38))
    _mark(d, (0.62, 0.66), (0.74, 0.54))
    _mark(d, (0.7, 0.74), (0.82, 0.62))


@draws("con_perpendicular")
def _perpendicular(d):
    _ln(d, (0.14, 0.84), (0.86, 0.84))
    _ln(d, (0.5, 0.84), (0.5, 0.14))
    d.poly([P(0.5, 0.66), P(0.68, 0.66), P(0.68, 0.84)], color=d.pal.make,
           width=0.05)


@draws("con_tangent")
def _tangent(d):
    _circle(d, (0.48, 0.5), 0.26)
    _ln(d, (0.08, 0.24), (0.9, 0.24))
    d.disc(P(0.48, 0.24), 0.07, d.pal.make)


@draws("con_equal")
def _equal(d):
    _ln(d, (0.12, 0.26), (0.62, 0.26))
    _ln(d, (0.38, 0.8), (0.88, 0.8))
    d.text(0.66, 0.6, "=", 0.22, d.pal.make)


@draws("con_concentric")
def _concentric(d):
    _circle(d, (0.5, 0.5), 0.38)
    _circle(d, (0.5, 0.5), 0.2, d.pal.sketch)
    d.disc(P(0.5, 0.5), 0.07, d.pal.make)


@draws("con_collinear")
def _collinear(d):
    _ln(d, (0.08, 0.76), (0.42, 0.5))
    _ln(d, (0.58, 0.38), (0.92, 0.12))
    d.line(P(0.42, 0.5), P(0.58, 0.38), d.pal.make, 0.04, [2, 2])


@draws("con_midpoint")
def _midpoint(d):
    _ln(d, (0.1, 0.7), (0.9, 0.7))
    d.dot(P(0.1, 0.7), d.pal.point, 0.05)
    d.dot(P(0.9, 0.7), d.pal.point, 0.05)
    d.poly([P(0.5, 0.56), P(0.62, 0.7), P(0.5, 0.84), P(0.38, 0.7)],
           d.pal.make, color=d.pal.make, width=0.03)
    d.text(0.5, 0.42, "M", 0.22, d.pal.make)


@draws("con_symmetric")
def _symmetric(d):
    d.line(P(0.5, 0.06), P(0.5, 0.94), d.pal.edge, 0.035, [3, 2])
    d.dot(P(0.22, 0.4), d.pal.sketch, 0.07)
    d.dot(P(0.78, 0.4), d.pal.sketch, 0.07)
    d.arc_arrow(P(0.5, 0.6), 0.28, 0.14, 160, 20, d.pal.make, 0.045)


@draws("con_fix")
def _fix(d):
    _ln(d, (0.1, 0.84), (0.6, 0.84))
    d.dot(P(0.6, 0.84), d.pal.point, 0.06)
    d.poly([P(0.42, 0.42), P(0.86, 0.42), P(0.86, 0.72), P(0.42, 0.72)],
           d.pal.make, color=d.pal.make, width=0.03)
    d.p.setPen(d.pen(d.pal.make, 0.06))
    d.p.setBrush(Qt.NoBrush)
    d.p.drawArc(QRectF(0.5, 0.18, 0.28, 0.34), 0, 180 * 16)


@draws("con_point_on")
def _point_on(d):
    _circle(d, (0.5, 0.56), 0.32)
    d.disc(P(0.27, 0.33), 0.09, d.pal.make)


@draws("con_distance")
def _distance(d):
    d.dot(P(0.16, 0.74), d.pal.sketch, 0.07)
    d.dot(P(0.84, 0.74), d.pal.sketch, 0.07)
    _dim(d, (0.16, 0.74), (0.84, 0.74), (0, -0.36))


@draws("con_hdistance")
def _hdistance(d):
    d.dot(P(0.16, 0.8), d.pal.sketch, 0.07)
    d.dot(P(0.84, 0.5), d.pal.sketch, 0.07)
    _dim(d, (0.16, 0.8), (0.84, 0.5), (0, 0))
    _mark(d, (0.16, 0.8), (0.16, 0.2), 0.03)
    _mark(d, (0.84, 0.5), (0.84, 0.2), 0.03)


@draws("con_vdistance")
def _vdistance(d):
    d.dot(P(0.25, 0.85), d.pal.sketch, 0.07)
    d.dot(P(0.55, 0.15), d.pal.sketch, 0.07)
    _mark(d, (0.25, 0.85), (0.85, 0.85), 0.03)
    _mark(d, (0.55, 0.15), (0.85, 0.15), 0.03)
    d.arrow(P(0.8, 0.5), P(0.8, 0.85), d.pal.make, 0.04, 0.1)
    d.arrow(P(0.8, 0.5), P(0.8, 0.15), d.pal.make, 0.04, 0.1)


@draws("con_length")
def _length(d):
    _ln(d, (0.14, 0.78), (0.86, 0.78))
    _dim(d, (0.14, 0.78), (0.86, 0.78), (0, -0.38))


@draws("con_point_line")
def _point_line(d):
    _ln(d, (0.1, 0.84), (0.9, 0.84))
    d.dot(P(0.5, 0.2), d.pal.sketch, 0.08)
    d.arrow(P(0.5, 0.5), P(0.5, 0.82), d.pal.make, 0.04, 0.1)
    d.arrow(P(0.5, 0.5), P(0.5, 0.24), d.pal.make, 0.04, 0.1)


@draws("con_radius")
def _radius(d):
    _circle(d, (0.44, 0.56), 0.34)
    d.dot(P(0.44, 0.56), d.pal.point, 0.05)
    d.arrow(P(0.44, 0.56), P(0.68, 0.32), d.pal.make, 0.045, 0.12)
    d.text(0.82, 0.24, "R", 0.2, d.pal.make)


@draws("con_diameter")
def _diameter(d):
    _circle(d, (0.5, 0.5), 0.36)
    d.arrow(P(0.5, 0.5), P(0.25, 0.75), d.pal.make, 0.045, 0.12)
    d.arrow(P(0.5, 0.5), P(0.75, 0.25), d.pal.make, 0.045, 0.12)


@draws("con_angle")
def _angle(d):
    _ln(d, (0.12, 0.84), (0.9, 0.84))
    _ln(d, (0.12, 0.84), (0.7, 0.2))
    d.arc_arrow(P(0.12, 0.84), 0.5, 0.5, 0, 47, d.pal.make, 0.045)


@draws("con_auto")
def _auto(d):
    d.poly([P(0.14, 0.3), P(0.7, 0.3), P(0.7, 0.86), P(0.14, 0.86)],
           color=d.pal.sketch, width=W)
    d.text(0.42, 0.66, "H", 0.2, d.pal.make)
    d.disc(P(0.7, 0.3), 0.07, d.pal.make)
    for a, b in (((0.82, 0.06), (0.82, 0.3)), ((0.7, 0.18), (0.94, 0.18))):
        _mark(d, a, b, 0.045)


@draws("con_list")
def _list(d):
    for i, y in enumerate((0.24, 0.5, 0.76)):
        d.text(0.2, y + 0.08, "HV="[i], 0.18, d.pal.make)
        _ln(d, (0.36, y), (0.88, y), 0.055)


@draws("configurations")
def _configurations(d):
    """Three stacked sheets, the front one a small part: named variants
    of one design."""
    for i, k in enumerate((0.0, 0.1, 0.2)):
        d.poly([P(0.1 + k, 0.5 - k), P(0.62 + k, 0.5 - k),
                P(0.62 + k, 0.92 - k), P(0.1 + k, 0.92 - k)],
               d.pal.paper, color=d.pal.edge, width=0.04)
    d.box(0.42, 0.42, 0.0, 0.28, 0.28, 0.16)


@draws("sk_trim")
def _sk_trim(d):
    _ln(d, (0.1, 0.5), (0.9, 0.5))
    _ln(d, (0.32, 0.12), (0.32, 0.88))
    _ln(d, (0.68, 0.12), (0.68, 0.88))
    d.line(P(0.36, 0.5), P(0.64, 0.5), d.pal.cut, 0.09)
    _mark(d, (0.42, 0.36), (0.58, 0.64), 0.05)
    _mark(d, (0.42, 0.64), (0.58, 0.36), 0.05)


@draws("regions")
def _regions(d):
    """A rectangle and a circle at its end, the long part and the circle
    filled in the make colour (the regions picked), the far corners
    left empty."""
    from PyQt5.QtGui import QPainterPath
    keep = QPainterPath()
    keep.moveTo(P(0.08, 0.32))
    keep.lineTo(P(0.66, 0.32))
    keep.arcTo(QRectF(P(0.48, 0.32), P(0.84, 0.68)), 90, -180)
    keep.lineTo(P(0.08, 0.68))
    keep.closeSubpath()
    d.p.fillPath(keep, d.pal.make)
    _ln(d, (0.08, 0.32), (0.92, 0.32))
    _ln(d, (0.08, 0.68), (0.92, 0.68))
    _ln(d, (0.08, 0.32), (0.08, 0.68))
    _ln(d, (0.92, 0.32), (0.92, 0.68))


@draws("make_region")
def _make_region(d):
    """The rectangle-and-circle regions, outlined, the kept ones filled
    with a plus: a region made, not extruded."""
    _regions(d)
    d.line(P(0.72, 0.08), P(0.72, 0.26), d.pal.make, 0.07)
    d.line(P(0.63, 0.17), P(0.81, 0.17), d.pal.make, 0.07)


@draws("sk_extend")
def _sk_extend(d):
    _ln(d, (0.82, 0.1), (0.82, 0.9))
    _ln(d, (0.1, 0.55), (0.45, 0.55))
    d.line(P(0.45, 0.55), P(0.78, 0.55), d.pal.make, 0.05, [2, 2])
    d.arrow(P(0.5, 0.35), P(0.78, 0.35), d.pal.make, 0.05, 0.1)


@draws("sk_fillet")
def _sk_fillet(d):
    from PyQt5.QtGui import QPainterPath
    _ln(d, (0.14, 0.88), (0.14, 0.45))
    _ln(d, (0.55, 0.12), (0.88, 0.12))
    path = QPainterPath(P(0.14, 0.45))
    path.quadTo(P(0.14, 0.12), P(0.55, 0.12))
    d.path(path, color=d.pal.make, width=0.08)


@draws("sk_chamfer")
def _sk_chamfer(d):
    _ln(d, (0.14, 0.88), (0.14, 0.45))
    _ln(d, (0.55, 0.12), (0.88, 0.12))
    d.line(P(0.14, 0.45), P(0.55, 0.12), d.pal.make, 0.08)


@draws("con_delete")
def _con_delete(d):
    """A constraint mark (=) struck out in red."""
    _ln(d, (0.1, 0.78), (0.9, 0.78))
    d.text(0.42, 0.56, "=", 0.3, d.pal.make)
    d.line(P(0.18, 0.18), P(0.7, 0.66), d.pal.cut, 0.08)
    d.line(P(0.7, 0.18), P(0.18, 0.66), d.pal.cut, 0.08)


@draws("con_dimension")
def _con_dimension(d):
    """A line with a driving dimension over it."""
    _ln(d, (0.14, 0.8), (0.86, 0.8))
    _dim(d, (0.14, 0.8), (0.86, 0.8), (0, -0.42))
    d.text(0.5, 0.32, "25", 0.2, d.pal.make)


@draws("stop_select")
def _stop_select(d):
    """The selection arrow: stop whatever runs, back to selecting."""
    d.poly([P(0.28, 0.1), P(0.28, 0.78), P(0.43, 0.63), P(0.55, 0.9),
            P(0.66, 0.85), P(0.54, 0.58), P(0.76, 0.58)],
           d.pal.paper, color=d.pal.edge, width=0.06)


# ------------------------------------------------ the Cut features
# SolidWorks-like (the user's ribbon picture): a solid with the cut
# really taken out of it, the cut's faces in the cut colour


@draws("extruded_cut")
def _extruded_cut(d):
    """A block with a step cut out of its right half: the floor and the
    wall of the cut in the cut colour (SolidWorks' Extruded Cut)."""
    cut = d.pal.cut
    d.box(0.0, 0.0, 0.0, 1.6, 1.6, 0.5)
    d.poly([d.P(0.9, 0.0, 0.5), d.P(1.6, 0.0, 0.5), d.P(1.6, 1.6, 0.5),
            d.P(0.9, 1.6, 0.5)], cut, color=d.pal.edge, width=0.035)
    d.box(0.0, 0.0, 0.5, 0.9, 1.6, 0.6)
    d.poly([d.P(0.9, 0.0, 0.5), d.P(0.9, 1.6, 0.5), d.P(0.9, 1.6, 1.1),
            d.P(0.9, 0.0, 1.1)], cut, color=d.pal.edge, width=0.035)


@draws("revolved_cut")
def _revolved_cut(d):
    """A round bar with a deep groove turned into it."""
    d.cyl(0.0, 0.0, 0.0, 0.75, 0.5)
    d.cyl(0.0, 0.0, 0.5, 0.42, 0.4, d.pal.cut)            # the groove
    d.cyl(0.0, 0.0, 0.9, 0.75, 0.5)


@draws("swept_cut")
def _swept_cut(d):
    """A block with a curving channel cut along its top."""
    from PyQt5.QtGui import QPainterPath
    d.box(0.0, 0.0, 0.0, 1.6, 1.6, 0.7)
    path = QPainterPath(d.P(0.0, 0.4, 0.7))
    path.cubicTo(d.P(0.7, 0.3, 0.7), d.P(0.8, 1.3, 0.7),
                 d.P(1.6, 1.2, 0.7))
    d.p.setBrush(Qt.NoBrush)
    d.p.setPen(d.pen(d.pal.edge, 0.17))
    d.p.drawPath(path)
    d.p.setPen(d.pen(d.pal.cut, 0.11))
    d.p.drawPath(path)


@draws("lofted_cut")
def _lofted_cut(d):
    """A block with a pocket narrowing from a wide mouth to a small
    floor: its sloping far walls show."""
    cut = d.pal.cut
    d.box(0.0, 0.0, 0.0, 1.6, 1.6, 0.8)
    top = [d.P(x, y, 0.8) for x, y in ((0.25, 0.25), (1.35, 0.25),
                                      (1.35, 1.35), (0.25, 1.35))]
    low = [d.P(x, y, 0.2) for x, y in ((0.6, 0.6), (1.0, 0.6),
                                      (1.0, 1.0), (0.6, 1.0))]
    d.poly([top[3], top[2], low[2], low[3]], cut, color=d.pal.edge,
           width=0.03)                                    # far slope
    d.poly([top[0], top[3], low[3], low[0]], cut, color=d.pal.edge,
           width=0.03)                                    # left slope
    d.poly(low, cut, color=d.pal.edge, width=0.03)        # floor
    d.poly(top, None, color=d.pal.edge, width=0.04)       # the mouth


@draws("boundary_cut")
def _boundary_cut(d):
    """A block with its front corner scooped out by a curved surface."""
    from PyQt5.QtGui import QPainterPath
    d.box(0.0, 0.0, 0.0, 1.6, 1.6, 0.8)
    scoop = QPainterPath(d.P(1.6, 0.0, 0.8))
    scoop.lineTo(d.P(1.6, 0.9, 0.8))
    scoop.quadTo(d.P(1.0, 0.8, 0.5), d.P(0.7, 0.0, 0.8))
    scoop.closeSubpath()
    d.p.setPen(d.pen(d.pal.edge, 0.04))
    d.p.setBrush(d.pal.cut)
    d.p.drawPath(scoop)
    side = QPainterPath(d.P(1.6, 0.0, 0.8))
    side.lineTo(d.P(0.7, 0.0, 0.8))
    side.quadTo(d.P(1.1, 0.0, 0.25), d.P(1.6, 0.0, 0.25))
    side.closeSubpath()
    d.p.drawPath(side)

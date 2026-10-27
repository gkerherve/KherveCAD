"""Painted icons for Reference Geometry (2026-10-27): see-through planes
in the style's 'make' colour (SolidWorks blue, Fusion orange) beside the
part they are made from, dash-dot axes, point crosses. Original drawings
on icons_cad's unit square and helpers.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtCore import QPointF
from PyQt5.QtGui import QColor

from .icons_cad import draws, shade


def _plane(d, z, x=-1.0, y=-1.0, w=2.0, dp=2.0, color=None):
    """A see-through horizontal plane at height z."""
    c = QColor(color or d.pal.make)
    fill = QColor(c)
    fill.setAlpha(70)
    d.ground([(x, y), (x + w, y), (x + w, y + dp), (x, y + dp)],
             color=c, z=z, width=0.06, fill=fill)


def _vplane(d, x, color=None):
    """A see-through upright plane x = const."""
    c = QColor(color or d.pal.make)
    fill = QColor(c)
    fill.setAlpha(70)
    pts = [d.P(x, -1.0, -0.1), d.P(x, 1.0, -0.1), d.P(x, 1.0, 1.4),
           d.P(x, -1.0, 1.4)]
    d.poly(pts, fill, color=c, width=0.06)


def _axis(d, a, b):
    d.line(d.P(*a), d.P(*b), d.pal.make, 0.06, dash=[4, 2, 1, 2])


@draws("ref_plane_offset")
def _offset(d):
    """Plane offset from a face: a block, a plane floating above it."""
    d.box(-0.8, -0.8, 0, 1.6, 1.6, 0.6, shade(d.pal.body, 0.95))
    d.arrow(d.P(0.6, 0.6, 0.6), d.P(0.6, 0.6, 1.15), d.pal.select,
            0.05, 0.12)
    _plane(d, 1.25)


@draws("ref_plane_3pt")
def _three(d):
    """Plane through three points."""
    _plane(d, 0.5)
    for x, y in ((-0.6, -0.6), (0.7, -0.4), (-0.2, 0.7)):
        d.dot(d.P(x, y, 0.5), d.pal.select, 0.09, fill=d.pal.select)


@draws("ref_plane_angle")
def _angle(d):
    """Plane at an angle through an edge."""
    d.box(-0.9, -0.9, 0, 1.8, 1.8, 0.4, shade(d.pal.body, 0.95))
    c = QColor(d.pal.make)
    fill = QColor(c)
    fill.setAlpha(70)
    d.poly([d.P(-0.9, 0.9, 0.4), d.P(0.9, 0.9, 0.4), d.P(0.9, -0.2, 1.5),
            d.P(-0.9, -0.2, 1.5)], fill, color=c, width=0.06)
    d.line(d.P(-0.9, 0.9, 0.4), d.P(0.9, 0.9, 0.4), d.pal.select, 0.09)


@draws("ref_plane_parallel")
def _parallel(d):
    """Parallel to a main plane: two planes, one over the other."""
    _plane(d, 0.0, color=d.pal.sketch)
    _plane(d, 1.0)
    d.arrow(d.P(0.8, 0.8, 0.05), d.P(0.8, 0.8, 0.95), d.pal.select,
            0.05, 0.12)


@draws("ref_axis")
def _axis_round(d):
    """Axis of a round face."""
    d.cyl(0, 0, 0, 0.7, 0.9, shade(d.pal.body, 0.95))
    _axis(d, (0, 0, -0.5), (0, 0, 1.6))


@draws("ref_axis_planes")
def _axis_planes(d):
    """Axis where two planes meet."""
    _plane(d, 0.5, color=d.pal.sketch)
    _vplane(d, 0.0, color=d.pal.sketch)
    d.line(d.P(0, -1.2, 0.5), d.P(0, 1.2, 0.5), d.pal.make, 0.08,
           dash=[4, 2, 1, 2])


@draws("ref_point")
def _point(d):
    """Point."""
    d.box(-0.8, -0.8, 0, 1.6, 1.6, 0.8, shade(d.pal.body, 0.95))
    q = d.P(0.8, 0.8, 0.8)
    d.line(q + QPointF(-0.12, 0), q + QPointF(0.12, 0), d.pal.make, 0.06)
    d.line(q + QPointF(0, -0.12), q + QPointF(0, 0.12), d.pal.make, 0.06)
    d.dot(q, d.pal.make, 0.06)


@draws("ref_sketch3d")
def _sketch3d(d):
    """Sketch in 3D: a rectangle drawn on a plane."""
    _plane(d, 0.3)
    d.ground([(-0.5, -0.4), (0.6, -0.4), (0.6, 0.5), (-0.5, 0.5)],
             color=d.pal.sketch, z=0.3, width=0.08, dots=True)


@draws("ref_up_to_face")
def _up_to(d):
    """Extrude up to a face: a short block rising to a plane face."""
    d.box(-0.6, -0.6, 0, 1.2, 1.2, 0.7, shade(d.pal.body, 0.95))
    d.arrow(d.P(0, 0, 0.7), d.P(0, 0, 1.25), d.pal.make, 0.07, 0.15)
    _plane(d, 1.35, color=d.pal.select)


@draws("ref_measure")
def _measure(d):
    """Measure: two points joined, a ruler."""
    d.box(-0.9, -0.5, 0, 1.8, 1.0, 0.5, shade(d.pal.body, 0.95))
    a, b = d.P(-0.9, -0.5, 0.5), d.P(0.9, -0.5, 0.5)
    d.line(a, b, d.pal.make, 0.07)
    d.dot(a, d.pal.make, 0.07, fill=d.pal.make)
    d.dot(b, d.pal.make, 0.07, fill=d.pal.make)


@draws("ref_show_planes")
def _show(d):
    """Show the main planes: three planes through the origin."""
    _plane(d, 0.5, color=d.pal.sketch)
    _vplane(d, 0.0)
    c = QColor(d.pal.select)
    fill = QColor(c)
    fill.setAlpha(60)
    d.poly([d.P(-1.0, 0.0, -0.1), d.P(1.0, 0.0, -0.1), d.P(1.0, 0.0, 1.4),
            d.P(-1.0, 0.0, 1.4)], fill, color=c, width=0.06)

"""Coloured projected faces for the 2D views: what a part looks like
seen straight along one axis, in its own colours, painted far -> near
(a painter's order along the viewing axis) — so the sketch/assembly
view reads like the 3D one instead of one flat translucent blob, and
the House Builder's floor plan shows every piece of furniture at its
real size and shape from above.

`plan_faces` turns a coloured triangle soup (`mesh.tessellate_colored`)
into painter-ordered (polygon, colour) pairs; `paint_faces` draws them.
`part_view` renders a Part Library part's top view once into a cached
picture plus its outline, which is what the floor-plan canvas paints
(cheap at any zoom, however many triangles the part has).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import json
import math
from dataclasses import dataclass
from functools import lru_cache

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import (QColor, QImage, QPainter, QPainterPath, QPen,
                         QPolygonF)

#: colour of a face no color() node paints
DEFAULT_FACE = "#b8a88f"

#: per 2D plane, the viewing axis and the sign that sorts faces far ->
#: near: Top looks down -Z (low z is far), Front looks along +Y from -Y
#: (high y is far), Side looks along -X from +X (low x is far)
DEPTH = {"Top (XY)": (2, 1.0), "Front (XZ)": (1, -1.0),
         "Side (YZ)": (0, 1.0)}

#: a face seen edge-on is dimmed down to this; one facing the viewer
#: keeps its full colour — enough shading to tell a seat from its arms
SHADE_MIN = 0.72

#: part pictures: resolution, capped so a big part stays a small image
PICTURE_PX_PER_MM = 0.35
MAX_PICTURE_PX = 900


def face_color(colour) -> QColor:
    """QColor of a tessellated face's ``(colour, alpha[, material])``
    (None: the default). The colour is a "#rrggbb" / SVG name string or
    an [r, g, b] list of 0..1 floats, like OpenSCAD's color()."""
    if colour is None:
        return QColor(DEFAULT_FACE)
    value = colour[0]
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        try:
            c = QColor.fromRgbF(*(max(0.0, min(1.0, float(v)))
                                  for v in value[:3]))
        except (TypeError, ValueError):
            c = QColor(DEFAULT_FACE)
    else:
        c = QColor(str(value))
        if not c.isValid():
            c = QColor(DEFAULT_FACE)
    try:
        alpha = float(colour[1])
    except (IndexError, TypeError, ValueError):
        alpha = 1.0
    c.setAlphaF(max(0.0, min(1.0, alpha)))
    return c


def plan_faces(colored, plane="Top (XY)", cut=None):
    """Painter-ordered ``[(QPolygonF, QColor)]`` of *colored* triangles
    ``[(tri, colour)]`` projected into *plane*: faces seen edge-on are
    dropped, the rest shaded by how squarely they face the viewer and
    sorted far -> near. With *cut* (Top only) a face lying wholly above
    z = *cut* is left out — a floor plan's cut, which is what lets a
    house's rooms show under its roof."""
    from .view2d import PLANES
    (ai, bi), _keys = PLANES[plane]
    di, sign = DEPTH[plane]
    cache = {}
    out = []
    for tri, colour in colored:
        if cut is not None and min(v[2] for v in tri) >= cut:
            continue
        (x0, y0), (x1, y1), (x2, y2) = ((v[ai], v[bi]) for v in tri)
        area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
        if abs(area) < 1e-6:
            continue                      # edge-on: nothing to see
        a, b, c = tri
        u = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
        v = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
        n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2],
             u[0] * v[1] - u[1] * v[0])
        length = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2) or 1.0
        lit = SHADE_MIN + (1.0 - SHADE_MIN) * abs(n[di]) / length
        key = (colour if colour is None else
               (str(colour[0]), colour[1] if len(colour) > 1 else 1.0),
               round(lit, 2))
        col = cache.get(key)
        if col is None:
            col = face_color(colour)
            if lit < 0.999:
                col = col.darker(int(100.0 / lit))
            cache[key] = col
        depth = sign * (a[di] + b[di] + c[di]) / 3.0
        poly = QPolygonF([QPointF(x0, y0), QPointF(x1, y1),
                          QPointF(x2, y2)])
        out.append((depth, len(out), poly, col))
    out.sort(key=lambda f: (f[0], f[1]))
    return [(poly, col) for _d, _i, poly, col in out]


def paint_faces(painter, faces):
    """Draw *faces* (from `plan_faces`) in order. An opaque face also
    gets a hairline in its own colour: without it the antialiased
    seams between neighbouring triangles show as a faint mesh."""
    painter.save()
    for poly, col in faces:
        if col.alpha() == 255:
            pen = QPen(col, 0)
            pen.setCosmetic(True)
            painter.setPen(pen)
        else:
            painter.setPen(Qt.NoPen)
        painter.setBrush(col)
        painter.drawPolygon(poly)
    painter.restore()


def faces_outline(faces) -> QPainterPath:
    """The filled outline of *faces*: every projected triangle turned
    the same way round under a winding fill (so front and back faces
    add up instead of cancelling), then merged into one path."""
    path = QPainterPath()
    path.setFillRule(Qt.WindingFill)
    for poly, _col in faces:
        p0, p1, p2 = poly[0], poly[1], poly[2]
        area = ((p1.x() - p0.x()) * (p2.y() - p0.y())
                - (p2.x() - p0.x()) * (p1.y() - p0.y()))
        path.addPolygon(poly if area >= 0 else QPolygonF([p0, p2, p1]))
        path.closeSubpath()
    return path.simplified()


@dataclass
class PartView:
    """A part's top view: *rect* (mm, the part's own frame, Y up),
    *image* (the coloured faces rendered once, row 0 at rect.top()),
    *outline* (its silhouette, for a crisp edge at any zoom)."""
    rect: QRectF
    image: QImage
    outline: QPainterPath


def part_view(part_id, dims):
    """The cached top view of Part Library part *part_id* built with
    *dims* (as `library.build_part` takes them), or None when it has no
    geometry seen from above."""
    key = json.dumps(dims or {}, sort_keys=True, default=str)
    return _part_view(part_id, key)


@lru_cache(maxsize=256)
def _part_view(part_id, dims_key):
    from . import library, mesh
    node = library.build_part(part_id, json.loads(dims_key))
    faces = plan_faces(mesh.tessellate_colored(node, fn=16))
    if not faces:
        return None
    rect = QRectF()
    for poly, _col in faces:
        rect = rect.united(poly.boundingRect())
    if rect.width() < 1e-6 or rect.height() < 1e-6:
        return None
    scale = min(PICTURE_PX_PER_MM,
                MAX_PICTURE_PX / max(rect.width(), rect.height()))
    w = max(2, int(math.ceil(rect.width() * scale)))
    h = max(2, int(math.ceil(rect.height() * scale)))
    image = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    # no Y flip: row 0 is rect.top() (the lowest y), matching how the
    # Y-up canvas maps the picture's rectangle back
    painter.scale(w / rect.width(), h / rect.height())
    painter.translate(-rect.left(), -rect.top())
    paint_faces(painter, faces)
    painter.end()
    return PartView(rect, image, faces_outline(faces))

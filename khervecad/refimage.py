"""Reference images: a photo or drawing behind the model, to match or
trace — the fork photos a model is checked against, a character sheet
to sculpt to, a scanned part to measure from.

An image lies on one of the three axis planes (the 2D view's Top /
Front / Side), with its lower-left corner at (x, y) on that plane and
a width in millimetres; its height follows the picture's aspect. The
sketch view draws it under the grid while that plane is showing; the
3D view draws it on its plane behind the model, in true perspective
(QTransform.quadToQuad is projective, so a planar quad maps exactly).

The images live in the document (DocumentModel.reference_images) —
saved in .kcad and undoable like any edit.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os

from PyQt5.QtCore import QPointF
from PyQt5.QtGui import QImage, QPolygonF, QTransform

#: plane -> (horizontal axis, vertical axis, normal axis), as indices
#: into (x, y, z) — the 2D view's planes
PLANES = {"Top (XY)": (0, 1, 2), "Front (XZ)": (0, 2, 1),
          "Side (YZ)": (1, 2, 0)}

_CACHE = {}


def load(path):
    """The picture at *path* (cached while the file is unchanged), or
    None when it cannot be read."""
    try:
        stamp = os.path.getmtime(path)
    except (OSError, TypeError):
        return None
    key = (path, stamp)
    image = _CACHE.get(key)
    if image is None:
        image = QImage(path)
        if image.isNull():
            return None
        if len(_CACHE) > 8:
            _CACHE.clear()
        _CACHE[key] = image
    return image


def aspect(path):
    """height / width of the picture, or None when it cannot be read."""
    image = load(path)
    if image is None or image.width() < 1:
        return None
    return image.height() / image.width()


def corners(ref) -> list:
    """World points of the picture's lower-left, lower-right,
    upper-right and upper-left corners."""
    u, v, n = PLANES.get(ref.get("plane"), PLANES["Top (XY)"])
    x, y = float(ref.get("x", 0.0)), float(ref.get("y", 0.0))
    w, h = float(ref.get("width", 100.0)), float(ref.get("height", 100.0))
    out = []
    for du, dv in ((0.0, 0.0), (w, 0.0), (w, h), (0.0, h)):
        p = [0.0, 0.0, 0.0]
        p[u], p[v], p[n] = x + du, y + dv, float(ref.get("offset", 0.0))
        out.append(tuple(p))
    return out


def draw_2d(painter, refs, plane):
    """Draw the references on *plane* into the sketch view's painter
    (scene coordinates, Y up)."""
    for ref in refs:
        if not ref.get("visible", True) or ref.get("plane") != plane:
            continue
        image = load(ref.get("path", ""))
        if image is None:
            continue
        x, y = float(ref.get("x", 0.0)), float(ref.get("y", 0.0))
        w, h = float(ref.get("width", 100.0)), float(ref.get("height", 100.0))
        painter.save()
        painter.setOpacity(float(ref.get("opacity", 0.5)))
        # the scene is Y-up and a picture is Y-down: flip it upright
        painter.translate(x, y + h)
        painter.scale(w / image.width(), -h / image.height())
        painter.drawImage(0, 0, image)
        painter.restore()


def draw_3d(painter, refs, project):
    """Draw the references on their planes through *project* (world
    point -> (x, y, depth) on screen, or None behind the camera)."""
    for ref in refs:
        if not ref.get("visible", True):
            continue
        image = load(ref.get("path", ""))
        if image is None:
            continue
        pts = [project(c) for c in corners(ref)]
        if any(p is None for p in pts):
            continue
        w, h = image.width(), image.height()
        # image space is Y-down: its lower-left corner is (0, h)
        src = QPolygonF([QPointF(0, h), QPointF(w, h), QPointF(w, 0),
                         QPointF(0, 0)])
        dst = QPolygonF([QPointF(p[0], p[1]) for p in pts])
        transform = QTransform()
        if not QTransform.quadToQuad(src, dst, transform):
            continue
        painter.save()
        painter.setOpacity(float(ref.get("opacity", 0.5)))
        painter.setTransform(transform, True)
        painter.drawImage(0, 0, image)
        painter.restore()

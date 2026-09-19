"""Orthographic pictures of a figure for the Human Builder: Front, Side
(from the figure's left) and Back, each its coloured faces projected and
painted far to near (`planview`), all at ONE scale so the three views
line up, on a floor line with the height written beside it.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from PyQt5.QtCore import QPointF
from PyQt5.QtGui import QColor, QFont, QImage, QPainter, QPen, QTransform

from . import planview

VIEWS = ("Front", "Side", "Back")
_PLANE = {"Front": "Front (XZ)", "Side": "Side (YZ)", "Back": "Front (XZ)"}
_AXES = {"Front": (0, 2), "Side": (1, 2), "Back": (0, 2)}


def _turned(colored, view):
    if view != "Back":
        return colored
    return [(tuple((-v[0], -v[1], v[2]) for v in tri), colour)
            for tri, colour in colored]


def extent(colored):
    """(half width across any view, lowest z, highest z) of the faces."""
    if not colored:
        return 500.0, 0.0, 1800.0
    xs = [abs(v[i]) for tri, _c in colored for v in tri for i in (0, 1)]
    zs = [v[2] for tri, _c in colored for v in tri]
    return max(xs), min(zs), max(zs)


def render(colored, view, width, height, background="#2b2e33",
           scale=None, frame=None):
    """A QImage of *colored* ``[(tri, colour)]`` seen from *view*. With
    *frame* (from `extent`) several views share one scale."""
    image = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
    image.fill(QColor(background))
    half, lo, hi = frame or extent(colored)
    span_h = max(hi - lo, 1.0) * 1.08
    span_w = max(2.0 * half, 1.0) * 1.08
    k = scale or min((width - 16) / span_w, (height - 30) / span_h)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    floor = height - 22
    ground = QPen(QColor("#6b7078"), 1)
    painter.setPen(ground)
    painter.drawLine(8, floor, width - 8, floor)
    faces = planview.plan_faces(_turned(colored, view), _PLANE[view])
    painter.setTransform(QTransform(k, 0, 0, -k, width / 2.0,
                                    floor + lo * k))
    planview.paint_faces(painter, faces)
    painter.resetTransform()
    painter.setPen(QColor("#c9ccd1"))
    font = QFont()
    font.setPointSize(9)
    painter.setFont(font)
    painter.drawText(QPointF(8, 14), view)
    if view == "Front":
        painter.drawText(QPointF(8, height - 6),
                         f"{(hi - lo) / 1000.0:.2f} m")
    painter.end()
    return image


def render_all(colored, width, height, background="#2b2e33"):
    """The three views side by side at one scale: {view: QImage}."""
    frame = extent(colored)
    return {view: render(colored, view, width, height, background,
                         frame=frame) for view in VIEWS}

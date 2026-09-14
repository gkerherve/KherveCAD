"""The 3D view's **scale bar**: a round length (1, 2 or 5 x 10^k) drawn
bottom-left in the document's unit, the way the 2D view has one.

A perspective picture has no single scale — nearer things are drawn
bigger — so the bar is true at the depth of the orbit centre (the
view's `target`, the point the camera turns about and zooms towards);
in orthographic it is true everywhere. Both cases are the view's focal
length over the camera distance, which is exactly what `View3D._project`
uses there.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from PyQt5.QtCore import QPointF
from PyQt5.QtGui import QColor, QPen

from . import units

#: the bar is drawn between these many pixels long; 1-2-5 steps are at
#: most x2.5 apart and 170 / 60 > 2.5, so one length always fits
MIN_PX, MAX_PX = 60, 170
#: from the bottom-left corner, clear of the source badge under it
MARGIN_X, MARGIN_BOTTOM = 14, 30


def px_per_unit(view) -> float:
    """Pixels per model unit at the orbit centre."""
    return view._focal() / max(view.distance, 1e-6)


def nice_length(ppu: float, lo: float = MIN_PX, hi: float = MAX_PX):
    """The shortest 1, 2 or 5 x 10^k model units whose bar is *lo* to
    *hi* pixels long at *ppu* pixels per unit; None if *ppu* is not a
    positive number."""
    if not ppu or ppu <= 0 or not math.isfinite(ppu):
        return None
    k = math.floor(math.log10(lo / ppu))
    for exp in range(k - 1, k + 3):
        for m in (1, 2, 5):
            length = round(m * 10.0 ** exp, 12 - exp)
            if lo <= length * ppu <= hi:
                return length
    return None


def label(length: float, unit) -> str:
    """"20 nm", "0.5 µm", "250 mm"."""
    return f"{units.tidy(length, 9)} {units.symbol(unit)}"


def draw(painter, width, height, ppu, unit, color):
    """Paint the bar bottom-left of a *width* x *height* view; returns
    the length drawn (model units), or None when there is none."""
    length = nice_length(ppu)
    if not length:
        return None
    px = length * ppu
    x0, y0 = float(MARGIN_X), float(height - MARGIN_BOTTOM)
    painter.save()
    painter.setPen(QPen(QColor(color), 1.6))
    painter.drawLine(QPointF(x0, y0), QPointF(x0 + px, y0))
    for x in (x0, x0 + px):
        painter.drawLine(QPointF(x, y0 - 5), QPointF(x, y0 + 5))
    text = label(length, unit)
    advance = painter.fontMetrics().horizontalAdvance(text)
    painter.drawText(QPointF(x0 + px / 2 - advance / 2, y0 - 8), text)
    painter.restore()
    return length

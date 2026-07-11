"""Toolbar icon helpers — qtawesome MDI glyphs with graceful fallback.

Same icon system as the rest of the Kherve family: themed Material
Design icons via qtawesome. When qtawesome is missing the actions
fall back to their text labels, so the app still works.

The window/taskbar mark is hand-painted (like KherveBook): a rounded
slate tile with a 'KCAD' wordmark above a small isometric cube, drawn
as stroked vector paths so it renders identically on every platform.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import (QColor, QIcon, QPainter, QPainterPath, QPen,
                         QPixmap, QTransform)

try:
    import qtawesome as qta
except ImportError:          # pragma: no cover - optional dependency
    qta = None

#: Brand colours: KherveFitting-family "Python blue" + the "CAD" orange.
_CAD_BLUE = "#3776ab"
_CAD_ORANGE = "#e07b39"

#: Glyph colour for neutral icons — set by the active theme.
DEFAULT_COLOR = "#444444"


def set_icon_color(color: str):
    """Called by style.apply_style so icons follow the theme."""
    global DEFAULT_COLOR
    DEFAULT_COLOR = color


def icon(name: str, color: str = None) -> QIcon:
    """Return the qtawesome icon *name* (e.g. "mdi.cube-outline"), or a
    null icon if qtawesome is unavailable."""
    if qta is None:
        return QIcon()
    try:
        return qta.icon(name, color=color or DEFAULT_COLOR)
    except Exception:
        return QIcon()


#: The app mark sits on a rounded square tinted from the Slate theme
#: (the default): a light slate tile with a slightly darker slate edge.
_SLATE_FILL = "#d5dbe3"
_SLATE_EDGE = "#b9c1cc"

# The letters are drawn as stroked vector paths (not text) so the mark
# renders identically on every platform and without depending on any
# system font being installed. Each glyph builder works in a unit box
# (0..1 in x and y) and is transformed into place by the caller.


def _glyph_K() -> tuple[QPainterPath, float]:
    """Uppercase K in a unit-height box. Returns (path, advance width)."""
    w = 0.82
    path = QPainterPath()
    path.moveTo(0.0, 0.0); path.lineTo(0.0, 1.0)          # stem
    path.moveTo(0.0, 0.52); path.lineTo(w, 0.0)           # upper arm
    path.moveTo(0.0, 0.52); path.lineTo(w, 1.0)           # lower arm
    return path, w


def _glyph_C() -> tuple[QPainterPath, float]:
    """Uppercase C as an open arc in a unit-height box."""
    w = 0.80
    path = QPainterPath()
    # Arc opening to the right: start upper-right, sweep round the left.
    rect = QRectF(0.0, 0.0, w, 1.0)
    path.arcMoveTo(rect, 55)
    path.arcTo(rect, 55, 250)
    return path, w


def _glyph_A() -> tuple[QPainterPath, float]:
    """Uppercase A: two legs meeting at the apex plus a crossbar."""
    w = 0.86
    path = QPainterPath()
    path.moveTo(0.0, 1.0); path.lineTo(w / 2.0, 0.0)      # left leg
    path.lineTo(w, 1.0)                                    # right leg
    path.moveTo(w * 0.18, 0.62); path.lineTo(w * 0.82, 0.62)  # crossbar
    return path, w


def _glyph_D() -> tuple[QPainterPath, float]:
    """Uppercase D: a stem closed by one large bowl."""
    w = 0.78
    path = QPainterPath()
    path.moveTo(0.0, 0.0); path.lineTo(0.0, 1.0)          # stem
    path.moveTo(0.0, 0.0)
    path.cubicTo(w * 1.55, 0.02, w * 1.55, 0.98, 0.0, 1.0)  # bowl
    return path, w


def _stroke(p: QPainter, path: QPainterPath, color: str,
            box: QRectF, weight: float):
    """Draw *path* (defined in a unit box) mapped into *box* and
    stroked in *color*. The path is transformed into device space
    first, then stroked with a uniform pen (width = *weight* of the
    box height in pixels) so vertical and horizontal strokes stay the
    same thickness even when the box isn't square."""
    t = QTransform()
    t.translate(box.x(), box.y())
    t.scale(box.width(), box.height())
    mapped = t.map(path)
    pen = QPen(QColor(color))
    pen.setWidthF(weight * box.height())
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawPath(mapped)


def _paint_slate_tile(p: QPainter, s: float) -> QRectF:
    """Fill a rounded-square slate tile covering the icon, and return the
    inner rectangle the wordmark is laid out in."""
    m = s * 0.06                       # outer margin
    radius = s * 0.22                  # corner rounding
    rect = QRectF(m, m, s - 2 * m, s - 2 * m)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(_SLATE_FILL))
    p.drawRoundedRect(rect, radius, radius)
    pen = QPen(QColor(_SLATE_EDGE))
    pen.setWidthF(max(1.0, s * 0.02))
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(rect, radius, radius)
    return rect


def _paint_wordmark(p: QPainter, rect: QRectF):
    """Draw 'KCAD' on a single baseline inside *rect*, scaled to fill
    the tile in the same black ink as the cube below."""
    ink = "#000000"                    # black letters on the slate tile
    items = [_glyph_K(), _glyph_C(), _glyph_A(), _glyph_D()]
    gap = 0.14
    total = sum(w for _path, w in items) + gap * (len(items) - 1)
    # Cap-height: as tall as the tile allows, but not so wide it overflows.
    pad_x, pad_y = rect.width() * 0.13, rect.height() * 0.20
    ch = min(rect.height() - 2 * pad_y, (rect.width() - 2 * pad_x) / total)
    word_w = total * ch
    x = rect.x() + (rect.width() - word_w) / 2.0
    top = rect.y() + (rect.height() - ch) / 2.0
    weight = 0.16
    for path, gw in items:
        _stroke(p, path, ink, QRectF(x, top, gw * ch, ch), weight)
        x += (gw + gap) * ch


def _paint_cube(p: QPainter, box: QRectF):
    """Stroke a small isometric wireframe cube inside *box* — the CAD
    mark: an outer hexagon with three inner edges meeting at the centre,
    the blue front faces picked out from the orange top."""
    # Hexagon vertices of an isometric cube (unit box, y grows downward).
    top = (0.50, 0.02)
    ur, lr = (0.97, 0.27), (0.97, 0.73)
    bot = (0.50, 0.98)
    ll, ul = (0.03, 0.73), (0.03, 0.27)
    ctr = (0.50, 0.50)

    outer = QPainterPath()
    outer.moveTo(*top)
    for pt in (ur, lr, bot, ll, ul):
        outer.lineTo(*pt)
    outer.closeSubpath()

    inner = QPainterPath()
    inner.moveTo(*ul); inner.lineTo(*ctr)          # top-left edge to centre
    inner.moveTo(*ur); inner.lineTo(*ctr)          # top-right edge to centre
    inner.moveTo(*ctr); inner.lineTo(*bot)         # vertical front edge

    _stroke(p, outer, _CAD_BLUE, box, weight=0.06)
    _stroke(p, inner, _CAD_BLUE, box, weight=0.06)


def _paint_kcad(size: int) -> QPixmap:
    """Draw the KherveCAD mark on a rounded slate tile: the 'KCAD'
    wordmark above a small isometric cube, at every size."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    s = float(size)
    rect = _paint_slate_tile(p, s)
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    _paint_wordmark(p, QRectF(x, y + h * 0.06, w, h * 0.40))   # upper half
    cw, chh = w * 0.42, h * 0.40
    _paint_cube(p, QRectF(x + (w - cw) / 2.0, y + h * 0.54, cw, chh))
    p.end()
    return pm


def app_icon() -> QIcon:
    """Window/taskbar icon: the 'KCAD' wordmark above an isometric cube
    on a rounded slate tile, rendered at each standard size."""
    ic = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        ic.addPixmap(_paint_kcad(size))
    return ic

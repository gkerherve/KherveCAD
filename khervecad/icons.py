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


#: one colour per toolbar family, so the bars are not a wall of grey:
#: (light-theme colour, dark-theme colour)
FAMILY_COLORS = {
    "draw": ("#00897b", "#4db6ac"),        # 2D drawing tools
    "measure": ("#8e24aa", "#ce93d8"),
    "build": ("#ef6c00", "#ffb74d"),       # builders (house)
    "extrude": ("#1e88e5", "#64b5f6"),
    "transform": ("#3949ab", "#9fa8da"),
    "combine": ("#e53935", "#ef9a9a"),
    "finish": ("#f57c00", "#ffcc80"),
    "deform": ("#8e24aa", "#ce93d8"),
    "character": ("#d81b60", "#f48fb1"),
    "logic": ("#43a047", "#a5d6a7"),
    "docs": ("#00838f", "#80deea"),        # Blueprint, BOM, P&ID
    "edit": ("#5e35b1", "#b39ddb"),
    "brand": (_CAD_ORANGE, _CAD_ORANGE),
}


def family_color(family: str) -> str:
    """The colour for icons of *family*, light or dark by the theme
    (judged from the theme's own icon colour)."""
    pair = FAMILY_COLORS.get(family)
    if pair is None:
        return DEFAULT_COLOR
    c = QColor(DEFAULT_COLOR)
    dark_theme = c.lightness() > 140        # light glyphs = a dark theme
    return pair[1] if dark_theme else pair[0]


def set_icon_color(color: str):
    """Called by style.apply_style so icons follow the theme."""
    global DEFAULT_COLOR
    DEFAULT_COLOR = color


def icon(name: str, color: str = None) -> QIcon:
    """Return the qtawesome icon *name* (e.g. "mdi.cube-outline"), or a
    null icon if qtawesome is unavailable."""
    if name.startswith("kc."):           # a painted solid (icons_solid)
        from . import icons_solid
        return icons_solid.icon(name[3:]) or QIcon()
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


def _iso(x, y, z, scale, ox, oy):
    """Isometric screen point: x right-down, y left-down, z up."""
    return (ox + (x - y) * 0.866 * scale,
            oy + ((x + y) * 0.5 - z) * scale)


def _paint_part(p: QPainter, s: float, ox: float, oy: float):
    """A machined L-bracket in shaded metal with a drilled hole — the
    mark's centre: what a CAD program makes."""
    from PyQt5.QtCore import QPointF
    from PyQt5.QtGui import QLinearGradient, QPolygonF
    # (x0, y0, z0, x1, y1, z1): a base plate and an upright at the back
    boxes = [(0.0, 0.0, 0.0, 2.6, 2.0, 0.7),
             (0.0, 0.0, 0.7, 0.75, 2.0, 2.4)]
    shade = {"top": ("#f4f5f7", "#c9cdd3"), "x": ("#b4b9c1", "#8a9099"),
             "y": ("#7c828c", "#565b63")}
    faces = []
    for x0, y0, z0, x1, y1, z1 in boxes:
        faces += [
            ("top", [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]),
            ("x", [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)]),
            ("y", [(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)])]
    faces.sort(key=lambda f: sum(a + b + c for a, b, c in f[1]))
    edge = QPen(QColor("#2b2e33"))
    edge.setWidthF(max(0.6, s * 0.006))
    edge.setJoinStyle(Qt.RoundJoin)
    for kind, pts in faces:
        poly = QPolygonF([QPointF(*_iso(*pt, s, ox, oy)) for pt in pts])
        r = poly.boundingRect()
        g = QLinearGradient(r.topLeft(), r.bottomRight())
        g.setColorAt(0, QColor(shade[kind][0]))
        g.setColorAt(1, QColor(shade[kind][1]))
        p.setPen(edge)
        p.setBrush(g)
        p.drawPolygon(poly)
    # the drilled hole in the base plate's top face
    import math
    hole = QPolygonF([QPointF(*_iso(1.75 + 0.42 * math.cos(t),
                                    1.0 + 0.42 * math.sin(t), 0.7,
                                    s, ox, oy))
                      for t in [i * math.pi / 24 for i in range(48)]])
    hg = QLinearGradient(hole.boundingRect().topLeft(),
                         hole.boundingRect().bottomLeft())
    hg.setColorAt(0, QColor("#1d1f23"))
    hg.setColorAt(1, QColor("#4b5058"))
    p.setBrush(hg)
    p.drawPolygon(hole)


def _paint_kcad(size: int) -> QPixmap:
    """The KherveCAD mark (2026-10-21, the user: "more like SolidWorks,
    more evolved"): an ORIGINAL design, not SolidWorks' logo — a deep red
    rounded tile with a soft highlight, a shaded machined bracket in
    metal, and the KCAD wordmark under it from 48 px up."""
    from PyQt5.QtGui import QLinearGradient, QRadialGradient
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    s = float(size)
    m = s * 0.05
    rect = QRectF(m, m, s - 2 * m, s - 2 * m)
    radius = s * 0.2
    g = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    g.setColorAt(0.0, QColor("#e2343a"))
    g.setColorAt(1.0, QColor("#8c0f16"))
    p.setPen(Qt.NoPen)
    p.setBrush(g)
    p.drawRoundedRect(rect, radius, radius)
    glow = QRadialGradient(rect.center().x(), rect.top() + rect.height()
                           * 0.25, rect.width() * 0.7)
    glow.setColorAt(0, QColor(255, 255, 255, 70))
    glow.setColorAt(1, QColor(255, 255, 255, 0))
    p.setBrush(glow)
    p.drawRoundedRect(rect, radius, radius)
    rim = QPen(QColor(90, 0, 6, 180))
    rim.setWidthF(max(1.0, s * 0.012))
    p.setPen(rim)
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(rect, radius, radius)
    words = size >= 48
    # the part spans 4.0 x 4.7 iso units (x - y from -2 to 2.6, height
    # from the upright's top to the plate's front corner)
    area_top = rect.top() + rect.height() * (0.09 if words else 0.1)
    area_h = rect.height() * (0.6 if words else 0.8)
    unit = area_h / 4.7
    cx = rect.center().x() - 0.26 * unit
    _paint_part(p, unit, cx, area_top + 2.4 * unit)
    if words:
        _paint_wordmark_white(p, QRectF(rect.x(), rect.y() + rect.height()
                                        * 0.72, rect.width(),
                                        rect.height() * 0.22))
    p.end()
    return pm


def _paint_wordmark_white(p: QPainter, rect: QRectF):
    """'KCAD' in a bold sans, white, with a faint shadow."""
    from PyQt5.QtGui import QFont
    font = QFont("Helvetica Neue")
    font.setStyleHint(QFont.SansSerif)
    font.setWeight(QFont.Black)
    font.setPixelSize(max(6, int(rect.height() * 0.95)))
    font.setLetterSpacing(QFont.PercentageSpacing, 104)
    path = QPainterPath()
    path.addText(0, 0, font, "KCAD")
    box = path.boundingRect()
    k = min(rect.width() * 0.78 / box.width(),
            rect.height() * 0.82 / box.height())
    from PyQt5.QtGui import QTransform
    t = QTransform()
    t.translate(rect.center().x(), rect.center().y())
    t.scale(k, k)
    t.translate(-box.center().x(), -box.center().y())
    path = t.map(path)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(60, 0, 4, 120))
    p.drawPath(path.translated(0, max(1.0, rect.height() * 0.05)))
    p.setBrush(QColor("#ffffff"))
    p.drawPath(path)


def app_icon() -> QIcon:
    """Window/taskbar icon: the 'KCAD' wordmark above an isometric cube
    on a rounded slate tile, rendered at each standard size."""
    ic = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        ic.addPixmap(_paint_kcad(size))
    return ic

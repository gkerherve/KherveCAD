"""The Blueprint sheet's items: the paper's frame and title block, the
placed views, and every annotation — dimensions, notes, balloons,
datums, geometric tolerances, surface finish, centre marks, sketch
lines and the parts list.

Every annotation describes itself as a handful of PRIMITIVES — lines,
polygons, circles, arcs and text — in its own coordinates. The same list
is painted on screen, printed into the PDF/SVG through Qt and written to
the DXF (`blueprint_export`), so the three can never disagree.

Anchored annotations are CHILDREN of the view they measure and keep
their points in that view's MODEL coordinates (u, v in mm): moving or
rescaling the view carries them along, and a dimension's number is the
model's distance, never a measurement of the paper.

Sheet coordinates are millimetres, origin at the paper's top-left
corner, y DOWN (Qt's way); a view's local frame puts its model bounds'
lower-left corner at the origin, so its content spans y in [-h, 0].

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import (QColor, QFont, QFontMetricsF, QPainterPath,
                         QPainterPathStroker, QPen, QPolygonF, QTransform)
from PyQt5.QtWidgets import QGraphicsItem

from . import drawing

# ── the look ───────────────────────────────────────────────────────

#: colour roles per sheet style
STYLES = {
    "paper": dict(ground="#ffffff", ink="#141414", faint="#6a6a6a",
                  dim="#141414", hatch="#4a4a4a", grid="",
                  select="#e8741e"),
    "blueprint": dict(ground="#1d4b87", ink="#f3f7ff", faint="#b7cbea",
                      dim="#eaf2ff", hatch="#b7cbea", grid="#2b5c9b",
                      select="#ffb347"),
}
STYLE_NAMES = {"paper": "White paper", "blueprint": "Blueprint blue"}

#: line kinds: (width mm, dash pattern mm or None, colour role) — ISO
#: 128 weights: 0.5 visible, 0.25 thin, 0.35 hidden, chain for centres
LINES = {
    "frame": (0.7, None, "ink"),
    "visible": (0.5, None, "ink"),
    "thin": (0.25, None, "ink"),
    "hidden": (0.3, (3.0, 1.5), "ink"),
    "center": (0.25, (8.0, 1.5, 1.5, 1.5), "ink"),
    "dim": (0.25, None, "dim"),
    "hatch": (0.18, None, "hatch"),
    "cut": (0.6, (10.0, 2.0, 2.0, 2.0), "ink"),
    "label": (0.18, None, "faint"),
}
#: text kinds -> colour role
TEXT_ROLES = {"text": "ink", "dim": "dim", "label": "faint",
              "title": "ink"}

ARROW_L, ARROW_W = 3.0, 1.0          # closed filled arrow, 3 : 1
EXT_GAP, EXT_OVER = 1.0, 2.0         # extension line: gap, overshoot
TEXT = 3.5                           # annotation text height (mm)
TEXT_GAP = 1.0                       # text above its dimension line
FONT_FAMILY = "Arial"


class Look:
    """The sheet style every item paints in (one per scene)."""

    def __init__(self, style="paper"):
        self.style = style if style in STYLES else "paper"
        self.exporting = False

    def color(self, role):
        return QColor(STYLES[self.style].get(role) or "#000000")

    def pen(self, kind, color=None, widen=0.0):
        width, dash, role = LINES.get(kind, LINES["thin"])
        width += widen
        pen = QPen(color if color is not None else self.color(role), width,
                   Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        if dash and not widen:
            pen.setCapStyle(Qt.FlatCap)
            pen.setDashPattern([d / width for d in dash])
        return pen

    def text_color(self, kind):
        return self.color(TEXT_ROLES.get(kind, "ink"))


DEFAULT_LOOK = Look()


# ── text as outlines ───────────────────────────────────────────────

_FONTS = {}
_PATHS = {}


def _font(bold):
    got = _FONTS.get(bool(bold))
    if got is None:
        font = QFont(FONT_FAMILY)
        font.setStyleHint(QFont.SansSerif)
        font.setPixelSize(100)
        font.setBold(bool(bold))
        got = _FONTS[bool(bold)] = (font, QFontMetricsF(font))
    return got


def _cap(fm):
    return fm.capHeight() or 70.0


def text_width(text, size, bold=False):
    """Width (mm) of the widest line of *text* with capitals *size* mm
    tall."""
    _font_, fm = _font(bold)
    return max((fm.horizontalAdvance(line) for line in str(text)
                .split("\n")), default=0.0) * size / _cap(fm)


def text_path(text, size, bold=False):
    """*text* as an outline: capitals *size* mm tall, first baseline at
    y = 0, left edge at x = 0, lines 1.6 x size apart. Outlines scale to
    any zoom and print as vectors, where a 3.5 mm font would snap to
    whole pixels."""
    key = (str(text), round(float(size), 4), bool(bold))
    path = _PATHS.get(key)
    if path is None:
        font, fm = _font(bold)
        cap = _cap(fm)
        raw = QPainterPath()
        for i, line in enumerate(key[0].split("\n")):
            raw.addText(0.0, i * 1.6 * cap, font, line)
        k = size / cap
        path = QTransform.fromScale(k, k).map(raw)
        if len(_PATHS) > 6000:
            _PATHS.clear()
        _PATHS[key] = path
    return path


def text_transform(prim):
    """Where a text primitive's outline goes: the QTransform from
    `text_path` coordinates to the item's."""
    _t, _kind, at, text, size, align, valign, angle, bold = prim
    lines = str(text).count("\n") + 1
    w = text_width(text, size, bold)
    dx = {"left": 0.0, "center": -w / 2.0, "right": -w}.get(align, 0.0)
    dy = {"baseline": 0.0, "top": size,
          "middle": size / 2.0 - (lines - 1) * 0.8 * size,
          "bottom": -(lines - 1) * 1.6 * size}.get(valign, 0.0)
    t = QTransform()
    t.translate(at[0], at[1])
    t.rotate(-angle)                 # visual counter-clockwise
    t.translate(dx, dy)
    return t


def placed_text(prim):
    return text_transform(prim).map(text_path(prim[3], prim[4], prim[8]))


# ── primitives ─────────────────────────────────────────────────────

def line(kind, a, b):
    return ("line", kind, (float(a[0]), float(a[1])),
            (float(b[0]), float(b[1])))


def poly(kind, pts, closed=True, fill=False):
    return ("poly", kind, [(float(x), float(y)) for x, y in pts], closed,
            fill)


def circle(kind, c, r, fill=False):
    return ("circle", kind, (float(c[0]), float(c[1])), float(r), fill)


def arc(kind, c, r, start, sweep):
    """*start*/*sweep* in degrees, visual counter-clockwise from 3
    o'clock (Qt's and DXF's convention)."""
    return ("arc", kind, (float(c[0]), float(c[1])), float(r),
            float(start), float(sweep))


def text(value, at, size=TEXT, align="center", valign="baseline",
         angle=0.0, bold=False, kind="dim"):
    return ("text", kind, (float(at[0]), float(at[1])), str(value),
            float(size), align, valign, float(angle), bool(bold))


def arrow(tip, direction, kind="dim"):
    """A filled arrowhead, point at *tip*, pointing along *direction*."""
    dx, dy = _unit(direction)
    bx, by = tip[0] - dx * ARROW_L, tip[1] - dy * ARROW_L
    nx, ny = -dy * ARROW_W / 2.0, dx * ARROW_W / 2.0
    return poly(kind, [tip, (bx + nx, by + ny), (bx - nx, by - ny)],
                True, True)


def _unit(v):
    n = math.hypot(v[0], v[1]) or 1.0
    return v[0] / n, v[1] / n


def _add(a, b, k=1.0):
    return a[0] + b[0] * k, a[1] + b[1] * k


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def _polar(c, r, deg):
    """Point at visual angle *deg* (counter-clockwise, y DOWN)."""
    a = math.radians(deg)
    return c[0] + r * math.cos(a), c[1] - r * math.sin(a)


def paint_prims(painter, prims, look, color=None, widen=0.0):
    """Draw *prims*; *color* overrides every colour, *widen* thickens
    every stroke (the selection halo)."""
    for p in prims:
        kind = p[1]
        if p[0] == "text":
            painter.setPen(Qt.NoPen)
            painter.setBrush(color if color is not None
                             else look.text_color(kind))
            path = placed_text(p)
            if widen:
                painter.setPen(look.pen("thin", color, widen))
            painter.drawPath(path)
            continue
        pen = look.pen(kind, color, widen)
        if p[0] == "line":
            painter.setPen(pen)
            painter.drawLine(QPointF(*p[2]), QPointF(*p[3]))
        elif p[0] == "poly":
            pts = QPolygonF([QPointF(x, y) for x, y in p[2]])
            if p[4]:
                painter.setPen(pen if widen else Qt.NoPen)
                painter.setBrush(pen.color())
                painter.drawPolygon(pts)
            else:
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
                if p[3]:
                    painter.drawPolygon(pts)
                else:
                    painter.drawPolyline(pts)
        elif p[0] == "circle":
            (cx, cy), r = p[2], p[3]
            if p[4]:
                painter.setPen(pen if widen else Qt.NoPen)
                painter.setBrush(pen.color())
            else:
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(cx, cy), r, r)
        elif p[0] == "arc":
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(_arc_path(p))


def _arc_path(p):
    (cx, cy), r, start, sweep = p[2], p[3], p[4], p[5]
    rect = QRectF(cx - r, cy - r, 2 * r, 2 * r)
    path = QPainterPath()
    path.arcMoveTo(rect, start)
    path.arcTo(rect, start, sweep)
    return path


def prims_path(prims):
    """Every primitive as one outline path (text as its outline)."""
    path = QPainterPath()
    for p in prims:
        if p[0] == "line":
            path.moveTo(*p[2])
            path.lineTo(*p[3])
        elif p[0] == "poly" and p[2]:
            path.moveTo(*p[2][0])
            for q in p[2][1:]:
                path.lineTo(*q)
            if p[3]:
                path.closeSubpath()
        elif p[0] == "circle":
            path.addEllipse(QPointF(*p[2]), p[3], p[3])
        elif p[0] == "arc":
            path.addPath(_arc_path(p))
        elif p[0] == "text":
            path.addRect(placed_text(p).boundingRect())
    return path


def prims_shape(prims, width=1.6):
    stroker = QPainterPathStroker()
    stroker.setWidth(width)
    return stroker.createStroke(prims_path(prims))


def fmt(value, decimals=2):
    """A measured value the drawing way: no trailing zeros."""
    s = f"{float(value):.{max(0, int(decimals))}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


# ── the base item ──────────────────────────────────────────────────

class SheetItem(QGraphicsItem):
    """An item drawn from primitives. Subclasses set KIND (the note type
    in the saved state), DEFAULTS, FIELDS (what the Properties panel
    edits: (key, label, editor, options)) and `primitives()`."""

    KIND = ""
    LAYER = "DIM"
    DEFAULTS = {}
    FIELDS = ()
    TITLE = "Annotation"
    #: True: the item stores model points of its parent view and a drag
    #: moves its label (`drag_to`), never the geometry it points at
    ANCHORED = False
    #: True: a free item the user can drag anywhere on the sheet
    MOVABLE = False

    def __init__(self, data=None, view=None):
        super().__init__(view)
        self.view = view
        self.data = {k: (list(v) if isinstance(v, list) else v)
                     for k, v in self.DEFAULTS.items()}
        self.data.update(dict(data or {}))
        self.prims = []
        self._bounds = QRectF()
        self._shape = QPainterPath()
        self._dragging = False
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        if self.MOVABLE:
            self.setFlag(QGraphicsItem.ItemIsMovable, True)
            self.setPos(float(self.data.get("x", 0.0)),
                        float(self.data.get("y", 0.0)))
        self.setZValue(5)
        self.rebuild()

    # -- coordinates: the view's local frame, or the sheet's
    def local(self, p):
        """Stored point -> item coordinates."""
        if self.view is not None:
            return self.view.to_local(p)
        return float(p[0]), float(p[1])

    def stored(self, q):
        """Item coordinates -> the point to store."""
        if self.view is not None:
            u, v = self.view.to_model(q)
            return [u, v]
        return [float(q[0]), float(q[1])]

    def look(self):
        scene = self.scene()
        return getattr(scene, "look", None) or DEFAULT_LOOK

    def primitives(self):
        return []

    def rebuild(self):
        self.prepareGeometryChange()
        try:
            self.prims = self.primitives()
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            self.prims = []                 # a half-made note draws nothing
        path = prims_path(self.prims)
        self._bounds = path.boundingRect().adjusted(-2.0, -2.0, 2.0, 2.0)
        self._shape = prims_shape(self.prims)
        self.update()

    def boundingRect(self):
        return self._bounds

    def shape(self):
        return self._shape

    def paint(self, painter, option, widget=None):
        look = self.look()
        if self.isSelected() and not look.exporting:
            halo = look.color("select")
            halo.setAlpha(90)
            paint_prims(painter, self.prims, look, halo, widen=0.9)
            paint_prims(painter, self.prims, look, look.color("select"))
            return
        paint_prims(painter, self.prims, look)

    def to_dict(self):
        out = {k: (list(v) if isinstance(v, (list, tuple)) else v)
               for k, v in self.data.items()}
        out["type"] = self.KIND
        if self.view is not None:
            out["view"] = self.view.data["id"]
        if self.MOVABLE:
            out["x"], out["y"] = round(self.pos().x(), 3), \
                round(self.pos().y(), 3)
        return out

    def set_field(self, key, value):
        self.data[key] = value
        self.rebuild()

    # -- dragging an anchored note's label
    def drag_to(self, q):
        """Move the label to item point *q* (anchored notes)."""

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self._dragging = self.ANCHORED and event.button() == Qt.LeftButton
        self._before = dict(self.data)

    def mouseMoveEvent(self, event):
        if self._dragging:
            p = self.mapFromScene(event.scenePos())
            self.drag_to((p.x(), p.y()))
            self.rebuild()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self._dragging:
            self._dragging = False
            if self.data != getattr(self, "_before", self.data):
                scene = self.scene()
                if scene is not None and hasattr(scene, "edited"):
                    scene.edited("Move annotation")


# ── dimensions ─────────────────────────────────────────────────────

class DimensionItem(SheetItem):
    """Linear (horizontal / vertical / aligned), diameter, radius and
    angle dimensions. The number is the MODEL's measurement."""

    KIND = "dim"
    TITLE = "Dimension"
    ANCHORED = True
    DEFAULTS = {"kind": "horizontal", "offset": 10.0, "text": "",
                "prefix": "", "suffix": "", "tol_plus": "",
                "tol_minus": "", "decimals": 2, "count": 1,
                "angle": 45.0}
    FIELDS = (("text", "Text (blank = measured)", "text", None),
              ("prefix", "Prefix", "text", None),
              ("suffix", "Suffix", "text", None),
              ("tol_plus", "Tolerance +", "text", None),
              ("tol_minus", "Tolerance −", "text", None),
              ("decimals", "Decimals", "int", (0, 4)),
              ("count", "Count (n×)", "int", (1, 999)))
    LINEAR = ("horizontal", "vertical", "aligned")

    def value(self):
        d = self.data
        k = d["kind"]
        if k in self.LINEAR:
            a, b = d["a"], d["b"]
            if k == "horizontal":
                return abs(b[0] - a[0])
            if k == "vertical":
                return abs(b[1] - a[1])
            return math.hypot(b[0] - a[0], b[1] - a[1])
        if k == "diameter":
            return 2.0 * float(d["r"])
        if k == "radius":
            return float(d["r"])
        if k == "angle":
            v, p, q = d["vertex"], d["p1"], d["p2"]
            a1 = math.atan2(p[1] - v[1], p[0] - v[0])
            a2 = math.atan2(q[1] - v[1], q[0] - v[0])
            deg = abs(math.degrees(a2 - a1)) % 360.0
            return 360.0 - deg if deg > 180.0 else deg
        return 0.0

    def label(self):
        d = self.data
        k = d["kind"]
        core = str(d.get("text") or "").strip()
        if not core:
            core = fmt(self.value(), d.get("decimals", 2)) + \
                ("°" if k == "angle" else "")
        prefix = d.get("prefix") or {"diameter": "Ø", "radius": "R"}.get(
            k, "")
        count = int(d.get("count") or 1)
        head = f"{count}× " if count > 1 else ""
        return head + prefix + core + str(d.get("suffix") or "")

    def _text_prims(self, at, angle):
        """The number, with its tolerance: one ±value, or a stacked
        upper/lower pair after the number."""
        label = self.label()
        plus = str(self.data.get("tol_plus") or "").strip()
        minus = str(self.data.get("tol_minus") or "").strip()
        if plus and (plus == minus or not minus and plus.startswith("±")):
            label += " ±" + plus.lstrip("±+")
            plus = minus = ""
        if not plus and not minus:
            return [text(label, at, TEXT, "center", "baseline", angle)]
        small = TEXT * 0.7
        up_txt = ("+" + plus.lstrip("+")) if plus else "0"
        lo_txt = ("-" + minus.lstrip("-−")) if minus else "0"
        w = text_width(label, TEXT)
        tw = max(text_width(up_txt, small), text_width(lo_txt, small))
        total = w + 0.8 + tw
        a = math.radians(angle)
        ux, uy = math.cos(a), -math.sin(a)          # along the text
        vx, vy = -math.sin(a), -math.cos(a)         # the text's "up"
        left = (at[0] - ux * total / 2.0, at[1] - uy * total / 2.0)
        tol = (left[0] + ux * (w + 0.8), left[1] + uy * (w + 0.8))
        return [text(label, left, TEXT, "left", "baseline", angle),
                text(up_txt, (tol[0] + vx * TEXT * 0.55,
                              tol[1] + vy * TEXT * 0.55), small, "left",
                     "baseline", angle),
                text(lo_txt, (tol[0] - vx * TEXT * 0.25,
                              tol[1] - vy * TEXT * 0.25), small, "left",
                     "baseline", angle)]

    def primitives(self):
        k = self.data["kind"]
        if k in self.LINEAR:
            return self._linear()
        if k in ("diameter", "radius"):
            return self._radial()
        if k == "angle":
            return self._angle()
        return []

    # -- linear
    def _frame(self):
        """(A, B, u, n, mid) — the measured points, the direction along
        the dimension, its normal, and the midpoint."""
        d = self.data
        A, B = self.local(d["a"]), self.local(d["b"])
        k = d["kind"]
        if k == "horizontal":
            u = (1.0, 0.0)
        elif k == "vertical":
            u = (0.0, -1.0)
        else:
            u = _unit((B[0] - A[0], B[1] - A[1]))
        n = (-u[1], u[0])
        mid = ((A[0] + B[0]) / 2.0, (A[1] + B[1]) / 2.0)
        return A, B, u, n, mid

    def _linear(self):
        A, B, u, n, mid = self._frame()
        off = float(self.data.get("offset", 10.0))
        M = _add(mid, n, off)
        P1 = _add(M, u, _dot((A[0] - M[0], A[1] - M[1]), u))
        P2 = _add(M, u, _dot((B[0] - M[0], B[1] - M[1]), u))
        if _dot((P2[0] - P1[0], P2[1] - P1[1]), u) < 0:
            P1, P2 = P2, P1
            A, B = B, A
        out = []
        for src, dst in ((A, P1), (B, P2)):
            gap = (dst[0] - src[0], dst[1] - src[1])
            length = math.hypot(*gap)
            if length > EXT_GAP + 0.2:
                e = _unit(gap)
                out.append(line("dim", _add(src, e, EXT_GAP),
                                _add(dst, e, EXT_OVER)))
        span = math.hypot(P2[0] - P1[0], P2[1] - P1[1])
        if span >= 2 * ARROW_L + 1.0:
            out.append(line("dim", P1, P2))
            out.append(arrow(P1, (-u[0], -u[1])))
            out.append(arrow(P2, u))
        else:                                # too tight: arrows outside
            out.append(line("dim", _add(P1, u, -(ARROW_L + 3.0)),
                            _add(P2, u, ARROW_L + 3.0)))
            out.append(arrow(P1, u))
            out.append(arrow(P2, (-u[0], -u[1])))
        angle = math.degrees(math.atan2(-u[1], u[0]))
        if angle <= -90.0 or angle > 90.0:   # keep it readable
            angle = angle + 180.0 if angle <= -90.0 else angle - 180.0
        a = math.radians(angle)
        up = (-math.sin(a), -math.cos(a))
        at = _add(((P1[0] + P2[0]) / 2.0, (P1[1] + P2[1]) / 2.0), up,
                  TEXT_GAP)
        return out + self._text_prims(at, angle)

    # -- diameter / radius
    def _radial(self):
        d = self.data
        C = self.local(d["centre"])
        R = float(d["r"]) * (self.view.scale_ if self.view else 1.0)
        theta = float(d.get("angle", 45.0))
        off = float(d.get("offset", 8.0))
        P = _polar(C, R, theta)
        Q = _polar(C, max(R + off, 0.5), theta)
        dirv = _unit((P[0] - C[0], P[1] - C[1]))
        side = 1.0 if dirv[0] >= -1e-9 else -1.0
        knee = (Q[0] + side * 4.0, Q[1])
        out = []
        if d["kind"] == "diameter":
            Pn = _polar(C, R, theta + 180.0)
            out += [line("dim", Pn, Q), arrow(Pn, (-dirv[0], -dirv[1])),
                    arrow(P, dirv)]
        else:
            out += [line("dim", C, Q), arrow(P, dirv)]
        out.append(line("dim", Q, knee))
        label = self._text_prims((0, 0), 0.0)
        w = sum(text_width(p[3], p[4]) for p in label[:1]) + (
            text_width(label[1][3], label[1][4]) + 0.8
            if len(label) > 1 else 0.0)
        start = (knee[0] + side * 1.0 + (0 if side > 0 else -w),
                 knee[1] + TEXT / 2.0)
        for p in self._text_prims((start[0] + w / 2.0, start[1]), 0.0):
            out.append(p)
        return out

    # -- angle
    def _angle(self):
        d = self.data
        V = self.local(d["vertex"])
        D1, D2 = self.local(d["p1"]), self.local(d["p2"])
        a1 = math.degrees(math.atan2(-(D1[1] - V[1]), D1[0] - V[0]))
        a2 = math.degrees(math.atan2(-(D2[1] - V[1]), D2[0] - V[0]))
        sweep = ((a2 - a1 + 540.0) % 360.0) - 180.0
        start = a1
        if sweep < 0:
            start, sweep = a2, -sweep
        R = max(float(d.get("offset", 15.0)), 3.0)
        out = [arc("dim", V, R, start, sweep)]
        for D in (D1, D2):
            reach = math.hypot(D[0] - V[0], D[1] - V[1])
            if R > reach + EXT_GAP:
                e = _unit((D[0] - V[0], D[1] - V[1]))
                out.append(line("dim", _add(D, e, EXT_GAP),
                                _add(V, e, R + EXT_OVER)))
        end = start + sweep
        e1, e2 = _polar(V, R, start), _polar(V, R, end)
        s, e = math.radians(start), math.radians(end)
        out.append(arrow(e1, (math.sin(s), math.cos(s))))
        out.append(arrow(e2, (-math.sin(e), -math.cos(e))))
        mid = start + sweep / 2.0
        at = _polar(V, R + TEXT * 0.9, mid)
        return out + [text(self.label(), at, TEXT, "center", "middle")]

    # -- dragging moves the dimension line / leader / arc
    def drag_to(self, q):
        d = self.data
        k = d["kind"]
        if k in self.LINEAR:
            _A, _B, _u, n, mid = self._frame()
            d["offset"] = round(_dot((q[0] - mid[0], q[1] - mid[1]), n), 3)
        elif k in ("diameter", "radius"):
            C = self.local(d["centre"])
            R = float(d["r"]) * (self.view.scale_ if self.view else 1.0)
            d["angle"] = round(math.degrees(
                math.atan2(-(q[1] - C[1]), q[0] - C[0])), 2)
            d["offset"] = round(math.hypot(q[0] - C[0], q[1] - C[1]) - R,
                                3)
        elif k == "angle":
            V = self.local(d["vertex"])
            d["offset"] = round(math.hypot(q[0] - V[0], q[1] - V[1]), 3)


# ── leaders and symbols ────────────────────────────────────────────

class _Tagged(SheetItem):
    """A note pointing at a spot: `tip` (a stored point) and `at`, the
    label's offset from the tip in sheet mm — so the label stays by the
    feature when the view moves."""

    ANCHORED = True
    DEFAULTS = {"tip": [0.0, 0.0], "at": [12.0, -10.0]}

    def _ends(self):
        tip = self.local(self.data["tip"])
        at = self.data.get("at") or [12.0, -10.0]
        return tip, (tip[0] + float(at[0]), tip[1] + float(at[1]))

    def drag_to(self, q):
        tip = self.local(self.data["tip"])
        self.data["at"] = [round(q[0] - tip[0], 3), round(q[1] - tip[1], 3)]

    def to_dict(self):
        out = super().to_dict()
        out["at"] = [float(v) for v in self.data.get("at", (0, 0))]
        return out


class LeaderItem(_Tagged):
    KIND = "leader"
    TITLE = "Note"
    LAYER = "TEXT"
    DEFAULTS = dict(_Tagged.DEFAULTS, text="NOTE", size=TEXT)
    FIELDS = (("text", "Text", "multiline", None),
              ("size", "Text height (mm)", "float", (1.0, 20.0)))

    def primitives(self):
        tip, knee = self._ends()
        side = 1.0 if knee[0] >= tip[0] else -1.0
        end = (knee[0] + side * 3.0, knee[1])
        out = [line("thin", tip, knee), line("thin", knee, end),
               arrow(tip, (tip[0] - knee[0], tip[1] - knee[1]))]
        out.append(text(self.data.get("text", ""), (end[0] + side, end[1]),
                        float(self.data.get("size", TEXT)),
                        "left" if side > 0 else "right", "middle",
                        kind="text"))
        return out


class BalloonItem(_Tagged):
    KIND = "balloon"
    TITLE = "Balloon"
    LAYER = "TEXT"
    RADIUS = 4.5
    DEFAULTS = dict(_Tagged.DEFAULTS, number="1")
    FIELDS = (("number", "Item number", "text", None),)

    def primitives(self):
        tip, c = self._ends()
        d = _unit((tip[0] - c[0], tip[1] - c[1]))
        edge = _add(c, d, self.RADIUS)
        return [circle("thin", c, self.RADIUS), line("thin", edge, tip),
                circle("thin", tip, 0.6, fill=True),
                text(self.data.get("number", ""), c, TEXT, "center",
                     "middle", kind="text")]


class DatumItem(_Tagged):
    KIND = "datum"
    TITLE = "Datum feature"
    LAYER = "TEXT"
    DEFAULTS = dict(_Tagged.DEFAULTS, letter="A", at=[0.0, -14.0])
    FIELDS = (("letter", "Datum letter", "text", None),)

    def primitives(self):
        tip, c = self._ends()
        s = 3.2
        d = _unit((c[0] - tip[0], c[1] - tip[1]))
        n = (-d[1], d[0])
        apex = _add(tip, d, 2.8)
        tri = [_add(tip, n, 1.7), _add(tip, n, -1.7), apex]
        # where the stem meets the box: the box side it points through
        if abs(d[0]) * s > abs(d[1]) * s:
            box_hit = (c[0] - math.copysign(s, d[0]), c[1])
        else:
            box_hit = (c[0], c[1] - math.copysign(s, d[1]))
        return [poly("thin", tri, True, True), line("thin", apex, box_hit),
                poly("thin", [(c[0] - s, c[1] - s), (c[0] + s, c[1] - s),
                              (c[0] + s, c[1] + s), (c[0] - s, c[1] + s)]),
                text(self.data.get("letter", "A"), c, TEXT, "center",
                     "middle", kind="text")]


#: geometric characteristics a feature control frame can carry
GDT = (("position", "Position"), ("flatness", "Flatness"),
       ("straightness", "Straightness"), ("circularity", "Circularity"),
       ("cylindricity", "Cylindricity"), ("parallelism", "Parallelism"),
       ("perpendicularity", "Perpendicularity"),
       ("angularity", "Angularity"), ("concentricity", "Concentricity"),
       ("symmetry", "Symmetry"), ("profile_line", "Profile of a line"),
       ("profile_surface", "Profile of a surface"),
       ("runout", "Circular runout"), ("total_runout", "Total runout"))


def gdt_symbol(key, cx, cy, s=4.4):
    """The ISO 1101 symbol for *key*, drawn in a square of side *s*."""
    h = s / 2.0
    k = "thin"
    if key == "flatness":
        return [poly(k, [(cx - h, cy + h * 0.45), (cx + h * 0.45,
                                                   cy + h * 0.45),
                         (cx + h, cy - h * 0.45), (cx - h * 0.45,
                                                   cy - h * 0.45)])]
    if key == "straightness":
        return [line(k, (cx - h, cy), (cx + h, cy))]
    if key == "circularity":
        return [circle(k, (cx, cy), h * 0.8)]
    if key == "cylindricity":
        r = h * 0.55
        dx, dy = 0.5, -0.866
        nx, ny = 0.866, 0.5
        out = [circle(k, (cx, cy), r)]
        for sgn in (1, -1):
            px, py = cx + sgn * nx * r, cy + sgn * ny * r
            out.append(line(k, (px - dx * h, py - dy * h),
                            (px + dx * h, py + dy * h)))
        return out
    if key == "parallelism":
        return [line(k, (cx - h * 0.8 + o, cy + h), (cx + o, cy - h))
                for o in (0.0, h * 0.8)]
    if key == "perpendicularity":
        return [line(k, (cx - h, cy + h * 0.8), (cx + h, cy + h * 0.8)),
                line(k, (cx, cy + h * 0.8), (cx, cy - h))]
    if key == "angularity":
        return [line(k, (cx - h, cy + h * 0.8), (cx + h, cy + h * 0.8)),
                line(k, (cx - h, cy + h * 0.8), (cx + h * 0.8, cy - h))]
    if key == "position":
        return [circle(k, (cx, cy), h * 0.6),
                line(k, (cx - h, cy), (cx + h, cy)),
                line(k, (cx, cy - h), (cx, cy + h))]
    if key == "concentricity":
        return [circle(k, (cx, cy), h * 0.35), circle(k, (cx, cy), h * 0.8)]
    if key == "symmetry":
        return [line(k, (cx - h, cy), (cx + h, cy)),
                line(k, (cx - h * 0.6, cy - h * 0.5),
                     (cx + h * 0.6, cy - h * 0.5)),
                line(k, (cx - h * 0.6, cy + h * 0.5),
                     (cx + h * 0.6, cy + h * 0.5))]
    if key in ("profile_line", "profile_surface"):
        out = [arc(k, (cx, cy + h * 0.45), h * 0.85, 0.0, 180.0)]
        if key == "profile_surface":
            out.append(line(k, (cx - h * 0.85, cy + h * 0.45),
                            (cx + h * 0.85, cy + h * 0.45)))
        return out
    if key in ("runout", "total_runout"):
        tips = [(cx + h * 0.2, cy - h)] if key == "runout" else \
            [(cx - h * 0.2, cy - h), (cx + h * 0.6, cy - h)]
        out = []
        for tx, ty in tips:
            base = (tx - h * 0.5, ty + h * 1.8)
            out.append(line(k, base, (tx, ty)))
            d = _unit((tx - base[0], ty - base[1]))
            out.append(poly(k, [(tx, ty), _add(_add((tx, ty), d, -1.4),
                                                (-d[1], d[0]), 0.5),
                                _add(_add((tx, ty), d, -1.4),
                                     (d[1], -d[0]), 0.5)], True, True))
        if key == "total_runout":
            out.append(line(k, (cx - h * 0.9, cy + h * 0.8),
                            (cx + h * 0.4, cy + h * 0.8)))
        return out
    return []


class FcfItem(_Tagged):
    """A feature control frame: symbol | tolerance | datums."""

    KIND = "fcf"
    TITLE = "Geometric tolerance"
    LAYER = "TEXT"
    CELL = 7.0
    DEFAULTS = dict(_Tagged.DEFAULTS, symbol="position", tolerance="Ø0.1",
                    datums="A B", at=[14.0, -12.0])
    FIELDS = (("symbol", "Characteristic", "choice", GDT),
              ("tolerance", "Tolerance", "text", None),
              ("datums", "Datums (A B C)", "text", None))

    def primitives(self):
        tip, c = self._ends()
        h = self.CELL
        tol = str(self.data.get("tolerance", ""))
        datums = str(self.data.get("datums", "")).replace("|", " ").split()
        widths = [h, text_width(tol, TEXT) + 3.0] + [h] * len(datums)
        total = sum(widths)
        right_side = tip[0] > c[0] + total / 2.0
        x0 = c[0] - total if right_side else c[0]
        y0 = c[1] - h / 2.0
        out = [poly("thin", [(x0, y0), (x0 + total, y0),
                             (x0 + total, y0 + h), (x0, y0 + h)])]
        x = x0
        for i, w in enumerate(widths):
            if i:
                out.append(line("thin", (x, y0), (x, y0 + h)))
            cx = x + w / 2.0
            if i == 0:
                out += gdt_symbol(self.data.get("symbol", "position"), cx,
                                  c[1])
            elif i == 1:
                out.append(text(tol, (cx, c[1]), TEXT, "center", "middle",
                                kind="text"))
            else:
                out.append(text(datums[i - 2], (cx, c[1]), TEXT, "center",
                                "middle", kind="text"))
            x += w
        start = (x0 + total, c[1]) if right_side else (x0, c[1])
        knee = (start[0] + (3.0 if right_side else -3.0), start[1])
        out += [line("thin", start, knee), line("thin", knee, tip),
                arrow(tip, (tip[0] - knee[0], tip[1] - knee[1]))]
        return out


#: ISO 1302 surface-texture symbols
FINISH_KINDS = (("removal", "Material removal required"),
                ("any", "Any process"),
                ("prohibited", "Removal prohibited"))


class FinishItem(SheetItem):
    """A surface-finish symbol standing on an edge, its value under the
    long leg's bar. Dragging moves it along the drawing."""

    KIND = "finish"
    TITLE = "Surface finish"
    LAYER = "TEXT"
    ANCHORED = True
    DEFAULTS = {"tip": [0.0, 0.0], "ra": "Ra 3.2", "process": "removal"}
    FIELDS = (("ra", "Roughness", "text", None),
              ("process", "Process", "choice", FINISH_KINDS))

    def primitives(self):
        T = self.local(self.data["tip"])
        L = (T[0] - 2.9, T[1] - 5.0)
        U = (T[0] + 5.8, T[1] - 10.0)
        value = str(self.data.get("ra", ""))
        bar = max(10.0, text_width(value, 2.5) + 3.0)
        out = [line("thin", L, T), line("thin", T, U),
               line("thin", U, (U[0] + bar, U[1]))]
        process = self.data.get("process", "removal")
        if process == "removal":
            out.append(line("thin", L, (T[0] + 2.9, T[1] - 5.0)))
        elif process == "prohibited":
            out.append(circle("thin", (T[0], T[1] - 3.3), 1.6))
        out.append(text(value, (U[0] + 1.5, U[1] + 3.5), 2.5, "left",
                        "baseline", kind="text"))
        return out

    def drag_to(self, q):
        self.data["tip"] = self.stored(q)


# ── centre marks and lines ─────────────────────────────────────────

class CentreMarkItem(SheetItem):
    KIND = "centre_mark"
    TITLE = "Centre mark"
    LAYER = "CENTER"
    DEFAULTS = {"centre": [0.0, 0.0], "r": 1.0}

    def primitives(self):
        C = self.local(self.data["centre"])
        R = float(self.data["r"]) * (self.view.scale_ if self.view else 1.0)
        reach = R + 2.5
        if R < 2.0:                         # a small hole: a plain cross
            return [line("thin", (C[0] - reach, C[1]), (C[0] + reach, C[1])),
                    line("thin", (C[0], C[1] - reach), (C[0], C[1] + reach))]
        return [line("center", (C[0] - reach, C[1]), (C[0] + reach, C[1])),
                line("center", (C[0], C[1] - reach), (C[0], C[1] + reach))]


class CentreLineItem(SheetItem):
    KIND = "centre_line"
    TITLE = "Centre line"
    LAYER = "CENTER"
    DEFAULTS = {"a": [0.0, 0.0], "b": [1.0, 0.0]}

    def primitives(self):
        A, B = self.local(self.data["a"]), self.local(self.data["b"])
        u = _unit((B[0] - A[0], B[1] - A[1]))
        return [line("center", _add(A, u, -3.0), _add(B, u, 3.0))]


# ── free items ─────────────────────────────────────────────────────

class TextItem(SheetItem):
    KIND = "text"
    TITLE = "Text"
    LAYER = "TEXT"
    MOVABLE = True
    DEFAULTS = {"text": "TEXT", "size": 5.0, "bold": False}
    FIELDS = (("text", "Text", "multiline", None),
              ("size", "Text height (mm)", "float", (1.0, 40.0)),
              ("bold", "Bold", "bool", None))

    def primitives(self):
        return [text(self.data.get("text", ""), (0.0, 0.0),
                     float(self.data.get("size", 5.0)), "left", "baseline",
                     bold=bool(self.data.get("bold")), kind="text")]


SKETCH_LINES = (("visible", "Visible (thick)"), ("thin", "Thin"),
                ("hidden", "Hidden (dashed)"), ("center", "Centre (chain)"))


class SketchItem(SheetItem):
    """A line, rectangle or circle drawn on the paper."""

    KIND = "sketch"
    TITLE = "Sketch"
    LAYER = "SKETCH"
    MOVABLE = True
    DEFAULTS = {"shape": "line", "p1": [0.0, 0.0], "p2": [10.0, 0.0],
                "line": "visible"}
    FIELDS = (("line", "Line type", "choice", SKETCH_LINES),)

    def primitives(self):
        k = self.data.get("line", "visible")
        a, b = self.data["p1"], self.data["p2"]
        shape = self.data.get("shape", "line")
        if shape == "rect":
            return [poly(k, [(a[0], a[1]), (b[0], a[1]), (b[0], b[1]),
                             (a[0], b[1])])]
        if shape == "circle":
            return [circle(k, a, math.hypot(b[0] - a[0], b[1] - a[1]))]
        return [line(k, a, b)]


class BomItem(SheetItem):
    """The parts list: item, part, quantity, material."""

    KIND = "bom"
    TITLE = "Parts list"
    LAYER = "TITLE"
    MOVABLE = True
    ROW = 6.0
    COLS = (("ITEM", 14.0), ("PART", 62.0), ("QTY", 14.0),
            ("MATERIAL", 40.0))
    DEFAULTS = {"rows": []}
    FIELDS = (("rows_text", "Rows (item | part | qty | material)",
               "multiline", None),)

    def width(self):
        return sum(w for _h, w in self.COLS)

    def height(self):
        return self.ROW * (len(self.data.get("rows") or []) + 1)

    def primitives(self):
        rows = self.data.get("rows") or []
        W, H = self.width(), self.height()
        out = [poly("visible", [(0, 0), (W, 0), (W, H), (0, H)])]
        for i in range(1, len(rows) + 1):
            out.append(line("thin", (0, i * self.ROW), (W, i * self.ROW)))
        x = 0.0
        for c, (head, w) in enumerate(self.COLS):
            if c:
                out.append(line("thin", (x, 0), (x, H)))
            out.append(text(head, (x + 1.5, self.ROW / 2.0), 2.2, "left",
                            "middle", bold=True, kind="text"))
            for r, row in enumerate(rows):
                value = str(row[c]) if c < len(row) else ""
                out.append(text(value, (x + 1.5, (r + 1.5) * self.ROW), 2.5,
                                "left", "middle", kind="text"))
            x += w
        return out

    def set_field(self, key, value):
        if key == "rows_text":
            rows = []
            for raw in str(value).splitlines():
                if raw.strip():
                    rows.append([c.strip() for c in raw.split("|")])
            self.data["rows"] = rows
            self.rebuild()
            return
        super().set_field(key, value)

    def field(self, key):
        if key == "rows_text":
            return "\n".join(" | ".join(str(c) for c in row)
                             for row in self.data.get("rows") or [])
        return self.data.get(key)


#: every note type the saved state can hold
NOTE_CLASSES = {cls.KIND: cls for cls in (
    DimensionItem, LeaderItem, BalloonItem, DatumItem, FcfItem, FinishItem,
    CentreMarkItem, CentreLineItem, TextItem, SketchItem, BomItem)}


def note_from_dict(data, view=None):
    cls = NOTE_CLASSES.get(data.get("type"))
    if cls is None:
        return None
    body = {k: v for k, v in data.items() if k not in ("type", "view")}
    return cls(body, view)


# ── marks a view places on another ─────────────────────────────────

class _Derived(SheetItem):
    """Drawn because of another view (a detail's circle, a section's
    cutting line); rebuilt with it, never saved on its own."""

    def __init__(self, data, view):
        super().__init__(data, view)
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.setZValue(4)


class DetailMarkItem(_Derived):
    LAYER = "THIN"

    def primitives(self):
        C = self.local(self.data["centre"])
        R = float(self.data["radius"]) * self.view.scale_
        spot = _polar(C, R + 3.5, 45.0)
        return [circle("thin", C, R),
                text(self.data.get("letter", "A"), spot, 4.5, "center",
                     "middle", bold=True, kind="text")]


class CuttingLineItem(_Derived):
    """A section's cutting plane, drawn on the view it cuts: a chain
    line, thick at its ends, with arrows looking the way the section is
    seen and its letter at each end."""

    LAYER = "CUT"

    def primitives(self):
        a, b = self.local(self.data["a"]), self.local(self.data["b"])
        u = _unit((b[0] - a[0], b[1] - a[1]))
        a, b = _add(a, u, -6.0), _add(b, u, 6.0)
        look = _unit(self.data["look"])          # sheet direction
        out = [line("center", a, b),
               line("visible", a, _add(a, u, 5.0)),
               line("visible", b, _add(b, u, -5.0))]
        letter = self.data.get("letter", "A")
        for end in (a, b):
            base = _add(end, u, 2.5 if end is a else -2.5)
            tip = _add(base, look, 7.0)
            out += [line("thin", base, tip), arrow(tip, look, "thin"),
                    text(letter, _add(tip, look, 3.2), 4.5, "center",
                         "middle", bold=True, kind="text")]
        return out


# ── views ──────────────────────────────────────────────────────────

VIEW_LABELS = {"Front": "FRONT", "Top": "TOP", "Right": "RIGHT",
               "Left": "LEFT", "Back": "BACK", "Bottom": "BOTTOM",
               "Isometric": "ISOMETRIC"}


class ViewItem(QGraphicsItem):
    """One view on the sheet: a projection, a section, a detail or a
    shaded picture. Its content (model-mm line segments, section
    outlines, a picture) is handed in by the scene, which owns the
    geometry; the item maps it into its local frame, draws it and keeps
    it aligned (the scene's `constrain_view`)."""

    def __init__(self, data):
        super().__init__()
        self.data = dict(data)
        self.lines = {"visible": [], "hidden": []}
        self.bounds = (0.0, 0.0, 1.0, 1.0)
        self.scale_ = 1.0
        self.outlines = []          # section: [[(u, v), ...]]
        self.image = None           # shaded: QImage
        self.clip = None            # detail: (centre, radius) model
        self.circles = []           # round edges, model coords
        self._paths = {}
        self._hatch = []
        self._label = []
        self._rect = QRectF()
        self.setFlags(QGraphicsItem.ItemIsMovable
                      | QGraphicsItem.ItemIsSelectable
                      | QGraphicsItem.ItemSendsGeometryChanges)
        self.setZValue(1)
        self.setPos(float(self.data.get("x", 0.0)),
                    float(self.data.get("y", 0.0)))

    TITLE = "View"
    FIELDS = (("label", "Label", "text", None),
              ("show_label", "Show label", "bool", None),
              ("aligned", "Keep aligned to Front", "bool", None))

    # -- mapping
    def to_local(self, p):
        u0, v0 = self.bounds[0], self.bounds[1]
        s = self.scale_
        return (float(p[0]) - u0) * s, -(float(p[1]) - v0) * s

    def to_model(self, q):
        u0, v0 = self.bounds[0], self.bounds[1]
        s = self.scale_ or 1.0
        return float(q[0]) / s + u0, -float(q[1]) / s + v0

    def size(self):
        u0, v0, u1, v1 = self.bounds
        return (u1 - u0) * self.scale_, (v1 - v0) * self.scale_

    def content_rect(self):
        w, h = self.size()
        return QRectF(0.0, -h, w, h)

    def look(self):
        scene = self.scene()
        return getattr(scene, "look", None) or DEFAULT_LOOK

    # -- content
    def set_content(self, *, scale, bounds, lines=None, outlines=None,
                    image=None, clip=None, circles=()):
        self.prepareGeometryChange()
        self.scale_ = float(scale)
        self.bounds = tuple(float(b) for b in bounds)
        self.lines = lines or {"visible": [], "hidden": []}
        self.outlines = outlines or []
        self.image = image
        self.clip = clip
        self.circles = list(circles)
        self._rebuild()

    def set_scale(self, scale):
        self.set_content(scale=scale, bounds=self.bounds, lines=self.lines,
                         outlines=self.outlines, image=self.image,
                         clip=self.clip, circles=self.circles)

    def label_text(self):
        custom = str(self.data.get("label") or "").strip()
        if custom:
            return custom
        kind = self.data.get("kind", "projected")
        letter = self.data.get("letter", "A")
        if kind == "section":
            return f"SECTION {letter}-{letter}"
        if kind == "detail":
            return f"DETAIL {letter}"
        if kind == "shaded":
            return "ISOMETRIC VIEW"
        return VIEW_LABELS.get(self.data.get("name"), str(
            self.data.get("name", "VIEW")).upper())

    def _rebuild(self):
        self.prepareGeometryChange()
        self._paths = {}
        for key in ("visible", "hidden"):
            path = QPainterPath()
            for a, b in self.lines.get(key, ()):
                path.moveTo(*self.to_local(a))
                path.lineTo(*self.to_local(b))
            self._paths[key] = path
        local = [[self.to_local(p) for p in o] for o in self.outlines]
        section = QPainterPath()
        for pts in local:
            if len(pts) >= 3:
                section.moveTo(*pts[0])
                for q in pts[1:]:
                    section.lineTo(*q)
                section.closeSubpath()
        self._paths["section"] = section
        self._hatch = drawing.hatch_segments(local, 2.5) if local else []
        w, h = self.size()
        rect = QRectF(0.0, -h, w, h)
        border = None
        if self.clip is not None:
            (cu, cv), r = self.clip
            c = self.to_local((cu, cv))
            border = circle("thin", c, r * self.scale_)
        self._border = border
        self._label = []
        if self.data.get("show_label", True):
            y = 7.0
            big = self.data.get("kind") in ("section", "detail")
            self._label.append(text(self.label_text(), (w / 2.0, y),
                                    5.0 if big else 3.5, "center", "top",
                                    bold=big, kind="text"))
            if self.data.get("kind") == "detail":
                self._label.append(text(
                    "SCALE " + drawing.scale_label(self.scale_), (
                        w / 2.0, y + 7.0), 3.5, "center", "top",
                    kind="text"))
        label_rect = prims_path(self._label).boundingRect() \
            if self._label else QRectF()
        self._rect = rect.united(label_rect).adjusted(-3.0, -3.0, 3.0, 3.0)
        self.update()

    def boundingRect(self):
        return self._rect

    def shape(self):
        path = QPainterPath()
        path.addRect(self._rect)
        return path

    def paint(self, painter, option, widget=None):
        look = self.look()
        if self.image is not None:
            painter.drawImage(self.content_rect(), self.image)
        if not self._paths["section"].isEmpty():
            painter.setPen(look.pen("hatch"))
            for a, b in self._hatch:
                painter.drawLine(QPointF(*a), QPointF(*b))
            painter.setPen(look.pen("visible"))
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(self._paths["section"])
        painter.setBrush(Qt.NoBrush)
        if not self._paths["hidden"].isEmpty():
            painter.setPen(look.pen("hidden"))
            painter.drawPath(self._paths["hidden"])
        if not self._paths["visible"].isEmpty():
            painter.setPen(look.pen("visible"))
            painter.drawPath(self._paths["visible"])
        if self._border is not None:
            paint_prims(painter, [self._border], look)
        paint_prims(painter, self._label, look)
        if self.isSelected() and not look.exporting:
            pen = QPen(look.color("select"), 0.4, Qt.DashLine)
            pen.setCosmetic(False)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self._rect)

    def dxf_prims(self):
        """The view as primitives, for the DXF (the screen paints cached
        paths instead — a threaded part has tens of thousands of
        lines)."""
        out = []
        for key in ("visible", "hidden"):
            for a, b in self.lines.get(key, ()):
                out.append(line(key, self.to_local(a), self.to_local(b)))
        for o in self.outlines:
            pts = [self.to_local(p) for p in o]
            if len(pts) >= 3:
                out.append(poly("visible", pts))
        out += [line("hatch", a, b) for a, b in self._hatch]
        if self._border is not None:
            out.append(self._border)
        return out + list(self._label)

    def to_dict(self):
        out = dict(self.data)
        out["x"], out["y"] = round(self.pos().x(), 3), round(self.pos().y(), 3)
        return out

    def field(self, key):
        default = {"show_label": True, "aligned": True}.get(key, "")
        return self.data.get(key, default)

    def set_field(self, key, value):
        self.data[key] = value
        self._rebuild()

    def itemChange(self, change, value):
        scene = self.scene()
        if scene is not None and hasattr(scene, "constrain_view"):
            if change == QGraphicsItem.ItemPositionChange:
                return scene.constrain_view(self, value)
            if change == QGraphicsItem.ItemPositionHasChanged:
                scene.view_moved(self)
        return super().itemChange(change, value)

    def mouseReleaseEvent(self, event):
        before = (self.data.get("x"), self.data.get("y"))
        super().mouseReleaseEvent(event)
        scene = self.scene()
        now = (round(self.pos().x(), 3), round(self.pos().y(), 3))
        if scene is not None and hasattr(scene, "edited") and \
                now != (round(float(before[0] or 0), 3),
                        round(float(before[1] or 0), 3)):
            scene.edited("Move view")


# ── the paper ──────────────────────────────────────────────────────

class FrameItem(SheetItem):
    """The drawing frame: a border 10 mm in, reference zones along the
    edges (numbers across, letters down) and centring marks."""

    LAYER = "FRAME"
    MARGIN = 10.0
    DEFAULTS = {"width": 297.0, "height": 210.0}

    def __init__(self, data):
        super().__init__(data)
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.setZValue(-5)

    def primitives(self):
        W, H, m = float(self.data["width"]), float(self.data["height"]), \
            self.MARGIN
        out = [poly("frame", [(m, m), (W - m, m), (W - m, H - m),
                              (m, H - m)])]
        cols = max(2, int(round((W - 2 * m) / 50.0)))
        rows = max(2, int(round((H - 2 * m) / 50.0)))
        step_x, step_y = (W - 2 * m) / cols, (H - 2 * m) / rows
        for i in range(cols):
            x = m + (i + 0.5) * step_x
            for y in (m / 2.0, H - m / 2.0):
                out.append(text(str(i + 1), (x, y), 2.5, "center", "middle",
                                kind="label"))
            if i:
                xx = m + i * step_x
                out += [line("thin", (xx, 0.0 + m * 0.4), (xx, m)),
                        line("thin", (xx, H - m), (xx, H - m * 0.4))]
        for j in range(rows):
            y = m + (j + 0.5) * step_y
            letter = chr(ord("A") + j % 26)
            for x in (m / 2.0, W - m / 2.0):
                out.append(text(letter, (x, y), 2.5, "center", "middle",
                                kind="label"))
            if j:
                yy = m + j * step_y
                out += [line("thin", (m * 0.4, yy), (m, yy)),
                        line("thin", (W - m, yy), (W - m * 0.4, yy))]
        for a, b in (((W / 2, 0.0), (W / 2, m)), ((W / 2, H - m), (W / 2, H)),
                     ((0.0, H / 2), (m, H / 2)), ((W - m, H / 2), (W, H / 2))):
            out.append(line("visible", a, b))
        return out


class TitleBlockItem(SheetItem):
    """The title block in the frame's bottom-right corner — title,
    drawing number, material, finish, mass, scale, sheet size, the
    third-angle symbol and who drew, checked and approved it."""

    KIND = "title"
    TITLE = "Title block"
    LAYER = "TITLE"
    DEFAULTS = {"fields": {}, "scale_label": "1:1", "sheet": "A4"}

    def __init__(self, data):
        super().__init__(data)
        self.setZValue(3)

    def primitives(self):
        cells = drawing.title_block_cells(self.data.get("fields") or {},
                                          self.data.get("scale_label", ""),
                                          self.data.get("sheet", ""))
        W, H = drawing.TITLE_W, drawing.TITLE_H
        out = [poly("frame", [(0, 0), (W, 0), (W, H), (0, H)])]
        for cell in cells:
            x, y, w, h = cell["rect"]
            out.append(poly("thin", [(x, y), (x + w, y), (x + w, y + h),
                                     (x, y + h)]))
            if cell["label"]:
                out.append(text(cell["label"], (x + 1.0, y + 1.0), 1.6,
                                "left", "top", kind="label"))
            if cell["key"] == "projection":
                lines, circles, centre = drawing.projection_symbol(
                    x, y + 2.0, w, h - 2.0)
                out += [line("thin", a, b) for a, b in lines]
                out += [circle("thin", c, r) for c, r in circles]
                out += [line("center", a, b) for a, b in centre]
                continue
            if cell["text"]:
                size = cell["size"]
                body_top = y + (3.0 if cell["label"] else 0.0)
                cy = (body_top + y + h) / 2.0 + 0.2
                value = cell["text"]
                room = w - 3.0
                if text_width(value, size, cell["bold"]) > room:
                    size = max(1.4, size * room / text_width(
                        value, size, cell["bold"]))
                out.append(text(value, (x + 1.5, cy), size, "left",
                                "middle", bold=cell["bold"],
                                kind="label" if cell["key"] == "credit"
                                else "text"))
        return out

    def field(self, key):
        return (self.data.get("fields") or {}).get(key, "")

    def set_field(self, key, value):
        fields = dict(self.data.get("fields") or {})
        fields[key] = value
        self.data["fields"] = fields
        self.rebuild()

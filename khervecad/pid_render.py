"""Drawing a P&ID: one painter for the screen, PDF, SVG and PNG, and a
layered DXF from the same primitives.

`paint(painter, diagram, selection)` draws the sheet in millimetres
(the caller sets the transform): border with zone marks, title block,
legend of the line kinds and services in use, every line (styled by its
kind, coloured by its service unless the diagram is black and white,
with flow arrows, insulation ticks and the line number along its longest
leg), tee dots, every symbol with its tag and label — an instrument's
ISA letters and loop number INSIDE its bubble — and the notes.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import datetime
import math
import re
from pathlib import Path

from PyQt5.QtCore import QMarginsF, QPointF, QRectF, QSize, QSizeF, Qt
from PyQt5.QtGui import (QBrush, QColor, QFont, QFontMetricsF, QImage,
                         QPainter, QPainterPath, QPen, QPolygonF)

from . import pid as P
from . import pid_symbols as ps

INK = QColor(20, 20, 20)
SELECT = QColor(0, 120, 215)
FONT = "Arial"
WIDTHS = {"main": 0.5, "thin": 0.25, "dash": 0.25, "chain": 0.35}


def _font(size_mm, bold=False):
    f = QFont(FONT)
    f.setPointSizeF(max(size_mm * 2.835, 0.5))   # 1 mm = 2.835 pt
    f.setBold(bold)
    return f


def _text(painter, value, at, size=2.5, align="center", valign="middle",
          bold=False, color=INK, angle=0.0):
    """Text by its CAP height in mm, anchored like the primitives."""
    if not str(value):
        return
    f = _font(size, bold)
    fm = QFontMetricsF(f)
    k = size / max(fm.capHeight(), 1e-6)
    w = fm.horizontalAdvance(str(value)) * k
    painter.save()
    painter.translate(at[0], at[1])
    if angle:
        painter.rotate(-angle)
    painter.scale(k, k)
    x = {"left": 0.0, "center": -w / 2.0 / k, "right": -w / k}[align]
    cap = fm.capHeight()
    y = {"baseline": 0.0, "middle": cap / 2.0, "top": cap,
         "bottom": -fm.descent()}[valign]
    painter.setFont(f)
    painter.setPen(QPen(color))
    painter.drawText(QPointF(x, y), str(value))
    painter.restore()


def text_width(value, size=2.5, bold=False):
    f = _font(size, bold)
    fm = QFontMetricsF(f)
    return fm.horizontalAdvance(str(value)) * size / max(fm.capHeight(),
                                                         1e-6)


def _pen(kind, color=INK, widen=0.0):
    pen = QPen(color, WIDTHS.get(kind, 0.25) + widen)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    if kind == "dash":
        pen.setDashPattern([6.0, 4.0])
    elif kind == "chain":
        pen.setDashPattern([16.0, 4.0, 2.0, 4.0])
    return pen


def paint_prims(painter, prims, color=INK, widen=0.0):
    for p in prims:
        t, kind = p[0], p[1]
        if t == "text":
            _text(painter, p[3], p[2], p[4], p[5], p[6], color=color)
            continue
        pen = _pen(kind, color, widen)
        if t == "line":
            painter.setPen(pen)
            painter.drawLine(QPointF(*p[2]), QPointF(*p[3]))
        elif t == "poly":
            pts = QPolygonF([QPointF(x, y) for x, y in p[2]])
            painter.setPen(pen)
            painter.setBrush(QBrush(color) if p[4] else Qt.NoBrush)
            if p[3]:
                painter.drawPolygon(pts)
            else:
                painter.drawPolyline(pts)
        elif t == "circle":
            painter.setPen(pen)
            painter.setBrush(QBrush(color) if p[4] else Qt.NoBrush)
            painter.drawEllipse(QPointF(*p[2]), p[3], p[3])
        elif t == "arc":
            (cx, cy), r = p[2], p[3]
            path = QPainterPath()
            rect = QRectF(cx - r, cy - r, 2 * r, 2 * r)
            path.arcMoveTo(rect, p[4])
            path.arcTo(rect, p[4], p[5])
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(path)


# ── what each thing draws ──────────────────────────────────────────

def symbol_prims(s):
    if s["kind"] == "boundary":
        w = float((s.get("data") or {}).get("w", 60))
        h = float((s.get("data") or {}).get("h", 40))
        x, y = s["x"], s["y"]
        return [("poly", "chain", [(x - w / 2, y - h / 2),
                                   (x + w / 2, y - h / 2),
                                   (x + w / 2, y + h / 2),
                                   (x - w / 2, y + h / 2)], True, False)]
    return ps.placed_prims(s["kind"], s["x"], s["y"], s.get("rot", 0),
                           s.get("mirror", False))


def _is_bubble(s):
    return s["kind"] in ("instrument", "instrument_panel", "flow_switch",
                         "temperature_sensor", "pressure_switch")


def _split_tag(tag):
    m = re.fullmatch(r"([A-Za-z]+)-?(\S*)", str(tag or ""))
    return (m.group(1), m.group(2)) if m else (str(tag or ""), "")


def symbol_labels(s):
    """[(text, at, size, align, bold)] of a symbol's tag and label."""
    x0, y0, x1, y1 = ps.bounds(s["kind"], s["x"], s["y"], s.get("rot", 0),
                               s.get("mirror", False))
    out = []
    tag, label = s.get("tag", ""), s.get("label", "")
    if _is_bubble(s):
        letters, number = _split_tag(tag)
        out.append((letters, (s["x"], s["y"] - 1.4), 2.0, "center", True))
        out.append((number, (s["x"], s["y"] + 2.0), 1.8, "center", False))
        if label:
            out.append((label, (x1 + 1.5, s["y"]), 2.0, "left", False))
        return out
    if s["kind"] == "off_page":
        text = label or tag
        size = 2.2
        while size > 1.2 and text_width(text, size) > 16.0:
            size -= 0.1               # the words fit in the arrow
        dx = 1.0 if s.get("mirror") else -1.0
        out.append((text, (s["x"] + dx, s["y"]), size, "center", False))
        return out
    if s["kind"] == "boundary":
        w = float((s.get("data") or {}).get("w", 60))
        h = float((s.get("data") or {}).get("h", 40))
        out.append((label or tag, (s["x"] - w / 2 + 2.0,
                                   s["y"] - h / 2 + 4.0), 2.5, "left",
                    True))
        return out
    if tag:
        out.append((tag, (s["x"], y1 + 3.5), 2.5, "center", True))
    if label:
        out.append((label, (s["x"], y1 + (7.0 if tag else 3.5)), 2.0,
                    "center", False))
    return out


def line_colour(diagram, ln):
    if not diagram.colour_lines:
        return INK
    return QColor(P.SERVICES.get(ln.get("service", ""), ("", "#202020"))[1])


def _longest_leg(pts):
    best, length = None, -1.0
    for a, b in zip(pts, pts[1:]):
        d = abs(b[0] - a[0]) + abs(b[1] - a[1])
        if d > length:
            best, length = (a, b), d
    return best, length


def line_label(ln):
    number = ln.get("number") or ""
    extra = ln.get("label") or ""
    return f"{number}  {extra}".strip() if number else extra


LABEL_SIZE = 1.9


def label_spots(diagram):
    """{line id: (text, anchor, angle)} — each line number on a leg of
    its line where its words clear every symbol, symbol label, note and
    the line numbers already placed; left out when nowhere fits."""
    taken = []
    for s in diagram.symbols:
        if s["kind"] == "boundary":
            continue
        taken.append(QRectF(*_box_rect(diagram.box(s))))
        for value, at, size, align, _b in symbol_labels(s):
            w = text_width(value, size)
            x = at[0] - (w / 2 if align == "center" else
                         (w if align == "right" else 0))
            taken.append(QRectF(x, at[1] - size / 2, w, size))
    for n in diagram.notes:
        rows = str(n.get("text", "")).splitlines() or [""]
        w = max(text_width(r, n.get("size", 3.0)) for r in rows)
        taken.append(QRectF(n["x"], n["y"], w,
                            len(rows) * n.get("size", 3.0) * 1.6))
    out = {}
    lines = sorted(diagram.lines, key=lambda ln: -P.length(
        ln.get("points") or []))
    for ln in lines:
        text = line_label(ln)
        pts = ln.get("points") or []
        if not text or len(pts) < 2:
            continue
        w = text_width(text, LABEL_SIZE)
        legs = sorted(zip(pts, pts[1:]), key=lambda ab: -(
            abs(ab[1][0] - ab[0][0]) + abs(ab[1][1] - ab[0][1])))
        placed = None
        for a, b in legs:
            span = abs(b[0] - a[0]) + abs(b[1] - a[1])
            if span < w + 4.0:
                continue
            horizontal = abs(b[1] - a[1]) < 1e-6
            lo = min(a[0], b[0]) if horizontal else min(a[1], b[1])
            for frac in (0.5, 0.3, 0.7, 0.15, 0.85):
                start = lo + (span - w) * frac
                for side in (-1, 1):
                    if horizontal:
                        y = a[1] + (-0.9 if side < 0 else 0.9 + LABEL_SIZE)
                        rect = QRectF(start, y - LABEL_SIZE, w, LABEL_SIZE)
                        cand = (text, (start, y), 0.0)
                    else:
                        x = a[0] + (-0.9 if side < 0 else 0.9 + LABEL_SIZE)
                        rect = QRectF(x - LABEL_SIZE, start, LABEL_SIZE, w)
                        cand = (text, (x, start + w), 90.0)
                    if not any(rect.intersects(t) for t in taken):
                        placed = cand
                        taken.append(rect)
                        break
                if placed:
                    break
            if placed:
                break
        if placed:
            out[ln["id"]] = placed
    return out


def _box_rect(box):
    return box[0], box[1], box[2] - box[0], box[3] - box[1]


def paint_line(painter, diagram, ln, color=None, widen=0.0,
               label_spot=None):
    pts = ln.get("points") or []
    if len(pts) < 2:
        return
    kind = ln.get("kind", "process")
    _label, width, style = P.LINE_KINDS.get(kind, P.LINE_KINDS["process"])
    col = color or line_colour(diagram, ln)
    pen = QPen(col, width + widen)
    pen.setCapStyle(Qt.FlatCap)
    pen.setJoinStyle(Qt.MiterJoin)
    if style == "dash":
        pen.setDashPattern([8.0, 5.0])
    elif style == "dashdot":
        pen.setDashPattern([12.0, 4.0, 2.0, 4.0])
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    painter.drawPolyline(QPolygonF([QPointF(x, y) for x, y in pts]))
    thin = QPen(col, 0.25)
    for a, b in zip(pts, pts[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy)
        if n < 1e-6:
            continue
        ux, uy = dx / n, dy / n
        if style in ("slash", "cross"):
            painter.setPen(thin)
            k = 6.0
            while k < n - 3.0:
                cx, cy = a[0] + ux * k, a[1] + uy * k
                if style == "slash":
                    for off in (-0.8, 0.8):
                        ox, oy = cx + ux * off, cy + uy * off
                        painter.drawLine(QPointF(ox - uy * 1.5 - ux * 1.0,
                                                 oy + ux * 1.5 - uy * 1.0),
                                         QPointF(ox + uy * 1.5 + ux * 1.0,
                                                 oy - ux * 1.5 + uy * 1.0))
                else:
                    for s1, s2 in ((1, 1), (1, -1)):
                        painter.drawLine(
                            QPointF(cx - (ux * s1 + uy * s2) * 1.2,
                                    cy - (uy * s1 - ux * s2) * 1.2),
                            QPointF(cx + (ux * s1 + uy * s2) * 1.2,
                                    cy + (uy * s1 - ux * s2) * 1.2))
                k += 10.0
        if ln.get("insulated") and kind in ("process", "secondary"):
            # ISO 10628: insulation as a dashed line along the pipe
            faint = QColor(col)
            faint.setAlpha(150)
            ins = QPen(faint, 0.2)
            ins.setDashPattern([1.0, 2.5])
            painter.setPen(ins)
            off = 1.6
            painter.drawLine(QPointF(a[0] - uy * off, a[1] + ux * off),
                             QPointF(b[0] - uy * off, b[1] + ux * off))
    leg, n = _longest_leg(pts)
    if leg is not None and ln.get("arrow", True) and \
            kind in ("process", "secondary") and n > 12.0:
        a, b = leg
        dx, dy = b[0] - a[0], b[1] - a[1]
        d = math.hypot(dx, dy)
        ux, uy = dx / d, dy / d
        mx, my = (a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0
        tip = QPointF(mx + ux * 1.8, my + uy * 1.8)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(col))
        painter.drawPolygon(QPolygonF([
            tip, QPointF(mx - ux * 1.8 - uy * 1.3, my - uy * 1.8 + ux * 1.3),
            QPointF(mx - ux * 1.8 + uy * 1.3, my - uy * 1.8 - ux * 1.3)]))
    spot = label_spot
    if spot is not None:
        text, at, angle = spot
        _text(painter, text, at, LABEL_SIZE, "left", "bottom", color=col,
              angle=angle)


def paint(painter, diagram, selection=(), hover=None, grid=False):
    """The whole sheet in mm."""
    W, H = diagram.size
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.fillRect(QRectF(0, 0, W, H), QColor(255, 255, 255))
    if grid:
        painter.setPen(QPen(QColor(232, 236, 242), 0.15))
        g = 5.0
        x = 0.0
        while x <= W:
            painter.drawLine(QPointF(x, 0), QPointF(x, H))
            x += g
        y = 0.0
        while y <= H:
            painter.drawLine(QPointF(0, y), QPointF(W, y))
            y += g
    _frame(painter, diagram)
    sel = set(selection or ())
    spots = label_spots(diagram)
    for ln in diagram.lines:
        if ln["id"] in sel:
            paint_line(painter, diagram, ln, SELECT, widen=0.6)
        paint_line(painter, diagram, ln, label_spot=spots.get(ln["id"]))
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(INK))
    for (x, y) in diagram.junctions():
        painter.drawEllipse(QPointF(x, y), 0.9, 0.9)
    for s in diagram.symbols:
        prims = symbol_prims(s)
        if s["id"] in sel:
            paint_prims(painter, prims, SELECT, widen=0.7)
        paint_prims(painter, prims, SELECT if s["id"] in sel else INK)
        for value, at, size, align, bold in symbol_labels(s):
            _text(painter, value, at, size, align, "middle", bold)
        if hover is not None and hover.get("symbol") == s["id"]:
            painter.setPen(QPen(SELECT, 0.3))
            painter.setBrush(QBrush(QColor(0, 120, 215, 70)))
            for name, ((px, py), _d) in diagram.ports(s).items():
                big = 1.4 if name == hover.get("port") else 0.9
                painter.drawEllipse(QPointF(px, py), big, big)
    for n in diagram.notes:
        col = SELECT if n["id"] in sel else INK
        for i, row in enumerate(str(n.get("text", "")).splitlines()):
            _text(painter, row, (n["x"], n["y"] + i * n.get("size", 3.0)
                                 * 1.6), n.get("size", 3.0), "left",
                  "top", color=col)


def _frame(painter, d):
    W, H = d.size
    m = P.MARGIN
    painter.setBrush(Qt.NoBrush)
    painter.setPen(QPen(INK, 0.7))
    painter.drawRect(QRectF(m, m, W - 2 * m, H - 2 * m))
    painter.setPen(QPen(INK, 0.25))
    cols = int(round((W - 2 * m) / 50.0))
    rows = int(round((H - 2 * m) / 50.0))
    for i in range(1, cols):
        x = m + i * (W - 2 * m) / cols
        painter.drawLine(QPointF(x, m - 4), QPointF(x, m))
        painter.drawLine(QPointF(x, H - m), QPointF(x, H - m + 4))
    for i in range(cols):
        x = m + (i + 0.5) * (W - 2 * m) / cols
        _text(painter, str(i + 1), (x, m - 2), 2.0)
        _text(painter, str(i + 1), (x, H - m + 2), 2.0)
    for i in range(rows):
        y = m + (i + 0.5) * (H - 2 * m) / rows
        letter = chr(65 + i)
        _text(painter, letter, (m - 2.5, y), 2.0)
        _text(painter, letter, (W - m + 2.5, y), 2.0)
    for i in range(1, rows):
        y = m + i * (H - 2 * m) / rows
        painter.drawLine(QPointF(m - 4, y), QPointF(m, y))
        painter.drawLine(QPointF(W - m, y), QPointF(W - m + 4, y))
    _title_block(painter, d)
    _legend(painter, d)


TB_W = 170.0


def _title_block(painter, d):
    W, H = d.size
    m = P.MARGIN
    x0, y0 = W - m - TB_W, H - m - P.TITLE_H
    f = d.fields
    painter.setPen(QPen(INK, 0.5))
    painter.setBrush(QBrush(QColor(255, 255, 255)))
    painter.drawRect(QRectF(x0, y0, TB_W, P.TITLE_H))
    painter.setPen(QPen(INK, 0.25))
    rows = (12.0, 8.0, 8.0, 8.0)
    y = y0
    for h in rows[:-1]:
        y += h
        painter.drawLine(QPointF(x0, y), QPointF(x0 + TB_W, y))
    cells = [
        (0, 0, TB_W * 0.62, "TITLE", f.get("title", ""), 3.0, True),
        (0, TB_W * 0.62, TB_W * 0.38, "COMPANY", f.get("company", ""), 2.4,
         False),
        (1, 0, 50, "DRAWING NO.", f.get("number", ""), 2.4, True),
        (1, 50, 25, "REV", f.get("revision", ""), 2.4, True),
        (1, 75, 30, "SHEET", f.get("sheet_no", "1 / 1"), 2.2, False),
        (1, 105, 65, "PROJECT", f.get("project", ""), 2.2, False),
        (2, 0, 50, "DRAWN", f.get("drawn", ""), 2.2, False),
        (2, 50, 55, "CHECKED", f.get("checked", ""), 2.2, False),
        (2, 105, 65, "APPROVED", f.get("approved", ""), 2.2, False),
        (3, 0, 50, "DATE", f.get("date") or datetime.date.today()
         .isoformat(), 2.2, False),
        (3, 50, 25, "SIZE", d.sheet, 2.2, False),
        (3, 75, 30, "SCALE", "NTS", 2.2, False),
        (3, 105, 65, "STANDARD", f.get("standard",
                                        "ISO 10628 / ISA-5.1"), 2.0,
         False),
    ]
    tops = [y0, y0 + rows[0], y0 + rows[0] + rows[1],
            y0 + rows[0] + rows[1] + rows[2]]
    for r, cx, w, head, value, size, bold in cells:
        top, h = tops[r], rows[r]
        if cx:
            painter.setPen(QPen(INK, 0.25))
            painter.drawLine(QPointF(x0 + cx, top), QPointF(x0 + cx,
                                                            top + h))
        _text(painter, head, (x0 + cx + 1.0, top + 1.2), 1.5, "left",
              "top", color=QColor(90, 90, 90))
        value = str(value)
        while value and text_width(value, size, bold) > w - 2.0:
            value = value[:-2] + "…" if len(value) > 2 else ""
        _text(painter, value, (x0 + cx + 1.0, top + h - 1.0), size, "left",
              "bottom", bold)


def legend_items(d):
    kinds = []
    services = []
    for ln in d.lines:
        if ln.get("kind") not in kinds:
            kinds.append(ln.get("kind"))
        sv = ln.get("service", "")
        if sv and sv not in services and ln.get("kind") in (
                "process", "secondary"):
            services.append(sv)
    return kinds, services


def _legend(painter, d):
    kinds, services = legend_items(d)
    if not kinds:
        return
    W, H = d.size
    m = P.MARGIN
    rows = len(kinds) + (len(services) if d.colour_lines else 0)
    h = 6.0 + rows * 4.2
    w = 62.0
    # beside the title block, bottom-aligned with it (above it there is
    # usually drawing)
    x0 = W - m - TB_W - w - 3.0
    y0 = H - m - h
    painter.setPen(QPen(INK, 0.35))
    painter.setBrush(QBrush(QColor(255, 255, 255)))
    painter.drawRect(QRectF(x0, y0, w, h))
    _text(painter, "LEGEND", (x0 + 2.0, y0 + 3.2), 2.0, "left", "middle",
          True)
    y = y0 + 7.5
    for k in kinds:
        label, width, style = P.LINE_KINDS.get(k, P.LINE_KINDS["process"])
        fake = {"kind": k, "points": [[x0 + 2, y], [x0 + 18, y]],
                "arrow": False}
        paint_line(painter, d, fake, INK)
        _text(painter, label, (x0 + 21.0, y), 1.9, "left", "middle")
        y += 4.2
    if d.colour_lines:
        for sv in services:
            meaning, colour = P.SERVICES.get(sv, (sv, "#202020"))
            painter.setPen(QPen(QColor(colour), 0.8))
            painter.drawLine(QPointF(x0 + 2, y), QPointF(x0 + 18, y))
            _text(painter, f"{sv}  {meaning}", (x0 + 21.0, y), 1.9, "left",
                  "middle")
            y += 4.2


# ── exports ────────────────────────────────────────────────────────

def to_image(diagram, px_per_mm=8.0):
    W, H = diagram.size
    image = QImage(int(W * px_per_mm), int(H * px_per_mm),
                   QImage.Format_ARGB32)
    image.fill(QColor(255, 255, 255))
    painter = QPainter(image)
    painter.scale(px_per_mm, px_per_mm)
    paint(painter, diagram)
    painter.end()
    return image


def write_png(diagram, path, px_per_mm=8.0):
    if not to_image(diagram, px_per_mm).save(str(path), "PNG"):
        raise OSError(f"Could not write {path}.")


def write_pdf(diagram, path):
    from PyQt5.QtGui import QPageSize, QPdfWriter
    W, H = diagram.size
    writer = QPdfWriter(str(path))
    writer.setPageSize(QPageSize(QSizeF(W, H), QPageSize.Millimeter))
    writer.setPageMargins(QMarginsF(0, 0, 0, 0))
    writer.setResolution(600)
    writer.setTitle(diagram.fields.get("title", "P&ID"))
    writer.setCreator("KherveCAD")
    painter = QPainter(writer)
    k = writer.width() / W
    painter.scale(k, k)
    paint(painter, diagram)
    painter.end()


def write_svg(diagram, path):
    from PyQt5.QtSvg import QSvgGenerator
    W, H = diagram.size
    k = 4.0
    gen = QSvgGenerator()
    gen.setFileName(str(path))
    gen.setSize(QSize(int(W * k), int(H * k)))
    gen.setViewBox(QRectF(0, 0, W * k, H * k))
    gen.setTitle(diagram.fields.get("title", "P&ID"))
    gen.setDescription("Drawn in KherveCAD")
    painter = QPainter(gen)
    painter.scale(k, k)
    paint(painter, diagram)
    painter.end()


def write_dxf(diagram, path):
    """Layers EQUIPMENT, PROCESS, SIGNAL, TEXT, FRAME in sheet mm."""
    from .blueprint_export import DxfWriter
    W, H = diagram.size
    dxf = DxfWriter(H)

    def prims(layer, items):
        for p in items:
            t = p[0]
            if t == "line":
                dxf.line(layer, p[2], p[3])
            elif t == "poly":
                pts = p[2] + ([p[2][0]] if p[3] else [])
                for a, b in zip(pts, pts[1:]):
                    dxf.line(layer, a, b)
            elif t == "circle":
                dxf.circle(layer, p[2], p[3])
            elif t == "arc":
                dxf.arc(layer, p[2], p[3], p[4], p[5])
            elif t == "text":
                dxf.text("TEXT", (p[2][0], p[2][1] + p[4] / 2.0), p[4],
                         p[3])
    m = P.MARGIN
    for a, b in (((m, m), (W - m, m)), ((W - m, m), (W - m, H - m)),
                 ((W - m, H - m), (m, H - m)), ((m, H - m), (m, m))):
        dxf.line("FRAME", a, b)
    for s in diagram.symbols:
        prims("EQUIPMENT", symbol_prims(s))
        for value, at, size, _align, _b in symbol_labels(s):
            dxf.text("TEXT", (at[0] - text_width(value, size) / 2.0,
                              at[1] + size / 2.0), size, value)
    spots = label_spots(diagram)
    for ln in diagram.lines:
        layer = "PROCESS" if ln.get("kind") in ("process", "secondary") \
            else "SIGNAL"
        pts = ln.get("points") or []
        for a, b in zip(pts, pts[1:]):
            dxf.line(layer, a, b)
        spot = spots.get(ln["id"])
        if spot is not None:
            dxf.text("TEXT", spot[1], LABEL_SIZE, spot[0], spot[2])
    for n in diagram.notes:
        for i, row in enumerate(str(n.get("text", "")).splitlines()):
            dxf.text("TEXT", (n["x"], n["y"] + n.get("size", 3.0) *
                              (1 + i * 1.6)), n.get("size", 3.0), row)
    f = diagram.fields
    x0, y0 = W - m - TB_W, H - m - P.TITLE_H
    for a, b in (((x0, y0), (W - m, y0)), ((x0, y0), (x0, H - m))):
        dxf.line("FRAME", a, b)
    dxf.text("TEXT", (x0 + 2, y0 + 8), 3.2, f.get("title", ""))
    dxf.text("TEXT", (x0 + 2, y0 + 15), 2.4, f.get("number", "") +
             "  rev " + f.get("revision", ""))
    Path(path).write_text(dxf.document(), encoding="ascii",
                          errors="replace")


WRITERS = {".pdf": write_pdf, ".svg": write_svg, ".png": write_png,
           ".dxf": write_dxf}


def export(diagram, path):
    suffix = Path(str(path)).suffix.lower()
    if suffix not in WRITERS:
        raise ValueError("A P&ID is written as .pdf, .svg, .png or .dxf")
    WRITERS[suffix](diagram, path)
    return str(path)


def schedule_rows(diagram):
    """{sheet: rows} of every schedule, header first — for CSV / XLSX."""
    sch = diagram.schedules()
    out = {}
    heads = {
        "Equipment": ["Tag", "Type", "Description", "Data", "3D part"],
        "Valves": ["Tag", "Type", "Description", "Data", "3D part"],
        "Instruments": ["Tag", "Function", "Type", "Description",
                        "Range / data"],
        "Lines": ["Line no.", "Service", "Size", "Material", "From", "To",
                  "Insulated", "Note"],
    }
    out["Equipment"] = [heads["Equipment"]] + [
        [r["tag"], r["type"], r["description"], r["data"], r["part"]]
        for r in sch["equipment"]]
    out["Valves"] = [heads["Valves"]] + [
        [r["tag"], r["type"], r["description"], r["data"], r["part"]]
        for r in sch["valves"]]
    out["Instruments"] = [heads["Instruments"]] + [
        [r["tag"], r.get("function", ""), r["type"], r["description"],
         r["data"]] for r in sch["instruments"]]
    out["Lines"] = [heads["Lines"]] + [
        [r["number"], r["service"], r["size"], r["material"], r["from"],
         r["to"], r["insulated"], r["label"]] for r in sch["lines"]]
    return out


def export_schedules(diagram, path):
    """.xlsx (one sheet per schedule) or .csv (all, one after another)."""
    rows = schedule_rows(diagram)
    if str(path).lower().endswith(".xlsx"):
        from . import xlsx
        return xlsx.write(path, rows)
    import csv
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        for name, table in rows.items():
            w.writerow([name.upper()])
            w.writerows(table)
            w.writerow([])
    return str(path)

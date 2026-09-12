"""Painting a `drawing.layout()` to a page — PDF, SVG, PNG through Qt,
and DXF (R12 entities, mm) written by hand — and File ▸ Make Drawing…

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import datetime
import math
from pathlib import Path

from PyQt5.QtCore import QPointF, QRectF, QSizeF, Qt
from PyQt5.QtGui import (QBrush, QColor, QFont, QImage, QPainter,
                         QPainterPath, QPen)

from . import drawing

INK = "#1c1c1c"
HIDDEN = "#666666"
DIM = "#1a4fa0"
HATCH = "#8a8a8a"


def paint(painter, lay, px_per_mm):
    """Draw the sheet with the painter's origin at the top-left corner
    of the page, *px_per_mm* device units per sheet mm."""
    k = px_per_mm
    W, H = lay["width"] * k, lay["height"] * k

    def pt(x, y):                              # sheet mm (y up) -> device
        return QPointF(x * k, H - y * k)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.fillRect(QRectF(0, 0, W, H), QColor("white"))
    m = lay["margin"] * k
    frame = QPen(QColor(INK), 0.5 * k)
    painter.setPen(frame)
    painter.setBrush(Qt.NoBrush)
    painter.drawRect(QRectF(m, m, W - 2 * m, H - 2 * m))
    solid = QPen(QColor(INK), 0.35 * k, Qt.SolidLine, Qt.RoundCap)
    dashed = QPen(QColor(HIDDEN), 0.25 * k, Qt.CustomDashLine, Qt.FlatCap)
    dashed.setDashPattern([6.0, 3.0])
    dim_pen = QPen(QColor(DIM), 0.2 * k)
    s = lay["scale"]
    font = QFont("Helvetica")
    font.setPixelSize(int(3.0 * k))
    painter.setFont(font)
    for view in lay["views"]:
        if view.get("section") is not None:
            _paint_section(painter, view, s, k, pt, solid)
        else:
            painter.setPen(dashed)
            for a, b in view["lines"]["hidden"]:
                painter.drawLine(pt(*drawing.to_sheet(view, *a, s)),
                                 pt(*drawing.to_sheet(view, *b, s)))
            painter.setPen(solid)
            for a, b in view["lines"]["visible"]:
                painter.drawLine(pt(*drawing.to_sheet(view, *a, s)),
                                 pt(*drawing.to_sheet(view, *b, s)))
        # the view's name under it
        b = (view["lines"]["bounds"] if view.get("lines")
             else view["section"]["bounds"])
        cx = view["x"] + (b[2] - b[0]) * s / 2
        # under the width dimension when there is one (its line sits
        # gap*0.35 below the view, its text a little lower still)
        below = 6.0
        if view["dims"]:
            below = -min(d["offset"][1] for d in view["dims"]) * s + 9.0
        label = pt(cx, view["y"] - below)
        painter.setPen(QPen(QColor(INK)))
        painter.drawText(QRectF(label.x() - 40 * k, label.y() - 2 * k,
                                80 * k, 5 * k), Qt.AlignHCenter, view["name"])
        for d in view["dims"]:
            _paint_dimension(painter, view, d, s, k, pt, dim_pen)
    _paint_title_block(painter, lay, k, pt, frame, font)


def _paint_dimension(painter, view, d, s, k, pt, pen):
    ax, ay = drawing.to_sheet(view, *d["a"], s)
    bx, by = drawing.to_sheet(view, *d["b"], s)
    ox, oy = d["offset"][0] * s, d["offset"][1] * s
    p1, p2 = (ax + ox, ay + oy), (bx + ox, by + oy)
    painter.setPen(pen)
    # extension lines a little past the dimension line, then the line
    ext = 1.5
    ux, uy = (ox, oy)
    ln = math.hypot(ux, uy) or 1.0
    ux, uy = ux / ln, uy / ln
    painter.drawLine(pt(ax, ay), pt(p1[0] + ux * ext, p1[1] + uy * ext))
    painter.drawLine(pt(bx, by), pt(p2[0] + ux * ext, p2[1] + uy * ext))
    painter.drawLine(pt(*p1), pt(*p2))
    # arrow heads
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    dl = math.hypot(dx, dy) or 1.0
    dx, dy = dx / dl, dy / dl
    for tip, sign in ((p1, 1), (p2, -1)):
        head = QPainterPath()
        head.moveTo(pt(*tip))
        head.lineTo(pt(tip[0] + sign * dx * 2.5 - dy * 0.8,
                       tip[1] + sign * dy * 2.5 + dx * 0.8))
        head.lineTo(pt(tip[0] + sign * dx * 2.5 + dy * 0.8,
                       tip[1] + sign * dy * 2.5 - dx * 0.8))
        head.closeSubpath()
        painter.fillPath(head, QBrush(QColor(DIM)))
    mid = ((p1[0] + p2[0]) / 2 + ux * 3.0, (p1[1] + p2[1]) / 2 + uy * 3.0)
    c = pt(*mid)
    painter.drawText(QRectF(c.x() - 30 * k, c.y() - 2.2 * k, 60 * k,
                            4.4 * k), Qt.AlignCenter, d["text"])


def _paint_section(painter, view, s, k, pt, solid):
    sec = view["section"]
    path = QPainterPath()
    for o in sec["outlines"]:
        pts = [pt(*drawing.to_sheet(view, p[0], p[1], s))
               for p in o["points"]]
        if not pts:
            continue
        path.moveTo(pts[0])
        for p in pts[1:]:
            path.lineTo(p)
        if o["closed"]:
            path.closeSubpath()
    path.setFillRule(Qt.OddEvenFill)
    b = sec["bounds"]
    x0, y0 = drawing.to_sheet(view, b[0], b[1], s)
    x1, y1 = drawing.to_sheet(view, b[2], b[3], s)
    painter.save()
    painter.setClipPath(path)
    painter.setPen(QPen(QColor(HATCH), 0.15 * k))
    step = 2.5
    span = (x1 - x0) + (y1 - y0)
    t = -span
    while t < span:
        painter.drawLine(pt(x0 + t, y0), pt(x0 + t + (y1 - y0), y1))
        t += step
    painter.restore()
    painter.setPen(solid)
    painter.setBrush(Qt.NoBrush)
    painter.drawPath(path)


def _paint_title_block(painter, lay, k, pt, frame, font):
    m, bh, W = lay["margin"], lay["block_h"], lay["width"]
    top = m + bh
    painter.setPen(frame)
    painter.drawLine(pt(m, top), pt(W - m, top))
    cols = [m, m + 90.0, m + 150.0, m + 200.0, W - m]
    for x in cols[1:-1]:
        painter.drawLine(pt(x, m), pt(x, top))
    small = QFont(font)
    small.setPixelSize(int(2.4 * k))
    big = QFont(font)
    big.setPixelSize(int(4.5 * k))
    big.setBold(True)
    cells = [(cols[0], cols[1], "TITLE", lay["title"], big),
             (cols[1], cols[2], "SCALE", lay["scale_label"], font),
             (cols[2], cols[3], "UNITS", "mm", font),
             (cols[3], cols[4], "DATE / SHEET",
              f"{datetime.date.today().isoformat()}   {lay['sheet']}  "
              f"1 / 1", font)]
    for x0, x1, head, text, f in cells:
        painter.setFont(small)
        painter.setPen(QPen(QColor(HIDDEN)))
        painter.drawText(QRectF(pt(x0 + 1.5, top - 1.0).x(),
                                pt(x0, top - 1.0).y(), (x1 - x0) * k,
                                4 * k), Qt.AlignLeft, head)
        painter.setFont(f)
        painter.setPen(QPen(QColor(INK)))
        painter.drawText(QRectF(pt(x0 + 1.5, m + bh - 6.0).x(),
                                pt(x0, m + bh - 6.0).y(), (x1 - x0) * k,
                                (bh - 7.0) * k), Qt.AlignLeft | Qt.AlignVCenter,
                         text)
    painter.setFont(small)
    painter.setPen(QPen(QColor(HIDDEN)))
    painter.drawText(QRectF(pt(W - m - 60.0, m + 3.0).x(),
                            pt(0, m + 3.0).y(), 58 * k, 3 * k),
                     Qt.AlignRight, "KherveCAD · third-angle projection")


# ------------------------------------------------------------- writers

def to_image(lay, px_per_mm=4.0):
    W = int(lay["width"] * px_per_mm)
    H = int(lay["height"] * px_per_mm)
    img = QImage(W, H, QImage.Format_ARGB32)
    img.fill(QColor("white"))
    p = QPainter(img)
    paint(p, lay, px_per_mm)
    p.end()
    return img


def write_pdf(lay, path):
    from PyQt5.QtGui import QPageSize, QPdfWriter
    writer = QPdfWriter(str(path))
    writer.setPageSize(QPageSize(QSizeF(lay["width"], lay["height"]),
                                 QPageSize.Millimeter))
    writer.setPageMargins(__import__("PyQt5.QtCore",
                                     fromlist=["QMarginsF"]).QMarginsF(
        0, 0, 0, 0))
    writer.setResolution(300)
    k = 300.0 / 25.4
    p = QPainter(writer)
    paint(p, lay, k)
    p.end()


def write_svg(lay, path):
    from PyQt5.QtCore import QSize
    from PyQt5.QtSvg import QSvgGenerator
    gen = QSvgGenerator()
    gen.setFileName(str(path))
    k = 4.0
    gen.setSize(QSize(int(lay["width"] * k), int(lay["height"] * k)))
    gen.setViewBox(QRectF(0, 0, lay["width"] * k, lay["height"] * k))
    gen.setTitle(lay["title"])
    p = QPainter(gen)
    paint(p, lay, k)
    p.end()


def write_png(lay, path, px_per_mm=6.0):
    to_image(lay, px_per_mm).save(str(path))


def write_dxf(lay, path):
    """A minimal DXF R12: the views' lines (layer VISIBLE / HIDDEN), the
    dimensions as lines and TEXT (layer DIM), the section outlines
    (layer SECTION) and the title text, in sheet millimetres."""
    out = ["0", "SECTION", "2", "ENTITIES"]

    def line(x0, y0, x1, y1, layer):
        out.extend(["0", "LINE", "8", layer, "10", f"{x0:.4f}", "20",
                    f"{y0:.4f}", "30", "0", "11", f"{x1:.4f}", "21",
                    f"{y1:.4f}", "31", "0"])

    def text(x, y, h, value, layer):
        out.extend(["0", "TEXT", "8", layer, "10", f"{x:.4f}", "20",
                    f"{y:.4f}", "30", "0", "40", f"{h:.3f}", "1",
                    str(value)])
    s = lay["scale"]
    for view in lay["views"]:
        if view.get("section") is not None:
            for o in view["section"]["outlines"]:
                pts = [drawing.to_sheet(view, p[0], p[1], s)
                       for p in o["points"]]
                for a, b in zip(pts, pts[1:] + (pts[:1] if o["closed"]
                                                else [])):
                    line(a[0], a[1], b[0], b[1], "SECTION")
        else:
            for layer, key in (("VISIBLE", "visible"), ("HIDDEN", "hidden")):
                for a, b in view["lines"][key]:
                    pa = drawing.to_sheet(view, *a, s)
                    pb = drawing.to_sheet(view, *b, s)
                    line(pa[0], pa[1], pb[0], pb[1], layer)
        b = (view["lines"]["bounds"] if view.get("lines")
             else view["section"]["bounds"])
        text(view["x"], view["y"] - 6.0, 3.0, view["name"], "TEXT")
        for d in view["dims"]:
            ax, ay = drawing.to_sheet(view, *d["a"], s)
            bx, by = drawing.to_sheet(view, *d["b"], s)
            ox, oy = d["offset"][0] * s, d["offset"][1] * s
            line(ax + ox, ay + oy, bx + ox, by + oy, "DIM")
            line(ax, ay, ax + ox, ay + oy, "DIM")
            line(bx, by, bx + ox, by + oy, "DIM")
            text((ax + bx) / 2 + ox, (ay + by) / 2 + oy + 1.0, 2.5,
                 d["text"], "DIM")
    m = lay["margin"]
    text(m + 1.5, m + 4.0, 4.0, lay["title"], "TEXT")
    text(m + 91.5, m + 4.0, 3.0, f"SCALE {lay['scale_label']}", "TEXT")
    out.extend(["0", "ENDSEC", "0", "EOF"])
    Path(path).write_text("\n".join(out) + "\n", encoding="ascii")


WRITERS = {".pdf": write_pdf, ".svg": write_svg, ".png": write_png,
           ".dxf": write_dxf}


def export(lay, path):
    suffix = Path(path).suffix.lower()
    if suffix not in WRITERS:
        raise ValueError("a drawing is written as .pdf, .svg, .png or "
                         ".dxf")
    WRITERS[suffix](lay, path)
    return str(path)

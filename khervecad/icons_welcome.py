"""Painted SolidWorks-style icons for the Welcome window (welcome.py):
Part, Assembly, Drawing and Open as large yellow shaded solids, sheets
and folders, the folder of Recent Folders, and the six Resources. Same
unit square, SolidWorks palette and iso helpers as icons_cad.py; original
drawings, never the program's artwork.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QPainterPath

from .icons_cad import DRAW, draws, icon, shade

STYLE = "SolidWorks"
BLUE = QColor("#2c62d0")
SKY = QColor("#8fc4ea")
GREEN = QColor("#3a9a3f")
RED = QColor("#d33a2c")
PAPER = QColor("#ffffff")
FOLDER = QColor("#f2c14e")


def _ellipse(d, c, rx, ry, fill=None, color=None, width=0.04):
    d.p.setPen(d.pen(color, width))
    d.p.setBrush(fill if fill is not None else Qt.NoBrush)
    d.p.drawEllipse(c, rx, ry)


# ================================================================ New
@draws("welcome_part")
def _part(d):
    """A yellow block with a boss on top and a blue sketch outline on
    its base plane — a part and the sketch it grew from."""
    d.cx, d.cy, d.k = 0.5, 0.66, 0.30
    d.ground([(-1.2, -1.2), (1.2, -1.2), (1.2, 1.2), (-1.2, 1.2)],
             d.pal.sketch, z=0.0, width=0.03)
    d.box(-1.0, -1.0, 0.0, 2.0, 2.0, 0.9)
    d.cyl(0.1, 0.0, 0.9, 0.6, 0.9)
    d.ground([(-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)],
             BLUE, z=0.0, width=0.025, dots=False)


@draws("welcome_assembly")
def _assembly(d):
    """Two yellow parts and a pale one, side by side."""
    d.cx, d.cy, d.k = 0.5, 0.66, 0.24
    d.box(-1.8, -0.4, 0.0, 1.5, 1.5, 0.7)
    d.cyl(-1.05, 0.35, 0.7, 0.45, 0.8)
    d.box(0.1, -1.4, 0.0, 1.7, 1.2, 1.1, SKY)
    d.box(0.4, 0.1, 0.0, 1.5, 1.4, 0.6, shade(d.pal.body, 0.9))
    d.ground([(-1.8, -1.6), (1.8, -1.6), (1.8, 1.8), (-1.8, 1.8)],
             d.pal.sketch, z=0.0, width=0.02)


@draws("welcome_drawing")
def _drawing(d):
    """A sheet with a frame, three views of a block and a title block."""
    d.poly([QPointF(0.10, 0.08), QPointF(0.90, 0.08), QPointF(0.90, 0.92),
            QPointF(0.10, 0.92)], PAPER, width=0.035)
    d.poly([QPointF(0.15, 0.13), QPointF(0.85, 0.13), QPointF(0.85, 0.87),
            QPointF(0.15, 0.87)], color=shade(d.pal.edge, 1.3), width=0.02)
    body = d.pal.body
    # front view and top view, drawn flat
    d.poly([QPointF(0.20, 0.50), QPointF(0.46, 0.50), QPointF(0.46, 0.68),
            QPointF(0.20, 0.68)], shade(body, 1.2), width=0.03)
    d.poly([QPointF(0.20, 0.20), QPointF(0.46, 0.20), QPointF(0.46, 0.42),
            QPointF(0.20, 0.42)], shade(body, 1.3), width=0.03)
    # an isometric of the same block
    d.cx, d.cy, d.k = 0.68, 0.45, 0.16
    d.box(-0.8, -0.8, 0.0, 1.6, 1.6, 1.0)
    # title block
    d.poly([QPointF(0.52, 0.74), QPointF(0.85, 0.74), QPointF(0.85, 0.87),
            QPointF(0.52, 0.87)], color=d.pal.edge, width=0.02)
    d.line(QPointF(0.52, 0.805), QPointF(0.85, 0.805), d.pal.edge, 0.015)
    d.line(QPointF(0.68, 0.74), QPointF(0.68, 0.87), d.pal.edge, 0.015)


@draws("welcome_open")
def _open(d):
    """A yellow folder with a green arrow coming out of it."""
    d.poly([QPointF(0.08, 0.22), QPointF(0.36, 0.22), QPointF(0.44, 0.32),
            QPointF(0.82, 0.32), QPointF(0.82, 0.84), QPointF(0.08, 0.84)],
           shade(FOLDER, 0.82))
    d.poly([QPointF(0.20, 0.46), QPointF(0.96, 0.46), QPointF(0.84, 0.84),
            QPointF(0.08, 0.84)], shade(FOLDER, 1.12))
    d.arrow(QPointF(0.20, 0.30), QPointF(0.62, 0.12), GREEN, 0.09, 0.2)


@draws("welcome_folder")
def _folder(d):
    d.poly([QPointF(0.08, 0.20), QPointF(0.38, 0.20), QPointF(0.46, 0.32),
            QPointF(0.92, 0.32), QPointF(0.92, 0.84), QPointF(0.08, 0.84)],
           shade(FOLDER, 0.85))
    d.poly([QPointF(0.08, 0.40), QPointF(0.92, 0.40), QPointF(0.92, 0.84),
            QPointF(0.08, 0.84)], shade(FOLDER, 1.12))


# ========================================================== resources
@draws("welcome_new")
def _whats_new(d):
    _ellipse(d, QPointF(0.5, 0.52), 0.36, 0.36, PAPER, BLUE, 0.05)
    d.text(0.44, 0.7, "?", 0.5, BLUE)
    star = QPainterPath()
    for i in range(10):
        r = 0.14 if i % 2 == 0 else 0.06
        a = math.radians(-90 + 36 * i)
        q = QPointF(0.78 + r * math.cos(a), 0.18 + r * math.sin(a))
        star.moveTo(q) if i == 0 else star.lineTo(q)
    star.closeSubpath()
    d.path(star, QColor("#f7b500"), shade(QColor("#f7b500"), 0.7), 0.02)


@draws("welcome_guide")
def _guide(d):
    d.poly([QPointF(0.10, 0.20), QPointF(0.48, 0.28), QPointF(0.48, 0.84),
            QPointF(0.10, 0.76)], PAPER, color=BLUE, width=0.045)
    d.poly([QPointF(0.90, 0.20), QPointF(0.52, 0.28), QPointF(0.52, 0.84),
            QPointF(0.90, 0.76)], PAPER, color=BLUE, width=0.045)
    for y in (0.40, 0.52, 0.64):
        d.line(QPointF(0.17, y), QPointF(0.42, y + 0.04), SKY, 0.035)
        d.line(QPointF(0.83, y), QPointF(0.58, y + 0.04), SKY, 0.035)


@draws("welcome_web")
def _web(d):
    c = QPointF(0.5, 0.5)
    _ellipse(d, c, 0.38, 0.38, SKY, BLUE, 0.05)
    _ellipse(d, c, 0.17, 0.38, None, BLUE, 0.035)
    d.line(QPointF(0.12, 0.5), QPointF(0.88, 0.5), BLUE, 0.035)
    d.line(QPointF(0.5, 0.12), QPointF(0.5, 0.88), BLUE, 0.035)
    d.p.setPen(d.pen(BLUE, 0.035))
    d.p.setBrush(Qt.NoBrush)
    d.p.drawArc(QRectF(0.16, 0.22, 0.68, 0.30), 0, 180 * 16)
    d.p.drawArc(QRectF(0.16, 0.48, 0.68, 0.30), 180 * 16, 180 * 16)


@draws("welcome_source")
def _source(d):
    d.poly([QPointF(0.14, 0.16), QPointF(0.86, 0.16), QPointF(0.86, 0.84),
            QPointF(0.14, 0.84)], QColor("#2b3137"), width=0.03)
    d.text(0.22, 0.52, "</>", 0.28, QColor("#f2c14e"))
    d.line(QPointF(0.24, 0.68), QPointF(0.62, 0.68), SKY, 0.04)


@draws("welcome_update")
def _update(d):
    c = QPointF(0.5, 0.5)
    d.p.setPen(d.pen(BLUE, 0.075))
    d.p.setBrush(Qt.NoBrush)
    d.p.drawArc(QRectF(0.16, 0.16, 0.68, 0.68), 40 * 16, 150 * 16)
    d.p.drawArc(QRectF(0.16, 0.16, 0.68, 0.68), 220 * 16, 150 * 16)
    d.arrow(QPointF(0.74, 0.22), QPointF(0.80, 0.34), BLUE, 0.07, 0.17)
    d.arrow(QPointF(0.26, 0.78), QPointF(0.20, 0.66), BLUE, 0.07, 0.17)
    _ellipse(d, c, 0.05, 0.05, BLUE, BLUE, 0.01)


@draws("welcome_support")
def _support(d):
    d.poly([QPointF(0.12, 0.28), QPointF(0.88, 0.28), QPointF(0.88, 0.86),
            QPointF(0.12, 0.86)], PAPER, color=shade(RED, 0.8), width=0.05)
    d.poly([QPointF(0.36, 0.16), QPointF(0.64, 0.16), QPointF(0.64, 0.28),
            QPointF(0.36, 0.28)], color=shade(RED, 0.8), width=0.04)
    d.poly([QPointF(0.44, 0.40), QPointF(0.56, 0.40), QPointF(0.56, 0.50),
            QPointF(0.66, 0.50), QPointF(0.66, 0.62), QPointF(0.56, 0.62),
            QPointF(0.56, 0.74), QPointF(0.44, 0.74), QPointF(0.44, 0.62),
            QPointF(0.34, 0.62), QPointF(0.34, 0.50), QPointF(0.44, 0.50)],
           RED, color=shade(RED, 0.7), width=0.02)


@draws("welcome_learn")
def _learn(d):
    d.poly([QPointF(0.50, 0.18), QPointF(0.92, 0.38), QPointF(0.50, 0.58),
            QPointF(0.08, 0.38)], BLUE, width=0.04)
    d.poly([QPointF(0.24, 0.50), QPointF(0.50, 0.63), QPointF(0.76, 0.50),
            QPointF(0.76, 0.70), QPointF(0.50, 0.84), QPointF(0.24, 0.70)],
           shade(BLUE, 1.25), width=0.04)
    d.line(QPointF(0.90, 0.42), QPointF(0.90, 0.72), d.pal.edge, 0.035)


@draws("welcome_tip")
def _tip(d):
    _ellipse(d, QPointF(0.5, 0.40), 0.26, 0.26, QColor("#f7e27a"),
             QColor("#a88a10"), 0.045)
    d.poly([QPointF(0.38, 0.62), QPointF(0.62, 0.62), QPointF(0.58, 0.78),
            QPointF(0.42, 0.78)], QColor("#c4c8cc"), width=0.035)
    d.line(QPointF(0.44, 0.88), QPointF(0.56, 0.88), d.pal.edge, 0.05)


# ================================================================ API
RESOURCE_KEYS = {
    "What's New": "welcome_new", "User Guide": "welcome_guide",
    "Website": "welcome_web", "Source on GitHub": "welcome_source",
    "Check for Updates": "welcome_update", "Get Support": "welcome_support",
}

KEYS = ("welcome_part", "welcome_assembly", "welcome_drawing",
        "welcome_open", "welcome_folder", "welcome_learn", "welcome_tip",
        *RESOURCE_KEYS.values())


def get(key):
    """The SolidWorks-style QIcon of *key* (always painted, whatever the
    window's Interface Style)."""
    return icon(key, STYLE)


def kind_of(path) -> str:
    """Which badge a card wears: a document's `part` / `assembly`
    (read from the file: more than one Object, or one placed instance,
    is an assembly) — fast and tolerant, `part` when unsure."""
    try:
        import json
        with open(path, encoding="utf-8") as fh:
            tree = json.load(fh).get("tree", {})
    except Exception:
        return "part"
    objects = [c for c in tree.get("children", [])
               if c.get("type") in ("component", "reference")]
    return "assembly" if len(objects) > 1 or any(
        c.get("type") == "reference" for c in objects) else "part"


assert all(k in DRAW for k in KEYS)

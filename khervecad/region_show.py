# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""The regions of a sketch, SHOWN while Extruded Boss / Cut picks them
(2026-11-12, the user: "we would understand what regions it created. It
would be visible on the screen"). Every closed area gets a pale colour of
its own and its number at its centre; a picked one is filled solid in
the accent colour with a bold number, so what will be solid and what
will stay a hole is plain before OK. Before, the only sign of a pick was
a red slab seen through the holes, which read as the holes being picked.

Painted through View3D's ``overlay_painters`` (never in clean pictures).
"""

PALETTE = [(91, 155, 213), (112, 173, 71), (237, 125, 49), (165, 105, 189),
           (38, 166, 154), (255, 192, 0), (233, 99, 132), (128, 128, 200)]
PICKED = (0, 120, 215)


def start(window, regions):
    """Show *regions* [(world loops [[(x, y, z)]], world label point,
    number)] until :func:`stop`."""
    window._region_show = dict(regions=regions, picked=set())
    if not getattr(window, "_region_show_painter", False):
        window.view3d.overlay_painters.append(
            lambda painter, project: paint(window, painter, project))
        window._region_show_painter = True
    window.view3d.update()


def set_picked(window, picked):
    state = getattr(window, "_region_show", None)
    if state is not None:
        state["picked"] = set(picked)
        window.view3d.update()


def stop(window):
    if getattr(window, "_region_show", None) is not None:
        window._region_show = None
        window.view3d.update()


def label(picked, count):
    """The Profiles box text: which regions are picked."""
    if not picked:
        return "Click the regions to use (%d found)" % count
    return "Picked: %s  (of %d)" % (
        ", ".join(str(i + 1) for i in sorted(picked)), count)


def paint(window, painter, project):
    state = getattr(window, "_region_show", None)
    if not state:
        return
    from PyQt5.QtCore import QPointF, Qt
    from PyQt5.QtGui import QBrush, QColor, QFont, QPainterPath, QPen
    painter.save()
    try:
        labels = []
        for k, (loops, at, number) in enumerate(state["regions"]):
            path = QPainterPath()
            path.setFillRule(Qt.OddEvenFill)
            ok = True
            for loop in loops:
                pts = [project(p) for p in loop]
                if any(p is None for p in pts) or len(pts) < 3:
                    ok = False
                    break
                path.moveTo(QPointF(pts[0][0], pts[0][1]))
                for p in pts[1:]:
                    path.lineTo(QPointF(p[0], p[1]))
                path.closeSubpath()
            if not ok:
                continue
            on = k in state["picked"]
            r, g, b = PICKED if on else PALETTE[k % len(PALETTE)]
            painter.setBrush(QBrush(QColor(r, g, b, 150 if on else 55)))
            painter.setPen(QPen(QColor(r, g, b, 230), 2.0 if on else 1.0))
            painter.drawPath(path)
            q = project(at)
            if q is not None:
                labels.append((q, number, on, (r, g, b)))
        font = QFont()
        font.setBold(True)
        font.setPointSizeF(10)
        painter.setFont(font)
        for q, number, on, (r, g, b) in labels:
            text = str(number)
            w = 10 + 7 * len(text)
            box_x, box_y = q[0] - w / 2, q[1] - 9
            painter.setPen(QPen(QColor(r, g, b), 1.5))
            painter.setBrush(QBrush(QColor(r, g, b) if on
                                    else QColor(255, 255, 255, 230)))
            painter.drawRoundedRect(int(box_x), int(box_y), int(w), 18, 6, 6)
            painter.setPen(QColor(255, 255, 255) if on else QColor(r, g, b))
            painter.drawText(int(box_x), int(box_y), int(w), 18,
                             Qt.AlignCenter, text)
    finally:
        painter.restore()

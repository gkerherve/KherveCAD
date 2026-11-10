# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""Sketch relation marks, one look in the 2D sketch and the 3D view, as
SolidWorks draws them (2026-11-10, the user: "look again at all
constraints ... how it is done in SolidWorks"):

- a small square tile beside the entity, holding a DRAWN symbol (a level
  bar for Horizontal, two strokes for Parallel, a circle and a line for
  Tangent, a pin for Fix...) — no longer letters, orange in 2D and green
  in 3D;
- shown while a sketch is edited, switched with View ▸ Sketch Relations
  (QSettings `sketch/relations`, `shown` / `set_shown`, default on) — off,
  the drawing shows its dimensions alone;
- two points simply joined (a line drawn from another's end) carry NO
  mark (`hidden`): SolidWorks merges them into one point. A point lying
  ON a line or circle keeps its coincident mark.
"""

from . import sketch_constraints as sc

#: the tile's side in pixels
SIZE = 17
#: the inks: symbol / tile outline, tile fill, a relation picked to delete
INK = "#2e7d32"
FILL = (240, 250, 238, 240)
HOT = "#d32f2f"
SETTING = "sketch/relations"


# ------------------------------------------------------------ the switch
def shown():
    from PyQt5.QtCore import QSettings
    v = QSettings("Kherve", "KherveCAD").value(SETTING, True)
    return v not in (False, "false", "0", 0)


def set_shown(on):
    from PyQt5.QtCore import QSettings
    QSettings("Kherve", "KherveCAD").setValue(SETTING, bool(on))


def action(win):
    """The checkable View ▸ Sketch Relations action (one per window)."""
    act = getattr(win, "_relations_act", None)
    if act is not None:
        return act
    from PyQt5.QtWidgets import QAction
    from . import language
    act = QAction(language.tr("Sketch Relations"), win)
    act.setCheckable(True)
    act.setChecked(shown())
    act.setStatusTip(language.tr(
        "Show the relation marks (horizontal, parallel, tangent…) of the "
        "sketch being edited"))

    def toggled(on):
        set_shown(on)
        for view in (getattr(win, "view2d", None),
                     getattr(win, "view3d", None)):
            if view is not None:
                (view.viewport() if hasattr(view, "viewport")
                 else view).update()
    act.toggled.connect(toggled)
    win._relations_act = act
    return act


# ---------------------------------------------------------- what shows
def hidden(container, row):
    """True for a relation that draws no mark: two POINTS made one."""
    if row.get("kind") != "coincident":
        return False
    refs = row.get("refs") or []
    if len(refs) != 2:
        return False
    try:
        return all(sc._geom(container, r, {})[0] == "point" for r in refs)
    except (KeyError, ValueError, IndexError, TypeError):
        return False


#: a point held ON something: one mark, at the point
AT_POINT = ("coincident", "fix", "on_edge", "midpoint", "point_on")


def spots(kind, refs):
    """The refs a relation's marks stand at."""
    return list(refs[:1]) if kind in AT_POINT else list(refs)


# ------------------------------------------------------------- drawing
def rect_at(x, y, dx=0.0):
    """The tile's rectangle beside an entity at (x, y) view pixels,
    *dx* along when several share the spot."""
    from PyQt5.QtCore import QRectF
    return QRectF(x + 6 + dx, y - 7 - SIZE, SIZE, SIZE)


def paint(painter, rect, kind, hot=False):
    """One relation tile in *rect* (view pixels, painter untransformed)."""
    from PyQt5.QtCore import QPointF, QRectF, Qt
    from PyQt5.QtGui import QBrush, QColor, QPen
    ink = QColor(HOT if hot else INK)
    painter.save()
    painter.setRenderHint(painter.Antialiasing, True)
    painter.setPen(QPen(ink, 1.0))
    painter.setBrush(QBrush(QColor(*FILL)))
    painter.drawRoundedRect(rect, 3, 3)
    pen = QPen(ink, 1.6)
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    x0, y0, s = rect.x(), rect.y(), rect.width()

    def P(u, v):                       # 0..1 across the tile, v down
        return QPointF(x0 + u * s, y0 + v * s)

    def line(a, b, c, d):
        painter.drawLine(P(a, b), P(c, d))

    def ring(u, v, r, fill=False):
        painter.setBrush(QBrush(ink) if fill else Qt.NoBrush)
        painter.drawEllipse(P(u, v), r * s, r * s)
        painter.setBrush(Qt.NoBrush)
    if kind == "horizontal":
        line(.22, .5, .78, .5)
    elif kind == "vertical":
        line(.5, .22, .5, .78)
    elif kind == "diagonal":
        line(.25, .75, .75, .25)
    elif kind == "parallel":
        line(.25, .72, .5, .28)
        line(.5, .72, .75, .28)
    elif kind == "perpendicular":
        line(.22, .75, .78, .75)
        line(.5, .75, .5, .25)
    elif kind == "tangent":
        ring(.5, .42, .2)
        line(.2, .72, .8, .72)
    elif kind == "equal":
        line(.25, .4, .75, .4)
        line(.25, .62, .75, .62)
    elif kind == "concentric":
        ring(.5, .5, .28)
        ring(.5, .5, .1, fill=True)
    elif kind == "collinear":
        line(.15, .5, .42, .5)
        line(.58, .5, .85, .5)
    elif kind == "midpoint":
        line(.2, .62, .8, .62)
        ring(.5, .62, .09, fill=True)
        line(.5, .25, .5, .45)
    elif kind == "symmetric":
        dash = QPen(pen)
        dash.setStyle(Qt.DotLine)
        painter.setPen(dash)
        line(.5, .18, .5, .82)
        painter.setPen(pen)
        ring(.24, .5, .08, fill=True)
        ring(.76, .5, .08, fill=True)
    elif kind == "fix":
        # a pin: head, needle
        ring(.5, .34, .15, fill=True)
        line(.5, .48, .5, .82)
        line(.3, .52, .7, .52)
    elif kind == "coincident":
        ring(.42, .5, .14, fill=True)
        ring(.6, .5, .14)
    elif kind in ("point_on", "on_edge"):
        if kind == "on_edge":
            dash = QPen(pen)
            dash.setStyle(Qt.DashLine)
            painter.setPen(dash)
        line(.15, .62, .85, .62)
        painter.setPen(pen)
        ring(.5, .62, .12, fill=True)
    else:                                  # anything new: its letter
        from .sketch_constrain_ui import MARK
        painter.drawText(QRectF(rect), int(Qt.AlignCenter),
                         MARK.get(kind, "?"))
    painter.restore()

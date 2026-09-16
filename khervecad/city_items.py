"""The City Builder plan's QGraphicsItems: buildings, roads, trees and
street lights drawn from above in a Y-up millimetre scene.

Each item holds the SPEC DICT it draws (one entry of the city spec's
"buildings", "roads", "trees" or "lights" list) and writes a drag
straight back into it, then reports through a callback — no document
coupling; the dialog decides when to Build.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import (QBrush, QColor, QPainter, QPainterPath,
                         QPainterPathStroker, QPen, QPolygonF)
from PyQt5.QtWidgets import QGraphicsItem

from . import city as C
from . import city_buildings as B
from .city_trees import TREE_KINDS

GRID = 500.0
SELECT = QColor("#2f7de1")


def snap(v, grid=GRID):
    return round(v / grid) * grid


def wrap(rz) -> float:
    """An angle in [0, 360): a turn all the way round is allowed."""
    rz = float(rz) % 360.0
    return 0.0 if abs(rz - 360.0) < 1e-9 else rz


class RotateHandle(QGraphicsItem):
    """A round grip in front of a selected piece: drag it round the
    piece to turn it (5° steps, Shift for 15°), any angle 0-360°."""

    SIZE = 8.0          # px

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.setFlags(QGraphicsItem.ItemIgnoresTransformations)
        self.setCursor(Qt.PointingHandCursor)
        self.setZValue(60)
        self.setToolTip("Drag round to turn (Shift: 15° steps)")
        self.place()

    def place(self):
        self.setPos(0.0, -self.owner.handle_reach())

    def boundingRect(self):
        s = self.SIZE + 2
        return QRectF(-s, -s, 2 * s, 2 * s)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(SELECT, 2.0))
        painter.setBrush(QColor("white"))
        painter.drawEllipse(QPointF(0, 0), self.SIZE, self.SIZE)
        painter.drawLine(QPointF(-4, 0), QPointF(4, 0))

    def mousePressEvent(self, event):
        event.accept()

    def mouseMoveEvent(self, event):
        centre = self.owner.scenePos()
        p = event.scenePos()
        angle = math.degrees(math.atan2(p.y() - centre.y(),
                                        p.x() - centre.x())) + 90.0
        step = 15.0 if event.modifiers() & Qt.ShiftModifier else 5.0
        self.owner.turn_to(wrap(round(angle / step) * step))

    def mouseReleaseEvent(self, event):
        if self.owner.on_release:
            self.owner.on_release(self.owner)


def _pen(colour, width=0.0, cosmetic=True, style=Qt.SolidLine):
    pen = QPen(QColor(colour), width, style)
    pen.setCosmetic(cosmetic)
    pen.setJoinStyle(Qt.RoundJoin)
    pen.setCapStyle(Qt.RoundCap)
    return pen


class _Movable(QGraphicsItem):
    """Common drag behaviour: snapped to the grid, written back into the
    spec on every move, reported when released."""

    def __init__(self, spec, on_change=None, on_pick=None, on_release=None):
        super().__init__()
        self.spec = spec
        self.on_change, self.on_pick = on_change, on_pick
        self.on_release = on_release
        # set before any flag: itemChange runs inside setPos, and an
        # exception escaping a Qt virtual aborts the process
        self._syncing = True
        self.setFlags(QGraphicsItem.ItemIsMovable
                      | QGraphicsItem.ItemIsSelectable
                      | QGraphicsItem.ItemSendsGeometryChanges)
        self.setPos(float(spec.get("x", 0.0)), float(spec.get("y", 0.0)))
        self._syncing = False

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and not self._syncing:
            return QPointF(snap(value.x()), snap(value.y()))
        if change == QGraphicsItem.ItemPositionHasChanged \
                and not self._syncing:
            self.spec["x"], self.spec["y"] = self.pos().x(), self.pos().y()
            if self.on_change:
                self.on_change(self)
        if change == QGraphicsItem.ItemSelectedHasChanged:
            self._show_handle(bool(value))
            if value and self.on_pick:
                self.on_pick(self)
        return super().itemChange(change, value)

    #: pieces that turn show a rotate handle while selected
    ROTATES = True
    on_turn = None

    def _show_handle(self, on):
        handle = getattr(self, "_handle", None)
        if handle is not None:
            handle.setParentItem(None)
            if handle.scene():
                handle.scene().removeItem(handle)
            self._handle = None
        if on and self.ROTATES:
            self._handle = RotateHandle(self)

    def handle_reach(self):
        r = self.boundingRect()
        return max(abs(r.top()), abs(r.bottom())) * 0.8 + 800.0

    def turn_to(self, rz):
        self.spec["rz"] = rz
        self.setRotation(rz)
        if self.on_turn:
            self.on_turn(self)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self.on_release:
            self.on_release(self)

    def sync(self):
        """Follow the spec after an edit in the side panel."""
        self._syncing = True
        self.prepareGeometryChange()
        self.setPos(float(self.spec.get("x", 0.0)),
                    float(self.spec.get("y", 0.0)))
        self.setRotation(float(self.spec.get("rz", 0.0)))
        self._syncing = False
        handle = getattr(self, "_handle", None)
        if handle is not None:
            handle.place()
        self.update()


class BuildingItem(_Movable):
    """A building's footprint in its wall colour, its roof drawn over it
    (ridge line for a pitched roof, parapet for a flat one, a circle for
    a round tower) and a door marker on the front (-Y) side."""

    def __init__(self, spec, index, **kw):
        super().__init__(spec, **kw)
        self.index = index
        self.setRotation(float(spec.get("rz", 0.0)))
        self.setZValue(10)

    def resolved(self):
        return B.footprint(self.spec, self.index)

    def boundingRect(self):
        r, wings = self.resolved()
        m = max(r["w"], r["d"]) * 0.8 + 2000
        return QRectF(-m, -m, 2 * m, 2 * m)

    def shape(self):
        r, wings = self.resolved()
        path = QPainterPath()
        for x0, y0, w, d in wings:
            path.addRect(QRectF(x0, y0, w, d))
        return path

    def paint(self, painter, option, widget=None):
        r, wings = self.resolved()
        painter.setRenderHint(QPainter.Antialiasing)
        wall = QColor(r["color"])
        roof = QColor(r["roof_color"])
        selected = self.isSelected()
        outline = _pen(SELECT if selected else "#3b3f45",
                       2.5 if selected else 1.0)
        if r["style"] == "round tower":
            rad = min(r["w"], r["d"]) / 2
            painter.setPen(outline)
            painter.setBrush(roof)
            painter.drawEllipse(QPointF(0, 0), rad, rad)
            painter.setPen(_pen(roof.darker(150)))
            painter.drawEllipse(QPointF(0, 0), rad * 0.15, rad * 0.15)
        else:
            for x0, y0, w, d in wings:
                rect = QRectF(x0, y0, w, d)
                painter.setPen(outline)
                painter.setBrush(roof if r["roof"] != "flat" else
                                 QColor("#a8a59f"))
                painter.drawRect(rect)
                if r["roof"] == "flat":
                    inset = min(w, d) * 0.08
                    painter.setPen(_pen("#7a7670"))
                    painter.setBrush(QColor("#8a8580"))
                    painter.drawRect(rect.adjusted(inset, inset, -inset,
                                                   -inset))
                else:
                    painter.setPen(_pen(roof.darker(160), 1.5))
                    cx, cy = x0 + w / 2, y0 + d / 2
                    if w >= d:
                        half = (w / 2) if r["roof"] == "gable" else \
                            max(w - d, 0) / 2
                        painter.drawLine(QPointF(cx - half, cy),
                                         QPointF(cx + half, cy))
                        if r["roof"] == "hip":
                            for sx in (-1, 1):
                                for sy in (-1, 1):
                                    painter.drawLine(
                                        QPointF(cx + sx * half, cy),
                                        QPointF(cx + sx * w / 2,
                                                cy + sy * d / 2))
                    else:
                        half = (d / 2) if r["roof"] == "gable" else \
                            max(d - w, 0) / 2
                        painter.drawLine(QPointF(cx, cy - half),
                                         QPointF(cx, cy + half))
                        if r["roof"] == "hip":
                            for sx in (-1, 1):
                                for sy in (-1, 1):
                                    painter.drawLine(
                                        QPointF(cx, cy + sy * half),
                                        QPointF(cx + sx * w / 2,
                                                cy + sy * d / 2))
            # wall colour as a band round the roof's edge
            painter.setPen(_pen(wall, 3.0))
            painter.setBrush(Qt.NoBrush)
            for x0, y0, w, d in wings:
                painter.drawRect(QRectF(x0, y0, w, d))
        # the front: a door triangle pointing out of the -Y side
        fy = -r["d"] / 2
        tri = QPolygonF([QPointF(-700, fy), QPointF(700, fy),
                         QPointF(0, fy - 1200)])
        painter.setPen(Qt.NoPen)
        painter.setBrush(SELECT if selected else QColor("#5b3a29"))
        painter.drawPolygon(tri)

    def label(self):
        r, _w = self.resolved()
        return (f"{r['name']} — {r['style']}, {r['floors']} floor"
                f"{'s' if r['floors'] > 1 else ''}")


class TreeItem(_Movable):
    def __init__(self, spec, **kw):
        super().__init__(spec, **kw)
        self.setRotation(float(spec.get("rz", 0.0)))
        self.setZValue(20)

    def radius(self):
        from .city_trees import species
        from .treegen import SPECIES
        kind = species(self.spec.get("kind", "oak"))
        h = float(self.spec.get("height", TREE_KINDS.get(kind, 6000.0)))
        k = {"cone": 0.22, "column": 0.1, "weeping": 0.4, "palm": 0.35,
             "shrub": 0.6}.get(SPECIES[kind]["crown"], 0.3)
        return max(400.0, h * k)

    def boundingRect(self):
        r = self.radius() + 200
        return QRectF(-r, -r, 2 * r, 2 * r)

    def shape(self):
        path = QPainterPath()
        r = self.radius()
        path.addEllipse(QPointF(0, 0), r, r)
        return path

    def paint(self, painter, option, widget=None):
        from .city_trees import DARK_LEAF, LIGHT_LEAF
        from .city_trees import species
        kind = species(self.spec.get("kind", "oak"))
        r = self.radius()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(_pen(SELECT if self.isSelected() else
                            QColor(DARK_LEAF.get(kind, "#3f7a32")).darker(130),
                            2.5 if self.isSelected() else 1.0))
        col = QColor(LIGHT_LEAF.get(kind, "#62a043"))
        col.setAlpha(210)
        painter.setBrush(col)
        if kind in ("spruce", "pine", "cypress"):
            star = QPolygonF([QPointF(math.cos(a) * (r if i % 2 == 0
                                                     else r * 0.55),
                                      math.sin(a) * (r if i % 2 == 0
                                                     else r * 0.55))
                              for i, a in enumerate(
                                  k * math.pi / 8 for k in range(16))])
            painter.drawPolygon(star)
        else:
            painter.drawEllipse(QPointF(0, 0), r, r)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#6b4b33"))
        painter.drawEllipse(QPointF(0, 0), r * 0.12, r * 0.12)

    def label(self):
        return f"Tree — {self.spec.get('kind', 'broadleaf')}"


class LightItem(_Movable):
    """A street light seen from above: the post and its arm reaching
    the way the lamp faces (local -Y, turned by rz)."""

    def __init__(self, spec, **kw):
        super().__init__(spec, **kw)
        self.setRotation(float(spec.get("rz", 0.0)))
        self.setZValue(25)

    def boundingRect(self):
        return QRectF(-700, -2500, 1400, 3200)

    def shape(self):
        path = QPainterPath()
        path.addEllipse(QPointF(0, 0), 500, 500)
        path.addRect(QRectF(-300, -2300, 600, 2300))
        return path

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        sel = self.isSelected()
        painter.setPen(_pen(SELECT if sel else "#30343a", 3.0 if sel else 2.0))
        painter.drawLine(QPointF(0, 0), QPointF(0, -2000))
        painter.setBrush(QColor("#30343a"))
        painter.drawEllipse(QPointF(0, 0), 260, 260)
        painter.setBrush(QColor("#ffd966"))
        painter.drawRect(QRectF(-200, -2350, 400, 650))

    def label(self):
        return "Street light"


class PropItem(_Movable):
    """A Part Library piece (a pitch, a lamp, a hill...) drawn as its
    real top view (`planview.part_view`), turned by its rz."""

    def __init__(self, spec, **kw):
        super().__init__(spec, **kw)
        self.setRotation(float(spec.get("rz", 0.0)))
        self.setZValue(5)
        self._view_key = None
        self.view = None
        self._load()

    def _load(self):
        from . import planview
        key = (self.spec.get("part_id"), repr(sorted(
            (self.spec.get("dims") or {}).items())))
        if key != self._view_key:
            self._view_key = key
            try:
                self.view = planview.part_view(self.spec.get("part_id"),
                                               self.spec.get("dims") or {})
            except Exception:
                self.view = None
            self.prepareGeometryChange()

    def sync(self):
        self._load()
        super().sync()

    def boundingRect(self):
        if self.view is not None:
            return self.view.rect.adjusted(-200, -200, 200, 200)
        return QRectF(-1000, -1000, 2000, 2000)

    def shape(self):
        path = QPainterPath()
        path.addRect(self.boundingRect())
        return path

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        if self.view is not None:
            painter.drawImage(self.view.rect, self.view.image)
            painter.setPen(_pen("#3b3f45", 1.0))
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(self.view.outline)
        else:
            painter.setPen(_pen("#3b3f45", 1.0))
            painter.setBrush(QColor(200, 200, 200, 120))
            painter.drawRect(QRectF(-1000, -1000, 2000, 2000))
        if self.isSelected():
            painter.setPen(_pen(SELECT, 2.5))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.boundingRect().adjusted(150, 150, -150,
                                                          -150))

    def label(self):
        from .library import PARTS
        spec = PARTS.get(self.spec.get("part_id")) or {}
        size = (self.spec.get("dims") or {}).get("_size", "")
        return f"{spec.get('label', self.spec.get('part_id'))} {size}".strip()


class Handle(QGraphicsItem):
    """A road vertex: drag it and the road follows."""

    SIZE = 7.0          # px, screen size

    def __init__(self, road_item, index):
        super().__init__(road_item)
        self.road_item, self.index = road_item, index
        self._syncing = True
        self.setFlags(QGraphicsItem.ItemIsMovable
                      | QGraphicsItem.ItemSendsGeometryChanges
                      | QGraphicsItem.ItemIgnoresTransformations)
        self.setCursor(Qt.SizeAllCursor)
        self.setZValue(40)
        pt = road_item.spec["points"][index]
        self._syncing = True
        self.setPos(float(pt[0]), float(pt[1]))
        self._syncing = False

    def boundingRect(self):
        s = self.SIZE
        return QRectF(-s, -s, 2 * s, 2 * s)

    def paint(self, painter, option, widget=None):
        painter.setPen(QPen(SELECT, 1.5))
        painter.setBrush(QColor("white"))
        painter.drawRect(self.boundingRect().adjusted(2, 2, -2, -2))

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and not self._syncing:
            return QPointF(snap(value.x()), snap(value.y()))
        if change == QGraphicsItem.ItemPositionHasChanged \
                and not self._syncing:
            self.road_item.move_point(self.index, self.pos())
        return super().itemChange(change, value)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self.road_item.on_release:
            self.road_item.on_release(self.road_item)


class RoadItem(QGraphicsItem):
    """A road's polyline at its true width: pavement, tarmac, a dashed
    centre line; handles on its vertices while selected."""

    def __init__(self, spec, on_change=None, on_pick=None, on_release=None):
        super().__init__()
        self.spec = spec
        self.on_change, self.on_pick = on_change, on_pick
        self.on_release = on_release
        self.setFlags(QGraphicsItem.ItemIsSelectable)
        self.setZValue(1)
        self.handles = []
        self._path = QPainterPath()
        self._rebuild()

    def _polyline(self):
        pts = [QPointF(float(p[0]), float(p[1]))
               for p in self.spec.get("points") or []]
        path = QPainterPath()
        if pts:
            path.moveTo(pts[0])
            for p in pts[1:]:
                path.lineTo(p)
        return path

    def _rebuild(self):
        self.prepareGeometryChange()
        width, walk, _ = C.road_style(self.spec)
        self._path = self._polyline()
        stroker = QPainterPathStroker()
        stroker.setWidth(width + 2 * walk)
        stroker.setCapStyle(Qt.RoundCap)
        stroker.setJoinStyle(Qt.RoundJoin)
        self._outline = stroker.createStroke(self._path)

    def boundingRect(self):
        return self._outline.boundingRect().adjusted(-100, -100, 100, 100)

    def shape(self):
        return self._outline

    def paint(self, painter, option, widget=None):
        width, walk, dashed = C.road_style(self.spec)
        painter.setRenderHint(QPainter.Antialiasing)
        if walk > 0:
            painter.setPen(_pen("#b8b3aa", width + 2 * walk, cosmetic=False))
            painter.drawPath(self._path)
        painter.setPen(_pen("#4a4c50", width, cosmetic=False))
        painter.drawPath(self._path)
        if dashed:
            pen = QPen(QColor("#f1efe6"), 150)
            pen.setDashPattern([20, 20])
            painter.setPen(pen)
            painter.drawPath(self._path)
        if self.isSelected():
            painter.setPen(_pen(SELECT, 2.0))
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(self._outline)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemSelectedHasChanged:
            self.show_handles(bool(value))
            if value and self.on_pick:
                self.on_pick(self)
        return super().itemChange(change, value)

    def show_handles(self, on):
        for h in self.handles:
            h.setParentItem(None)
            if h.scene():
                h.scene().removeItem(h)
        self.handles = []
        if on:
            self.handles = [Handle(self, i) for i in
                            range(len(self.spec.get("points") or []))]

    def move_point(self, index, pos):
        self.spec["points"][index] = [pos.x(), pos.y()]
        self._rebuild()
        self.update()
        if self.on_change:
            self.on_change(self)

    def sync(self):
        self._rebuild()
        self.update()
        if self.isSelected():
            self.show_handles(True)

    def label(self):
        n = len(self.spec.get("points") or [])
        return f"Road — {self.spec.get('kind', 'street')}, {n} points"


class RoadDraft(QGraphicsItem):
    """The road being drawn: its points so far and a rubber band to the
    cursor."""

    def __init__(self, width):
        super().__init__()
        self.points, self.cursor, self.width = [], None, width
        self.setZValue(50)

    def boundingRect(self):
        pts = self.points + ([self.cursor] if self.cursor else [])
        if not pts:
            return QRectF()
        xs = [p.x() for p in pts]
        ys = [p.y() for p in pts]
        m = self.width
        return QRectF(min(xs) - m, min(ys) - m, max(xs) - min(xs) + 2 * m,
                      max(ys) - min(ys) + 2 * m)

    def set_cursor(self, pt):
        self.prepareGeometryChange()
        self.cursor = pt
        self.update()

    def add(self, pt):
        self.prepareGeometryChange()
        self.points.append(pt)
        self.update()

    def paint(self, painter, option, widget=None):
        pts = self.points + ([self.cursor] if self.cursor else [])
        if not pts:
            return
        path = QPainterPath(pts[0])
        for p in pts[1:]:
            path.lineTo(p)
        pen = QPen(QColor(47, 125, 225, 90), self.width)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.drawPath(path)
        painter.setPen(_pen(SELECT, 1.5, style=Qt.DashLine))
        painter.drawPath(path)
        painter.setBrush(QBrush(QColor("white")))
        for p in self.points:
            painter.drawEllipse(p, 250, 250)

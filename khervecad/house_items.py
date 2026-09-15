"""QGraphicsItems for the House Builder's floor-plan canvas
(`house_dialog.py`): a draggable, corner-resizable rectangle for each
Room, and a small draggable marker for each placed Furniture item.
Self-contained (no CadNode/DocumentModel coupling) — every drag writes
straight back into the `house.Room`/`house.Furniture` dataclass the
item represents, and the scene is Y-up like the rest of the app's 2D
views (the dialog flips the view, not these items).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QBrush, QColor, QPen
from PyQt5.QtWidgets import (QGraphicsItem, QGraphicsRectItem,
                             QGraphicsSimpleTextItem)

#: rooms/furniture snap to this grid while dragging or resizing, mm —
#: keeps adjacent rooms sharing an exact wall (house.collect_walls
#: merges two rooms' edges only when they match to 0.1 mm)
GRID = 50.0
MIN_ROOM = 500.0
FURNITURE_MARK = 400.0

ROOM_FILL = QColor(214, 224, 230, 210)
ROOM_FILL_SEL = QColor(190, 212, 232, 230)
ROOM_LINE = QColor("#2e3440")
FURN_FILL = QColor(200, 168, 120, 220)
FURN_LINE = QColor("#5b3d27")


def _snap(v: float) -> float:
    return round(v / GRID) * GRID


class Handle(QGraphicsRectItem):
    """Square corner handle, constant size on screen, that resizes the
    parent RoomItem when dragged."""

    SIZE = 8.0
    _CURSORS = {"TL": Qt.SizeFDiagCursor, "BR": Qt.SizeFDiagCursor,
               "TR": Qt.SizeBDiagCursor, "BL": Qt.SizeBDiagCursor}

    def __init__(self, role, parent):
        s = self.SIZE
        super().__init__(-s / 2.0, -s / 2.0, s, s, parent)
        self.role = role
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        self.setBrush(QBrush(QColor("#ffffff")))
        self.setPen(QPen(QColor("#2176c7"), 1.2))
        self.setCursor(self._CURSORS[role])
        self.setZValue(10.0)
        self.setAcceptedMouseButtons(Qt.LeftButton)

    def mousePressEvent(self, event):
        event.accept()

    def mouseMoveEvent(self, event):
        self.parentItem().handle_dragged(self.role, event.scenePos())

    def mouseReleaseEvent(self, event):
        event.accept()


class RoomItem(QGraphicsRectItem):
    """A draggable, corner-resizable rectangle bound to a `house.Room`.
    *on_change* is called after every move/resize (position or size)."""

    def __init__(self, room, on_change=None, on_pick=None):
        super().__init__()
        self.room = room
        self.on_change = on_change
        self.on_pick = on_pick
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setBrush(QBrush(ROOM_FILL))
        self.setPen(QPen(ROOM_LINE, 0))
        self.setCursor(Qt.SizeAllCursor)
        self.label = QGraphicsSimpleTextItem(room.name, self)
        self.label.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        self.handles = [Handle(role, self)
                        for role in ("TL", "TR", "BL", "BR")]
        self.apply_room()

    def apply_room(self):
        """house.Room -> item geometry."""
        self.setPos(self.room.x, self.room.y)
        self.setRect(0.0, 0.0, self.room.w, self.room.d)
        self.label.setText(self.room.name)
        self.label.setPos(6.0, 6.0)
        self._position_handles()

    def _position_handles(self):
        r = self.rect()
        pts = {"TL": r.topLeft(), "TR": r.topRight(),
               "BL": r.bottomLeft(), "BR": r.bottomRight()}
        for h in self.handles:
            h.setPos(pts[h.role])

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            value.setX(_snap(value.x()))
            value.setY(_snap(value.y()))
        elif change == QGraphicsItem.ItemPositionHasChanged:
            self.room.x, self.room.y = self.pos().x(), self.pos().y()
            if self.on_change:
                self.on_change()
        elif change == QGraphicsItem.ItemSelectedHasChanged and value \
                and self.on_pick:
            self.on_pick(self.room)
        return super().itemChange(change, value)

    def handle_dragged(self, role, scene_pos):
        x0, y0 = self.room.x, self.room.y
        x1, y1 = x0 + self.room.w, y0 + self.room.d
        px, py = _snap(scene_pos.x()), _snap(scene_pos.y())
        if "L" in role:
            x0 = min(px, x1 - MIN_ROOM)
        if "R" in role:
            x1 = max(px, x0 + MIN_ROOM)
        if "B" in role:
            y0 = min(py, y1 - MIN_ROOM)
        if "T" in role:
            y1 = max(py, y0 + MIN_ROOM)
        self.room.x, self.room.y = x0, y0
        self.room.w, self.room.d = x1 - x0, y1 - y0
        self.apply_room()
        if self.on_change:
            self.on_change()

    def paint(self, painter, option, widget=None):
        self.setBrush(QBrush(ROOM_FILL_SEL if self.isSelected()
                             else ROOM_FILL))
        super().paint(painter, option, widget)


class FurnitureItem(QGraphicsRectItem):
    """A small draggable marker bound to a `house.Furniture` — position
    only; rotation is edited in the dialog's furniture table."""

    def __init__(self, item, label, on_change=None, on_pick=None):
        super().__init__(-FURNITURE_MARK / 2.0, -FURNITURE_MARK / 2.0,
                         FURNITURE_MARK, FURNITURE_MARK)
        self.item = item
        self.on_change = on_change
        self.on_pick = on_pick
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setBrush(QBrush(FURN_FILL))
        self.setPen(QPen(FURN_LINE, 0))
        self.setZValue(5.0)
        self.setCursor(Qt.SizeAllCursor)
        self.setToolTip(label)
        text = QGraphicsSimpleTextItem(label, self)
        text.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        text.setPos(-FURNITURE_MARK / 2.0 + 4.0, -FURNITURE_MARK / 2.0 + 4.0)
        self.setPos(item.x, item.y)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            value.setX(_snap(value.x()))
            value.setY(_snap(value.y()))
        elif change == QGraphicsItem.ItemPositionHasChanged:
            self.item.x, self.item.y = self.pos().x(), self.pos().y()
            if self.on_change:
                self.on_change()
        elif change == QGraphicsItem.ItemSelectedHasChanged and value \
                and self.on_pick:
            self.on_pick(self.item)
        return super().itemChange(change, value)

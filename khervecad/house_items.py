"""QGraphicsItems for the House Builder's floor-plan canvas
(`house_dialog.py`), drawn the way an architect's plan reads:

- `RoomItem` — a room's floor, draggable, resizable from eight handles
  (shown on the selected room only), captioned with its name, size and
  area. Dragging a room carries its furniture with it.
- `WallsItem` — every wall of the floor at its real thickness, with
  the gaps the doors and windows leave (`house.collect_walls`, the
  same walls Build makes), under the rooms' floors.
- `OpeningItem` — a door (its leaf and swing arc) or a window (frame
  and glass line) in its wall; drag it along the wall, or onto another
  wall of its room.
- `FurnitureItem` — each piece at its REAL size and shape, seen from
  above in its own colours (`planview.part_view`), turned by its
  rotation. Double-click turns it 90° (Shift: the other way).
- `GardenItem` — the garden where Build puts it.

Self-contained (no CadNode/DocumentModel coupling) — every drag writes
straight back into the `house.Room` / `Opening` / `Furniture` it
represents and reports through the item's callback. The scene is Y-up
like the rest of the app's 2D views (the canvas flips the view, not
these items).

Handles are named by COMPASS side (N = +Y, the top of the flipped view)
rather than by Qt's y-down rect corners: naming them "top" from
`QRectF.topLeft()` put the handle drawn at the bottom of the room in
charge of its top edge. The selected room is raised above its
neighbours, so where two rooms share a corner the handle under the
cursor is the selected room's.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import (QBrush, QColor, QFont, QFontMetricsF, QPainter,
                         QPainterPath, QPen, QTransform)
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsRectItem

from . import house as H
from . import planview

#: rooms snap to this grid while dragging or resizing, mm — keeps
#: adjacent rooms sharing an exact wall (house.collect_walls merges two
#: rooms' edges only when they match to 0.1 mm)
GRID = 50.0
#: furniture, doors and windows move in finer steps
FINE_GRID = 10.0
MIN_ROOM = 500.0
FURNITURE_MARK = 400.0             # a part with no top view: a square

ROOM_FILL = QColor("#fbf8f1")
ROOM_FILL_SEL = QColor("#e1eefa")
WALL_FILL = QColor("#3b4048")
DOOR_LINE = QColor("#8a5a2b")
WINDOW_LINE = QColor("#2f86c4")
WINDOW_FILL = QColor(191, 224, 232, 230)
GARDEN_FILL = QColor(90, 156, 74, 80)
GARDEN_EDGE = QColor("#3f7d33")
FURN_LINE = QColor("#5b3d27")
SELECT = QColor("#2176c7")
#: an outdoor area's ground: lawn or paving (house.SURFACES)
OUTDOOR_FILLS = {"garden": QColor("#cfe6c4"), "paving": QColor("#e4e0d8")}
GARAGE_LINE = QColor("#6b7078")
GARAGE_FILL = QColor(216, 218, 221, 230)
ROOF_LINE = QColor(138, 90, 58, 180)

#: every resize handle: compass role -> (fx, fy), its place as a
#: fraction of the room's width/depth (Y-up: fy = 1 is the N edge)
HANDLE_ROLES = {"SW": (0.0, 0.0), "S": (0.5, 0.0), "SE": (1.0, 0.0),
                "E": (1.0, 0.5), "NE": (1.0, 1.0), "N": (0.5, 1.0),
                "NW": (0.0, 1.0), "W": (0.0, 0.5)}

#: which way is "into the room" from each side
INWARD = {"S": (0.0, 1.0), "N": (0.0, -1.0), "W": (1.0, 0.0),
          "E": (-1.0, 0.0)}


def _snap(v: float, grid: float = GRID) -> float:
    return round(v / grid) * grid


def _cosmetic(color, width=1.0, style=Qt.SolidLine) -> QPen:
    pen = QPen(color, width, style)
    pen.setCosmetic(True)
    return pen


def room_caption(room) -> str:
    """"Kitchen / 3.00 × 4.50 m · 13.5 m²" — what a plan writes in a
    room."""
    return (f"{room.name}\n{room.w / 1000:.2f} × {room.d / 1000:.2f} m"
            f"  ·  {room.w * room.d / 1e6:.1f} m²"
            + ("" if room.indoor else "  ·  outdoor"))


def nearest_side(room, point):
    """(side, along) — the side of *room* nearest *point* and how far
    along it (from the side's start corner) *point* projects."""
    best = None
    for side, ((x1, y1), (x2, y2)) in room.edges().items():
        length = math.hypot(x2 - x1, y2 - y1) or 1.0
        t = ((point.x() - x1) * (x2 - x1)
             + (point.y() - y1) * (y2 - y1)) / length
        t = max(0.0, min(length, t))
        px = x1 + (x2 - x1) * t / length
        py = y1 + (y2 - y1) * t / length
        dist = math.hypot(point.x() - px, point.y() - py)
        if best is None or dist < best[0]:
            best = (dist, side, t)
    return best[1], best[2]


def wall_pieces(p1, p2, openings, thickness, height):
    """The plan rectangles of one wall (`house.collect_walls` output):
    the solid runs between its openings, each end of the wall carried
    on half a thickness so the corners close."""
    horizontal = abs(p1[1] - p2[1]) < 1e-6
    if horizontal:
        a0, a1 = sorted((p1[0], p2[0]))
        c = p1[1]
    else:
        a0, a1 = sorted((p1[1], p2[1]))
        c = p1[0]
    half = thickness / 2.0
    length = a1 - a0
    runs, cursor = [], -half
    for start, end, *_rest in H._opening_spans(openings, length, height):
        if start - cursor > 1e-6:
            runs.append((cursor, start))
        cursor = end
    if length + half - cursor > 1e-6:
        runs.append((cursor, length + half))
    if horizontal:
        return [QRectF(a0 + s, c - half, e - s, thickness) for s, e in runs]
    return [QRectF(c - half, a0 + s, thickness, e - s) for s, e in runs]


class Label(QGraphicsItem):
    """Screen-sized text on a soft white plate, upright whatever the
    view's flip and zoom or the parent's rotation. *anchor* "center"
    centres it on its position; "corner" hangs it below-right of it."""

    def __init__(self, parent, text="", anchor="center", bold=False,
                 size=9.0):
        super().__init__(parent)
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        self.setAcceptedMouseButtons(Qt.NoButton)
        self.font = QFont()
        self.font.setPointSizeF(size)
        self.font.setBold(bold)
        self.anchor = anchor
        self.text = ""
        self._rect = QRectF()
        self.set_text(text)

    def set_text(self, text):
        self.prepareGeometryChange()
        self.text = text
        fm = QFontMetricsF(self.font)
        lines = text.split("\n")
        w = max(fm.horizontalAdvance(line) for line in lines) + 10.0
        h = fm.height() * len(lines) + 4.0
        self._rect = (QRectF(-w / 2.0, -h / 2.0, w, h)
                      if self.anchor == "center"
                      else QRectF(8.0, 6.0, w, h))
        self.update()

    def width(self) -> float:
        return self._rect.width()

    def boundingRect(self):
        return self._rect

    def paint(self, painter, option, widget=None):
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, 200))
        painter.drawRoundedRect(self._rect, 3.0, 3.0)
        painter.setPen(QColor("#1f2328"))
        painter.setFont(self.font)
        painter.drawText(self._rect, Qt.AlignCenter, self.text)


class Handle(QGraphicsRectItem):
    """Square resize handle, constant size on screen, that resizes the
    parent RoomItem when dragged."""

    SIZE = 11.0
    # the view is Y-flipped, so on screen NE/SW run "/" and NW/SE "\"
    _CURSORS = {"NW": Qt.SizeFDiagCursor, "SE": Qt.SizeFDiagCursor,
                "NE": Qt.SizeBDiagCursor, "SW": Qt.SizeBDiagCursor,
                "N": Qt.SizeVerCursor, "S": Qt.SizeVerCursor,
                "E": Qt.SizeHorCursor, "W": Qt.SizeHorCursor}

    def __init__(self, role, parent):
        s = self.SIZE
        super().__init__(-s / 2.0, -s / 2.0, s, s, parent)
        self.role = role
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        self.setBrush(QBrush(QColor("#ffffff")))
        self.setPen(QPen(SELECT, 1.5))
        self.setCursor(self._CURSORS[role])
        self.setZValue(10.0)
        self.setAcceptedMouseButtons(Qt.LeftButton)
        self.setToolTip("Drag to resize the room")

    def mousePressEvent(self, event):
        room = self.parentItem()
        if not room.isSelected():         # a handle press picks its room
            if room.scene() is not None:
                room.scene().clearSelection()
            room.setSelected(True)
        event.accept()

    def mouseMoveEvent(self, event):
        self.parentItem().handle_dragged(self.role, event.scenePos())

    def mouseReleaseEvent(self, event):
        event.accept()


class RoomItem(QGraphicsRectItem):
    """A draggable, edge- and corner-resizable room floor bound to a
    `house.Room`. *on_change(room)* is called after every move/resize;
    a move shifts the room's furniture with it. The floor is painted
    inside the walls (*inset* = half the wall thickness), which
    `WallsItem` draws underneath."""

    Z_IDLE, Z_SELECTED = 0.0, 1.0

    def __init__(self, room, on_change=None, on_pick=None, inset=0.0):
        super().__init__()
        self.room = room
        self.on_change = on_change
        self.on_pick = on_pick
        self.inset = inset
        self._syncing = False
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setPen(QPen(Qt.NoPen))
        self.setCursor(Qt.SizeAllCursor)
        self.setToolTip("Drag to move the room (its furniture comes "
                        "along); drag the blue squares to resize it")
        # the caption is its own item, centred and above the furniture:
        # as a child hung from a corner it hid under whatever stood
        # against that wall. It joins the room's scene (itemChange).
        self.label = Label(None)
        self.label.setZValue(7.0)
        self.handles = [Handle(role, self) for role in HANDLE_ROLES]
        for h in self.handles:
            h.setVisible(False)           # only the selected room's
        self.apply_room()

    def apply_room(self):
        """house.Room -> item geometry."""
        self._syncing = True
        self.setPos(self.room.x, self.room.y)
        self._syncing = False
        self.setRect(0.0, 0.0, self.room.w, self.room.d)
        self.label.set_text(room_caption(self.room))
        self._place_label()
        self._position_handles()

    def _place_label(self):
        self.label.setPos(self.room.x + self.room.w / 2.0,
                          self.room.y + self.room.d / 2.0)

    def _position_handles(self):
        for h in self.handles:
            fx, fy = HANDLE_ROLES[h.role]
            h.setPos(fx * self.room.w, fy * self.room.d)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and \
                not self._syncing:
            return QPointF(_snap(value.x()), _snap(value.y()))
        if change == QGraphicsItem.ItemPositionHasChanged and \
                not self._syncing:
            dx = self.pos().x() - self.room.x
            dy = self.pos().y() - self.room.y
            if dx or dy:
                self.room.x += dx
                self.room.y += dy
                for f in self.room.furniture:     # contents come along
                    f.x += dx
                    f.y += dy
                self._place_label()
                if self.on_change:
                    self.on_change(self.room)
        elif change == QGraphicsItem.ItemSceneHasChanged:
            try:
                scene = self.scene()
                if scene is not None and self.label.scene() is not scene:
                    scene.addItem(self.label)
            except RuntimeError:          # the scene is being torn down
                pass
        elif change == QGraphicsItem.ItemSelectedHasChanged:
            self.setZValue(self.Z_SELECTED if value else self.Z_IDLE)
            for h in self.handles:
                h.setVisible(bool(value))
            if value and self.on_pick:
                self.on_pick(self.room)
        return super().itemChange(change, value)

    def handle_dragged(self, role, scene_pos):
        x0, y0 = self.room.x, self.room.y
        x1, y1 = x0 + self.room.w, y0 + self.room.d
        px, py = _snap(scene_pos.x()), _snap(scene_pos.y())
        if "W" in role:
            x0 = min(px, x1 - MIN_ROOM)
        if "E" in role:
            x1 = max(px, x0 + MIN_ROOM)
        if "S" in role:
            y0 = min(py, y1 - MIN_ROOM)
        if "N" in role:
            y1 = max(py, y0 + MIN_ROOM)
        self.room.x, self.room.y = x0, y0
        self.room.w, self.room.d = x1 - x0, y1 - y0
        self.apply_room()
        if self.on_change:
            self.on_change(self.room)

    def paint(self, painter, option, widget=None):
        inset = self.inset if self.room.indoor else 0.0   # no walls outside
        inner = self.rect().adjusted(inset, inset, -inset, -inset)
        painter.setPen(Qt.NoPen)
        painter.setBrush(ROOM_FILL_SEL if self.isSelected() else
                         OUTDOOR_FILLS.get(self.room.surface, ROOM_FILL))
        painter.drawRect(inner)
        if self.isSelected():
            painter.setPen(_cosmetic(SELECT, 1.5, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(inner)


class WallsItem(QGraphicsItem):
    """Every wall of a floor at its real thickness, the openings left as
    gaps — recomputed at each paint, so it follows a drag live. Under
    the rooms and click-through."""

    def __init__(self, floor):
        super().__init__()
        self.floor = floor
        self.setZValue(-1.0)
        self.setAcceptedMouseButtons(Qt.NoButton)
        self._rect = QRectF()
        self.refresh()

    def refresh(self):
        self.prepareGeometryChange()
        b = self.floor.bounds()
        t = self.floor.wall_thickness
        self._rect = (QRectF(b[0] - t, b[1] - t, b[2] - b[0] + 2 * t,
                             b[3] - b[1] + 2 * t) if b else QRectF())
        self.update()

    def boundingRect(self):
        return self._rect

    def paint(self, painter, option, widget=None):
        painter.setPen(Qt.NoPen)
        painter.setBrush(WALL_FILL)
        t, h = self.floor.wall_thickness, self.floor.wall_height
        for p1, p2, openings in H.collect_walls(self.floor):
            for rect in wall_pieces(p1, p2, openings, t, h):
                painter.drawRect(rect)


class OpeningItem(QGraphicsItem):
    """A door or window in its room's wall, drawn as a plan symbol in a
    local frame: x along the wall from the opening's start, y into the
    room. Drag it along the wall, or towards another wall of the room
    to move it there. *on_change(item)* after every move."""

    def __init__(self, room, opening, floor, on_change=None, on_pick=None):
        super().__init__()
        self.room = room
        self.opening = opening
        self.floor = floor
        self.on_change = on_change
        self.on_pick = on_pick
        self._grab = 0.0
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setZValue(6.0)
        self.setCursor(Qt.SizeAllCursor)
        self.setToolTip(f"{opening.kind.capitalize()} — drag along the "
                        "wall, or onto another wall of the room")
        self.apply()

    def frame(self):
        """((x, y) of the side's start, along, inward, side length)."""
        (x1, y1), (x2, y2) = self.room.edges()[self.opening.side]
        length = math.hypot(x2 - x1, y2 - y1) or 1.0
        along = ((x2 - x1) / length, (y2 - y1) / length)
        return (x1, y1), along, INWARD[self.opening.side], length

    def apply(self):
        """Opening -> item geometry (clamped into the wall, as Build
        clamps it)."""
        self.prepareGeometryChange()
        (x1, y1), d, n, length = self.frame()
        op = self.opening
        offset = max(0.0, min(op.offset, length - op.width))
        self.setTransform(QTransform(d[0], d[1], n[0], n[1], 0.0, 0.0))
        self.setPos(x1 + d[0] * offset, y1 + d[1] * offset)
        self.update()

    def _body(self) -> QRectF:
        t = self.floor.wall_thickness
        return QRectF(0.0, -t / 2.0, self.opening.width, t)

    def boundingRect(self):
        body = self._body()
        reach = {"door": self.opening.width,
                 "garage door": min(self.opening.height, 2200.0) * 0.9
                 }.get(self.opening.kind, 0.0)
        return QRectF(body.left(), body.top(), body.width(),
                      body.height() / 2.0 + max(reach, body.height() / 2.0)
                      ).adjusted(-40.0, -40.0, 40.0, 40.0)

    def shape(self):
        path = QPainterPath()
        path.addRect(self._body().adjusted(-40.0, -60.0, 40.0, 60.0))
        return path

    def paint(self, painter, option, widget=None):
        body = self._body()
        w = self.opening.width
        painter.setRenderHint(QPainter.Antialiasing)
        if self.opening.kind == "window":
            painter.setPen(_cosmetic(WINDOW_LINE, 1.4))
            painter.setBrush(WINDOW_FILL)
            painter.drawRect(body)
            painter.drawLine(QPointF(0.0, 0.0), QPointF(w, 0.0))
        elif self.opening.kind == "garage door":
            painter.setPen(_cosmetic(GARAGE_LINE, 1.4))
            painter.setBrush(GARAGE_FILL)
            painter.drawRect(body)
            # an up-and-over door: how far it swings into the garage
            painter.setPen(_cosmetic(GARAGE_LINE, 1.0, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(QRectF(0.0, 0.0, w, min(self.opening.height,
                                                      2200.0) * 0.9))
        else:
            painter.setPen(Qt.NoPen)
            painter.setBrush(ROOM_FILL)
            painter.drawRect(body)                 # the threshold
            painter.setPen(_cosmetic(DOOR_LINE, 1.0, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            arc = QPainterPath(QPointF(w, 0.0))    # the swing
            for i in range(1, 19):
                a = math.radians(i * 5.0)
                arc.lineTo(w * math.cos(a), w * math.sin(a))
            painter.drawPath(arc)
            painter.setPen(_cosmetic(DOOR_LINE, 2.4))
            painter.drawLine(QPointF(0.0, 0.0), QPointF(0.0, w))  # leaf
        if self.isSelected():
            painter.setPen(_cosmetic(SELECT, 2.0, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(body.adjusted(-30.0, -30.0, 30.0, 30.0))

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemSelectedHasChanged and value and \
                self.on_pick:
            self.on_pick(self.room, self.opening)
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            event.ignore()
            return
        if not self.isSelected():
            if self.scene() is not None:
                self.scene().clearSelection()
            self.setSelected(True)
        local = self.mapFromScene(event.scenePos())
        self._grab = max(0.0, min(self.opening.width, local.x()))
        event.accept()

    def mouseMoveEvent(self, event):
        side, along = nearest_side(self.room, event.scenePos())
        (x1, y1), (x2, y2) = self.room.edges()[side]
        length = math.hypot(x2 - x1, y2 - y1)
        offset = _snap(along - self._grab, FINE_GRID)
        offset = max(0.0, min(offset, length - self.opening.width))
        if (side, offset) != (self.opening.side, self.opening.offset):
            self.opening.side, self.opening.offset = side, offset
            self.apply()
            if self.on_change:
                self.on_change(self)
        event.accept()

    def mouseReleaseEvent(self, event):
        event.accept()


class FurnitureItem(QGraphicsItem):
    """A piece of furniture at its real size and shape, seen from above
    (`planview.part_view`), bound to a `house.Furniture`: drag to move,
    double-click to turn 90° (Shift: -90°). *on_change(item)* after a
    move or turn; *on_release(item)* when a drag ends."""

    def __init__(self, item, label, on_change=None, on_pick=None,
                 on_release=None):
        super().__init__()
        self.item = item
        self.on_change = on_change
        self.on_pick = on_pick
        self.on_release = on_release
        self._syncing = False
        self.view = planview.part_view(item.part_id, item.dims)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setZValue(5.0)
        self.setCursor(Qt.SizeAllCursor)
        self.setToolTip(f"{label} — drag to move, double-click to turn "
                        "it 90° (Shift+double-click: the other way)")
        self.label = Label(self, label, size=8.0)
        self.label.setPos(self.rect().center())
        self.apply()

    def rect(self) -> QRectF:
        if self.view is not None:
            return self.view.rect
        s = FURNITURE_MARK
        return QRectF(-s / 2.0, -s / 2.0, s, s)

    def apply(self):
        """Furniture -> item position and rotation."""
        self._syncing = True
        self.setPos(self.item.x, self.item.y)
        self.setRotation(self.item.rz)     # CCW in the Y-up scene
        self._syncing = False
        # a piece set higher is drawn over what it stands on (a TV over
        # its unit, a pendant over the table)
        self.setZValue(5.0 + min(max(self.item.z, 0.0), 3000.0) / 1000.0)

    def screen_width(self, px_per_mm) -> float:
        r = self.rect()
        return min(r.width(), r.height()) * px_per_mm \
            if abs(math.sin(math.radians(self.item.rz))) > 0.5 \
            else r.width() * px_per_mm

    def boundingRect(self):
        return self.rect().adjusted(-20.0, -20.0, 20.0, 20.0)

    def shape(self):
        path = QPainterPath()
        path.addRect(self.rect())
        return path

    def paint(self, painter, option, widget=None):
        r = self.rect()
        selected = self.isSelected()
        painter.setRenderHint(QPainter.Antialiasing)
        if self.view is not None:
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            painter.drawImage(r, self.view.image)
            painter.setPen(_cosmetic(FURN_LINE, 1.0))
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(self.view.outline)
        else:
            painter.setPen(_cosmetic(FURN_LINE, 1.0))
            painter.setBrush(QColor(200, 168, 120, 220))
            painter.drawRect(r)
        if selected:
            painter.setPen(_cosmetic(SELECT, 2.0, Qt.DashLine))
            painter.setBrush(QColor(33, 118, 199, 30))
            painter.drawRect(r.adjusted(-25.0, -25.0, 25.0, 25.0))

    def rotate_by(self, step):
        """Turn by *step* degrees, kept in (-180, 180]."""
        rz = (self.item.rz + step) % 360.0
        self.item.rz = rz - 360.0 if rz > 180.0 else rz
        self.apply()
        if self.on_change:
            self.on_change(self)

    def mouseDoubleClickEvent(self, event):
        self.rotate_by(-90.0 if event.modifiers() & Qt.ShiftModifier
                       else 90.0)
        event.accept()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self.on_release:
            self.on_release(self)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and \
                not self._syncing:
            return QPointF(_snap(value.x(), FINE_GRID),
                           _snap(value.y(), FINE_GRID))
        if change == QGraphicsItem.ItemPositionHasChanged and \
                not self._syncing:
            self.item.x, self.item.y = self.pos().x(), self.pos().y()
            if self.on_change:
                self.on_change(self)
        elif change == QGraphicsItem.ItemSelectedHasChanged and value \
                and self.on_pick:
            self.on_pick(self.item)
        return super().itemChange(change, value)


class GardenItem(QGraphicsRectItem):
    """The garden, where Build puts it (beside the house's east side) —
    edited in the Garden fields, so not draggable."""

    def __init__(self, rect):
        super().__init__(rect)
        self.setBrush(GARDEN_FILL)
        self.setPen(_cosmetic(GARDEN_EDGE, 1.2, Qt.DashLine))
        self.setZValue(-2.0)
        self.setAcceptedMouseButtons(Qt.NoButton)
        self.setToolTip("Garden — set its size in the Garden fields")
        label = Label(self, "Garden")
        label.setPos(rect.center())


class RoofItem(QGraphicsItem):
    """The top floor's roof seen from above — its eaves dashed, its
    ridge, hips or fall line drawn thin (`house.roof_outline`) — so the
    way it runs shows before Build. Click-through, over everything."""

    def __init__(self, outline):
        super().__init__()
        x0, y0, x1, y1 = outline["eave"]
        self.eave = QRectF(x0, y0, x1 - x0, y1 - y0)
        self.lines = outline["lines"]
        self.setZValue(8.0)
        self.setAcceptedMouseButtons(Qt.NoButton)

    def boundingRect(self):
        return self.eave.adjusted(-50.0, -50.0, 50.0, 50.0)

    def paint(self, painter, option, widget=None):
        painter.setBrush(Qt.NoBrush)
        painter.setPen(_cosmetic(ROOF_LINE, 1.2, Qt.DashLine))
        painter.drawRect(self.eave)
        painter.setPen(_cosmetic(ROOF_LINE, 1.0, Qt.DashDotLine))
        for (ax, ay), (bx, by) in self.lines:
            painter.drawLine(QPointF(ax, ay), QPointF(bx, by))

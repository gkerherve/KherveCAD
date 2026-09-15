"""AI/Library ▸ House Builder…: a non-modal window with its OWN 2D
floor-plan canvas (separate from the sketch/assembly view) — lay out
rectangular rooms floor by floor, cut door/window openings into their
walls, place furniture from the Part Library's room/home catalogue,
size a garden, then Build compiles the design into the document: one
Object per floor (stacked in Z, so it reads as a real house) and one
"Garden" Object beside it — see `house.py` for the geometry and
`house_items.py` for the canvas's draggable/resizable items.

One-per-window like `crystal_dialog.py` / `molecule_dialog.py`; each
Build is a fresh insert (like the Part Library's Insert), so clicking
it again after further edits adds another house rather than trying to
patch the first one in place.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import (QAbstractItemView, QComboBox, QDialog,
                             QDoubleSpinBox, QFormLayout, QGraphicsScene,
                             QGraphicsView, QGroupBox, QHBoxLayout, QLabel,
                             QLineEdit, QListWidget, QListWidgetItem,
                             QMessageBox, QPushButton, QSplitter,
                             QTableWidget, QTableWidgetItem, QVBoxLayout,
                             QWidget)

from . import house as H
from . import house_items as HI
from . import icons
from .library import PARTS as LIBRARY_PARTS

_ORDINALS = ("Ground floor", "First floor", "Second floor", "Third floor",
            "Fourth floor", "Fifth floor")
MIN_ROOM_UI = 500.0


def _floor_default_name(index: int) -> str:
    return _ORDINALS[index] if index < len(_ORDINALS) else f"Floor {index}"


def _spin(lo, hi, value, step=50.0, suffix=" mm", decimals=0):
    box = QDoubleSpinBox()
    box.setRange(lo, hi)
    box.setSingleStep(step)
    box.setDecimals(decimals)
    box.setSuffix(suffix)
    box.setValue(value)
    return box


class FloorCanvas(QGraphicsView):
    """The floor plan's own 2D canvas — Y-up, millimetres, a light grid,
    draggable/resizable Room rectangles and Furniture markers."""

    def __init__(self, dialog):
        super().__init__(QGraphicsScene())
        self.dialog = dialog
        self.setRenderHint(QPainter.Antialiasing)
        self.setBackgroundBrush(QColor("#f4f5f7"))
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.scale(0.09, -0.09)                # mm -> px, Y-up

    def rebuild(self, floor):
        scene = self.scene()
        scene.clear()
        if floor is None:
            return
        bounds = floor.bounds() or (0.0, 0.0, 4000.0, 4000.0)
        self._draw_grid(bounds)
        for room in floor.rooms:
            item = HI.RoomItem(room, on_change=self.dialog._room_edited,
                               on_pick=self.dialog._pick_room)
            item.setSelected(room is self.dialog.current_room)
            scene.addItem(item)
            for f in room.furniture:
                label = LIBRARY_PARTS.get(f.part_id, {}).get(
                    "label", f.part_id)
                fi = HI.FurnitureItem(
                    f, label, on_change=self.dialog._furniture_edited,
                    on_pick=lambda it, r=room: self.dialog._pick_furniture(
                        r, it))
                fi.setSelected(f is self.dialog.current_furniture)
                scene.addItem(fi)
        pad = 1500.0
        scene.setSceneRect(bounds[0] - pad, bounds[1] - pad,
                           (bounds[2] - bounds[0]) + 2 * pad,
                           (bounds[3] - bounds[1]) + 2 * pad)

    def _draw_grid(self, bounds):
        x0, y0, x1, y1 = (bounds[0] - 1000.0, bounds[1] - 1000.0,
                          bounds[2] + 1000.0, bounds[3] + 1000.0)
        pen = QPen(QColor("#dfe2e6"), 0)
        step = 1000.0
        x = step * (int(x0 // step))
        while x <= x1:
            self.scene().addLine(x, y0, x, y1, pen)
            x += step
        y = step * (int(y0 // step))
        while y <= y1:
            self.scene().addLine(x0, y, x1, y, pen)
            y += step
        origin_pen = QPen(QColor("#adb3ba"), 0)
        self.scene().addLine(x0, 0.0, x1, 0.0, origin_pen)
        self.scene().addLine(0.0, y0, 0.0, y1, origin_pen)

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)


class HouseBuilder(QDialog):
    """The House Builder window: floor/room lists and properties on the
    left, the floor-plan canvas on the right, garden + Build at the
    bottom."""

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle("House Builder")
        self.setModal(False)
        self.resize(1180, 760)
        self.house = H.House(
            floors=[H.Floor(_floor_default_name(0), rooms=[
                H.Room("Living room", 0.0, 0.0, 5000.0, 4000.0)])],
            garden=H.Garden())
        self.current_floor_index = 0
        self.current_room = self.house.floors[0].rooms[0]
        self.current_furniture = None
        self._building_ui = True
        self._build_ui()
        self._building_ui = False
        self._sync_all()

    # ------------------------------------------------------------ ui
    def _build_ui(self):
        root = QVBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

        left = QWidget()
        left_l = QVBoxLayout(left)
        left_l.setContentsMargins(4, 4, 4, 4)
        left.setMaximumWidth(420)
        splitter.addWidget(left)

        left_l.addWidget(self._floors_group())
        left_l.addWidget(self._floor_settings_group())
        left_l.addWidget(self._rooms_group())
        left_l.addWidget(self._room_fields_group())
        left_l.addWidget(self._openings_group(), 1)
        left_l.addWidget(self._furniture_group(), 1)

        right = QWidget()
        right_l = QVBoxLayout(right)
        right_l.setContentsMargins(4, 4, 4, 4)
        self.canvas = FloorCanvas(self)
        right_l.addWidget(self.canvas, 1)
        right_l.addWidget(self._garden_group())
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)

        bottom = QHBoxLayout()
        self.status = QLabel("")
        bottom.addWidget(self.status, 1)
        build_btn = QPushButton(icons.icon("mdi.home-city-outline"),
                                "Build")
        build_btn.setToolTip(
            "Insert the current design into the document: one Object "
            "per floor, stacked, plus a Garden Object beside the "
            "house. Clicking Build again adds another copy.")
        build_btn.clicked.connect(self._build)
        bottom.addWidget(build_btn)
        root.addLayout(bottom)

    def _floors_group(self):
        box = QGroupBox("Floors")
        lay = QVBoxLayout(box)
        self.floor_list = QListWidget()
        self.floor_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.floor_list.currentRowChanged.connect(self._floor_row_changed)
        lay.addWidget(self.floor_list)
        row = QHBoxLayout()
        add = QPushButton("+ Floor")
        add.clicked.connect(self._add_floor)
        rm = QPushButton("Remove floor")
        rm.clicked.connect(self._remove_floor)
        row.addWidget(add)
        row.addWidget(rm)
        lay.addLayout(row)
        return box

    def _floor_settings_group(self):
        box = QGroupBox("Floor settings")
        form = QFormLayout(box)
        self.wall_height = _spin(1500.0, 6000.0, H.WALL_HEIGHT)
        self.wall_thickness = _spin(50.0, 500.0, H.WALL_THICKNESS)
        self.slab_thickness = _spin(50.0, 500.0, H.SLAB_THICKNESS)
        for w, key in ((self.wall_height, "wall_height"),
                      (self.wall_thickness, "wall_thickness"),
                      (self.slab_thickness, "slab_thickness")):
            w.valueChanged.connect(
                lambda v, k=key: self._floor_field_changed(k, v))
        form.addRow("Wall height:", self.wall_height)
        form.addRow("Wall thickness:", self.wall_thickness)
        form.addRow("Slab thickness:", self.slab_thickness)
        return box

    def _rooms_group(self):
        box = QGroupBox("Rooms on this floor")
        lay = QVBoxLayout(box)
        self.room_list = QListWidget()
        self.room_list.currentRowChanged.connect(self._room_row_changed)
        lay.addWidget(self.room_list)
        row = QHBoxLayout()
        add = QPushButton("+ Room")
        add.clicked.connect(self._add_room)
        rm = QPushButton("Remove room")
        rm.clicked.connect(self._remove_room)
        row.addWidget(add)
        row.addWidget(rm)
        lay.addLayout(row)
        return box

    def _room_fields_group(self):
        box = QGroupBox("Selected room")
        form = QFormLayout(box)
        self.room_name = QLineEdit()
        self.room_name.editingFinished.connect(self._room_name_changed)
        self.room_x = _spin(-1e5, 1e5, 0.0)
        self.room_y = _spin(-1e5, 1e5, 0.0)
        self.room_w = _spin(MIN_ROOM_UI, 1e5, 4000.0)
        self.room_d = _spin(MIN_ROOM_UI, 1e5, 3000.0)
        for w, key in ((self.room_x, "x"), (self.room_y, "y"),
                      (self.room_w, "w"), (self.room_d, "d")):
            w.valueChanged.connect(
                lambda v, k=key: self._room_field_changed(k, v))
        form.addRow("Name:", self.room_name)
        form.addRow("X:", self.room_x)
        form.addRow("Y:", self.room_y)
        form.addRow("Width:", self.room_w)
        form.addRow("Depth:", self.room_d)
        return box

    def _openings_group(self):
        box = QGroupBox("Doors && windows (selected room)")
        lay = QVBoxLayout(box)
        self.openings_table = QTableWidget(0, 6)
        self.openings_table.setHorizontalHeaderLabels(
            ["Side", "Type", "Offset", "Width", "Height", "Sill"])
        self.openings_table.verticalHeader().setVisible(False)
        lay.addWidget(self.openings_table)
        row = QHBoxLayout()
        add_door = QPushButton("+ Door")
        add_door.clicked.connect(lambda: self._add_opening("door"))
        add_win = QPushButton("+ Window")
        add_win.clicked.connect(lambda: self._add_opening("window"))
        rm = QPushButton("Remove")
        rm.clicked.connect(self._remove_opening)
        row.addWidget(add_door)
        row.addWidget(add_win)
        row.addWidget(rm)
        lay.addLayout(row)
        return box

    def _furniture_group(self):
        box = QGroupBox("Furniture (selected room)")
        lay = QVBoxLayout(box)
        self.furniture_table = QTableWidget(0, 4)
        self.furniture_table.setHorizontalHeaderLabels(
            ["Part", "X", "Y", "Rotation"])
        self.furniture_table.verticalHeader().setVisible(False)
        lay.addWidget(self.furniture_table)
        row = QHBoxLayout()
        add = QPushButton("+ Add furniture…")
        add.clicked.connect(self._add_furniture)
        rm = QPushButton("Remove")
        rm.clicked.connect(self._remove_furniture)
        row.addWidget(add)
        row.addWidget(rm)
        lay.addLayout(row)
        return box

    def _garden_group(self):
        box = QGroupBox("Garden (beside the house)")
        form = QHBoxLayout(box)
        self.garden_w = _spin(0.0, 5e4, 4000.0)
        self.garden_d = _spin(0.0, 5e4, 6000.0)
        self.garden_gap = _spin(0.0, 1e4, 1500.0)
        for w, key in ((self.garden_w, "width"), (self.garden_d, "depth"),
                      (self.garden_gap, "gap")):
            w.valueChanged.connect(
                lambda v, k=key: self._garden_field_changed(k, v))
        form.addWidget(QLabel("Width:"))
        form.addWidget(self.garden_w)
        form.addWidget(QLabel("Depth:"))
        form.addWidget(self.garden_d)
        form.addWidget(QLabel("Gap from house:"))
        form.addWidget(self.garden_gap)
        return box

    # --------------------------------------------------------- floors
    @property
    def current_floor(self):
        if 0 <= self.current_floor_index < len(self.house.floors):
            return self.house.floors[self.current_floor_index]
        return None

    def _add_floor(self):
        index = len(self.house.floors)
        floor = H.Floor(_floor_default_name(index))
        prev = self.house.floors[-1] if self.house.floors else None
        if prev and prev.rooms:
            x0, y0, x1, y1 = prev.bounds()
            floor.rooms.append(H.Room(f"Room {index + 1}", x0, y0,
                                      min(4000.0, x1 - x0), min(3000.0,
                                      y1 - y0)))
        else:
            floor.rooms.append(H.Room("Room 1", 0.0, 0.0, 4000.0, 3000.0))
        self.house.floors.append(floor)
        self.current_floor_index = index
        self.current_room = floor.rooms[0]
        self.current_furniture = None
        self._sync_all()

    def _remove_floor(self):
        if len(self.house.floors) <= 1:
            QMessageBox.information(self, "House Builder",
                                    "A house needs at least one floor.")
            return
        del self.house.floors[self.current_floor_index]
        self.current_floor_index = max(0, self.current_floor_index - 1)
        floor = self.current_floor
        self.current_room = floor.rooms[0] if floor.rooms else None
        self.current_furniture = None
        self._sync_all()

    def _floor_row_changed(self, row):
        if self._building_ui or row < 0:
            return
        self.current_floor_index = row
        floor = self.current_floor
        self.current_room = floor.rooms[0] if floor and floor.rooms \
            else None
        self.current_furniture = None
        self._sync_all()

    def _floor_field_changed(self, key, value):
        if self._building_ui or self.current_floor is None:
            return
        setattr(self.current_floor, key, value)

    # ---------------------------------------------------------- rooms
    def _add_room(self):
        floor = self.current_floor
        if floor is None:
            return
        x, y = 0.0, 0.0
        if floor.rooms:
            x0, y0, x1, y1 = floor.bounds()
            x = x1
        room = H.Room(f"Room {len(floor.rooms) + 1}", x, y, 4000.0, 3000.0)
        floor.rooms.append(room)
        self.current_room = room
        self._sync_all()

    def _remove_room(self):
        floor = self.current_floor
        if floor is None or self.current_room is None:
            return
        floor.rooms.remove(self.current_room)
        self.current_room = floor.rooms[0] if floor.rooms else None
        self.current_furniture = None
        self._sync_all()

    def _room_row_changed(self, row):
        if self._building_ui or row < 0 or self.current_floor is None:
            return
        rooms = self.current_floor.rooms
        self.current_room = rooms[row] if row < len(rooms) else None
        self.current_furniture = None
        self._sync_room_fields()
        self._sync_openings_table()
        self._sync_furniture_table()
        self._rebuild_canvas()

    def _pick_room(self, room):
        self.current_room = room
        self.current_furniture = None
        self._sync_room_list_selection()
        self._sync_room_fields()
        self._sync_openings_table()
        self._sync_furniture_table()

    def _room_edited(self):
        """A drag/resize on the canvas changed the selected room."""
        self._sync_room_fields()

    def _room_name_changed(self):
        if self.current_room is None:
            return
        self.current_room.name = self.room_name.text().strip() or \
            self.current_room.name
        self._sync_room_list()
        self._rebuild_canvas()

    def _room_field_changed(self, key, value):
        if self._building_ui or self.current_room is None:
            return
        setattr(self.current_room, key, value)
        self._rebuild_canvas()

    # ------------------------------------------------------- openings
    def _add_opening(self, kind):
        if self.current_room is None:
            return
        if kind == "door":
            w, h, sill = H.DOOR_SIZE
        else:
            w, h, sill = H.WINDOW_SIZE
        self.current_room.openings.append(H.Opening(kind, "S", 0.0, w, h,
                                                     sill))
        self._sync_openings_table()
        self._rebuild_canvas()

    def _remove_opening(self):
        if self.current_room is None:
            return
        row = self.openings_table.currentRow()
        if 0 <= row < len(self.current_room.openings):
            del self.current_room.openings[row]
            self._sync_openings_table()
            self._rebuild_canvas()

    def _sync_openings_table(self):
        t = self.openings_table
        t.setRowCount(0)
        room = self.current_room
        if room is None:
            return
        t.setRowCount(len(room.openings))
        for row, op in enumerate(room.openings):
            side = QComboBox()
            side.addItems(list(H.SIDES))
            side.setCurrentText(op.side)
            side.currentTextChanged.connect(
                lambda v, r=row: self._opening_field(r, "side", v))
            t.setCellWidget(row, 0, side)
            kind = QComboBox()
            kind.addItems(["door", "window"])
            kind.setCurrentText(op.kind)
            kind.currentTextChanged.connect(
                lambda v, r=row: self._opening_field(r, "kind", v))
            t.setCellWidget(row, 1, kind)
            for col, key, val in ((2, "offset", op.offset),
                                  (3, "width", op.width),
                                  (4, "height", op.height),
                                  (5, "sill", op.sill)):
                spin = _spin(0.0, 2e4, val)
                spin.valueChanged.connect(
                    lambda v, r=row, k=key: self._opening_field(r, k, v))
                t.setCellWidget(row, col, spin)

    def _opening_field(self, row, key, value):
        if self.current_room is None or row >= len(self.current_room.
                                                     openings):
            return
        setattr(self.current_room.openings[row], key, value)
        self._rebuild_canvas()

    # ------------------------------------------------------ furniture
    def _add_furniture(self):
        if self.current_room is None:
            QMessageBox.information(self, "House Builder",
                                    "Select a room first.")
            return
        part_id = _pick_furniture_part(self)
        if not part_id:
            return
        room = self.current_room
        f = H.Furniture(part_id, room.x + room.w / 2.0,
                        room.y + room.d / 2.0, 0.0)
        room.furniture.append(f)
        self.current_furniture = f
        self._sync_furniture_table()
        self._rebuild_canvas()

    def _remove_furniture(self):
        if self.current_room is None:
            return
        row = self.furniture_table.currentRow()
        if 0 <= row < len(self.current_room.furniture):
            del self.current_room.furniture[row]
            self.current_furniture = None
            self._sync_furniture_table()
            self._rebuild_canvas()

    def _pick_furniture(self, room, item):
        self.current_room = room
        self.current_furniture = item
        self._sync_room_list_selection()
        self._sync_room_fields()
        self._sync_openings_table()
        self._sync_furniture_table()

    def _furniture_edited(self):
        self._sync_furniture_table()

    def _sync_furniture_table(self):
        t = self.furniture_table
        t.setRowCount(0)
        room = self.current_room
        if room is None:
            return
        t.setRowCount(len(room.furniture))
        for row, f in enumerate(room.furniture):
            label = LIBRARY_PARTS.get(f.part_id, {}).get("label",
                                                          f.part_id)
            item = QTableWidgetItem(label)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            t.setItem(row, 0, item)
            for col, key, val, suffix in ((1, "x", f.x, " mm"),
                                          (2, "y", f.y, " mm"),
                                          (3, "rz", f.rz, "°")):
                spin = _spin(-1e5, 1e5, val, suffix=suffix)
                spin.valueChanged.connect(
                    lambda v, r=row, k=key: self._furniture_field(r, k, v))
                t.setCellWidget(row, col, spin)

    def _furniture_field(self, row, key, value):
        if self.current_room is None or row >= len(self.current_room.
                                                     furniture):
            return
        setattr(self.current_room.furniture[row], key, value)
        self._rebuild_canvas()

    # --------------------------------------------------------- garden
    def _garden_field_changed(self, key, value):
        if self._building_ui:
            return
        if self.house.garden is None:
            self.house.garden = H.Garden()
        setattr(self.house.garden, key, value)

    # ---------------------------------------------------------- sync
    def _sync_all(self):
        self._sync_floor_list()
        self._sync_floor_fields()
        self._sync_room_list()
        self._sync_room_fields()
        self._sync_openings_table()
        self._sync_furniture_table()
        self._rebuild_canvas()

    def _sync_floor_list(self):
        self._building_ui = True
        self.floor_list.clear()
        for floor in self.house.floors:
            self.floor_list.addItem(QListWidgetItem(floor.name))
        self.floor_list.setCurrentRow(self.current_floor_index)
        self._building_ui = False

    def _sync_floor_fields(self):
        floor = self.current_floor
        self._building_ui = True
        if floor is not None:
            self.wall_height.setValue(floor.wall_height)
            self.wall_thickness.setValue(floor.wall_thickness)
            self.slab_thickness.setValue(floor.slab_thickness)
        self._building_ui = False

    def _sync_room_list(self):
        self._building_ui = True
        self.room_list.clear()
        floor = self.current_floor
        if floor is not None:
            for room in floor.rooms:
                self.room_list.addItem(QListWidgetItem(room.name))
        self._sync_room_list_selection()
        self._building_ui = False

    def _sync_room_list_selection(self):
        floor = self.current_floor
        if floor is None or self.current_room not in floor.rooms:
            return
        self._building_ui = True
        self.room_list.setCurrentRow(floor.rooms.index(self.current_room))
        self._building_ui = False

    def _sync_room_fields(self):
        self._building_ui = True
        room = self.current_room
        enabled = room is not None
        for w in (self.room_name, self.room_x, self.room_y, self.room_w,
                 self.room_d):
            w.setEnabled(enabled)
        if room is not None:
            self.room_name.setText(room.name)
            self.room_x.setValue(room.x)
            self.room_y.setValue(room.y)
            self.room_w.setValue(room.w)
            self.room_d.setValue(room.d)
        self._building_ui = False

    def _rebuild_canvas(self):
        self.canvas.rebuild(self.current_floor)

    # ---------------------------------------------------------- build
    def _build(self):
        try:
            inserted = H.apply(self.window.model, self.house)
        except H.HouseError as exc:
            QMessageBox.warning(self, "House Builder", str(exc))
            return
        names = ", ".join(c.name for c in inserted)
        self.status.setText(f"Built: {names}")
        self.window.builder.tree.select_nodes(inserted)
        self.window.view3d.fit()


def _pick_furniture_part(parent) -> str:
    """A small modal picker: category -> part. Returns a part id, or
    "" if cancelled."""
    dlg = QDialog(parent)
    dlg.setWindowTitle("Add furniture")
    lay = QVBoxLayout(dlg)
    form = QFormLayout()
    lay.addLayout(form)
    category = QComboBox()
    category.addItems(list(H.FURNITURE_CATALOG))
    part = QComboBox()

    def _fill_parts():
        part.clear()
        for pid in H.FURNITURE_CATALOG[category.currentText()]:
            label = LIBRARY_PARTS.get(pid, {}).get("label", pid)
            part.addItem(label, pid)

    category.currentTextChanged.connect(_fill_parts)
    _fill_parts()
    form.addRow("Room type:", category)
    form.addRow("Furniture:", part)
    row = QHBoxLayout()
    ok = QPushButton("Add")
    ok.clicked.connect(dlg.accept)
    cancel = QPushButton("Cancel")
    cancel.clicked.connect(dlg.reject)
    row.addStretch(1)
    row.addWidget(cancel)
    row.addWidget(ok)
    lay.addLayout(row)
    if dlg.exec_() == QDialog.Accepted and part.currentIndex() >= 0:
        return part.currentData()
    return ""


def open_builder(window):
    panel = getattr(window, "_house_builder", None)
    if panel is None:
        panel = window._house_builder = HouseBuilder(window)
    panel.show()
    panel.raise_()
    panel.activateWindow()
    return panel

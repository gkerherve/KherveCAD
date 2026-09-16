"""AI/Library ▸ House Builder…: a non-modal window with its OWN 2D
floor-plan canvas (separate from the sketch/assembly view) — lay out
rectangular rooms floor by floor, put doors and windows in their
walls, place furniture from the Part Library's room/home catalogue,
size a garden, then Build compiles the design into the document: one
Object per floor (stacked in Z, so it reads as a real house) and one
"Garden" Object beside it — see `house.py` for the geometry and
`house_items.py` for the plan's items.

The window is laid out as the steps you take, top to bottom on the
left: 1 Floor, 2 Rooms (+ the selected room's name and size), 3 what is
in that room (doors, windows, furniture), then an editor for whichever
of those is selected — on the list or on the plan, they follow each
other. The plan above the garden fields draws what Build will make:
walls at their thickness with the openings' gaps, door swings, window
glass, every piece of furniture at its real size seen from above.
Lengths read in metres (stored in mm, like the rest of the house).

One-per-window like `crystal_dialog.py` / `molecule_dialog.py`; Build
replaces the house the last Build made, so editing and building again
updates it.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import json

from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox,
                             QFormLayout, QFrame, QGraphicsScene,
                             QGraphicsView, QGridLayout, QGroupBox,
                             QHBoxLayout, QLabel, QLineEdit, QListWidget,
                             QListWidgetItem, QMenu, QMessageBox,
                             QPushButton,
                             QScrollArea, QSplitter, QStackedWidget,
                             QToolButton, QVBoxLayout, QWidget)

from . import house as H
from . import house_items as HI
from . import icons
from .library import PARTS as LIBRARY_PARTS

MIN_ROOM_M = HI.MIN_ROOM / 1000.0
_floor_default_name = H.floor_default_name

#: the wall combo: side -> how people say it (the plan's top is north)
SIDE_NAMES = (("S", "Bottom wall (south)"), ("N", "Top wall (north)"),
              ("W", "Left wall (west)"), ("E", "Right wall (east)"))
SIDE_SHORT = {"S": "bottom wall", "N": "top wall", "W": "left wall",
              "E": "right wall"}

HINT = ("Drag a room to move it (its furniture comes along) and its blue "
        "squares to resize it · drag a door or window along its wall · "
        "double-click furniture to turn it 90° · Delete removes, R turns "
        "· wheel zooms, drag empty space to pan")


def _label(part_id) -> str:
    return LIBRARY_PARTS.get(part_id, {}).get("label", part_id)


class MetreSpin(QDoubleSpinBox):
    """A length shown in metres — what people measure rooms in — and
    read/written in millimetres, the house's own unit. Reports only
    finished values (no rebuild per keystroke)."""

    def __init__(self, lo_m, hi_m, step=0.05, decimals=2):
        super().__init__()
        self.setRange(lo_m, hi_m)
        self.setSingleStep(step)
        self.setDecimals(decimals)
        self.setSuffix(" m")
        self.setKeyboardTracking(False)

    def mm(self) -> float:
        return round(self.value() * 1000.0, 3)

    def set_mm(self, mm):
        self.setValue(mm / 1000.0)


def _hint(text) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet("color: #6b7280; font-size: 11px;")
    return label


def _step_box(number, title) -> QGroupBox:
    return QGroupBox(f"{number}  ·  {title}")


class FloorCanvas(QGraphicsView):
    """The floor plan's own 2D canvas — Y-up, millimetres, an adaptive
    grid, and the `house_items` items for one floor plus the garden."""

    #: canvas zoom range, px per mm — a 100 m site down to a doorframe
    MIN_ZOOM, MAX_ZOOM = 0.002, 5.0

    def __init__(self, dialog):
        super().__init__(QGraphicsScene())
        self.dialog = dialog
        self.setRenderHints(QPainter.Antialiasing
                            | QPainter.SmoothPixmapTransform)
        self.setBackgroundBrush(QColor("#eef0f3"))
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setFocusPolicy(Qt.StrongFocus)
        self.scale(0.09, -0.09)                # mm -> px, Y-up
        self.items_by_obj = {}                 # id(model obj) -> item
        self.walls = None
        self.garden_item = None
        self._pan = None

    # ----------------------------------------------------------- items
    def rebuild(self, floor, house, selected=None):
        scene = self.scene()
        scene.clear()
        self.items_by_obj = {}
        self.walls = self.garden_item = None
        if floor is None:
            return
        d = self.dialog
        self.walls = HI.WallsItem(floor)
        scene.addItem(self.walls)
        inset = floor.wall_thickness / 2.0
        for room in floor.rooms:
            item = HI.RoomItem(room, on_change=d._room_dragged,
                               on_pick=d._pick_room, inset=inset)
            scene.addItem(item)
            self.items_by_obj[id(room)] = item
            for op in room.openings:
                oi = HI.OpeningItem(room, op, floor,
                                    on_change=d._opening_dragged,
                                    on_pick=d._pick_opening)
                scene.addItem(oi)
                self.items_by_obj[id(op)] = oi
            for f in room.furniture:
                fi = HI.FurnitureItem(f, _label(f.part_id),
                                      on_change=d._furniture_dragged,
                                      on_pick=d._pick_furniture,
                                      on_release=d._furniture_released)
                scene.addItem(fi)
                self.items_by_obj[id(f)] = fi
        self.place_garden(house)
        floors = house.floors if house is not None else []
        roof = (house.roof if house is not None else None) or H.Roof()
        if floors and floor is floors[-1]:     # the roof is the top floor's
            outline = H.roof_outline(roof, floor)
            if outline is not None:
                scene.addItem(HI.RoofItem(outline))
        if floors and floor in floors:         # ...and one over each wing
            style = None if roof.wings == "Same as main" else roof.wings
            for bounds, attach in H.wing_roofs(house, floors.index(floor)):
                outline = H.roof_outline(roof, floor, bounds=bounds,
                                         style=style, attach=attach)
                if outline is not None:
                    scene.addItem(HI.RoofItem(outline))
        item = self.items_by_obj.get(id(selected)) if selected else None
        if item is not None:
            item.setSelected(True)
        rect = self.content_rect(floor)
        pad = max(rect.width(), rect.height(), 20000.0)
        scene.setSceneRect(rect.adjusted(-pad, -pad, pad, pad))
        self.update_labels()

    def place_garden(self, house):
        """(Re)draw the garden where Build puts it: beside the house's
        east side, `gap` away, level with its south wall."""
        if self.garden_item is not None:
            self.scene().removeItem(self.garden_item)
            self.garden_item = None
        g = house.garden if house is not None else None
        bounds = house.bounds() if house is not None else None
        if g is None or not bounds or g.width <= 0 or g.depth <= 0:
            return
        x0, y0, x1, _y1 = bounds
        self.garden_item = HI.GardenItem(
            QRectF(x1 + g.gap, y0, g.width, g.depth))
        self.scene().addItem(self.garden_item)

    def sync_room(self, room):
        """A room moved or resized: its doors, windows and furniture
        follow, the walls are recomputed."""
        for obj in list(room.openings) + list(room.furniture):
            item = self.items_by_obj.get(id(obj))
            if item is not None:
                item.apply()
        if self.walls is not None:
            self.walls.refresh()
        self.place_garden(self.dialog.house)

    def select(self, obj):
        """Select *obj*'s item (a room, opening or furniture) on the
        plan, quietly — the dialog is already showing it."""
        scene = self.scene()
        item = self.items_by_obj.get(id(obj)) if obj is not None else None
        with self.dialog.quiet():
            scene.clearSelection()
            if item is not None:
                item.setSelected(True)
                self.ensureVisible(item.sceneBoundingRect(), 40, 40)
        self.update_labels()

    def content_rect(self, floor=None) -> QRectF:
        floor = floor or self.dialog.current_floor
        b = floor.bounds() if floor is not None else None
        rect = QRectF(b[0], b[1], b[2] - b[0], b[3] - b[1]) if b \
            else QRectF(0.0, 0.0, 4000.0, 4000.0)
        if self.garden_item is not None:
            rect = rect.united(self.garden_item.rect())
        return rect

    # ------------------------------------------------------------ zoom
    def fit(self):
        """Frame the floor and the garden with a metre of margin."""
        rect = self.content_rect()
        self.fitInView(rect.adjusted(-1000.0, -1000.0, 1000.0, 1000.0),
                       Qt.KeepAspectRatio)
        self.update_labels()

    def px_per_mm(self) -> float:
        return abs(self.transform().m11())

    def zoom(self, factor):
        if self.MIN_ZOOM < self.px_per_mm() * factor < self.MAX_ZOOM:
            self.scale(factor, factor)
            self.update_labels()

    def wheelEvent(self, event):
        self.zoom(1.15 if event.angleDelta().y() > 0 else 1 / 1.15)

    def update_labels(self):
        """Name a piece of furniture only when the name fits on it (or
        it is selected) — a plan full of overlapping names read as
        noise; the tooltip always has it."""
        ppm = self.px_per_mm()
        for item in self.items_by_obj.values():
            if isinstance(item, HI.FurnitureItem):
                item.label.setVisible(
                    item.isSelected()
                    or item.screen_width(ppm) >= item.label.width() + 4)

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        ppm = self.px_per_mm()
        step = 1000.0                          # a metre...
        while step * ppm < 12:
            step *= 5.0                        # ...or coarser, never dense
        for major, color in ((False, "#dde1e6"), (True, "#c7ccd3")):
            s = step * 5 if major else step
            pen = QPen(QColor(color), 0)
            pen.setCosmetic(True)
            painter.setPen(pen)
            x = s * int(rect.left() // s)
            while x <= rect.right():
                painter.drawLine(int(x), int(rect.top()), int(x),
                                 int(rect.bottom()))
                x += s
            y = s * int(rect.top() // s)
            while y <= rect.bottom():
                painter.drawLine(int(rect.left()), int(y),
                                 int(rect.right()), int(y))
                y += s

    # ----------------------------------------------------------- input
    def mousePressEvent(self, event):
        empty = self.itemAt(event.pos()) is None
        if event.button() == Qt.MiddleButton or \
                (event.button() == Qt.LeftButton and empty):
            self._pan = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            if empty and event.button() == Qt.LeftButton:
                self.scene().clearSelection()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._pan is not None:
            delta = event.pos() - self._pan
            self._pan = event.pos()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._pan is not None:
            self._pan = None
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key_Delete, Qt.Key_Backspace):
            self.dialog._remove_selected()
        elif key == Qt.Key_R:
            self.dialog._rotate_selected(
                -90.0 if event.modifiers() & Qt.ShiftModifier else 90.0)
        elif key == Qt.Key_Escape:
            self.scene().clearSelection()
        else:
            super().keyPressEvent(event)


class _Quiet:
    """``with dialog.quiet():`` — selection/field changes made by the
    dialog itself don't echo back into it."""

    def __init__(self, dialog):
        self.dialog = dialog

    def __enter__(self):
        self.saved = self.dialog._syncing
        self.dialog._syncing = True

    def __exit__(self, *exc):
        self.dialog._syncing = self.saved


class HouseBuilder(QDialog):
    """The House Builder window: the numbered steps on the left, the
    floor plan (with its toolbar and hint line) on the right, the garden
    under it and Build at the bottom."""

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle("House Builder")
        self.setModal(False)
        self.resize(1280, 820)
        self.house = H.House(
            floors=[H.Floor(_floor_default_name(0), rooms=[
                H.Room("Living room", 0.0, 0.0, 5000.0, 4000.0)])],
            garden=H.Garden(),
            roof=H.Roof("Gable", pitch=H.ROOF_PITCH["Gable"]))
        self.current_floor_index = 0
        self.current_room = self.house.floors[0].rooms[0]
        self.current_item = None           # an Opening or a Furniture
        self._syncing = True
        self._fitted = False
        self._build_ui()
        self._syncing = False
        self._loaded = None               # the design last loaded / built
        self._sync_all()
        self.load_from_document()

    def quiet(self):
        return _Quiet(self)

    @property
    def current_furniture(self):
        return self.current_item if isinstance(self.current_item,
                                               H.Furniture) else None

    def load_from_document(self, force=False) -> bool:
        """Fill the builder with the house the document holds
        (``model.house``: built here, by build_house, or saved in the
        .kcad) so its rooms, openings and furniture can be edited and
        built again. Skipped when that design is already the one shown,
        so reopening the window keeps edits not yet built — unless
        *force*. Returns whether it loaded."""
        spec = self.window.model.house
        key = json.dumps(spec, sort_keys=True) if spec else None
        if not spec or (key == self._loaded and not force):
            return False
        try:
            house = H.house_from_spec(spec)
        except H.HouseError:
            return False
        self._loaded = key
        self.house = house
        self.current_floor_index = 0
        floor = house.floors[0]
        self.current_room = floor.rooms[0] if floor.rooms else None
        self.current_item = None
        self._sync_garden_fields()
        self._sync_roof_fields()
        self._sync_wall_fields()
        self._sync_all()
        self.canvas.fit()
        self.status.setText("Editing the document's house — Build "
                            "updates it.")
        return True

    def load_template(self, name, ask=True) -> bool:
        """Replace the design on the plan with the building template
        *name* (house_templates); Build then puts it in the document."""
        from . import house_templates
        has_rooms = any(f.rooms for f in self.house.floors)
        if ask and has_rooms and QMessageBox.question(
                self, "House Builder",
                f"Replace the design on the plan with the {name} "
                "template?") != QMessageBox.Yes:
            return False
        try:
            house = H.house_from_spec(house_templates.spec(name))
        except (KeyError, H.HouseError) as exc:
            self.status.setText(str(exc))
            return False
        self.house = house
        self.current_floor_index = 0
        floor = house.floors[0]
        self.current_room = floor.rooms[0] if floor.rooms else None
        self.current_item = None
        self._sync_garden_fields()
        self._sync_roof_fields()
        self._sync_wall_fields()
        self._sync_all()
        self.canvas.fit()
        self.status.setText(f"{name} template loaded — edit it, then "
                            "Build.")
        return True

    def showEvent(self, event):
        super().showEvent(event)
        if not self._fitted:              # the view has its size now
            self._fitted = True
            self.canvas.fit()

    # ------------------------------------------------------------ ui
    def _build_ui(self):
        root = QVBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

        left = QWidget()
        left_l = QVBoxLayout(left)
        left_l.setContentsMargins(4, 4, 8, 4)
        left_l.addWidget(self._floor_group())
        left_l.addWidget(self._rooms_group())
        left_l.addWidget(self._contents_group())
        left_l.addWidget(self._editor_group())
        left_l.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidget(left)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(470)       # every row fits, none clipped
        scroll.setMaximumWidth(520)
        splitter.addWidget(scroll)

        right = QWidget()
        right_l = QVBoxLayout(right)
        right_l.setContentsMargins(4, 4, 4, 4)
        self.canvas = FloorCanvas(self)
        right_l.addLayout(self._toolbar())
        right_l.addWidget(_hint(HINT))
        right_l.addWidget(self.canvas, 1)
        right_l.addWidget(self._roof_group())
        right_l.addWidget(self._garden_group())
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([420, 860])

        bottom = QHBoxLayout()
        self.status = QLabel("")
        bottom.addWidget(self.status, 1)
        build_btn = QPushButton(icons.icon("mdi.home-city-outline"),
                                "Build house")
        build_btn.setDefault(True)
        build_btn.setToolTip(
            "Build the design into the document: one Object per floor, "
            "stacked, each piece of furniture an Object inside it, plus "
            "a Garden Object. Building again replaces the house built "
            "last time; the design is saved with the document.")
        build_btn.clicked.connect(self._build)
        bottom.addWidget(build_btn)
        root.addLayout(bottom)

    def _tool(self, icon, text, tip, slot):
        b = QToolButton()
        b.setIcon(icons.icon(icon))
        b.setText(text)
        b.setToolTip(tip)
        b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        b.setAutoRaise(True)
        b.clicked.connect(slot)
        return b

    def _toolbar(self):
        row = QHBoxLayout()
        room_btn = self._tool("mdi.floor-plan", "Room",
                              "Add a room — pick its kind: bedroom, garage, "
                              "corridor, reception, porch, garden…",
                              lambda: None)
        room_btn.setMenu(self._room_menu())
        room_btn.setPopupMode(QToolButton.InstantPopup)
        row.addWidget(room_btn)
        tmpl_btn = self._tool("mdi.office-building-outline", "Template",
                              "Start from a whole furnished building: a "
                              "chemistry lab, a physics lab or a company "
                              "office", lambda: None)
        tmpl_menu = QMenu(self)
        from . import house_templates
        for name in house_templates.names():
            tmpl_menu.addAction(icons.icon("mdi.office-building-outline"),
                                name, lambda n=name: self.load_template(n))
        tmpl_btn.setMenu(tmpl_menu)
        tmpl_btn.setPopupMode(QToolButton.InstantPopup)
        row.addWidget(tmpl_btn)
        for icon, text, tip, slot in (
                ("mdi.door", "Door", "Add a door to the selected room",
                 lambda: self._add_opening("door")),
                ("mdi.window-closed-variant", "Window",
                 "Add a window to the selected room",
                 lambda: self._add_opening("window")),
                ("mdi.sofa-outline", "Furniture…",
                 "Add a piece of furniture to the selected room",
                 self._add_furniture)):
            row.addWidget(self._tool(icon, text, tip, slot))
        row.addSpacing(12)
        row.addWidget(self._tool("mdi.rotate-left", "Turn 90°",
                                 "Turn the selected furniture 90° (R)",
                                 lambda: self._rotate_selected(90.0)))
        row.addWidget(self._tool("mdi.delete-outline", "Delete",
                                 "Remove the selected door, window, "
                                 "furniture or room (Delete)",
                                 self._remove_selected))
        row.addStretch(1)
        for icon, tip, slot in (
                ("mdi.magnify-minus-outline", "Zoom out",
                 lambda: self.canvas.zoom(1 / 1.25)),
                ("mdi.magnify-plus-outline", "Zoom in",
                 lambda: self.canvas.zoom(1.25)),
                ("mdi.fit-to-page-outline", "Show the whole floor",
                 lambda: self.canvas.fit())):
            b = self._tool(icon, "", tip, slot)
            b.setToolButtonStyle(Qt.ToolButtonIconOnly)
            row.addWidget(b)
        return row

    def _floor_group(self):
        box = _step_box(1, "Floor")
        lay = QVBoxLayout(box)
        row = QHBoxLayout()
        self.floor_combo = QComboBox()
        self.floor_combo.setToolTip("The storey shown on the plan")
        self.floor_combo.currentIndexChanged.connect(self._floor_changed)
        row.addWidget(self.floor_combo, 1)
        add = QPushButton("+ Add floor")
        add.setToolTip("Add a storey on top, starting with one room")
        add.clicked.connect(self._add_floor)
        rm = QPushButton("Remove")
        rm.setToolTip("Remove this floor")
        rm.clicked.connect(self._remove_floor)
        row.addWidget(add)
        row.addWidget(rm)
        lay.addLayout(row)
        form = QFormLayout()
        self.wall_height = MetreSpin(1.5, 6.0, 0.05)
        self.wall_thickness = MetreSpin(0.05, 0.5, 0.01)
        self.slab_thickness = MetreSpin(0.05, 0.5, 0.01)
        for w, key, tip in (
                (self.wall_height, "wall_height",
                 "Floor-to-ceiling height of this storey"),
                (self.wall_thickness, "wall_thickness",
                 "Thickness of every wall on this floor"),
                (self.slab_thickness, "slab_thickness",
                 "Thickness of the floor slab under the rooms")):
            w.setToolTip(tip)
            w.valueChanged.connect(
                lambda _v, k=key, s=w: self._floor_field_changed(k, s.mm()))
        form.addRow("Ceiling height:", self.wall_height)
        form.addRow("Wall thickness:", self.wall_thickness)
        form.addRow("Floor slab:", self.slab_thickness)
        self.outer_wall = QComboBox()
        for name, (hexcol, _mat) in H.WALL_STYLES.items():
            self.outer_wall.addItem(_swatch(hexcol), name, name)
        self.outer_wall.setToolTip("How the outside of the house is "
                                   "finished")
        self.inner_wall = QComboBox()
        for name, (hexcol, _mat) in H.INNER_WALL_STYLES.items():
            self.inner_wall.addItem(_swatch(hexcol), name, name)
        self.inner_wall.setToolTip("How the walls between rooms are "
                                   "finished (a room can have its own "
                                   "finish too)")
        for combo, key in ((self.outer_wall, "outer_wall"),
                           (self.inner_wall, "inner_wall")):
            combo.currentIndexChanged.connect(
                lambda _i, k=key, c=combo: self._wall_style_changed(
                    k, c.currentData()))
        form.addRow("Outside walls:", self.outer_wall)
        form.addRow("Walls between rooms:", self.inner_wall)
        lay.addLayout(form)
        return box

    def _wall_style_changed(self, key, value):
        if self._syncing:
            return
        setattr(self.house, key, value)
        self._rebuild_canvas()
        self.status.setText(f"{value} — Build to see it in 3D.")

    def _sync_wall_fields(self):
        with self.quiet():
            self.outer_wall.setCurrentIndex(
                max(0, self.outer_wall.findData(self.house.outer_wall)))
            self.inner_wall.setCurrentIndex(
                max(0, self.inner_wall.findData(self.house.inner_wall)))

    def _rooms_group(self):
        box = _step_box(2, "Rooms")
        lay = QVBoxLayout(box)
        self.room_list = QListWidget()
        self.room_list.setMaximumHeight(110)
        self.room_list.currentRowChanged.connect(self._room_row_changed)
        lay.addWidget(self.room_list)
        row = QHBoxLayout()
        add = QPushButton("+ Add room")
        add.setToolTip("Add a room to the right of the others — pick its "
                       "kind")
        add.setMenu(self._room_menu())
        rm = QPushButton("Remove room")
        rm.clicked.connect(self._remove_room)
        row.addWidget(add)
        row.addWidget(rm)
        lay.addLayout(row)
        form = QFormLayout()
        self.room_name = QLineEdit()
        self.room_name.setPlaceholderText("e.g. Kitchen")
        self.room_name.editingFinished.connect(self._room_name_changed)
        self.room_w = MetreSpin(MIN_ROOM_M, 100.0)
        self.room_d = MetreSpin(MIN_ROOM_M, 100.0)
        self.room_x = MetreSpin(-100.0, 100.0)
        self.room_y = MetreSpin(-100.0, 100.0)
        self.room_x.setToolTip("Where its left wall is, from the origin")
        self.room_y.setToolTip("Where its bottom wall is, from the origin")
        for w, key in ((self.room_x, "x"), (self.room_y, "y"),
                      (self.room_w, "w"), (self.room_d, "d")):
            w.valueChanged.connect(
                lambda _v, k=key, s=w: self._room_field_changed(k, s.mm()))
        size = QHBoxLayout()
        size.addWidget(self.room_w)
        size.addWidget(QLabel("×"))
        size.addWidget(self.room_d)
        pos = QHBoxLayout()
        pos.addWidget(self.room_x)
        pos.addWidget(QLabel(","))
        pos.addWidget(self.room_y)
        form.addRow("Name:", self.room_name)
        self.room_kind = QComboBox()
        for label, surface in (("Indoor room (walls)", "indoor"),
                               ("Garden (lawn, no walls)", "garden"),
                               ("Paving (porch, patio, drive)", "paving")):
            self.room_kind.addItem(label, surface)
        self.room_kind.setToolTip("An indoor room gets walls and sits under "
                                  "the roof; a garden or paved area is "
                                  "outdoors, ground only")
        self.room_kind.currentIndexChanged.connect(
            lambda _i: self._room_field_changed(
                "surface", self.room_kind.currentData()))
        form.addRow("Kind:", self.room_kind)
        self.room_finish = QComboBox()
        self.room_finish.addItem("Same as the house", "")
        for name, ((hexcol, _m), _floor) in H.ROOM_FINISHES.items():
            self.room_finish.addItem(_swatch(hexcol), name, name)
        self.room_finish.setToolTip("This room's own finish: tiles or "
                                    "panelling lining its walls and floor "
                                    "— a bathroom, a kitchen")
        self.room_finish.currentIndexChanged.connect(
            lambda _i: self._room_field_changed(
                "finish", self.room_finish.currentData()))
        form.addRow("Finish:", self.room_finish)
        form.addRow("Size (w × d):", size)
        form.addRow("Position (x, y):", pos)
        lay.addLayout(form)
        return box

    def _contents_group(self):
        self.contents_box = _step_box(3, "In this room")
        lay = QVBoxLayout(self.contents_box)
        self.items_list = QListWidget()
        self.items_list.setMaximumHeight(150)
        self.items_list.currentRowChanged.connect(self._item_row_changed)
        lay.addWidget(self.items_list)
        grid = QGridLayout()
        for i, (text, icon, slot) in enumerate((
                ("+ Door", "mdi.door", lambda: self._add_opening("door")),
                ("+ Window", "mdi.window-closed-variant",
                 lambda: self._add_opening("window")),
                ("+ Furniture…", "mdi.sofa-outline", self._add_furniture),
                ("Remove", "mdi.delete-outline", self._remove_item))):
            b = QPushButton(icons.icon(icon), text)
            b.clicked.connect(slot)
            grid.addWidget(b, i // 2, i % 2)
        lay.addLayout(grid)
        return self.contents_box

    def _editor_group(self):
        self.editor_box = _step_box(4, "Selected item")
        lay = QVBoxLayout(self.editor_box)
        self.editor = QStackedWidget()
        lay.addWidget(self.editor)
        self.editor.addWidget(_hint(
            "Click a door, window or piece of furniture — in the list "
            "above or on the plan — to change it here."))
        self.editor.addWidget(self._opening_editor())
        self.editor.addWidget(self._furniture_editor())
        return self.editor_box

    def _opening_editor(self):
        page = QWidget()
        form = QFormLayout(page)
        form.setContentsMargins(0, 0, 0, 0)
        self.op_kind = QComboBox()
        self.op_kind.addItem(icons.icon("mdi.door"), "Door", "door")
        self.op_kind.addItem(icons.icon("mdi.window-closed-variant"),
                             "Window", "window")
        self.op_kind.addItem(icons.icon("mdi.garage"), "Garage door",
                             "garage door")
        self.op_kind.currentIndexChanged.connect(
            lambda _i: self._opening_field("kind",
                                           self.op_kind.currentData()))
        self.op_side = QComboBox()
        for side, name in SIDE_NAMES:
            self.op_side.addItem(name, side)
        self.op_side.currentIndexChanged.connect(
            lambda _i: self._opening_field("side",
                                           self.op_side.currentData()))
        self.op_offset = MetreSpin(0.0, 100.0)
        self.op_offset.setToolTip(
            "From the wall's left end (top and bottom walls) or its "
            "bottom end (left and right walls)")
        self.op_width = MetreSpin(0.3, 20.0)
        self.op_height = MetreSpin(0.3, 6.0)
        self.op_sill = MetreSpin(0.0, 3.0)
        self.op_sill.setToolTip("Height of the window's bottom edge above "
                                "the floor")
        for w, key in ((self.op_offset, "offset"), (self.op_width, "width"),
                      (self.op_height, "height"), (self.op_sill, "sill")):
            w.valueChanged.connect(
                lambda _v, k=key, s=w: self._opening_field(k, s.mm()))
        form.addRow("Type:", self.op_kind)
        form.addRow("In the:", self.op_side)
        form.addRow("From the corner:", self.op_offset)
        form.addRow("Width:", self.op_width)
        form.addRow("Height:", self.op_height)
        form.addRow("Sill height:", self.op_sill)
        form.addRow(_hint("Tip: drag it on the plan — along its wall, or "
                          "onto another wall of the room."))
        return page

    def _furniture_editor(self):
        page = QWidget()
        form = QFormLayout(page)
        form.setContentsMargins(0, 0, 0, 0)
        self.fu_title = QLabel()
        font = QFont(self.fu_title.font())
        font.setBold(True)
        self.fu_title.setFont(font)
        form.addRow(self.fu_title)
        self.fu_size = QComboBox()
        self.fu_size.currentIndexChanged.connect(self._furniture_look)
        self.fu_color = QComboBox()
        self.fu_color.currentIndexChanged.connect(self._furniture_look)
        form.addRow("Size:", self.fu_size)
        form.addRow("Colour:", self.fu_color)
        self.fu_x = MetreSpin(-100.0, 100.0, 0.05)
        self.fu_y = MetreSpin(-100.0, 100.0, 0.05)
        self.fu_x.setToolTip("Its centre, from the room's left wall")
        self.fu_y.setToolTip("Its centre, from the room's bottom wall")
        self.fu_x.valueChanged.connect(
            lambda _v: self._furniture_field("x", self.fu_x.mm()))
        self.fu_y.valueChanged.connect(
            lambda _v: self._furniture_field("y", self.fu_y.mm()))
        pos = QHBoxLayout()
        pos.addWidget(self.fu_x)
        pos.addWidget(QLabel(","))
        pos.addWidget(self.fu_y)
        form.addRow("In the room (x, y):", pos)
        self.fu_z = MetreSpin(0.0, 5.0, 0.05)
        self.fu_z.setToolTip("How high its base sits above the floor — a TV "
                             "on its stand, a shelf or a mirror on the wall")
        self.fu_z.valueChanged.connect(
            lambda _v: self._furniture_field("z", self.fu_z.mm()))
        sit = QToolButton()
        sit.setIcon(icons.icon("mdi.arrow-collapse-down"))
        sit.setText("Sit on what's below")
        sit.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        sit.setToolTip("Set it down on top of the furniture under it — a TV "
                       "on its unit, a lamp on a table — or on the floor")
        sit.clicked.connect(self._sit_selected)
        height = QHBoxLayout()
        height.addWidget(self.fu_z, 1)
        height.addWidget(sit)
        form.addRow("Height above floor:", height)
        self.fu_rz = QDoubleSpinBox()
        self.fu_rz.setRange(-180.0, 180.0)
        self.fu_rz.setWrapping(True)
        self.fu_rz.setSingleStep(15.0)
        self.fu_rz.setDecimals(0)
        self.fu_rz.setSuffix("°")
        self.fu_rz.setKeyboardTracking(False)
        self.fu_rz.valueChanged.connect(
            lambda v: self._furniture_field("rz", v))
        turn = QHBoxLayout()
        turn.addWidget(self.fu_rz, 1)
        for icon, step, tip in (("mdi.rotate-left", 90.0,
                                 "Turn 90° anticlockwise"),
                                ("mdi.rotate-right", -90.0,
                                 "Turn 90° clockwise")):
            b = QToolButton()
            b.setIcon(icons.icon(icon))
            b.setToolTip(tip)
            b.clicked.connect(lambda _c=False, s=step:
                              self._rotate_selected(s))
            turn.addWidget(b)
        form.addRow("Rotation:", turn)
        form.addRow(_hint("Tip: on the plan, drag it to move it and "
                          "double-click it to turn it 90°."))
        return page

    def _garden_group(self):
        box = QGroupBox("Garden")
        row = QHBoxLayout(box)
        self.garden_on = QCheckBox("Add a garden beside the house")
        self.garden_on.toggled.connect(self._garden_toggled)
        row.addWidget(self.garden_on)
        self.garden_w = MetreSpin(0.5, 200.0, 0.5)
        self.garden_d = MetreSpin(0.5, 200.0, 0.5)
        self.garden_gap = MetreSpin(0.0, 50.0, 0.5)
        for w, key in ((self.garden_w, "width"), (self.garden_d, "depth"),
                      (self.garden_gap, "gap")):
            w.valueChanged.connect(
                lambda _v, k=key, s=w: self._garden_field_changed(k,
                                                                  s.mm()))
        for text, w in (("Width:", self.garden_w), ("Depth:", self.garden_d),
                        ("Gap from the house:", self.garden_gap)):
            row.addWidget(QLabel(text))
            row.addWidget(w)
        row.addStretch(1)
        self._sync_garden_fields()
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
        if prev is not None:
            floor.wall_height = prev.wall_height
            floor.wall_thickness = prev.wall_thickness
            floor.slab_thickness = prev.slab_thickness
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
        self.current_item = None
        self._sync_all()
        self.status.setText(f"Added the {floor.name.lower()} — draw its "
                            "rooms on the plan.")

    def _remove_floor(self):
        if len(self.house.floors) <= 1:
            QMessageBox.information(self, "House Builder",
                                    "A house needs at least one floor.")
            return
        del self.house.floors[self.current_floor_index]
        self.current_floor_index = max(0, self.current_floor_index - 1)
        floor = self.current_floor
        self.current_room = floor.rooms[0] if floor.rooms else None
        self.current_item = None
        self._sync_all()

    def _floor_changed(self, index):
        if self._syncing or index < 0:
            return
        self.current_floor_index = index
        floor = self.current_floor
        self.current_room = floor.rooms[0] if floor and floor.rooms \
            else None
        self.current_item = None
        self._sync_all()
        self.canvas.fit()

    def _floor_field_changed(self, key, value):
        if self._syncing or self.current_floor is None:
            return
        setattr(self.current_floor, key, value)
        self._rebuild_canvas()

    # ---------------------------------------------------------- rooms
    def _room_menu(self):
        """The kinds of room "+ Room" offers, each with its usual size."""
        menu = QMenu(self)
        menu.addAction(icons.icon("mdi.floor-plan"), "Plain room (4 × 3 m)",
                       lambda: self._add_room())
        menu.addSeparator()
        for name, (w, d, surface) in H.ROOM_TYPES.items():
            outdoor = surface != "indoor"
            menu.addAction(
                icons.icon("mdi.tree-outline" if outdoor
                           else "mdi.floor-plan"),
                f"{name}    {w / 1000:g} × {d / 1000:g} m"
                + ("  (outdoor)" if outdoor else ""),
                lambda n=name: self._add_room(n))
        return menu

    def _add_room(self, kind=None):
        floor = self.current_floor
        if floor is None:
            return
        x, y = 0.0, 0.0
        if floor.rooms:
            x0, y0, x1, y1 = floor.bounds()
            x, y = x1, y0
        if kind in H.ROOM_TYPES:
            w, d, surface = H.ROOM_TYPES[kind]
            names = {r.name for r in floor.rooms}
            name, i = kind, 2
            while name in names:
                name, i = f"{kind} {i}", i + 1
        else:
            w, d, surface = 4000.0, 3000.0, "indoor"
            name = f"Room {len(floor.rooms) + 1}"
        room = H.Room(name, x, y, w, d, surface=surface)
        floor.rooms.append(room)
        self.current_room = room
        self.current_item = None
        self._sync_all()
        self.room_name.setFocus()
        self.room_name.selectAll()
        self.status.setText("Added a room — name it, then drag it into "
                            "place or type its size.")

    def _remove_room(self):
        floor = self.current_floor
        room = self.current_room
        if floor is None or room is None:
            return
        if room.openings or room.furniture:
            answer = QMessageBox.question(
                self, "House Builder",
                f'Remove "{room.name}" with its {len(room.openings)} '
                f"door(s)/window(s) and {len(room.furniture)} piece(s) of "
                "furniture?")
            if answer != QMessageBox.Yes:
                return
        floor.rooms.remove(room)
        self.current_room = floor.rooms[0] if floor.rooms else None
        self.current_item = None
        self._sync_all()

    def _room_row_changed(self, row):
        if self._syncing or row < 0 or self.current_floor is None:
            return
        rooms = self.current_floor.rooms
        self.current_room = rooms[row] if row < len(rooms) else None
        self.current_item = None
        self._sync_room_fields()
        self._sync_items()
        self.canvas.select(self.current_room)

    def _pick_room(self, room):
        """A room was clicked on the plan."""
        if self._syncing:
            return
        self.current_room = room
        self.current_item = None
        self._sync_room_list_selection()
        self._sync_room_fields()
        self._sync_items()

    def _room_dragged(self, room):
        """A drag/resize on the plan changed *room*."""
        self.canvas.sync_room(room)
        if room is self.current_room:
            self._sync_room_fields()
        self._sync_room_captions()

    def _room_name_changed(self):
        if self._syncing or self.current_room is None:
            return
        name = self.room_name.text().strip()
        if not name or name == self.current_room.name:
            return
        self.current_room.name = name
        self._sync_room_captions()
        self._sync_items()
        self._rebuild_canvas()

    def _room_field_changed(self, key, value):
        room = self.current_room
        if self._syncing or room is None:
            return
        if key in ("x", "y"):                 # its contents come along
            delta = value - getattr(room, key)
            for f in room.furniture:
                setattr(f, key, getattr(f, key) + delta)
        setattr(room, key, value)
        self._sync_room_captions()
        self._rebuild_canvas()

    # ----------------------------------------------- openings/furniture
    def _room_of(self, obj):
        floor = self.current_floor
        for room in floor.rooms if floor else []:
            if obj in room.openings or obj in room.furniture:
                return room
        return None

    def _add_opening(self, kind):
        room = self.current_room
        if room is None:
            self.status.setText("Select a room first.")
            return
        if not room.indoor:
            self.status.setText(f"{room.name} is outdoors and has no walls "
                                "— put the door or window on the room "
                                "next to it.")
            return
        w, h, sill = H.opening_size(kind)
        # doors in the bottom wall, a window in the top one, centred
        side = "N" if kind == "window" else "S"
        length = room.w
        op = H.Opening(kind, side, max(0.0, (length - w) / 2.0), w, h, sill)
        room.openings.append(op)
        self.current_item = op
        self._sync_items()
        self._rebuild_canvas()
        self.status.setText(f"Added a {kind} in the {SIDE_SHORT[side]} of "
                            f"{room.name} — drag it where you want it.")

    def _add_furniture(self):
        room = self.current_room
        if room is None:
            self.status.setText("Select a room first.")
            return
        part_id = _pick_furniture_part(self, room.name)
        if not part_id:
            return
        f = H.Furniture(part_id, room.x + room.w / 2.0,
                        room.y + room.d / 2.0, 0.0,
                        dims=H.part_dims(part_id),
                        z=H.part_rest_z(part_id))    # a shelf on the wall
        room.furniture.append(f)
        if H.sits_on_top(part_id):                   # a lamp on the table
            f.z = H.surface_below(self.current_floor, f)
        self.current_item = f
        self._sync_items()
        self._rebuild_canvas()
        self.status.setText(f"Added {_label(part_id).lower()} to "
                            f"{room.name} — drag it into place, "
                            "double-click to turn it.")

    def _remove_item(self):
        room, obj = self.current_room, self.current_item
        if room is None or obj is None:
            self.status.setText("Select a door, window or piece of "
                                "furniture to remove.")
            return
        owner = self._room_of(obj) or room
        if obj in owner.openings:
            owner.openings.remove(obj)
        elif obj in owner.furniture:
            owner.furniture.remove(obj)
        self.current_item = None
        self._sync_items()
        self._rebuild_canvas()

    def _remove_selected(self):
        """Delete key / toolbar: the selected item, else the room."""
        if self.current_item is not None:
            self._remove_item()
        elif self.current_room is not None:
            self._remove_room()

    def _rotate_selected(self, step):
        f = self.current_furniture
        item = self.canvas.items_by_obj.get(id(f)) if f else None
        if item is None:
            self.status.setText("Select a piece of furniture to turn it.")
            return
        item.rotate_by(step)

    def _item_row_changed(self, row):
        if self._syncing or self.current_room is None or row < 0:
            return
        objs = self._room_items(self.current_room)
        self.current_item = objs[row] if row < len(objs) else None
        self._sync_editor()
        self.canvas.select(self.current_item or self.current_room)

    def _pick_opening(self, room, op):
        if self._syncing:
            return
        self.current_room = room
        self.current_item = op
        self._sync_after_pick()

    def _pick_furniture(self, f):
        if self._syncing:
            return
        self.current_room = self._room_of(f) or self.current_room
        self.current_item = f
        self._sync_after_pick()

    def _sync_after_pick(self):
        self._sync_room_list_selection()
        self._sync_room_fields()
        self._sync_items()
        self.canvas.update_labels()

    def _opening_dragged(self, item):
        if self.canvas.walls is not None:
            self.canvas.walls.update()
        if item.opening is self.current_item:
            self._sync_editor()
            self._sync_item_captions()

    def _furniture_dragged(self, item):
        if item.item is self.current_item:
            self._sync_editor()

    def _furniture_released(self, item):
        """A drag ended. A piece dropped in another room now belongs to
        that room; a lamp, TV, microwave... is set down on whatever it
        was dropped on (`house.surface_below`)."""
        f = item.item
        floor = self.current_floor
        if floor is None:
            return
        if H.sits_on_top(f.part_id):
            z = H.surface_below(floor, f)
            if abs(z - f.z) > 0.5:
                f.z = z
                item.apply()
                if f is self.current_item:
                    self._sync_editor()
                    self._sync_item_captions()
        owner = self._room_of(f)
        target = next((r for r in floor.rooms
                       if r.x <= f.x <= r.x + r.w
                       and r.y <= f.y <= r.y + r.d), None)
        if owner is None or target is None or target is owner:
            return
        owner.furniture.remove(f)
        target.furniture.append(f)
        self.current_room = target
        self._sync_after_pick()
        self.status.setText(f"{_label(f.part_id)} moved into "
                            f"{target.name}.")

    def _opening_field(self, key, value):
        op = self.current_item
        if self._syncing or not isinstance(op, H.Opening):
            return
        setattr(op, key, value)
        if key == "kind":                    # its usual size and sill
            op.width, op.height, op.sill = H.opening_size(value)
            self._sync_editor()
        if op.kind != "window":
            op.sill = 0.0
        self._sync_item_captions()
        self._rebuild_canvas()

    def _furniture_field(self, key, value):
        f = self.current_furniture
        room = self._room_of(f) if f is not None else None
        if self._syncing or f is None or room is None:
            return
        if key == "x":
            f.x = room.x + value
        elif key == "y":
            f.y = room.y + value
        elif key == "z":
            f.z = value
        else:
            f.rz = value
        item = self.canvas.items_by_obj.get(id(f))
        if item is not None:
            item.apply()
            self.canvas.update_labels()
        if key == "z":
            self._sync_item_captions()

    def _furniture_look(self, _index=None):
        """The size or colour combo changed: rebuild the part's dims."""
        f = self.current_furniture
        if self._syncing or f is None:
            return
        size = self.fu_size.currentData()
        color = self.fu_color.currentData()
        try:
            f.dims = H.part_dims(f.part_id, size, color)
        except H.HouseError as exc:
            self.status.setText(str(exc))
            return
        self._sync_item_captions()
        self._rebuild_canvas()

    def _room_items(self, room):
        return list(room.openings) + list(room.furniture)

    def _sit_selected(self):
        """Set the selected piece down on the furniture under it (or on
        the floor when there is none)."""
        f = self.current_furniture
        if f is None or self.current_floor is None:
            self.status.setText("Select a piece of furniture first.")
            return
        f.z = H.surface_below(self.current_floor, f)
        item = self.canvas.items_by_obj.get(id(f))
        if item is not None:
            item.apply()
        self._sync_editor()
        self._sync_item_captions()
        name = _label(f.part_id)
        self.status.setText(
            f"{name} sits {f.z / 1000:.2f} m up, on what is under it."
            if f.z > 0 else
            f"Nothing under {name.lower()} to stand on — it is on the "
            "floor.")

    # ----------------------------------------------------------- roof
    def _roof_group(self):
        box = QGroupBox("Roof (on the top floor)")
        row = QHBoxLayout(box)
        self.roof_style = QComboBox()
        self.roof_style.addItems(list(H.ROOF_STYLES))
        self.roof_style.setToolTip("The roof's shape. The plan shows its "
                                   "eaves and ridge dashed; Build makes it "
                                   "in 3D.")
        self.roof_pitch = QDoubleSpinBox()
        self.roof_pitch.setRange(*H.ROOF_PITCH_RANGE)
        self.roof_pitch.setDecimals(0)
        self.roof_pitch.setSingleStep(5.0)
        self.roof_pitch.setSuffix("°")
        self.roof_pitch.setKeyboardTracking(False)
        self.roof_pitch.setToolTip("How steep the roof is")
        self.roof_overhang = MetreSpin(0.0, 2.0, 0.05)
        self.roof_overhang.setToolTip("How far the roof reaches past the "
                                      "walls")
        self.roof_ridge = QComboBox()
        for label, key in (("Along the long side", "auto"),
                           ("Left–right (X)", "x"),
                           ("Bottom–top (Y)", "y")):
            self.roof_ridge.addItem(label, key)
        self.roof_ridge.setToolTip("Which way the ridge runs (a lean-to "
                                   "rises across it)")
        self.roof_color = QComboBox()
        for name, (hexcol, _mat) in H.ROOF_COLORS.items():
            self.roof_color.addItem(_swatch(hexcol), name, name)
        self.roof_wings = QComboBox()
        for name in H.WING_STYLES:
            self.roof_wings.addItem(name, name)
        self.roof_wings.setToolTip(
            "The roof over a side wing — a part of a floor with nothing "
            "above it, like a garage. A lean-to leans on the taller part.")
        self.roof_wings.currentIndexChanged.connect(
            lambda _i: self._roof_changed())
        self.roof_style.currentIndexChanged.connect(
            lambda _i: self._roof_changed(style_changed=True))
        self.roof_pitch.valueChanged.connect(lambda _v: self._roof_changed())
        self.roof_overhang.valueChanged.connect(
            lambda _v: self._roof_changed())
        for combo in (self.roof_ridge, self.roof_color):
            combo.currentIndexChanged.connect(lambda _i: self._roof_changed())
        for text, w in (("Style:", self.roof_style),
                        ("Pitch:", self.roof_pitch),
                        ("Overhang:", self.roof_overhang),
                        ("Ridge:", self.roof_ridge),
                        ("Covering:", self.roof_color),
                        ("Side wings:", self.roof_wings)):
            row.addWidget(QLabel(text))
            row.addWidget(w)
        row.addStretch(1)
        self._sync_roof_fields()
        return box

    def _roof_changed(self, style_changed=False):
        if self._syncing:
            return
        style = self.roof_style.currentText()
        if style_changed and style != "Flat":
            with self.quiet():                # its usual pitch
                self.roof_pitch.setValue(H.ROOF_PITCH[style])
        self.house.roof = H.Roof(style, self.roof_pitch.value(),
                                 self.roof_overhang.mm(),
                                 self.roof_ridge.currentData(),
                                 self.roof_color.currentData(),
                                 self.roof_wings.currentData())
        self._enable_roof_fields()
        self._rebuild_canvas()
        pitch = "" if style == "Flat" else f", {self.roof_pitch.value():.0f}°"
        self.status.setText(f"Roof: {style.lower()}{pitch} — Build to see "
                            "it in 3D.")

    def _enable_roof_fields(self):
        sloped = (self.house.roof or H.Roof()).style != "Flat"
        self.roof_pitch.setEnabled(sloped)
        self.roof_ridge.setEnabled(sloped)

    def _sync_roof_fields(self):
        r = self.house.roof or H.Roof()
        with self.quiet():
            self.roof_style.setCurrentText(r.style)
            self.roof_pitch.setValue(r.pitch)
            self.roof_overhang.set_mm(r.overhang)
            self.roof_ridge.setCurrentIndex(
                max(0, self.roof_ridge.findData(r.ridge)))
            self.roof_color.setCurrentIndex(
                max(0, self.roof_color.findData(r.color)))
            self.roof_wings.setCurrentIndex(
                max(0, self.roof_wings.findData(r.wings)))
        self._enable_roof_fields()

    # --------------------------------------------------------- garden
    def _garden_toggled(self, on):
        if self._syncing:
            return
        self.house.garden = H.Garden(width=self.garden_w.mm(),
                                     depth=self.garden_d.mm(),
                                     gap=self.garden_gap.mm()) if on \
            else None
        self._sync_garden_fields()
        self.canvas.place_garden(self.house)

    def _garden_field_changed(self, key, value):
        if self._syncing:
            return
        if self.house.garden is None:
            self.house.garden = H.Garden()
        setattr(self.house.garden, key, value)
        self.canvas.place_garden(self.house)

    def _sync_garden_fields(self):
        g = self.house.garden
        with self.quiet():
            self.garden_on.setChecked(g is not None)
            shown = g or H.Garden()
            self.garden_w.set_mm(shown.width)
            self.garden_d.set_mm(shown.depth)
            self.garden_gap.set_mm(shown.gap)
            for w in (self.garden_w, self.garden_d, self.garden_gap):
                w.setEnabled(g is not None)

    # ---------------------------------------------------------- sync
    def _sync_all(self):
        self._sync_floor_combo()
        self._sync_floor_fields()
        self._sync_room_list()
        self._sync_room_fields()
        self._sync_items()
        self._rebuild_canvas()

    def _sync_floor_combo(self):
        with self.quiet():
            self.floor_combo.clear()
            for floor in self.house.floors:
                self.floor_combo.addItem(icons.icon("mdi.layers-outline"),
                                         floor.name)
            self.floor_combo.setCurrentIndex(self.current_floor_index)

    def _sync_floor_fields(self):
        floor = self.current_floor
        with self.quiet():
            if floor is not None:
                self.wall_height.set_mm(floor.wall_height)
                self.wall_thickness.set_mm(floor.wall_thickness)
                self.slab_thickness.set_mm(floor.slab_thickness)

    def _room_caption(self, room) -> str:
        return f"{room.name}    {room.w / 1000:.2f} × {room.d / 1000:.2f} m"

    def _sync_room_list(self):
        with self.quiet():
            self.room_list.clear()
            floor = self.current_floor
            for room in floor.rooms if floor else []:
                self.room_list.addItem(QListWidgetItem(
                    icons.icon("mdi.floor-plan"), self._room_caption(room)))
        self._sync_room_list_selection()

    def _sync_room_captions(self):
        floor = self.current_floor
        for i, room in enumerate(floor.rooms if floor else []):
            item = self.room_list.item(i)
            if item is not None:
                item.setText(self._room_caption(room))

    def _sync_room_list_selection(self):
        floor = self.current_floor
        if floor is None or self.current_room not in floor.rooms:
            return
        with self.quiet():
            self.room_list.setCurrentRow(
                floor.rooms.index(self.current_room))

    def _sync_room_fields(self):
        room = self.current_room
        with self.quiet():
            for w in (self.room_name, self.room_x, self.room_y,
                      self.room_w, self.room_d, self.room_kind,
                      self.room_finish):
                w.setEnabled(room is not None)
            if room is not None:
                self.room_name.setText(room.name)
                self.room_kind.setCurrentIndex(
                    max(0, self.room_kind.findData(room.surface)))
                self.room_finish.setCurrentIndex(
                    max(0, self.room_finish.findData(room.finish)))
                self.room_x.set_mm(room.x)
                self.room_y.set_mm(room.y)
                self.room_w.set_mm(room.w)
                self.room_d.set_mm(room.d)

    def _item_caption(self, obj):
        if isinstance(obj, H.Opening):
            return (f"{obj.kind.capitalize()} — {SIDE_SHORT[obj.side]}, "
                    f"{obj.width / 1000:.2f} m wide")
        size = _size_name(obj)
        up = f"  ·  {obj.z / 1000:.2f} m up" if obj.z > 0.5 else ""
        return _label(obj.part_id) + (f" ({size})" if size else "") + up

    def _item_icon(self, obj):
        if isinstance(obj, H.Opening):
            return icons.icon({"door": "mdi.door",
                               "garage door": "mdi.garage"}.get(
                obj.kind, "mdi.window-closed-variant"))
        return icons.icon("mdi.sofa-outline")

    def _sync_items(self):
        """The room's contents list, its title, and the item editor."""
        room = self.current_room
        self.contents_box.setTitle(
            f"3  ·  In {room.name}" if room else "3  ·  In this room")
        with self.quiet():
            self.items_list.clear()
            objs = self._room_items(room) if room else []
            for obj in objs:
                self.items_list.addItem(QListWidgetItem(
                    self._item_icon(obj), self._item_caption(obj)))
            if self.current_item in objs:
                self.items_list.setCurrentRow(objs.index(self.current_item))
        self._sync_editor()

    def _sync_item_captions(self):
        room = self.current_room
        for i, obj in enumerate(self._room_items(room) if room else []):
            item = self.items_list.item(i)
            if item is not None:
                item.setText(self._item_caption(obj))
                item.setIcon(self._item_icon(obj))

    def _sync_editor(self):
        obj = self.current_item
        with self.quiet():
            if isinstance(obj, H.Opening):
                self.editor.setCurrentIndex(1)
                self.editor_box.setTitle(f"4  ·  {obj.kind.capitalize()}")
                self.op_kind.setCurrentIndex(
                    self.op_kind.findData(obj.kind))
                self.op_side.setCurrentIndex(
                    self.op_side.findData(obj.side))
                self.op_offset.set_mm(obj.offset)
                self.op_width.set_mm(obj.width)
                self.op_height.set_mm(obj.height)
                self.op_sill.set_mm(obj.sill)
                self.op_sill.setEnabled(obj.kind == "window")
            elif isinstance(obj, H.Furniture):
                room = self._room_of(obj) or self.current_room
                self.editor.setCurrentIndex(2)
                self.editor_box.setTitle("4  ·  Furniture")
                self.fu_title.setText(_label(obj.part_id))
                _fill_look_combos(obj, self.fu_size, self.fu_color)
                self.fu_x.set_mm(obj.x - room.x)
                self.fu_y.set_mm(obj.y - room.y)
                self.fu_rz.setValue(obj.rz)
                self.fu_z.set_mm(obj.z)
            else:
                self.editor.setCurrentIndex(0)
                self.editor_box.setTitle("4  ·  Selected item")

    def _rebuild_canvas(self):
        with self.quiet():
            self.canvas.rebuild(self.current_floor, self.house,
                                self.current_item or self.current_room)

    # ---------------------------------------------------------- build
    def _build(self):
        try:
            inserted = H.apply(self.window.model, self.house)
        except H.HouseError as exc:
            QMessageBox.warning(self, "House Builder", str(exc))
            return
        self._loaded = json.dumps(self.window.model.house, sort_keys=True)
        names = ", ".join(c.name for c in inserted)
        self.status.setText(f"Built: {names}")
        self.window.builder.tree.select_nodes(inserted)
        self.window.view3d.fit()


# ----------------------------------------------------------- furniture
def _size_name(f) -> str:
    """The Part Library size *f*'s dims were made from, or ""."""
    sizes = LIBRARY_PARTS.get(f.part_id, {}).get("sizes") or {}
    for name, dims in sizes.items():
        if all(f.dims.get(k) == v for k, v in dims.items()):
            return name
    return ""


def _fill_look_combos(f, size_combo, color_combo):
    """Offer *f*'s part sizes and colours, the current ones selected."""
    spec = LIBRARY_PARTS.get(f.part_id, {})
    size_combo.clear()
    sizes = spec.get("sizes") or {}
    current = _size_name(f)
    if current == "" and sizes:
        size_combo.addItem("Custom", None)
    for name in sizes:
        size_combo.addItem(name, name)
    size_combo.setCurrentIndex(max(0, size_combo.findData(current or None)))
    size_combo.setEnabled(len(sizes) > 1)
    color_combo.clear()
    colors = spec.get("colors") or []
    for name in colors:
        color_combo.addItem(name, name)
    if not colors:
        color_combo.addItem("—", None)
    index = color_combo.findData(f.dims.get("_color"))
    color_combo.setCurrentIndex(max(0, index))
    color_combo.setEnabled(bool(colors))


#: words in a room's name -> the catalogue section it suggests, tried in
#: this order ("Kids bedroom" is a kids' room, "Bathroom" not a bedroom)
CATEGORY_WORDS = (
    ("Chemistry lab", ("chem", "fume", "wet lab")),
    ("Physics lab", ("physic", "laser", "optic", "vacuum", "clean room")),
    ("Server room", ("server", "data")),
    ("Meeting room", ("meeting", "conference", "board")),
    ("Break room", ("break", "canteen", "cafe", "staff room")),
    ("Open-plan office", ("open-plan", "open plan", "desks")),
    ("Kids' room", ("kid", "child", "nursery", "baby", "play")),
    ("Bathroom", ("bath", "shower", "toilet", "wc", "en-suite", "ensuite",
                  "cloakroom")),
    ("Bedroom", ("bedroom", "bed room", "guest", "master")),
    ("Dining room", ("dining",)),
    ("Living room", ("living", "lounge", "sitting", "family", "snug")),
    ("Kitchen", ("kitchen",)),
    ("Office / study", ("office", "study", "work")),
    ("Reception", ("reception", "waiting", "lobby")),
    ("Garage", ("garage", "carport", "drive")),
    ("Utility / laundry", ("utility", "laundry")),
    ("Stairs", ("stair",)),
    ("Entrance / porch", ("entrance", "entry", "porch", "vestibule")),
    ("Hallway / corridor", ("hall", "corridor", "landing")),
    ("Garden / outdoor", ("garden", "patio", "yard", "terrace", "lawn",
                          "outdoor")),
)


def _guess_category(room_name) -> str:
    """The catalogue section a room's name suggests ("Main bedroom" ->
    "Bedroom", "Front porch" -> "Entrance / porch"), or ""."""
    words = room_name.lower()
    for category, keys in CATEGORY_WORDS:
        if category in H.FURNITURE_CATALOG and any(k in words for k in keys):
            return category
    return ""


def _swatch(hexcol) -> QIcon:
    pix = QPixmap(14, 14)
    pix.fill(QColor(hexcol))
    return QIcon(pix)


def _pick_furniture_part(parent, room_name="") -> str:
    """A searchable list of the furniture catalogue, grouped by room
    type, opened on the section the room's name suggests. Returns a
    part id, or "" if cancelled."""
    dlg = QDialog(parent)
    dlg.setWindowTitle("Add furniture")
    dlg.resize(380, 520)
    lay = QVBoxLayout(dlg)
    search = QLineEdit()
    search.setPlaceholderText("Search: sofa, bed, table…")
    search.setClearButtonEnabled(True)
    lay.addWidget(search)
    parts = QListWidget()
    lay.addWidget(parts, 1)
    bold = QFont(parts.font())
    bold.setBold(True)
    rows = []                               # (header, [items])
    for category, ids in H.FURNITURE_CATALOG.items():
        header = QListWidgetItem(category)
        header.setFlags(Qt.NoItemFlags)
        header.setFont(bold)
        parts.addItem(header)
        items = []
        for pid in ids:
            item = QListWidgetItem(icons.icon("mdi.sofa-outline"),
                                   "   " + _label(pid))
            item.setData(Qt.UserRole, pid)
            parts.addItem(item)
            items.append(item)
        rows.append((header, category, items))

    def _filter(text):
        text = text.strip().lower()
        for header, category, items in rows:
            shown = 0
            for item in items:
                hide = bool(text) and text not in item.text().lower() \
                    and text not in category.lower()
                item.setHidden(hide)
                shown += not hide
            header.setHidden(shown == 0)

    search.textChanged.connect(_filter)
    guess = _guess_category(room_name)
    for header, category, items in rows:
        if category == guess and items:
            parts.setCurrentItem(items[0])
            parts.scrollToItem(header, QListWidget.PositionAtTop)
            break
    row = QHBoxLayout()
    row.addWidget(_hint("Double-click to add"), 1)
    cancel = QPushButton("Cancel")
    cancel.clicked.connect(dlg.reject)
    ok = QPushButton("Add")
    ok.setDefault(True)
    ok.clicked.connect(dlg.accept)
    row.addWidget(cancel)
    row.addWidget(ok)
    lay.addLayout(row)
    parts.itemDoubleClicked.connect(
        lambda item: dlg.accept() if item.data(Qt.UserRole) else None)
    if dlg.exec_() == QDialog.Accepted and parts.currentItem() is not None:
        return parts.currentItem().data(Qt.UserRole) or ""
    return ""


def open_builder(window):
    panel = getattr(window, "_house_builder", None)
    if panel is None:
        panel = window._house_builder = HouseBuilder(window)
    else:
        panel.load_from_document()    # a house opened/built since
    panel.show()
    panel.raise_()
    panel.activateWindow()
    return panel

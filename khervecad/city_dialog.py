"""Library ▸ City Builder…: design a village, town or city on a 2D plan
and place every road, building, tree and street light by hand.

The window edits a city SPEC (city.resolve's shape: explicit lists of
roads, buildings, lights and trees) on its own Y-up canvas. Generate
fills it from a layout and a seed; the tools add pieces with a click
(a road is clicked point by point, double-click or Enter to finish);
select a piece to drag it, R to turn it, Delete to remove it, and edit
it in the panel — style, floors, size, wall (brick / concrete / render
/ stone) and its colour, roof shape, tiles or slate and their colour.
**Build** writes it into the document with `city.apply`, which replaces
the city built last time and stores the design as ``model.city`` (saved
in the .kcad), so the window reopens on it.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import copy
import json
import math

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import (QAction, QActionGroup, QColorDialog, QComboBox,
                             QDialog, QDoubleSpinBox, QFormLayout,
                             QGraphicsScene, QGraphicsView, QGroupBox,
                             QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                             QPushButton, QScrollArea, QSpinBox,
                             QStackedWidget, QToolBar, QVBoxLayout, QWidget)

from . import city as C
from . import city_buildings as B
from . import city_items as CI
from . import icons
from .city_trees import TREE_KINDS
from .house_dialog import MetreSpin

#: a new building's footprint by style, mm
DEFAULT_SIZE = {"cottage": (9000, 7000), "house": (10000, 8000),
                "terrace": (7000, 9000), "shop": (9000, 10000),
                "block": (16000, 12000), "tower": (18000, 18000),
                "round tower": (14000, 14000), "L-shape": (14000, 12000),
                "church": (22000, 11000)}

TOOLS = (("select", "mdi.cursor-default-outline", "Select and move (S)"),
         ("road", "mdi.road-variant", "Draw a road: click its points, "
          "double-click or Enter to finish (D)"),
         ("building", "mdi.home-city-outline", "Place a building (B)"),
         ("tree", "mdi.pine-tree", "Plant a tree (T)"),
         ("light", "mdi.lightbulb-outline", "Place a street light (L)"))


def _hint(text):
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet("color: #6b7280; font-size: 11px;")
    return label


def empty_spec():
    return dict(name="City", roads=[], buildings=[], lights=[], trees=[],
                ground=dict(margin=20000.0, color=C.GRASS))


class CityCanvas(QGraphicsView):
    """The plan: Y-up millimetres, an adaptive grid, pan by dragging
    empty space or with the middle button, wheel zoom."""

    MIN_ZOOM, MAX_ZOOM = 0.0004, 1.0

    def __init__(self, dialog):
        super().__init__(QGraphicsScene())
        self.dialog = dialog
        self.setRenderHints(QPainter.Antialiasing)
        self.setBackgroundBrush(QColor("#dfe8d6"))
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.scale(0.02, -0.02)
        self.items_by_id = {}
        self.draft = None
        self._pan = None

    # ----------------------------------------------------------- items
    def rebuild(self, spec, selected=None):
        scene = self.scene()
        scene.clearSelection()
        scene.clear()
        self.items_by_id = {}
        self.draft = None
        d = self.dialog
        kw = dict(on_change=d._item_moved, on_pick=d._item_picked,
                  on_release=d._item_released)
        for road in spec["roads"]:
            self._add(CI.RoadItem(road, **kw), road)
        for i, b in enumerate(spec["buildings"]):
            self._add(CI.BuildingItem(b, i, **kw), b)
        for t in spec["trees"]:
            self._add(CI.TreeItem(t, **kw), t)
        for p in spec["lights"]:
            self._add(CI.LightItem(p, **kw), p)
        rect = self.content_rect()
        pad = max(rect.width(), rect.height(), 200000.0)
        scene.setSceneRect(rect.adjusted(-pad, -pad, pad, pad))
        if selected is not None:
            item = self.items_by_id.get(id(selected))
            if item is not None:
                item.setSelected(True)

    def _add(self, item, spec):
        self.scene().addItem(item)
        self.items_by_id[id(spec)] = item
        return item

    def content_rect(self):
        rect = QRectF()
        for item in self.items_by_id.values():
            rect = rect.united(item.sceneBoundingRect())
        return rect if not rect.isNull() else QRectF(-50000, -50000,
                                                     100000, 100000)

    def fit(self):
        rect = self.content_rect().adjusted(-10000, -10000, 10000, 10000)
        self.fitInView(rect, Qt.KeepAspectRatio)
        t = self.transform()                   # keep Y up
        if t.m22() > 0:
            self.scale(1, -1)

    def px_per_mm(self):
        return abs(self.transform().m11())

    def wheelEvent(self, event):
        f = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        if self.MIN_ZOOM < self.px_per_mm() * f < self.MAX_ZOOM:
            self.scale(f, f)

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        ppm = self.px_per_mm()
        step = 1000.0
        while step * ppm < 10:
            step *= 5.0
        for major, colour in ((False, "#d2dccb"), (True, "#bccab4")):
            s = step * 5 if major else step
            pen = QPen(QColor(colour), 0)
            pen.setCosmetic(True)
            painter.setPen(pen)
            x = s * math.floor(rect.left() / s)
            while x <= rect.right():
                painter.drawLine(QPointF(x, rect.top()),
                                 QPointF(x, rect.bottom()))
                x += s
            y = s * math.floor(rect.top() / s)
            while y <= rect.bottom():
                painter.drawLine(QPointF(rect.left(), y),
                                 QPointF(rect.right(), y))
                y += s

    # ----------------------------------------------------------- input
    def _scene_pt(self, event):
        p = self.mapToScene(event.pos())
        return QPointF(CI.snap(p.x()), CI.snap(p.y()))

    def mousePressEvent(self, event):
        tool = self.dialog.tool
        if event.button() == Qt.LeftButton and tool != "select":
            pt = self._scene_pt(event)
            if tool == "road":
                if self.draft is None:
                    width, walk, _ = C.road_style(
                        dict(kind=self.dialog.road_kind()))
                    self.draft = CI.RoadDraft(width + 2 * walk)
                    self.scene().addItem(self.draft)
                self.draft.add(pt)
            else:
                self.dialog._place(tool, pt)
            event.accept()
            return
        empty = self.itemAt(event.pos()) is None
        if event.button() == Qt.MiddleButton or (
                event.button() == Qt.LeftButton and empty):
            self._pan = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            if empty and event.button() == Qt.LeftButton:
                self.scene().clearSelection()
                self.dialog._item_picked(None)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self.dialog.tool == "road" and self.draft is not None:
            self.finish_road()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

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
        if self.draft is not None:
            self.draft.set_cursor(self._scene_pt(event))
        p = self.mapToScene(event.pos())
        self.dialog.coords.setText(f"x {p.x() / 1000:.1f} m   "
                                   f"y {p.y() / 1000:.1f} m")
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._pan is not None:
            self._pan = None
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def finish_road(self):
        draft, self.draft = self.draft, None
        if draft is None:
            return
        pts = []
        for p in draft.points:                 # a double-click adds twice
            if not pts or (abs(p.x() - pts[-1][0]) > 1
                           or abs(p.y() - pts[-1][1]) > 1):
                pts.append([p.x(), p.y()])
        self.scene().removeItem(draft)
        if len(pts) >= 2:
            self.dialog._add_road(pts)

    def cancel_road(self):
        if self.draft is not None:
            self.scene().removeItem(self.draft)
            self.draft = None

    def keyPressEvent(self, event):
        key = event.key()
        d = self.dialog
        if key in (Qt.Key_Return, Qt.Key_Enter) and self.draft is not None:
            self.finish_road()
        elif key == Qt.Key_Escape:
            if self.draft is not None:
                self.cancel_road()
            else:
                d.set_tool("select")
                self.scene().clearSelection()
        elif key in (Qt.Key_Delete, Qt.Key_Backspace):
            d._remove_selected()
        elif key == Qt.Key_R:
            d._rotate_selected(-90.0 if event.modifiers() & Qt.ShiftModifier
                               else 90.0)
        elif key in (Qt.Key_S, Qt.Key_D, Qt.Key_B, Qt.Key_T, Qt.Key_L):
            d.set_tool({Qt.Key_S: "select", Qt.Key_D: "road",
                        Qt.Key_B: "building", Qt.Key_T: "tree",
                        Qt.Key_L: "light"}[key])
        else:
            super().keyPressEvent(event)


class ColorButton(QPushButton):
    def __init__(self, on_pick):
        super().__init__()
        self.on_pick = on_pick
        self.colour = "#ffffff"
        self.setFixedWidth(80)
        self.clicked.connect(self._choose)

    def set_colour(self, colour):
        self.colour = colour
        self.setText(colour)
        text = "#000" if QColor(colour).lightness() > 128 else "#fff"
        self.setStyleSheet(f"background:{colour}; color:{text};")

    def _choose(self):
        c = QColorDialog.getColor(QColor(self.colour), self, "Colour")
        if c.isValid():
            self.set_colour(c.name())
            self.on_pick(c.name())


class CityBuilder(QDialog):
    """The City Builder window (one per main window)."""

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle("City Builder")
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
        self.resize(1300, 820)
        self.spec = empty_spec()
        self.selected = None           # the spec dict of the selection
        self.tool = "select"
        self._quiet = False
        self._loaded = None
        self._build_ui()
        self.load_from_document(force=True)

    # --------------------------------------------------------------- ui
    def _build_ui(self):
        outer = QHBoxLayout(self)
        side = QWidget()
        col = QVBoxLayout(side)
        col.addWidget(self._generate_group())
        col.addWidget(self._place_group())
        col.addWidget(self._editor_group())
        col.addWidget(self._along_group())
        col.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidget(side)
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(330)
        outer.addWidget(scroll)

        right = QVBoxLayout()
        self.canvas = CityCanvas(self)
        right.addWidget(self._toolbar())
        right.addWidget(_hint(
            "Drag a piece to move it (0.5 m grid), R / Shift+R turns it, "
            "Delete removes it. Roads: click each point, double-click or "
            "Enter to finish; select a road to drag its points. Drag empty "
            "space to pan, wheel to zoom."))
        right.addWidget(self.canvas, 1)
        bottom = QHBoxLayout()
        self.coords = QLabel("")
        self.counts = QLabel("")
        bottom.addWidget(self.counts)
        bottom.addStretch(1)
        bottom.addWidget(self.coords)
        self.build_btn = QPushButton(icons.icon("mdi.city-variant-outline"),
                                     "  Build into the document")
        self.build_btn.setDefault(True)
        self.build_btn.clicked.connect(self._build)
        bottom.addWidget(self.build_btn)
        right.addLayout(bottom)
        outer.addLayout(right, 1)

    def _toolbar(self):
        bar = QToolBar()
        self.tool_actions = {}
        group = QActionGroup(self)
        for key, icon, tip in TOOLS:
            act = QAction(icons.icon(icon), tip.split(" (")[0].split(":")[0],
                          self)
            act.setToolTip(tip)
            act.setCheckable(True)
            act.triggered.connect(lambda _=False, k=key: self.set_tool(k))
            group.addAction(act)
            bar.addAction(act)
            self.tool_actions[key] = act
        self.tool_actions["select"].setChecked(True)
        bar.addSeparator()
        for icon, text, slot in (
                ("mdi.rotate-left", "Turn left", lambda: self._rotate_selected(90)),
                ("mdi.rotate-right", "Turn right",
                 lambda: self._rotate_selected(-90)),
                ("mdi.delete-outline", "Delete", self._remove_selected),
                ("mdi.fit-to-page-outline", "Fit", self.canvas.fit)):
            act = bar.addAction(icons.icon(icon), text)
            act.triggered.connect(slot)
        return bar

    def _generate_group(self):
        box = QGroupBox("1  Start from a layout")
        form = QFormLayout(box)
        self.layout_combo = QComboBox()
        self.layout_combo.addItems(["village", "town", "city"])
        self.blocks = QSpinBox()
        self.blocks.setRange(0, 12)
        self.blocks.setSpecialValueText("auto")
        self.seed = QSpinBox()
        self.seed.setRange(1, 99999)
        form.addRow("Layout", self.layout_combo)
        form.addRow("Blocks", self.blocks)
        form.addRow("Seed", self.seed)
        row = QHBoxLayout()
        gen = QPushButton("Generate")
        gen.clicked.connect(self._generate)
        clear = QPushButton("Clear plan")
        clear.clicked.connect(self._clear)
        row.addWidget(gen)
        row.addWidget(clear)
        form.addRow(row)
        form.addRow(_hint("Generating replaces the plan; every piece stays "
                          "editable afterwards."))
        return box

    def _place_group(self):
        box = QGroupBox("2  What the tools place")
        form = QFormLayout(box)
        self.style_combo = QComboBox()
        self.style_combo.addItems(list(B.STYLES))
        self.tree_combo = QComboBox()
        self.tree_combo.addItems(list(TREE_KINDS))
        self.road_combo = QComboBox()
        self.road_combo.addItems(list(C.ROAD_KINDS))
        self.road_combo.setCurrentText("street")
        form.addRow("Building", self.style_combo)
        form.addRow("Tree", self.tree_combo)
        form.addRow("Road", self.road_combo)
        return box

    def _editor_group(self):
        box = QGroupBox("3  Selected")
        lay = QVBoxLayout(box)
        self.sel_label = QLabel("Nothing selected")
        self.sel_label.setWordWrap(True)
        lay.addWidget(self.sel_label)
        self.stack = QStackedWidget()
        self.stack.addWidget(QWidget())
        self.stack.addWidget(self._building_editor())
        self.stack.addWidget(self._road_editor())
        self.stack.addWidget(self._tree_editor())
        self.stack.addWidget(self._light_editor())
        lay.addWidget(self.stack)
        return box

    def _building_editor(self):
        w = QWidget()
        f = QFormLayout(w)
        self.b_name = QLineEdit()
        self.b_name.editingFinished.connect(
            lambda: self._set_b("name", self.b_name.text().strip()))
        self.b_style = QComboBox()
        self.b_style.addItems(list(B.STYLES))
        self.b_style.activated.connect(
            lambda _i: self._set_b("style", self.b_style.currentText()))
        self.b_floors = QSpinBox()
        self.b_floors.setRange(1, 80)
        self.b_floors.setKeyboardTracking(False)
        self.b_floors.valueChanged.connect(
            lambda v: self._set_b("floors", v))
        self.b_fh = MetreSpin(2.2, 6.0, 0.1)
        self.b_fh.valueChanged.connect(
            lambda _v: self._set_b("floor_height", self.b_fh.mm()))
        self.b_w = MetreSpin(2.0, 200.0, 0.5)
        self.b_w.valueChanged.connect(lambda _v: self._set_b("w", self.b_w.mm()))
        self.b_d = MetreSpin(2.0, 200.0, 0.5)
        self.b_d.valueChanged.connect(lambda _v: self._set_b("d", self.b_d.mm()))
        self.b_rz = QDoubleSpinBox()
        self.b_rz.setRange(-180, 180)
        self.b_rz.setSuffix("°")
        self.b_rz.setKeyboardTracking(False)
        self.b_rz.valueChanged.connect(lambda v: self._set_b("rz", v))
        self.b_wall = QComboBox()
        self.b_wall.addItems(list(B.WALLS))
        self.b_wall.activated.connect(self._wall_changed)
        self.b_wall_col = ColorButton(lambda c: self._set_b("color", c))
        self.b_roof = QComboBox()
        self.b_roof.addItems(list(B.ROOF_KINDS))
        self.b_roof.activated.connect(
            lambda _i: self._set_b("roof", self.b_roof.currentText()))
        self.b_roof_mat = QComboBox()
        self.b_roof_mat.addItems(list(B.ROOFS))
        self.b_roof_mat.activated.connect(self._roof_mat_changed)
        self.b_roof_col = ColorButton(lambda c: self._set_b("roof_color", c))
        for label, widget in (("Name", self.b_name), ("Style", self.b_style),
                              ("Floors", self.b_floors),
                              ("Floor height", self.b_fh),
                              ("Width (along front)", self.b_w),
                              ("Depth", self.b_d), ("Rotation", self.b_rz),
                              ("Walls", self.b_wall),
                              ("Wall colour", self.b_wall_col),
                              ("Roof", self.b_roof),
                              ("Roof covering", self.b_roof_mat),
                              ("Roof colour", self.b_roof_col)):
            f.addRow(label, widget)
        return w

    def _road_editor(self):
        w = QWidget()
        f = QFormLayout(w)
        self.r_kind = QComboBox()
        self.r_kind.addItems(list(C.ROAD_KINDS))
        self.r_kind.activated.connect(self._road_kind_changed)
        self.r_width = MetreSpin(1.0, 40.0, 0.5)
        self.r_width.valueChanged.connect(
            lambda _v: self._set_r("width", self.r_width.mm()))
        self.r_walk = MetreSpin(0.0, 10.0, 0.25)
        self.r_walk.valueChanged.connect(
            lambda _v: self._set_r("sidewalk", self.r_walk.mm()))
        f.addRow("Kind", self.r_kind)
        f.addRow("Carriageway", self.r_width)
        f.addRow("Pavement each side", self.r_walk)
        return w

    def _tree_editor(self):
        w = QWidget()
        f = QFormLayout(w)
        self.t_kind = QComboBox()
        self.t_kind.addItems(list(TREE_KINDS))
        self.t_kind.activated.connect(self._tree_kind_changed)
        self.t_height = MetreSpin(1.0, 40.0, 0.5)
        self.t_height.valueChanged.connect(
            lambda _v: self._set_t("height", self.t_height.mm()))
        f.addRow("Kind", self.t_kind)
        f.addRow("Height", self.t_height)
        return w

    def _light_editor(self):
        w = QWidget()
        f = QFormLayout(w)
        self.l_rz = QDoubleSpinBox()
        self.l_rz.setRange(-180, 180)
        self.l_rz.setSuffix("°")
        self.l_rz.setKeyboardTracking(False)
        self.l_rz.valueChanged.connect(lambda v: self._set_l(v))
        face = QPushButton("Face the nearest road")
        face.clicked.connect(self._face_road)
        f.addRow("Facing", self.l_rz)
        f.addRow(face)
        return w

    def _along_group(self):
        box = QGroupBox("4  Along the roads")
        form = QFormLayout(box)
        self.spacing = MetreSpin(5.0, 200.0, 1.0, decimals=0)
        self.spacing.set_mm(30000)
        form.addRow("Spacing", self.spacing)
        row = QHBoxLayout()
        lights = QPushButton("Line with lights")
        lights.setToolTip("Replace every street light with a row along "
                          "both pavements of every road")
        lights.clicked.connect(self._line_lights)
        trees = QPushButton("Add street trees")
        trees.clicked.connect(self._line_trees)
        row.addWidget(lights)
        row.addWidget(trees)
        form.addRow(row)
        self.margin = MetreSpin(0.0, 500.0, 5.0, decimals=0)
        self.margin.valueChanged.connect(self._margin_changed)
        form.addRow("Grass beyond the plan", self.margin)
        return box

    # ------------------------------------------------------------ state
    def load_from_document(self, force=False):
        """Show the document's city (model.city), unless it is already
        the one on screen — unbuilt edits survive reopening."""
        stored = self.window.model.city
        key = json.dumps(stored, sort_keys=True) if stored else None
        if not force and key == self._loaded:
            return False
        self._loaded = key
        spec = copy.deepcopy(stored) if stored else empty_spec()
        spec.pop("objects", None)
        for k in ("roads", "buildings", "lights", "trees"):
            spec.setdefault(k, [])
        self.spec = spec
        self.selected = None
        self._refresh(fit=True)
        return True

    def _refresh(self, fit=False):
        self.canvas.rebuild(self.spec, self.selected)
        if fit:
            self.canvas.fit()
        g = self.spec.get("ground") or {}
        self._quiet = True
        self.margin.set_mm(float(g.get("margin", 0.0)))
        self._quiet = False
        self._show_selection()
        self._update_counts()

    def _update_counts(self):
        s = self.spec
        self.counts.setText(
            f"{len(s['roads'])} roads · {len(s['buildings'])} buildings · "
            f"{len(s['trees'])} trees · {len(s['lights'])} lights")

    def set_tool(self, tool):
        if tool != "road":
            self.canvas.finish_road()
        self.tool = tool
        self.tool_actions[tool].setChecked(True)
        self.canvas.setCursor(Qt.ArrowCursor if tool == "select"
                              else Qt.CrossCursor)

    def road_kind(self):
        return self.road_combo.currentText()

    def _kind_of(self, spec):
        for kind in ("roads", "buildings", "trees", "lights"):
            if any(x is spec for x in self.spec[kind]):
                return kind
        return None

    # ------------------------------------------------------- selection
    def _item_picked(self, item):
        if self._quiet:
            return
        self.selected = item.spec if item is not None else None
        self._show_selection()

    def _item_moved(self, item):
        """A drag writes x/y into the spec itself; nothing to mirror."""

    def _item_released(self, item):
        self._update_counts()

    def _show_selection(self):
        s = self.selected
        kind = self._kind_of(s) if s is not None else None
        self._quiet = True
        try:
            if kind is None:
                self.stack.setCurrentIndex(0)
                self.sel_label.setText("Nothing selected — click a piece "
                                       "on the plan.")
                return
            item = self.canvas.items_by_id.get(id(s))
            self.sel_label.setText(item.label() if item else "")
            if kind == "buildings":
                index = self.spec["buildings"].index(s)
                r = B.resolve(s, index)
                s.update(r)                    # show and keep the defaults
                self.b_name.setText(r["name"])
                self.b_style.setCurrentText(r["style"])
                self.b_floors.setValue(r["floors"])
                self.b_fh.set_mm(r["floor_height"])
                self.b_w.set_mm(r["w"])
                self.b_d.set_mm(r["d"])
                self.b_rz.setValue(r["rz"])
                self.b_wall.setCurrentText(r["wall"])
                self.b_wall_col.set_colour(r["color"])
                self.b_roof.setCurrentText(r["roof"])
                self.b_roof_mat.setCurrentText(r["roof_material"])
                self.b_roof_col.set_colour(r["roof_color"])
                self.stack.setCurrentIndex(1)
            elif kind == "roads":
                width, walk, _ = C.road_style(s)
                self.r_kind.setCurrentText(s.get("kind", "street"))
                self.r_width.set_mm(width)
                self.r_walk.set_mm(walk)
                self.stack.setCurrentIndex(2)
            elif kind == "trees":
                self.t_kind.setCurrentText(s.get("kind", "broadleaf"))
                self.t_height.set_mm(float(s.get("height", 6000)))
                self.stack.setCurrentIndex(3)
            else:
                self.l_rz.setValue(float(s.get("rz", 0.0)))
                self.stack.setCurrentIndex(4)
        finally:
            self._quiet = False

    def _sync_selected(self):
        item = self.canvas.items_by_id.get(id(self.selected))
        if item is not None:
            item.sync()
            self.sel_label.setText(item.label())

    # ----------------------------------------------------------- edits
    def _set_b(self, key, value):
        if self._quiet or self._kind_of(self.selected) != "buildings":
            return
        if key == "name" and not value:
            return
        self.selected[key] = value
        if key == "style":                     # a style brings its looks
            (lo, hi), roof, _g, wall = B.STYLES[value]
            self.selected.update(roof=roof, wall=wall)
            self.selected["floors"] = min(max(int(self.selected.get(
                "floors", lo)), lo), hi)
            w, d = DEFAULT_SIZE[value]
            self.selected.update(w=w, d=d)
            for k in ("color", "roof_material", "roof_color"):
                self.selected.pop(k, None)
        self._sync_selected()
        if key == "style":
            self._show_selection()

    def _wall_changed(self, _i=None):
        if self._quiet or self._kind_of(self.selected) != "buildings":
            return
        wall = self.b_wall.currentText()
        self.selected["wall"] = wall
        index = self.spec["buildings"].index(self.selected)
        pal = B.WALLS[wall][1]
        self.selected["color"] = pal[index % len(pal)]
        self._sync_selected()
        self._show_selection()

    def _roof_mat_changed(self, _i=None):
        if self._quiet or self._kind_of(self.selected) != "buildings":
            return
        mat = self.b_roof_mat.currentText()
        self.selected["roof_material"] = mat
        index = self.spec["buildings"].index(self.selected)
        pal = B.ROOFS[mat][1]
        self.selected["roof_color"] = pal[index % len(pal)]
        self._sync_selected()
        self._show_selection()

    def _set_r(self, key, value):
        if self._quiet or self._kind_of(self.selected) != "roads":
            return
        self.selected[key] = value
        self._sync_selected()

    def _road_kind_changed(self, _i=None):
        if self._quiet or self._kind_of(self.selected) != "roads":
            return
        self.selected["kind"] = self.r_kind.currentText()
        self.selected.pop("width", None)
        self.selected.pop("sidewalk", None)
        self._sync_selected()
        self._show_selection()

    def _set_t(self, key, value):
        if self._quiet or self._kind_of(self.selected) != "trees":
            return
        self.selected[key] = value
        self._sync_selected()

    def _tree_kind_changed(self, _i=None):
        if self._quiet or self._kind_of(self.selected) != "trees":
            return
        kind = self.t_kind.currentText()
        self.selected["kind"] = kind
        self.selected["height"] = TREE_KINDS[kind]
        self._sync_selected()
        self._show_selection()

    def _set_l(self, value):
        if self._quiet or self._kind_of(self.selected) != "lights":
            return
        self.selected["rz"] = value
        self._sync_selected()

    def _face_road(self):
        if self._kind_of(self.selected) != "lights":
            return
        rz = self._facing(self.selected["x"], self.selected["y"])
        if rz is not None:
            self.selected["rz"] = rz
            self._sync_selected()
            self._show_selection()

    def _facing(self, x, y):
        """The turn that points a light's arm (local -Y) at the nearest
        road centre-line, or None with no road."""
        best = None
        for road in self.spec["roads"]:
            for a, b in C._segments(road):
                dx, dy = b[0] - a[0], b[1] - a[1]
                t = max(0.0, min(1.0, ((x - a[0]) * dx + (y - a[1]) * dy)
                                 / (dx * dx + dy * dy)))
                px, py = a[0] + t * dx, a[1] + t * dy
                dist = math.hypot(px - x, py - y)
                if best is None or dist < best[0]:
                    best = (dist, px, py)
        if best is None:
            return None
        _d, px, py = best
        return round(math.degrees(math.atan2(py - y, px - x)) + 90.0, 1)

    def _margin_changed(self, _v=None):
        if self._quiet:
            return
        g = self.spec.get("ground") or dict(color=C.GRASS)
        g["margin"] = self.margin.mm()
        self.spec["ground"] = g

    # --------------------------------------------------- add / remove
    def _place(self, tool, pt):
        x, y = pt.x(), pt.y()
        if tool == "building":
            style = self.style_combo.currentText()
            w, d = DEFAULT_SIZE[style]
            index = len(self.spec["buildings"])
            # the front (-Y) faces the nearest road, like a light's arm
            spec = B.resolve(dict(style=style, x=x, y=y, w=w, d=d,
                                  rz=self._facing(x, y) or 0.0), index)
            names = {b.get("name") for b in self.spec["buildings"]}
            base, n = spec["name"], 2
            while spec["name"] in names:
                spec["name"] = f"{base.rsplit(' ', 1)[0]} {index + n}"
                n += 1
            self.spec["buildings"].append(spec)
        elif tool == "tree":
            kind = self.tree_combo.currentText()
            spec = dict(x=x, y=y, z=0.0, rz=0.0, kind=kind,
                        height=TREE_KINDS[kind])
            self.spec["trees"].append(spec)
        elif tool == "light":
            spec = dict(x=x, y=y, rz=self._facing(x, y) or 0.0)
            self.spec["lights"].append(spec)
        else:
            return
        self.selected = spec
        self._refresh()

    def _add_road(self, pts):
        spec = dict(kind=self.road_kind(), points=pts)
        self.spec["roads"].append(spec)
        self.selected = spec
        self._refresh()

    def _remove_selected(self):
        kind = self._kind_of(self.selected)
        if kind is None:
            return
        self.spec[kind] = [x for x in self.spec[kind]
                           if x is not self.selected]
        self.selected = None
        self._refresh()

    def _rotate_selected(self, step):
        kind = self._kind_of(self.selected)
        if kind not in ("buildings", "lights"):
            return
        rz = float(self.selected.get("rz", 0.0)) + step
        while rz > 180:
            rz -= 360
        while rz <= -180:
            rz += 360
        self.selected["rz"] = rz
        self._sync_selected()
        self._show_selection()

    def _generate(self):
        if (self.spec["roads"] or self.spec["buildings"]) and \
                QMessageBox.question(
                    self, "Generate",
                    "Replace the plan with a generated layout?") \
                != QMessageBox.Yes:
            return
        try:
            spec = C.resolve(dict(layout=self.layout_combo.currentText(),
                                  blocks=self.blocks.value(),
                                  seed=self.seed.value()))
        except C.CityError as exc:
            QMessageBox.warning(self, "Generate", str(exc))
            return
        self.spec = spec
        self.selected = None
        self._refresh(fit=True)

    def _clear(self):
        if QMessageBox.question(self, "Clear plan", "Remove every road, "
                                "building, tree and light from the plan?") \
                != QMessageBox.Yes:
            return
        self.spec = empty_spec()
        self.selected = None
        self._refresh(fit=True)

    def _line_lights(self):
        pts = C.along_roads(self.spec["roads"], self.spacing.mm())
        self.spec["lights"] = [dict(x=x, y=y, rz=rz) for x, y, rz in pts]
        self.selected = None
        self._refresh()

    def _line_trees(self):
        kind = self.tree_combo.currentText()
        for x, y, rz in C.along_roads(self.spec["roads"], self.spacing.mm(),
                                      phase=0.5):
            self.spec["trees"].append(dict(x=x, y=y, z=C.KERB, rz=rz,
                                           kind=kind,
                                           height=TREE_KINDS[kind]))
        self.selected = None
        self._refresh()

    # ------------------------------------------------------------ build
    def _build(self):
        self.canvas.finish_road()
        try:
            result = C.apply(self.window.model, self.spec)
        except C.CityError as exc:
            QMessageBox.warning(self, "City Builder", str(exc))
            return
        self._loaded = json.dumps(self.window.model.city, sort_keys=True)
        self.window.view3d.fit()
        c = result["counts"]
        self.window.statusBar().showMessage(
            f"City built: {c['buildings']} buildings, {c['roads']} roads, "
            f"{c['trees']} trees, {c['lights']} lights", 6000)


def open_builder(window):
    panel = getattr(window, "_city_builder", None)
    if panel is None:
        panel = window._city_builder = CityBuilder(window)
    else:
        panel.load_from_document()
    panel.show()
    panel.raise_()
    panel.activateWindow()
    return panel

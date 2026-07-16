"""MainWindow shell: panels, toolbars, menus, selection sync.

Layout (the classic 3D-builder arrangement):

- left column — the object builder: Objects tree / Code tabs on top,
  the Properties panel below;
- right column — the 2D sketch view on top, the 3D preview below;
- vertical toolbar — shape tools (select, line, rectangle, circle,
  polygon, text) and 3D primitives (cube, sphere, cylinder);
- horizontal toolbar — file ops, the operations that wrap selected
  objects (linear/rotate extrude, transforms, booleans) and grid
  controls.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from pathlib import Path

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtWidgets import (QAbstractSpinBox, QAction, QActionGroup,
                             QApplication, QComboBox, QDockWidget,
                             QDoubleSpinBox, QFileDialog, QLabel,
                             QMainWindow, QMessageBox, QSplitter,
                             QToolBar)

from . import APP_NAME, __version__, document, icons, mesh
from .engine import ScadEngine, set_openscad_path
from .model import NODE_TYPES, DocumentModel
from .properties import PropertiesPanel
from .style import THEMES, apply_style, current_theme
from .treepanel import BuilderPanel
from .view2d import (CIRCLE, DIMENSION, LINE, MEASURE, PLANES, POLYGON,
                     RECT, SELECT, TEXT, SketchScene, SketchView)
from .view3d import View3D

ICON_SIZE = QSize(28, 28)

#: (tool id, mdi icon, label, shortcut) for the 2D drawing tools.
TOOLS = [
    (SELECT, "mdi.cursor-default-outline", "Select", "V"),
    (LINE, "mdi.vector-line", "Line", "L"),
    (RECT, "mdi.rectangle-outline", "Rectangle", "R"),
    (CIRCLE, "mdi.circle-outline", "Circle", "C"),
    (POLYGON, "mdi.vector-polygon", "Polygon", "P"),
    (TEXT, "mdi.format-text", "Text", "T"),
]

#: measure / annotation tools (grouped after a separator in the bar).
MEASURE_TOOLS = [
    (MEASURE, "mdi.tape-measure", "Measure distance", "M"),
    (DIMENSION, "mdi.ruler-square", "Add dimension", "D"),
]

#: 3D primitives added with one click.
PRIMITIVES = ["cube", "sphere", "cylinder"]

#: operations in the horizontal toolbar (applied to the selection —
#: control-flow tools insert standalone when nothing is selected).
OPERATIONS = ["linear_extrude", "rotate_extrude", "translate", "rotate",
              "scale", "mirror", "union", "difference", "intersection",
              "for_loop", "while_loop", "if_else"]


class MainWindow(QMainWindow):
    #: every open window, so a second instance isn't garbage-collected.
    _windows = []

    def __init__(self):
        super().__init__()
        self.setWindowIcon(icons.app_icon())
        self.resize(1400, 900)
        self.setAcceptDrops(True)             # drop .kcad/.scad/.stl to open

        self.model = DocumentModel()
        self.engine = ScadEngine(self)
        self._path = None
        self._dirty = False
        self._syncing = False
        self._fitted = False

        # ---- panels
        self.builder = BuilderPanel(self.model)
        self.properties = PropertiesPanel(self.model)
        self.scene = SketchScene(self.model)
        self.view2d = SketchView(self.scene)
        self.view3d = View3D()

        left = QSplitter(Qt.Vertical)
        left.addWidget(self.builder)
        left.addWidget(self.properties)
        # give the Properties panel roughly the same height as the tree
        # (it holds a tall form + point tables), and let both grow
        left.setStretchFactor(0, 1)
        left.setStretchFactor(1, 1)
        left.setSizes([380, 470])

        right = QSplitter(Qt.Vertical)
        right.addWidget(self.view2d)
        right.addWidget(self.view3d)
        # give the 3D preview the larger share of the right column
        right.setStretchFactor(0, 2)
        right.setStretchFactor(1, 3)
        right.setSizes([360, 500])

        split = QSplitter(Qt.Horizontal)
        split.addWidget(left)
        split.addWidget(right)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        # a wider left column so property fields (often expressions like
        # "seat_w - inset - leg_t") are readable
        split.setSizes([430, 970])
        self.setCentralWidget(split)

        # ---- wiring
        self.builder.tree.selection_changed.connect(self._tree_selected)
        self.builder.object_tab.tree.selection_changed.connect(
            self._tree_selected)
        self.builder.masters_tree.selection_changed.connect(
            self._masters_selected)
        # the Object tab isolates both viewers to the active Object
        self.scene.isolation_resolver = self.builder.isolated_component
        self.builder.active_component_changed.connect(
            lambda _n: self._isolation_changed())
        self.builder.currentChanged.connect(
            lambda _i: self._isolation_changed())
        self.scene.selection_changed.connect(self._scene_selected)
        self.scene.node_created.connect(self._node_created)
        self.scene.plane_changed.connect(self._on_plane_auto_changed)
        self.properties.point_selected.connect(
            self.scene.set_point_highlight)
        self.view2d.cursor_moved.connect(self._cursor_moved)
        self.view2d.zoom_changed.connect(
            lambda ppm: self._zoom_label.setText(
                f"1 mm = {ppm:.2f} px"))
        self.scene.measure_changed.connect(
            lambda text: self._measure_label.setText(text))
        self.view2d.clipboard_op.connect(
            lambda op: {"cut": self.builder.tree.cut_selection,
                        "copy": self.builder.tree.copy_selection,
                        "paste": self.builder.tree.paste_clipboard
                        }[op]())
        self.view2d.step_object.connect(
            self.builder.tree.step_selection)
        self.model.structure_changed.connect(self._model_edited)
        self.model.node_changed.connect(lambda _n: self._model_edited())
        self.engine.mesh_ready.connect(self._engine_mesh)
        self.engine.render_failed.connect(self._engine_failed)
        self.engine.busy_changed.connect(self._engine_busy)

        self._build_chat_dock()
        self._build_tool_bar()
        self._build_options_bar()
        self._build_menus()
        self._build_status_bar()
        self._update_title()
        self._refresh_preview()

    def _build_chat_dock(self):
        from .chat import ChatPanel
        self.chat = ChatPanel(self)
        self._chat_dock = QDockWidget("Assistant", self)
        self._chat_dock.setObjectName("chat_dock")
        self._chat_dock.setWidget(self.chat)
        self.addDockWidget(Qt.RightDockWidgetArea, self._chat_dock)
        self._chat_dock.show()               # visible by default (Ctrl+/)

    # ------------------------------------------------------------ chrome
    def _build_tool_bar(self):
        bar = QToolBar("Tools")
        bar.setIconSize(ICON_SIZE)
        bar.setMovable(False)
        self.addToolBar(Qt.LeftToolBarArea, bar)
        self._tool_group = QActionGroup(self)
        for tool, glyph, label, shortcut in TOOLS:
            act = QAction(icons.icon(glyph), label, self)
            act.setCheckable(True)
            act.setShortcut(shortcut)
            act.setToolTip(f"{label} ({shortcut})")
            act.triggered.connect(lambda _, t=tool: self._set_tool(t))
            self._tool_group.addAction(act)
            bar.addAction(act)
        self._tool_group.actions()[0].setChecked(True)
        bar.addSeparator()
        for tool, glyph, label, shortcut in MEASURE_TOOLS:
            act = QAction(icons.icon(glyph), label, self)
            act.setCheckable(True)
            act.setShortcut(shortcut)
            act.setToolTip(f"{label} ({shortcut})")
            act.triggered.connect(lambda _, t=tool: self._set_tool(t))
            self._tool_group.addAction(act)
            bar.addAction(act)
        bar.addSeparator()
        for prim in PRIMITIVES:
            spec = NODE_TYPES[prim]
            bar.addAction(icons.icon(spec["icon"]), spec["label"],
                          lambda _=False, t=prim: self._add_primitive(t))

    def _build_options_bar(self):
        bar = QToolBar("Options")
        bar.setIconSize(ICON_SIZE)
        bar.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, bar)

        bar.addAction(icons.icon("mdi.file-outline"), "New",
                      self.new_document)
        bar.addAction(icons.icon("mdi.folder-open-outline"), "Open",
                      self.open_file)
        bar.addAction(icons.icon("mdi.content-save-outline"), "Save",
                      self.save_file)
        bar.addSeparator()

        undo_act = self.model.undo_stack.createUndoAction(self)
        undo_act.setIcon(icons.icon("mdi.undo"))
        undo_act.setText("Undo")
        undo_act.setToolTip("Undo (Ctrl+Z)")
        bar.addAction(undo_act)
        redo_act = self.model.undo_stack.createRedoAction(self)
        redo_act.setIcon(icons.icon("mdi.redo"))
        redo_act.setText("Redo")
        redo_act.setToolTip("Redo (Ctrl+Y)")
        bar.addAction(redo_act)
        bar.addSeparator()

        for op in OPERATIONS:
            spec = NODE_TYPES[op]
            bar.addAction(icons.icon(spec["icon"]), spec["label"],
                          lambda _=False, o=op: self._apply_operation(o))
        bar.addSeparator()

        self._grid_act = QAction(icons.icon("mdi.grid"), "Grid", self)
        self._grid_act.setCheckable(True)
        self._grid_act.setChecked(self.scene.show_grid)
        self._grid_act.setToolTip("Show grid (Ctrl+')")
        self._grid_act.setShortcut("Ctrl+'")
        self._grid_act.toggled.connect(self._set_show_grid)
        bar.addAction(self._grid_act)

        self._snap_act = QAction(icons.icon("mdi.magnet"), "Snap", self)
        self._snap_act.setCheckable(True)
        self._snap_act.setChecked(self.scene.snap_enabled)
        self._snap_act.setToolTip("Snap to grid (Ctrl+Shift+')")
        self._snap_act.setShortcut("Ctrl+Shift+'")
        self._snap_act.toggled.connect(self._set_snap)
        bar.addAction(self._snap_act)

        bar.addWidget(QLabel(" Grid "))
        self._grid_spin = QDoubleSpinBox()
        self._grid_spin.setDecimals(2)                  # down to 0.01 mm
        self._grid_spin.setRange(0.01, 1000.0)
        self._grid_spin.setSingleStep(0.5)
        # step in proportion to the value (0.6, 0.7… near 0.5; 6, 7…
        # near 5) where the Qt build supports it
        self._grid_spin.setStepType(
            QAbstractSpinBox.AdaptiveDecimalStepType)
        self._grid_spin.setSuffix(" mm")
        self._grid_spin.setValue(self.scene.grid_size)
        self._grid_spin.valueChanged.connect(self._set_grid_size)
        bar.addWidget(self._grid_spin)
        bar.addSeparator()

        bar.addWidget(QLabel(" Plane "))
        self._plane_combo = QComboBox()
        self._plane_combo.addItems(list(PLANES))
        self._plane_combo.setToolTip(
            "Assembly view plane — drag part outlines to position "
            "them along the chosen axes")
        self._plane_combo.currentTextChanged.connect(self._set_plane)
        bar.addWidget(self._plane_combo)
        bar.addSeparator()

        bar.addAction(icons.icon("mdi.fit-to-page-outline"),
                      "Fit sketch (Ctrl+Shift+F)",
                      self.view2d.fit_content)

        bar.addAction(icons.icon("mdi.play-outline"), "Render (F5)",
                      self._render_now).setShortcut("F5")
        bar.addAction(icons.icon("mdi.arrow-expand-all"), "Fit 3D",
                      self.view3d.fit)
        bar.addSeparator()
        chat_btn = QAction(icons.icon("mdi.robot-outline"),
                           "Assistant (Ctrl+/)", self)
        chat_btn.triggered.connect(
            lambda: self._chat_dock.setVisible(
                not self._chat_dock.isVisible()))
        bar.addAction(chat_btn)

    def _build_menus(self):
        m = self.menuBar()

        file_menu = m.addMenu("&File")
        file_menu.addAction("&New", self.new_document, "Ctrl+N")
        file_menu.addAction("New &Window", self.new_window,
                            "Ctrl+Shift+N")
        file_menu.addAction("&Open...", self.open_file, "Ctrl+O")
        self.recent_menu = file_menu.addMenu("Open &Recent")
        self.recent_menu.aboutToShow.connect(self._rebuild_recent_menu)
        self._rebuild_recent_menu()
        file_menu.addAction("&Save", self.save_file, "Ctrl+S")
        file_menu.addAction("Save &As...", self.save_file_as,
                            "Ctrl+Shift+S")
        file_menu.addAction(icons.icon("mdi.folder-eye-outline"),
                            "Show in File E&xplorer",
                            self._show_in_explorer)
        file_menu.addSeparator()
        file_menu.addAction("&Import OpenSCAD...", self.import_scad,
                            "Ctrl+I")
        file_menu.addAction("Import &Mesh (STL/OBJ/OFF/3MF)...",
                            self.import_stl, "Ctrl+Shift+I")
        file_menu.addSeparator()
        file_menu.addAction("Export Open&SCAD...", self.export_scad,
                            "Ctrl+E")
        file_menu.addAction("Export S&TL...", self.export_stl,
                            "Ctrl+Shift+E")
        file_menu.addSeparator()
        file_menu.addAction("E&xit", self.close, "Ctrl+Q")

        edit_menu = m.addMenu("&Edit")
        undo_act = self.model.undo_stack.createUndoAction(self, "&Undo")
        undo_act.setIcon(icons.icon("mdi.undo"))
        undo_act.setShortcut("Ctrl+Z")
        edit_menu.addAction(undo_act)
        redo_act = self.model.undo_stack.createRedoAction(self, "&Redo")
        redo_act.setIcon(icons.icon("mdi.redo"))
        redo_act.setShortcuts(["Ctrl+Y", "Ctrl+Shift+Z"])
        edit_menu.addAction(redo_act)
        edit_menu.addSeparator()
        edit_menu.addAction(icons.icon("mdi.content-cut"),
                            "Cu&t\tCtrl+X",
                            self.builder.tree.cut_selection)
        edit_menu.addAction(icons.icon("mdi.content-copy"),
                            "&Copy\tCtrl+C",
                            self.builder.tree.copy_selection)
        edit_menu.addAction(icons.icon("mdi.content-paste"),
                            "&Paste\tCtrl+V",
                            self.builder.tree.paste_clipboard)
        edit_menu.addSeparator()
        edit_menu.addAction("Move &Up\tCtrl+Up",
                            lambda: self.builder.tree.shift_selection(-1))
        edit_menu.addAction("Move Dow&n\tCtrl+Down",
                            lambda: self.builder.tree.shift_selection(1))
        edit_menu.addSeparator()
        edit_menu.addAction("&Delete", self._delete_selection, "Delete")
        edit_menu.addAction("D&uplicate", self._duplicate_selection,
                            "Ctrl+D")
        edit_menu.addSeparator()
        edit_menu.addAction("&Group", lambda: self._apply_operation(
            "union"), "Ctrl+G")
        edit_menu.addAction("&Ungroup", self._ungroup_selection,
                            "Ctrl+Shift+G")
        edit_menu.addSeparator()
        edit_menu.addAction("&Locate OpenSCAD...", self._locate_openscad)

        insert_menu = m.addMenu("&Insert")
        insert_menu.addAction(icons.icon("mdi.package-variant-closed"),
                              "New &Object", self._new_object,
                              "Ctrl+Alt+N")
        insert_menu.addSeparator()
        insert_menu.addAction(icons.icon("mdi.toy-brick-outline"),
                              "&Part Library...", self.open_library,
                              "Ctrl+L")
        insert_menu.addSeparator()
        for control in ("for_loop", "while_loop", "if_else", "assign",
                        "stl_import", "scad_raw"):
            spec = NODE_TYPES[control]
            insert_menu.addAction(
                icons.icon(spec["icon"]), spec["label"],
                lambda _=False, t=control: self._add_primitive(t))

        self._build_library_menu(m)
        self._build_examples_menu(m)

        view_menu = m.addMenu("&View")
        chat_act = self._chat_dock.toggleViewAction()
        chat_act.setText("&Assistant")
        chat_act.setIcon(icons.icon("mdi.robot-outline"))
        chat_act.setShortcut("Ctrl+/")
        view_menu.addAction(chat_act)
        view_menu.addSeparator()
        view_menu.addAction(self._grid_act)
        view_menu.addAction(self._snap_act)
        from PyQt5.QtCore import QSettings
        show_dims = QSettings("Kherve", "KherveCAD").value(
            "show_dims", True, type=bool)
        self.scene.show_dims = show_dims
        self._dims_act = QAction(icons.icon("mdi.ruler-square"),
                                 "Dimensions on selection", self)
        self._dims_act.setCheckable(True)
        self._dims_act.setChecked(show_dims)
        self._dims_act.setToolTip("Show the size of selected shapes")
        self._dims_act.toggled.connect(self._set_show_dims)
        view_menu.addAction(self._dims_act)
        view_menu.addAction("Clear &Dimensions",
                            self.model.clear_dimensions)
        view_menu.addSeparator()
        view_menu.addAction("Zoom &In", lambda: self.view2d.zoom(1.25),
                            "Ctrl++")
        view_menu.addAction("Zoom &Out",
                            lambda: self.view2d.zoom(1 / 1.25), "Ctrl+-")
        view_menu.addAction("&Reset 2D Zoom", self.view2d.zoom_reset,
                            "Ctrl+0")
        view_menu.addAction("Fit &Sketch", self.view2d.fit_content,
                            "Ctrl+Shift+F")
        view_menu.addAction("Zoom to Se&lection",
                            self.view2d.zoom_selection)
        view_menu.addAction("&Fit 3D View", self.view3d.fit, "Ctrl+F")
        views_menu = view_menu.addMenu("3D &Camera")
        for name in self.view3d.VIEWS:
            views_menu.addAction(
                name, lambda _=False, n=name: self.view3d.set_view(n))
        view_menu.addSeparator()
        from .view3d import BACKGROUNDS, RENDER_STYLES
        style_menu = view_menu.addMenu("3D &Render Style")
        style_group = QActionGroup(self)
        for name in RENDER_STYLES:
            act = QAction(name, self, checkable=True)
            act.setChecked(name == self.view3d.style)
            act.triggered.connect(
                lambda _, n=name: self.view3d.set_style(n))
            style_group.addAction(act)
            style_menu.addAction(act)
        bg_menu = view_menu.addMenu("3D &Background")
        bg_group = QActionGroup(self)
        for name in BACKGROUNDS:
            act = QAction(name, self, checkable=True)
            act.setChecked(name == self.view3d.background)
            act.triggered.connect(
                lambda _, n=name: self.view3d.set_background(n))
            bg_group.addAction(act)
            bg_menu.addAction(act)
        view_menu.addSeparator()
        theme_menu = view_menu.addMenu("&Theme")
        theme_group = QActionGroup(self)
        for name in THEMES:
            act = QAction(name, self, checkable=True)
            act.setChecked(name == current_theme())
            act.triggered.connect(
                lambda _, n=name: (apply_style(QApplication.instance(),
                                               n),
                                   self.builder.refresh_theme()))
            theme_group.addAction(act)
            theme_menu.addAction(act)

        git_menu = m.addMenu("&Git")
        git_menu.addAction(icons.icon("mdi.source-commit"),
                           "&Commit...", self._git_commit, "Ctrl+K")
        git_menu.addAction(icons.icon("mdi.cloud-upload-outline"),
                           "&Push", self._git_push)
        git_menu.addAction(icons.icon("mdi.cloud-download-outline"),
                           "P&ull", self._git_pull)
        git_menu.addSeparator()
        git_menu.addAction(icons.icon("mdi.github"),
                           "Connect to Git&Hub / GitLab...",
                           self._git_connect)

        help_menu = m.addMenu("&Help")
        help_menu.addAction("&User Guide", self._user_guide, "F1")
        help_menu.addSeparator()
        help_menu.addAction("&About", self._about)

    def _build_library_menu(self, menubar):
        """A Library menu that inserts a part at its default size in one
        click — the same catalogue as the Part Library dialog, grouped by
        category, without opening the dialog."""
        from .library import PARTS
        menu = menubar.addMenu("&Library")
        menu.addAction(icons.icon("mdi.toy-brick-outline"),
                       "Part Library (customise)...", self.open_library,
                       "Ctrl+L")
        menu.addSeparator()
        submenus = {}
        for part_id, spec in PARTS.items():
            cat = spec.get("category", "Other")
            sub = submenus.get(cat)
            if sub is None:
                sub = submenus[cat] = menu.addMenu(cat)
            sub.addAction(
                spec["label"],
                lambda _=False, pid=part_id: self._insert_library_part(pid))

    def _build_examples_menu(self, menubar):
        """An Examples menu of complete demo models; picking one replaces
        the document (Ctrl+Z to get the old one back)."""
        from .examples import EXAMPLES
        menu = menubar.addMenu("&Examples")
        submenus = {}
        for label, cat, build in EXAMPLES:
            sub = submenus.get(cat)
            if sub is None:
                sub = submenus[cat] = menu.addMenu(cat)
            sub.addAction(
                label,
                lambda _=False, b=build: self._load_example(b))

    def _insert_library_part(self, part_id):
        from .library import default_part
        try:
            node = default_part(part_id)
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME,
                                f"Could not build the part:\n{exc}")
            return
        self.model.root.add(node)
        self.model.structure_changed.emit()
        self.builder.tree.select_nodes([node])
        self.view3d.fit()

    def _load_example(self, build):
        if not self._confirm_discard():
            return
        from .examples import load_example
        load_example(self.model, build)
        self._path = None
        self._dirty = False
        self._fitted = False
        self.view3d.fit()
        self._update_title()

    def _build_status_bar(self):
        self._cursor_label = QLabel("x: 0.0 mm  y: 0.0 mm")
        self.statusBar().addWidget(self._cursor_label)
        self._measure_label = QLabel("")
        self.statusBar().addWidget(self._measure_label)
        self._dims_label = QLabel("")          # selected object's size
        self.statusBar().addWidget(self._dims_label)
        self._file_label = QLabel()            # current document path
        self.statusBar().addPermanentWidget(self._file_label)
        self._zoom_label = QLabel(
            f"1 mm = {self.view2d.px_per_mm():.2f} px")
        self.statusBar().addPermanentWidget(self._zoom_label)
        self._engine_label = QLabel()
        self.statusBar().addPermanentWidget(self._engine_label)
        self._refresh_engine_label()
        self._update_title()                   # fills the file label

    def _cursor_moved(self, p):
        _axes, (kx, ky) = PLANES[self.scene.plane]
        self._cursor_label.setText(
            f"{kx}: {p.x():.1f} mm  {ky}: {p.y():.1f} mm")

    def _on_plane_auto_changed(self, plane):
        """The 2D view jumped planes to expose a primitive's edit handles;
        reflect it in the Plane combo without re-triggering a rebuild."""
        self._plane_combo.blockSignals(True)
        self._plane_combo.setCurrentText(plane)
        self._plane_combo.blockSignals(False)

    def _set_plane(self, plane):
        self.scene.set_plane(plane)
        self.view2d.viewport().update()

    def _refresh_engine_label(self, busy=False):
        if self.engine.available:
            state = "rendering…" if busy else "ready"
            self._engine_label.setText(f"Engine: OpenSCAD ({state})")
        else:
            self._engine_label.setText(
                "Engine: built-in preview — OpenSCAD not found "
                "(Edit > Locate OpenSCAD)")

    # ---------------------------------------------------------- editing
    def _set_tool(self, tool):
        self.view2d.set_tool(tool)

    def _add_primitive(self, type: str):
        # while the Object tab edits an Object, new geometry lands
        # inside it — matching what both viewers show
        parent = self.builder.isolated_component()
        node = self.model.add_node(type, parent=parent)
        tree = self.builder.tree if parent is None \
            else self.builder.object_tab.tree
        tree.select_nodes([node])

    def _new_object(self):
        """Insert > New Object: create an empty Object and open it for
        editing in the Object tab."""
        self.builder.open_component(self.model.new_component())

    def _apply_operation(self, op: str):
        nodes = self.builder.tree.selected_nodes()
        if not nodes:
            if op in ("for_loop", "while_loop", "if_else", "union"):
                self._add_primitive(op)       # empty, fill it after
                return
            self.statusBar().showMessage(
                "Select objects in the tree first.", 3000)
            return
        wrapper = self.model.wrap_nodes(nodes, op)
        if wrapper is not None:
            self.builder.tree.select_nodes([wrapper])

    def _ungroup_selection(self):
        for node in self.builder.tree.selected_nodes():
            self.model.ungroup(node)

    def _delete_selection(self):
        for node in self.builder.tree.selected_nodes():
            self.model.remove_node(node)

    def _duplicate_selection(self):
        for node in self.builder.tree.selected_nodes():
            self.model.duplicate(node)

    def _set_show_grid(self, show):
        self.scene.show_grid = show
        self.view2d.viewport().update()

    def _set_show_dims(self, show):
        self.scene.show_dims = show
        self.view2d.viewport().update()
        from PyQt5.QtCore import QSettings
        QSettings("Kherve", "KherveCAD").setValue("show_dims", show)

    def _set_snap(self, snap):
        self.scene.snap_enabled = snap

    def _set_grid_size(self, size):
        self.scene.grid_size = float(size)
        self.view2d.viewport().update()

    # -------------------------------------------------- selection sync
    def _tree_selected(self, nodes):
        if self._syncing:
            return
        self._syncing = True
        self.properties.set_node(nodes[0] if len(nodes) == 1 else None)
        self.scene.select_nodes(nodes)
        self.builder.highlight_nodes(nodes)
        self._sync_highlight(nodes)
        self._syncing = False

    def _masters_selected(self, nodes):
        """A master picked in the Masters tab drives the Properties panel,
        the code highlight, and both viewers — its projected outline in
        2D and its glow in 3D. A master lives in the non-rendering store,
        so `mesh.selected_world_tris` falls back to tessellating its own
        subtree directly (see mesh.py)."""
        if self._syncing:
            return
        self._syncing = True
        self.builder.tree.clearSelection()   # one tree selected at a time
        self.properties.set_node(nodes[0] if len(nodes) == 1 else None)
        self.builder.highlight_nodes(nodes)
        self._sync_highlight(nodes)
        self._syncing = False

    def _scene_selected(self, nodes):
        if self._syncing:
            return
        self._syncing = True
        self.builder.tree.select_nodes(nodes)
        self.properties.set_node(nodes[0] if len(nodes) == 1 else None)
        self.builder.highlight_nodes(nodes)
        self._sync_highlight(nodes)
        self._syncing = False

    def _sync_highlight(self, nodes):
        """Draw the selected object's geometry highlighted in both
        the 2D (projected outline) and 3D (glowing faces) views."""
        self._selected_ids = {n.id for n in nodes}
        self.scene.set_highlight(nodes)
        # zoom the 2D view to the selected object (a part silhouette or
        # an edited profile) so it is framed and centred, not clipped
        rect = self.scene.isolated_bounds()
        if rect is not None:
            self.view2d.frame_rect(rect)
        tris = (mesh.selected_world_tris(self.model.root,
                                         self._selected_ids,
                                         fn=self.model.effective_fn())
                if self._selected_ids else [])
        self.view3d.set_highlight_mesh(tris)
        self._show_dimensions(tris)

    def _show_dimensions(self, tris):
        """Status-bar read-out of the selected object's overall size
        (its world bounding-box extents in X, Y and Z)."""
        if not tris:
            self._dims_label.setText("")
            return
        xs = [v[0] for t in tris for v in t]
        ys = [v[1] for t in tris for v in t]
        zs = [v[2] for t in tris for v in t]
        dx, dy, dz = (max(xs) - min(xs), max(ys) - min(ys),
                      max(zs) - min(zs))
        self._dims_label.setText(
            f"Size  X {dx:.1f} · Y {dy:.1f} · Z {dz:.1f} mm")

    def _node_created(self, node):
        tree = self.builder.tree \
            if self.builder.isolated_component() is None \
            else self.builder.object_tab.tree
        tree.select_nodes([node])

    # ---------------------------------------------------- 3D pipeline
    def _model_edited(self):
        self._dirty = True
        self._update_title()
        self._refresh_preview()

    def _isolation_changed(self):
        """The Object tab took or released the viewers: re-render both
        for the (un)isolated scope."""
        self.scene.rebuild()
        self._refresh_preview()

    def _render_scope(self):
        """(root node, scad code callable) for the current view — the
        active Object while the Object tab is current, else the whole
        document."""
        iso = self.builder.isolated_component()
        if iso is not None:
            return iso, (lambda: self.model.subtree_scad(iso))
        return self.model.root, self.model.to_scad

    def _refresh_preview(self):
        fn = self.model.effective_fn()
        root, scad = self._render_scope()
        colored = mesh.tessellate_colored(root, fn=fn)
        tris = [t for t, _c in colored]
        colors = [c for _t, c in colored]
        has_colors = any(c is not None for c in colors)
        label = "built-in preview"
        if root is not self.model.root:
            label += f" — Object: {root.name}"
        if mesh.uses_booleans(root):
            label += (" (booleans approximated)"
                      if not self.engine.available else "")
        self.view3d.set_mesh(tris, label,
                             colors if has_colors else None)
        selected = getattr(self, "_selected_ids", set())
        if selected:
            self.view3d.set_highlight_mesh(
                mesh.selected_world_tris(self.model.root, selected, fn=fn))
        if tris and not self._fitted and not self.view3d.user_moved:
            self.view3d.fit()
            self._fitted = True
        # An exact render is a single STL with no colour, so it can only
        # carry one overall tint. Detect whether the *whole* model is one
        # colour (every face the same, none left uncoloured) — only then
        # may an exact render stand in for the built-in colour preview.
        seen = set(colors)
        uniform = len(seen) == 1 and None not in seen
        self._engine_color = next(iter(seen)) if uniform else None
        if self.engine.available and self.model.root.children:
            # No colours, or one overall colour: run the exact render (and
            # tint it if uniform) so booleans cut real holes. A model with
            # several colours keeps the built-in per-part colour preview,
            # since an STL cannot carry them — tinting it all one colour
            # would wrongly paint every part the same.
            if not has_colors or uniform:
                self.engine.request_render(scad())

    def _render_now(self):
        if self.engine.available:
            self.engine.request_render(self._render_scope()[1]())
            self.statusBar().showMessage("Rendering with OpenSCAD…",
                                         2000)
        else:
            self._refresh_preview()
            self.statusBar().showMessage(
                "OpenSCAD not found — using built-in preview.", 4000)

    def _engine_mesh(self, tris):
        color = getattr(self, "_engine_color", None)
        self.view3d.set_mesh(tris, "OpenSCAD",
                             [color] * len(tris) if color else None)
        self.builder.set_engine_errors({})

    def _engine_failed(self, stderr):
        """Map OpenSCAD compiler errors back to the offending nodes
        (they turn red in the tree and the code tab)."""
        import re
        errors = {}
        for line in stderr.splitlines():
            if "ERROR" not in line and "WARNING" not in line.upper():
                continue
            match = re.search(r"line (\d+)", line)
            if match is None:
                continue
            node = self.model.node_at_line(int(match.group(1)) - 1)
            if node is not None and node.parent is not None:
                errors.setdefault(
                    node.id,
                    "OpenSCAD: " + line.split("ERROR:")[-1]
                    .split("WARNING:")[-1].strip())
        self.builder.set_engine_errors(errors)
        first = next((l for l in stderr.splitlines() if "ERROR" in l),
                     stderr.splitlines()[-1] if stderr else "failed")
        self.statusBar().showMessage(f"OpenSCAD: {first}", 6000)

    def _engine_busy(self, busy):
        self._refresh_engine_label(busy)

    def _locate_openscad(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Locate the OpenSCAD executable")
        if not path:
            return
        set_openscad_path(path)
        self.engine.refresh_binary()
        self._refresh_engine_label()
        self._refresh_preview()

    # ---------------------------------------------------- recent files
    _MAX_RECENT = 12

    def _recent_files(self) -> list:
        from PyQt5.QtCore import QSettings
        val = QSettings("Kherve", "KherveCAD").value("recent_files", [])
        if isinstance(val, str):            # a one-item list comes back as str
            val = [val]
        return [str(x) for x in (val or [])]

    def _set_recent_files(self, files):
        from PyQt5.QtCore import QSettings
        QSettings("Kherve", "KherveCAD").setValue("recent_files", files)

    def _add_recent(self, path):
        if not path:
            return
        path = str(Path(path))
        files = [f for f in self._recent_files() if f != path]
        files.insert(0, path)
        del files[self._MAX_RECENT:]
        self._set_recent_files(files)

    def _forget_recent(self, path):
        path = str(Path(path))
        self._set_recent_files(
            [f for f in self._recent_files() if str(Path(f)) != path])

    def _short_path(self, path) -> str:
        p = Path(path)
        parent = str(p.parent)
        home = str(Path.home())
        if parent.startswith(home):
            parent = "~" + parent[len(home):]
        parent = parent.replace("\\", "/")
        if len(parent) > 40:
            parent = parent[:18] + "…" + parent[-20:]
        return f"{p.name}    {parent}"

    def _rebuild_recent_menu(self):
        self.recent_menu.clear()
        files = self._recent_files()
        if not files:
            none = self.recent_menu.addAction("(no recent files)")
            none.setEnabled(False)
            return
        for i, path in enumerate(files):
            accel = f"&{i + 1}" if i < 9 else f"{i + 1}"
            shown = self._short_path(path).replace("&", "&&")
            act = self.recent_menu.addAction(f"{accel}  {shown}")
            act.setToolTip(path)
            act.setEnabled(Path(path).exists())
            act.triggered.connect(
                lambda _=False, p=path: self._open_path(p))
        self.recent_menu.addSeparator()
        self.recent_menu.addAction("&Clear Recent Files",
                                   self._clear_recent)

    def _clear_recent(self):
        self._set_recent_files([])
        self._rebuild_recent_menu()

    # ------------------------------------------------------------ files
    def new_document(self):
        if not self._confirm_discard():
            return
        self.model.clear()
        self._path = None
        self._dirty = False
        self._fitted = False
        self.view3d.user_moved = False        # fresh document, frame it
        self._update_title()

    def new_window(self):
        """Open a second, independent KherveCAD window (empty document)."""
        win = MainWindow()
        MainWindow._windows.append(win)       # keep it alive
        # offset it a little so it doesn't sit exactly on this one
        win.move(self.x() + 40, self.y() + 40)
        win.show()
        win.raise_()
        win.activateWindow()

    def open_file(self):
        recent = self._recent_files()
        start = str(Path(recent[0]).parent) if recent else ""
        path, _ = QFileDialog.getOpenFileName(
            self, "Open", start,
            "All supported (*.kcad *.scad *.stl *.obj *.off *.3mf);;"
            "KherveCAD document (*.kcad);;OpenSCAD program (*.scad);;"
            "Mesh (*.stl *.obj *.off *.3mf)")
        if not path:
            return
        self.open_any(path)

    def open_any(self, path):
        """Open or import a file by extension — .kcad opens, .scad
        imports (as objects, or a raw block), and mesh files
        (.stl/.obj/.off/.3mf) import as a mesh. Used by File > Open and
        by drag-and-drop."""
        from .engine import MESH_EXTS
        ext = Path(path).suffix.lower()
        if ext == ".kcad":
            self._open_path(path)
        elif ext == ".scad":
            if not self._confirm_discard():
                return
            self._import_scad_path(path)
        elif ext in MESH_EXTS:
            self._import_mesh_path(path)
        else:
            QMessageBox.warning(
                self, APP_NAME,
                f"KherveCAD can open .kcad, .scad and mesh files "
                f"(.stl/.obj/.off/.3mf) — not {ext or 'this type'}.")

    # ------------------------------------------------------ drag & drop
    _DROP_EXTS = (".kcad", ".scad", ".stl", ".obj", ".off", ".3mf")

    def _dropped_file(self, event):
        """The first supported local file in a file drag, or None."""
        md = event.mimeData()
        if not md.hasUrls():
            return None
        for url in md.urls():
            p = url.toLocalFile()
            if p and p.lower().endswith(self._DROP_EXTS):
                return p
        return None

    def dragEnterEvent(self, event):
        if self._dropped_file(event):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if self._dropped_file(event):
            event.acceptProposedAction()

    def dropEvent(self, event):
        path = self._dropped_file(event)
        if path:
            event.acceptProposedAction()
            self.open_any(path)

    def _open_path(self, path, confirm=True):
        """Load *path* into the model (shared by Open... and Recent)."""
        if confirm and not self._confirm_discard():
            return
        if not Path(path).exists():
            QMessageBox.warning(
                self, APP_NAME, f"File no longer exists:\n{path}")
            self._forget_recent(path)
            return
        try:
            document.load_kcad(self.model, path)
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME, f"Could not open:\n{exc}")
            return
        self._path = path
        self._dirty = False
        self._fitted = False
        self.view3d.user_moved = False        # fresh document, frame it
        self._add_recent(path)
        self.view3d.fit()
        self._update_title()

    def save_file(self):
        if self._path is None:
            self.save_file_as()
            return
        try:
            document.save_kcad(self.model, self._path)
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME, f"Could not save:\n{exc}")
            return
        self._dirty = False
        self._add_recent(self._path)
        self._update_title()

    def save_file_as(self):
        recent = self._recent_files()
        start = str(Path(recent[0]).parent) if recent else ""
        path, _ = QFileDialog.getSaveFileName(
            self, "Save As", start, "KherveCAD document (*.kcad)")
        if not path:
            return
        if not path.lower().endswith(".kcad"):
            path += ".kcad"
        self._path = path
        self.save_file()

    def _show_in_explorer(self):
        """Reveal the current document in the OS file manager."""
        if not self._path:
            QMessageBox.information(
                self, APP_NAME,
                "Save the document first — there is no file to show yet.")
            return
        import subprocess
        import sys
        path = Path(self._path)
        try:
            if sys.platform == "win32":
                subprocess.Popen(["explorer", "/select,", str(path)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path.parent)])
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME,
                                f"Could not open the file manager:\n{exc}")

    # -------------------------------------------------------------- git
    def _git_ready(self):
        """The document's repo dir, after ensuring it is saved and that
        pygit2 is available. Returns the Path, or None (with a message)
        when Git can't proceed."""
        from . import git_backend
        if not git_backend.is_available():
            QMessageBox.warning(
                self, APP_NAME,
                "Git support needs the 'pygit2' package, which isn't "
                "installed.\n\n    pip install pygit2")
            return None
        if self._path is None:
            self.save_file_as()
            if self._path is None:
                return None
        return Path(self._path).parent

    def _git_commit(self):
        """Save, then snapshot the current document as a git commit."""
        repo_dir = self._git_ready()
        if repo_dir is None:
            return
        self.save_file()
        from PyQt5.QtWidgets import QInputDialog
        from . import git_backend
        stem = Path(self._path).stem
        message, ok = QInputDialog.getText(
            self, "Commit", "Commit message:",
            text=f"Update {Path(self._path).name}")
        if not ok or not message.strip():
            return
        oid = git_backend.commit_all(repo_dir, message.strip(),
                                     file_stem=stem)
        if oid:
            self.statusBar().showMessage(
                f"Committed {oid[:8]} on "
                f"{git_backend.current_branch(repo_dir) or '?'}", 5000)
        else:
            self.statusBar().showMessage(
                "Nothing to commit — no changes since the last commit.",
                5000)

    def _git_push(self):
        repo_dir = self._git_ready()
        if repo_dir is None:
            return
        from . import git_backend
        if not git_backend.get_remotes(repo_dir):
            if QMessageBox.question(
                    self, APP_NAME,
                    "No remote is configured. Connect to GitHub / GitLab "
                    "now?") == QMessageBox.Yes:
                self._git_connect()
            return
        branch = git_backend.current_branch(repo_dir) or "main"
        ok, message = git_backend.push(repo_dir, "origin", branch)
        (QMessageBox.information if ok
         else QMessageBox.warning)(self, APP_NAME, message)

    def _git_pull(self):
        repo_dir = self._git_ready()
        if repo_dir is None:
            return
        from . import git_backend
        ok, message = git_backend.pull(repo_dir, "origin")
        (QMessageBox.information if ok
         else QMessageBox.warning)(self, APP_NAME, message)

    def _git_connect(self):
        repo_dir = self._git_ready()
        if repo_dir is None:
            return
        from PyQt5.QtWidgets import QInputDialog
        from . import git_backend
        current = dict(git_backend.get_remotes(repo_dir)).get("origin", "")
        url, ok = QInputDialog.getText(
            self, "Connect to GitHub / GitLab",
            "Remote URL for 'origin'\n"
            "(e.g. https://github.com/you/repo.git):", text=current)
        if not ok or not url.strip():
            return
        if git_backend.set_remote(repo_dir, "origin", url.strip()):
            self.statusBar().showMessage(
                "Remote 'origin' configured — use Git > Push.", 5000)
        else:
            QMessageBox.warning(self, APP_NAME,
                                "Could not set the remote.")

    def open_library(self):
        """Non-modal: the library stays open while you keep editing."""
        if getattr(self, "_library_dialog", None) is None:
            from .library import PartLibraryDialog
            self._library_dialog = PartLibraryDialog(self.model, self)
            self._library_dialog.part_inserted.connect(
                self._part_inserted)
        self._library_dialog.show()
        self._library_dialog.raise_()
        self._library_dialog.activateWindow()

    def _part_inserted(self, node):
        self.builder.tree.select_nodes([node])
        if not self.view3d.user_moved:        # don't jump a view you set
            self.view3d.fit()

    def import_scad(self):
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Import OpenSCAD", "", "OpenSCAD program (*.scad)")
        if not path:
            return
        self._import_scad_path(path)

    def _import_scad_path(self, path):
        from . import mesh, scadparse
        try:
            warnings = scadparse.import_scad(self.model, path)
        except Exception as exc:
            # KherveCAD couldn't parse it into objects at all (e.g. it
            # uses vector .x/.y, ranges, custom modules). Offer the raw
            # OpenSCAD block so the file still opens and renders.
            reason = (f"KherveCAD couldn't read this file as editable "
                      f"objects:\n{exc}")
            if not self._offer_scad_raw(path, reason):
                QMessageBox.warning(self, APP_NAME,
                                    f"Could not import:\n{exc}")
            return
        # Parsed, but a file built on custom modules/functions comes in
        # empty — offer the raw block for that case too.
        empty = not mesh.tessellate(self.model.root,
                                    fn=self.model.effective_fn())
        advanced = any("not supported" in w or "unsupported" in w
                       for w in warnings)
        if empty and advanced:
            reason = ("This file is built from custom OpenSCAD "
                      "modules/functions that KherveCAD can't turn into "
                      "editable objects, so the object tree is empty.")
            if self._offer_scad_raw(path, reason):
                return
        self._path = None                     # imported: save as .kcad
        self._dirty = True
        self._fitted = False
        self.view3d.user_moved = False        # fresh document, frame it
        self._add_recent(path)                # re-openable from Recent
        self.view3d.fit()
        self._update_title()
        if warnings:
            QMessageBox.information(
                self, APP_NAME,
                "Imported with limitations:\n- "
                + "\n- ".join(warnings[:12])
                + ("\n…" if len(warnings) > 12 else ""))

    def _offer_scad_raw(self, path, reason):
        """Ask whether to load *path* as a raw OpenSCAD block; do it and
        return True if the user accepts."""
        note = "" if self.engine.available else (
            "\n\n(OpenSCAD isn't detected — set it via Edit > Locate "
            "OpenSCAD to render it.)")
        answer = QMessageBox.question(
            self, APP_NAME,
            reason + "\n\nLoad the whole file as a raw OpenSCAD block? "
            "It renders through the OpenSCAD engine and is editable as "
            "text in the Code tab (not as objects)." + note,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if answer == QMessageBox.Yes:
            self._load_scad_raw(path)
            return True
        return False

    def _load_scad_raw(self, path):
        """Replace the document with a single raw-OpenSCAD node holding
        the file's text — for programs KherveCAD can't model as a tree."""
        from .model import CadNode
        text = Path(path).read_text(encoding="utf-8")
        root = CadNode("root")
        root.add(CadNode("scad_raw", Path(path).stem, dict(code=text)))
        self.model.root = root
        self.model.structure_changed.emit()
        self._path = None
        self._dirty = True
        self._fitted = False
        self.view3d.user_moved = False
        self._add_recent(path)
        self._update_title()
        if self.engine.available:
            self._render_now()

    def import_stl(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import mesh", "",
            "Mesh (*.stl *.obj *.off *.3mf);;STL (*.stl);;"
            "Wavefront OBJ (*.obj);;OFF (*.off);;3MF (*.3mf)")
        if not path:
            return
        self._import_mesh_path(path)

    def _import_mesh_path(self, path):
        # OpenSCAD's import() renders STL/OFF/3MF but not OBJ, so convert
        # an OBJ to a sibling STL (from the same triangles the preview
        # uses) and point the node at that, so the exact render works too.
        use_path = path
        if Path(path).suffix.lower() == ".obj":
            from .engine import parse_mesh, write_stl
            tris = parse_mesh(path)
            if tris:
                stl_path = Path(path).with_name(
                    Path(path).stem + "_from_obj.stl")
                try:
                    write_stl(tris, str(stl_path), Path(path).stem)
                    use_path = str(stl_path)
                    self.statusBar().showMessage(
                        f"Converted OBJ → {stl_path.name} for rendering",
                        6000)
                except OSError:
                    pass                     # fall back to the .obj path
        # an imported mesh arrives as one Object holding the whole
        # structure — it moves, snaps and lists as a single part
        comp = self.model.new_component(Path(path).stem)
        self.model.add_node("stl_import", dict(path=use_path),
                            parent=comp, name=f"{Path(path).stem} mesh")
        self.builder.tree.select_nodes([comp])
        if not self.view3d.user_moved:
            self.view3d.fit()

    def export_scad(self):
        suggestion = str(Path(self._path).with_suffix(".scad")) \
            if self._path else ""
        path, _ = QFileDialog.getSaveFileName(
            self, "Export OpenSCAD", suggestion,
            "OpenSCAD program (*.scad)")
        if not path:
            return
        if not path.lower().endswith(".scad"):
            path += ".scad"
        try:
            document.export_scad(self.model, path)
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME,
                                f"Could not export:\n{exc}")

    def export_stl(self):
        suggestion = str(Path(self._path).with_suffix(".stl")) \
            if self._path else ""
        path, _ = QFileDialog.getSaveFileName(
            self, "Export STL", suggestion, "STL mesh (*.stl)")
        if not path:
            return
        if not path.lower().endswith(".stl"):
            path += ".stl"
        if self.engine.available:
            error = self.engine.export_stl(self.model.to_scad(), path)
            if error:
                QMessageBox.warning(self, APP_NAME,
                                    f"OpenSCAD export failed:\n{error}")
            return
        from .engine import write_stl
        write_stl(mesh.tessellate(self.model.root), path)
        if mesh.uses_booleans(self.model.root):
            QMessageBox.information(
                self, APP_NAME,
                "Exported with the built-in tessellator: booleans are "
                "approximated. Install OpenSCAD for exact geometry.")

    # ------------------------------------------------------------- misc
    def _update_title(self):
        name = Path(self._path).name if self._path else "Untitled"
        star = "*" if self._dirty else ""
        self.setWindowTitle(f"{star}{name} — {APP_NAME} v{__version__}")
        label = getattr(self, "_file_label", None)
        if label is not None:
            if self._path:
                label.setText(f"File: {star}{self._path}")
                label.setToolTip(str(self._path))
            else:
                label.setText(f"File: {star}Untitled (not saved)")
                label.setToolTip("")

    def _confirm_discard(self) -> bool:
        if not self._dirty:
            return True
        answer = QMessageBox.question(
            self, APP_NAME, "Discard unsaved changes?",
            QMessageBox.Discard | QMessageBox.Cancel)
        return answer == QMessageBox.Discard

    def closeEvent(self, event):
        if self._confirm_discard():
            if self in MainWindow._windows:    # let a closed window GC
                MainWindow._windows.remove(self)
            event.accept()
        else:
            event.ignore()

    def _user_guide(self):
        from .userguide import show_user_guide
        show_user_guide(self)

    def _about(self):
        import sys

        from PyQt5.QtCore import PYQT_VERSION_STR, QT_VERSION_STR

        def _ver(mod):
            try:
                return __import__(mod).__version__
            except Exception:
                return "—"

        engine = getattr(self, "engine", None)
        scad_path = getattr(engine, "binary", None) or getattr(
            engine, "openscad_path", None)
        engine_line = (f"OpenSCAD engine: <b>{scad_path}</b>"
                       if scad_path else
                       "OpenSCAD not found — using the built-in preview "
                       "tessellator")

        box = QMessageBox(self)
        box.setWindowTitle(f"About {APP_NAME}")
        box.setIconPixmap(icons.app_icon().pixmap(64, 64))
        box.setTextFormat(Qt.RichText)
        box.setText(
            f"<h2 style='margin-bottom:0'>"
            f"<span style='color:#3776ab'>Kherve</span>"
            f"<span style='color:#e07b39'>CAD</span></h2>"
            f"<p style='color:gray;margin-top:2px'>version {__version__}</p>"
            f"<p>An easy-to-use CAD program with <b>OpenSCAD as the "
            f"engine</b>: the model is a tree of objects &mdash; 2D shapes, "
            f"3D primitives, extrusions, transforms and booleans &mdash; that "
            f"maps one-to-one to an OpenSCAD program.</p>"
            f"<p style='color:gray'>{engine_line}.</p>"
            f"<hr>"
            f"<p><b>Created by Gwilherm Kerherve</b><br>"
            f"Imperial College London<br>"
            f"<a href='https://github.com/gkerherve'>github.com/gkerherve</a>"
            f"</p>"
            f"<p>Part of the <b>Kherve</b> family of native scientific "
            f"apps &mdash; KherveFitting (XPS curve fitting), KherveSheet "
            f"(spreadsheets), KherveBook (notebooks), KhervePDF, KherveDOC "
            f"and KhervePaint.</p>"
            f"<hr>"
            f"<p style='color:gray'><b>Built with</b> "
            f"Python {sys.version.split()[0]}, Qt {QT_VERSION_STR}, "
            f"PyQt5 {PYQT_VERSION_STR}, qtawesome {_ver('qtawesome')}.</p>"
            f"<p>Copyright &copy; 2026 Gwilherm Kerherve — licensed under "
            f"the <a href='https://www.gnu.org/licenses/gpl-3.0.html'>"
            f"GNU GPL v3.0</a>.</p>")
        box.exec_()

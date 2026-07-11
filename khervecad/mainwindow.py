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
from PyQt5.QtWidgets import (QAction, QActionGroup, QApplication,
                             QComboBox, QDockWidget, QFileDialog,
                             QLabel, QMainWindow, QMessageBox,
                             QSpinBox, QSplitter, QToolBar)

from . import APP_NAME, __version__, document, icons, mesh
from .engine import ScadEngine, set_openscad_path
from .model import NODE_TYPES, DocumentModel
from .properties import PropertiesPanel
from .style import THEMES, apply_style, current_theme
from .treepanel import BuilderPanel
from .view2d import (CIRCLE, LINE, PLANES, POLYGON, RECT, SELECT,
                     TEXT, SketchScene, SketchView)
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

#: 3D primitives added with one click.
PRIMITIVES = ["cube", "sphere", "cylinder"]

#: operations in the horizontal toolbar (applied to the selection —
#: control-flow tools insert standalone when nothing is selected).
OPERATIONS = ["linear_extrude", "rotate_extrude", "translate", "rotate",
              "scale", "mirror", "union", "difference", "intersection",
              "for_loop", "while_loop", "if_else"]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(icons.app_icon())
        self.resize(1400, 900)

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
        left.setStretchFactor(0, 3)
        left.setStretchFactor(1, 2)

        right = QSplitter(Qt.Vertical)
        right.addWidget(self.view2d)
        right.addWidget(self.view3d)
        right.setStretchFactor(0, 3)
        right.setStretchFactor(1, 2)

        split = QSplitter(Qt.Horizontal)
        split.addWidget(left)
        split.addWidget(right)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([340, 1060])
        self.setCentralWidget(split)

        # ---- wiring
        self.builder.tree.selection_changed.connect(self._tree_selected)
        self.scene.selection_changed.connect(self._scene_selected)
        self.scene.node_created.connect(self._node_created)
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
        self._chat_dock = QDockWidget("KherveAI", self)
        self._chat_dock.setObjectName("chat_dock")
        self._chat_dock.setWidget(self.chat)
        self.addDockWidget(Qt.RightDockWidgetArea, self._chat_dock)
        self._chat_dock.hide()               # opt-in via View or Ctrl+/

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
        self._grid_spin = QSpinBox()
        self._grid_spin.setRange(1, 100)
        self._grid_spin.setSuffix(" mm")
        self._grid_spin.setValue(int(self.scene.grid_size))
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
                           "KherveAI chat (Ctrl+/)", self)
        chat_btn.triggered.connect(
            lambda: self._chat_dock.setVisible(
                not self._chat_dock.isVisible()))
        bar.addAction(chat_btn)

    def _build_menus(self):
        m = self.menuBar()

        file_menu = m.addMenu("&File")
        file_menu.addAction("&New", self.new_document, "Ctrl+N")
        file_menu.addAction("&Open...", self.open_file, "Ctrl+O")
        file_menu.addAction("&Save", self.save_file, "Ctrl+S")
        file_menu.addAction("Save &As...", self.save_file_as,
                            "Ctrl+Shift+S")
        file_menu.addSeparator()
        file_menu.addAction("&Import OpenSCAD...", self.import_scad,
                            "Ctrl+I")
        file_menu.addAction("Import S&TL...", self.import_stl,
                            "Ctrl+Shift+I")
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
        insert_menu.addAction(icons.icon("mdi.toy-brick-outline"),
                              "&Part Library...", self.open_library,
                              "Ctrl+L")
        insert_menu.addSeparator()
        for control in ("for_loop", "while_loop", "if_else", "assign",
                        "stl_import"):
            spec = NODE_TYPES[control]
            insert_menu.addAction(
                icons.icon(spec["icon"]), spec["label"],
                lambda _=False, t=control: self._add_primitive(t))

        view_menu = m.addMenu("&View")
        chat_act = self._chat_dock.toggleViewAction()
        chat_act.setText("&Chat Assistant (KherveAI)")
        chat_act.setIcon(icons.icon("mdi.robot-outline"))
        chat_act.setShortcut("Ctrl+/")
        view_menu.addAction(chat_act)
        view_menu.addSeparator()
        view_menu.addAction(self._grid_act)
        view_menu.addAction(self._snap_act)
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

        help_menu = m.addMenu("&Help")
        help_menu.addAction("&About", self._about)

    def _build_status_bar(self):
        self._cursor_label = QLabel("x: 0.0 mm  y: 0.0 mm")
        self.statusBar().addWidget(self._cursor_label)
        self._measure_label = QLabel("")
        self.statusBar().addWidget(self._measure_label)
        self._zoom_label = QLabel(
            f"1 mm = {self.view2d.px_per_mm():.2f} px")
        self.statusBar().addPermanentWidget(self._zoom_label)
        self._engine_label = QLabel()
        self.statusBar().addPermanentWidget(self._engine_label)
        self._refresh_engine_label()

    def _cursor_moved(self, p):
        _axes, (kx, ky) = PLANES[self.scene.plane]
        self._cursor_label.setText(
            f"{kx}: {p.x():.1f} mm  {ky}: {p.y():.1f} mm")

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
        node = self.model.add_node(type)
        self.builder.tree.select_nodes([node])

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
        self._syncing = False

    def _scene_selected(self, nodes):
        if self._syncing:
            return
        self._syncing = True
        self.builder.tree.select_nodes(nodes)
        self.properties.set_node(nodes[0] if len(nodes) == 1 else None)
        self.builder.highlight_nodes(nodes)
        self._syncing = False

    def _node_created(self, node):
        self.builder.tree.select_nodes([node])

    # ---------------------------------------------------- 3D pipeline
    def _model_edited(self):
        self._dirty = True
        self._update_title()
        self._refresh_preview()

    def _refresh_preview(self):
        colored = mesh.tessellate_colored(self.model.root)
        tris = [t for t, _c in colored]
        colors = [c for _t, c in colored]
        has_colors = any(c is not None for c in colors)
        label = "built-in preview"
        if mesh.uses_booleans(self.model.root):
            label += (" (booleans approximated)"
                      if not self.engine.available else "")
        self.view3d.set_mesh(tris, label,
                             colors if has_colors else None)
        if tris and not self._fitted:
            self.view3d.fit()
            self._fitted = True
        if self.engine.available and self.model.root.children:
            # colours only exist in the preview: STL is geometry-only,
            # so skip the engine swap while the document is coloured
            # (F5 still forces an exact render).
            if not has_colors:
                self.engine.request_render(self.model.to_scad())

    def _render_now(self):
        if self.engine.available:
            self.engine.request_render(self.model.to_scad())
            self.statusBar().showMessage("Rendering with OpenSCAD…",
                                         2000)
        else:
            self._refresh_preview()
            self.statusBar().showMessage(
                "OpenSCAD not found — using built-in preview.", 4000)

    def _engine_mesh(self, tris):
        self.view3d.set_mesh(tris, "OpenSCAD")
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

    # ------------------------------------------------------------ files
    def new_document(self):
        if not self._confirm_discard():
            return
        self.model.clear()
        self._path = None
        self._dirty = False
        self._fitted = False
        self._update_title()

    def open_file(self):
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Open", "", "KherveCAD document (*.kcad)")
        if not path:
            return
        try:
            document.load_kcad(self.model, path)
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME, f"Could not open:\n{exc}")
            return
        self._path = path
        self._dirty = False
        self._fitted = False
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
        self._update_title()

    def save_file_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save As", "", "KherveCAD document (*.kcad)")
        if not path:
            return
        if not path.lower().endswith(".kcad"):
            path += ".kcad"
        self._path = path
        self.save_file()

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
        self.view3d.fit()

    def import_scad(self):
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Import OpenSCAD", "", "OpenSCAD program (*.scad)")
        if not path:
            return
        from . import scadparse
        try:
            warnings = scadparse.import_scad(self.model, path)
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME,
                                f"Could not import:\n{exc}")
            return
        self._path = None                     # imported = new document
        self._dirty = True
        self._fitted = False
        self._update_title()
        if warnings:
            QMessageBox.information(
                self, APP_NAME,
                "Imported with limitations:\n- "
                + "\n- ".join(warnings[:12])
                + ("\n…" if len(warnings) > 12 else ""))

    def import_stl(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import STL", "", "STL mesh (*.stl)")
        if not path:
            return
        node = self.model.add_node("stl_import", dict(path=path),
                                   name=Path(path).stem)
        self.builder.tree.select_nodes([node])
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

    def _confirm_discard(self) -> bool:
        if not self._dirty:
            return True
        answer = QMessageBox.question(
            self, APP_NAME, "Discard unsaved changes?",
            QMessageBox.Discard | QMessageBox.Cancel)
        return answer == QMessageBox.Discard

    def closeEvent(self, event):
        if self._confirm_discard():
            event.accept()
        else:
            event.ignore()

    def _about(self):
        QMessageBox.about(
            self, f"About {APP_NAME}",
            f"<b>{APP_NAME}</b> v{__version__}<br>"
            "Easy-to-use CAD GUI with OpenSCAD as the engine, in the "
            "Kherve family.<br><br>GPL-3.0 — Gwilherm Kerherve")

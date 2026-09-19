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

import sys
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QAction, QActionGroup, QApplication,
                             QDockWidget, QFileDialog, QLabel,
                             QMainWindow, QMessageBox, QSplitter)

from . import APP_NAME, __version__, document, icons, mesh, units
from .engine import ScadEngine, set_openscad_path
from .model import NODE_TYPES, DocumentModel
from .properties import PropertiesPanel
from .style import THEMES, apply_style, current_theme
from .treepanel import BuilderPanel
from .toolbars import build_options_bar, build_tool_bar
from .view2d import PLANES, SketchScene, SketchView
from .view3d import View3D

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
        # exploded view (explode.py): a display, remembered between runs
        from PyQt5.QtCore import QSettings as _QSettings
        from . import explode as _explode
        _saved = _QSettings("Kherve", "KherveCAD")
        _mode = str(_saved.value("explode/mode", _explode.DEFAULT_MODE))
        try:
            _amount = float(_saved.value("explode/amount",
                                         _explode.DEFAULT_AMOUNT))
        except (TypeError, ValueError):
            _amount = _explode.DEFAULT_AMOUNT
        self._explode = dict(
            on=False, amount=_amount,
            mode=_mode if _mode in _explode.MODES else _explode.DEFAULT_MODE)

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
        self._left_column = left              # folded away by Vibe Model
        # zoom / pan / focus buttons floating on both views
        from . import viewnav
        viewnav.attach_2d(self.view2d)
        viewnav.attach_3d(self.view3d)

        # ---- wiring
        self.builder.tree.selection_changed.connect(self._tree_selected)
        self.builder.object_tab.tree.selection_changed.connect(
            self._tree_selected)
        # the Object tab isolates both viewers to the active Object
        self.scene.isolation_resolver = self.builder.isolated_component
        self.builder.active_component_changed.connect(
            lambda _n: self._isolation_changed())
        self.builder.currentChanged.connect(
            lambda _i: self._isolation_changed())
        self.builder.tree.pick_anchor.connect(self._start_anchor_pick)
        self.builder.object_tab.tree.pick_anchor.connect(
            self._start_anchor_pick)
        self.builder.tree.snap_objects.connect(self._start_snap)
        self.builder.object_tab.tree.snap_objects.connect(
            self._start_snap)
        self.scene.selection_changed.connect(self._scene_selected)
        self.scene.node_created.connect(self._node_created)
        self.scene.plane_changed.connect(self._on_plane_auto_changed)
        self.properties.point_selected.connect(
            self.scene.set_point_highlight)
        self.view2d.cursor_moved.connect(self._cursor_moved)
        self.view2d.zoom_changed.connect(
            lambda ppm: self._zoom_label.setText(
                f"1 {self._unit()} = {ppm:.2f} px"))
        self.scene.status.connect(
            lambda text: self.statusBar().showMessage(text, 6000))
        self.scene.measure_changed.connect(
            lambda text: self._measure_label.setText(text))
        self.view2d.clipboard_op.connect(
            lambda op: self._tree_command(op))
        self.view2d.step_object.connect(
            lambda step: self._tree_command("step", step))
        self.model.structure_changed.connect(self._model_edited)
        self.model.node_changed.connect(lambda _n: self._model_edited())
        self.model.references_changed.connect(self._model_edited)
        self.model.drawing_changed.connect(self._drawing_edited)
        self.model.unit_changed.connect(self._unit_changed)
        self.model.scale_changed.connect(self._scale_changed)
        self.model.mate_released.connect(
            lambda n: self.statusBar().showMessage(
                f"{n.name} detached — its position is now yours to "
                f"set (the mate would have overwritten it).", 5000))
        self.view3d.lighting_bar.refresh_requested.connect(
            self.force_refresh)
        self.engine.mesh_ready.connect(self._engine_mesh)
        self.engine.part_ready.connect(self._part_mesh_ready)
        self.engine.render_failed.connect(self._engine_failed)
        self.engine.busy_changed.connect(self._engine_busy)

        self._build_chat_dock()
        from . import customizer_panel
        customizer_panel.attach(self)
        self._build_tool_bar()
        self._build_options_bar()
        self._build_menus()
        self._build_status_bar()
        self._update_title()
        self._refresh_preview()
        # an installed build looks for a new release once a day
        self.updater.schedule_startup_check()

    def _build_chat_dock(self):
        from .chat import ChatPanel
        self.chat = ChatPanel(self)
        self._chat_dock = QDockWidget("Assistant", self)
        self._chat_dock.setObjectName("chat_dock")
        self._chat_dock.setWidget(self.chat)
        self.addDockWidget(Qt.RightDockWidgetArea, self._chat_dock)
        # Hidden by default: the ChatBox needs the user's own API key,
        # so it stays folded away until they ask for it (AI > ChatBox,
        # Ctrl+/).
        self._chat_dock.hide()

    # ------------------------------------------------------------ chrome
    def _build_tool_bar(self):
        self._tools_bar = build_tool_bar(self)

    def _build_options_bar(self):
        self._options_bar = build_options_bar(self)

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
        file_menu.addAction(icons.icon("mdi.svg"),
                            "Import 2D &Drawing (SVG/DXF)...",
                            self.import_drawing)
        file_menu.addAction(icons.icon("mdi.image-filter-hdr"),
                            "Import &Height Map (surface)...",
                            self.import_surface)
        file_menu.addSeparator()
        file_menu.addAction("Export Open&SCAD...", self.export_scad,
                            "Ctrl+E")
        file_menu.addAction("Export S&TL...", self.export_stl,
                            "Ctrl+Shift+E")
        from .pngexport import open_dialog as export_png_dialog
        file_menu.addAction(icons.icon("mdi.image-outline"),
                            "Export PN&G...",
                            lambda: export_png_dialog(self),
                            "Ctrl+Alt+E")
        from . import photoreal_ui
        file_menu.addAction(icons.icon("mdi.camera-iris"),
                            "Render P&hoto (Blender)...",
                            lambda: photoreal_ui.open_dialog(self))
        file_menu.addAction(icons.icon("mdi.drawing-box"),
                            "&Blueprint (2D Drawing)...",
                            self.open_blueprint, "Ctrl+Shift+D")
        file_menu.addSeparator()
        file_menu.addAction(icons.icon("mdi.cloud-upload-outline"),
                            "&Publish to Printables...",
                            self.publish_to_printables,
                            "Ctrl+Shift+P")

        def _planetcraft():
            from . import planetcraft_dialog
            planetcraft_dialog.open_dialog(self)
        file_menu.addAction(icons.icon("mdi.earth"),
                            "Send to Planet&Craft...", _planetcraft)
        file_menu.addSeparator()
        # Qt moves an action called "Exit" into the macOS application
        # menu unless told otherwise, so File had no way out on a Mac.
        # There the app menu's own Quit owns Cmd+Q; claiming it twice
        # would make Qt fire neither.
        exit_act = file_menu.addAction(
            "E&xit", self.close,
            "" if sys.platform == "darwin" else "Ctrl+Q")
        exit_act.setMenuRole(QAction.NoRole)

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
                            lambda: self._tree_command("cut"))
        edit_menu.addAction(icons.icon("mdi.content-copy"),
                            "&Copy\tCtrl+C",
                            lambda: self._tree_command("copy"))
        edit_menu.addAction(icons.icon("mdi.content-paste"),
                            "&Paste\tCtrl+V",
                            lambda: self._tree_command("paste"))
        edit_menu.addSeparator()
        edit_menu.addAction("Move &Up\tCtrl+Up",
                            lambda: self._tree_command("shift", -1))
        edit_menu.addAction("Move Dow&n\tCtrl+Down",
                            lambda: self._tree_command("shift", 1))
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
        edit_menu.addAction("Document &Units...", self.choose_unit)
        edit_menu.addAction("Document &Scale (1 : N)...", self.choose_scale)
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
        # every toolbar tool, grouped the way the toolbars group them
        from .toolbars import build_insert_menu
        build_insert_menu(self, insert_menu)

        self._build_library_menu(m)

        view_menu = m.addMenu("&View")
        customizer_act = self._customizer_dock.toggleViewAction()
        customizer_act.setIcon(icons.icon("mdi.tune-variant"))
        customizer_act.setText("&Customizer (sliders)")
        view_menu.addAction(customizer_act)
        from . import animate
        view_menu.addAction(icons.icon("mdi.play-circle-outline"),
                            "&Animate ($t)...",
                            lambda: animate.open_panel(self))
        view_menu.addAction(self._grid_act)
        view_menu.addAction(self._snap_act)
        view_menu.addAction(self._vibe_act)
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
        view_menu.addAction(icons.icon("mdi.image-outline"),
                            "Add &Reference Image…",
                            self._add_reference_image)
        view_menu.addAction("Clear Reference &Images",
                            self.model.clear_reference_images)
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
        from .view3d import PROJECTIONS
        proj_menu = view_menu.addMenu("3D &Projection")
        self._proj_group = QActionGroup(self)
        for name in PROJECTIONS:
            act = QAction(name, self, checkable=True)
            act.setChecked(name == self.view3d.projection)
            act.triggered.connect(
                lambda _, n=name: self.set_projection(n))
            self._proj_group.addAction(act)
            proj_menu.addAction(act)
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
        # the model on a round platform with a soft shadow (stage.py)
        self._stage_act = QAction("3D &Platform && Shadow", self,
                                  checkable=True)
        self._stage_act.setChecked(self.view3d.stage)
        self._stage_act.setStatusTip(
            "Stand the model on a platform with a soft shadow from a "
            "light at the top left, instead of the ground grid")
        self._stage_act.triggered.connect(self.view3d.set_stage)
        self.view3d.stage_toggled.connect(self._stage_act.setChecked)
        view_menu.addAction(self._stage_act)
        # Blender-style looks (shading.py): valleys darker, edges drawn
        self._cavity_act = QAction("3D &Cavity Shading", self,
                                   checkable=True)
        self._cavity_act.setChecked(self.view3d.cavity)
        self._cavity_act.setStatusTip("Darken valleys and lighten ridges "
                                      "so the shape reads at a glance")
        self._cavity_act.triggered.connect(self.view3d.set_cavity)
        self._edges_act = QAction("3D &Edge Lines", self, checkable=True)
        self._edges_act.setChecked(self.view3d.edges)
        self._edges_act.setStatusTip("Draw the model's edges and outline "
                                     "as thin lines")
        self._edges_act.triggered.connect(self.view3d.set_edges)
        self._smooth_act = QAction("3D &Smooth Shading", self,
                                   checkable=True)
        self._smooth_act.setChecked(self.view3d.smooth)
        self._smooth_act.setStatusTip(
            "Shade curved surfaces smoothly (a normal per vertex) instead "
            "of showing their facets; edges sharper than 40° stay hard")
        self._smooth_act.triggered.connect(self.view3d.set_smooth)
        self._overlay_act = QAction("Compare to &Reference Image (overlay)",
                                    self, checkable=True)
        self._overlay_act.setChecked(self.view3d.overlay)
        self._overlay_act.setStatusTip(
            "Draw the reference pictures over the model as well as behind "
            "it: from the plane's square-on view (Front, Top, Right) the "
            "model's outline is checked against the photo")
        self._overlay_act.triggered.connect(self.view3d.set_overlay)
        self._gl_act = QAction("3D &Hardware Rendering (OpenGL)", self,
                               checkable=True)
        self._gl_act.setChecked(self.view3d.hardware)
        self._gl_act.setStatusTip(
            "Draw the model with OpenGL: exact occlusion at any size, "
            "anti-aliased. Off, the built-in painter draws it")
        self._gl_act.triggered.connect(self.view3d.set_hardware)
        # a bar in the document's unit, true at the orbit centre
        self.view3d.unit = self.model.unit
        self.view3d.real_scale = self.model.real_scale
        self._scale_bar_act = QAction("3D Scale &Bar", self, checkable=True)
        self._scale_bar_act.setChecked(self.view3d.scale_bar)
        self._scale_bar_act.setStatusTip(
            "Show a scale bar in the document's unit in the 3D view — "
            "true at the point the camera orbits (everywhere in "
            "orthographic)")
        self._scale_bar_act.triggered.connect(self.view3d.set_scale_bar)
        self.view3d.look_toggled.connect(
            lambda key, on: {"cavity": self._cavity_act,
                             "edges": self._edges_act,
                             "smooth": self._smooth_act,
                             "overlay": self._overlay_act,
                             "scale_bar": self._scale_bar_act,
                             "hardware": self._gl_act}[key].setChecked(on))
        view_menu.addAction(self._cavity_act)
        view_menu.addAction(self._edges_act)
        view_menu.addAction(self._scale_bar_act)
        view_menu.addAction(self._smooth_act)
        view_menu.addAction(self._overlay_act)
        view_menu.addAction(self._gl_act)
        self._build_explode_menu(view_menu)
        self._build_cut_menu(view_menu)
        self._add_view_toggles()
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

        analyse_menu = m.addMenu("A&nalyse")
        from .analysis_dialog import open_analysis
        analyse_menu.addAction(
            icons.icon("mdi.scale-balance"), "&Mass properties...",
            lambda: open_analysis(self, "mass"))
        analyse_menu.addAction(
            icons.icon("mdi.printer-3d-nozzle-outline"),
            "Check for 3D &printing...",
            lambda: open_analysis(self, "print"))
        analyse_menu.addAction(
            icons.icon("mdi.set-center"), "Check &interference...",
            lambda: open_analysis(self, "interference"))
        from . import heatmap_ui
        heatmap_ui.add_menu(self, analyse_menu)

        ai_menu = m.addMenu("&AI")
        mcp_act = ai_menu.addAction("&Connect to Claude (Simple)\u2026",
                                    self._open_mcp_dialog)
        mcp_act.setIcon(icons.icon("mdi.lan-connect"))
        mcp_act.setToolTip("Let Claude Desktop, Claude Code or "
                           "another assistant build in this "
                           "document \u2014 no API key, it uses the "
                           "login you already have")
        chat_act = self._chat_dock.toggleViewAction()
        chat_act.setText("Chat&Box (requires API key)")
        chat_act.setIcon(icons.icon("mdi.robot-outline"))
        chat_act.setShortcut("Ctrl+/")
        chat_act.setToolTip("A chat box docked in the window; it "
                            "needs your own Claude, Mistral or "
                            "Ollama API key")
        ai_menu.addAction(chat_act)
        photo_act = ai_menu.addAction(
            icons.icon("mdi.camera-outline"), "Mesh from &Photo\u2026",
            self._open_photo3d)
        photo_act.setToolTip("Turn one picture into a 3D surface with an "
                             "image-to-3D model (Tripo, Meshy, or a "
                             "command you run locally) and import it")

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
        from .updater import Updater
        self.updater = Updater(self)
        self.updater.add_menu_actions(help_menu)
        help_menu.addSeparator()
        help_menu.addAction("&About", self._about)

    def _build_library_menu(self, menubar):
        """Library: parts to ADD, in themed sections (library_menu.py)."""
        from .library_menu import build_library_menu
        return build_library_menu(self, menubar)

    def _open_scad_libraries(self):
        """Library ▸ OpenSCAD Libraries: install BOSL2, MCAD, NopSCADlib…
        and insert the include line (scadlib_dialog.py)."""
        from . import scadlib_dialog
        scadlib_dialog.open_dialog(self)

    def _insert_library_part(self, part_id):
        from .library import (default_dims, default_part, insert_hook,
                              prepare_document)
        note = prepare_document(self.model, part_id,
                                default_dims(part_id))
        hook = insert_hook(part_id)
        if hook is not None:               # builds itself (a house)
            try:
                nodes = hook(self.model, default_dims(part_id))
            except Exception as exc:
                QMessageBox.warning(self, APP_NAME,
                                    f"Could not build the part:\n{exc}")
                return
            self.builder.tree.select_nodes([])
            self.view3d.fit()
            return
        try:
            node = default_part(part_id)
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME,
                                f"Could not build the part:\n{exc}")
            return
        self.model.root.add(node)
        self.model.structure_changed.emit()
        self.builder.tree.select_nodes([])
        self.view3d.fit()
        if note:
            self.statusBar().showMessage(note, 10000)

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
        u = self._unit()
        self._cursor_label = QLabel(f"x: 0.0 {u}  y: 0.0 {u}")
        self.statusBar().addWidget(self._cursor_label)
        self._measure_label = QLabel("")
        self.statusBar().addWidget(self._measure_label)
        self._dims_label = QLabel("")          # selected object's size
        self.statusBar().addWidget(self._dims_label)
        self._file_label = QLabel()            # current document path
        self.statusBar().addPermanentWidget(self._file_label)
        self._zoom_label = QLabel(
            f"1 {u} = {self.view2d.px_per_mm():.2f} px")
        self.statusBar().addPermanentWidget(self._zoom_label)
        self._engine_label = QLabel()
        self.statusBar().addPermanentWidget(self._engine_label)
        self._refresh_engine_label()
        self._update_title()                   # fills the file label

    def _cursor_moved(self, p):
        _axes, (kx, ky) = PLANES[self.scene.plane]
        u = self._unit()
        self._cursor_label.setText(
            f"{kx}: {p.x():.1f} {u}  {ky}: {p.y():.1f} {u}")

    # ---------------------------------------------------------- units
    def _unit(self) -> str:
        """The document unit's symbol for a readout ("mm", "nm", ...)."""
        return units.symbol(self.model.unit)

    def choose_unit(self):
        from . import units_ui
        units_ui.choose(self)

    def choose_scale(self):
        from . import units_ui
        units_ui.choose_scale(self)

    def _scale_changed(self, n):
        from . import units_ui
        units_ui.scale_changed(self, n)

    def _unit_changed(self, unit):
        from . import units_ui
        units_ui.changed(self, unit)

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
        if parent is None:
            self._geometry_created_in_main(node)
            return
        self.builder.object_tab.tree.select_nodes([node])

    def _geometry_created_in_main(self, node):
        """Raw geometry created while the Main tab is current: the Main
        assembly lists only whole parts, so wrap it in a new visible
        Object and continue in the Object tab — the part is already
        placed in Main as a single row."""
        comp = self.model.enclose_as_part(node)
        self.builder.open_component(comp)
        self.builder.object_tab.tree.select_nodes([node])
        self.statusBar().showMessage(
            f"New Object '{comp.name}' — it shows as one part in Main; "
            f"keep building it here, then switch back to Main to place "
            f"or snap it.", 8000)

    def _new_object(self):
        """Insert > New Object: create an empty Object and open it for
        editing in the Object tab. New Objects start hidden in the
        Main assembly — show them (Space) when they are ready."""
        self.builder.open_component(
            self.model.new_component(visible=False))

    def _tree_command(self, op: str, step: int = 0):
        """Run a selection command on whichever tree is in front — the
        Object tab's while it is current, else Main."""
        tree = self.builder.active_tree()
        if op == "step":                     # walk to the next object
            tree.step_selection(step)
        elif op == "shift":                  # reorder within the parent
            tree.shift_selection(step)
        else:
            {"cut": tree.cut_selection, "copy": tree.copy_selection,
             "paste": tree.paste_clipboard}[op]()

    def _apply_operation(self, op: str):
        tree = self.builder.active_tree()
        nodes = tree.selected_nodes()
        if not nodes:
            if op in ("for_loop", "while_loop", "if_else", "union",
                      "pattern", "intersection_for", "let"):
                self._add_primitive(op)       # empty, fill it after
                return
            self.statusBar().showMessage(
                "Select objects in the tree first.", 3000)
            return
        wrapper = self.model.wrap_nodes(nodes, op)
        if wrapper is not None:
            tree.select_nodes([wrapper])
            if op == "fillet":                # now: which edges?
                self.start_fillet_pick(wrapper)
            elif op == "sculpt":              # now: where to push?
                self.start_sculpt(wrapper)
            elif op == "push_pull":           # now: which faces?
                from . import faceedit_ui
                faceedit_ui.start(self, wrapper)

    def start_sculpt(self, node):
        """Open the sculpt panel for *node* (a sculpt): each click in
        the 3D view lands one brush stroke (sculpt_ui.py)."""
        from . import sculpt_ui
        sculpt_ui.start(self, node)

    def start_fillet_pick(self, node):
        """Arm the 3D view so clicks on the part add edges to the
        fillet *node* (fillet_pick.py); Esc finishes."""
        from . import fillet_pick
        fillet_pick.start(self, node)

    def _ungroup_selection(self):
        for node in self.builder.active_tree().selected_nodes():
            self.model.ungroup(node)

    def _delete_selection(self):
        for node in self.builder.active_tree().selected_nodes():
            self.model.remove_node(node)

    def _duplicate_selection(self):
        for node in self.builder.active_tree().selected_nodes():
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
        if self._explode["on"]:
            # which assembly comes apart follows the selection
            self._refresh_preview()
        self.scene.set_highlight(nodes)
        # zoom the 2D view to the selected object (a part silhouette or
        # an edited profile) so it is framed and centred, not clipped
        rect = self.scene.isolated_bounds()
        if rect is not None:
            self.view2d.frame_rect(rect)
        tris = self._highlight_tris()
        self.view3d.set_highlight_mesh(tris)
        self._refresh_anchor_markers()
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
            f"Size  X {dx:.1f} · Y {dy:.1f} · Z {dz:.1f} {self._unit()}")

    def _node_created(self, node):
        if self.builder.isolated_component() is None \
                and node.parent is self.model.root:
            self._geometry_created_in_main(node)   # drawn in Main
            return
        self.builder.object_tab.tree.select_nodes([node])

    # ---------------------------------------------------- 3D pipeline
    def _model_edited(self):
        # keep attached Objects glued to their (possibly just moved)
        # parents; the guard makes nested refreshes no-ops
        from . import mates
        mates.refresh(self.model)
        self._dirty = True
        self._update_title()
        self.view3d.set_reference_images(self.model.reference_images)
        self._refresh_preview()

    def _isolation_changed(self):
        """The Object tab took or released the viewers: re-render both
        for the (un)isolated scope."""
        self.scene.rebuild()
        self._refresh_preview()
        self._refresh_anchor_markers()

    # ---------------------------------------------------------- anchors
    def _anchor_component(self):
        """The part whose anchors show in the 3D view. In the Object
        tab: a single selected group inside the Object (its secondary
        anchors), else the Object itself. In Main: a single selected
        Object or instance."""
        from . import mates
        iso = self.builder.isolated_component()
        selected = [self.model.find(nid)
                    for nid in getattr(self, "_selected_ids", set())]
        if iso is not None:
            groups = [n for n in selected if n is not None
                      and n.type in ("union", "component")
                      and n is not iso and n.parent is iso]
            return groups[0] if len(groups) == 1 else iso
        chosen = [n for n in selected if n is not None
                  and (n.type == "component"
                       or (n.type == "reference"
                           and mates.definition_of(self.model, n)
                           is not None))]
        return chosen[0] if len(chosen) == 1 else None

    def _refresh_anchor_markers(self):
        from . import anchors, mates
        part = self._anchor_component()
        markers = []
        if part is not None:
            definition = mates.definition_of(self.model, part) \
                if part.type == "reference" else None
            # in the Object tab the view shows the Object at its own
            # origin, so compute markers in that same local frame
            with self._isolated_frame(self.builder.isolated_component()):
                markers = anchors.world_markers(
                    part, env=anchors.doc_env(self.model),
                    fn=self.model.effective_fn(), definition=definition)
        self.view3d.set_anchor_markers(markers)

    def _start_anchor_pick(self, comp):
        """Context menu "Add anchor": let the user click a face or
        edge in the 3D view. On an *instance* the pick runs in the
        Main assembly against that instance's own mesh and the anchor
        is stored on its definition; on an Object it isolates first."""
        from . import anchors, mates
        if comp.type == "reference":
            definition = mates.definition_of(self.model, comp)
            if definition is None:
                return
            env = anchors.doc_env(self.model)
            tris = mesh.tessellate(comp, env=env,
                                   fn=self.model.effective_fn())
            if not tris:
                return
            self.statusBar().showMessage(
                f"Click a face or edge of {comp.name} in the 3D view "
                f"to add an anchor (stored on {definition.name}, "
                f"shared by all its instances) — right-click to "
                f"cancel.", 10000)

            def done_instance(desc, _key=None):
                if desc is None:
                    self.statusBar().showMessage(
                        "Anchor pick cancelled.", 3000)
                    return
                pos = anchors.to_local(comp, desc["pos"], env)
                direction = anchors.dir_to_local(comp, desc["dir"], env)
                anchor = anchors.add_user_anchor(
                    self.model, definition, pos, direction,
                    name=desc.get("name", "Anchor"), kind="custom")
                self.statusBar().showMessage(
                    f"Anchor '{anchor['name']}' added to "
                    f"{definition.name} ({desc['kind']}).", 5000)
                self._refresh_anchor_markers()
            self.view3d.start_pick(done_instance, groups=[(comp, tris)])
            return
        if comp.type == "union":
            # a group inside an Object: pick against its own mesh in the
            # isolated view and store a secondary anchor on the group
            env = anchors.doc_env(self.model)
            tris = mesh.tessellate(comp, env=env,
                                   fn=self.model.effective_fn())
            if not tris:
                return
            self.statusBar().showMessage(
                f"Click a face or edge of {comp.name} to add a "
                f"secondary anchor — right-click to cancel.", 10000)

            def done_group(desc, _key=None):
                if desc is None:
                    self.statusBar().showMessage(
                        "Anchor pick cancelled.", 3000)
                    return
                pos = anchors.to_local(comp, desc["pos"], env)
                direction = anchors.dir_to_local(comp, desc["dir"], env)
                anchor = anchors.add_user_anchor(
                    self.model, comp, pos, direction,
                    name=desc.get("name", "Anchor"), kind="custom")
                self.statusBar().showMessage(
                    f"Secondary anchor '{anchor['name']}' added to "
                    f"{comp.name} ({desc['kind']}).", 5000)
                self._refresh_anchor_markers()
            self.view3d.start_pick(done_group, groups=[(comp, tris)])
            return
        self.builder.open_component(comp)
        self.statusBar().showMessage(
            "Click a face or edge of the object in the 3D view to add "
            "an anchor — right-click to cancel.", 10000)

        def done(desc):
            if desc is None:
                self.statusBar().showMessage("Anchor pick cancelled.",
                                             3000)
                return
            env = anchors.doc_env(self.model)
            pos = anchors.to_local(comp, desc["pos"], env)
            direction = anchors.dir_to_local(comp, desc["dir"], env)
            anchor = anchors.add_user_anchor(
                self.model, comp, pos, direction,
                name=desc.get("name", "Anchor"), kind="custom")
            self.statusBar().showMessage(
                f"Anchor '{anchor['name']}' added to {comp.name} "
                f"({desc['kind']}).", 5000)
            self._refresh_anchor_markers()
        self.view3d.start_pick(
            done, banner="Click a face or edge to add an anchor "
                         "(Esc cancels)")

    # ------------------------------------------------- two-click snap
    def _snap_scope(self):
        """Where snapping/anchoring happens: the active Object while
        the Object tab is current (snap its groups together — the
        "secondary" anchors), else None for the Main assembly."""
        return self.builder.isolated_component()

    def _snap_groups(self, scope=None):
        """[(part, world triangles)] of every visible mateable part at
        *scope* — Objects and instances in the assembly, or the groups
        inside an Object — what the two-click Snap tool picks against.
        In an Object scope the parts are tessellated in the Object's
        own local frame (its placement zeroed), matching the isolated
        3D view."""
        from . import anchors, mates
        env = anchors.doc_env(self.model)
        fn = self.model.effective_fn()
        groups = []
        for part in mates.parts(self.model, scope):
            if not part.visible:
                continue
            tris = mesh.tessellate(part, env=env, fn=fn)
            if tris:
                groups.append((part, tris))
        return groups

    @staticmethod
    def _match_anchor(anchor_list, pos, direction):
        """The anchor in *anchor_list* at local *pos* pointing along
        *direction* (within 0.1 mm, aligned), or None."""
        for anchor in anchor_list:
            d2 = sum((anchor["pos"][i] - pos[i]) ** 2 for i in range(3))
            dot = sum(anchor["dir"][i] * direction[i]
                      for i in range(3))
            if d2 < 0.01 and dot > 0.999:
                return anchor
        return None

    def _anchor_for_pick(self, part, desc):
        """The anchor a world-space pick means on *part*: an existing
        anchor at that spot (a bbox face like "Top", or an already
        picked one) when there is an exact match, else a new custom
        anchor — so snapping boxy parts reads as Top/Bottom mates and
        never litters duplicates. Anchors live on the part's
        *definition*, so every instance of an Object shares them."""
        from . import anchors, mates
        env = anchors.doc_env(self.model)
        definition = mates.definition_of(self.model, part) or part
        pos = anchors.to_local(part, desc["pos"], env)
        direction = anchors.dir_to_local(part, desc["dir"], env)
        anchor = self._match_anchor(
            anchors.anchors_of(definition, env=env,
                               fn=self.model.effective_fn()),
            pos, direction)
        if anchor is not None:
            return anchor
        return anchors.add_user_anchor(self.model, definition, pos,
                                       direction,
                                       name=desc.get("name", "Anchor"))

    def _snap_labeler(self):
        """A hover labeler for the Snap tool: names the anchor a click
        would reuse ("Base · Top") instead of the generic Face/Edge.
        Anchor lists are cached per part for the pick session, so the
        throttled hover never re-tessellates."""
        from . import anchors, mates
        env = anchors.doc_env(self.model)
        fn = self.model.effective_fn()
        cache = {}

        def label(desc, part):
            if part is None:
                return desc.get("name", "")
            if part.id not in cache:
                definition = mates.definition_of(self.model, part) \
                    or part
                cache[part.id] = anchors.anchors_of(definition,
                                                    env=env, fn=fn)
            pos = anchors.to_local(part, desc["pos"], env)
            direction = anchors.dir_to_local(part, desc["dir"], env)
            anchor = self._match_anchor(cache[part.id], pos, direction)
            name = anchor["name"] if anchor is not None \
                else desc.get("name", "")
            return f"{part.name} · {name}"
        return label

    def _start_snap(self):
        """Fusion-style two-click snap: click a face/edge on the part
        to move, then the target face on another part — the mate is
        created and solved immediately. In the Main tab this snaps
        whole Objects; in the Object tab it snaps the groups that make
        up the Object (the secondary anchors)."""
        from . import mates
        scope = self._snap_scope()
        groups = self._snap_groups(scope)
        if len(groups) < 2:
            where = (f"inside {scope.name}" if scope is not None
                     else "in the Main assembly")
            found = ", ".join(part.name for part, _tris in groups) \
                or "none"
            self.statusBar().showMessage(
                f"Snap needs two visible parts {where} — found "
                f"{len(groups)} ({found}). Hidden parts don't count; "
                f"select loose geometry and Group it (Ctrl+G) to make "
                f"it a part.", 8000)
            return
        if scope is None:
            self.builder.setCurrentIndex(0)      # the assembly view
        labeler = self._snap_labeler()
        self.statusBar().showMessage(
            "Snap 1/2: click the face or edge of the part to MOVE "
            "— Esc or right-click cancels.", 0)

        def first(desc, comp):
            if desc is None:
                self.statusBar().showMessage("Snap cancelled.", 3000)
                return
            # the part that MOVES has to hold the mate: a Move or a
            # bare boolean has nowhere to put the rotation, so it is
            # promoted to a Group first (geometry unchanged, undoable)
            promoted = mates.ensure_part(self.model, comp)
            if promoted is not comp:
                self.statusBar().showMessage(
                    f"{comp.name} is now in '{promoted.name}' so it can "
                    f"carry the snap.", 6000)
                comp = promoted
            child_anchor = self._anchor_for_pick(comp, desc)
            self.builder.active_tree().select_nodes([comp])
            # keep the first pick visibly marked while the second is
            # aimed, so you never lose track of what will move
            self.view3d.set_pick_pinned(
                desc, f"{comp.name} · {child_anchor['name']}")
            self.statusBar().showMessage(
                f"Snap 2/2: {comp.name} · {child_anchor['name']} — now "
                f"click the target face on ANOTHER object.", 0)

            def second(desc2, target):
                if desc2 is None:
                    self.statusBar().showMessage("Snap cancelled.",
                                                 3000)
                    return
                if target is comp:
                    self.statusBar().showMessage(
                        "That is the same object — click a face on a "
                        "different one (right-click cancels).", 0)
                    self.view3d.start_pick(
                        second, groups=groups, labeler=labeler,
                        banner=f"Snap 2/2 — that was {comp.name} "
                               f"itself: click a face on ANOTHER part")
                    return
                self.view3d.set_pick_pinned(None)
                parent_anchor = self._anchor_for_pick(target, desc2)
                mates.attach(self.model, comp, target.name,
                             child_anchor["name"],
                             parent_anchor["name"])
                self.statusBar().showMessage(
                    f"Snapped {comp.name} ({child_anchor['name']}) "
                    f"onto {target.name} ({parent_anchor['name']}).",
                    8000)
                self._show_snap_tweak(comp)
            self.view3d.start_pick(
                second, groups=groups, labeler=labeler,
                banner=f"Snap 2/2 — {comp.name}: "
                       f"{child_anchor['name']} picked. Click the "
                       f"target face on ANOTHER part (Esc cancels)")
        self.view3d.start_pick(
            first, groups=groups, labeler=labeler,
            banner="Snap 1/2 — click the face or edge of the part to "
                   "MOVE (Esc cancels)")

    def _show_snap_tweak(self, comp):
        """The small non-modal follow-up after a two-click snap:
        offset / spin / flip applied live, no context-menu digging."""
        from . import mates
        if getattr(self, "_snap_tweak", None) is not None:
            self._snap_tweak.close()
        popup = mates.SnapTweakPopup(self.model, comp, self)
        popup.setAttribute(Qt.WA_DeleteOnClose)
        popup.finished.connect(
            lambda _r: setattr(self, "_snap_tweak", None))
        self._snap_tweak = popup
        popup.show()

    def _render_scope(self):
        """(root node, scad code callable) for the current view — the
        active Object while the Object tab is current, else the whole
        document."""
        iso = self.builder.isolated_component()
        if iso is not None:
            return iso, (lambda: self.model.subtree_scad(iso))
        return self.model.root, self.model.to_scad

    _PLACEMENT = ("x", "y", "z", "rx", "ry", "rz")

    def _isolated_frame(self, node):
        """Context manager: render *node* in its own LOCAL frame — its
        Main-assembly placement (set by a mate) zeroed and its
        hidden-in-Main flag forced visible. The Object tab edits a
        part at its own origin, independent of where it sits in the
        assembly. No-op when *node* is None (the Main tab)."""
        from contextlib import contextmanager

        @contextmanager
        def ctx():
            if node is None:
                yield
                return
            saved = {k: node.params.get(k, 0.0) for k in self._PLACEMENT
                     if k in node.params}
            saved_visible = node.visible
            for k in saved:
                node.params[k] = 0.0
            node.visible = True
            try:
                yield
            finally:
                node.params.update(saved)
                node.visible = saved_visible
        return ctx()

    def _highlight_tris(self):
        """World triangles of the selection, walked from the *current
        scope* — the active Object in the Object tab, the document in
        Main. Walking the document root instead would tessellate the
        selection again for every Main instance of that Object and drop
        those copies, at their assembly placement, into the isolated
        view: the Object tab would show geometry that belongs to Main."""
        ids = getattr(self, "_selected_ids", set())
        if not ids:
            return []
        from . import part_collections
        with part_collections.hiding(self.model):
            return self._highlight_tris_now(ids)

    def _highlight_tris_now(self, ids):
        root = self._render_scope()[0]
        iso = root if root is not self.model.root else None
        plan = getattr(self, "_explode_plan", None)
        with self._isolated_frame(iso):
            if plan is not None and plan.group is not None:
                # exploded: the tint goes where its part went
                from . import explode
                return explode.highlight(root, ids, plan,
                                         fn=self.model.effective_fn())
            return mesh.selected_world_tris(
                root, ids, fn=self.model.effective_fn())

    def _queue_part_renders(self, root):
        """Ask OpenSCAD for an exact mesh of every part in view that
        doesn't have one yet, one part at a time in the background.

        An assembly is parts placed side by side, not booleaned
        together, so each part can be rendered on its own and the
        preview assembled from the results: bolt holes are really cut,
        every part keeps its own colour (a single STL of the whole
        document could carry only one, which is why a coloured document
        used to stay approximate), and a part is re-rendered only when
        its own contents change. Returns (exact, total) for the badge."""
        if not self.engine.available:
            return 0, 0
        from . import anchors
        env = anchors.doc_env(self.model)
        exact = total = 0
        for node in root.walk():
            if node.type != "component" or not node.children:
                continue
            if not mesh.needs_exact(node, env):
                continue        # already exact in the preview, or coloured
            key = mesh.exact_key(node, env, fn=self.model.effective_fn())
            if key is None:                 # holds a Linked copy: unkeyable
                continue
            total += 1
            if mesh.has_exact_mesh(key):
                exact += 1
            else:
                self.engine.request_part_render(
                    key, self.model.subtree_scad(node))
        return exact, total

    def _part_mesh_ready(self, key, tris):
        """One part finished rendering: keep its exact mesh and redraw
        (cheap — every other part comes from the cache)."""
        mesh.set_exact_mesh(key, tris)
        self._refresh_preview()

    def _refresh_preview(self):
        # a hidden collection's parts stay out of the views and the
        # exact render, never out of the document (part_collections)
        from . import part_collections
        with part_collections.hiding(self.model):
            self._refresh_preview_now()

    def _refresh_preview_now(self):
        fn = self.model.effective_fn()
        root, scad = self._render_scope()
        iso = root if root is not self.model.root else None
        exploding = self._explode["on"]
        plan = None
        with self._isolated_frame(iso):
            if exploding:
                from . import anchors, explode
                plan = explode.plan(
                    root, anchors.doc_env(self.model), fn,
                    self._explode["amount"], self._explode["mode"],
                    self._explode_selection(root))
                colored = plan.items
            else:
                colored = mesh.tessellate_colored(root, fn=fn)
            booleans = mesh.approximates(root)
        self._explode_plan = plan
        tris = [t for t, _c in colored]
        colors = [c for _t, c in colored]
        has_colors = any(c is not None for c in colors)
        exact, total = self._queue_part_renders(root)
        label = "built-in preview"
        if iso is not None:
            label += f" — Object: {root.name}"
        if total:
            label += f" — {exact}/{total} parts exact"
        if booleans and not self.engine.available:
            label += " (booleans approximated)"
        if plan is not None:
            label += (" — exploded" if plan.group is not None
                      else " — nothing to pull apart")
        from . import heatmap_ui
        colors, label = heatmap_ui.apply(self, tris, colors, label)
        has_colors = has_colors or bool(self._heat_stats)
        self.view3d.set_mesh(tris, label,
                             colors if has_colors else None)
        if getattr(self, "_selected_ids", set()):
            self.view3d.set_highlight_mesh(self._highlight_tris())
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
            # would wrongly paint every part the same. An exploded view
            # is per-part too: one STL of the whole would land on top of
            # it with the parts back together.
            if exploding:
                self.engine.cancel()
            elif not has_colors or uniform:
                self.engine.request_render(scad())
            else:
                # A render requested a moment ago (before the document
                # was coloured) would land on top of the colour preview
                # and quietly wipe it — the "3D forgot my colours" bug.
                self.engine.cancel()

    def _add_reference_image(self):
        """A picture to model against, on the plane the 2D view shows,
        centred on the origin at the width the user gives."""
        from PyQt5.QtWidgets import QFileDialog, QInputDialog
        from . import refimage
        path, _filter = QFileDialog.getOpenFileName(
            self, "Reference image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp)")
        if not path:
            return
        ratio = refimage.aspect(path)
        if ratio is None:
            QMessageBox.warning(self, "Reference image",
                                f"Could not read an image from {path}.")
            return
        width, ok = QInputDialog.getDouble(
            self, "Reference image",
            f"Width on the plane ({self._unit()}):", 100.0, 0.1, 1e6, 1)
        if not ok:
            return
        height = width * ratio
        self.model.add_reference_image(dict(
            path=path, plane=self.scene.plane, x=-width / 2,
            y=-height / 2, width=width, height=height, offset=0.0,
            opacity=0.5, visible=True))
        self.statusBar().showMessage(
            f"Reference image on the {self.scene.plane} plane — the MCP "
            "tool set_reference_image can place and size it exactly.",
            6000)

    def set_projection(self, name: str):
        """Perspective or orthographic 3D view, with the View menu's
        tick kept in step (an MCP client can change it too)."""
        self.view3d.set_projection(name)
        for act in self._proj_group.actions():
            act.setChecked(act.text() == self.view3d.projection)

    def set_vibe_model(self, on: bool):
        """Vibe Model: the object tree, Properties, the 2D sketch, the
        drawing tools and all of the main toolbar but file, undo and
        this toggle fold away and the 3D model fills the window — for
        building by talking to an assistant and watching the result.
        Toggling back restores the panels exactly as they were."""
        on = bool(on)
        self._left_column.setVisible(not on)
        self.view2d.setVisible(not on)
        self._tools_bar.setVisible(not on)
        for act in self._options_bar.actions():
            if act not in self._vibe_keep:
                act.setVisible(not on)
        act = getattr(self, "_vibe_act", None)
        if act is not None and act.isChecked() != on:
            act.blockSignals(True)
            act.setChecked(on)
            act.blockSignals(False)
        self.statusBar().showMessage(
            "Vibe Model — describe the part to your assistant (AI menu) "
            "and watch it build; Ctrl+Shift+M brings the panels back."
            if on else "Panels back — edit by hand.", 6000)

    # --------------------------------------------------- cut through
    def _add_view_toggles(self):
        """Exploded View and Cut Through on the 3D view's floating bar:
        a button that switches each, and an arrow holding every option —
        the View menu's own actions, so the two always agree."""
        from . import viewnav
        bar = getattr(self.view3d, "nav_bar", None)
        if bar is None:
            return
        explode = viewnav.add_menu_button(
            bar, "explode", "mdi.cube-unfolded", "✥",
            "Exploded view: pull the parts apart to show how they go "
            "together (Ctrl+Shift+X). With a part selected, the assembly "
            "it belongs to comes apart. The arrow: distance and direction.",
            self._explode_menu.actions(),
            lambda on: self.set_explode(bool(on)))
        explode.setChecked(self._explode["on"])
        self._explode_act.toggled.connect(explode.setChecked)
        cut = viewnav.add_menu_button(
            bar, "cut", "mdi.content-cut", "✂",
            "Cut through: slice the model to see inside it (Ctrl+Alt+X). "
            "The arrow: which axis, where, and which half stays.",
            self._cut_menu.actions(), lambda on: self.set_cut(bool(on)))
        cut.setChecked(self.view3d.cut_state() is not None)
        self.view3d.cut_changed.connect(
            lambda *_: cut.setChecked(self.view3d.cut_state() is not None))
        viewnav.add_options_button(
            bar, "display", "mdi.eye-settings-outline", "☰",
            "Display: platform & shadow, cavity shading, edge lines, "
            "scale bar, smooth shading, reference image overlay and "
            "hardware rendering — the same switches as the View menu.",
            [self._stage_act, self._cavity_act, self._edges_act,
             self._scale_bar_act, self._smooth_act, self._overlay_act,
             self._gl_act])

    def _build_cut_menu(self, view_menu):
        """View ▸ Cut Through (cut_ui.py)."""
        from . import cut_ui
        cut_ui.build_menu(self, view_menu)

    def set_cut(self, on=True, axis=None, position=None, flip=None):
        """Cut Through on or off (and which axis, where, which half)."""
        from . import cut_ui
        cut_ui.set_cut(self, on, axis, position, flip)

    def _sync_cut(self):
        from . import cut_ui
        cut_ui.sync(self)

    # ------------------------------------------------- exploded view
    def _build_explode_menu(self, view_menu):
        """View ▸ Exploded View: on/off, how far, which way."""
        from . import explode
        menu = self._explode_menu = view_menu.addMenu(
            icons.icon("mdi.arrow-expand-all"), "E&xploded View")
        self._explode_act = QAction("&Explode the Assembly", self,
                                    checkable=True)
        self._explode_act.setShortcut("Ctrl+Shift+X")
        self._explode_act.setStatusTip(
            "Push every part away from the centre to show how the "
            "assembly goes together — the model itself does not move")
        self._explode_act.triggered.connect(
            lambda on: self.set_explode(bool(on)))
        menu.addAction(self._explode_act)
        menu.addSeparator()
        self._explode_amounts = QActionGroup(self)
        for amount in explode.AMOUNTS:
            act = QAction(f"Distance {int(round(amount * 100))} %", self,
                          checkable=True)
            act.setData(amount)
            act.triggered.connect(
                lambda _=False, a=amount: self.set_explode(True, amount=a))
            self._explode_amounts.addAction(act)
            menu.addAction(act)
        menu.addSeparator()
        self._explode_modes = QActionGroup(self)
        for mode in explode.MODES:
            act = QAction("Outwards (radial)" if mode == "Radial"
                          else f"Along {mode}", self, checkable=True)
            act.setData(mode)
            act.triggered.connect(
                lambda _=False, m=mode: self.set_explode(True, mode=m))
            self._explode_modes.addAction(act)
            menu.addAction(act)
        self._sync_explode_menu()

    def _sync_explode_menu(self):
        if not hasattr(self, "_explode_act"):
            return
        state = self._explode
        self._explode_act.setChecked(state["on"])
        for act in self._explode_amounts.actions():
            act.setChecked(abs(float(act.data()) - state["amount"]) < 1e-9)
        for act in self._explode_modes.actions():
            act.setChecked(act.data() == state["mode"])

    def explode_state(self) -> dict:
        """{on, amount, mode} of the exploded view — plus, while it is
        on, the parts it pulled apart and the status-bar note."""
        state = dict(self._explode)
        plan = getattr(self, "_explode_plan", None)
        if state["on"] and plan is not None:
            state["note"] = plan.note
            state["parts"] = [part.name for part, _move in plan.pieces]
        return state

    def _explode_selection(self, root):
        """The selected nodes inside *root*: an exploded view pulls apart
        the assembly they belong to. Pictures (explode.showing) show the
        whole assembly whatever is selected."""
        ids = getattr(self, "_selected_ids", set())
        if not ids or getattr(self, "_explode_whole", False):
            return []
        return [n for n in root.walk() if n.id in ids]

    def set_explode(self, on=None, amount=None, mode=None):
        """Switch the exploded view and/or change how far and which
        way the parts move; the 3D view redraws at once."""
        from PyQt5.QtCore import QSettings
        from . import explode
        state = self._explode
        if on is not None:
            state["on"] = bool(on)
        if amount is not None:
            state["amount"] = max(0.0, float(amount))
        if mode is not None and mode in explode.MODES:
            state["mode"] = mode
        settings = QSettings("Kherve", "KherveCAD")
        settings.setValue("explode/amount", state["amount"])
        settings.setValue("explode/mode", state["mode"])
        self._sync_explode_menu()
        self._refresh_preview()
        plan = getattr(self, "_explode_plan", None)
        if not state["on"]:
            message = "Parts back together."
        elif plan is None or plan.group is None:
            # say so: switching it on and seeing nothing move read as a
            # broken menu item
            message = plan.note if plan is not None else \
                "Nothing to pull apart."
        else:
            message = (f"Exploded view — {plan.note}, "
                       f"{int(round(state['amount'] * 100))} %, "
                       f"{state['mode'].lower()}; Ctrl+F frames it, "
                       "Ctrl+Shift+X puts the parts back.")
        self.statusBar().showMessage(message, 8000)

    def force_refresh(self):
        """Redraw everything from the object tree: drop the mesh caches
        and rebuild both views. The 3D pipeline is incremental (cached
        per Object, an exact render swapped in when it lands), so this
        is the way to make it start over when what is on screen looks
        stale."""
        mesh.clear_component_cache()
        self.scene.rebuild()
        self._refresh_preview()
        self.view3d.update()
        self.statusBar().showMessage("Redrew both views from the "
                                     "object tree.", 3000)

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
        colors = [color] * len(tris) if color else None
        from . import heatmap_ui
        colors, label = heatmap_ui.apply(self, tris, colors, "OpenSCAD")
        self.view3d.set_mesh(tris, label, colors)
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
        elif ext in (".scad", ".csg"):          # .csg: OpenSCAD's export
            if not self._confirm_discard():
                return
            self._import_scad_path(path)
        elif ext in MESH_EXTS:
            self._import_mesh_path(path)
        elif ext in (".svg", ".dxf"):
            self._import_drawing_path(path)
        elif ext == ".dat":
            self._import_surface_path(path)
        else:
            QMessageBox.warning(
                self, APP_NAME,
                f"KherveCAD can open .kcad, .scad, .csg, mesh files "
                f"(.stl/.obj/.off/.3mf/.amf/.glb), 2D drawings (.svg/.dxf) "
                f"and height maps (.dat) — not {ext or 'this type'}.")

    # ------------------------------------------------------ drag & drop
    _DROP_EXTS = (".kcad", ".scad", ".csg", ".stl", ".obj", ".off", ".3mf",
                  ".amf", ".svg", ".dxf", ".dat")

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

    def _flush_blueprint(self):
        """An edit still waiting in the Blueprint's Properties goes into
        the document before it is saved or the window closes."""
        board = getattr(self, "_blueprint", None)
        if board is not None:
            board.flush_pending()

    def save_file(self):
        self._flush_blueprint()
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
        self.builder.tree.select_nodes([])
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
        # the imported program's loose geometry lands as ONE part in
        # the Main assembly, edited in the Object tab like any other
        # part; module-defined Objects and instances keep their shape
        self.model.enclose_import_as_part(Path(path).stem)
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

    def import_drawing(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import 2D drawing", "",
            "2D drawing (*.svg *.dxf);;SVG (*.svg);;DXF (*.dxf)")
        if path:
            self._import_drawing_path(path)

    def _import_drawing_path(self, path):
        """An SVG / DXF as an import_2d shape in a new Object, extruded
        (OpenSCAD's import() gives a 2D shape; a flat part is useless
        in an assembly, so it arrives as a 3 mm plate to adjust)."""
        stem = Path(path).stem
        comp = self.model.new_component(stem)
        extrude = self.model.add_node("linear_extrude", dict(
            height=3.0, twist=0.0, scale=1.0, center=False, segments=0),
            parent=comp, name=f"Extrude {stem}")
        node = self.model.add_node("import_2d", dict(
            path=path, x=0.0, y=0.0, center=False, dpi=72.0, layer="",
            id="", segments=32), parent=extrude, name=f"{stem} drawing")
        self.builder.tree.select_nodes([comp])
        if not self.view3d.user_moved:
            self.view3d.fit()
        self.statusBar().showMessage(
            f"Imported {Path(path).name} as a 3 mm extrusion — select the "
            f"drawing to set its layer, DPI or centre, or the extrude to "
            f"change the height.", 10000)
        return node

    def import_surface(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import height map", "",
            "Height map (*.dat *.png *.jpg *.jpeg);;Heights (*.dat);;"
            "Picture (*.png *.jpg *.jpeg)")
        if path:
            self._import_surface_path(path)

    def _import_surface_path(self, path):
        """A .dat matrix or a picture as a surface() in a new Object."""
        stem = Path(path).stem
        comp = self.model.new_component(stem)
        node = self.model.add_node("surface", dict(
            file=path, center=True, invert=False, convexity=1),
            parent=comp, name=f"{stem} surface")
        self.builder.tree.select_nodes([comp])
        if not self.view3d.user_moved:
            self.view3d.fit()
        self.statusBar().showMessage(
            f"Imported {Path(path).name} as a surface — one cell per "
            f"value or pixel, heights 0 to 100 for a picture: wrap it in "
            f"a Scale or Resize to size it.", 10000)
        return node

    def import_stl(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import mesh", "",
            "Mesh (*.stl *.obj *.off *.3mf *.glb);;STL (*.stl);;"
            "Wavefront OBJ (*.obj);;OFF (*.off);;3MF (*.3mf);;"
            "glTF binary (*.glb)")
        if not path:
            return
        self._import_mesh_path(path)

    def _import_mesh_path(self, path):
        # OpenSCAD's import() renders STL/OFF/3MF but not OBJ, so convert
        # an OBJ to a sibling STL (from the same triangles the preview
        # uses) and point the node at that, so the exact render works too.
        use_path, note = path, ""
        ext = Path(path).suffix.lower()
        if ext in (".obj", ".glb"):
            from .engine import parse_mesh, write_stl
            tris = parse_mesh(path)
            if tris:
                stl_path = Path(path).with_name(
                    Path(path).stem + f"_from_{ext[1:]}.stl")
                try:
                    write_stl(tris, str(stl_path), Path(path).stem)
                    use_path = str(stl_path)
                    note = f" (converted to {stl_path.name} to render)"
                except OSError:
                    pass                     # fall back to the .obj path
        # an imported mesh arrives as one Object holding the whole
        # structure — it moves, snaps and lists as a single part
        comp = self.model.new_component(Path(path).stem)
        node = self.model.add_node("stl_import", dict(path=use_path),
                                   parent=comp,
                                   name=f"{Path(path).stem} mesh")
        self.builder.tree.select_nodes([comp])
        if not self.view3d.user_moved:
            self.view3d.fit()
        # the size first: an STL has no units, and a part drawn in
        # inches or metres is only obviously wrong once it is measured
        from .meshimport import size_text
        self.statusBar().showMessage(
            f"Imported {Path(path).name}"
            f"{size_text(node, unit=self.model.unit)}{note} — "
            "right-click ▸ Imported mesh to centre it, stand it on the "
            "floor or fix its units.", 12000)

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
        factor = self._export_scale()
        if factor is None:
            return
        if self.engine.available:
            error = self.engine.export_stl(self.model.to_scad(), path)
            if error:
                QMessageBox.warning(self, APP_NAME,
                                    f"OpenSCAD export failed:\n{error}")
                return
        else:
            from .engine import write_stl
            write_stl(mesh.tessellate(self.model.root), path)
        if factor != 1.0:
            units.scale_mesh_file(path, factor)
        if not self.engine.available and mesh.approximates(self.model.root):
            QMessageBox.information(
                self, APP_NAME,
                "Exported with the built-in tessellator: booleans are "
                "approximated. Install OpenSCAD for exact geometry.")

    def _export_scale(self):
        from . import units_ui
        return units_ui.export_scale(self)

    def publish_to_printables(self):
        """Build the Printables upload bundle for the open model."""
        from .printables import PublishDialog
        PublishDialog(self).exec_()

    def open_blueprint(self):
        """File ▸ Blueprint… — the 2D engineering drawing window."""
        from .blueprint import open_blueprint
        return open_blueprint(self)

    def _drawing_edited(self):
        """The Blueprint sheet lives in the document: an edit to it is
        an unsaved change (no preview to rebuild)."""
        if self.model.drawing is not None:
            self._dirty = True
            self._update_title()

    # -------------------------------------------------------------- MCP
    def mcp_bridge(self):
        """The MCP bridge for this window, created on first use."""
        if getattr(self, "_mcp_bridge", None) is None:
            from PyQt5.QtCore import QSettings
            from .mcp_bridge import (ACCESS_LEVELS, DEFAULT_ACCESS,
                                     McpBridge)
            self._mcp_bridge = McpBridge(self)
            level = QSettings("Kherve", "KherveCAD").value(
                "mcp/access", DEFAULT_ACCESS)
            self._mcp_bridge.set_access(
                level if level in ACCESS_LEVELS else DEFAULT_ACCESS)
            self._mcp_bridge.tool_invoked.connect(
                lambda name, _s: self.statusBar().showMessage(
                    f"MCP: {name}", 3000))
        return self._mcp_bridge

    def start_mcp_if_enabled(self):
        """Re-open the bridge when the user left it on last session."""
        from PyQt5.QtCore import QSettings
        if QSettings("Kherve", "KherveCAD").value(
                "mcp/enabled", False, type=bool):
            self.mcp_bridge().start()

    def _open_photo3d(self):
        """AI ▸ Mesh from Photo…: one picture -> a generated surface,
        imported as a mesh part (photo3d_dialog.py)."""
        from .photo3d_dialog import open_photo3d
        open_photo3d(self)

    def _open_mcp_dialog(self):
        """Open the MCP server control panel (non-modal)."""
        from .mcp_dialog import McpServerDialog
        dlg = McpServerDialog(self.mcp_bridge(), self)
        dlg.setAttribute(Qt.WA_DeleteOnClose)
        dlg.show()

    # ------------------------------------------------------------- misc
    def _update_title(self):
        name = Path(self._path).name if self._path else "Untitled"
        # `use <...>` resolves beside the open document, as in OpenSCAD
        from . import scadlib
        scadlib.DOCUMENT_DIR = str(Path(self._path).parent) \
            if self._path else None
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
        self._flush_blueprint()             # so the unsaved check sees it
        if self._confirm_discard():
            # The bridge holds a listening socket and an endpoint file
            # naming this process; both have to go with the window.
            if getattr(self, "_mcp_bridge", None) is not None:
                self._mcp_bridge.stop()
            # an OpenSCAD render still running must not outlive the
            # window that asked for it
            self.engine.shutdown()
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

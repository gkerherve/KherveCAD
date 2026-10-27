"""The main window's two toolbars.

- the **vertical** bar — 2D drawing tools, measuring tools and the 3D
  solids added with one click;
- the **horizontal** bar — file and undo, then the operations grouped
  into families (Extrude, Move & transform, Combine, Deform & sculpt,
  Character, Repeat & logic), assembly snapping, the sketch controls and
  the 3D view.

Twenty operation icons side by side made a bar nobody could read, so
each family is one `GroupButton`: a click runs the tool used last (it
is remembered), the small arrow lists the whole family. Every icon's
tooltip explains what it does and how to use it (tooltips.py).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtCore import QPointF, QSettings, QSize, Qt
from PyQt5.QtGui import QPainter, QPen, QPolygonF
from PyQt5.QtWidgets import (QAbstractSpinBox, QAction, QActionGroup,
                             QComboBox, QDoubleSpinBox, QLabel, QMenu,
                             QToolBar, QToolButton)

from . import icons, language, tooltips
from .model import NODE_TYPES
from .view2d import (CIRCLE, DIMENSION, LINE, MEASURE, PLANES, POLYGON,
                     RECT, SELECT, TEXT)

ICON_SIZE = QSize(28, 28)

#: (tool id, mdi icon, label, shortcut) for the 2D drawing tools. The
#: label is translated at the point of use (`_action`), not here — a
#: module-level dict is built once, before a language is chosen.
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
PRIMITIVES = ["cube", "sphere", "cylinder", "capsule", "ellipsoid",
              "rounded_box", "loft", "skin", "human"]
#: the ones with a button on the vertical bar (2026-10-17, the user: too
#: many buttons — Skin and Human stay in Insert ▸ 3D Solids)
BAR_PRIMITIVES = ["cube", "sphere", "cylinder", "capsule", "ellipsoid",
                  "rounded_box", "loft"]

#: the operation families of the horizontal bar, in order (applied to
#: the selection — Group and the control-flow tools insert an empty
#: node when nothing is selected).
OPERATION_GROUPS = [
    ("extrude", ["linear_extrude", "rotate_extrude", "sweep",
                 "section_loft"]),
    ("transform", ["translate", "rotate", "scale", "mirror", "resize",
                   "multmatrix"]),
    ("combine", ["union", "difference", "intersection", "render"]),
    ("finish", ["fillet", "bevel", "push_pull", "bisect", "hull",
                "minkowski"]),
    ("deform", ["blend", "bend", "twist", "taper", "lattice",
                "subdivide", "decimate", "remesh", "wireframe", "shell",
                "sculpt", "displace",
                "shrinkwrap"]),
    ("character", ["symmetry", "joint", "armature", "shape_keys", "paint",
                   "weathering",
                   "hair_cap", "hair_strands", "vertex_paint",
                   "cloth"]),
    ("logic", ["for_loop", "while_loop", "if_else", "pattern", "scatter",
               "intersection_for", "let"]),
]
OPERATIONS = [op for _key, ops in OPERATION_GROUPS for op in ops]

#: shortcuts shown in the operation tooltips (bound in the Edit menu)
_OP_SHORTCUTS = {"union": "Ctrl+G"}

_SETTINGS = ("Kherve", "KherveCAD")


class GroupButton(QToolButton):
    """One toolbar button for a family of tools. Clicking it runs the
    family's current tool — the one used last, remembered across
    sessions — and the arrow on its right opens the whole family."""

    ARROW_W = 11

    def __init__(self, key, actions, parent=None):
        super().__init__(parent)
        self.key = key
        self.family = list(actions)
        self.setPopupMode(QToolButton.MenuButtonPopup)
        self.setAutoRaise(True)
        title = language.tr(tooltips.GROUPS.get(key, (key, ""))[0])
        menu = QMenu(title, self)
        menu.setToolTipsVisible(True)       # the rich tips while browsing
        for act in self.family:
            menu.addAction(act)
        # through the menu, not each action: the actions belong to the
        # window and outlive this button when the Interface Style
        # rebuilds the bar (a slot on a deleted button would abort)
        menu.triggered.connect(
            lambda a: self.set_current(a, remember=True))
        self.setMenu(menu)
        # the theme hides menu arrows; draw our own chevron (paintEvent)
        # in a slim strip that still opens the menu when clicked
        self.setStyleSheet(
            f"QToolButton {{ padding-right: {self.ARROW_W + 2}px; }}"
            f"QToolButton::menu-button {{ border: none; background: "
            f"transparent; width: {self.ARROW_W}px; }}"
            "QToolButton::menu-arrow { image: none; }")
        saved = QSettings(*_SETTINGS).value(f"toolbar/{key}", "")
        self.set_current(next((a for a in self.family
                               if a.data() == saved), self.family[0]))

    def set_current(self, action, remember=False):
        """Make *action* the one a plain click runs."""
        self.setDefaultAction(action)
        labels = [a.text() for a in self.family]
        self.setToolTip(tooltips.rich(
            action.data(), _OP_SHORTCUTS.get(action.data(), ""),
            footer=tooltips.group_footer(self.key, labels)))
        if remember:
            QSettings(*_SETTINGS).setValue(f"toolbar/{self.key}",
                                           action.data())

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        color = self.palette().color(self.foregroundRole())
        color.setAlpha(170)
        painter.setPen(QPen(color, 1.4))
        cx = self.width() - self.ARROW_W / 2.0 - 1.5
        cy = self.height() / 2.0 + 1.0
        painter.drawPolyline(QPolygonF([QPointF(cx - 3, cy - 1.5),
                                        QPointF(cx, cy + 1.5),
                                        QPointF(cx + 3, cy - 1.5)]))
        painter.end()


def remember_glyph(act, glyph, family=None):
    """Note the glyph an action's icon was made from, so an Interface
    Style can paint its own icon and the classic one can come back
    (toolbar_style.restyle_icons)."""
    act.setProperty("kc_glyph", glyph)
    act.setProperty("kc_family", family or "")


def _action(win, glyph, text, key, slot=None, shortcut="",
            checkable=False, bind=True, family=None):
    """A toolbar action with its rich tooltip. *bind* False shows the
    shortcut in the tip without claiming it — a menu already owns it,
    and two actions on one key make Qt ignore both. *family* colours
    the glyph (icons.FAMILY_COLORS)."""
    color = icons.family_color(family) if family else None
    act = QAction(icons.icon(glyph, color), language.tr(text), win)
    act.setData(key)
    remember_glyph(act, glyph, family)
    act.setCheckable(checkable)
    if shortcut and bind:
        act.setShortcut(shortcut)
    tooltips.apply(act, key, shortcut)
    if slot is not None:
        act.triggered.connect(slot)
    return act


def build_tool_bar(win):
    """The vertical bar: drawing tools, measuring, 3D solids."""
    bar = QToolBar("Tools")
    bar.setObjectName("tools_bar")
    bar.setIconSize(ICON_SIZE)
    bar.setMovable(False)
    win.addToolBar(Qt.LeftToolBarArea, bar)
    win._tool_group = QActionGroup(win)
    #: (caption, first action) per section, for the Fusion captions
    win._tool_sections = []
    for tools, family in ((TOOLS, "draw"), (MEASURE_TOOLS, "measure")):
        win._tool_sections.append(("Sketch" if family == "draw"
                                   else "Inspect", None))
        for tool, glyph, label, shortcut in tools:
            act = _action(win, glyph, label, tool,
                          lambda _=False, t=tool: win._set_tool(t),
                          shortcut, checkable=True,
                          family=None if tool == SELECT else family)
            win._tool_group.addAction(act)
            bar.addAction(act)
            if win._tool_sections[-1][1] is None:
                win._tool_sections[-1] = (win._tool_sections[-1][0], act)
        bar.addSeparator()
    # Fusion's other SKETCH ▸ CREATE tools (sketch_tools.py): in the tool
    # group, the ribbon and Insert ▸ 2D Shapes, not on the classic bar
    from . import sketch_tools
    for tool, glyph, label, shortcut in sketch_tools.TOOLS:
        act = _action(win, glyph, label, tool,
                      lambda _=False, t=tool: win._set_tool(t),
                      shortcut, checkable=True, family="draw")
        win._tool_group.addAction(act)
    win._tool_group.actions()[0].setChecked(True)
    for prim in BAR_PRIMITIVES:
        spec = NODE_TYPES[prim]
        act = _action(win, spec["icon"], spec["label"], prim,
                      lambda _=False, t=prim: win._add_primitive(t))
        if prim == BAR_PRIMITIVES[0]:
            win._tool_sections.append(("Solids", act))
        bar.addAction(act)
    bar.addSeparator()

    # Human, Skin and the City Builder left the bar (2026-10-17, the
    # user): Insert ▸ 3D Solids and Library ▸ City still have them
    def _house_builder():
        from . import house_dialog
        house_dialog.open_builder(win)

    act = _action(win, "mdi.home-city-outline", "House Builder",
                  "house_builder", _house_builder, family="build")
    win._tool_sections.append(("Build", act))
    bar.addAction(act)
    return bar


def build_options_bar(win):
    """The horizontal bar. Its actions are made once (`make_bar_actions`)
    and laid out by the Interface Style: `fill_classic` here, or the
    quick-access row over a ribbon (toolbar_style.py)."""
    bar = QToolBar("Options")
    bar.setObjectName("options_bar")
    bar.setIconSize(ICON_SIZE)
    bar.setMovable(False)
    win.addToolBar(Qt.TopToolBarArea, bar)
    make_bar_actions(win)
    fill_classic(win, bar)
    return bar


def make_bar_actions(win):
    """Every action of the horizontal bar, once per window, in
    `win._bar_parts` — they belong to the window, so laying the bar out
    again (another Interface Style) keeps their state and shortcuts."""
    parts = {}
    # -- file
    parts["file"] = [
        _action(win, "mdi.file-outline", "New", "new", win.new_document),
        _action(win, "mdi.folder-open-outline", "Open", "open",
                win.open_file),
        _action(win, "mdi.content-save-outline", "Save", "save",
                win.save_file)]
    # -- undo
    parts["undo"] = []
    for make, glyph, text, key, keys in (
            (win.model.undo_stack.createUndoAction, "mdi.undo", "Undo",
             "undo", "Ctrl+Z"),
            (win.model.undo_stack.createRedoAction, "mdi.redo", "Redo",
             "redo", "Ctrl+Y")):
        act = make(win)
        act.setIcon(icons.icon(glyph))
        act.setData(key)
        remember_glyph(act, glyph)
        act.setText(language.tr(text))
        tooltips.apply(act, key, keys)
        parts["undo"].append(act)
    # -- operations, one family each
    parts["families"] = []
    for key, ops in OPERATION_GROUPS:
        family = []
        for op in ops:
            spec = NODE_TYPES[op]
            family.append(_action(
                win, spec["icon"], spec["label"], op,
                lambda _=False, o=op: win._apply_operation(o),
                _OP_SHORTCUTS.get(op, ""), bind=False,  # Edit menu's
                family=key))
        parts["families"].append((key, family))
    # Blender's Edit Mode: Tab over the 3D view (View3D.tab_pressed)
    win._edit_mesh_act = _action(win, "mdi.vector-polyline-edit",
                                 "Edit vertices", "edit_mesh",
                                 shortcut="Tab", checkable=True,
                                 bind=False, family="edit")
    win._edit_mesh_act.toggled.connect(
        lambda on: win.set_edit_mode(bool(on)))
    # -- assembly
    parts["snap"] = _action(win, "mdi.magnet-on", "Snap objects",
                            "snap_objects", win._start_snap, "J")

    # -- sketch: grid, snap and the plane live on the 2D view's own bar
    # (viewnav.add_sketch_controls); the actions stay for the shortcuts
    # and the View menu
    win._grid_act = _action(win, "mdi.grid", "Grid", "grid",
                            shortcut="Ctrl+'", checkable=True)
    win._grid_act.setChecked(win.scene.show_grid)
    win._grid_act.toggled.connect(win._set_show_grid)
    win._snap_act = _action(win, "mdi.magnet", "Snap", "grid_snap",
                            shortcut="Ctrl+Shift+'", checkable=True)
    win._snap_act.setChecked(win.scene.snap_enabled)
    win._snap_act.toggled.connect(win._set_snap)
    win.addAction(win._grid_act)
    win.addAction(win._snap_act)

    # -- 3D
    # Render and Fit 3D left the bar (2026-10-16, the user: obsolete — the
    # exact render runs by itself and the 3D view's own bar fits); F5
    # still forces a render from anywhere in the window
    win.addAction(_action(win, "mdi.play-outline", "Render", "render",
                          win._render_now, "F5"))
    parts["docs"] = [
        _action(win, "mdi.drawing-box", "Blueprint", "blueprint",
                win.open_blueprint, "Ctrl+Shift+D", bind=False,
                family="docs"),                        # File menu's
        _action(win, "mdi.format-list-numbered", "Bill of materials",
                "bom", win.open_bom, "Ctrl+Alt+B", bind=False,
                family="docs"),
        _action(win, "mdi.pipe", "P&&ID (process diagram)", "pid",
                win.open_pid, "Ctrl+Alt+I", bind=False, family="docs")]
    win._cut_tool_act = _action(win, "mdi.content-cut", "Cut through",
                                "cut_through", shortcut="Ctrl+Alt+X",
                                checkable=True, bind=False)  # View menu's
    win._cut_tool_act.toggled.connect(lambda on: win.set_cut(bool(on)))
    win.addAction(win._cut_tool_act)      # the 3D view's bar has the button

    # -- the 3D-only layout for building with an assistant (the ChatBox
    # stays in the AI menu, Ctrl+/; it no longer earns a toolbar button).
    # Icon only (2026-10-17, the user: the name made it too long); the
    # tooltip still names it
    win._vibe_act = _action(win, "mdi.creation", "Vibe Model",
                            "vibe_model", shortcut="Ctrl+Shift+M",
                            checkable=True, family="brand")
    win._vibe_act.toggled.connect(win.set_vibe_model)
    win._bar_parts = parts
    return parts


def fill_classic(win, bar):
    """KherveCAD's own layout, left to right: file, undo, the operation
    families as drop-down buttons, assembly snapping, the engineering
    documents and Vibe Model — a separator between each section."""
    parts = win._bar_parts
    for act in parts["file"]:
        bar.addAction(act)
    bar.addSeparator()
    for act in parts["undo"]:
        bar.addAction(act)
    bar.addSeparator()
    # Vibe Model hides the rest of the bar: talking to an assistant
    # needs file and undo, not the modelling tools
    win._vibe_keep = set(bar.actions())
    win._op_groups = {}
    for key, family in parts["families"]:
        if key == "logic":
            bar.addAction(win._edit_mesh_act)    # just before the loops
        button = GroupButton(key, family, bar)
        button.setIconSize(ICON_SIZE)
        bar.addWidget(button)
        win._op_groups[key] = button
    bar.addSeparator()
    bar.addAction(parts["snap"])
    bar.addSeparator()
    for act in parts["docs"]:
        bar.addAction(act)
    bar.addSeparator()
    bar.addAction(win._vibe_act)
    win._vibe_keep.add(win._vibe_act)


#: (submenu title, tool keys) of the Insert menu's groups that are not
#: operation families; the families follow, in the toolbar's own order
INSERT_EXTRAS = [
    ("Code && files", ["assign", "echo", "assert", "stl_import",
                       "scad_raw", "sheet_metal"]),
    ("&Mechanical features", ["gear", "thread", "hole", "knurl",
                              "textured"]),
    ("Shapes && &patterns", ["curve", "polyhedron_solid", "star",
                             "rounded_polygon", "bezier_shape", "svg_path",
                             "honeycomb"]),
]


#: operation families that work on what is already there — the Tools
#: menu; the others (Repeat & logic) add a node and stay under Insert
TOOL_FAMILIES = ("extrude", "transform", "combine", "finish", "deform",
                 "character")


def _family_menus(win, menu, keys):
    """One submenu per operation family named in *keys*, in the
    toolbar's own order."""
    for key, ops in OPERATION_GROUPS:
        if key not in keys:
            continue
        title = language.tr(
            tooltips.GROUPS.get(key, (key, ""))[0]).replace("&", "&&")
        sub = menu.addMenu(icons.icon(NODE_TYPES[ops[0]]["icon"]), title)
        sub.setToolTipsVisible(True)
        for op in ops:
            spec = NODE_TYPES[op]
            sub.addAction(_action(
                win, spec["icon"], spec["label"], op,
                lambda _=False, o=op: win._apply_operation(o),
                _OP_SHORTCUTS.get(op, ""), bind=False))


def build_insert_menu(win, menu):
    """What ADDS something, as a menu: the drawing tools, the solids,
    Repeat & logic, code and files, features — the same tables the
    toolbars are built from, so the two never disagree. The drawing
    tools are the toolbar's own checkable actions (the tick shows the
    tool in use); the rest run the same slot as their button, with the
    same how-to tooltip. What changes the selection is in Tools."""
    menu.setToolTipsVisible(True)
    shapes = menu.addMenu(icons.icon("mdi.vector-polygon"),
                          language.tr("&2D Shapes"))
    shapes.setToolTipsVisible(True)
    by_key = {a.data(): a for a in win._tool_group.actions()}
    from . import sketch_tools
    for tool, _glyph, _label, _key in TOOLS[1:] + sketch_tools.TOOLS:
        shapes.addAction(by_key[tool])
    solids = menu.addMenu(icons.icon("mdi.cube-outline"),
                          language.tr("3D &Solids"))
    solids.setToolTipsVisible(True)
    for prim in PRIMITIVES:
        spec = NODE_TYPES[prim]
        solids.addAction(_action(
            win, spec["icon"], spec["label"], prim,
            lambda _=False, t=prim: win._add_primitive(t)))

    def _subd_box():
        from . import subd
        parent = win.builder.isolated_component()
        node = subd.insert_box(win.model, parent)
        if parent is None:
            win._geometry_created_in_main(node)
        win.statusBar().showMessage(language.tr(
            "SubD box: press Tab over the 3D view to edit its cage — drag "
            "points, E to extrude a face — and the smooth surface "
            "follows."), 12000)
    menu.addAction(_action(win, "mdi.circle-box-outline",
                           "SubD &Box (smooth, edit its cage)", "subd",
                           _subd_box))

    def _draw_curve():
        from . import curve_draw
        curve_draw.start(win)
    menu.addAction(_action(win, "mdi.vector-curve",
                           "Draw 3D &Curve (click points)", "draw_curve",
                           _draw_curve, "Ctrl+Alt+C"))
    menu.addSeparator()
    _family_menus(win, menu, [k for k, _ops in OPERATION_GROUPS
                              if k not in TOOL_FAMILIES])
    menu.addSeparator()
    for title, keys in INSERT_EXTRAS:
        sub = menu.addMenu(icons.icon("mdi.code-braces"), language.tr(title))
        sub.setToolTipsVisible(True)
        for key in keys:
            spec = NODE_TYPES[key]
            sub.addAction(_action(
                win, spec["icon"], spec["label"], key,
                lambda _=False, t=key: win._add_primitive(t)))
    from . import sheet_metal_ui
    sheet_metal_ui.build_menu(win, menu)
    return menu


def build_tools_menu(win, menu):
    """What WORKS ON the selection, as a menu: the operation families
    that wrap it (extrude, move, combine, finish, deform, character),
    Edit Mode, snapping parts together, measuring."""
    menu.setToolTipsVisible(True)
    _family_menus(win, menu, TOOL_FAMILIES)
    menu.addSeparator()
    edit = _action(win, "mdi.vector-polyline-edit",
                   "Edit &Vertices (Edit Mode)", "edit_mesh",
                   lambda _=False: win.set_edit_mode(None), "Tab",
                   bind=False)
    edit.setText(edit.text() + "\tTab")       # shown, the view owns Tab
    menu.addAction(edit)
    def _to_subd():
        from . import subd
        nodes = win.builder.active_tree().selected_nodes()
        if len(nodes) != 1:
            win.statusBar().showMessage(language.tr(
                "Convert to SubD: select one solid first."), 6000)
            return
        try:
            node = subd.convert(win.model, nodes[0],
                                win.model.effective_fn())
        except ValueError as exc:
            win.statusBar().showMessage(language.tr(str(exc)), 8000)
            return
        win.builder.active_tree().select_nodes([node])
        win.statusBar().showMessage(language.tr(
            "Now a SubD: Tab edits its cage; Smoothness and creases are "
            "in Properties."), 10000)
    menu.addAction(_action(win, "mdi.circle-box-outline",
                           "Convert to &SubD (smooth cage)", "subd",
                           _to_subd))
    surf = menu.addMenu(icons.icon("mdi.vector-curve"),
                        language.tr("Surface from &Curves"))
    surf.setToolTipsVisible(True)
    from . import curve_surface, curve_surface_ui
    for kind, label in curve_surface.KIND_LABELS:
        surf.addAction(_action(
            win, "mdi.vector-curve", label, "curve_surface",
            lambda _=False, k=kind: curve_surface_ui.from_selection(win, k)))
    menu.addAction(_action(win, "mdi.magnet-on", "Snap objects",
                           "snap_objects", win._start_snap, "J",
                           bind=False))
    # the sketch's CONSTRAIN panel (sketch_constrain_ui.py)
    from . import sketch_constrain_ui
    cons = menu.addMenu(icons.icon("mdi.vector-link"),
                        language.tr("Sketch &Constraints"))
    cons.setToolTipsVisible(True)
    for act in sketch_constrain_ui.panel_actions(win):
        cons.addAction(act)
    from . import sketch_modify
    mod = menu.addMenu(icons.icon("mdi.content-cut"),
                       language.tr("Sketch &Modify"))
    mod.setToolTipsVisible(True)
    for act in sketch_modify.panel_actions(win):
        mod.addAction(act)
    measure = menu.addMenu(icons.icon("mdi.tape-measure"),
                           language.tr("&Measure && annotate"))
    measure.setToolTipsVisible(True)
    by_key = {a.data(): a for a in win._tool_group.actions()}
    for tool, _glyph, _label, _key in MEASURE_TOOLS:
        measure.addAction(by_key[tool])
    # the builders (2026-10-17, the user: what left the vertical bar
    # must still be under Tools — the Library menu has them too)
    menu.addSection(language.tr("Builders"))
    import importlib

    def _builder(module):
        def run(_=False):
            importlib.import_module("khervecad." + module).open_builder(win)
        return run
    for glyph, label, module, key in (
            ("mdi.home-city-outline", "&House Builder...", "house_dialog",
             "house_builder"),
            ("mdi.city-variant-outline", "C&ity Builder...", "city_dialog",
             "city_builder"),
            ("mdi.human-handsup", "H&uman Builder...", "human_dialog",
             "human_builder"),
            ("mdi.car-sports", "Ca&r Builder...", "car_dialog",
             "car_builder"),
            ("mdi.toy-brick-outline", "&Lego Builder...", "lego_builder",
             "lego_builder"),
            ("mdi.atom", "Cr&ystal Builder...", "crystal_dialog",
             "crystal_builder"),
            ("mdi.molecule", "C&ompound Builder...", "molecule_dialog",
             "compound_builder"),
            ("mdi.flask-outline", "C&hemistry Builder...", "chem_dialog",
             "chemistry_builder")):
        act = menu.addAction(icons.icon(glyph, icons.family_color(
            "build")), language.tr(label), _builder(module))
        act.setData(key)
        remember_glyph(act, glyph, "build")
        # the ribbon's BUILD tab shows these same actions
        win.__dict__.setdefault("_builder_actions", []).append(act)
    figures = menu.addMenu(icons.icon("mdi.human", icons.family_color(
        "character")), language.tr("Add a &figure"))
    figures.setToolTipsVisible(True)
    for prim in ("human", "skin"):
        spec = NODE_TYPES[prim]
        figures.addAction(_action(
            win, spec["icon"], spec["label"], prim,
            lambda _=False, t=prim: win._add_primitive(t)))
    # the engineering documents of the design (also in the File menu,
    # which owns their shortcuts)
    menu.addSection(language.tr("Engineering documents"))
    for glyph, label, key, slot, keys in (
            ("mdi.drawing-box", "&Blueprint (2D drawing)...", "blueprint",
             win.open_blueprint, "Ctrl+Shift+D"),
            ("mdi.format-list-numbered", "Bill of &Materials...", "bom",
             win.open_bom, "Ctrl+Alt+B"),
            ("mdi.pipe", "P&&&ID (Process Diagram)...", "pid",
             win.open_pid, "Ctrl+Alt+I")):
        act = _action(win, glyph, label, key, slot, keys, bind=False)
        act.setText(act.text() + "\t" + keys)
        menu.addAction(act)
    return menu

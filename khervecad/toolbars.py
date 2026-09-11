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

from . import icons, tooltips
from .model import NODE_TYPES
from .view2d import (CIRCLE, DIMENSION, LINE, MEASURE, PLANES, POLYGON,
                     RECT, SELECT, TEXT)

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
PRIMITIVES = ["cube", "sphere", "cylinder", "capsule", "ellipsoid",
              "rounded_box", "loft"]

#: the operation families of the horizontal bar, in order (applied to
#: the selection — Group and the control-flow tools insert an empty
#: node when nothing is selected).
OPERATION_GROUPS = [
    ("extrude", ["linear_extrude", "rotate_extrude", "sweep"]),
    ("transform", ["translate", "rotate", "scale", "mirror"]),
    ("combine", ["union", "difference", "intersection"]),
    ("deform", ["blend", "bend", "twist", "taper", "lattice",
                "subdivide"]),
    ("character", ["symmetry", "joint"]),
    ("logic", ["for_loop", "while_loop", "if_else"]),
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
        title = tooltips.GROUPS.get(key, (key, ""))[0]
        menu = QMenu(title, self)
        menu.setToolTipsVisible(True)       # the rich tips while browsing
        for act in self.family:
            menu.addAction(act)
            act.triggered.connect(
                lambda _=False, a=act: self.set_current(a, remember=True))
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


def _action(win, glyph, text, key, slot=None, shortcut="",
            checkable=False, bind=True):
    """A toolbar action with its rich tooltip. *bind* False shows the
    shortcut in the tip without claiming it — a menu already owns it,
    and two actions on one key make Qt ignore both."""
    act = QAction(icons.icon(glyph), text, win)
    act.setData(key)
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
    for tools in (TOOLS, MEASURE_TOOLS):
        for tool, glyph, label, shortcut in tools:
            act = _action(win, glyph, label, tool,
                          lambda _=False, t=tool: win._set_tool(t),
                          shortcut, checkable=True)
            win._tool_group.addAction(act)
            bar.addAction(act)
        bar.addSeparator()
    win._tool_group.actions()[0].setChecked(True)
    for prim in PRIMITIVES:
        spec = NODE_TYPES[prim]
        bar.addAction(_action(
            win, spec["icon"], spec["label"], prim,
            lambda _=False, t=prim: win._add_primitive(t)))
    return bar


def build_options_bar(win):
    """The horizontal bar, left to right: file, undo, the operation
    families, assembly snapping, the sketch controls, the 3D view and
    the assistant — a separator between each section."""
    bar = QToolBar("Options")
    bar.setObjectName("options_bar")
    bar.setIconSize(ICON_SIZE)
    bar.setMovable(False)
    win.addToolBar(Qt.TopToolBarArea, bar)

    # -- file
    bar.addAction(_action(win, "mdi.file-outline", "New", "new",
                          win.new_document))
    bar.addAction(_action(win, "mdi.folder-open-outline", "Open", "open",
                          win.open_file))
    bar.addAction(_action(win, "mdi.content-save-outline", "Save",
                          "save", win.save_file))
    bar.addSeparator()

    # -- undo
    for make, glyph, text, key, keys in (
            (win.model.undo_stack.createUndoAction, "mdi.undo", "Undo",
             "undo", "Ctrl+Z"),
            (win.model.undo_stack.createRedoAction, "mdi.redo", "Redo",
             "redo", "Ctrl+Y")):
        act = make(win)
        act.setIcon(icons.icon(glyph))
        act.setText(text)
        tooltips.apply(act, key, keys)
        bar.addAction(act)
    bar.addSeparator()

    # -- operations, one button per family
    win._op_groups = {}
    for key, ops in OPERATION_GROUPS:
        family = []
        for op in ops:
            spec = NODE_TYPES[op]
            family.append(_action(
                win, spec["icon"], spec["label"], op,
                lambda _=False, o=op: win._apply_operation(o),
                _OP_SHORTCUTS.get(op, ""), bind=False))  # Edit menu's
        button = GroupButton(key, family, bar)
        button.setIconSize(ICON_SIZE)
        bar.addWidget(button)
        win._op_groups[key] = button
    bar.addSeparator()

    # -- assembly
    bar.addAction(_action(win, "mdi.magnet-on", "Snap objects",
                          "snap_objects", win._start_snap, "J"))
    bar.addSeparator()

    # -- sketch
    win._grid_act = _action(win, "mdi.grid", "Grid", "grid",
                            shortcut="Ctrl+'", checkable=True)
    win._grid_act.setChecked(win.scene.show_grid)
    win._grid_act.toggled.connect(win._set_show_grid)
    bar.addAction(win._grid_act)
    win._snap_act = _action(win, "mdi.magnet", "Snap", "grid_snap",
                            shortcut="Ctrl+Shift+'", checkable=True)
    win._snap_act.setChecked(win.scene.snap_enabled)
    win._snap_act.toggled.connect(win._set_snap)
    bar.addAction(win._snap_act)
    bar.addWidget(QLabel(" Grid "))
    win._grid_spin = QDoubleSpinBox()
    win._grid_spin.setDecimals(2)                   # down to 0.01 mm
    win._grid_spin.setRange(0.01, 1000.0)
    win._grid_spin.setSingleStep(0.5)
    # step in proportion to the value (0.6, 0.7… near 0.5; 6, 7… near 5)
    win._grid_spin.setStepType(QAbstractSpinBox.AdaptiveDecimalStepType)
    win._grid_spin.setSuffix(" mm")
    win._grid_spin.setValue(win.scene.grid_size)
    win._grid_spin.valueChanged.connect(win._set_grid_size)
    tooltips.apply(win._grid_spin, "grid_size")
    bar.addWidget(win._grid_spin)
    bar.addWidget(QLabel(" Plane "))
    win._plane_combo = QComboBox()
    win._plane_combo.addItems(list(PLANES))
    tooltips.apply(win._plane_combo, "plane")
    win._plane_combo.currentTextChanged.connect(win._set_plane)
    bar.addWidget(win._plane_combo)
    bar.addAction(_action(win, "mdi.fit-to-page-outline", "Fit sketch",
                          "fit_sketch", win.view2d.fit_content,
                          "Ctrl+Shift+F", bind=False))     # View menu's
    bar.addSeparator()

    # -- 3D
    bar.addAction(_action(win, "mdi.play-outline", "Render", "render",
                          win._render_now, "F5"))
    bar.addAction(_action(win, "mdi.arrow-expand-all", "Fit 3D", "fit_3d",
                          win.view3d.fit))
    bar.addSeparator()

    # -- assistant, and the 3D-only layout for building with one
    bar.addAction(_action(
        win, "mdi.robot-outline", "Assistant", "assistant",
        lambda: win._chat_dock.setVisible(not win._chat_dock.isVisible())))
    win._vibe_act = _action(win, "mdi.creation", "Vibe Model",
                            "vibe_model", shortcut="Ctrl+Shift+M",
                            checkable=True)
    win._vibe_act.toggled.connect(win.set_vibe_model)
    bar.addAction(win._vibe_act)
    # named on the bar: the only toggle that changes the whole window
    bar.widgetForAction(win._vibe_act).setToolButtonStyle(
        Qt.ToolButtonTextBesideIcon)
    return bar

"""Cut Through's controls: the floating bar along the bottom of the 3D
view, and View ▸ Cut Through in the main window. The geometry is
cutaway.py (Qt-free); `View3D.set_cut` applies it to what is shown.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QAction, QActionGroup, QGridLayout, QLabel,
                             QSlider, QToolButton, QWidget)


def _unit(view) -> str:
    """The unit symbol of the document the 3D *view* shows."""
    from .units import symbol
    model = getattr(view.window(), "model", None)
    return symbol(getattr(model, "unit", "mm"))


class CutBar(QWidget):
    """Floating controls for View ▸ Cut Through, along the bottom of the
    3D view while a cut is on: the axis the model is sliced across, a
    slider for where, which half stays, and a close button."""

    def __init__(self, view):
        super().__init__(view)
        self.view = view
        self.setObjectName("cutBar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            "#cutBar { background: rgba(24, 27, 31, 190);"
            " border: 1px solid rgba(255, 255, 255, 40);"
            " border-radius: 6px; }"
            "#cutBar QLabel { color: #e6e9ec; font-size: 11px; }"
            "#cutBar QToolButton { color: #e6e9ec; background: transparent;"
            " border: 1px solid transparent; border-radius: 3px;"
            " font-size: 12px; font-weight: bold; padding: 1px 5px; }"
            "#cutBar QToolButton:hover { border-color: rgba(255,255,255,70); }"
            "#cutBar QToolButton:checked { color: #1d1f22;"
            " background: #ffb347; }")
        grid = QGridLayout(self)
        grid.setContentsMargins(8, 4, 6, 4)
        grid.setHorizontalSpacing(4)
        grid.addWidget(QLabel("Cut", self), 0, 0)
        self.axis_buttons = {}
        for col, axis in enumerate("xyz", 1):
            button = QToolButton(self)
            button.setText(axis.upper())
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.setToolTip(f"Slice across the {axis.upper()} axis")
            button.clicked.connect(
                lambda _=False, a=axis: self.view.set_cut(axis=a))
            grid.addWidget(button, 0, col)
            self.axis_buttons[axis] = button
        down = QToolButton(self)
        down.setText("−")
        down.setToolTip("Move the cut back a little (Ctrl+Alt+Down)")
        down.setAutoRepeat(True)
        down.clicked.connect(lambda: self._step(-0.02))
        grid.addWidget(down, 0, 4)
        self.slider = QSlider(Qt.Horizontal, self)
        self.slider.setRange(0, 1000)
        self.slider.setFixedWidth(170)
        self.slider.setPageStep(50)
        self.slider.setToolTip("Where the cut goes, across the whole model "
                               "— the arrow keys nudge it a tenth of a "
                               "percent")
        self.slider.valueChanged.connect(
            lambda value: self.view.set_cut(position=value / 1000.0))
        grid.addWidget(self.slider, 0, 5)
        up = QToolButton(self)
        up.setText("+")
        up.setToolTip("Move the cut on a little (Ctrl+Alt+Up)")
        up.setAutoRepeat(True)
        up.clicked.connect(lambda: self._step(0.02))
        grid.addWidget(up, 0, 6)
        self.readout = QLabel("", self)
        self.readout.setMinimumWidth(120)
        grid.addWidget(self.readout, 0, 7)
        flip = QToolButton(self)
        flip.setText("⇄")
        flip.setToolTip("Keep the other half")
        flip.clicked.connect(lambda: self.view.set_cut(
            flip=not (self.view.cut or {}).get("flip", False)))
        grid.addWidget(flip, 0, 8)
        close = QToolButton(self)
        close.setText("✕")
        close.setToolTip("Stop cutting — show the whole model")
        close.clicked.connect(lambda: self.view.set_cut(enabled=False))
        grid.addWidget(close, 0, 9)

    def _step(self, delta):
        where = (self.view.cut or {}).get("position", 0.5)
        self.view.set_cut(position=max(0.0, min(1.0, where + delta)))

    def sync(self):
        cut = self.view.cut
        if cut is None:
            return
        for axis, button in self.axis_buttons.items():
            button.setChecked(axis == cut["axis"])
        self.slider.blockSignals(True)
        self.slider.setValue(int(round(cut["position"] * 1000)))
        self.slider.blockSignals(False)
        self.readout.setText(f"{cut['axis'].upper()} = "
                             f"{cut.get('offset', 0.0):.1f} "
                             f"{_unit(self.view)}  ·  "
                             f"{cut['position'] * 100:.0f} %")


def build_menu(win, view_menu):
    """View ▸ Cut Through: on/off, which axis, which half."""
    from . import icons
    menu = win._cut_menu = view_menu.addMenu(icons.icon("mdi.content-cut"),
                                             "C&ut Through")
    win._cut_act = QAction("&Cut Through the Model", win, checkable=True)
    win._cut_act.setShortcut("Ctrl+Alt+X")
    win._cut_act.setStatusTip(
        "Slice the 3D view with a plane and cap the cut face, to see the "
        "holes, walls and threads inside — the model itself is not cut")
    win._cut_act.triggered.connect(lambda on: win.set_cut(bool(on)))
    menu.addAction(win._cut_act)
    menu.addSeparator()
    win._cut_axes = QActionGroup(win)
    for axis, label in (("x", "Across &X (side to side)"),
                        ("y", "Across &Y (front to back)"),
                        ("z", "Across &Z (top to bottom)")):
        act = QAction(label, win, checkable=True)
        act.setData(axis)
        act.triggered.connect(lambda _=False, a=axis: win.set_cut(True, axis=a))
        win._cut_axes.addAction(act)
        menu.addAction(act)
    menu.addSeparator()
    # where the cut goes — the bar's slider does it finely, but a menu
    # (and the 3D view's own button) has no slider. Quarters alone were
    # too coarse for a house: every tenth, and a storey of its own.
    win._cut_positions = QActionGroup(win)
    where = menu.addMenu("&Where")
    for step in range(1, 10):
        value = step / 10.0
        act = QAction(f"At &{step}0 %", win, checkable=True)
        act.setData(value)
        act.triggered.connect(
            lambda _=False, v=value: win.set_cut(True, position=v))
        win._cut_positions.addAction(act)
        where.addAction(act)
    storeys = win._cut_storeys = menu.addMenu("Cut at a &Storey")
    storeys.aboutToShow.connect(lambda: _fill_storeys(win, storeys))
    _fill_storeys(win, storeys)
    for label, shortcut, delta in (("Move the Cut &Up", "Ctrl+Alt+Up", 0.02),
                                   ("Move the Cut &Down", "Ctrl+Alt+Down",
                                    -0.02)):
        act = QAction(label, win)
        act.setShortcut(shortcut)
        act.triggered.connect(lambda _=False, d=delta: step_cut(win, d))
        menu.addAction(act)
    menu.addSeparator()
    other = QAction("Keep the &Other Half", win)
    other.triggered.connect(lambda: win.set_cut(
        True, flip=not (win.view3d.cut or {}).get("flip", False)))
    menu.addAction(other)
    win.view3d.cut_changed.connect(win._sync_cut)
    sync(win)


def storey_positions(win):
    """[(label, position)] — where each storey of the document's house
    is cut through, as a fraction of the model's height. A two-storey
    house needs more than quarters, and these land in the right rooms."""
    house = getattr(getattr(win, "model", None), "house", None) or {}
    floors = house.get("floors") or []
    mesh = getattr(win.view3d, "model_mesh", None)
    if not floors or not mesh:
        return []
    try:
        zs = [p[2] for tri in mesh for p in tri]
    except (TypeError, IndexError):
        return []
    if not zs:
        return []
    z0, z1 = min(zs), max(zs)
    if z1 - z0 < 1e-6:
        return []
    from .house import PLAN_CUT, SLAB_THICKNESS, WALL_HEIGHT
    out, base = [], 0.0
    for floor in floors:
        level = base + PLAN_CUT
        out.append((str(floor.get("name") or "Floor"),
                    max(0.0, min(1.0, (level - z0) / (z1 - z0)))))
        base += (float(floor.get("wall_height", WALL_HEIGHT))
                 + float(floor.get("slab_thickness", SLAB_THICKNESS)))
    return out


def _fill_storeys(win, menu):
    """The storey entries, rebuilt each time the menu opens (the house
    and the model's height change under it)."""
    menu.clear()
    levels = storey_positions(win)
    menu.setEnabled(bool(levels))
    for name, value in levels:
        act = QAction(f"{name} (waist height)", win)
        act.triggered.connect(
            lambda _=False, v=value: win.set_cut(True, axis="z", position=v))
        menu.addAction(act)
    if not levels:
        menu.addAction(QAction("Build a house to cut it by storey", win))


def step_cut(win, delta):
    """Nudge the cut along its axis (the menu's Up/Down, the bar's
    - and + buttons)."""
    cut = win.view3d.cut_state()
    where = (cut or {}).get("position", 0.5)
    win.set_cut(True, position=max(0.0, min(1.0, where + delta)))


def set_cut(win, on=True, axis=None, position=None, flip=None):
    """Cut Through on or off (and which axis, where, which half), with a
    status line saying how to move it and how to get the whole back."""
    if not on:
        win.view3d.set_cut(enabled=False)
        win.statusBar().showMessage("The whole model again.", 4000)
        return
    win.view3d.set_cut(axis=axis, position=position, flip=flip)
    cut = win.view3d.cut_state()
    win.statusBar().showMessage(
        f"Cut through {cut['axis'].upper()} at {cut['offset']:.1f} "
        f"{_unit(win.view3d)} — "
        "slide it along the bar at the bottom of the 3D view; Ctrl+Alt+X "
        "shows the whole model again.", 8000)


def sync(win):
    """The menu entry and the toolbar button follow the 3D view."""
    cut = win.view3d.cut_state()
    for act in (getattr(win, "_cut_act", None),
                getattr(win, "_cut_tool_act", None)):
        if act is not None and act.isChecked() != (cut is not None):
            act.blockSignals(True)
            act.setChecked(cut is not None)
            act.blockSignals(False)
    group = getattr(win, "_cut_axes", None)
    for act in (group.actions() if group is not None else ()):
        act.setChecked(cut is not None and act.data() == cut["axis"])
    group = getattr(win, "_cut_positions", None)
    for act in (group.actions() if group is not None else ()):
        act.setChecked(cut is not None and
                       abs(float(act.data()) - cut["position"]) < 0.005)

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
        self.slider = QSlider(Qt.Horizontal, self)
        self.slider.setRange(0, 1000)
        self.slider.setFixedWidth(170)
        self.slider.setToolTip("Where the cut goes, across the whole model")
        self.slider.valueChanged.connect(
            lambda value: self.view.set_cut(position=value / 1000.0))
        grid.addWidget(self.slider, 0, 4)
        self.readout = QLabel("", self)
        self.readout.setMinimumWidth(78)
        grid.addWidget(self.readout, 0, 5)
        flip = QToolButton(self)
        flip.setText("⇄")
        flip.setToolTip("Keep the other half")
        flip.clicked.connect(lambda: self.view.set_cut(
            flip=not (self.view.cut or {}).get("flip", False)))
        grid.addWidget(flip, 0, 6)
        close = QToolButton(self)
        close.setText("✕")
        close.setToolTip("Stop cutting — show the whole model")
        close.clicked.connect(lambda: self.view.set_cut(enabled=False))
        grid.addWidget(close, 0, 7)

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
                             f"{_unit(self.view)}")


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
    # (and the 3D view's own button) has no slider
    win._cut_positions = QActionGroup(win)
    for value, label in ((0.25, "Cut at a &Quarter"),
                         (0.5, "Cut Through the &Middle"),
                         (0.75, "Cut at &Three Quarters")):
        act = QAction(label, win, checkable=True)
        act.setData(value)
        act.triggered.connect(
            lambda _=False, v=value: win.set_cut(True, position=v))
        win._cut_positions.addAction(act)
        menu.addAction(act)
    menu.addSeparator()
    other = QAction("Keep the &Other Half", win)
    other.triggered.connect(lambda: win.set_cut(
        True, flip=not (win.view3d.cut or {}).get("flip", False)))
    menu.addAction(other)
    win.view3d.cut_changed.connect(win._sync_cut)
    sync(win)


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

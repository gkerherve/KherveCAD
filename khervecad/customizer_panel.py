"""View ▸ Customizer: OpenSCAD's Customizer pane for a KherveCAD document.

The document's annotated variables (customizer.py) as a panel of their
own, docked beside the 3D view: one box per ``/* [Group] */`` tab, each
variable a row with its description, its control (slider, drop-down,
checkbox, text) and its current value. Dragging a slider changes the
variable at once, so everything whose size or angle reads it moves in
the views while you drag. A slider's ▶ button sweeps it back and forth
through its range — a motor angle turns the gear train, a lid opens —
until pressed again.

It opens by itself when a document with annotated variables is loaded
(unless closed for that document), and edits are ordinary model edits:
undoable, saved, and written back to the program.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QDockWidget, QGroupBox,
                             QHBoxLayout, QLabel, QLineEdit, QScrollArea,
                             QSlider, QToolButton, QVBoxLayout, QWidget)

from . import customizer, expr, icons

#: sweep speed of a playing slider
PLAY_INTERVAL_MS = 60


def annotated(model):
    """The document's global variables that carry Customizer controls
    (not Hidden), in document order."""
    return [n for n in model.global_assigns()
            if customizer.widget(n) is not None and not customizer.hidden(n)
            and str(n.params.get("options") or "").strip()]


def _fmt(value):
    if isinstance(value, float) and value == int(value):
        return str(int(value))
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)


class CustomizerPanel(QWidget):
    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model
        self._rows = {}               # node id -> (node, value label, control)
        self._updating = False
        self._playing = None          # (slider, direction)
        self._timer = QTimer(self)
        self._timer.setInterval(PLAY_INTERVAL_MS)
        self._timer.timeout.connect(self._tick)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        self.empty = QLabel(
            "No adjustable variables. Annotate a variable the OpenSCAD "
            "Customizer way — width = 40;  // [10:5:200] — and it gets a "
            "slider here.")
        self.empty.setWordWrap(True)
        outer.addWidget(self.empty)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.body = QWidget()
        self.form = QVBoxLayout(self.body)
        self.form.addStretch()
        scroll.setWidget(self.body)
        outer.addWidget(scroll, 1)
        model.structure_changed.connect(self.rebuild)
        model.node_changed.connect(self._node_changed)
        self.rebuild()

    # ------------------------------------------------------------- build
    def rebuild(self):
        self._stop()
        while self.form.count() > 1:
            item = self.form.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self._rows = {}
        nodes = annotated(self.model)
        self.empty.setVisible(not nodes)
        groups = {}
        for node in nodes:
            title = customizer.group_of(node) or "Parameters"
            box = groups.get(title)
            if box is None:
                box = groups[title] = QGroupBox(title)
                box.setLayout(QVBoxLayout())
                self.form.insertWidget(self.form.count() - 1, box)
            box.layout().addWidget(self._row(node))

    def _row(self, node):
        spec = customizer.widget(node)
        row = QWidget()
        lay = QVBoxLayout(row)
        lay.setContentsMargins(0, 2, 0, 2)
        name = str(node.params.get("variable", ""))
        description = str(node.params.get("description") or "").strip()
        head = QHBoxLayout()
        title = QLabel(f"<b>{name}</b>" + (f" — {description}"
                                           if description else ""))
        title.setWordWrap(True)
        head.addWidget(title, 1)
        value = QLabel()
        value.setMinimumWidth(48)
        value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        head.addWidget(value)
        lay.addLayout(head)
        line = QHBoxLayout()
        control = self._control(node, spec)
        line.addWidget(control, 1)
        if spec["kind"] == "slider":
            play = QToolButton()
            play.setIcon(icons.icon("mdi.play"))
            play.setCheckable(True)
            play.setToolTip("Sweep this value back and forth to see what "
                            "it moves")
            play.toggled.connect(lambda on, s=control, b=play:
                                 self._play(s, b, on))
            control.play_button = play
            line.addWidget(play)
        lay.addLayout(line)
        self._rows[node.id] = (node, value, control)
        self._show_value(node)
        return row

    def _control(self, node, spec):
        current = self._current(node)
        kind = spec["kind"]
        if kind == "slider":
            lo, hi = float(spec["min"]), float(spec["max"])
            step = float(spec["step"]) or 1.0
            slider = QSlider(Qt.Horizontal)
            slider.setRange(0, max(int(round((hi - lo) / step)), 1))
            if isinstance(current, (int, float)):
                slider.setValue(int(round((float(current) - lo) / step)))
            slider.valueChanged.connect(
                lambda k, n=node: self._set(n, round(lo + k * step, 10)))
            return slider
        if kind == "dropdown":
            box = QComboBox()
            source = str(node.params.get("value", "")).strip()
            for raw, label in spec["items"]:
                box.addItem(label, raw)
            for i, (raw, _label) in enumerate(spec["items"]):
                if raw == source or _same(raw, current):
                    box.setCurrentIndex(i)
                    break
            box.currentIndexChanged.connect(
                lambda i, n=node, b=box: self._set(n, b.itemData(i)))
            return box
        if kind == "checkbox":
            box = QCheckBox()
            box.setChecked(bool(current))
            box.toggled.connect(lambda on, n=node: self._set(
                n, "true" if on else "false"))
            return box
        box = QLineEdit(current if isinstance(current, str) else "")
        if spec.get("max"):
            box.setMaxLength(int(spec["max"]))
        box.editingFinished.connect(lambda n=node, b=box: self._set(
            n, '"' + b.text().replace('"', '\\"') + '"'))
        return box

    # ------------------------------------------------------------ values
    @staticmethod
    def _current(node):
        try:
            return expr.evaluate(node.params.get("value"), {})
        except expr.ExprError:
            return None

    def _show_value(self, node):
        entry = self._rows.get(node.id)
        if entry is not None:
            entry[1].setText(_fmt(self._current(node)))

    def _set(self, node, value):
        if self._updating:
            return
        if isinstance(value, str):
            try:
                value = float(value)
            except ValueError:
                pass
        node.params["value"] = value
        self._updating = True
        try:
            self._show_value(node)
            self.model.node_changed.emit(node)
        finally:
            self._updating = False

    def _node_changed(self, node):
        if self._updating or getattr(node, "type", None) != "assign":
            return
        if node.id in self._rows:
            self.rebuild()

    # ---------------------------------------------------------- playing
    def _play(self, slider, button, on):
        if not on:
            if self._playing and self._playing[0] is slider:
                self._stop()
            return
        if self._playing and self._playing[0] is not slider:
            self._playing[0].play_button.setChecked(False)
        self._playing = [slider, 1]
        self._timer.start()

    def _stop(self):
        self._timer.stop()
        if self._playing:
            slider = self._playing[0]
            self._playing = None
            try:
                slider.play_button.setChecked(False)
            except RuntimeError:           # the row was rebuilt away
                pass

    def _tick(self):
        if not self._playing:
            return
        slider, direction = self._playing
        try:
            value = slider.value() + direction
        except RuntimeError:
            self._playing = None
            self._timer.stop()
            return
        if value > slider.maximum() or value < slider.minimum():
            direction = -direction
            self._playing[1] = direction
            value = slider.value() + direction
        slider.setValue(value)


def _same(raw, value):
    try:
        return expr.evaluate(raw, {}) == value
    except expr.ExprError:
        return False


def attach(window):
    """Create the Customizer dock on *window* (hidden until a document has
    annotated variables or View ▸ Customizer is ticked)."""
    panel = CustomizerPanel(window.model)
    dock = QDockWidget("Customizer", window)
    dock.setObjectName("customizer_dock")
    dock.setWidget(panel)
    window.addDockWidget(Qt.RightDockWidgetArea, dock)
    dock.hide()
    window._customizer_dock = dock
    window._customizer = panel
    state = {"shown_for": None}

    def maybe_show():
        # open by itself once per document that has controls
        if not annotated(window.model):
            return
        key = id(window.model.root)
        if state["shown_for"] != key and not dock.isVisible():
            state["shown_for"] = key
            dock.show()
    window.model.structure_changed.connect(maybe_show)
    return dock

"""Library ▸ Cars ▸ **Car Builder…**: pick a car, its paint, its wheels
and tyres, and drop it into the document as one Object.

Non-modal (one per main window, `open_builder`), like the House and
City Builders: the make and model come from `car_models`, the wheel and
tyre choices from `car_wheels`, and Build hands the lot to
`car_build.build_car`. Each build lands beside whatever is already
there and remembers its choices on the Object (`params["car"]`), so
selecting it and pressing **Update selected** rebuilds that car in
place instead of adding another.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtWidgets import (QComboBox, QDialog, QDialogButtonBox,
                             QFormLayout, QLabel, QPushButton, QVBoxLayout)

from . import car_build, car_models, car_wheels, icons, mesh
from .model import CadNode


class CarBuilder(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle("Car Builder")
        self.setModal(False)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self._make = QComboBox()
        self._model = QComboBox()
        self._paint = QComboBox()
        self._rim = QComboBox()
        self._tyre = QComboBox()
        self._finish = QComboBox()
        self._caliper = QComboBox()
        self._scale = QComboBox()
        self._makes = car_models.makes()
        self._make.addItems(sorted(self._makes))
        self._paint.addItems(["As delivered"] + list(car_models.PAINTS))
        self._rim.addItems(["As delivered"] + list(car_wheels.RIMS))
        self._tyre.addItems(list(car_wheels.TYRES))
        self._finish.addItems(list(car_wheels.FINISHES))
        self._caliper.addItems(list(car_wheels.CALIPERS))
        self._scale.addItems(list(car_build.SCALES))
        self._scale.setCurrentText("Full-size")
        for label, w in (("Make", self._make), ("Model", self._model),
                         ("Paint", self._paint), ("Wheels", self._rim),
                         ("Tyres", self._tyre),
                         ("Wheel finish", self._finish),
                         ("Calipers", self._caliper),
                         ("Size", self._scale)):
            form.addRow(label, w)

        self._info = QLabel()
        self._info.setWordWrap(True)
        layout.addWidget(self._info)

        buttons = QDialogButtonBox()
        self._build = QPushButton(icons.icon("mdi.car-sports"), "Build")
        self._update = QPushButton("Update selected")
        buttons.addButton(self._build, QDialogButtonBox.AcceptRole)
        buttons.addButton(self._update, QDialogButtonBox.ApplyRole)
        buttons.addButton(QDialogButtonBox.Close)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)

        self._make.currentTextChanged.connect(self._fill_models)
        self._model.currentTextChanged.connect(self._describe)
        self._build.clicked.connect(lambda: self._apply(None))
        self._update.clicked.connect(self._apply_selected)
        self._fill_models()

    # ------------------------------------------------------------ state
    def _fill_models(self):
        keys = self._makes.get(self._make.currentText(), [])
        self._model.blockSignals(True)
        self._model.clear()
        for key in keys:
            car = car_models.CARS[key]
            self._model.addItem(f"{car['model']} ({car['year']})", key)
        self._model.blockSignals(False)
        self._describe()

    def key(self) -> str:
        return self._model.currentData() or ""

    def options(self) -> dict:
        paint = self._paint.currentText()
        rim = self._rim.currentText()
        return dict(paint="" if paint == "As delivered" else paint,
                    rim="" if rim == "As delivered" else rim,
                    tyre=self._tyre.currentText(),
                    finish=self._finish.currentText(),
                    caliper=self._caliper.currentText(),
                    scale=car_build.SCALES[self._scale.currentText()])

    def _describe(self):
        key = self.key()
        if not key:
            return
        car = car_models.CARS[key]
        self._info.setText(
            f"{car['L']} × {car['W']} × {car['H']} mm, wheelbase "
            f"{car['wb']} mm; tyres {car['tyre_front']} front, "
            f"{car['tyre_rear']} rear. Published figures — the body is "
            "shaped to those proportions, not traced from a drawing.")

    def load_from(self, node: CadNode):
        """Show the choices a built car carries (`params['car']`)."""
        saved = (node.params or {}).get("car") or {}
        key = saved.get("key")
        if key not in car_models.CARS:
            return
        self._make.setCurrentText(car_models.CARS[key]["make"])
        self._model.setCurrentText(
            f"{car_models.CARS[key]['model']} ({car_models.CARS[key]['year']})")
        self._paint.setCurrentText(saved.get("paint") or "As delivered")
        self._rim.setCurrentText(saved.get("rim") or "As delivered")
        self._tyre.setCurrentText(saved.get("tyre") or "As delivered")
        self._finish.setCurrentText(saved.get("finish") or "Silver")
        self._caliper.setCurrentText(saved.get("caliper") or "Red")

    # ------------------------------------------------------------ build
    def _apply_selected(self):
        node = selected_car(self.window)
        if node is None:
            self.window.statusBar().showMessage(
                "Select a car built here first.", 6000)
            return
        self._apply(node)

    def _apply(self, replace):
        key, options = self.key(), self.options()
        if not key:
            return
        model = self.window.model
        body = car_build.build_car(key, options)
        x = y = 0.0
        if replace is not None:
            x = float(replace.params.get("x", 0.0))
            y = float(replace.params.get("y", 0.0))
            model.remove_node(replace)
        else:
            x = _free_x(model)
        model.root.add(body)
        part = model.enclose_as_part(body, car_build.label_of(key))
        part.params["x"], part.params["y"] = x, y
        part.params["car"] = dict(options, key=key)
        model.structure_changed.emit()
        self.window.builder.tree.select_nodes([part])
        self.window.view3d.fit()


def selected_car(window):
    """The selected node's own car Object, or None."""
    for node in window.builder.active_tree().selected_nodes():
        while node is not None:
            if (node.params or {}).get("car"):
                return node
            node = node.parent
    return None


def _free_x(model) -> float:
    """Right of everything already in the document, with a gap."""
    tris = mesh.tessellate(model.root, fn=12)
    if not tris:
        return 0.0
    return max(p[0] for t in tris for p in t) + 1500.0


def open_builder(window):
    panel = getattr(window, "_car_builder", None)
    if panel is None:
        panel = window._car_builder = CarBuilder(window)
    node = selected_car(window)
    if node is not None:
        panel.load_from(node)
    panel.show()
    panel.raise_()
    panel.activateWindow()
    return panel

"""Library ▸ Surfaces ▸ Surface Builder… — a slab of any library crystal
cut along any (hkl) plane: Si(111), SiO2 (0001), rutile (110)…

A non-modal panel over `crystal_surface`: crystal, Miller indices (three,
or four for a hexagonal crystal), the surface cells across, how many
interplanar spacings deep, and where the cut falls (automatic: the
widest gap between planes, so the fewest bonds break). Every change
re-describes the surface — cell, angle, spacing, atoms, triangles — and
a slab the 3D view could not draw disables Build.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from dataclasses import replace

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QDialog,
                             QDoubleSpinBox, QFormLayout, QHBoxLayout,
                             QLabel, QLineEdit, QMessageBox, QPushButton,
                             QSpinBox, QVBoxLayout)

from . import crystal_build as cb
from . import crystal_surface as cs
from .crystal_library import CATEGORIES, LIBRARY

PRESETS = (("Si (111)", "si", "111"), ("Si (100)", "si", "100"),
           ("SiO2 α-quartz (0001)", "quartz", "0001"),
           ("TiO2 rutile (110)", "rutile", "110"),
           ("Cu (111)", "cu", "111"), ("Au (111)", "au", "111"),
           ("MgO (100)", "mgo", "100"), ("GaN (0001)", "gan", "0001"),
           ("SrTiO3 (100)", "srtio3", "100"),
           ("Graphite (0001)", "graphite", "0001"))


class SurfaceBuilder(QDialog):
    """The non-modal Surface Builder panel."""

    def __init__(self, window):
        super().__init__(window)
        self.window_ = window
        self.setWindowTitle("Surface Builder")
        self.setModal(False)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.preset = QComboBox()
        self.preset.addItem("Common surfaces…")
        for label, key, hkl in PRESETS:
            self.preset.addItem(label, (key, hkl))
        self.preset.activated.connect(self._use_preset)
        form.addRow("Preset:", self.preset)
        self.crystal = QComboBox()
        for cat in CATEGORIES:
            members = [c for c in LIBRARY.values() if c.category == cat]
            if not members:
                continue
            self.crystal.addItem(f"— {cat} —")
            item = self.crystal.model().item(self.crystal.count() - 1)
            item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            for c in members:
                self.crystal.addItem(f"   {c.name}", c.key)
        self.crystal.setCurrentIndex(self.crystal.findData("si"))
        form.addRow("Crystal:", self.crystal)
        self.miller = QLineEdit("111")
        self.miller.setToolTip("Miller indices: 111, 1 1 0, 1-10; four for "
                               "a hexagonal crystal: 0001, 10-10")
        form.addRow("Surface (hkl):", self.miller)
        reps = QHBoxLayout()
        self.repeat = []
        for _axis in "uv":
            box = QSpinBox()
            box.setRange(1, cs.MAX_REPEAT)
            box.setValue(8)
            reps.addWidget(box)
            self.repeat.append(box)
        form.addRow("Surface cells (u × v):", reps)
        self.layers = QSpinBox()
        self.layers.setRange(1, 60)
        self.layers.setValue(4)
        self.layers.setSuffix(" layers")
        form.addRow("Depth:", self.layers)
        self.auto_cut = QCheckBox("Cut where the fewest bonds break")
        self.auto_cut.setChecked(True)
        form.addRow(self.auto_cut)
        self.term = QDoubleSpinBox()
        self.term.setRange(0.0, 0.99)
        self.term.setSingleStep(0.05)
        self.term.setDecimals(3)
        self.term.setToolTip("Where the cut falls, as a fraction of one "
                             "layer: picks the terminating plane")
        form.addRow("Termination:", self.term)
        self.atom_scale = QDoubleSpinBox()
        self.atom_scale.setRange(0.05, 3.0)
        self.atom_scale.setSingleStep(0.05)
        self.atom_scale.setValue(1.0)
        self.atom_scale.setSuffix(" × covalent radius")
        form.addRow("Atom size:", self.atom_scale)
        self.cell_box = QCheckBox("Draw the slab's base plate")
        self.cell_box.setChecked(True)
        form.addRow(self.cell_box)
        layout.addLayout(form)
        self.estimate = QLabel()
        self.estimate.setWordWrap(True)
        self.estimate.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.estimate)
        buttons = QHBoxLayout()
        self.go = QPushButton("Build")
        self.go.setDefault(True)
        self.go.clicked.connect(self.build_now)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        buttons.addStretch(1)
        buttons.addWidget(self.go)
        buttons.addWidget(close)
        layout.addLayout(buttons)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._refresh)
        self.crystal.currentIndexChanged.connect(self._timer.start)
        self.miller.textChanged.connect(self._timer.start)
        for box in self.repeat + [self.layers, self.term, self.atom_scale]:
            box.valueChanged.connect(self._timer.start)
        for check in (self.auto_cut, self.cell_box):
            check.toggled.connect(self._timer.start)
        self._refresh()

    def _use_preset(self, index):
        data = self.preset.itemData(index)
        if data:
            self.crystal.setCurrentIndex(self.crystal.findData(data[0]))
            self.miller.setText(data[1])

    def spec(self) -> cs.SurfaceSpec:
        return cs.SurfaceSpec(
            crystal=LIBRARY.get(self.crystal.currentData() or "si"),
            miller=cs.parse_miller(self.miller.text()),
            repeat=tuple(b.value() for b in self.repeat),
            layers=self.layers.value(),
            termination=(None if self.auto_cut.isChecked()
                         else self.term.value()),
            atom_scale=self.atom_scale.value(),
            cell_box=self.cell_box.isChecked())

    def _refresh(self):
        self.term.setEnabled(not self.auto_cut.isChecked())
        try:
            _code, st = cs.program(replace(self.spec(), prefix="x"))
        except cb.BuildError as exc:
            self.estimate.setText(f"<span style='color:#c0392b'>{exc}"
                                  "</span>")
            self.go.setEnabled(False)
            return
        self.go.setEnabled(True)
        if self.auto_cut.isChecked():
            self.term.blockSignals(True)
            self.term.setValue(st["termination"])
            self.term.blockSignals(False)
        self.estimate.setText(describe(st))

    def build_now(self):
        try:
            stats = cs.apply(self.window_, self.spec())
        except cb.BuildError as exc:
            QMessageBox.warning(self, "Surface Builder", str(exc))
            return
        self.window_.statusBar().showMessage(
            f"Built {stats['surface']} — {stats['atoms']:,} atoms. "
            + " ".join(stats.get("notes", [])), 12000)


def describe(st: dict) -> str:
    a, b = st["surface_cell_nm"]
    x, y, z = st["slab_nm"]
    return "<br>".join([
        f"<b>{st['surface']}</b>",
        f"Surface cell {a:g} × {b:g} nm at {st['surface_angle_deg']:g}°; "
        f"layer spacing {st['interplanar_spacing_nm']:g} nm",
        f"Slab {x:g} × {y:g} nm, {z:g} nm deep: {st['atoms']:,} atoms, "
        f"≈ {st['triangles']:,} triangles",
        f"<i>{st['notes'][0]}</i>"])


def open_builder(window):
    """Show the (one) Surface Builder panel."""
    panel = getattr(window, "_surface_builder", None)
    if panel is None:
        panel = window._surface_builder = SurfaceBuilder(window)
    panel.show()
    panel.raise_()
    return panel

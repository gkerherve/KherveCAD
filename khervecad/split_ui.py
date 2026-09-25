"""Right-click ▸ Split for printing…: the dialog over split.py — the
axis, where to cut (the part's extent shown), how many dowels and their
size, and the gap to leave between the halves.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtWidgets import (QComboBox, QDialog, QDialogButtonBox,
                             QDoubleSpinBox, QFormLayout, QLabel, QSpinBox)

from . import anchors, language, mesh, split


def _extent(model, part):
    source = part
    if part.type == "reference":
        from .mates import definition_of
        source = definition_of(model, part) or part
    env = anchors.doc_env(model)
    tris = anchors.local_tris(source, env=env, fn=model.effective_fn()) \
        if source.type == "component" else mesh.tessellate(
            source, env=env, fn=model.effective_fn())
    return anchors.bbox(tris)


class SplitDialog(QDialog):
    def __init__(self, window, part):
        super().__init__(window)
        self.window, self.part = window, part
        self.setWindowTitle(
            language.tr("Split {name} for printing").format(
                name=part.name))
        self.box = _extent(window.model, part)
        form = QFormLayout(self)
        self.axis = QComboBox()
        self.axis.addItems([language.tr("Z (a horizontal cut)"), "X", "Y"])
        self.axis.currentIndexChanged.connect(self._axis_changed)
        form.addRow(language.tr("Cut across"), self.axis)
        self.position = QDoubleSpinBox()
        self.position.setDecimals(2)
        self.position.setSuffix(" mm")
        form.addRow(language.tr("At"), self.position)
        self.range = QLabel()
        form.addRow("", self.range)
        self.dowels = QSpinBox()
        self.dowels.setRange(0, 4)
        self.dowels.setValue(2)
        form.addRow(language.tr("Dowels"), self.dowels)
        self.diameter = self._spin(5.0, 1.0, 50.0)
        form.addRow(language.tr("Dowel diameter"), self.diameter)
        self.depth = self._spin(10.0, 2.0, 200.0)
        form.addRow(language.tr("Dowel length"), self.depth)
        self.clearance = self._spin(0.15, 0.0, 2.0)
        form.addRow(language.tr("Hole clearance"), self.clearance)
        self.gap = self._spin(10.0, 0.0, 1000.0)
        form.addRow(language.tr("Gap between halves"), self.gap)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok
                                   | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(language.tr("Split"))
        buttons.accepted.connect(self._split)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self.message = QLabel()
        self.message.setWordWrap(True)
        form.addRow(self.message)
        self._axis_changed()

    @staticmethod
    def _spin(value, low, high):
        box = QDoubleSpinBox()
        box.setRange(low, high)
        box.setDecimals(2)
        box.setSuffix(" mm")
        box.setValue(value)
        return box

    def axis_name(self):
        return ("z", "x", "y")[self.axis.currentIndex()]

    def _axis_changed(self):
        if self.box is None:
            self.message.setText(
                language.tr("This part has no geometry to split."))
            return
        k = split.AXES.index(self.axis_name())
        lo, hi = self.box[0][k], self.box[1][k]
        self.position.setRange(lo, hi)
        self.position.setValue((lo + hi) / 2)
        self.range.setText(language.tr(
            "the part runs from {lo:.1f} to {hi:.1f} mm").format(
                lo=lo, hi=hi))

    def _split(self):
        try:
            first, second, pin, points = split.split_part(
                self.window.model, self.part, self.axis_name(),
                self.position.value(), self.dowels.value(),
                self.diameter.value(), self.depth.value(),
                self.clearance.value(), self.gap.value())
        except ValueError as exc:
            self.message.setText(str(exc))
            return
        extra = (" " + language.tr(
            "and {count} dowel hole(s) with a pin Object").format(
                count=len(points))) if points else ""
        self.window.statusBar().showMessage(language.tr(
            "Split {name} into {first} and {second}{extra}; the "
            "original is hidden.").format(
                name=self.part.name, first=first.name, second=second.name,
                extra=extra), 10000)
        self.accept()


def open_dialog(window, part):
    dialog = SplitDialog(window, part)
    dialog.show()
    return dialog

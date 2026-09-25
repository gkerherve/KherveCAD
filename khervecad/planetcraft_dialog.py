"""File ▸ Send to PlanetCraft…: the model (or the selected Object) as a
walking creature in the PlanetCraft game — see planetcraft.py.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import os

from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox,
                             QDoubleSpinBox, QFileDialog, QFormLayout,
                             QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                             QPushButton, QSpinBox, QVBoxLayout, QWidget)

from . import language, planetcraft

KEY = "planetcraft/folder"


class SendDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle(language.tr("Send to PlanetCraft"))
        model = window.model
        sel = window.builder.active_tree().selected_nodes() \
            if hasattr(window.builder, "active_tree") else []
        self.node = sel[0] if len(sel) == 1 else None
        stem = os.path.splitext(os.path.basename(
            getattr(window, "_path", None) or ""))[0]
        name = (self.node.name if self.node is not None else stem) or \
            "Creature"

        form = QFormLayout()
        self.name = QLineEdit(name)
        form.addRow(language.tr("Creature name"), self.name)
        self.real = QCheckBox(language.tr("Real size (1 block = 1 m)"))
        self.real.setChecked(True)
        self.height = QDoubleSpinBox()
        self.height.setRange(0.2, 12.0)
        self.height.setDecimals(2)
        self.height.setValue(1.2)
        self.height.setSuffix(" " + language.tr("blocks"))
        self.height.setEnabled(False)
        self.real.toggled.connect(lambda on: self.height.setEnabled(not on))
        row = QHBoxLayout()
        row.addWidget(self.real)
        row.addWidget(self.height)
        box = QWidget()
        box.setLayout(row)
        form.addRow(language.tr("Height"), box)
        self.speed = QDoubleSpinBox()
        self.speed.setRange(0.1, 4.0)
        self.speed.setValue(1.0)
        form.addRow(language.tr("Speed"), self.speed)
        self.health = QSpinBox()
        self.health.setRange(1, 200)
        self.health.setValue(12)
        form.addRow(language.tr("Health"), self.health)
        self.wild = QCheckBox(
            language.tr("Roams the wild herds of new worlds"))
        self.wild.setChecked(True)
        form.addRow("", self.wild)
        folder = QSettings().value(KEY, "") or planetcraft.default_folder()
        self.folder = QLineEdit(folder)
        pick = QPushButton("…")
        pick.clicked.connect(self._pick)
        frow = QHBoxLayout()
        frow.addWidget(self.folder)
        frow.addWidget(pick)
        fbox = QWidget()
        fbox.setLayout(frow)
        form.addRow(language.tr("PlanetCraft folder"), fbox)

        what = (language.tr("the selected part “{name}”").format(
                    name=self.node.name)
               if self.node is not None else language.tr("the whole model"))
        self.info = QLabel(language.tr(
            "Sends {what}. Name parts <b>Head</b>, <b>Tail</b>, "
            "<b>Wing</b> or <b>Front left leg</b>… to choose the "
            "joints; unnamed legs are found by themselves. Restart "
            "PlanetCraft (or reload the page) and a pair appears near "
            "you.").format(what=what))
        self.info.setWordWrap(True)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok |
                                   QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(language.tr("Send"))
        buttons.accepted.connect(self._send)
        buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(self.info)
        lay.addWidget(buttons)
        self.resize(460, self.sizeHint().height())

    def _pick(self):
        d = QFileDialog.getExistingDirectory(
            self, language.tr("PlanetCraft folder"), self.folder.text())
        if d:
            self.folder.setText(d)

    def _send(self):
        folder = self.folder.text().strip()
        title = language.tr("Send to PlanetCraft")
        try:
            r = planetcraft.export(
                self.window.model, self.name.text(), folder, self.node,
                None if self.real.isChecked() else self.height.value(),
                self.speed.value(), self.health.value(),
                self.wild.isChecked())
        except planetcraft.PlanetCraftError as exc:
            QMessageBox.warning(self, title, str(exc))
            return
        QSettings().setValue(KEY, folder)
        legs = r["legs"]
        msg = language.tr(
            "“{label}” is in PlanetCraft: {height} blocks tall, "
            "{triangles} triangles, parts: {parts}").format(
                label=r['label'], height=r['height_blocks'],
                triangles=r['triangles'], parts=', '.join(r['parts']))
        if r["auto_legs"]:
            msg += " " + language.tr(
                "({legs} legs found automatically)").format(legs=legs)
        msg += "\n\n" + language.tr(
            "Reload PlanetCraft; a pair appears near you and it joins "
            "the wild herds of new worlds.")
        QMessageBox.information(self, title, msg)
        self.accept()


def open_dialog(window):
    SendDialog(window).exec_()

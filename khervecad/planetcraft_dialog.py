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

from PyQt5.QtCore import QSettings, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QDialog,
                             QDialogButtonBox,
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
        # a creature from build_creature or Library > Monsters knows what it
        # is: its name (the tree's label, not "Group"), and its game numbers
        from .model import name_tag
        self.mark = planetcraft.creature_of(self.node or model.root)
        label = name_tag(self.node.name) or self.node.name \
            if self.node is not None else ""
        if not label and self.mark:
            found = [n for n in model.root.walk()
                     if (n.params or {}).get("creature")]
            label = name_tag(found[0].name) if len(found) == 1 else ""
        name = label or stem or "Creature"

        form = QFormLayout()
        self.name = QLineEdit(name)
        form.addRow(language.tr("Creature name"), self.name)
        # what the game makes of it — see planetcraft.NATURES
        self.nature = QComboBox()
        for label, key in ((language.tr("Automatic"), "auto"),
                           (language.tr("Animal — grazes, bolts when hit"),
                            "animal"),
                           (language.tr("Person — walks about, looks at you"),
                            "person"),
                           (language.tr("Monster — hunts you"), "monster")):
            self.nature.addItem(label, key)
        form.addRow(language.tr("What is it?"), self.nature)
        if self.mark.get("nature"):
            self.nature.setCurrentIndex(max(0, self.nature.findData(
                self.mark["nature"])))
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
        self.speed.setValue(float(self.mark.get("speed") or 1.0))
        form.addRow(language.tr("Speed"), self.speed)
        self.health = QSpinBox()
        self.health.setRange(1, 200)
        self.health.setValue(int(self.mark.get("health") or 12))
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
            "<b>Wing</b> or <b>Left leg</b>, <b>Front left leg</b>… to "
            "choose the joints; unnamed legs are found by themselves. A "
            "man on two legs walks about as a person; call it a troll, a "
            "dragon or a monster — or choose Monster — and it hunts you. "
            "A running PlanetCraft picks it up within seconds and puts it "
            "in front of you; it is also in the game's Creatures book "
            "(menu ▸ Creatures). Ready-made monsters: Library ▸ Toys & "
            "models ▸ Monsters.").format(what=what))
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
                self.wild.isChecked(), self.nature.currentData())
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
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle(title)
        if r.get("game_running"):
            msg += "\n\n" + language.tr(
                "PlanetCraft is running: it will walk up to you within a "
                "few seconds, and it is in the Creatures book.")
            show = box.addButton(language.tr("Show in PlanetCraft"),
                                 QMessageBox.ActionRole)
        else:
            msg += "\n\n" + language.tr(
                "Start PlanetCraft: it appears near you, joins the wild "
                "herds of new worlds, and is in the Creatures book (menu ▸ "
                "Creatures).")
            show = None
        box.setText(msg)
        box.addButton(QMessageBox.Ok)
        box.exec_()
        if show is not None and box.clickedButton() is show:
            QDesktopServices.openUrl(QUrl(r["book_url"]))
        self.accept()


def open_dialog(window):
    SendDialog(window).exec_()

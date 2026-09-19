"""Library ▸ People & characters ▸ **Human Builder…**: dress and pose a
person from combo boxes and see it from the Front, the Side and the
Back as you choose, then drop it into the document as one Object.

Non-modal (one per main window, `open_builder`), like the Car and Lego
Builders. The choices are a `human_design` spec; every change rebuilds
the figure on a worker thread (the body, its outfit and the loose
pieces — a couple of seconds in pure Python) and the three views are
painted there too, so the combo boxes never freeze. **Insert** adds a
new person beside the model; the Object keeps its spec
(``params["character"]``), so selecting it and pressing **Update
selected** rebuilds it in place.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import random

from PyQt5.QtCore import QObject, Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QFormLayout,
                             QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                             QPushButton, QScrollArea, QVBoxLayout, QWidget)

from . import human_design as D
from . import icons

DEFAULT_LABEL = "(default)"
VIEW_W, VIEW_H = 260, 420


class _Worker(QObject):
    """Builds and paints on its own thread; only the newest request is
    worked on."""
    done = pyqtSignal(int, object, str)

    def __init__(self):
        super().__init__()
        self._pending = None

    def request(self, serial, spec):
        self._pending = (serial, spec)
        QTimer.singleShot(0, self._run)

    def _run(self):
        if self._pending is None:
            return
        serial, spec = self._pending
        self._pending = None
        from . import human_views, mesh
        try:
            node = D.build(spec)
            colored = [(t, c) for t, c, *_ in mesh.tessellate_colored(node)]
            images = human_views.render_all(colored, VIEW_W, VIEW_H)
            self.done.emit(serial, images, "")
        except Exception as exc:                  # a bad custom garment
            self.done.emit(serial, None, str(exc))


class HumanBuilder(QDialog):
    _ask = pyqtSignal(int, object)

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle("Human Builder")
        self.setModal(False)
        self.resize(1180, 700)
        self._serial = 0
        self._quiet = False
        self._combos = {}
        self._colours = {}

        outer = QHBoxLayout(self)
        left = QWidget()
        form_box = QVBoxLayout(left)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(left)
        scroll.setMinimumWidth(390)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.addWidget(scroll)

        top = QFormLayout()
        self._preset = QComboBox()
        self._preset.addItems(["(choose a preset)"] + list(D.PRESETS))
        self._preset.activated[str].connect(self._load_preset)
        self._name = QLineEdit("Person")
        top.addRow("Preset", self._preset)
        top.addRow("Name", self._name)
        form_box.addLayout(top)

        def group(title, rows):
            box = QGroupBox(title)
            form = QFormLayout(box)
            for label, widget in rows:
                form.addRow(label, widget)
            form_box.addWidget(box)

        self._stature = QDoubleSpinBox()
        self._stature.setRange(1.2, 2.3)
        self._stature.setSingleStep(0.01)
        self._stature.setDecimals(2)
        self._stature.setSuffix(" m")
        self._stature.setSpecialValueText("Typical")
        self._stature.setMinimum(1.19)
        self._stature.setValue(1.19)
        group("Body", [("Gender", self._combo("gender")),
                       ("Age", self._combo("age")),
                       ("Build", self._combo("build")),
                       ("Height", self._stature),
                       ("Skin", self._combo("skin"))])
        group("Pose", [("Arms", self._combo("gesture")),
                       ("Legs", self._combo("stance"))])
        group("Head", [("Hair", self._combo("hair")),
                       ("Hair colour", self._combo("hair_colour")),
                       ("Beard", self._combo("beard")),
                       ("Glasses", self._combo("glasses")),
                       ("Hat", self._pair("hat"))])
        group("Clothes", [("Top", self._pair("top")),
                          ("Bottom", self._pair("bottom")),
                          ("Coat", self._pair("coat")),
                          ("Shoes", self._pair("shoes")),
                          ("Gloves", self._pair("gloves"))])
        note = QLabel("Clothes follow the body parts, so they stay on in "
                      "any pose. An assistant can add its own garments "
                      "(any part, any colour) through the MCP tool "
                      "build_character.")
        note.setWordWrap(True)
        note.setStyleSheet("color: gray;")
        form_box.addWidget(note)
        form_box.addStretch(1)

        right = QVBoxLayout()
        views = QHBoxLayout()
        self._views = []
        for _ in range(3):
            label = QLabel()
            label.setFixedSize(VIEW_W, VIEW_H)
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("background: #2b2e33;")
            views.addWidget(label)
            self._views.append(label)
        right.addLayout(views)
        self._status = QLabel("")
        right.addWidget(self._status)
        buttons = QHBoxLayout()
        for text, icon, slot in (
                ("Random", "mdi.dice-multiple", self._random),
                ("Insert", "mdi.account-plus", lambda: self._apply(None)),
                ("Update selected", "mdi.account-edit",
                 lambda: self._apply(selected_character(self.window))),
                ("Close", "mdi.close", self.close)):
            b = QPushButton(icons.icon(icon), text)
            b.clicked.connect(slot)
            buttons.addWidget(b)
        right.addLayout(buttons)
        outer.addLayout(right, 1)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._rebuild)
        self._thread = QThread(self)
        self._worker = _Worker()
        self._worker.moveToThread(self._thread)
        self._ask.connect(self._worker.request)
        self._worker.done.connect(self._shown)
        self._thread.start()
        self._stature.valueChanged.connect(self._changed)
        self._name.textChanged.connect(lambda _t: None)
        self.set_spec(D.PRESETS["Casual man"])

    # ---------------------------------------------------------- widgets
    def _combo(self, key):
        box = QComboBox()
        table = D.CHOICES[key]
        box.addItems(list(table))
        box.currentIndexChanged.connect(self._changed)
        self._combos[key] = box
        return box

    def _pair(self, key):
        """The item's combo and its colour combo side by side."""
        holder = QWidget()
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self._combo(key), 3)
        colour = QComboBox()
        colour.setEditable(True)
        colour.addItems([DEFAULT_LABEL] + list(D.COLOURS))
        colour.setToolTip("A colour name or #rrggbb")
        colour.currentTextChanged.connect(self._changed)
        self._colours[f"{key}_colour"] = colour
        row.addWidget(colour, 2)
        return holder

    # ------------------------------------------------------------- spec
    def spec(self) -> dict:
        out = {key: box.currentText() for key, box in self._combos.items()}
        for key, box in self._colours.items():
            text = box.currentText().strip()
            out[key] = "" if text in ("", DEFAULT_LABEL) else text
        value = self._stature.value()
        out["stature"] = 0.0 if value <= 1.195 else value * 1000.0
        out["name"] = self._name.text().strip() or "Person"
        out["garments"] = list(getattr(self, "_garments", []))
        return out

    def set_spec(self, spec):
        spec = D.normalise(spec)
        self._quiet = True
        try:
            for key, box in self._combos.items():
                box.setCurrentText(str(spec[key]))
            for key, box in self._colours.items():
                box.setCurrentText(spec[key] or DEFAULT_LABEL)
            stature = float(spec.get("stature") or 0.0)
            self._stature.setValue(stature / 1000.0 if stature else 1.19)
            self._name.setText(spec.get("name") or "Person")
            self._garments = list(spec.get("garments") or [])
        finally:
            self._quiet = False
        self._changed()

    def _load_preset(self, name):
        if name in D.PRESETS:
            self.set_spec(dict(D.PRESETS[name]))

    def _random(self):
        rnd = random.Random()
        spec = {key: rnd.choice(list(table))
                for key, table in D.CHOICES.items()}
        spec["skin"] = rnd.choice(list(D.SKIN_TONES)[:6])
        for key in D.COLOUR_KEYS:
            spec[key] = rnd.choice(list(D.COLOURS))
        spec["name"] = "Random person"
        self.set_spec(spec)

    # ----------------------------------------------------------- update
    def _changed(self, *_args):
        if self._quiet:
            return
        self._status.setText("Updating…")
        self._timer.start()

    def _rebuild(self):
        try:
            spec = D.normalise(self.spec())
        except D.SpecError as exc:
            self._status.setText(str(exc))
            return
        self._serial += 1
        self._ask.emit(self._serial, spec)

    def _shown(self, serial, images, error):
        if serial != self._serial:
            return
        if images is None:
            self._status.setText(f"Could not build: {error}")
            return
        for label, view in zip(self._views, ("Front", "Side", "Back")):
            label.setPixmap(QPixmap.fromImage(images[view]))
        self._status.setText("Front, left side and back, to one scale.")

    def _apply(self, replace):
        try:
            spec = D.normalise(self.spec())
        except D.SpecError as exc:
            self._status.setText(str(exc))
            return
        part = D.insert(self.window.model, spec, replace=replace)
        self.window.builder.tree.select_nodes([part])
        self.window.view3d.fit()
        self._status.setText(f"{'Updated' if replace else 'Inserted'} "
                             f"{spec['name']}.")

    def load_from(self, node):
        spec = (node.params or {}).get("character")
        if spec:
            self.set_spec(spec)

    def closeEvent(self, event):
        super().closeEvent(event)

    def shutdown(self):
        self._thread.quit()
        self._thread.wait(3000)


def selected_character(window):
    """The selected node's own person Object, or None."""
    for node in window.builder.active_tree().selected_nodes():
        while node is not None:
            if (node.params or {}).get("character"):
                return node
            node = node.parent
    return None


def open_builder(window):
    panel = getattr(window, "_human_builder", None)
    if panel is None:
        panel = window._human_builder = HumanBuilder(window)
        window.destroyed.connect(lambda *_: panel.shutdown())
    node = selected_character(window)
    if node is not None:
        panel.load_from(node)
    panel.show()
    panel.raise_()
    panel.activateWindow()
    return panel

"""Library ▸ Everyday things ▸ Shoes ▸ **Shoe Builder…**: choose a
preset, then gender, EU size, toe, upper, sole, heel and colours, see
the shoe from the side and from above as you choose, and drop it into
the document as one Object (or a pair). The Object keeps its spec in
``params["shoe"]``, so selecting it and pressing **Update selected**
rebuilds it in place. A shoe builds in a fraction of a second, so the
preview is redrawn on the GUI thread after a short pause.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtCore import QPointF, Qt, QTimer
from PyQt5.QtGui import QColor, QImage, QPainter, QPixmap, QTransform
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox,
                             QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QVBoxLayout, QWidget)

from . import icons, language
from . import shoe_design as D

DEFAULT_LABEL = "(default)"
VIEW_W, VIEW_H = 520, 250
COLOUR_KEYS = (("upper_colour", "Upper"), ("lining_colour", "Lining"),
               ("sole_colour", "Sole"), ("heel_colour", "Heel"),
               ("accent_colour", "Accent"), ("lace_colour", "Laces"))


def render_view(colored, plane, width, height, label=""):
    """A QImage of the coloured faces seen on *plane* ("Front (XZ)" =
    from the side, "Top (XY)" = from above), fitted to the picture."""
    from . import planview
    image = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
    image.fill(QColor("#2b2e33"))
    if colored:
        a, b = (0, 2) if plane.startswith("Front") else (0, 1)
        us = [v[a] for tri, _c in colored for v in tri]
        vs = [v[b] for tri, _c in colored for v in tri]
        w = max(max(us) - min(us), 1.0)
        h = max(max(vs) - min(vs), 1.0)
        k = min((width - 24) / w, (height - 30) / h)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        cx = (max(us) + min(us)) / 2.0
        cy = (max(vs) + min(vs)) / 2.0
        painter.setTransform(QTransform(k, 0, 0, -k, width / 2.0 - cx * k,
                                        height / 2.0 + 6 + cy * k))
        planview.paint_faces(painter, planview.plan_faces(colored, plane))
        painter.resetTransform()
        painter.setPen(QColor("#c9ccd1"))
        painter.drawText(QPointF(8, 16), label)
        painter.end()
    return image


class ShoeBuilder(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle(language.tr("Shoe Builder"))
        self.setModal(False)
        self.resize(1000, 640)
        self._quiet = False
        self._combos = {}
        self._colours = {}

        outer = QHBoxLayout(self)
        left = QWidget()
        form_box = QVBoxLayout(left)
        left.setMinimumWidth(360)
        outer.addWidget(left)

        top = QFormLayout()
        self._preset = QComboBox()
        self._preset.addItems([language.tr("(choose a preset)")]
                              + list(D.PRESETS))
        self._preset.activated[str].connect(self._load_preset)
        self._name = QLineEdit("Shoe")
        top.addRow(language.tr("Preset"), self._preset)
        top.addRow(language.tr("Name"), self._name)
        form_box.addLayout(top)

        def group(title, rows):
            box = QGroupBox(title)
            form = QFormLayout(box)
            for label, widget in rows:
                form.addRow(label, widget)
            form_box.addWidget(box)

        self._size = QDoubleSpinBox()
        self._size.setRange(30, 50)
        self._size.setSingleStep(0.5)
        self._size.setDecimals(1)
        self._size.setPrefix("EU ")
        self._size.valueChanged.connect(self._changed)
        self._heel_h = QDoubleSpinBox()
        self._heel_h.setRange(0, 160)
        self._heel_h.setSingleStep(5)
        self._heel_h.setSuffix(" mm")
        self._heel_h.valueChanged.connect(self._changed)
        self._arrow = QCheckBox(language.tr("Devil arrow tip"))
        self._arrow.toggled.connect(self._changed)
        self._pair = QCheckBox(language.tr("Make a pair"))
        self._pair.toggled.connect(self._changed)
        group(language.tr("Last"),
              [(language.tr("For"), self._combo("gender", D.GENDERS)),
               (language.tr("Size"), self._size),
               (language.tr("Toe"), self._combo("toe", list(D.WIDTHS)))])
        group(language.tr("Shoe"),
              [(language.tr("Upper"), self._combo("upper", list(D.UPPERS))),
               (language.tr("Sole"), self._combo("sole", list(D.SOLES))),
               (language.tr("Heel"), self._combo("heel", D.HEELS)),
               (language.tr("Heel height"), self._heel_h),
               ("", self._arrow),
               (language.tr("Side decoration"),
                self._combo("decoration", D.DECORATIONS)),
               ("", self._pair)])
        group(language.tr("Colours"),
              [(language.tr(label), self._colour(key))
               for key, label in COLOUR_KEYS])
        note = QLabel(language.tr(
            "Every choice is the same parametric last, so any mix works. "
            "No brand marks: the side decoration is an original wave or "
            "stripe. An assistant can build shoes with the MCP tool "
            "build_shoe."))
        note.setWordWrap(True)
        note.setStyleSheet("color: gray;")
        form_box.addWidget(note)
        form_box.addStretch(1)

        right = QVBoxLayout()
        self._views = []
        for _ in range(2):
            label = QLabel()
            label.setFixedSize(VIEW_W, VIEW_H)
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("background: #2b2e33;")
            right.addWidget(label)
            self._views.append(label)
        self._status = QLabel("")
        right.addWidget(self._status)
        buttons = QHBoxLayout()
        for text, icon, slot in (
                (language.tr("Insert"), "mdi.plus-box",
                 lambda: self._apply(None)),
                (language.tr("Update selected"), "mdi.pencil",
                 lambda: self._apply(selected_shoe(self.window))),
                (language.tr("Close"), "mdi.close", self.close)):
            b = QPushButton(icons.icon(icon), text)
            b.clicked.connect(slot)
            buttons.addWidget(b)
        right.addLayout(buttons)
        outer.addLayout(right, 1)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(200)
        self._timer.timeout.connect(self._rebuild)
        self.set_spec({"preset": "Devil arrow pump"})

    # ---------------------------------------------------------- widgets
    def _combo(self, key, items):
        box = QComboBox()
        box.addItems([str(i) for i in items])
        box.currentIndexChanged.connect(self._changed)
        self._combos[key] = box
        return box

    def _colour(self, key):
        box = QComboBox()
        box.setEditable(True)
        box.addItems([DEFAULT_LABEL] + list(D.COLOURS))
        box.setToolTip(language.tr("A colour name or #rrggbb"))
        box.currentTextChanged.connect(self._changed)
        self._colours[key] = box
        return box

    # ------------------------------------------------------------- spec
    def spec(self) -> dict:
        out = {key: box.currentText() for key, box in self._combos.items()}
        for key, box in self._colours.items():
            text = box.currentText().strip()
            out[key] = "" if text in ("", DEFAULT_LABEL) else text
        out.update(size=self._size.value(), heel_height=self._heel_h.value(),
                   arrow=self._arrow.isChecked(),
                   pair=self._pair.isChecked(),
                   name=self._name.text().strip() or "Shoe")
        return out

    def set_spec(self, spec):
        spec = D.normalise(spec)
        self._quiet = True
        try:
            for key, box in self._combos.items():
                box.setCurrentText(str(spec[key]))
            for key, box in self._colours.items():
                box.setCurrentText(spec[key] or DEFAULT_LABEL)
            self._size.setValue(float(spec["size"]))
            self._heel_h.setValue(float(spec["heel_height"]))
            self._arrow.setChecked(bool(spec["arrow"]))
            self._pair.setChecked(bool(spec["pair"]))
            self._name.setText(spec["name"])
        finally:
            self._quiet = False
        self._rebuild()

    def _load_preset(self, name):
        if name in D.PRESETS:
            self.set_spec({"preset": name})

    # ----------------------------------------------------------- update
    def _changed(self, *_args):
        if self._quiet:
            return
        self._status.setText(language.tr("Updating…"))
        self._timer.start()

    def _rebuild(self):
        from . import mesh
        try:
            spec = D.normalise(self.spec())
            node = D.build(spec)
            colored = [(t, c) for t, c, *_ in mesh.tessellate_colored(node)]
        except Exception as exc:                 # a bad colour, mostly
            self._status.setText(str(exc))
            return
        for label, plane, name in zip(self._views,
                                      ("Front (XZ)", "Top (XY)"),
                                      ("Side", "Top")):
            label.setPixmap(QPixmap.fromImage(render_view(
                colored, plane, VIEW_W, VIEW_H, language.tr(name))))
        self._status.setText(language.tr(
            "{size:.0f} mm long, {n} triangles.").format(
            size=D.length_mm(spec), n=len(colored)))

    def _apply(self, replace):
        try:
            spec = D.normalise(self.spec())
        except D.SpecError as exc:
            self._status.setText(str(exc))
            return
        part = D.insert(self.window.model, spec, replace=replace)
        self.window.builder.tree.select_nodes([part])
        if not self.window.view3d.user_moved:
            self.window.view3d.fit()
        verb = language.tr("Updated") if replace else language.tr("Inserted")
        self._status.setText(f"{verb} {spec['name']}.")

    def load_from(self, node):
        spec = (node.params or {}).get("shoe")
        if spec:
            self.set_spec(spec)


def selected_shoe(window):
    """The selected node's own shoe Object, or None."""
    for node in window.builder.active_tree().selected_nodes():
        while node is not None:
            if (node.params or {}).get("shoe"):
                return node
            node = node.parent
    return None


def open_builder(window):
    panel = getattr(window, "_shoe_builder", None)
    if panel is None:
        panel = window._shoe_builder = ShoeBuilder(window)
    node = selected_shoe(window)
    if node is not None:
        panel.load_from(node)
    panel.show()
    panel.raise_()
    panel.activateWindow()
    return panel

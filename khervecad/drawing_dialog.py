"""File ▸ Make Drawing… — the sheet, the views, a section, then PDF,
SVG, PNG or DXF, with a live preview.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from pathlib import Path

from PyQt5.QtCore import QSettings, Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QDialog,
                             QDialogButtonBox, QFileDialog, QFormLayout,
                             QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                             QPushButton, QVBoxLayout)

from . import drawing, drawing_export, mesh

_SETTINGS = ("Kherve", "KherveCAD")
STANDARD = ("Front", "Top", "Right", "Isometric")


def model_tris(window):
    """The mesh the drawing is of: the selection, else the whole
    document (the Object being edited, in the Object tab)."""
    nodes = window.builder.active_tree().selected_nodes()
    fn = window.model.effective_fn()
    if nodes:
        with window._isolated_frame(window.builder.isolated_component()):
            return mesh.selected_world_tris(
                window._render_scope()[0], {n.id for n in nodes}, fn=fn), \
                nodes[0].name
    root = window._render_scope()[0]
    iso = root if root is not window.model.root else None
    with window._isolated_frame(iso):
        tris = mesh.tessellate(root, fn=fn)
    name = root.name if iso is not None else (
        Path(window._path).stem if window._path else "Part")
    return tris, name


def make_layout(window, *, sheet="A4", views=STANDARD, dimensions=True,
                section_axis=None, title=None, scale=None,
                hidden_lines=True):
    tris, name = model_tris(window)
    if not tris:
        raise ValueError("nothing to draw — the model has no solid")
    return drawing.layout(tris, sheet=sheet, views=views,
                          dimensions=dimensions, section_axis=section_axis,
                          title=title or name, scale=scale,
                          hidden_lines=hidden_lines)


class DrawingDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window_ = window
        self.setWindowTitle("Make Drawing")
        self.resize(900, 620)
        settings = QSettings(*_SETTINGS)
        form = QFormLayout()
        self.title = QLineEdit(model_tris(window)[1])
        form.addRow("Title:", self.title)
        self.sheet = QComboBox()
        self.sheet.addItems(list(drawing.SHEETS))
        self.sheet.setCurrentText(settings.value("drawing/sheet", "A4"))
        form.addRow("Sheet:", self.sheet)
        views = QHBoxLayout()
        self.view_boxes = {}
        for name in STANDARD:
            box = QCheckBox(name)
            box.setChecked(True)
            self.view_boxes[name] = box
            views.addWidget(box)
        form.addRow("Views:", views)
        self.dims = QCheckBox("Overall dimensions")
        self.dims.setChecked(True)
        self.hidden = QCheckBox("Hidden lines (dashed)")
        self.hidden.setChecked(True)
        self.hidden.setToolTip("Edges behind the surface, dashed. Turn off "
                               "for threaded or very detailed parts")
        opts = QHBoxLayout()
        opts.addWidget(self.dims)
        opts.addWidget(self.hidden)
        form.addRow("", opts)
        self.section = QComboBox()
        self.section.addItem("none", None)
        for axis, label in (("y", "Y — front to back"),
                            ("x", "X — side to side"),
                            ("z", "Z — top to bottom")):
            self.section.addItem(f"Section through the middle, {label}",
                                 axis)
        form.addRow("Section:", self.section)
        self.scale = QComboBox()
        self.scale.addItem("Automatic", None)
        for s in drawing.SCALES:
            self.scale.addItem(drawing.scale_label(s), s)
        form.addRow("Scale:", self.scale)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumHeight(360)
        layout.addWidget(self.preview, 1)
        self.status = QLabel("")
        layout.addWidget(self.status)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        self.refresh_btn = QPushButton("Update preview")
        self.refresh_btn.clicked.connect(self.refresh)
        buttons.addButton(self.refresh_btn, QDialogButtonBox.ActionRole)
        self.save_btn = QPushButton("Save as…")
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self.save)
        buttons.addButton(self.save_btn, QDialogButtonBox.AcceptRole)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.lay = None
        self.refresh()

    def options(self):
        return dict(sheet=self.sheet.currentText(),
                    views=tuple(n for n, b in self.view_boxes.items()
                                if b.isChecked()) or ("Front",),
                    dimensions=self.dims.isChecked(),
                    hidden_lines=self.hidden.isChecked(),
                    section_axis=self.section.currentData(),
                    title=self.title.text().strip() or "Part",
                    scale=self.scale.currentData())

    def refresh(self):
        try:
            self.lay = make_layout(self.window_, **self.options())
        except ValueError as exc:
            self.status.setText(str(exc))
            self.lay = None
            return
        img = drawing_export.to_image(self.lay, 3.0)
        pix = QPixmap.fromImage(img).scaled(
            self.preview.width() - 8, self.preview.height() - 8,
            Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview.setPixmap(pix)
        n = sum(len(v["lines"]["visible"]) for v in self.lay["views"]
                if v.get("lines"))
        self.status.setText(f"{self.lay['sheet']} at "
                            f"{self.lay['scale_label']}, {n} visible lines")

    def save(self):
        if self.lay is None:
            self.refresh()
            if self.lay is None:
                return
        settings = QSettings(*_SETTINGS)
        settings.setValue("drawing/sheet", self.sheet.currentText())
        start = str(Path(self.window_._path).with_suffix(".pdf")) \
            if self.window_._path else f"{self.lay['title']}.pdf"
        path, _f = QFileDialog.getSaveFileName(
            self, "Save drawing", start,
            "PDF (*.pdf);;SVG (*.svg);;DXF (*.dxf);;PNG (*.png)")
        if not path:
            return
        if Path(path).suffix.lower() not in drawing_export.WRITERS:
            path += ".pdf"
        try:
            drawing_export.export(self.lay, path)
        except Exception as exc:
            QMessageBox.warning(self, "Make Drawing",
                                f"Could not write the drawing:\n{exc}")
            return
        self.window_.statusBar().showMessage(f"Drawing saved: {path}",
                                             8000)
        self.accept()


def open_dialog(window):
    DrawingDialog(window).exec_()

"""File ▸ Import Image Stack (TIFF): the window's half of tiffstack.py.

The dialog shows the stack one slice at a time with what the threshold
makes solid tinted, picks the threshold (Otsu by default), the voxel
size (from the file when it says, ImageJ's spacing included), the
down-sampling and smoothing, then builds the surface. The solid lands
like any imported mesh — one Object named after the file, holding an
`stl_import` of "<stem>_volume_<key>.stl" written beside the stack (the
cache folder when that folder is read-only), so OpenSCAD renders the
same triangles. The settings ride on the mesh node as
`params["volume"]`, and the tree's right-click ▸ Imported mesh ▸ Image
stack… builds it again with others. `build` is also the MCP
`import_image_stack` body.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import hashlib
import json
from pathlib import Path

import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (QApplication, QCheckBox, QDialog,
                             QDialogButtonBox, QDoubleSpinBox, QFileDialog,
                             QFormLayout, QHBoxLayout, QLabel, QMessageBox,
                             QPushButton, QSlider, QSpinBox, QVBoxLayout)

from . import language, tiffstack

PREVIEW_PX = 360


# ---------------------------------------------------------- the build
def _stl_path(sources, settings):
    """Where the surface is written: beside the first source, else the
    cache folder; named by the settings so two imports never clash."""
    first = Path(sources[0])
    key = hashlib.sha1(json.dumps(
        [str(s) for s in sources] + [settings], sort_keys=True,
        default=str).encode()).hexdigest()[:8]
    stem = first.stem if first.is_file() else first.name
    name = f"{stem}_volume_{key}.stl"
    folder = first.parent if first.is_file() else first
    probe = folder / name
    try:
        probe.touch(exist_ok=True)
        return probe
    except OSError:
        from PyQt5.QtCore import QStandardPaths
        cache = Path(QStandardPaths.writableLocation(
            QStandardPaths.CacheLocation)) / "image_stacks"
        cache.mkdir(parents=True, exist_ok=True)
        return cache / name


def build(model, stack, settings, node=None):
    """Mesh *stack* with *settings* {threshold, invert, spacing, step,
    smooth} and put it in *model*: a new Object, or — given the mesh
    *node* — in place of that node's surface. Returns (node, info)."""
    from . import units
    # a microscope's voxels are microns: an EMPTY millimetre document
    # switches to µm (as crystals switch to nm), so the cell is 40 µm
    # across, not 0.04 mm; the surface is written in the document's unit
    if node is None and not model.root.children and model.unit == "mm" \
            and min(float(v) for v in settings["spacing"]) < 0.01:
        model.set_unit("um")
    per_unit = units.to_mm(model.unit)          # mm in one document unit
    spacing = tuple(float(v) / per_unit for v in settings["spacing"])
    tris = tiffstack.surface(
        stack, float(settings["threshold"]),
        spacing=spacing, step=int(settings["step"]),
        invert=bool(settings.get("invert")),
        smooth=bool(settings.get("smooth", True)))
    if len(tris) == 0:
        raise tiffstack.StackError(
            "nothing is solid at that threshold — lower it, or tick "
            "Invert for dark objects")
    sources = [str(s) for s in stack.sources]
    path = _stl_path(sources, settings)
    tiffstack.write_stl(tris, str(path))
    record = dict(settings, sources=sources)
    record["spacing"] = [float(v) for v in settings["spacing"]]
    if node is None:
        stem = Path(sources[0]).stem if len(sources) == 1 else \
            Path(sources[0]).parent.name
        comp = model.new_component(stem)
        node = model.add_node("stl_import", dict(path=str(path)),
                              parent=comp, name=f"{stem} volume")
        node.params["volume"] = record
        model.node_changed.emit(node)
    else:                                  # rebuilt in place (one undo step)
        node.params["path"] = str(path)
        node.params["volume"] = record
        model.node_changed.emit(node)
    arr = np.asarray(tris)
    lo, hi = arr.reshape(-1, 3).min(axis=0), arr.reshape(-1, 3).max(axis=0)
    info = dict(triangles=int(len(arr)), stl=str(path),
                size=[units.significant(float(v)) for v in hi - lo],
                unit=model.unit,
                size_mm=[units.significant(float(v) * per_unit)
                         for v in hi - lo],
                threshold=float(settings["threshold"]))
    return node, info


def default_settings(stack):
    spacing = list(stack.spacing) if stack.spacing else [1.0, 1.0, 1.0]
    return dict(threshold=tiffstack.otsu(stack.values), invert=False,
                spacing=spacing, step=tiffstack.auto_step(stack.shape),
                smooth=True)


# --------------------------------------------------------- the dialog
class StackDialog(QDialog):
    def __init__(self, stack, settings, parent=None):
        super().__init__(parent)
        self.stack = stack
        self.setWindowTitle(language.tr("Import Image Stack"))
        v = stack.values
        self.lo, self.hi = float(v.min()), float(v.max())
        lay = QVBoxLayout(self)
        names = ", ".join(Path(s).name for s in stack.sources[:3])
        if len(stack.sources) > 3:
            names += f" … ({len(stack.sources)} files)"
        head = QLabel(f"<b>{names}</b><br>{stack.describe()}")
        head.setWordWrap(True)
        lay.addWidget(head)
        self.picture = QLabel()
        self.picture.setFixedSize(PREVIEW_PX, PREVIEW_PX)
        self.picture.setAlignment(Qt.AlignCenter)
        self.picture.setStyleSheet("background: #111;")
        lay.addWidget(self.picture, 0, Qt.AlignHCenter)
        nz = v.shape[0]
        self.slice = QSlider(Qt.Horizontal)
        self.slice.setRange(0, max(nz - 1, 0))
        self.slice.setValue(nz // 2)
        self.slice_label = QLabel()
        row = QHBoxLayout()
        row.addWidget(QLabel(language.tr("Slice")))
        row.addWidget(self.slice, 1)
        row.addWidget(self.slice_label)
        lay.addLayout(row)

        form = QFormLayout()
        self.thr_slider = QSlider(Qt.Horizontal)
        self.thr_slider.setRange(0, 1000)
        self.thr = QDoubleSpinBox()
        self.thr.setDecimals(3)
        self.thr.setRange(self.lo, self.hi if self.hi > self.lo
                          else self.lo + 1)
        auto = QPushButton(language.tr("Auto"))
        auto.setToolTip(language.tr(
            "The threshold that best splits the values in two (Otsu)"))
        auto.clicked.connect(lambda: self.thr.setValue(
            tiffstack.otsu(self.stack.values)))
        trow = QHBoxLayout()
        trow.addWidget(self.thr_slider, 1)
        trow.addWidget(self.thr)
        trow.addWidget(auto)
        form.addRow(language.tr("Threshold"), trow)
        self.invert = QCheckBox(language.tr(
            "Dark objects (solid below the threshold)"))
        form.addRow("", self.invert)
        self.spacing = []
        srow = QHBoxLayout()
        for axis in "XYZ":
            box = QDoubleSpinBox()
            box.setDecimals(6)
            box.setRange(1e-9, 1e6)
            box.setSuffix(" mm")
            box.setToolTip(language.tr(
                "Size of one voxel along {axis}").format(axis=axis))
            srow.addWidget(QLabel(axis))
            srow.addWidget(box)
            self.spacing.append(box)
        form.addRow(language.tr("Voxel size"), srow)
        if stack.spacing:
            note = QLabel(language.tr("From the file ({unit}).").format(
                unit=stack.unit or "resolution tags"))
        else:
            note = QLabel(language.tr(
                "The file gives no scale: 1 mm a voxel unless you say."))
        note.setStyleSheet("color: gray;")
        form.addRow("", note)
        self.step = QSpinBox()
        self.step.setRange(1, 64)
        self.grid_label = QLabel()
        grow = QHBoxLayout()
        grow.addWidget(self.step)
        grow.addWidget(self.grid_label, 1)
        form.addRow(language.tr("Down-sample by"), grow)
        self.smooth = QCheckBox(language.tr(
            "Smooth (removes speckle noise)"))
        form.addRow("", self.smooth)
        lay.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok
                                   | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(language.tr("Import"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

        self.thr.setValue(float(settings["threshold"]))
        self._sync_slider()
        self.invert.setChecked(bool(settings.get("invert")))
        for box, val in zip(self.spacing, settings["spacing"]):
            box.setValue(float(val))
        self.step.setValue(int(settings["step"]))
        self.smooth.setChecked(bool(settings.get("smooth", True)))
        self.slice.valueChanged.connect(self._draw)
        self.thr.valueChanged.connect(lambda _v: (self._sync_slider(),
                                                  self._draw()))
        self.thr_slider.valueChanged.connect(self._slider_moved)
        self.invert.toggled.connect(self._draw)
        self.step.valueChanged.connect(self._grid)
        self._grid()
        self._draw()

    def _slider_moved(self, pos):
        if getattr(self, "_syncing", False):
            return
        self.thr.setValue(self.lo + (self.hi - self.lo) * pos / 1000.0)

    def _sync_slider(self):
        self._syncing = True
        span = (self.hi - self.lo) or 1.0
        self.thr_slider.setValue(int(round(
            (self.thr.value() - self.lo) / span * 1000)))
        self._syncing = False

    def _grid(self):
        gx, gy, gz = tiffstack.grid_size(self.stack.shape,
                                         self.step.value())
        n = gx * gy * gz
        self.grid_label.setText(language.tr(
            "grid {gx} × {gy} × {gz} ({n:.1f} M voxels)").format(
                gx=gx, gy=gy, gz=gz, n=n / 1e6))

    def _draw(self):
        k = self.slice.value()
        self.slice_label.setText(f"{k + 1} / {self.stack.values.shape[0]}")
        img = self.stack.values[k][::-1]           # row 0 on top again
        span = (self.hi - self.lo) or 1.0
        grey = np.clip((img - self.lo) / span * 255.0, 0, 255)
        rgb = np.repeat(grey[..., None], 3, axis=2)
        t = self.thr.value()
        solid = img < t if self.invert.isChecked() else img >= t
        rgb[solid] = rgb[solid] * 0.45 + np.array([230.0, 60.0, 40.0]) * 0.55
        rgb = np.ascontiguousarray(rgb.astype(np.uint8))
        h, w = rgb.shape[:2]
        qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888).copy()
        self.picture.setPixmap(QPixmap.fromImage(qimg).scaled(
            PREVIEW_PX, PREVIEW_PX, Qt.KeepAspectRatio,
            Qt.SmoothTransformation))

    def settings(self):
        return dict(threshold=self.thr.value(),
                    invert=self.invert.isChecked(),
                    spacing=[b.value() for b in self.spacing],
                    step=self.step.value(), smooth=self.smooth.isChecked())


def _busy(fn):
    QApplication.setOverrideCursor(Qt.WaitCursor)
    try:
        return fn()
    finally:
        QApplication.restoreOverrideCursor()


def import_dialog(window, paths=None):
    """File ▸ Import Image Stack: pick the file(s), set it up, build."""
    if not paths:
        paths, _ = QFileDialog.getOpenFileNames(
            window, language.tr("Import Image Stack"), "",
            language.tr("TIFF images (*.tif *.tiff);;All files (*)"))
        if not paths:
            return None
    try:
        stack = _busy(lambda: tiffstack.read_stack(paths))
    except tiffstack.StackError as exc:
        QMessageBox.warning(window, language.tr("Import Image Stack"),
                            str(exc))
        return None
    return _run(window, stack, default_settings(stack))


def _run(window, stack, settings, node=None):
    dlg = StackDialog(stack, settings, window)
    if dlg.exec_() != QDialog.Accepted:
        return None
    try:
        node, info = _busy(lambda: build(window.model, stack,
                                         dlg.settings(), node))
    except tiffstack.StackError as exc:
        QMessageBox.warning(window, language.tr("Import Image Stack"),
                            str(exc))
        return None
    comp = node.parent if node.parent is not None else node
    window.builder.tree.select_nodes([comp])
    if not window.view3d.user_moved:
        window.view3d.fit()
    from . import units
    window.statusBar().showMessage(language.tr(
        "Image stack: {n} triangles, {x:g} × {y:g} × {z:g} {u}, saved as "
        "{name}.").format(n=info["triangles"], x=info["size"][0],
                          y=info["size"][1], z=info["size"][2],
                          u=units.symbol(info["unit"]),
                          name=Path(info["stl"]).name), 12000)
    return node


def redo_dialog(window, node):
    """Right-click ▸ Imported mesh ▸ Image stack…: the same dialog on
    the node's own settings; Import rebuilds its surface in place."""
    record = node.params.get("volume") or {}
    try:
        stack = _busy(lambda: tiffstack.read_stack(record["sources"]))
    except (KeyError, tiffstack.StackError) as exc:
        QMessageBox.warning(window, language.tr("Import Image Stack"),
                            language.tr("The image stack is not there any "
                                        "more: {e}").format(e=exc))
        return None
    settings = dict(default_settings(stack))
    settings.update({k: record[k] for k in settings if k in record})
    return _run(window, stack, settings, node)


# ---------------------------------------------------------------- MCP
def mcp_import(executor, params):
    """The MCP `import_image_stack` body."""
    paths = params.get("paths") or ([params["path"]] if params.get("path")
                                    else [])
    if not paths:
        raise tiffstack.StackError("give path (a TIFF or a folder of "
                                   "them) or paths")
    stack = tiffstack.read_stack([str(Path(p).expanduser())
                                  for p in paths])
    settings = default_settings(stack)
    thr = params.get("threshold", "auto")
    if thr not in (None, "auto"):
        settings["threshold"] = float(thr)
    for key in ("invert", "smooth"):
        if params.get(key) is not None:
            settings[key] = bool(params[key])
    if params.get("voxel_size"):
        size = params["voxel_size"]
        size = [size] * 3 if isinstance(size, (int, float)) else size
        if len(size) != 3 or min(float(s) for s in size) <= 0:
            raise tiffstack.StackError("voxel_size is [x, y, z] mm, "
                                       "all above 0")
        settings["spacing"] = [float(s) for s in size]
    if params.get("step"):
        settings["step"] = max(int(params["step"]), 1)
    node, info = build(executor._model, stack, settings)
    info.update(node_id=node.id, object_id=node.parent.id,
                stack=stack.describe(),
                voxel_size_mm=settings["spacing"], step=settings["step"],
                scale_from_file=stack.spacing is not None)
    return info

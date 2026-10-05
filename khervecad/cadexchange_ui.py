"""The window's half of CAD exchange: File ▸ Import CAD File and File ▸
Export for Other CAD (STEP, IGES, Rhino), drag and drop, File ▸ Open.

The rule that shaped it: somebody opening a STEP file from a supplier
should not have to know what XCAF, tessellation or deflection are. So:

* Open and drop just WORK — no dialog. Normal quality, the parts land
  as one Object named after the file, each part a group with its own
  name and colour, sized in the document's unit, framed in the view.
  The status line says how many parts arrived and how big the whole is.
* The Import menu item adds the one choice that matters, mesh quality
  (Draft / Normal / Fine), with a sentence on when to pick each.
* Export asks only for a file name: the format follows the extension
  the user picks in the dialog, the file is always in real millimetres
  (STEP carries its unit), and the answer is one plain sentence saying
  whether the surfaces are exact or faceted, and which parts were not.
* A missing engine is a message that names the pip command, never a
  traceback.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import re
from pathlib import Path

from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtWidgets import (QApplication, QDialog, QDialogButtonBox,
                             QFileDialog, QLabel, QMessageBox, QRadioButton,
                             QVBoxLayout)

from . import cadexchange as cx
from . import language

#: the file-dialog filters, most useful first
IMPORT_FILTER = ("CAD files (*.step *.stp *.iges *.igs *.3dm *.brep);;"
                 "STEP (*.step *.stp);;IGES (*.iges *.igs);;"
                 "Rhino (*.3dm);;OpenCascade BREP (*.brep)")
EXPORT_FILTERS = [
    ("STEP — for Fusion, SolidWorks, Onshape, FreeCAD, Rhino (*.step)",
     ".step"),
    ("IGES — for older CAD programs (*.iges)", ".iges"),
    ("Rhino 3DM — meshes on named layers (*.3dm)", ".3dm"),
    ("OpenCascade BREP (*.brep)", ".brep"),
]

_HINTS = {
    "Draft": "Fastest. Big assemblies, or a first look.",
    "Normal": "Smooth enough for most parts. The usual choice.",
    "Fine": "Smoothest curves, for renders — slower, larger.",
}


def _settings():
    return QSettings("KherveCAD", "KherveCAD")


def quality_setting() -> str:
    q = str(_settings().value("cad/quality", "Normal"))
    return q if q in cx.QUALITY else "Normal"


class QualityDialog(QDialog):
    """One question: how smooth? The answer is remembered."""

    def __init__(self, parent, name):
        super().__init__(parent)
        self.setWindowTitle(language.tr("Import CAD file"))
        lay = QVBoxLayout(self)
        intro = QLabel(language.tr(
            "<b>{name}</b><br>Curved surfaces are turned into small "
            "flat facets to show them. How smooth should they be?")
            .format(name=name))
        intro.setWordWrap(True)
        lay.addWidget(intro)
        self.buttons = {}
        current = quality_setting()
        for key in cx.QUALITY:
            rb = QRadioButton(f"{language.tr(key)} — "
                              f"{language.tr(_HINTS[key])}")
            rb.setChecked(key == current)
            self.buttons[key] = rb
            lay.addWidget(rb)
        box = QDialogButtonBox(QDialogButtonBox.Ok |
                               QDialogButtonBox.Cancel)
        box.button(QDialogButtonBox.Ok).setText(language.tr("Import"))
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        lay.addWidget(box)

    def choice(self):
        for key, rb in self.buttons.items():
            if rb.isChecked():
                return key
        return "Normal"


# ================================================================ import

def import_cad_dialog(window):
    """File ▸ Import CAD File… — pick a file, pick the smoothness."""
    start = str(_settings().value("cad/last_dir", ""))
    path, _ = QFileDialog.getOpenFileName(
        window, language.tr("Import CAD file"), start,
        language.tr(IMPORT_FILTER))
    if not path:
        return None
    _settings().setValue("cad/last_dir", str(Path(path).parent))
    dlg = QualityDialog(window, Path(path).name)
    if dlg.exec_() != QDialog.Accepted:
        return None
    _settings().setValue("cad/quality", dlg.choice())
    return import_cad(window, path, dlg.choice())


def _safe(name):
    return re.sub(r"[^\w\- .]+", "_", name).strip() or "part"


def _mesh_folder(path):
    """Where each part's mesh file goes: a "<stem> parts" folder beside
    the CAD file, or the cache when that folder cannot be written (a
    read-only share, a mounted disk image)."""
    folder = Path(path).with_name(Path(path).stem + " parts")
    try:
        folder.mkdir(exist_ok=True)
        probe = folder / ".kcad-write-test"
        probe.write_bytes(b"")
        probe.unlink()
        return folder
    except OSError:
        from PyQt5.QtCore import QStandardPaths
        base = QStandardPaths.writableLocation(QStandardPaths.CacheLocation)
        folder = Path(base or Path.home()) / "imports" / _safe(
            Path(path).stem)
        folder.mkdir(parents=True, exist_ok=True)
        return folder


def import_cad(window, path, quality=None):
    """Read *path* into the document. Returns the Object made, or None
    (the reason already shown). No dialog: this is what Open and a
    drop call."""
    from . import units
    quality = quality or quality_setting()
    name = Path(path).name
    problem = cx.missing(Path(path).suffix)
    if problem:
        QMessageBox.warning(window, language.tr("Import CAD file"),
                            language.tr(problem))
        return None
    QApplication.setOverrideCursor(Qt.WaitCursor)
    window.statusBar().showMessage(
        language.tr("Reading {name}…").format(name=name))
    QApplication.processEvents()
    try:
        parts = cx.read_parts(path, quality)
    except (ValueError, OSError, RuntimeError) as exc:
        QApplication.restoreOverrideCursor()
        QMessageBox.warning(window, language.tr("Import CAD file"),
                            language.tr(str(exc)))
        return None
    finally:
        if QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()
    node = place_parts(window.model, path, parts, units.to_mm(
        window.model.unit))
    tree = getattr(window, "builder", None)
    if tree is not None:
        tree.tree.select_nodes([node])
    view = getattr(window, "view3d", None)
    if view is not None and not view.user_moved:
        view.fit()
    window.statusBar().showMessage(summary(parts, window.model.unit),
                                   15000)
    if hasattr(window, "_add_recent"):
        window._add_recent(str(path))
    return node


def place_parts(model, path, parts, unit_mm=1.0):
    """The parts into *model* as one Object named after the file: a
    group per part (name + colour) holding its mesh. Each mesh is
    written as an STL beside the file so the OpenSCAD engine renders
    the same triangles the preview shows. Qt-free apart from the
    model's signals, so the tests drive it directly."""
    from .engine import write_stl
    stem = Path(path).stem
    folder = _mesh_folder(path)
    k = 1.0 / unit_mm if unit_mm else 1.0
    comp = model.new_component(stem)
    exact = Path(path).suffix.lower() in cx.OCC_EXTS
    for index, part in enumerate(parts):
        tris = part.tris if k == 1.0 else [
            tuple((v[0] * k, v[1] * k, v[2] * k) for v in t)
            for t in part.tris]
        stl = folder / f"{_safe(part.name)}.stl"
        write_stl(tris, str(stl), part.name)
        if len(parts) == 1:
            holder = comp
        else:
            holder = model.add_node("union", {}, parent=comp,
                                    name=part.name)
        target = holder
        if part.color:
            target = model.add_node("color", dict(color=part.color),
                                    parent=holder, name="Color")
        params = dict(path=str(stl))
        if exact:
            # remembered so an export writes the file's own surfaces
            params.update(cad_source=str(Path(path).resolve()),
                          cad_part=index)
        model.add_node("stl_import", params, parent=target,
                       name=part.name)
    return comp


def summary(parts, unit="mm") -> str:
    from . import units
    pts = [v for p in parts for t in p.tris for v in t]
    size = ""
    if pts:
        k = 1.0 / units.to_mm(unit)
        dims = [(max(p[i] for p in pts) - min(p[i] for p in pts)) * k
                for i in range(3)]
        size = " — {} × {} × {} {}".format(
            *(units.tidy(d, 1) for d in dims), units.symbol(unit))
    n = len(parts)
    what = language.tr("1 part") if n == 1 else \
        language.tr("{n} parts").format(n=n)
    return language.tr(
        "Imported {what}{size}. Each part is a group in the Object "
        "tab with its own colour; drag the Object to place it.").format(
        what=what, size=size)


# ================================================================ export

def export_cad_dialog(window):
    """File ▸ Export for Other CAD… — STEP by default."""
    filters = ";;".join(language.tr(f) for f, _e in EXPORT_FILTERS)
    last = str(_settings().value("cad/export_ext", ".step"))
    chosen = next((language.tr(f) for f, e in EXPORT_FILTERS if e == last),
                  None)
    base = Path(window._path).with_suffix(last) if getattr(
        window, "_path", None) else Path(
        str(_settings().value("cad/last_dir", ""))) / ("model" + last)
    path, picked = QFileDialog.getSaveFileName(
        window, language.tr("Export for other CAD"), str(base), filters,
        chosen)
    if not path:
        return None
    ext = Path(path).suffix.lower()
    if ext not in cx.CAD_EXTS:
        ext = next((e for f, e in EXPORT_FILTERS
                    if language.tr(f) == picked), ".step")
        path += ext
    _settings().setValue("cad/export_ext", ".iges" if ext == ".igs" else
                         ".step" if ext == ".stp" else ext)
    _settings().setValue("cad/last_dir", str(Path(path).parent))
    return export_cad(window, path)


def export_cad(window, path, interactive=True):
    """Write the document to *path*. Returns the Report (or raises
    ValueError when not interactive)."""
    from . import units
    fn = window.model.effective_fn()
    QApplication.setOverrideCursor(Qt.WaitCursor)
    try:
        report = cx.export_model(window.model.root, path, fn=fn,
                                 unit_mm=units.to_mm(window.model.unit))
    except (ValueError, OSError, RuntimeError) as exc:
        QApplication.restoreOverrideCursor()
        if not interactive:
            raise ValueError(str(exc))
        QMessageBox.warning(window, language.tr("Export for other CAD"),
                            language.tr(str(exc)))
        return None
    QApplication.restoreOverrideCursor()
    fmt = cx.FORMAT_NAMES.get(Path(path).suffix.lower(), "CAD")
    if interactive:
        box = QMessageBox(window)
        box.setWindowTitle(language.tr("Export for other CAD"))
        box.setIcon(QMessageBox.Information)
        box.setText(language.tr(report.sentence(fmt)))
        box.setInformativeText(str(path))
        show = box.addButton(language.tr("Show in Folder"),
                             QMessageBox.ActionRole)
        box.addButton(QMessageBox.Ok)
        box.exec_()
        if box.clickedButton() is show:
            from PyQt5.QtGui import QDesktopServices
            from PyQt5.QtCore import QUrl
            QDesktopServices.openUrl(QUrl.fromLocalFile(
                str(Path(path).parent)))
    return report

"""Make2D — Rhino's line drawing of the model exactly as the 3D view
looks at it (File ▸ Make 2D Drawing of This View…).

The Blueprint draws the standard views; Make2D draws the ONE the user
has turned the model to — a three-quarter view for a brochure, a
section-free outline for a laser cutter, any angle — as clean vector
lines: every crease and the silhouette, hidden edges left out (or
dashed when asked). It reuses the Blueprint's own projection
(`drawing.view_lines`) through a temporary "Current view" entry built
from the camera, and the drawing exporters, so SVG, DXF, PDF and PNG
come out with the same quality as the engineering sheet, at a standard
scale with a title block.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

VIEW = "Current view"
FILTERS = ("SVG drawing (*.svg);;DXF for CAD and laser cutters (*.dxf);;"
           "PDF (*.pdf);;PNG picture (*.png)")


@contextmanager
def camera_view(view3d):
    """drawing.VIEWS["Current view"] while inside: the 3D view's own
    right / up / forward, so the lines are what the screen shows
    (as a parallel projection)."""
    from . import drawing
    _eye, right, up, forward = view3d._camera()
    drawing.VIEWS[VIEW] = (tuple(right), tuple(up), tuple(forward))
    try:
        yield VIEW
    finally:
        drawing.VIEWS.pop(VIEW, None)


def make(window, path, hidden=False, sheet="A4", title=None):
    """Write the current view's line drawing to *path* (.svg / .dxf /
    .pdf / .png). Returns the layout. Raises ValueError with a sentence
    for the user."""
    from . import drawing_dialog, drawing_export
    suffix = Path(path).suffix.lower()
    if suffix not in drawing_export.WRITERS:
        raise ValueError("Make 2D writes .svg, .dxf, .pdf or .png")
    with camera_view(window.view3d) as name:
        lay = drawing_dialog.make_layout(
            window, sheet=sheet, views=(name,), dimensions=False,
            title=title, hidden_lines=hidden)
        drawing_export.export(lay, path)
    return lay


def open_dialog(window):
    """Ask where (the format follows the extension) and whether to dash
    the hidden edges, then write it and say where it went."""
    from PyQt5.QtCore import QSettings
    from PyQt5.QtWidgets import QCheckBox, QFileDialog, QMessageBox
    from . import language
    settings = QSettings("Kherve", "KherveCAD")
    start = str(settings.value("make2d/last", ""))
    if not start and getattr(window, "_path", None):
        start = str(Path(window._path).with_suffix(".svg"))
    dlg = QFileDialog(window, language.tr("Make 2D drawing of this view"),
                      start, language.tr(FILTERS))
    dlg.setAcceptMode(QFileDialog.AcceptSave)
    dlg.setOption(QFileDialog.DontUseNativeDialog, True)
    hidden = QCheckBox(language.tr("Show hidden edges dashed"))
    hidden.setChecked(settings.value("make2d/hidden", False, type=bool))
    lay = dlg.layout()
    if lay is not None:
        lay.addWidget(hidden, lay.rowCount(), 0, 1, -1)
    if not dlg.exec_():
        return None
    path = dlg.selectedFiles()[0]
    if Path(path).suffix.lower() not in (".svg", ".dxf", ".pdf", ".png"):
        ext = {"SVG": ".svg", "DXF": ".dxf", "PDF": ".pdf", "PNG": ".png"}
        path += next((e for k, e in ext.items()
                      if dlg.selectedNameFilter().startswith(k)), ".svg")
    settings.setValue("make2d/last", path)
    settings.setValue("make2d/hidden", hidden.isChecked())
    try:
        make(window, path, hidden=hidden.isChecked())
    except (ValueError, OSError) as exc:
        QMessageBox.warning(window, language.tr("Make 2D"),
                            language.tr(str(exc)))
        return None
    window.statusBar().showMessage(language.tr(
        "Line drawing of this view saved to {path}.").format(path=path),
        10000)
    return path

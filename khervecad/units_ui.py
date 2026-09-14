"""The Qt side of the document unit (units.py): Edit ▸ Document
Units…, the main window's readouts following a change, and Export
STL's question about scaling to millimetres. The main window keeps
thin wrappers only.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtWidgets import QInputDialog, QMessageBox

from . import units


def choose(win):
    """Edit ▸ Document Units… — what one model unit stands for. A
    label: nothing in the model is rescaled."""
    options = units.choices()
    labels = [label for _code, label in options]
    current = [code for code, _l in options].index(
        units.coerce(win.model.unit))
    label, ok = QInputDialog.getItem(
        win, "Document units",
        "One model unit is one…\n(the geometry is not rescaled — "
        "only what the numbers are called)", labels, current, False)
    if ok:
        win.model.set_unit(options[labels.index(label)][0])


def changed(win, unit):
    """Every readout follows the new unit; the model is unchanged."""
    u = units.symbol(unit)
    win._zoom_label.setText(f"1 {u} = {win.view2d.px_per_mm():.2f} px")
    win._cursor_label.setText(f"x: 0.0 {u}  y: 0.0 {u}")
    win._show_dimensions(getattr(win.view3d, "highlight_mesh", None))
    win.scene.clear_measure()
    win.view2d.viewport().update()
    win.view3d.unit = unit                # the 3D scale bar's label
    win.view3d.update()
    if getattr(win.view3d, "cut", None) is not None:
        win._sync_cut()
    win._dirty = True
    win._update_title()
    win.statusBar().showMessage(
        f"Units: {units.name(unit)} — every readout now says {u}; the "
        "geometry itself is unchanged.", 6000)


def export_scale(win):
    """How an STL of this document should be written: 1.0 (1:1), the
    factor to millimetres, or None (cancelled). A mm document is never
    asked — an STL is conventionally millimetres already."""
    unit = win.model.unit
    if units.coerce(unit) == "mm":
        return 1.0
    box = QMessageBox(win)
    box.setWindowTitle("Export STL")
    box.setIcon(QMessageBox.Question)
    box.setText(units.export_note(unit))
    scale = box.addButton(f"Scale to millimetres (×{units.to_mm(unit):g})",
                          QMessageBox.AcceptRole)
    keep = box.addButton(f"Keep 1:1 (1 {units.symbol(unit)} → 1 mm)",
                         QMessageBox.AcceptRole)
    box.addButton(QMessageBox.Cancel)
    box.setDefaultButton(keep)
    box.exec_()
    if box.clickedButton() is scale:
        return units.to_mm(unit)
    if box.clickedButton() is keep:
        return 1.0
    return None

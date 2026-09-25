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

from . import language, units


def _unit_name(unit) -> str:
    """`units.name()`, translated for display — `units.py` is Qt-free
    by design (used from the MCP subprocess, which never imports Qt),
    so the translation happens here, at the point of display."""
    return language.tr(units.name(unit))


def choose(win):
    """Edit ▸ Document Units… — what one model unit stands for. A
    label: nothing in the model is rescaled."""
    options = units.choices()
    labels = [f"{units.symbol(code)} — {_unit_name(code)}"
             for code, _label in options]
    current = [code for code, _l in options].index(
        units.coerce(win.model.unit))
    label, ok = QInputDialog.getItem(
        win, language.tr("Document units"),
        language.tr("One model unit is one…\n(the geometry is not "
                    "rescaled — only what the numbers are called)"),
        labels, current, False)
    if ok:
        win.model.set_unit(options[labels.index(label)][0])


def choose_scale(win):
    """Edit ▸ Document Scale… — how the model compares with the real
    thing, as 1 : N. The scale bar then measures the real thing (a
    60 mm Earth's bar says kilometres). A label: nothing is rescaled."""
    from PyQt5.QtWidgets import QInputDialog
    text, ok = QInputDialog.getText(
        win, language.tr("Document scale"),
        language.tr(
            "The model is to the real thing as…\n"
            "1 : 1 is life size; 1 : 250000000 a planet on a desk; "
            "25 : 1 an insect enlarged.\nThe scale bar then measures "
            "the real thing — the geometry is not rescaled."),
        text=units.ratio_text(win.model.real_scale))
    if not ok:
        return
    try:
        win.model.set_real_scale(text)
    except ValueError:
        QMessageBox.warning(win, language.tr("Document scale"),
                            language.tr(
                                "{text!r} is not a scale — write it as "
                                "1 : 250000000, or 25 : 1.").format(
                                    text=text))


def scale_changed(win, n):
    """The scale bar measures the real thing at 1 : *n*."""
    win.view3d.real_scale = n
    win.view3d.update()
    win._dirty = True
    win._update_title()
    what = (language.tr("life size") if abs(n - 1.0) < 1e-9
           else units.ratio_text(n))
    win.statusBar().showMessage(language.tr(
        "Scale: {what} — the scale bar now measures the real thing; "
        "the geometry itself is unchanged.").format(what=what), 6000)


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
    win.statusBar().showMessage(language.tr(
        "Units: {name} — every readout now says {symbol}; the "
        "geometry itself is unchanged.").format(
            name=_unit_name(unit), symbol=u), 6000)


def export_scale(win):
    """How an STL of this document should be written: 1.0 (1:1), the
    factor to millimetres, or None (cancelled). A mm document is never
    asked — an STL is conventionally millimetres already."""
    unit = win.model.unit
    if units.coerce(unit) == "mm":
        return 1.0
    box = QMessageBox(win)
    title = language.tr("Export STL")
    box.setWindowTitle(title)
    box.setIcon(QMessageBox.Question)
    box.setText(language.tr(
        "The document is in {name}. STL and 3MF files are read as "
        "millimetres, so exported 1:1 each {symbol} becomes 1 mm; "
        "scaled to millimetres every length is multiplied by "
        "{factor:g}.").format(name=_unit_name(unit),
                              symbol=units.symbol(unit),
                              factor=units.to_mm(unit)))
    scale = box.addButton(
        language.tr("Scale to millimetres (×{factor:g})").format(
            factor=units.to_mm(unit)), QMessageBox.AcceptRole)
    keep = box.addButton(
        language.tr("Keep 1:1 (1 {symbol} → 1 mm)").format(
            symbol=units.symbol(unit)), QMessageBox.AcceptRole)
    box.addButton(QMessageBox.Cancel)
    box.setDefaultButton(keep)
    box.exec_()
    if box.clickedButton() is scale:
        return units.to_mm(unit)
    if box.clickedButton() is keep:
        return 1.0
    return None

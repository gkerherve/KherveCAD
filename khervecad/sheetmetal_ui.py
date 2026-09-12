"""The window side of sheet metal: Unfold and Export flat pattern.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from pathlib import Path

from PyQt5.QtWidgets import QFileDialog, QMessageBox

from . import sheetmetal


def _env(window):
    from . import anchors
    return anchors.doc_env(window.model)


def unfold(window, node):
    """Add the flat pattern as a polygon beside the part, as a new
    Object, and say how big the blank is."""
    model = window.model
    poly, pat = sheetmetal.unfold_node(node, _env(window))
    ext = model.add_node("linear_extrude",
                         dict(height=pat["thickness"]))
    ext.name = f"{node.name} blank"
    model.root.remove(ext)
    ext.add(poly)
    model.root.add(ext)
    model.structure_changed.emit()
    comp = model.enclose_as_part(ext, f"{node.name} flat pattern")
    model.set_param(comp, "x", round(float(node.params.get("x", 0.0))
                                     + pat["width"] * 0.0, 3))
    model.set_param(comp, "y", -pat["height"] - 20.0)
    window.builder.tree.select_nodes([comp])
    lines = ", ".join(f"{f['edge'].upper()} {f['allowance']:.2f} mm"
                      for f in pat["flanges"])
    window.statusBar().showMessage(
        f"Flat pattern: {pat['width']:.1f} × {pat['height']:.1f} mm blank"
        + (f" — bend allowance {lines}" if lines else "")
        + " — Ctrl+Z to undo.", 10000)
    return comp


def export_flat(window, node):
    pat = sheetmetal.flat_pattern(node.params, _env(window))
    start = str(Path(window._path).with_name(
        f"{node.name}-flat.dxf")) if window._path else f"{node.name}-flat.dxf"
    path, _f = QFileDialog.getSaveFileName(window, "Export flat pattern",
                                           start, "DXF (*.dxf)")
    if not path:
        return None
    if not path.lower().endswith(".dxf"):
        path += ".dxf"
    try:
        sheetmetal.flat_dxf(pat, path)
    except OSError as exc:
        QMessageBox.warning(window, "Export flat pattern",
                            f"Could not write the DXF:\n{exc}")
        return None
    window.statusBar().showMessage(
        f"Flat pattern written: {path} ({pat['width']:.1f} × "
        f"{pat['height']:.1f} mm, CUT and BEND layers).", 8000)
    return path

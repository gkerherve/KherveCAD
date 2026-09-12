"""Library ▸ Convert to Lego… and Library ▸ Fuse Lego into one solid —
the window side of legoize.py (also on the tree's right-click menu).

Both work on the selection (else the Object being edited) and never
touch it: the result arrives as a new Object in Main, placed just to
the right of the source so the two can be compared, and one Ctrl+Z
takes it away again.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtWidgets import (QComboBox, QDialog, QDialogButtonBox,
                             QFormLayout, QLabel, QMessageBox, QSpinBox)

from . import legoize, mesh
from .library_lego import COLORS

#: the gap between a source and the Object made from it (mm)
GAP_MM = 20.0


def source(window):
    """The node to convert: the first selected row, else the Object
    open in the Object tab, else None."""
    nodes = window.builder.active_tree().selected_nodes()
    if nodes:
        return nodes[0]
    return window.builder.isolated_component()


def _mesh(window, node):
    colored = mesh.tessellate_colored(node, fn=window.model.effective_fn())
    return [t for t, _c in colored], [c for _t, c in colored]


def _place(window, node, name, beside):
    """Add *node* to Main as a new visible Object, to the right of the
    source's bounding box *beside* (lo, hi)."""
    model = window.model
    model.root.add(node)
    model.structure_changed.emit()
    comp = model.enclose_as_part(node, name)
    lo, hi = beside
    model.set_param(comp, "x", round(hi[0] + GAP_MM, 3))
    model.set_param(comp, "y", round(lo[1], 3))
    window.builder.tree.select_nodes([comp])
    return comp


class ToLegoDialog(QDialog):
    """How big, how fine, and in which colours."""

    def __init__(self, name, size, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Convert to Lego")
        form = QFormLayout(self)
        form.addRow(QLabel(f"<b>{name}</b> — {size[0]:.0f} × {size[1]:.0f}"
                           f" × {size[2]:.0f} mm"))
        self.studs = QSpinBox()
        self.studs.setRange(4, 96)
        self.studs.setValue(24)
        self.studs.setSuffix(" studs")
        self.studs.setToolTip("Studs along the longer horizontal side: "
                              "more studs, more detail, more bricks")
        form.addRow("Across:", self.studs)
        self.layers = QComboBox()
        self.layers.addItems(["Bricks (9.6 mm a layer)",
                              "Plates (3.2 mm — finer, for thin parts)"])
        form.addRow("Layers:", self.layers)
        self.colour = QComboBox()
        self.colour.addItem("The part's own colours")
        self.colour.addItems(list(COLORS))
        form.addRow("Colour:", self.colour)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok
                                   | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def options(self):
        return dict(studs_across=self.studs.value(),
                    plates=self.layers.currentIndex() == 1,
                    colour=None if self.colour.currentIndex() == 0
                    else self.colour.currentText())


def convert_to_lego(window, node=None, options=None):
    """Voxelize the selection into bricks (asks how, unless *options*
    are given). Returns the new Object, or None."""
    node = node or source(window)
    if node is None:
        window.statusBar().showMessage(
            "Select the part to convert to Lego first.", 5000)
        return None
    tris, colours = _mesh(window, node)
    if not tris:
        QMessageBox.information(window, "Convert to Lego",
                                f"{node.name} has no solid to convert.")
        return None
    lo, hi = legoize.bounds(tris)
    if options is None:
        dialog = ToLegoDialog(node.name, [b - a for a, b in zip(lo, hi)],
                              window)
        if dialog.exec_() != QDialog.Accepted:
            return None
        options = dialog.options()
    try:
        lego, info = legoize.to_lego(tris, colours, name=f"{node.name} "
                                     "(Lego)", **options)
    except ValueError as exc:
        QMessageBox.warning(window, "Convert to Lego", str(exc))
        return None
    comp = _place(window, lego, f"{node.name} Lego", (lo, hi))
    w, d, h = info["size_mm"]
    window.statusBar().showMessage(
        f"{node.name} in Lego: {info['pieces']} bricks, "
        f"{info['studs'][0]} × {info['studs'][1]} studs, "
        f"{w:.0f} × {d:.0f} × {h:.0f} mm — Ctrl+Z to undo.", 10000)
    return comp


def fuse_lego(window, node=None):
    """Fuse the selected brick build into one stud-free solid Object."""
    node = node or source(window)
    if node is None:
        window.statusBar().showMessage(
            "Select the Lego build to fuse first.", 5000)
        return None
    tris, colours = _mesh(window, node)
    try:
        solid, info = legoize.to_solid(tris, colours,
                                       name=f"{node.name} (solid)")
    except ValueError as exc:
        QMessageBox.warning(window, "Fuse Lego", str(exc))
        return None
    comp = _place(window, solid, f"{node.name} solid",
                  legoize.bounds(tris))
    window.statusBar().showMessage(
        f"{node.name} fused into one solid: {info['blocks']} blocks in "
        f"{info['colours']} colour(s), no studs, no seams — Ctrl+Z to "
        "undo.", 10000)
    return comp

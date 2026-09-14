"""Sculpting by clicking the 3D view: a small non-modal panel (brush,
radius, strength, mirror) that keeps the view's pick mode armed on the
sculpt node's part. Every click lands one stroke where the surface was
hit — in the part's LOCAL frame, so the sculpt survives placing the
Object — and the baked mesh recomputes at once.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QFormLayout,
                             QHBoxLayout, QLabel, QPushButton, QVBoxLayout)

from . import mesh, sculpt


def meshes(window, node):
    """``(world_tris, local_tris)`` of the sculpt node's CURRENT surface
    — as the view shows it and as the node computes it, same order —
    or ``(None, None)``."""
    from . import bake
    root = window._render_scope()[0]
    iso = root if root is not window.model.root else None
    fn = window.model.effective_fn()
    with window._isolated_frame(iso):
        world = mesh.selected_world_tris(root, {node.id}, fn=fn)
    env = bake._codegen_env(node)
    mesh._set_fn(fn)
    try:
        _points, _faces, local = bake.baked(node, env)
    except Exception:
        local = []
    finally:
        mesh._set_fn(None)
    if not world or len(world) != len(local):
        return None, None
    return world, local


def add_stroke(model, node, kind, point, radius, strength, direction=None,
               world=None, local=None) -> bool:
    """Append one stroke to *node* (a sculpt). *point*/*direction* are
    world coordinates when *world*/*local* are given, else local."""
    if world is not None:
        point, direction = sculpt.to_local(world, local, point, direction)
        if point is None:
            return False
    k = sculpt.kind_index(kind)
    if k < 0:
        return False
    d = list(direction) if direction is not None else [0.0, 0.0, 0.0]
    row = [k] + [round(float(v), 3) for v in point] + [
        round(float(radius), 3), round(float(strength), 3)] + [
        round(float(v), 4) for v in d]
    rows = [list(r) for r in (node.params.get("strokes") or [])]
    model.set_param(node, "strokes", rows + [row])
    return True


class SculptPanel(QDialog):
    """Brush settings + the armed pick. Closing the panel ends the
    sculpt (the strokes stay on the node)."""

    def __init__(self, window, node):
        super().__init__(window)
        self.setWindowTitle(f"Sculpt — {node.name}")
        self.setWindowFlag(Qt.Tool, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.window_, self.node = window, node
        self._world = self._local = None
        form = QFormLayout()
        self.kind = QComboBox()
        for name in sculpt.KINDS:
            self.kind.addItem(name.capitalize(), name)
        self.kind.setCurrentIndex(1)                 # inflate
        self.radius = QDoubleSpinBox()
        self.radius.setRange(0.05, 10000.0)
        self.radius.setValue(5.0)
        self.radius.setSuffix(" mm")
        self.strength = QDoubleSpinBox()
        self.strength.setRange(-1000.0, 1000.0)
        self.strength.setDecimals(2)
        self.strength.setValue(1.0)
        self.mirror = QComboBox()
        for name in sculpt.MIRRORS:
            self.mirror.addItem(name, name)
        self.mirror.setCurrentText(str(node.params.get("mirror", "none")))
        self.mirror.currentTextChanged.connect(self._set_mirror)
        form.addRow("Brush", self.kind)
        form.addRow("Radius", self.radius)
        form.addRow("Strength", self.strength)
        form.addRow("Mirror", self.mirror)
        self.count = QLabel()
        undo = QPushButton("Undo last stroke")
        undo.clicked.connect(self.undo_last)
        done = QPushButton("Done")
        done.clicked.connect(self.close)
        row = QHBoxLayout()
        row.addWidget(undo)
        row.addStretch(1)
        row.addWidget(done)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(QLabel("Click the surface in the 3D view to sculpt. "
                             "Grab drags along the surface normal; a "
                             "negative strength pushes in."))
        lay.addWidget(self.count)
        lay.addLayout(row)
        self._refresh_count()
        self.arm()

    # -- the pick -------------------------------------------------------
    def _banner(self):
        n = len(self.node.params.get("strokes") or [])
        return (f"Sculpt: {self.kind.currentData()} brush, "
                f"{self.radius.value():g} mm · {n} stroke(s) · click the "
                "surface; Esc or right-click when done")

    def arm(self):
        self._world, self._local = meshes(self.window_, self.node)
        if self._world is None:
            self.window_.statusBar().showMessage(
                f"{self.node.name}: nothing to sculpt yet — put a solid "
                "inside it first.", 6000)
            return
        self.window_.view3d.start_pick(
            self._on_pick, groups=[(self.node, self._world)],
            banner=self._banner(),
            labeler=lambda desc, _k: f"{self.kind.currentData()} here")

    def _on_pick(self, desc, _key):
        if desc is None:                       # Esc / right-click
            self.window_.statusBar().showMessage(
                "Sculpting paused — click a brush in the panel to "
                "continue, or Done.", 5000)
            return
        ok = add_stroke(
            self.window_.model, self.node, self.kind.currentData(),
            desc.get("point"), self.radius.value(), self.strength.value(),
            desc.get("normal"), world=self._world, local=self._local)
        if not ok:
            self.window_.statusBar().showMessage(
                "That click missed the sculpted surface.", 3000)
        self._refresh_count()
        self.arm()                             # the surface has moved

    def _set_mirror(self, name):
        self.window_.model.set_param(self.node, "mirror", name)
        self.arm()

    def undo_last(self):
        rows = [list(r) for r in (self.node.params.get("strokes") or [])]
        if rows:
            self.window_.model.set_param(self.node, "strokes", rows[:-1])
        self._refresh_count()
        self.arm()

    def _refresh_count(self):
        self.count.setText(
            f"{len(self.node.params.get('strokes') or [])} stroke(s)")

    def closeEvent(self, event):
        view = self.window_.view3d
        if getattr(view, "_pick_cb", None) is not None:
            view.cancel_pick() if hasattr(view, "cancel_pick") else None
        super().closeEvent(event)


def start(window, node):
    """Open the sculpt panel for *node* (a sculpt) and arm the pick."""
    panel = SculptPanel(window, node)
    panel.show()
    window._sculpt_panel = panel
    return panel

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

from . import language, mesh, sculpt


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


def stroke_row(kind, point, radius, strength, direction=None,
               world=None, local=None):
    """One stroke row for a sculpt, or None. *point*/*direction* are
    world coordinates when *world*/*local* are given, else local."""
    if world is not None:
        point, direction = sculpt.to_local(world, local, point, direction)
        if point is None:
            return None
    k = sculpt.kind_index(kind)
    if k < 0:
        return None
    d = list(direction) if direction is not None else [0.0, 0.0, 0.0]
    return [k] + [round(float(v), 3) for v in point] + [
        round(float(radius), 3), round(float(strength), 3)] + [
        round(float(v), 4) for v in d]


def add_stroke(model, node, kind, point, radius, strength, direction=None,
               world=None, local=None) -> bool:
    """Append one stroke to *node* (a sculpt). *point*/*direction* are
    world coordinates when *world*/*local* are given, else local."""
    row = stroke_row(kind, point, radius, strength, direction, world, local)
    if row is None:
        return False
    rows = [list(r) for r in (node.params.get("strokes") or [])]
    model.set_param(node, "strokes", rows + [row])
    return True


def add_line(model, node, kind, start, end, radius, strength,
             world=None, local=None) -> bool:
    """Append a crease / ridge from *start* to *end* (world points when
    *world*/*local* are given, else the node's own frame)."""
    if world is not None:
        start, _d = sculpt.to_local(world, local, start)
        end, _d = sculpt.to_local(world, local, end)
        if start is None or end is None:
            return False
    direction = [end[k] - start[k] for k in range(3)]
    return add_stroke(model, node, kind, start, radius, strength, direction)


class SculptPanel(QDialog):
    """Brush settings + the armed pick. Closing the panel ends the
    sculpt (the strokes stay on the node)."""

    def __init__(self, window, node):
        super().__init__(window)
        self.setWindowTitle(
            language.tr("Sculpt — {name}").format(name=node.name))
        self.setWindowFlag(Qt.Tool, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.window_, self.node = window, node
        self._world = self._local = None
        #: a crease / ridge is drawn with two clicks: where it starts
        #: (world point, kept while the end is aimed)
        self._line_start = None
        form = QFormLayout()
        self.kind = QComboBox()
        for name in sculpt.KINDS:
            self.kind.addItem(language.tr(name.capitalize()), name)
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
            self.mirror.addItem(
                language.tr("none") if name == "none" else name, name)
        self.mirror.setCurrentIndex(self.mirror.findData(
            str(node.params.get("mirror", "none"))))
        self.mirror.currentIndexChanged.connect(
            lambda _i: self._set_mirror(self.mirror.currentData()))
        form.addRow(language.tr("Brush"), self.kind)
        form.addRow(language.tr("Radius"), self.radius)
        form.addRow(language.tr("Strength"), self.strength)
        form.addRow(language.tr("Mirror"), self.mirror)
        self.count = QLabel()
        undo = QPushButton(language.tr("Undo last stroke"))
        undo.clicked.connect(self.undo_last)
        done = QPushButton(language.tr("Done"))
        done.clicked.connect(self.close)
        row = QHBoxLayout()
        row.addWidget(undo)
        row.addStretch(1)
        row.addWidget(done)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(QLabel(language.tr(
            "Click the surface in the 3D view to sculpt. Grab drags "
            "along the surface normal; a negative strength pushes "
            "in.")))
        lay.addWidget(self.count)
        lay.addLayout(row)
        self._refresh_count()
        self.arm()

    # -- the pick -------------------------------------------------------
    def _banner(self):
        n = len(self.node.params.get("strokes") or [])
        if self._line_start is not None:
            return language.tr(
                "Sculpt: {kind} — now click where it ends; Esc "
                "cancels").format(
                    kind=language.tr(self.kind.currentData().capitalize()))
        if self.kind.currentData() in sculpt.LINES:
            return language.tr(
                "Sculpt: {kind} line, {radius:g} mm wide · {count} "
                "stroke(s) · click where it starts").format(
                    kind=language.tr(self.kind.currentData().capitalize()),
                    radius=self.radius.value(), count=n)
        return language.tr(
            "Sculpt: {kind} brush, {radius:g} mm · {count} stroke(s) "
            "· click the surface; Esc or right-click when done").format(
                kind=language.tr(self.kind.currentData().capitalize()),
                radius=self.radius.value(), count=n)

    def arm(self):
        self._world, self._local = meshes(self.window_, self.node)
        if self._world is None:
            self.window_.statusBar().showMessage(language.tr(
                "{name}: nothing to sculpt yet — put a solid inside "
                "it first.").format(name=self.node.name), 6000)
            return
        self.window_.view3d.start_pick(
            self._on_pick, groups=[(self.node, self._world)],
            banner=self._banner(),
            labeler=lambda desc, _k: language.tr("{kind} here").format(
                kind=language.tr(self.kind.currentData().capitalize())))

    def _on_pick(self, desc, _key):
        if desc is None:                       # Esc / right-click
            self._line_start = None
            self.window_.view3d.set_pick_pinned(None)
            self.window_.statusBar().showMessage(language.tr(
                "Sculpting paused — click a brush in the panel to "
                "continue, or Done."), 5000)
            return
        if self.kind.currentData() in sculpt.LINES:
            point = desc.get("point")
            if self._line_start is None:       # first click: the start
                self._line_start = list(point)
                self.window_.view3d.set_pick_pinned(desc, language.tr(
                    "start"))
                self.arm()
                return
            start, self._line_start = self._line_start, None
            self.window_.view3d.set_pick_pinned(None)
            ok = add_line(self.window_.model, self.node,
                          self.kind.currentData(), start, point,
                          self.radius.value(), self.strength.value(),
                          world=self._world, local=self._local)
            if not ok:
                self.window_.statusBar().showMessage(language.tr(
                    "That line missed the sculpted surface."), 3000)
            self._refresh_count()
            self.arm()
            return
        ok = add_stroke(
            self.window_.model, self.node, self.kind.currentData(),
            desc.get("point"), self.radius.value(), self.strength.value(),
            desc.get("normal"), world=self._world, local=self._local)
        if not ok:
            self.window_.statusBar().showMessage(language.tr(
                "That click missed the sculpted surface."), 3000)
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
        self.count.setText(language.tr("{count} stroke(s)").format(
            count=len(self.node.params.get('strokes') or [])))

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

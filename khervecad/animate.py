"""View ▸ Animate…: OpenSCAD's ``$t`` animation.

A program reads ``$t`` — the time, 0 to 1 — to move its parts:
``rotate([0, 0, 360 * $t])`` turns a gear, ``translate([0, 0, 20 *
sin(360 * $t)])`` bobs a piston. OpenSCAD steps ``$t`` through a number
of frames; this does the same for KherveCAD's views: `set_time` puts the
value where every expression reads special variables
(`expr.SPECIAL_DEFAULTS`), where OpenSCAD renders get it (``-D $t=…``,
`engine.DEFINES`) and into the exact-mesh keys of parts that use it
(mesh._component_key), then the views redraw. The document is not
changed — the time is a way of looking at it, so saving, undo and the
exported program are unaffected.

The panel plays, pauses and scrubs; Export frames… writes one PNG per
step through the same offscreen snapshot as Export PNG. MCP:
``set_render_options time``.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import os

from . import expr


def current_time() -> float:
    return float(expr.SPECIAL_DEFAULTS.get("$t", 0) or 0)


def uses_time(root) -> bool:
    """True when anything in the tree reads $t."""
    for node in root.walk():
        for value in node.params.values():
            if isinstance(value, str) and "$t" in value:
                return True
    return False


def set_time(window, t: float):
    """Show the document at time *t* (wrapped into 0..1)."""
    from . import engine
    t = float(t)
    if t < 0 or t > 1:
        t = t % 1.0
    expr.SPECIAL_DEFAULTS["$t"] = t
    if t:
        engine.DEFINES["$t"] = f"{t:g}"
    else:
        engine.DEFINES.pop("$t", None)
    if window is not None:
        window.scene.rebuild()
        window._refresh_preview()
        window.view3d.update()
    return t


def export_frames(window, folder, steps, width=None, height=None):
    """One PNG per step (``frame-0000.png``…) of the current view, time
    0 to (steps - 1) / steps like OpenSCAD's animation. Returns the
    paths; the time is put back afterwards."""
    from . import pngexport
    os.makedirs(folder, exist_ok=True)
    before = current_time()
    paths = []
    try:
        for k in range(max(int(steps), 1)):
            set_time(window, k / max(int(steps), 1))
            path = os.path.join(folder, f"frame-{k:04d}.png")
            pngexport.export_request(window.view3d, path, view="current",
                                     width=width, height=height,
                                     window=window)
            paths.append(path)
    finally:
        set_time(window, before)
    return paths


def open_panel(window):
    panel = getattr(window, "_animate_panel", None)
    if panel is None:
        panel = window._animate_panel = AnimatePanel(window)
    panel.show()
    panel.raise_()
    return panel


def _panel_class():
    from PyQt5.QtCore import Qt, QTimer
    from PyQt5.QtWidgets import (QDialog, QFileDialog, QHBoxLayout, QLabel,
                                 QPushButton, QSlider, QSpinBox,
                                 QVBoxLayout)
    from . import icons

    class _AnimatePanel(QDialog):
        def __init__(self, window):
            super().__init__(window)
            self.window = window
            self.setWindowTitle("Animate ($t)")
            self.resize(420, 150)
            layout = QVBoxLayout(self)
            self.info = QLabel()
            self.info.setWordWrap(True)
            layout.addWidget(self.info)
            row = QHBoxLayout()
            self.play = QPushButton(icons.icon("mdi.play"), "Play")
            self.play.setCheckable(True)
            self.play.toggled.connect(self._toggle)
            row.addWidget(self.play)
            self.slider = QSlider(Qt.Horizontal)
            self.slider.valueChanged.connect(self._scrub)
            row.addWidget(self.slider, 1)
            self.label = QLabel("$t = 0")
            row.addWidget(self.label)
            layout.addLayout(row)
            row = QHBoxLayout()
            row.addWidget(QLabel("FPS"))
            self.fps = QSpinBox()
            self.fps.setRange(1, 60)
            self.fps.setValue(10)
            self.fps.valueChanged.connect(self._timing)
            row.addWidget(self.fps)
            row.addWidget(QLabel("Steps"))
            self.steps = QSpinBox()
            self.steps.setRange(2, 1000)
            self.steps.setValue(36)
            self.steps.valueChanged.connect(self._timing)
            row.addWidget(self.steps)
            row.addStretch()
            export = QPushButton(icons.icon("mdi.filmstrip"),
                                 "Export frames...")
            export.clicked.connect(self._export)
            row.addWidget(export)
            layout.addLayout(row)
            self.timer = QTimer(self)
            self.timer.timeout.connect(self._tick)
            self._timing()
            self._describe()

        def _describe(self):
            if uses_time(self.window.model.root):
                self.info.setText("The model reads $t: play or drag to "
                                  "move it through time (0 to 1).")
            else:
                self.info.setText("Nothing in this model reads $t yet — "
                                  "use it in an expression, e.g. a Rotate "
                                  "Z of 360 * $t.")

        def _timing(self):
            self.slider.setRange(0, self.steps.value() - 1)
            self.timer.setInterval(int(1000 / self.fps.value()))

        def _scrub(self, k):
            t = k / self.steps.value()
            self.label.setText(f"$t = {t:.3f}")
            set_time(self.window, t)

        def _tick(self):
            self.slider.setValue((self.slider.value() + 1)
                                 % self.steps.value())

        def _toggle(self, on):
            self.play.setText("Pause" if on else "Play")
            self.play.setIcon(icons.icon("mdi.pause" if on else "mdi.play"))
            (self.timer.start if on else self.timer.stop)()

        def _export(self):
            folder = QFileDialog.getExistingDirectory(
                self, "Folder for the frames")
            if folder:
                paths = export_frames(self.window, folder,
                                      self.steps.value())
                self.info.setText(f"Wrote {len(paths)} frames to {folder}")

        def showEvent(self, event):
            self._describe()
            super().showEvent(event)

        def closeEvent(self, event):
            self.play.setChecked(False)
            set_time(self.window, 0.0)
            self.slider.setValue(0)
            super().closeEvent(event)

    return _AnimatePanel


def AnimatePanel(window):                                    # noqa: N802
    return _panel_class()(window)

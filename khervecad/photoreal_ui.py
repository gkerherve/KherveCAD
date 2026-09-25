"""File ▸ Render Photo (Blender)… and the MCP body: photoreal.render off
the GUI thread, with the window's own camera and colours.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import threading
import time

from . import language, photoreal


def scene(window):
    """(colored rows, camera dict) of what the 3D view shows — the whole
    model, never a Cut Through copy."""
    view = window.view3d
    tris = list(view.model_mesh)
    colors = view.model_colors or [None] * len(tris)
    return list(zip(tris, colors)), dict(
        yaw=view.yaw, pitch=view.pitch, distance=view.distance,
        target=list(view.target))


def run_pumping(fn):
    """Run *fn* on a thread while the GUI keeps painting; its result or
    its exception."""
    from PyQt5.QtWidgets import QApplication
    box = {}

    def work():
        try:
            box["value"] = fn()
        except Exception as exc:                 # handed back below
            box["error"] = exc
    t = threading.Thread(target=work, daemon=True)
    t.start()
    app = QApplication.instance()
    while t.is_alive():
        if app is not None:
            app.processEvents()
        time.sleep(0.02)
    if "error" in box:
        raise box["error"]
    return box.get("value")


def render_window(window, out, view="current", size=(1600, 1200),
                  samples=96, engine="cycles", ground=True,
                  transparent=False, binary=None, timeout=None):
    """Render the window's scene to *out*; *view* is "current" (the
    user's camera exactly) or a preset name (framed)."""
    from . import engine as engine_mod
    colored, cam = scene(window)
    if view != "current":
        rotation = engine_mod.CAMERA_ROTATIONS.get(view)
        if rotation is None:
            raise ValueError("view must be 'current' or one of "
                             + ", ".join(engine_mod.CAMERA_ROTATIONS))
        yaw, pitch = engine_mod.view_angles(rotation)
        cam = dict(yaw=yaw, pitch=pitch, distance=None, target=None)
    return run_pumping(lambda: photoreal.render(
        colored, out, cam["yaw"], cam["pitch"], cam["distance"],
        cam["target"], size, samples, engine, ground, transparent,
        binary=binary, timeout=timeout or photoreal.DEFAULT_TIMEOUT))


def open_dialog(window):
    from PyQt5.QtWidgets import QFileDialog, QMessageBox
    title = language.tr("Render Photo")
    if photoreal.find_blender() is None:
        QMessageBox.information(
            window, title, language.tr(
                "Photo rendering uses Blender (free, blender.org) in "
                "the background. Install it, or set KHERVECAD_BLENDER "
                "to its executable, and try again."))
        return
    path, _f = QFileDialog.getSaveFileName(window, title,
                                           "render.png", "PNG (*.png)")
    if not path:
        return
    window.statusBar().showMessage(
        language.tr("Rendering with Blender (Cycles)…"))
    try:
        render_window(window, path)
    except Exception as exc:
        QMessageBox.warning(window, title, str(exc))
        return
    window.statusBar().showMessage(
        language.tr("Rendered {path}").format(path=path), 8000)
    from PyQt5.QtCore import QUrl
    from PyQt5.QtGui import QDesktopServices
    QDesktopServices.openUrl(QUrl.fromLocalFile(path))

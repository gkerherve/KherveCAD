"""Pictures of documents for the Welcome window's Recent cards — the 3D
view of the part, as SolidWorks shows in its Recent Documents.

Two sources, both kept as PNGs in the cache folder:

- `save_from_window`: when a document is saved, the picture of the 3D
  view the user is looking at (square on to the iso camera, the part
  framed, no grid or axes);
- `render_file`: for a .kcad with no picture yet (saved by an older
  version, or by another program), the file is loaded into a SCRATCH
  model, tessellated by the built-in preview and painted by an offscreen
  View3D — never touching the open document. A document too heavy to
  draw quickly (`MAX_BYTES`, `MAX_TRIS`) gets a marker so it is not
  tried again.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import hashlib
import os
from pathlib import Path

from PyQt5.QtCore import QStandardPaths
from PyQt5.QtGui import QImage

SIZE = (360, 270)
VIEW = "Isometric"
BACKGROUND = "Light"
MAX_BYTES = 6 * 1024 * 1024
MAX_TRIS = 120_000


def folder() -> str:
    base = QStandardPaths.writableLocation(QStandardPaths.CacheLocation) \
        or os.path.join(os.path.expanduser("~"), ".cache", "KherveCAD")
    return os.path.join(base, "welcome-thumbs")


def _key(doc_path) -> str:
    return hashlib.sha1(
        str(Path(doc_path).resolve()).encode()).hexdigest()[:20]


def path_of(doc_path) -> str:
    return os.path.join(folder(), _key(doc_path) + ".png")


def _marker(doc_path) -> str:
    return os.path.join(folder(), _key(doc_path) + ".none")


def _stamp(doc_path) -> float:
    try:
        return os.path.getmtime(doc_path)
    except OSError:
        return 0.0


def current(doc_path):
    """The kept picture of *doc_path* when it is as new as the file."""
    png = path_of(doc_path)
    if os.path.exists(png) and os.path.getmtime(png) >= _stamp(doc_path):
        return png
    return None


def refused(doc_path) -> bool:
    mark = _marker(doc_path)
    return os.path.exists(mark) and os.path.getmtime(mark) >= \
        _stamp(doc_path)


def _paint(view, size=SIZE):
    from .pngexport import camera
    yaw, pitch = camera(VIEW)
    view.wait_for_bsp()
    image, _cam = view.snapshot(size[0], size[1], yaw=yaw, pitch=pitch,
                                frame=True, clean=True)
    return image


def _keep(image, doc_path) -> bool:
    os.makedirs(folder(), exist_ok=True)
    ok = isinstance(image, QImage) and not image.isNull() and \
        image.save(path_of(doc_path), "PNG")
    if ok and os.path.exists(_marker(doc_path)):
        os.remove(_marker(doc_path))
    return bool(ok)


def save_from_window(win, doc_path, force=False) -> bool:
    """The picture of the window's own 3D view. Skipped on the offscreen
    platform (the tests) unless *force*. Never raises."""
    if not force and os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        return False
    try:
        if not getattr(win.view3d, "model_mesh", None):
            return False
        return _keep(_paint(win.view3d), doc_path)
    except Exception:
        return False


def render_file(doc_path) -> bool:
    """Make the picture of the .kcad at *doc_path* from the file alone.
    False (and a marker) when it cannot or should not be drawn."""
    from . import document, mesh
    from .model import DocumentModel
    from .view3d import View3D
    try:
        if not os.path.exists(doc_path) or \
                os.path.getsize(doc_path) > MAX_BYTES:
            raise ValueError("too big")
        model = DocumentModel()
        document.load_kcad(model, str(doc_path))
        colored = mesh.tessellate_colored(model.root,
                                          fn=model.effective_fn())
        if not colored or len(colored) > MAX_TRIS:
            raise ValueError("nothing to draw or too heavy")
        view = View3D()
        view.background = BACKGROUND
        view.stage = False
        view.resize(*SIZE)
        colors = [c for _t, c in colored]
        view.set_mesh([t for t, _c in colored], "thumbnail",
                      colors if any(c is not None for c in colors)
                      else None)
        image = _paint(view)
        view.deleteLater()
        if _keep(image, doc_path):
            return True
        raise ValueError("could not save")
    except Exception:
        try:
            os.makedirs(folder(), exist_ok=True)
            Path(_marker(doc_path)).write_text("")
        except OSError:
            pass
        return False

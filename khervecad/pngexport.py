"""File ▸ Export PNG: pictures of the 3D view.

Rendered by the built-in renderer through `View3D.snapshot`, so what
comes out is what the user has been looking at — colours, materials,
render style, background and lighting — only bigger, and with the
viewport furniture (grid, axes, badge, selection tint) left out.  The
user's own camera never moves: every picture comes from an offscreen
twin of the view.

Two kinds of export:

* **Current view** — exactly the camera on screen (same direction,
  distance, target and projection), at the size asked for.
* **All standard views** — one file per `STILL_VIEWS` entry, each
  framed on the whole model, front-right isometric first.  The same
  set, in the same order, as the preview stills of a Printables bundle
  (`printables._render_previews` falls back to `render` when OpenSCAD
  is missing), and the cameras come from the same table
  (`engine.CAMERA_ROTATIONS` via `engine.view_angles`), so the two can
  never disagree about which side is the front.

`export_request` is the `export_document` MCP tool's PNG branch.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import re
from pathlib import Path

from PyQt5.QtCore import QSettings, Qt
from PyQt5.QtWidgets import (QApplication, QButtonGroup, QCheckBox,
                             QComboBox, QDialog, QDialogButtonBox,
                             QFileDialog, QFormLayout, QGroupBox,
                             QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                             QPushButton, QRadioButton, QVBoxLayout)

from .engine import CAMERA_ROTATIONS, view_angles
from .mcp_schema import PNG_DEFAULT_SIZE, STILL_VIEWS

#: The view that leads: Printables makes the first image the cover, and
#: a numbered folder sorts it first everywhere else too.
COVER = "Isometric"

#: (key, label, (width, height)) — ``None`` is the window size × 2,
#: which keeps the on-screen framing exactly.
SIZES = (
    ("1280x720", "1280 × 720 (HD)", (1280, 720)),
    ("1920x1080", "1920 × 1080 (Full HD)", (1920, 1080)),
    ("2560x1440", "2560 × 1440 (QHD)", (2560, 1440)),
    ("3840x2160", "3840 × 2160 (4K)", (3840, 2160)),
    ("2048x2048", "2048 × 2048 (square)", (2048, 2048)),
    ("window2", "Window size × 2", None),
)
DEFAULT_SIZE_KEY = "1920x1080"

#: No side smaller or larger than this: a 16 px picture is useless and
#: a 20 000 px one is an out-of-memory crash, not an image.
MIN_SIDE, MAX_SIDE = 16, 8192

#: QSettings group holding the dialog's last choices.
SETTINGS_GROUP = "png_export"


# ── rendering ──────────────────────────────────────────────────────

def ordered_views(names) -> tuple:
    """(known views with the cover first, unknown names), duplicates
    dropped — the order the files are numbered in."""
    known, unknown = [], []
    for name in dict.fromkeys(names):
        (known if name in CAMERA_ROTATIONS else unknown).append(name)
    if COVER in known:
        known.insert(0, known.pop(known.index(COVER)))
    return known, unknown


def camera(name) -> tuple:
    """The 3D view's (yaw, pitch) for a standard view name."""
    return view_angles(CAMERA_ROTATIONS[name])


def file_name(stem, index, view) -> str:
    """``<stem>-<n>-<view>.png``: numbered so the cover sorts first."""
    tag = re.sub(r"[^a-z0-9]+", "-", str(view).lower()).strip("-")
    return f"{stem}-{index}-{tag}.png"


def render(view3d, width, height, view="current", transparent=False):
    """A QImage of the model. *view* is ``"current"`` (the camera on
    screen, untouched) or a standard view name (framed on the whole
    model from that side)."""
    if not view3d.mesh:
        raise ValueError("There is nothing in the 3D view to export.")
    if view == "current":
        image, _cam = view3d.snapshot(width, height, clean=True,
                                      transparent=transparent)
        return image
    if view not in CAMERA_ROTATIONS:
        raise ValueError(f"Unknown view {view!r}. Choose one of: "
                         f"current, {', '.join(STILL_VIEWS)}.")
    yaw, pitch = camera(view)
    image, _cam = view3d.snapshot(width, height, yaw=yaw, pitch=pitch,
                                  frame=True, clean=True,
                                  transparent=transparent)
    return image


def _save(image, path) -> Path:
    path = Path(str(path)).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(path), "PNG"):
        raise OSError(f"Could not write {path}.")
    return path


def window_size_x2(view3d) -> tuple:
    return (max(view3d.width() * 2, MIN_SIDE),
            max(view3d.height() * 2, MIN_SIDE))


def resolve_size(view3d, key) -> tuple:
    """Pixel size for a `SIZES` key; unknown keys get the default."""
    for k, _label, size in SIZES:
        if k == key:
            return size if size is not None else window_size_x2(view3d)
    return PNG_DEFAULT_SIZE


def export_current(view3d, path, size, transparent=False) -> Path:
    return _save(render(view3d, size[0], size[1], "current",
                        transparent), path)


def export_views(view3d, folder, stem, size, transparent=False,
                 views=STILL_VIEWS) -> list:
    """One PNG per view into *folder*, cover first. Returns the paths."""
    names, unknown = ordered_views(views)
    if unknown:
        raise ValueError(f"Unknown view(s) {', '.join(unknown)}.")
    folder = Path(str(folder)).expanduser()
    return [_save(render(view3d, size[0], size[1], name, transparent),
                  folder / file_name(stem, index, name))
            for index, name in enumerate(names, 1)]


def _side(value, default) -> int:
    if value is None:
        return int(default)
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise ValueError("'width' and 'height' are whole pixels.")
    if not MIN_SIDE <= value <= MAX_SIDE:
        raise ValueError(f"'width' and 'height' must be between "
                         f"{MIN_SIDE} and {MAX_SIDE} pixels.")
    return value


def export_request(view3d, path, *, view="current", width=None,
                   height=None, transparent=False) -> dict:
    """The export_document tool's PNG branch. Raises ValueError for a
    request the client should fix."""
    path = Path(str(path)).expanduser()
    if path.suffix.lower() != ".png":
        raise ValueError("A picture export path must end in .png.")
    if view not in ("current", "all", *STILL_VIEWS):
        raise ValueError(f"Unknown view {view!r}. Choose one of: "
                         f"current, all, {', '.join(STILL_VIEWS)}.")
    default = window_size_x2(view3d) if view == "current" \
        else PNG_DEFAULT_SIZE
    size = (_side(width, default[0]), _side(height, default[1]))
    result = {"format": "png", "width": size[0], "height": size[1],
              "transparent": bool(transparent)}
    if view == "all":
        paths = export_views(view3d, path.parent, path.stem, size,
                             transparent)
        result.update(exported=[str(p) for p in paths],
                      views=ordered_views(STILL_VIEWS)[0])
    else:
        image = render(view3d, size[0], size[1], view, transparent)
        result.update(exported=str(_save(image, path)), view=view)
    return result


# ── remembered choices ─────────────────────────────────────────────

def _settings(settings=None):
    return settings if settings is not None else \
        QSettings("Kherve", "KherveCAD")


def load_choices(settings=None) -> dict:
    """The dialog's last choices: what, size, transparent, dir."""
    s = _settings(settings)
    what = s.value(f"{SETTINGS_GROUP}/what", "current")
    size = s.value(f"{SETTINGS_GROUP}/size", DEFAULT_SIZE_KEY)
    return {
        "what": what if what in ("current", "all") else "current",
        "size": size if size in {k for k, _l, _s in SIZES}
        else DEFAULT_SIZE_KEY,
        "transparent": s.value(f"{SETTINGS_GROUP}/transparent", False,
                               type=bool),
        "dir": str(s.value(f"{SETTINGS_GROUP}/dir", "") or ""),
    }


def save_choices(choices, settings=None):
    s = _settings(settings)
    for key in ("what", "size", "transparent", "dir"):
        if key in choices:
            s.setValue(f"{SETTINGS_GROUP}/{key}", choices[key])
    s.sync()


# ── the dialog ─────────────────────────────────────────────────────

class PngExportDialog(QDialog):
    """File ▸ Export PNG… — what, how big, what behind it, and where."""

    def __init__(self, window, settings=None):
        super().__init__(window)
        self._w = window
        self._settings = settings
        self.setWindowTitle("Export PNG")
        self.setMinimumWidth(520)
        choices = load_choices(settings)
        doc = Path(window._path) if getattr(window, "_path", None) \
            else None
        self._stem = re.sub(r"[^\w.-]+", "-", doc.stem).strip("-") \
            if doc else "model"
        self._stem = self._stem or "model"
        base = choices["dir"] or (str(doc.parent) if doc else "")
        if not base or not Path(base).is_dir():
            pictures = Path.home() / "Pictures"
            base = str(pictures if pictures.is_dir() else Path.home())
        self._dir = base

        layout = QVBoxLayout(self)
        what_box = QGroupBox("What")
        what_col = QVBoxLayout(what_box)
        self.current_radio = QRadioButton(
            "Current view — exactly the camera on screen")
        self.all_radio = QRadioButton(
            "All standard views — one file per view (%d), framed on "
            "the model" % len(STILL_VIEWS))
        self._what = QButtonGroup(self)
        for button in (self.current_radio, self.all_radio):
            self._what.addButton(button)
            what_col.addWidget(button)
        (self.all_radio if choices["what"] == "all"
         else self.current_radio).setChecked(True)
        layout.addWidget(what_box)

        form = QFormLayout()
        self.size_combo = QComboBox()
        w2 = window_size_x2(window.view3d)
        for key, label, size in SIZES:
            if size is None:
                label += " (%d × %d)" % w2
            self.size_combo.addItem(label, key)
        self.size_combo.setCurrentIndex(
            max(self.size_combo.findData(choices["size"]), 0))
        form.addRow("Size", self.size_combo)
        self.transparent_box = QCheckBox("Transparent background")
        self.transparent_box.setChecked(choices["transparent"])
        form.addRow("Background", self.transparent_box)
        layout.addLayout(form)

        path_row = QHBoxLayout()
        self.path_label = QLabel()
        self.path_edit = QLineEdit()
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        path_row.addWidget(self.path_label)
        path_row.addWidget(self.path_edit, 1)
        path_row.addWidget(browse)
        layout.addLayout(path_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        go = buttons.addButton("Export", QDialogButtonBox.AcceptRole)
        go.clicked.connect(self._export_clicked)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._what.buttonToggled.connect(lambda *_: self._sync_path())
        self._sync_path()

    # ------------------------------------------------------------ bits
    def is_all(self) -> bool:
        return self.all_radio.isChecked()

    def _sync_path(self):
        """File for one picture, folder for all of them."""
        if self.is_all():
            self.path_label.setText("Folder")
            self.path_edit.setText(str(Path(self._dir) /
                                       f"{self._stem}-views"))
        else:
            self.path_label.setText("File")
            self.path_edit.setText(str(Path(self._dir) /
                                       f"{self._stem}.png"))

    def _browse(self):
        if self.is_all():
            path = QFileDialog.getExistingDirectory(
                self, "Folder for the pictures", self.path_edit.text())
        else:
            path, _ = QFileDialog.getSaveFileName(
                self, "Export PNG", self.path_edit.text(),
                "PNG image (*.png)")
        if path:
            self.path_edit.setText(path)

    def choices(self) -> dict:
        # the file's folder, or the folder the views folder sits in:
        # either way, where the next export starts
        path = Path(self.path_edit.text()).expanduser()
        return {"what": "all" if self.is_all() else "current",
                "size": self.size_combo.currentData(),
                "transparent": self.transparent_box.isChecked(),
                "dir": str(path.parent)}

    # ----------------------------------------------------------- export
    def export(self) -> list:
        """Write the picture(s) and remember the choices. Returns the
        paths written; raises ValueError/OSError on failure."""
        choices = self.choices()
        view3d = self._w.view3d
        size = resolve_size(view3d, choices["size"])
        text = self.path_edit.text().strip()
        if not text:
            raise ValueError("Choose where to save.")
        path = Path(text).expanduser()
        if self.is_all():
            paths = export_views(view3d, path, self._stem, size,
                                 choices["transparent"])
        else:
            if path.suffix.lower() != ".png":
                path = path.with_suffix(".png")
            paths = [export_current(view3d, path, size,
                                    choices["transparent"])]
        save_choices(choices, self._settings)
        return paths

    def _export_clicked(self):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            paths = self.export()
        except (ValueError, OSError) as exc:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Export PNG", str(exc))
            return
        QApplication.restoreOverrideCursor()
        where = paths[0] if len(paths) == 1 else paths[0].parent
        status = getattr(self._w, "statusBar", None)
        if callable(status):
            status().showMessage(
                "Exported %d PNG%s to %s" % (
                    len(paths), "" if len(paths) == 1 else "s", where),
                8000)
        self.accept()


def open_dialog(window):
    """File ▸ Export PNG…"""
    PngExportDialog(window).exec_()

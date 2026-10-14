"""File ▸ Import / Export Animated Character and the Pose Character panel
(Qt side of character.py).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import QSettings, Qt
from PyQt5.QtWidgets import (QApplication, QComboBox, QDialog,
                             QDialogButtonBox, QFileDialog, QFormLayout,
                             QLabel, QMessageBox, QSlider)

from . import character, language

TITLE_IMPORT = "Import animated character"
TITLE_EXPORT = "Export animated character"


def _settings():
    return QSettings("Kherve", "KherveCAD")


def _tree(window):
    builder = getattr(window, "builder", None)
    return builder.active_tree() if builder is not None else None


def characters(window):
    """The imported characters in the document (their Objects)."""
    return [n for n in window.model.root.walk() if n.type == "component"
            and isinstance(n.params.get(character.INFO_KEY), dict)]


def current_character(window):
    """The selected character (or the one holding the selection), else
    the only character in the document, else None."""
    tree = _tree(window)
    for node in (tree.selected_nodes() if tree is not None else []):
        found = character.info_of(node)
        if found is not None:
            return found[0]
    found = characters(window)
    return found[0] if len(found) == 1 else None


def _select(window, node):
    tree = _tree(window)
    if tree is not None and hasattr(tree, "select_nodes"):
        tree.select_nodes([node])


def _show_in_folder(path):
    from PyQt5.QtCore import QUrl
    from PyQt5.QtGui import QDesktopServices
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).parent)))


# ------------------------------------------------------------ import

def import_character_dialog(window):
    tr = language.tr
    start = str(_settings().value("character/last_dir", ""))
    path, _f = QFileDialog.getOpenFileName(
        window, tr(TITLE_IMPORT), start,
        tr("Animated character (*.glb)"))
    if not path:
        return None
    _settings().setValue("character/last_dir", str(Path(path).parent))
    QApplication.setOverrideCursor(Qt.WaitCursor)
    try:
        comp = character.import_character(window.model, path)
        clips = character.pose(window.model, comp)["clips"]
    except (character.CharacterError, OSError, ValueError) as exc:
        QApplication.restoreOverrideCursor()
        QMessageBox.warning(window, tr(TITLE_IMPORT), tr(str(exc)))
        return None
    QApplication.restoreOverrideCursor()
    _select(window, comp)
    info = comp.params[character.INFO_KEY]
    QMessageBox.information(
        window, tr(TITLE_IMPORT),
        tr("{name}: {h:.0f} mm tall, {b} bones, {c} animation clips.")
        .format(name=comp.name, h=info["height_mm"], b=len(info["bones"]),
                c=len(clips))
        + "\n\n" + tr("Add parts inside it, attach them to bones (or "
                      "leave them: they go to the nearest bone), check a "
                      "clip with File ▸ Pose Character, then File ▸ "
                      "Export Animated Character."))
    return comp


# ------------------------------------------------------------ export

def _need_character(window, title):
    comp = current_character(window)
    if comp is None:
        QMessageBox.information(
            window, language.tr(title),
            language.tr("Select the character to use (or a part inside "
                        "it). Bring one in with File ▸ Import Animated "
                        "Character.") if characters(window) else
            language.tr("There is no animated character in this "
                        "document: File ▸ Import Animated Character "
                        "first."))
    return comp


def export_character_dialog(window):
    tr = language.tr
    comp = _need_character(window, TITLE_EXPORT)
    if comp is None:
        return None
    start = Path(str(_settings().value("character/export_dir", "")
                     or Path.home())) / (comp.name + ".glb")
    path, _f = QFileDialog.getSaveFileName(
        window, tr(TITLE_EXPORT), str(start),
        tr("Animated character (*.glb)"))
    if not path:
        return None
    if not path.lower().endswith(".glb"):
        path += ".glb"
    _settings().setValue("character/export_dir", str(Path(path).parent))
    QApplication.setOverrideCursor(Qt.WaitCursor)
    try:
        out = character.export_glb(window.model, comp, path)
    except (character.CharacterError, OSError, ValueError) as exc:
        QApplication.restoreOverrideCursor()
        QMessageBox.warning(window, tr(TITLE_EXPORT), tr(str(exc)))
        return None
    QApplication.restoreOverrideCursor()
    box = QMessageBox(window)
    box.setWindowTitle(tr(TITLE_EXPORT))
    box.setIcon(QMessageBox.Information)
    box.setText(tr("{p} parts on {b} bones, {c} clips, {kb} KB.").format(
        p=out["parts"], b=len(out["bones_used"]), c=len(out["clips"]),
        kb=out["kb"]))
    box.setInformativeText(out["path"])
    show = box.addButton(tr("Show in Folder"), QMessageBox.ActionRole)
    box.addButton(QMessageBox.Ok)
    box.exec_()
    if box.clickedButton() is show:
        _show_in_folder(out["path"])
    return out


# ------------------------------------------------------------ pose

class PoseDialog(QDialog):
    """A clip and a time: the character takes the pose as you move."""

    STEPS = 200

    def __init__(self, window, comp):
        super().__init__(window)
        tr = language.tr
        self.window_, self.comp = window, comp
        self.setWindowTitle(tr("Pose character — {n}").format(n=comp.name))
        info = comp.params[character.INFO_KEY]
        self.clips = character.Glb(info["source"]).clips()
        form = QFormLayout(self)
        self.clip = QComboBox()
        self.clip.addItem(tr("Rest pose"), None)
        for name, seconds in self.clips:
            self.clip.addItem(f"{name}  ({seconds:.2f} s)", name)
        if info.get("clip"):
            self.clip.setCurrentIndex(max(0, self.clip.findData(
                info["clip"])))
        self.time = QSlider(Qt.Horizontal)
        self.time.setRange(0, self.STEPS)
        self.label = QLabel()
        form.addRow(tr("Clip"), self.clip)
        form.addRow(tr("Time"), self.time)
        form.addRow("", self.label)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        dur = self._duration()
        if dur > 0:
            self.time.setValue(int(round(float(info.get("time", 0.0)) / dur
                                         * self.STEPS)))
        self.clip.currentIndexChanged.connect(self._apply)
        self.time.valueChanged.connect(self._apply)
        self._apply()

    def _duration(self):
        name = self.clip.currentData()
        return next((d for n, d in self.clips if n == name), 0.0)

    def _apply(self, *_):
        name = self.clip.currentData()
        self.time.setEnabled(name is not None)
        t = self._duration() * self.time.value() / self.STEPS
        self.label.setText(language.tr("{t:.2f} s").format(t=t)
                           if name else "")
        try:
            character.pose(self.window_.model, self.comp, name, t)
        except character.CharacterError as exc:
            self.label.setText(str(exc))


def pose_character_dialog(window):
    comp = _need_character(window, "Pose character")
    if comp is None:
        return None
    dlg = PoseDialog(window, comp)
    dlg.show()
    window._pose_dialog = dlg          # keep it alive while open
    return dlg

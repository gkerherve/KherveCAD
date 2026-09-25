"""Library ▸ OpenSCAD Libraries…: the community libraries of the OpenSCAD
manual and openscad.org — which are installed, installing one (a
download from its GitHub project, only on the user's click), opening
the library folder, and inserting the ``include <...>`` line a program
starts with. The MCP tools list_scad_libraries / install_scad_library
share `run_install`.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import os
import threading
import time

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (QApplication, QDialog, QHBoxLayout, QLabel,
                             QListWidget, QListWidgetItem, QPushButton,
                             QVBoxLayout)

from . import icons, language, scadlib


def run_install(lib, progress=None) -> str:
    """Install *lib* on a worker thread while the GUI keeps painting.
    Returns the folder; raises what the download raised."""
    result = {}

    def work():
        try:
            result["folder"] = scadlib.install(lib)
        except Exception as exc:              # reported to the caller
            result["error"] = exc
    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    app = QApplication.instance()
    while thread.is_alive():
        if app is not None:
            app.processEvents()
        time.sleep(0.03)
    if "error" in result:
        raise result["error"]
    if progress:
        progress(language.tr("Installed in {folder}").format(
            folder=result['folder']))
    return result["folder"]


def describe() -> dict:
    """Every known library and where OpenSCAD looks — the MCP listing."""
    return {
        "library_folder": scadlib.user_library_dir(),
        "search_folders": scadlib.search_dirs(),
        "libraries": [
            {"key": lib.key, "title": lib.title, "about": lib.blurb,
             "include": lib.include, "licence": lib.licence,
             "project": f"https://github.com/{lib.repo}",
             "installed": scadlib.installed(lib)
             or scadlib.resolve(lib.key) is not None
             or any(os.path.isdir(os.path.join(d, lib.key))
                    for d in scadlib.search_dirs())}
            for lib in scadlib.KNOWN],
    }


class LibrariesDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle(language.tr("OpenSCAD Libraries"))
        self.resize(620, 460)
        layout = QVBoxLayout(self)
        intro = QLabel(language.tr(
            "Community libraries for OpenSCAD. Once installed, a "
            "program that includes one opens here: calls that import "
            "cleanly become objects, the rest stay as OpenSCAD code "
            "rendered by the engine. Installing downloads the project "
            "from GitHub into your OpenSCAD library folder, shared "
            "with OpenSCAD."))
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self._update)
        layout.addWidget(self.list, 1)
        self.detail = QLabel()
        self.detail.setWordWrap(True)
        self.detail.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.detail)
        buttons = QHBoxLayout()
        self.install_btn = QPushButton(icons.icon("mdi.download"),
                                       language.tr("Install"))
        self.install_btn.clicked.connect(self._install)
        self.insert_btn = QPushButton(icons.icon("mdi.bookshelf"),
                                      language.tr("Insert include line"))
        self.insert_btn.clicked.connect(self._insert)
        folder = QPushButton(icons.icon("mdi.folder-open-outline"),
                             language.tr("Open library folder"))
        folder.clicked.connect(self._open_folder)
        close = QPushButton(language.tr("Close"))
        close.clicked.connect(self.close)
        for b in (self.install_btn, self.insert_btn, folder):
            buttons.addWidget(b)
        buttons.addStretch()
        buttons.addWidget(close)
        layout.addLayout(buttons)
        self.status = QLabel()
        layout.addWidget(self.status)
        self._fill()

    def _fill(self):
        row = max(self.list.currentRow(), 0)
        self.list.clear()
        for entry in describe()["libraries"]:
            mark = "✓ " if entry["installed"] else "   "
            item = QListWidgetItem(f"{mark}{entry['title']}")
            item.setData(Qt.UserRole, entry)
            self.list.addItem(item)
        self.list.setCurrentRow(row)

    def _entry(self):
        item = self.list.currentItem()
        return item.data(Qt.UserRole) if item is not None else None

    def _update(self, _row=None):
        entry = self._entry()
        if entry is None:
            return
        self.detail.setText(language.tr(
            "<b>{title}</b> — {about}<br>Program line: "
            "<code>{include}</code><br>Licence: {licence} · "
            "{project}").format(
                title=entry['title'], about=entry['about'],
                include=entry['include'], licence=entry['licence'],
                project=entry['project']))
        self.install_btn.setText(
            language.tr("Reinstall") if entry["installed"]
            else language.tr("Install"))

    def _install(self):
        entry = self._entry()
        if entry is None:
            return
        lib = next(lib for lib in scadlib.KNOWN if lib.key == entry["key"])
        self.install_btn.setEnabled(False)
        self.status.setText(
            language.tr("Downloading {title}…").format(title=lib.title))
        try:
            folder = run_install(lib)
        except Exception as exc:
            self.status.setText(language.tr(
                "Could not install {title}: {error}").format(
                    title=lib.title, error=exc))
        else:
            self.status.setText(language.tr(
                "Installed {title} in {folder}").format(
                    title=lib.title, folder=folder))
        finally:
            self.install_btn.setEnabled(True)
        self._fill()

    def _insert(self):
        entry = self._entry()
        if entry is None:
            return
        import re
        match = re.match(r"(use|include)\s*<([^>]*)>", entry["include"])
        if match is None or "..." in match.group(2):
            self.status.setText(language.tr(
                "This library has no single file to include — write "
                "the use line for the file you need in the Code "
                "tab."))
            return
        model = self.window.model
        node = model.add_node("scad_use", dict(kind=match.group(1),
                                               path=match.group(2)))
        node.parent.remove(node)
        model.root.add(node, 0)                   # a program starts with it
        model.structure_changed.emit()
        self.status.setText(language.tr(
            "Added {include} to the document.").format(
                include=entry['include']))

    def _open_folder(self):
        folder = scadlib.user_library_dir()
        os.makedirs(folder, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))


def open_dialog(window):
    dialog = getattr(window, "_scadlib_dialog", None)
    if dialog is None:
        dialog = window._scadlib_dialog = LibrariesDialog(window)
    dialog._fill()
    dialog.show()
    dialog.raise_()
    return dialog

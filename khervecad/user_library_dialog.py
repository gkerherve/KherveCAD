"""The Qt side of **My Library** (`user_library`): the Library ▸ My
Library submenu (filled each time it opens, so a part saved a moment ago
— by the user or an assistant over MCP — is there without a restart),
and the Save to My Library dialog (title, section, description, tags).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (QComboBox, QDialog, QDialogButtonBox,
                             QFormLayout, QLineEdit, QMessageBox,
                             QPlainTextEdit)

from . import icons, user_library


def add_menu(window, menu):
    """Library ▸ My Library, rebuilt on every opening."""
    sub = menu.addMenu(icons.icon("mdi.bookshelf"), "My Library")

    def fill():
        from . import library
        sub.clear()
        sub.addAction(icons.icon("mdi.content-save-outline"),
                      "Save Selection to My Library...",
                      lambda: save_selection(window))
        sub.addAction(icons.icon("mdi.folder-open-outline"),
                      "Open My Library Folder",
                      lambda: open_folder())
        mine = user_library.refresh(library.PARTS)
        if not mine:
            empty = sub.addAction("(nothing saved yet)")
            empty.setEnabled(False)
            return
        sub.addSeparator()
        by_section = {}
        for pid, spec in mine.items():
            by_section.setdefault(spec["category"], []).append(pid)
        for cat in sorted(by_section):
            target = sub if len(by_section) == 1 else sub.addMenu(
                cat.split(": ", 1)[-1])
            for pid in sorted(by_section[cat],
                              key=lambda p: mine[p]["label"].lower()):
                act = target.addAction(
                    mine[pid]["label"].replace("&", "&&"),
                    lambda _=False, p=pid: window._insert_library_part(p))
                if mine[pid].get("description"):
                    act.setToolTip(mine[pid]["description"])
        sub.setToolTipsVisible(True)
    sub.aboutToShow.connect(fill)
    fill()
    return sub


def open_folder():
    root = user_library.folder()
    root.mkdir(parents=True, exist_ok=True)
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(root)))


def sections():
    root = user_library.folder()
    names = [user_library.DEFAULT_SECTION]
    if root.is_dir():
        names += sorted(p.name for p in root.iterdir() if p.is_dir()
                        and not p.name.startswith((".", "_")))
    return names


class SaveDialog(QDialog):
    def __init__(self, parent, title=""):
        super().__init__(parent)
        self.setWindowTitle("Save to My Library")
        form = QFormLayout(self)
        self.title = QLineEdit(title)
        self.title.setPlaceholderText("What it is, with its key size — "
                                      "e.g. Shelf bracket, 150 mm, 2 screws")
        self.section = QComboBox()
        self.section.setEditable(True)
        self.section.addItems(sections())
        self.description = QPlainTextEdit()
        self.description.setPlaceholderText(
            "What it is for, its overall size, its parameters and what "
            "they change, how it is built. This is what a search — yours "
            "or the assistant's — reads.")
        self.tags = QLineEdit()
        self.tags.setPlaceholderText("Search words, comma separated")
        form.addRow("Title", self.title)
        form.addRow("Section", self.section)
        form.addRow("Description", self.description)
        form.addRow("Tags", self.tags)
        buttons = QDialogButtonBox(QDialogButtonBox.Save
                                   | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self.resize(560, 380)

    def values(self):
        return dict(title=self.title.text().strip(),
                    section=self.section.currentText().strip(),
                    description=self.description.toPlainText().strip(),
                    tags=[t.strip() for t in self.tags.text().split(",")
                          if t.strip()])


def save_selection(window, node=None):
    """Ask for the title and description, then save the selected part."""
    from . import library
    if node is None:
        tree = window.builder.active_tree()
        picked = tree.selected_nodes() if hasattr(tree, "selected_nodes") \
            else []
        node = picked[0] if picked else None
    if node is None:
        QMessageBox.information(window, "My Library",
                                "Select the Object to save first.")
        return None
    dlg = SaveDialog(window, node.name)
    while dlg.exec_():
        v = dlg.values()
        if not v["title"]:
            QMessageBox.warning(dlg, "My Library", "Give it a title.")
            continue
        model = window.model
        try:
            saved = user_library.save(node, v["title"], v["description"],
                                      v["section"], v["tags"],
                                      root=model.root, unit=model.unit,
                                      source="user",
                                      global_fn=model.global_fn)
        except (ValueError, OSError) as exc:
            QMessageBox.warning(window, "My Library", str(exc))
            return None
        user_library.refresh(library.PARTS)
        window.statusBar().showMessage(
            f"Saved to My Library: {saved['path']}", 8000)
        return saved
    return None

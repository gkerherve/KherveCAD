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
        sub.addAction(icons.icon("mdi.folder-cog-outline"),
                      "Manage My Library...",
                      lambda: ManageDialog(window).exec_())
        sub.addAction(icons.icon("mdi.folder-open-outline"),
                      "Open My Library Folder",
                      lambda: open_folder())
        auto = sub.addAction("Save New Objects Automatically")
        auto.setCheckable(True)
        auto.setChecked(autosave_enabled())
        auto.toggled.connect(lambda on: QSettings(
            "Kherve", "KherveCAD").setValue(AUTOSAVE_KEY, bool(on)))
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
    if not hasattr(window, "library_autosaver") and hasattr(window,
                                                           "model"):
        window.library_autosaver = AutoSaver(window)
    return sub


def open_folder():
    root = user_library.folder()
    root.mkdir(parents=True, exist_ok=True)
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(root)))


def sections():
    root = user_library.folder()
    names = user_library.existing_sections()
    return names + [a for a in user_library.AREAS if a not in names] + [
        user_library.DEFAULT_SECTION]


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
        self.section.setCurrentText(user_library.choose_section(
            "", title))
        self.section.setToolTip("The area of work — its folder. Type a "
                                "new name to make a new folder.")
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
        if node.type == "component":
            user_library.unignore(saved["uid"])
            user_library.remember(node, saved, v["description"], v["tags"],
                                  source="user")
        user_library.refresh(library.PARTS)
        window.statusBar().showMessage(
            f"Saved to My Library: {saved['path']}", 8000)
        return saved
    return None


# ------------------------------------------------------------ autosave
from PyQt5.QtCore import QFile, QObject, QSettings, QTimer  # noqa: E402

AUTOSAVE_KEY = "user_library/autosave"
AUTOSAVE_DELAY_MS = 4000


def autosave_enabled() -> bool:
    return QSettings("Kherve", "KherveCAD").value(AUTOSAVE_KEY, True,
                                                  type=bool)


class AutoSaver(QObject):
    """Saves every Object the user or an assistant designs to My Library
    a few seconds after it last changed. Objects already in a document
    when it was opened are the baseline and are only saved once edited;
    Library parts and builder output (houses, cities) are left out."""

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.model = window.model
        self._root = None
        self._seen = {}
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.flush)
        self.model.structure_changed.connect(self._changed)
        self.model.node_changed.connect(self._changed)
        self._rebaseline()

    def _objects(self):
        out, stack = [], list(self.model.root.children)
        while stack:
            n = stack.pop()
            if n.type == "component":
                out.append(n)
            elif n.type in ("union", "variables", "color", "translate"):
                stack.extend(n.children)
        return out

    def _built(self):
        names = set()
        for attr in ("house", "city"):
            spec = getattr(self.model, attr, None)
            if isinstance(spec, dict):
                names.update(spec.get("objects") or [])
        return names

    @staticmethod
    def _print(node):
        import json
        from .document import node_to_dict
        data = node_to_dict(node)
        data["params"] = {k: v for k, v in data["params"].items()
                          if k != "library"}
        return json.dumps(data, sort_keys=True, default=str)

    def _rebaseline(self):
        """The model's tree was replaced. A document just OPENED from a
        file is the baseline: its Objects are not new designs until they
        change. Anything else — a new document, which an assistant may
        fill in the same breath before this ever runs, or an undo — starts
        from nothing, so every Object in it is saved."""
        self._root = self.model.root
        opened = bool(getattr(self.window, "_path", None)) and not \
            getattr(self.window, "_dirty", True)
        self._seen = ({id(n): self._print(n) for n in self._objects()}
                      if opened else {})

    def _changed(self, *_args):
        if self.model.root is not self._root:
            self._rebaseline()
        if autosave_enabled():
            self._timer.start(AUTOSAVE_DELAY_MS)

    def flush(self):
        """Save every eligible Object that changed since it was last seen;
        returns what was saved."""
        from . import library, user_library
        if self.model.root is not self._root:
            self._rebaseline()
            return []
        saved, built = [], self._built()
        for node in self._objects():
            fp = self._print(node)
            if self._seen.get(id(node)) == fp or node.name in built:
                continue
            self._seen[id(node)] = fp
            try:
                result = user_library.autosave(
                    node, root=self.model.root, unit=self.model.unit,
                    global_fn=self.model.global_fn)
            except (OSError, ValueError):
                continue
            if result:
                saved.append(result)
        if saved:
            user_library.refresh(library.PARTS)
            try:
                self.window.statusBar().showMessage(
                    "Saved to My Library: " + ", ".join(
                        s["title"] for s in saved), 6000)
            except Exception:
                pass
        return saved


def trash(path) -> bool:
    """Move to the system trash when Qt can (5.15+)."""
    fn = getattr(QFile, "moveToTrash", None)
    return bool(fn and fn(path))


# ------------------------------------------------------------ managing
from PyQt5.QtCore import Qt  # noqa: E402
from PyQt5.QtWidgets import (QFileDialog, QHBoxLayout, QInputDialog,  # noqa
                             QLabel, QPushButton, QTreeWidget,
                             QTreeWidgetItem, QVBoxLayout, QWidget)

ROLE_PATH = Qt.UserRole
ROLE_KIND = Qt.UserRole + 1


class ManageDialog(QDialog):
    """Library ▸ My Library ▸ Manage: the folder as sections and parts —
    add a section or import files, rename or delete sections, delete a
    part or move it to another section, edit its title, description
    and tags. Deleted items go to the trash."""

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle("Manage My Library")
        self.resize(900, 560)
        layout = QHBoxLayout(self)
        left = QVBoxLayout()
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Section / part"])
        self.tree.itemSelectionChanged.connect(self._picked)
        left.addWidget(self.tree)
        row = QHBoxLayout()
        for text, slot in (("New section...", self._new_section),
                           ("Import files...", self._import),
                           ("Rename...", self._rename),
                           ("Delete", self._delete),
                           ("Open folder", open_folder)):
            b = QPushButton(text)
            b.clicked.connect(slot)
            row.addWidget(b)
        left.addLayout(row)
        layout.addLayout(left, 3)
        panel = QWidget()
        form = QFormLayout(panel)
        self.title = QLineEdit()
        self.section = QComboBox()
        self.section.setEditable(True)
        self.description = QPlainTextEdit()
        self.tags = QLineEdit()
        self.path = QLabel()
        self.path.setWordWrap(True)
        self.path.setTextInteractionFlags(Qt.TextSelectableByMouse)
        save = QPushButton("Save changes")
        save.clicked.connect(self._save_changes)
        form.addRow("Title", self.title)
        form.addRow("Section", self.section)
        form.addRow("Description", self.description)
        form.addRow("Tags", self.tags)
        form.addRow("File", self.path)
        form.addRow(save)
        layout.addWidget(panel, 4)
        self.reload()

    def reload(self, select=None):
        self.tree.clear()
        root = user_library.folder()
        sections = {}
        general = QTreeWidgetItem([user_library.DEFAULT_SECTION])
        general.setData(0, ROLE_PATH, str(root))
        general.setData(0, ROLE_KIND, "root")
        self.tree.addTopLevelItem(general)
        for name in user_library.existing_sections():
            item = QTreeWidgetItem([name])
            item.setData(0, ROLE_PATH, str(root / name))
            item.setData(0, ROLE_KIND, "section")
            self.tree.addTopLevelItem(item)
            sections[name] = item
        for path in user_library.files():
            info = user_library.read_info(path)
            parent = sections.get(info.get("section"), general)
            child = QTreeWidgetItem([info.get("title", path.stem)])
            child.setToolTip(0, info.get("description", ""))
            child.setData(0, ROLE_PATH, str(path))
            child.setData(0, ROLE_KIND, "part")
            parent.addChild(child)
            if select and str(path) == str(select):
                self.tree.setCurrentItem(child)
        self.tree.expandAll()
        self.section.clear()
        self.section.addItems(sections_list())

    def _current(self):
        item = self.tree.currentItem()
        if item is None:
            return None, None
        return item.data(0, ROLE_KIND), item.data(0, ROLE_PATH)

    def _picked(self):
        kind, path = self._current()
        part = kind == "part"
        for w in (self.title, self.section, self.description, self.tags):
            w.setEnabled(part)
        if not part:
            self.title.clear()
            self.description.clear()
            self.tags.clear()
            self.path.setText(path or "")
            return
        info = user_library.read_info(path)
        self.title.setText(info.get("title", ""))
        self.section.setCurrentText(info.get("section", ""))
        self.description.setPlainText(info.get("description", ""))
        self.tags.setText(", ".join(info.get("tags", [])))
        self.path.setText(path)

    def _done(self, select=None):
        from . import library
        user_library.refresh(library.PARTS)
        self.reload(select)

    def _warn(self, exc):
        QMessageBox.warning(self, "My Library", str(exc))

    def _save_changes(self):
        kind, path = self._current()
        if kind != "part":
            return
        try:
            new = user_library.update_info(
                path, self.title.text(), self.description.toPlainText(),
                [t for t in self.tags.text().split(",")])
            section = self.section.currentText().strip()
            if section and section != user_library.read_info(new).get(
                    "section"):
                new = user_library.move(new, user_library.choose_section(
                    section))
        except (OSError, ValueError) as exc:
            self._warn(exc)
            return
        self._done(new)

    def _new_section(self):
        name, ok = QInputDialog.getText(self, "New section",
                                        "Name of the area:")
        if ok and name.strip():
            try:
                user_library.add_section(name)
            except (OSError, ValueError) as exc:
                self._warn(exc)
            self._done()

    def _import(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add to My Library", "", "KherveCAD (*.kcad)")
        kind, path = self._current()
        section = ""
        if kind == "section":
            section = self.tree.currentItem().text(0)
        for src in paths:
            try:
                user_library.import_file(src, section)
            except (OSError, ValueError) as exc:
                self._warn(exc)
        self._done()

    def _rename(self):
        kind, path = self._current()
        if kind == "section":
            old = self.tree.currentItem().text(0)
            new, ok = QInputDialog.getText(self, "Rename section",
                                           "New name:", text=old)
            if ok and new.strip() and new != old:
                try:
                    user_library.rename_section(old, new)
                except (OSError, ValueError) as exc:
                    self._warn(exc)
                self._done()
        elif kind == "part":
            self.title.setFocus()
            self.title.selectAll()

    def _delete(self):
        kind, path = self._current()
        if kind not in ("part", "section"):
            return
        what = ("the section and every part in it" if kind == "section"
                else "this part")
        name = self.tree.currentItem().text(0)
        if QMessageBox.question(
                self, "My Library",
                f"Move {what} ({name}) to the trash?\nAutosave will not "
                "bring it back.") != QMessageBox.Yes:
            return
        try:
            user_library.remove(path, trash=trash)
        except (OSError, ValueError) as exc:
            self._warn(exc)
        self._done()


def sections_list():
    return sections()


def design_saved(window, path):
    """After the document was saved to *path*: keep the whole design in
    My Library too (when autosave is on). Never lets a library problem
    spoil the save itself."""
    if not autosave_enabled():
        return None
    from . import library
    try:
        saved = user_library.save_design(window.model, path)
    except Exception:
        return None
    if saved:
        user_library.refresh(library.PARTS)
    return saved

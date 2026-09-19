"""The **Collections** tab — Blender's outliner collections.

Each collection is a row with an eye (show / hide in the views; Ctrl+
click shows it alone) and a padlock (lock against picking and dragging
in the 2D view); its parts are listed under it, and the parts in no
collection under a last "Not in a collection" row. Dragging parts onto
a collection moves them there — from this tab or from the Main tree —
and so does Main's right-click ▸ Move to Collection. Selecting a part
here selects it in Main. The rules themselves live in
`part_collections` (Qt-free); this is only the view.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView,
                             QInputDialog, QLabel, QMenu, QMessageBox,
                             QToolButton, QTreeWidget, QTreeWidgetItem,
                             QVBoxLayout, QWidget)

from . import icons
from . import part_collections as pc
from .model import NODE_TYPES

#: item data: ("collection", name) | ("part", node id) | ("loose", None)
ROLE = Qt.UserRole
NAME, EYE, LOCK = 0, 1, 2
LOOSE = "Not in a collection"
#: top-level node types that are not parts
NOT_PARTS = ("variables", "assign", "masters", "scad_use")


def loose_parts(model) -> list:
    """Top-level parts shown in Main that are in no collection."""
    return [c for c in model.root.children
            if c.type not in NOT_PARTS
            and not (c.type == "component" and not c.visible)
            and not pc.of(c)]


def _mark(item, column, icon_name, text):
    """An icon in *column*, or *text* when the icon set is missing (the
    eye and the padlock must show either way — they are the buttons)."""
    icon = icons.icon(icon_name)
    if icon.isNull():
        item.setText(column, text)
        item.setTextAlignment(column, Qt.AlignCenter)
    else:
        item.setIcon(column, icon)


class CollectionsTree(QTreeWidget):
    def __init__(self, panel):
        super().__init__()
        self.panel = panel
        self.setColumnCount(3)
        self.setHeaderHidden(True)
        header = self.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(NAME, QHeaderView.Stretch)
        for col in (EYE, LOCK):
            header.setSectionResizeMode(col, QHeaderView.Fixed)
            header.resizeSection(col, 32)
        self.setIconSize(QSize(16, 16))
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setIndentation(14)

    # a part dropped on a collection row (or on one of its parts) goes
    # into that collection; dropped on "Not in a collection", out of all
    def _target(self, item):
        while item is not None:
            kind, value = item.data(0, ROLE)
            if kind == "collection":
                return value
            if kind == "loose":
                return ""
            item = item.parent()
        return None

    def dragEnterEvent(self, event):
        event.acceptProposedAction()

    def dragMoveEvent(self, event):
        item = self.itemAt(event.pos())
        if self._target(item) is None:
            event.ignore()
        else:
            event.acceptProposedAction()

    def dropEvent(self, event):
        target = self._target(self.itemAt(event.pos()))
        source = event.source()
        if target is None:
            event.ignore()
            return
        if source is self:
            nodes = self.panel.selected_parts()
        elif hasattr(source, "_top_level_selection"):
            nodes = source._top_level_selection()    # from the Main tree
        else:
            event.ignore()
            return
        event.setDropAction(Qt.CopyAction)       # never let Qt move rows
        event.accept()
        if nodes:
            pc.assign(self.panel.model, nodes, target)


class CollectionsPanel(QWidget):
    def __init__(self, model, main_tree, parent=None):
        super().__init__(parent)
        self.model = model
        self.main_tree = main_tree
        self._building = False
        #: rows the user folded (by ("collection", name) / ("loose",))
        self._collapsed = set()
        box = QVBoxLayout(self)
        box.setContentsMargins(4, 4, 4, 0)
        box.setSpacing(4)
        row = QHBoxLayout()
        for icon, text, tip, slot in (
                ("mdi.folder-plus-outline", "New",
                 "New collection (holding the parts selected in Main)",
                 self.new_collection),
                ("mdi.folder-arrow-right-outline", "Add",
                 "Move the parts selected in Main into the selected "
                 "collection", self.add_selected),
                ("mdi.folder-remove-outline", "Remove",
                 "Take the selected parts out of their collection",
                 self.take_out),
                ("mdi.eye-outline", "Show all", "Show every collection",
                 self.show_all),
                ("mdi.delete-outline", "Delete",
                 "Delete the selected collection (its parts stay)",
                 self.delete_selected)):
            b = QToolButton()
            b.setIcon(icons.icon(icon))
            if b.icon().isNull():
                b.setText(text)
            b.setToolTip(tip)
            b.setAutoRaise(True)
            b.clicked.connect(slot)
            row.addWidget(b)
        row.addStretch()
        box.addLayout(row)
        self.tree = CollectionsTree(self)
        box.addWidget(self.tree)
        self.hint = QLabel("Collections group parts to show, hide or lock "
                           "together — the eye hides them in the views "
                           "(never in the program or exports), Ctrl+click "
                           "shows one alone. In Main: right-click ▸ Move "
                           "to Collection; here, drag parts between "
                           "collections.")
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet("color: gray;")
        box.addWidget(self.hint)
        self.tree.itemClicked.connect(self._clicked)
        self.tree.itemCollapsed.connect(
            lambda it: self._building or self._collapsed.add(self._key(it)))
        self.tree.itemExpanded.connect(
            lambda it: self._building
            or self._collapsed.discard(self._key(it)))
        self.tree.itemChanged.connect(self._renamed)
        self.tree.itemSelectionChanged.connect(self._selected)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._menu)
        model.structure_changed.connect(self.refresh)
        model.node_changed.connect(lambda _n: self.refresh())
        self.refresh()

    # ----------------------------------------------------------- build
    def refresh(self):
        pc.forget_missing(self.model)
        self._building = True
        self.tree.clear()
        for c in self.model.collections:
            item = self._collection_item(c)
            for node in pc.members(self.model, c["name"]):
                item.addChild(self._part_item(node, c))
            self.tree.addTopLevelItem(item)
            item.setExpanded(("collection", c["name"])
                             not in self._collapsed)
        loose = loose_parts(self.model)
        if loose or not self.model.collections:
            item = QTreeWidgetItem([LOOSE, "", ""])
            item.setData(0, ROLE, ("loose", None))
            item.setIcon(NAME, icons.icon("mdi.folder-outline"))
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsDropEnabled)
            font = item.font(NAME)
            font.setItalic(True)
            item.setFont(NAME, font)
            for node in loose:
                item.addChild(self._part_item(node, None))
            self.tree.addTopLevelItem(item)
            item.setExpanded(("loose", None) not in self._collapsed)
        self._building = False

    @staticmethod
    def _key(item):
        return tuple(item.data(0, ROLE)) if item is not None else None

    def _collection_item(self, c):
        visible = bool(c.get("visible", True))
        locked = bool(c.get("locked", False))
        item = QTreeWidgetItem([c["name"], "", ""])
        item.setData(0, ROLE, ("collection", c["name"]))
        item.setIcon(NAME, icons.icon("mdi.folder-multiple-outline"))
        _mark(item, EYE, "mdi.eye-outline" if visible
              else "mdi.eye-off-outline", "●" if visible else "○")
        _mark(item, LOCK, "mdi.lock-outline" if locked
              else "mdi.lock-open-variant-outline", "🔒" if locked else "·")
        item.setToolTip(EYE, "Show / hide in the views "
                             "(Ctrl+click: show this one alone)")
        item.setToolTip(LOCK, "Lock: its parts cannot be picked or "
                              "dragged in the 2D view")
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable
                      | Qt.ItemIsEditable | Qt.ItemIsDropEnabled)
        font = item.font(NAME)
        font.setBold(True)
        font.setItalic(not visible)
        item.setFont(NAME, font)
        return item

    def _part_item(self, node, c):
        item = QTreeWidgetItem([node.name, "", ""])
        item.setData(0, ROLE, ("part", node.id))
        spec = NODE_TYPES.get(node.type, {})
        item.setIcon(NAME, icons.icon(spec.get("icon", "mdi.cube-outline")))
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable
                      | Qt.ItemIsDragEnabled)
        if c is not None and not c.get("visible", True):
            font = item.font(NAME)
            font.setItalic(True)
            item.setFont(NAME, font)
            item.setForeground(NAME, self.palette().mid())
        return item

    # --------------------------------------------------------- reading
    def selected_collection(self):
        for item in self.tree.selectedItems():
            kind, value = item.data(0, ROLE)
            if kind == "collection":
                return value
            if kind == "part" and item.parent() is not None:
                pkind, pvalue = item.parent().data(0, ROLE)
                if pkind == "collection":
                    return pvalue
        return None

    def selected_parts(self):
        nodes = []
        for item in self.tree.selectedItems():
            kind, value = item.data(0, ROLE)
            if kind == "part":
                node = self.model.find(value)
                if node is not None:
                    nodes.append(node)
        return nodes

    # --------------------------------------------------------- actions
    def _clicked(self, item, column):
        kind, name = item.data(0, ROLE)
        if kind != "collection":
            return
        from PyQt5.QtWidgets import QApplication
        c = pc.get(self.model, name)
        if column == EYE:
            if QApplication.keyboardModifiers() & Qt.ControlModifier:
                pc.solo(self.model, name)
            else:
                pc.set_visible(self.model, name,
                               not c.get("visible", True))
        elif column == LOCK:
            pc.set_locked(self.model, name, not c.get("locked", False))

    def _renamed(self, item, column):
        if self._building or column != NAME:
            return
        kind, old = item.data(0, ROLE)
        if kind != "collection" or item.text(NAME) == old:
            return
        try:
            pc.rename(self.model, old, item.text(NAME))
        except pc.CollectionError as exc:
            QMessageBox.warning(self, "Collections", str(exc))
            self.refresh()

    def _selected(self):
        if self._building:
            return
        nodes = self.selected_parts()
        if nodes:
            self.main_tree.select_nodes(nodes)

    def new_collection(self):
        nodes = self.main_tree._top_level_selection()
        name, ok = QInputDialog.getText(
            self, "New collection", "Name:",
            text=pc.unique_name(self.model))
        if ok:
            pc.create(self.model, name, nodes)

    def add_selected(self):
        name = self.selected_collection()
        nodes = self.main_tree._top_level_selection()
        if name is None:
            if nodes:
                self.new_collection()
            return
        if nodes:
            pc.assign(self.model, nodes, name)

    def take_out(self):
        nodes = self.selected_parts()
        if nodes:
            pc.assign(self.model, nodes, "")

    def show_all(self):
        for c in self.model.collections:
            c["visible"] = True
        self.model.structure_changed.emit()

    def delete_selected(self):
        name = self.selected_collection()
        if name is not None:
            pc.remove(self.model, name)

    def _menu(self, pos):
        item = self.tree.itemAt(pos)
        menu = QMenu(self)
        kind, name = item.data(0, ROLE) if item is not None \
            else (None, None)
        if kind == "collection":
            c = pc.get(self.model, name)
            menu.addAction(icons.icon("mdi.eye-outline"),
                           "Hide" if c.get("visible", True) else "Show",
                           lambda: pc.set_visible(
                               self.model, name, not c.get("visible",
                                                           True)))
            menu.addAction(icons.icon("mdi.eye-circle-outline"),
                           "Show only this", lambda: pc.solo(self.model,
                                                             name))
            menu.addAction(icons.icon("mdi.lock-outline"),
                           "Unlock" if c.get("locked") else "Lock",
                           lambda: pc.set_locked(
                               self.model, name, not c.get("locked")))
            menu.addAction(icons.icon("mdi.cursor-default-click-outline"),
                           "Select its parts",
                           lambda: self.main_tree.select_nodes(
                               pc.members(self.model, name)))
            menu.addAction(icons.icon("mdi.folder-arrow-right-outline"),
                           "Move Main's selection here",
                           self.add_selected)
            menu.addAction(icons.icon("mdi.rename-box"), "Rename",
                           lambda: self.tree.editItem(item, NAME))
            menu.addSeparator()
            menu.addAction(icons.icon("mdi.delete-outline"),
                           "Delete collection (keep its parts)",
                           lambda: pc.remove(self.model, name))
        elif kind == "part":
            sub = menu.addMenu(icons.icon("mdi.folder-arrow-right-outline"),
                               "Move to collection")
            fill_move_menu(sub, self.model, self.selected_parts)
            menu.addAction(icons.icon("mdi.folder-remove-outline"),
                           "Take out of its collection", self.take_out)
        else:
            menu.addAction(icons.icon("mdi.folder-plus-outline"),
                           "New collection", self.new_collection)
        menu.exec_(self.tree.viewport().mapToGlobal(pos))


def fill_move_menu(menu, model, nodes_of):
    """"Move to collection ▸" entries: every collection, New…, None.
    *nodes_of* is called when an entry is chosen."""
    for name in pc.names(model):
        menu.addAction(icons.icon("mdi.folder-multiple-outline"), name,
                       lambda _=False, n=name: pc.assign(model, nodes_of(),
                                                         n))
    if pc.names(model):
        menu.addSeparator()

    def new():
        name, ok = QInputDialog.getText(
            menu.parentWidget(), "New collection", "Name:",
            text=pc.unique_name(model))
        if ok:
            pc.create(model, name, nodes_of())
    menu.addAction(icons.icon("mdi.folder-plus-outline"),
                   "New collection…", new)
    menu.addAction(icons.icon("mdi.folder-remove-outline"),
                   "None (take out)",
                   lambda: pc.assign(model, nodes_of(), ""))

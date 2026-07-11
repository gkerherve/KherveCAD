"""Object builder panel — the tree of objects and the generated code.

Left-hand tabbed panel: the **Objects** tab shows the document tree
(rename, hide, group, apply operations via the context menu, reorder
by drag & drop); the **Code** tab shows the OpenSCAD program that the
tree generates, with syntax highlighting. The code is read-only — the
tree is the source of truth.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import re

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import (QColor, QFont, QSyntaxHighlighter,
                         QTextCharFormat)
from PyQt5.QtWidgets import (QAbstractItemView, QMenu, QPlainTextEdit,
                             QTabWidget, QTreeWidget, QTreeWidgetItem)

from . import icons
from .model import NODE_TYPES, OPERATION, DocumentModel

#: operations offered by the "Apply" context submenu.
APPLY_OPS = ["linear_extrude", "rotate_extrude", "offset", "translate",
             "rotate", "scale", "mirror", "difference", "intersection",
             "hull", "minkowski", "for_loop", "while_loop", "if_else"]


class ObjectTree(QTreeWidget):
    """The work tree: one item per CadNode, checkbox = visibility."""

    selection_changed = pyqtSignal(list)     # list of CadNode

    def __init__(self, model: DocumentModel, parent=None):
        super().__init__(parent)
        self.model = model
        self._updating = False
        self.setHeaderLabels(["Object"])
        self.setHeaderHidden(True)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setExpandsOnDoubleClick(False)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)
        self.itemChanged.connect(self._item_changed)
        self.itemSelectionChanged.connect(self._emit_selection)
        self.itemDoubleClicked.connect(
            lambda item, _col: self.editItem(item, 0))
        model.structure_changed.connect(self.rebuild)
        model.node_changed.connect(self._refresh_node)
        self.rebuild()

    # ------------------------------------------------------------ sync
    def node_of(self, item: QTreeWidgetItem):
        return self.model.find(item.data(0, Qt.UserRole)) if item else None

    def _item_of(self, node, root_item=None):
        root_item = root_item or self.invisibleRootItem()
        for i in range(root_item.childCount()):
            child = root_item.child(i)
            if child.data(0, Qt.UserRole) == node.id:
                return child
            found = self._item_of(node, child)
            if found:
                return found
        return None

    def selected_nodes(self):
        return [n for n in (self.node_of(i) for i in self.selectedItems())
                if n is not None]

    def rebuild(self):
        expanded = {self.node_of(item).id
                    for item in self._all_items()
                    if item.isExpanded() and self.node_of(item)}
        selected = {n.id for n in self.selected_nodes()}
        self._updating = True
        self.clear()
        for child in self.model.root.children:
            self._build_item(child, self.invisibleRootItem(),
                             expanded, selected)
        self._updating = False
        self._emit_selection()

    def _build_item(self, node, parent_item, expanded, selected):
        item = QTreeWidgetItem(parent_item)
        item.setData(0, Qt.UserRole, node.id)
        item.setFlags(item.flags() | Qt.ItemIsEditable
                      | Qt.ItemIsUserCheckable
                      | (Qt.ItemIsDropEnabled if node.is_container()
                         else Qt.ItemFlags()))
        if not node.is_container():
            item.setFlags(item.flags() & ~Qt.ItemIsDropEnabled)
        self._decorate(item, node)
        if node.id in expanded or node.is_container():
            item.setExpanded(True)
        if node.id in selected:
            item.setSelected(True)
        for child in node.children:
            self._build_item(child, item, expanded, selected)

    def _decorate(self, item, node):
        item.setText(0, node.name)
        item.setIcon(0, icons.icon(NODE_TYPES[node.type]["icon"]))
        item.setCheckState(0, Qt.Checked if node.visible else Qt.Unchecked)
        item.setToolTip(0, NODE_TYPES[node.type]["label"])

    def _all_items(self):
        result = []

        def collect(parent):
            for i in range(parent.childCount()):
                result.append(parent.child(i))
                collect(parent.child(i))
        collect(self.invisibleRootItem())
        return result

    def _refresh_node(self, node):
        item = self._item_of(node)
        if item:
            self._updating = True
            self._decorate(item, node)
            self._updating = False

    def _item_changed(self, item, column):
        if self._updating or column != 0:
            return
        node = self.node_of(item)
        if node is None:
            return
        visible = item.checkState(0) == Qt.Checked
        if visible != node.visible:
            self.model.set_visible(node, visible)
        if item.text(0) and item.text(0) != node.name:
            self.model.rename(node, item.text(0))

    def _emit_selection(self):
        if not self._updating:
            self.selection_changed.emit(self.selected_nodes())

    def select_nodes(self, nodes):
        """Programmatic selection (e.g. clicked in the 2D view)."""
        self._updating = True
        self.clearSelection()
        for node in nodes:
            item = self._item_of(node)
            if item:
                item.setSelected(True)
                self.scrollToItem(item)
        self._updating = False
        self._emit_selection()

    # ----------------------------------------------------- drag & drop
    def dropEvent(self, event):
        moving = self.selected_nodes()
        target_item = self.itemAt(event.pos())
        target = self.node_of(target_item) or self.model.root
        pos = self.dropIndicatorPosition()
        if pos == QAbstractItemView.OnItem and not target.is_container():
            pos = QAbstractItemView.BelowItem
        event.setDropAction(Qt.IgnoreAction)   # we mutate the model
        event.accept()
        for node in moving:
            if pos == QAbstractItemView.OnItem:
                self.model.move_node(node, target)
            elif target.parent is not None:
                index = target.index() + \
                    (1 if pos == QAbstractItemView.BelowItem else 0)
                self.model.move_node(node, target.parent, index)
            else:
                self.model.move_node(node, self.model.root)

    # --------------------------------------------------- context menu
    def _context_menu(self, pos):
        nodes = self.selected_nodes()
        menu = QMenu(self)
        if nodes:
            hidden = [n for n in nodes if not n.visible]
            menu.addAction(
                icons.icon("mdi.eye-outline" if hidden
                           else "mdi.eye-off-outline"),
                "Show" if hidden else "Hide",
                lambda: [self.model.set_visible(n, bool(hidden))
                         for n in nodes])
            menu.addSeparator()
            apply_menu = menu.addMenu(icons.icon("mdi.auto-fix"), "Apply")
            for op in APPLY_OPS:
                apply_menu.addAction(
                    icons.icon(NODE_TYPES[op]["icon"]),
                    NODE_TYPES[op]["label"],
                    lambda _=False, o=op: self.model.wrap_nodes(nodes, o))
            apply_menu.addSeparator()
            apply_menu.addAction(
                icons.icon("mdi.circle-opacity"), "Round edges (3D)",
                lambda: self.model.round_edges(nodes))
            menu.addAction(icons.icon("mdi.group"), "Group\tCtrl+G",
                           lambda: self.model.group_nodes(nodes))
            containers = [n for n in nodes if n.is_container()]
            if containers:
                menu.addAction(
                    icons.icon("mdi.ungroup"), "Ungroup\tCtrl+Shift+G",
                    lambda: [self.model.ungroup(n) for n in containers])
            menu.addSeparator()
            if len(nodes) == 1:
                menu.addAction(icons.icon("mdi.rename-box"), "Rename",
                               lambda: self.editItem(
                                   self.selectedItems()[0], 0))
            menu.addAction(icons.icon("mdi.content-copy"), "Duplicate",
                           lambda: [self.model.duplicate(n)
                                    for n in nodes])
            menu.addSeparator()
            menu.addAction(icons.icon("mdi.delete-outline"), "Delete",
                           lambda: [self.model.remove_node(n)
                                    for n in nodes])
        if menu.actions():
            menu.exec_(self.viewport().mapToGlobal(pos))


# ------------------------------------------------------------- code tab

class ScadHighlighter(QSyntaxHighlighter):
    """Minimal OpenSCAD syntax highlighting for the Code tab."""

    KEYWORDS = ("module|function|if|else|for|let|union|difference|"
                "intersection|hull|minkowski|translate|rotate|scale|"
                "mirror|resize|color|linear_extrude|rotate_extrude|"
                "circle|square|polygon|text|cube|sphere|cylinder|"
                "polyhedron|import|surface|projection|offset|true|false")

    def __init__(self, doc, tokens: dict):
        super().__init__(doc)
        def fmt(color, bold=False):
            f = QTextCharFormat()
            f.setForeground(QColor(color))
            if bold:
                f.setFontWeight(QFont.Bold)
            return f
        dark = tokens.get("dark")
        self.rules = [
            (re.compile(r"\b(%s)\b" % self.KEYWORDS),
             fmt("#6ab0f3" if dark else "#1565c0", bold=True)),
            (re.compile(r"\$\w+"),
             fmt("#c586c0" if dark else "#7b1fa2")),
            (re.compile(r"\b\d+(\.\d+)?\b"),
             fmt("#b5cea8" if dark else "#0f7c5a")),
            (re.compile(r'"(\\.|[^"\\])*"'),
             fmt("#ce9178" if dark else "#b3541e")),
            (re.compile(r"^\s*\*"),
             fmt("#e06c75" if dark else "#c62828", bold=True)),
            (re.compile(r"//[^\n]*"),
             fmt("#7f848e" if dark else "#8a919c")),
        ]

    def highlightBlock(self, text):
        for pattern, fmt in self.rules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(),
                               match.end() - match.start(), fmt)


class CodeView(QPlainTextEdit):
    """Read-only view of the generated OpenSCAD program."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        font = QFont("Consolas")
        font.setStyleHint(QFont.Monospace)
        font.setPointSize(10)
        self.setFont(font)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        from .style import tokens
        self._highlighter = ScadHighlighter(self.document(), tokens())

    def set_code(self, code: str):
        bar = self.verticalScrollBar()
        pos = bar.value()
        self.setPlainText(code)
        bar.setValue(min(pos, bar.maximum()))


class BuilderPanel(QTabWidget):
    """Objects tree + Code tabs, kept in sync with the model."""

    def __init__(self, model: DocumentModel, parent=None):
        super().__init__(parent)
        self.model = model
        self.tree = ObjectTree(model)
        self.code = CodeView()
        self.addTab(self.tree, icons.icon("mdi.file-tree"), "Objects")
        self.addTab(self.code, icons.icon("mdi.code-braces"), "Code")
        model.structure_changed.connect(self.refresh_code)
        model.node_changed.connect(lambda _n: self.refresh_code())
        self.refresh_code()

    def refresh_code(self):
        self.code.set_code(self.model.to_scad())

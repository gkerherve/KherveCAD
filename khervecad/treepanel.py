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

import json
import re

from PyQt5.QtCore import QEvent, Qt, pyqtSignal
from PyQt5.QtGui import (QBrush, QColor, QFont, QKeySequence,
                         QSyntaxHighlighter, QTextCharFormat)
from PyQt5.QtWidgets import (QAbstractItemView, QApplication, QCheckBox,
                             QHBoxLayout, QMenu, QMessageBox,
                             QPlainTextEdit, QPushButton, QSpinBox,
                             QTableWidget, QTableWidgetItem, QTabWidget,
                             QTextEdit, QTreeWidget, QTreeWidgetItem,
                             QVBoxLayout, QWidget)

from . import icons
from .document import node_from_dict, node_to_dict
from .model import (CadNode, NODE_TYPES, OPERATION, DocumentModel,
                    validate)

#: colour for objects whose code would be broken.
ERROR_COLOR = "#c62828"
ERROR_COLOR_DARK = "#ef6c6c"
#: colour for variable (assign) nodes so they read as a group.
VAR_COLOR = "#6f42c1"
VAR_COLOR_DARK = "#c39bf0"

CLIPBOARD_FORMAT = "kcad-clipboard"

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
        self.errors = {}                      # node id -> message
        #: {node id: expanded?} — the user's own expand/collapse, kept
        #: across rebuilds so adding an object never re-opens a group
        #: you collapsed.
        self._expand_state = {}
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
        self.itemExpanded.connect(self._remember_expanded)
        self.itemCollapsed.connect(self._remember_collapsed)
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
        selected = {n.id for n in self.selected_nodes()}
        self._updating = True
        self.clear()
        for child in self.model.root.children:
            self._build_item(child, self.invisibleRootItem(), selected)
        self._updating = False
        self._emit_selection()

    def _remember_expanded(self, item):
        if not self._updating:
            node = self.node_of(item)
            if node is not None:
                self._expand_state[node.id] = True

    def _remember_collapsed(self, item):
        if not self._updating:
            node = self.node_of(item)
            if node is not None:
                self._expand_state[node.id] = False

    def _build_item(self, node, parent_item, selected):
        item = QTreeWidgetItem(parent_item)
        item.setData(0, Qt.UserRole, node.id)
        item.setFlags(item.flags() | Qt.ItemIsEditable
                      | Qt.ItemIsUserCheckable
                      | (Qt.ItemIsDropEnabled if node.is_container()
                         else Qt.ItemFlags()))
        if not node.is_container():
            item.setFlags(item.flags() & ~Qt.ItemIsDropEnabled)
        self._decorate(item, node)
        # honour the user's own expand/collapse (remembered across
        # rebuilds); a brand-new container defaults to open, except the
        # Variables group which starts collapsed
        if node.is_container():
            default_open = node.type != "variables"
            if self._expand_state.get(node.id, default_open):
                item.setExpanded(True)
        if node.id in selected:
            item.setSelected(True)
        for child in node.children:
            self._build_item(child, item, selected)

    def _decorate(self, item, node):
        item.setText(0, node.name)
        item.setIcon(0, icons.icon(NODE_TYPES[node.type]["icon"]))
        item.setCheckState(0, Qt.Checked if node.visible else Qt.Unchecked)
        error = self.errors.get(node.id)
        if error:
            from .style import tokens
            color = ERROR_COLOR_DARK if tokens().get("dark") \
                else ERROR_COLOR
            item.setForeground(0, QBrush(QColor(color)))
            item.setToolTip(0, f"⚠ {error}")
        elif node.type == "assign":
            from .style import tokens
            color = VAR_COLOR_DARK if tokens().get("dark") else VAR_COLOR
            item.setForeground(0, QBrush(QColor(color)))
            item.setToolTip(0, "Variable — also editable in the "
                               "Variables sheet")
        else:
            item.setData(0, Qt.ForegroundRole, None)
            item.setToolTip(0, NODE_TYPES[node.type]["label"])

    def set_errors(self, errors: dict):
        """Paint nodes with problems red (tooltip = the message)."""
        self.errors = errors or {}
        self._updating = True
        for item in self._all_items():
            node = self.node_of(item)
            if node is not None:
                self._decorate(item, node)
        self._updating = False

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

    # -------------------------------------------------------- clipboard
    def _top_level_selection(self):
        """Selected nodes minus any whose ancestor is also selected."""
        nodes = self.selected_nodes()
        chosen = []
        for node in nodes:
            probe = node.parent
            while probe is not None and probe not in nodes:
                probe = probe.parent
            if probe is None:
                chosen.append(node)
        return chosen

    def copy_selection(self):
        nodes = self._top_level_selection()
        if not nodes:
            return
        payload = {"format": CLIPBOARD_FORMAT,
                   "nodes": [node_to_dict(n) for n in nodes]}
        QApplication.clipboard().setText(json.dumps(payload))

    def cut_selection(self):
        nodes = self._top_level_selection()
        if not nodes:
            return
        self.copy_selection()
        for node in nodes:
            self.model.remove_node(node)

    def paste_clipboard(self):
        """Paste into the selected container, after the selected
        object, or at the end of the document."""
        try:
            payload = json.loads(QApplication.clipboard().text())
        except (ValueError, TypeError):
            return
        if not isinstance(payload, dict) or \
                payload.get("format") != CLIPBOARD_FORMAT:
            return
        try:
            nodes = [node_from_dict(d) for d in payload.get("nodes", [])]
        except (ValueError, KeyError, TypeError):
            return
        if not nodes:
            return
        selected = self._top_level_selection()
        parent, index = self.model.root, None
        if len(selected) == 1:
            if selected[0].is_container():
                parent = selected[0]
            elif selected[0].parent is not None:
                parent = selected[0].parent
                index = selected[0].index() + 1
        for offset, node in enumerate(nodes):
            node.name = self._pasted_name(node.name)
            parent.add(node, None if index is None else index + offset)
        self.model.structure_changed.emit()
        self.select_nodes(nodes)

    def _pasted_name(self, name):
        taken = {n.name for n in self.model.root.walk()}
        if name not in taken:
            return name
        base = re.sub(r" \(copy( \d+)?\)$", "", name)
        for i in range(1, 1000):
            suffix = " (copy)" if i == 1 else f" (copy {i})"
            if base + suffix not in taken:
                return base + suffix
        return name

    def shift_selection(self, delta: int):
        nodes = self._top_level_selection()
        for node in (nodes if delta < 0 else reversed(nodes)):
            self.model.shift_node(node, delta)
        self.select_nodes(nodes)

    def step_selection(self, delta: int):
        """Move the selection to the next/previous object in tree order
        (Tab / Shift+Tab, or Q / A) — wraps around the ends."""
        order = [n for n in self.model.root.walk() if n.type != "root"]
        if not order:
            return
        current = self.selected_nodes()
        if current:
            try:
                index = order.index(current[-1])
            except ValueError:
                index = 0
            index = (index + delta) % len(order)
        else:
            index = 0 if delta >= 0 else len(order) - 1
        self.select_nodes([order[index]])

    def event(self, e):
        # Tab is normally consumed by focus traversal — grab it here so
        # it steps through objects instead.
        if e.type() == QEvent.KeyPress and \
                e.key() in (Qt.Key_Tab, Qt.Key_Backtab):
            self.step_selection(1 if e.key() == Qt.Key_Tab else -1)
            return True
        return super().event(e)

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Q:
            self.step_selection(-1)           # Q: up / previous
        elif key == Qt.Key_A:
            self.step_selection(1)            # A: down / next
        elif event.matches(QKeySequence.Copy):
            self.copy_selection()
        elif event.matches(QKeySequence.Cut):
            self.cut_selection()
        elif event.matches(QKeySequence.Paste):
            self.paste_clipboard()
        elif event.matches(QKeySequence.Delete):
            for node in self._top_level_selection():
                self.model.remove_node(node)
        elif event.key() == Qt.Key_Up and \
                event.modifiers() & Qt.ControlModifier:
            self.shift_selection(-1)
        elif event.key() == Qt.Key_Down and \
                event.modifiers() & Qt.ControlModifier:
            self.shift_selection(1)
        else:
            super().keyPressEvent(event)

    def _pick_color(self, nodes):
        """Colour the selected objects with OpenSCAD's color()."""
        from PyQt5.QtWidgets import QColorDialog
        current = "#4a90d9"
        alpha = 1.0
        for node in nodes:
            probe = node if node.type == "color" else \
                (node.parent if node.parent is not None
                 and node.parent.type == "color" else None)
            if probe is not None:
                current = str(probe.params.get("color", current))
                alpha = float(probe.params.get("alpha", 1.0))
                break
        initial = QColor(current)
        if initial.isValid():
            initial.setAlphaF(alpha)
        chosen = QColorDialog.getColor(
            initial if initial.isValid() else QColor("#4a90d9"),
            self, "Object colour",
            QColorDialog.ShowAlphaChannel)
        if chosen.isValid():
            self.model.set_color(nodes, chosen.name(),
                                 round(chosen.alphaF(), 3))

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
                icons.icon("mdi.blur"), "Round edges (3D)",
                lambda: self.model.round_edges(nodes))
            menu.addAction(icons.icon("mdi.palette-outline"),
                           "Color...", lambda: self._pick_color(nodes))
            menu.addAction(icons.icon("mdi.group"), "Group\tCtrl+G",
                           lambda: self.model.group_nodes(nodes))
            containers = [n for n in nodes if n.is_container()]
            if containers:
                menu.addAction(
                    icons.icon("mdi.ungroup"), "Ungroup\tCtrl+Shift+G",
                    lambda: [self.model.ungroup(n) for n in containers])
            menu.addSeparator()
            menu.addAction(icons.icon("mdi.content-cut"),
                           "Cut\tCtrl+X", self.cut_selection)
            menu.addAction(icons.icon("mdi.content-copy"),
                           "Copy\tCtrl+C", self.copy_selection)
            menu.addAction(icons.icon("mdi.content-paste"),
                           "Paste\tCtrl+V", self.paste_clipboard)
            menu.addSeparator()
            if len(nodes) == 1:
                menu.addAction(icons.icon("mdi.rename-box"), "Rename",
                               lambda: self.editItem(
                                   self.selectedItems()[0], 0))
            menu.addAction(icons.icon("mdi.content-duplicate"),
                           "Duplicate", lambda: [self.model.duplicate(n)
                                                 for n in nodes])
            if len(nodes) == 1:
                menu.addAction(
                    icons.icon("mdi.link-variant"),
                    "Linked copy (updates with master)",
                    lambda: self.model.add_linked_copy(nodes[0]))
            menu.addSeparator()
            menu.addAction(icons.icon("mdi.delete-outline"), "Delete",
                           lambda: [self.model.remove_node(n)
                                    for n in nodes])
        else:
            menu.addAction(icons.icon("mdi.content-paste"),
                           "Paste\tCtrl+V", self.paste_clipboard)
        if menu.actions():
            menu.exec_(self.viewport().mapToGlobal(pos))


# ------------------------------------------------------------- code tab

class ScadHighlighter(QSyntaxHighlighter):
    """OpenSCAD syntax highlighting: each family of constructs gets
    its own colour so the program structure is readable at a glance —
    2D/3D shapes, transforms, booleans, control flow, numbers,
    strings, special variables, comments and the `*` disable
    modifier."""

    SHAPES = (r"circle|square|polygon|text|cube|sphere|cylinder|"
              r"polyhedron|import|surface")
    TRANSFORMS = (r"translate|rotate|scale|mirror|resize|"
                  r"linear_extrude|rotate_extrude|offset|projection|"
                  r"color")
    BOOLEANS = r"union|difference|intersection|hull|minkowski"
    CONTROL = r"module|function|if|else|for|let|each|echo|assert"

    def __init__(self, doc, tokens: dict):
        super().__init__(doc)

        def fmt(color, bold=False, italic=False):
            f = QTextCharFormat()
            f.setForeground(QColor(color))
            if bold:
                f.setFontWeight(QFont.Bold)
            if italic:
                f.setFontItalic(True)
            return f
        dark = tokens.get("dark")

        def pick(dark_color, light_color):
            return dark_color if dark else light_color
        self.rules = [
            # assigned variable names (start of line: name = ...)
            (re.compile(r"^\s*(\$?[A-Za-z_]\w*)(?=\s*=[^=])"),
             fmt(pick("#e5c07b", "#8d6e00"))),
            (re.compile(r"\b(%s)\b(?=\s*\()" % self.SHAPES),
             fmt(pick("#4ec9b0", "#0f7c5a"), bold=True)),
            (re.compile(r"\b(%s)\b(?=\s*\()" % self.TRANSFORMS),
             fmt(pick("#6ab0f3", "#1565c0"), bold=True)),
            (re.compile(r"\b(%s)\b(?=\s*\()" % self.BOOLEANS),
             fmt(pick("#c586c0", "#7b1fa2"), bold=True)),
            (re.compile(r"\b(%s)\b" % self.CONTROL),
             fmt(pick("#e06c75", "#b3541e"), bold=True)),
            (re.compile(r"\b(true|false|undef|PI)\b"),
             fmt(pick("#d19a66", "#986801"), bold=True)),
            (re.compile(r"\$\w+"),
             fmt(pick("#c586c0", "#7b1fa2"), italic=True)),
            (re.compile(r"\b\d+\.?\d*([eE][-+]?\d+)?\b|\.\d+"),
             fmt(pick("#b5cea8", "#0b8043"))),
            (re.compile(r'"(\\.|[^"\\])*"'),
             fmt(pick("#ce9178", "#b3541e"))),
            (re.compile(r"^\s*\*[^\n]*"),
             fmt(pick("#7f848e", "#9aa0a6"), italic=True)),
            (re.compile(r"//[^\n]*"),
             fmt(pick("#7f848e", "#8a919c"), italic=True)),
        ]

    def highlightBlock(self, text):
        for pattern, fmt in self.rules:
            for match in pattern.finditer(text):
                start = match.start(1) if match.groups() else \
                    match.start()
                end = match.end(1) if match.groups() else match.end()
                self.setFormat(start, end - start, fmt)


class CodeView(QPlainTextEdit):
    """Editable view of the OpenSCAD program with line highlights: the
    selected object's lines glow in the theme accent, broken lines are
    tinted red. Edits take effect only when "Apply code" re-parses the
    text back into the object tree."""

    def __init__(self, parent=None):
        super().__init__(parent)
        font = QFont("Consolas")
        font.setStyleHint(QFont.Monospace)
        font.setPointSize(10)
        self.setFont(font)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self._selected_ranges = []
        self._error_ranges = []
        self.refresh_theme()

    def refresh_theme(self):
        from .style import tokens
        self._highlighter = ScadHighlighter(self.document(), tokens())
        self._apply_marks()

    def set_code(self, code: str):
        bar = self.verticalScrollBar()
        pos = bar.value()
        self.setPlainText(code)
        bar.setValue(min(pos, bar.maximum()))
        self._apply_marks()

    def set_marks(self, selected_ranges, error_ranges):
        """Line ranges (start, end_exclusive) to tint."""
        self._selected_ranges = list(selected_ranges)
        self._error_ranges = list(error_ranges)
        self._apply_marks()

    def _apply_marks(self):
        from .style import tokens
        t = tokens()
        select = QColor(t["select"])
        select.setAlpha(45)
        error = QColor(ERROR_COLOR_DARK if t.get("dark")
                       else ERROR_COLOR)
        error.setAlpha(55)
        extras = []
        for ranges, color in ((self._selected_ranges, select),
                              (self._error_ranges, error)):
            for start, end in ranges:
                for line in range(start, end):
                    block = self.document().findBlockByNumber(line)
                    if not block.isValid():
                        continue
                    selection = QTextEdit.ExtraSelection()
                    selection.format.setBackground(color)
                    selection.format.setProperty(
                        QTextCharFormat.FullWidthSelection, True)
                    from PyQt5.QtGui import QTextCursor
                    selection.cursor = QTextCursor(block)
                    extras.append(selection)
        self.setExtraSelections(extras)
        # scroll the first selected span into view
        if self._selected_ranges:
            first = self._selected_ranges[0][0]
            block = self.document().findBlockByNumber(first)
            if block.isValid():
                from PyQt5.QtGui import QTextCursor
                cursor = QTextCursor(block)
                self.setTextCursor(cursor)
                self.ensureCursorVisible()


class VariablesSheet(QWidget):
    """A spreadsheet of the document's variables (assign nodes), so all
    the parameters live in one place instead of sprawling down the
    object tree. Edits write straight back to the model, and it stays in
    sync when variables are changed elsewhere."""

    def __init__(self, model: DocumentModel, parent=None):
        super().__init__(parent)
        self.model = model
        self._updating = False
        self._rows = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Name", "Value / expression"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 170)
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.itemChanged.connect(self._cell_edited)
        layout.addWidget(self.table)

        buttons = QHBoxLayout()
        add = QPushButton(icons.icon("mdi.plus"), " Variable")
        add.setToolTip("Add a variable")
        add.clicked.connect(self._add)
        remove = QPushButton(icons.icon("mdi.minus"), " Remove")
        remove.setToolTip("Remove the selected variable")
        remove.clicked.connect(self._remove)
        buttons.addWidget(add)
        buttons.addWidget(remove)
        buttons.addStretch()
        layout.addLayout(buttons)

        model.structure_changed.connect(self.rebuild)
        model.node_changed.connect(self._node_changed)
        self.rebuild()

    def _assigns(self):
        return [n for n in self.model.root.walk() if n.type == "assign"]

    def rebuild(self):
        self._updating = True
        self._rows = self._assigns()
        self.table.setRowCount(len(self._rows))
        for row, node in enumerate(self._rows):
            self.table.setItem(row, 0, QTableWidgetItem(
                str(node.params.get("variable", ""))))
            self.table.setItem(row, 1, QTableWidgetItem(
                str(node.params.get("value", ""))))
        self._updating = False

    def _node_changed(self, node):
        if not self._updating and getattr(node, "type", None) == "assign":
            self.rebuild()

    def _cell_edited(self, item):
        if self._updating or item.row() >= len(self._rows):
            return
        node = self._rows[item.row()]
        if item.column() == 0:
            name = item.text().strip()
            if name:
                node.params["variable"] = name
                node.name = f"{name} ="
        else:
            node.params["value"] = item.text().strip()
        self.model.node_changed.emit(node)

    def _add(self):
        assigns = self._assigns()
        used = {n.params.get("variable") for n in assigns}
        i = 1
        while f"var{i}" in used:
            i += 1
        name = f"var{i}"
        node = CadNode("assign", f"{name} =",
                       dict(variable=name, value="0"))
        # keep new variables in the variable block, ahead of geometry
        if assigns:
            last = assigns[-1]
            last.parent.add(node, last.index() + 1)
        else:
            self.model.root.add(node, 0)
        self.model.structure_changed.emit()

    def _remove(self):
        row = self.table.currentRow()
        if 0 <= row < len(self._rows):
            self.model.remove_node(self._rows[row])


class BuilderPanel(QTabWidget):
    """Objects tree + Variables + Code tabs, kept in sync with the model.

    Also owns the error state: static validation runs on every change
    and OpenSCAD compiler errors are merged in by the main window;
    broken nodes turn red in the tree and their lines red in the
    code."""

    def __init__(self, model: DocumentModel, parent=None):
        super().__init__(parent)
        self.model = model
        self.tree = ObjectTree(model)
        self.code = CodeView()
        self._spans = {}
        self._engine_errors = {}
        self._selected_ids = []

        # Objects tab: a common-segments toggle pinned above the tree
        objects = QWidget()
        box = QVBoxLayout(objects)
        box.setContentsMargins(4, 4, 4, 0)
        box.setSpacing(4)
        row = QHBoxLayout()
        self.fn_check = QCheckBox("Common segments ($fn)")
        self.fn_check.setToolTip(
            "Force one segment count on every round object — cylinders, "
            "spheres and revolved flanges — overriding their own $fn")
        self.fn_check.setChecked(model.global_fn_on)
        self.fn_spin = QSpinBox()
        self.fn_spin.setRange(3, 512)
        self.fn_spin.setValue(int(model.global_fn))
        self.fn_spin.setEnabled(model.global_fn_on)
        self.fn_check.toggled.connect(self._fn_toggled)
        self.fn_spin.valueChanged.connect(self._fn_value_changed)
        row.addWidget(self.fn_check)
        row.addWidget(self.fn_spin)
        row.addStretch()
        box.addLayout(row)
        box.addWidget(self.tree)

        self.variables = VariablesSheet(model)

        # Code tab: the editable program + an Apply button that parses it
        # back into the object tree
        code_tab = QWidget()
        cbox = QVBoxLayout(code_tab)
        cbox.setContentsMargins(0, 0, 0, 0)
        cbox.setSpacing(4)
        cbox.addWidget(self.code)
        crow = QHBoxLayout()
        crow.setContentsMargins(4, 0, 4, 4)
        crow.addStretch()
        self.apply_btn = QPushButton(icons.icon("mdi.check"),
                                     " Apply code")
        self.apply_btn.setToolTip(
            "Parse the edited program back into the object tree "
            "(replaces the document; Ctrl+Z to undo)")
        self.apply_btn.clicked.connect(self._apply_code)
        crow.addWidget(self.apply_btn)
        cbox.addLayout(crow)

        self.addTab(objects, icons.icon("mdi.file-tree"), "Objects")
        self.addTab(self.variables, icons.icon("mdi.table"), "Variables")
        self.addTab(code_tab, icons.icon("mdi.code-braces"), "Code")
        model.structure_changed.connect(self.refresh_code)
        model.structure_changed.connect(self._sync_fn_ui)
        model.node_changed.connect(lambda _n: self.refresh_code())
        self.refresh_code()

    def _fn_toggled(self, on):
        self.fn_spin.setEnabled(on)
        self.model.set_global_fn(on, self.fn_spin.value())

    def _fn_value_changed(self, value):
        if self.fn_check.isChecked():
            self.model.set_global_fn(True, value)
        else:
            self.model.global_fn = value

    def _sync_fn_ui(self):
        """Reflect the model's setting (e.g. after loading a document)
        without echoing back a change."""
        on = self.model.global_fn_on
        for w in (self.fn_check, self.fn_spin):
            w.blockSignals(True)
        self.fn_check.setChecked(on)
        self.fn_spin.setValue(int(self.model.global_fn))
        self.fn_spin.setEnabled(on)
        for w in (self.fn_check, self.fn_spin):
            w.blockSignals(False)

    def refresh_code(self):
        code, self._spans = self.model.to_scad_map()
        self.code.set_code(code)
        self._refresh_errors()

    def _apply_code(self):
        """Parse the edited program back into the object tree. Only the
        supported subset survives (no modules/functions); anything else
        is reported and skipped."""
        from .scadparse import parse_scad
        try:
            root, warnings = parse_scad(self.code.toPlainText())
        except Exception as exc:
            QMessageBox.warning(self, "Apply code",
                                f"Could not parse the program:\n{exc}")
            return
        self.model.root = root
        self.model.group_variables()
        self.model.structure_changed.emit()       # regenerates + undoable
        if warnings:
            QMessageBox.information(
                self, "Apply code",
                "Applied, but some constructs were skipped:\n- "
                + "\n- ".join(warnings[:12])
                + ("\n…" if len(warnings) > 12 else ""))

    def set_engine_errors(self, errors: dict):
        """OpenSCAD compiler errors mapped to nodes ({id: message})."""
        self._engine_errors = errors or {}
        self._refresh_errors()

    def highlight_nodes(self, nodes):
        """Mark the selected objects' lines in the code tab."""
        self._selected_ids = [n.id for n in nodes]
        self._apply_marks()

    def errors(self) -> dict:
        combined = dict(validate(self.model.root))
        combined.update(self._engine_errors)
        return combined

    def _refresh_errors(self):
        errors = self.errors()
        self.tree.set_errors(errors)
        self._error_ids = list(errors)
        self._apply_marks()

    def _apply_marks(self):
        selected = [self._spans[i] for i in self._selected_ids
                    if i in self._spans]
        errored = [self._spans[i] for i in
                   getattr(self, "_error_ids", [])
                   if i in self._spans]
        self.code.set_marks(selected, errored)

    def refresh_theme(self):
        self.code.refresh_theme()
        self.tree.set_errors(self.tree.errors)

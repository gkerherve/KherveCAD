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

from PyQt5.QtCore import QEvent, QRect, QSize, Qt, pyqtSignal
from PyQt5.QtGui import (QBrush, QColor, QFont, QKeySequence, QPainter,
                         QPen, QSyntaxHighlighter, QTextCharFormat,
                         QTextCursor)
from PyQt5.QtWidgets import (QAbstractItemView, QApplication, QCheckBox,
                             QHBoxLayout, QMenu, QMessageBox,
                             QPlainTextEdit, QPushButton, QSpinBox,
                             QStyledItemDelegate, QTableWidget,
                             QTableWidgetItem, QTabWidget, QTextEdit,
                             QToolBar, QTreeWidget, QTreeWidgetItem,
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
#: dimmed colour for hidden objects (shown greyed + italic, no checkbox).
HIDDEN_COLOR = "#a8adb4"
HIDDEN_COLOR_DARK = "#697079"

#: single-child "decorator" wrappers that collapse onto the object they
#: modify: a chain of these ending in a leaf shows as one row + badges.
DECORATOR_TYPES = ("color", "translate", "rotate", "scale", "mirror",
                   "offset")
#: MDI icon per decorator for its row badge (color uses a live swatch).
BADGE_ICON = {
    "translate": "mdi.cursor-move",
    "rotate": "mdi.rotate-right",
    "scale": "mdi.resize",
    "mirror": "mdi.flip-horizontal",
    "offset": "mdi.rounded-corner",
}

# item data roles beyond the primary node id (Qt.UserRole)
ROLE_ROOT = Qt.UserRole + 1        # chain root node id (structural ops)
ROLE_BADGES = Qt.UserRole + 2      # [("icon", name) | ("color", hex)]
ROLE_CHAIN = Qt.UserRole + 3       # all node ids in the collapsed chain
ROLE_TAG = Qt.UserRole + 4         # True -> paint a "(hidden)" tag

CLIPBOARD_FORMAT = "kcad-clipboard"


class _RowDelegate(QStyledItemDelegate):
    """Paints modifier badges (colour swatch / transform glyphs) at the
    right of a merged row, after the normal icon + text."""

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        # a "(hidden)" tag just after the object's name
        if index.data(ROLE_TAG):
            fm = option.fontMetrics
            text = index.data(Qt.DisplayRole) or ""
            icon_w = option.decorationSize.width() + 6
            x = option.rect.left() + icon_w + fm.horizontalAdvance(text) + 8
            painter.save()
            f = painter.font()
            f.setItalic(True)
            painter.setFont(f)
            painter.setPen(QColor("#9aa0a6"))
            painter.drawText(x, option.rect.top(), 90, option.rect.height(),
                             int(Qt.AlignVCenter), "(hidden)")
            painter.restore()
        badges = index.data(ROLE_BADGES)
        if not badges:
            return
        size = 13
        gap = 3
        x = option.rect.right() - gap
        y = option.rect.center().y() - size // 2
        painter.save()
        for kind, value in reversed(badges):
            x -= size
            if kind == "color":
                painter.setPen(QPen(QColor("#888888")))
                painter.setBrush(QColor(value))
                painter.drawRoundedRect(x, y, size, size, 3, 3)
            else:
                icons.icon(value).paint(painter, x, y, size, size)
            x -= gap
        painter.restore()

#: operations offered by the "Apply" context submenu.
APPLY_OPS = ["linear_extrude", "rotate_extrude", "offset", "translate",
             "rotate", "scale", "mirror", "difference", "intersection",
             "hull", "minkowski", "for_loop", "while_loop", "if_else"]


class ObjectTree(QTreeWidget):
    """The work tree: one item per CadNode, checkbox = visibility."""

    selection_changed = pyqtSignal(list)     # list of CadNode

    #: True in the Masters variant — roots at the masters store and hides
    #: the store from the ordinary Objects tab.
    IS_MASTERS = False

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
        # deep trees stay compact and readable: a tight indent and the
        # connecting guide lines drawn in drawBranches()
        self.setIndentation(15)
        self.setRootIsDecorated(True)
        self.setItemDelegate(_RowDelegate(self))
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
        """The node a row represents for selection/properties — the
        geometry itself when a decorator chain is merged onto it."""
        return self.model.find(item.data(0, Qt.UserRole)) if item else None

    def _root_of(self, item):
        """The node a row represents for structural ops (delete, drag,
        duplicate) — the outermost node of a merged chain, so the whole
        decorated part moves together."""
        if item is None:
            return None
        rid = item.data(0, ROLE_ROOT)
        return self.model.find(rid) if rid is not None else self.node_of(item)

    def _item_of(self, node, root_item=None):
        root_item = root_item or self.invisibleRootItem()
        for i in range(root_item.childCount()):
            child = root_item.child(i)
            # match the primary node or the merged chain's root, so
            # selecting either the geometry or its wrapper finds the row
            if child.data(0, Qt.UserRole) == node.id \
                    or child.data(0, ROLE_ROOT) == node.id:
                return child
            found = self._item_of(node, child)
            if found:
                return found
        return None

    def selected_nodes(self):
        return [n for n in (self.node_of(i) for i in self.selectedItems())
                if n is not None]

    def selected_roots(self):
        """Structural nodes for the selected rows (chain roots)."""
        return [n for n in (self._root_of(i) for i in self.selectedItems())
                if n is not None]

    def _collapse_chain(self, node):
        """If *node* begins a chain of single-child decorators
        (color/transform), fold them onto the object they wrap: return
        ``(end, modifiers)`` where *end* is the wrapped node (a leaf, or
        a container whose children still nest under the merged row).
        None when *node* isn't such a chain."""
        if node.type not in DECORATOR_TYPES or len(node.children) != 1:
            return None
        mods = []
        cur = node
        while cur.type in DECORATOR_TYPES and len(cur.children) == 1:
            mods.append(cur)
            cur = cur.children[0]
        return cur, mods

    def _top_nodes(self):
        """The nodes shown at the top level of this tree — the document
        root's children with the Masters store filtered out."""
        return [c for c in self.model.root.children if c.type != "masters"]

    def _drop_container(self):
        """Container a top-level drop lands in."""
        return self.model.root

    def rebuild(self):
        selected = {n.id for n in self.selected_nodes()}
        self._updating = True
        self.clear()
        for child in self._top_nodes():
            self._build_node(child, self.invisibleRootItem(), selected)
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

    def _new_item(self, parent_item, node):
        item = QTreeWidgetItem(parent_item)
        # no visibility checkbox — hidden objects are dimmed instead,
        # toggled with Space or the right-click Hide/Show. Tree items are
        # user-checkable by default, so clear that flag explicitly.
        flags = (item.flags() | Qt.ItemIsEditable) \
            & ~Qt.ItemIsUserCheckable
        if node.is_container():
            flags |= Qt.ItemIsDropEnabled
        else:
            flags &= ~Qt.ItemIsDropEnabled
        item.setFlags(flags)
        return item

    def _build_node(self, node, parent_item, selected):
        merged = self._collapse_chain(node)
        if merged is not None:
            end, mods = merged
            item = self._new_item(parent_item, end)
            item.setData(0, Qt.UserRole, end.id)   # selection -> wrapped
            item.setData(0, ROLE_ROOT, node.id)    # structural -> chain
            item.setData(0, ROLE_CHAIN,
                         [m.id for m in mods] + [end.id])
            item.setData(0, ROLE_BADGES, self._badges(mods))
            self._decorate(item, end)
            # a wrapped container still shows its children one level down
            if end.is_container():
                if self._expand_state.get(end.id, end.type != "variables"):
                    item.setExpanded(True)
                for child in end.children:
                    self._build_node(child, item, selected)
            if end.id in selected or node.id in selected:
                item.setSelected(True)
            return
        # a normal row, recursing into its children
        item = self._new_item(parent_item, node)
        item.setData(0, Qt.UserRole, node.id)
        self._decorate(item, node)
        if node.is_container():
            default_open = node.type != "variables"
            if self._expand_state.get(node.id, default_open):
                item.setExpanded(True)
        if node.id in selected:
            item.setSelected(True)
        for child in node.children:
            self._build_node(child, item, selected)

    @staticmethod
    def _badges(mods):
        """Badge specs for a merged chain's modifiers (outermost first)."""
        out = []
        for m in mods:
            if m.type == "color":
                out.append(("color", str(m.params.get("color", "#888"))))
            else:
                out.append(("icon", BADGE_ICON.get(m.type, "mdi.cog")))
        return out

    def _model_visible(self, node):
        """True only if *node* and every ancestor is visible — hiding a
        parent effectively hides the whole subtree below it."""
        n = node
        while n is not None:
            if not n.visible:
                return False
            n = n.parent
        return True

    def _decorate(self, item, node):
        from .style import tokens
        dark = tokens().get("dark")
        item.setIcon(0, icons.icon(NODE_TYPES[node.type]["icon"]))
        own_hidden = not node.visible                 # explicitly hidden
        eff_hidden = not self._model_visible(node)    # or a parent is
        # keep the row text clean (so renaming isn't polluted); the
        # "(hidden)" tag on the explicitly-hidden node is painted by the
        # delegate from ROLE_TAG
        item.setText(0, node.name)
        item.setData(0, ROLE_TAG, own_hidden)
        # dim + italic if hidden by itself OR by an ancestor
        font = item.font(0)
        font.setItalic(eff_hidden)
        item.setFont(0, font)
        # an error on any node of a merged chain reddens the row
        chain = item.data(0, ROLE_CHAIN) or [node.id]
        error = next((self.errors[i] for i in chain if i in self.errors),
                     None)
        label = NODE_TYPES[node.type]["label"]
        if error:
            color = ERROR_COLOR_DARK if dark else ERROR_COLOR
            item.setForeground(0, QBrush(QColor(color)))
            item.setToolTip(0, f"⚠ {error}")
        elif eff_hidden:
            color = HIDDEN_COLOR_DARK if dark else HIDDEN_COLOR
            item.setForeground(0, QBrush(QColor(color)))
            item.setToolTip(0, f"{label} — hidden (Space to show)"
                            if own_hidden
                            else f"{label} — hidden by a parent")
        elif node.type == "assign":
            color = VAR_COLOR_DARK if dark else VAR_COLOR
            item.setForeground(0, QBrush(QColor(color)))
            item.setToolTip(0, "Variable — also editable in the "
                               "Variables sheet")
        else:
            item.setData(0, Qt.ForegroundRole, None)
            item.setToolTip(0, label)

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
            # re-decorate the whole subtree: hiding a node dims every row
            # below it, so its descendants must refresh too
            self._decorate_subtree(item)
            self._updating = False

    def _decorate_subtree(self, item):
        node = self.node_of(item)
        if node is not None:
            # always redraw with the row's primary node (a merged row
            # shows its wrapped object, even when a modifier changed)
            self._decorate(item, node)
            root = self._root_of(item)
            merged = self._collapse_chain(root) if root is not None \
                else None
            if merged is not None:
                item.setData(0, ROLE_BADGES, self._badges(merged[1]))
        for i in range(item.childCount()):
            self._decorate_subtree(item.child(i))

    def _item_changed(self, item, column):
        # only rename now — visibility is toggled via Space / context menu.
        # Read the edit-role name (clean of the "(hidden)" display tag).
        if self._updating or column != 0:
            return
        node = self.node_of(item)
        if node is None:
            return
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
        """Structural roots for the selection, minus any whose ancestor
        is also selected — the whole decorated part for a merged row, so
        cut/copy/delete/group act on the entire chain."""
        nodes = self.selected_roots()
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
        elif key == Qt.Key_Space:
            self._toggle_visibility(self.selected_nodes())
        else:
            super().keyPressEvent(event)

    def _toggle_visibility(self, nodes):
        """Show/hide the given objects — the whole selection flips to the
        opposite of the first one's state, so a mixed selection lands in
        sync."""
        if not nodes:
            return
        target = not nodes[0].visible
        for node in nodes:
            self.model.set_visible(node, target)

    # ------------------------------------------------------ guide lines
    def drawBranches(self, painter, rect, index):
        """Draw faint connecting lines down the indentation so deep trees
        read clearly — a vertical line per continuing ancestor and an
        L/T connector into each row."""
        item = self.itemFromIndex(index)
        if item is None:
            super().drawBranches(painter, rect, index)
            return
        # for the item and each ancestor: does it have a sibling below?
        cont = []
        cur = item
        while cur is not None:
            parent = cur.parent() or self.invisibleRootItem()
            cont.append(parent.indexOfChild(cur)
                        < parent.childCount() - 1)
            cur = cur.parent()
        cont.reverse()                         # top ancestor .. this item
        depth = len(cont) - 1
        indent = self.indentation()
        from .style import tokens
        pen = QPen(QColor("#5b6168" if tokens().get("dark")
                          else "#ccd0d6"))
        pen.setWidthF(1.0)
        painter.save()
        painter.setPen(pen)
        top, bottom = rect.top(), rect.bottom()
        mid = (top + bottom) // 2
        base = rect.left()
        for c in range(depth):                 # ancestor continuation lines
            if cont[c]:
                x = base + c * indent + indent // 2
                painter.drawLine(x, top, x, bottom)
        xc = rect.right() - indent // 2         # this row's own column
        painter.drawLine(xc, top, xc, bottom if cont[depth] else mid)
        painter.drawLine(xc, mid, rect.right(), mid)
        painter.restore()
        super().drawBranches(painter, rect, index)   # expand arrow on top

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
        moving = self.selected_roots()         # move whole decorated parts
        fallback = self._drop_container()
        target_item = self.itemAt(event.pos())
        into = self.node_of(target_item)       # drop INTO this container
        beside = self._root_of(target_item) or fallback   # or reorder by it
        pos = self.dropIndicatorPosition()
        if pos == QAbstractItemView.OnItem \
                and (into is None or not into.is_container()):
            pos = QAbstractItemView.BelowItem
        event.setDropAction(Qt.IgnoreAction)   # we mutate the model
        event.accept()
        for node in moving:
            if pos == QAbstractItemView.OnItem:
                self.model.move_node(node, into)
            elif beside is not None and beside.parent is not None:
                index = beside.index() + \
                    (1 if pos == QAbstractItemView.BelowItem else 0)
                self.model.move_node(node, beside.parent, index)
            else:
                self.model.move_node(node, fallback)

    # --------------------------------------------------- context menu
    def _context_menu(self, pos):
        nodes = self.selected_nodes()          # geometry (hide/colour)
        roots = self._top_level_selection()    # whole parts (structural)
        menu = QMenu(self)
        if nodes and self.IS_MASTERS:
            self._masters_menu(menu, nodes, roots)
        elif nodes:
            self._objects_menu(menu, nodes, roots)
        else:
            menu.addAction(icons.icon("mdi.content-paste"),
                           "Paste\tCtrl+V", self.paste_clipboard)
            if self.IS_MASTERS:
                menu.addAction(icons.icon("mdi.plus"), "New master",
                               lambda: self.select_nodes(
                                   [self.model.new_master()]))
        if menu.actions():
            menu.exec_(self.viewport().mapToGlobal(pos))

    def _modifiers_menu(self, menu):
        """For a single merged row, a submenu to jump to each wrapped
        modifier's properties (colour, transform)."""
        items = self.selectedItems()
        if len(items) != 1:
            return
        chain = items[0].data(0, ROLE_CHAIN)
        mods = [self.model.find(i) for i in (chain or [])[:-1]]
        mods = [m for m in mods if m is not None]
        if not mods:
            return
        sub = menu.addMenu(icons.icon("mdi.tune-variant"), "Modifiers")
        for m in mods:
            sub.addAction(
                icons.icon(NODE_TYPES[m.type]["icon"]),
                f"{NODE_TYPES[m.type]['label']} — {m.name}",
                lambda _=False, node=m: self.selection_changed.emit([node]))

    def _masters_menu(self, menu, nodes, roots):
        """Context menu inside the Masters tab."""
        menu.addAction(
            icons.icon("mdi.link-variant"), "Add to Scene (Linked copy)",
            lambda: [self.model.instance_master(n) for n in roots])
        menu.addAction(icons.icon("mdi.plus"), "New master",
                       lambda: self.select_nodes(
                           [self.model.new_master()]))
        menu.addSeparator()
        menu.addAction(icons.icon("mdi.palette-outline"),
                       "Color...", lambda: self._pick_color(nodes))
        if len(nodes) == 1:
            menu.addAction(icons.icon("mdi.rename-box"), "Rename",
                           lambda: self.editItem(self.selectedItems()[0], 0))
        menu.addAction(icons.icon("mdi.content-duplicate"), "Duplicate",
                       lambda: [self.model.duplicate(n) for n in roots])
        menu.addSeparator()
        menu.addAction(icons.icon("mdi.delete-outline"), "Delete",
                       lambda: [self.model.remove_node(n) for n in roots])

    def _objects_menu(self, menu, nodes, roots):
        hidden = [n for n in nodes if not n.visible]
        menu.addAction(
            icons.icon("mdi.eye-outline" if hidden
                       else "mdi.eye-off-outline"),
            "Show" if hidden else "Hide",
            lambda: [self.model.set_visible(n, bool(hidden))
                     for n in nodes])
        self._modifiers_menu(menu)
        menu.addSeparator()
        apply_menu = menu.addMenu(icons.icon("mdi.auto-fix"), "Apply")
        for op in APPLY_OPS:
            apply_menu.addAction(
                icons.icon(NODE_TYPES[op]["icon"]),
                NODE_TYPES[op]["label"],
                lambda _=False, o=op: self.model.wrap_nodes(roots, o))
        apply_menu.addSeparator()
        apply_menu.addAction(
            icons.icon("mdi.blur"), "Round edges (3D)",
            lambda: self.model.round_edges(roots))
        menu.addAction(icons.icon("mdi.palette-outline"),
                       "Color...", lambda: self._pick_color(nodes))
        menu.addAction(icons.icon("mdi.group"), "Group\tCtrl+G",
                       lambda: self.model.group_nodes(roots))
        containers = [n for n in roots if n.is_container()]
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
                                             for n in roots])
        if len(roots) == 1:
            menu.addAction(
                icons.icon("mdi.link-variant"),
                "Linked copy (updates with master)",
                lambda: self.model.add_linked_copy(roots[0]))
        promotable = [n for n in roots if n.type not in
                      ("assign", "variables", "masters", "reference")]
        if promotable:
            menu.addAction(
                icons.icon("mdi.folder-star-outline"),
                "Make Master (moves to Masters tab)",
                lambda: [self.model.make_master(n)
                         for n in promotable])
        menu.addSeparator()
        menu.addAction(icons.icon("mdi.delete-outline"), "Delete",
                       lambda: [self.model.remove_node(n)
                                for n in roots])


class MastersTree(ObjectTree):
    """The Masters store as its own tree: it roots at the masters group
    (created on demand) and lists only the master definitions, so the
    Objects tab stays uncluttered. Masters render in the scene only
    through Linked copies."""

    IS_MASTERS = True

    def _top_nodes(self):
        group = self.model.masters_group()
        return list(group.children) if group else []

    def _drop_container(self):
        return self.model.masters_group(create=True)


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


class _LineNumberArea(QWidget):
    """The gutter that paints line numbers next to the code."""

    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.editor.paint_line_numbers(event)


class CodeView(QPlainTextEdit):
    """Editable view of the OpenSCAD program with a line-number gutter
    and text-editor conveniences (Tab/Shift+Tab indent, the toolbar's
    cut/copy/paste/undo/redo). Line highlights show the selected
    object's lines in the accent and broken lines in red. Edits take
    effect only when "Apply code" re-parses the text into the tree."""

    #: spaces inserted per Tab / indent step.
    INDENT = "    "

    def __init__(self, parent=None):
        super().__init__(parent)
        font = QFont("Consolas")
        font.setStyleHint(QFont.Monospace)
        font.setPointSize(10)
        self.setFont(font)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setTabStopDistance(4 * self.fontMetrics().horizontalAdvance(" "))
        self._selected_ranges = []
        self._error_ranges = []
        # line-number gutter
        self._gutter = _LineNumberArea(self)
        self.blockCountChanged.connect(self._update_gutter_width)
        self.updateRequest.connect(self._update_gutter)
        self._update_gutter_width(0)
        self.refresh_theme()

    # ----------------------------------------------------- line numbers
    def line_number_area_width(self):
        digits = len(str(max(1, self.blockCount())))
        return 12 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_gutter_width(self, _count):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_gutter(self, rect, dy):
        if dy:
            self._gutter.scroll(0, dy)
        else:
            self._gutter.update(0, rect.y(), self._gutter.width(),
                                rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_gutter_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._gutter.setGeometry(QRect(cr.left(), cr.top(),
                                       self.line_number_area_width(),
                                       cr.height()))

    def paint_line_numbers(self, event):
        from .style import tokens
        t = tokens()
        painter = QPainter(self._gutter)
        bg = QColor(t.get("chrome", "#f0f0f0"))
        painter.fillRect(event.rect(), bg)
        pen = QColor("#7f848e" if t.get("dark") else "#9aa0a6")
        block = self.firstVisibleBlock()
        num = block.blockNumber()
        top = round(self.blockBoundingGeometry(block)
                    .translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        h = self.fontMetrics().height()
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(pen)
                painter.drawText(0, top, self._gutter.width() - 5, h,
                                 Qt.AlignRight, str(num + 1))
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            num += 1

    # ------------------------------------------------------ indentation
    def indent_selection(self):
        self._shift_lines(1)

    def dedent_selection(self):
        self._shift_lines(-1)

    def _shift_lines(self, direction):
        doc = self.document()
        cur = self.textCursor()
        start, end = cur.selectionStart(), cur.selectionEnd()
        first = doc.findBlock(start).blockNumber()
        last = doc.findBlock(max(end - 1, start)).blockNumber()
        cur.beginEditBlock()
        for bn in range(first, last + 1):
            block = doc.findBlockByNumber(bn)
            edit = QTextCursor(block)
            edit.movePosition(QTextCursor.StartOfBlock)
            if direction > 0:
                edit.insertText(self.INDENT)
            else:
                text = block.text()
                for _ in range(len(self.INDENT)):
                    if block.text().startswith(" "):
                        edit.deleteChar()
                    elif block.text().startswith("\t"):
                        edit.deleteChar()
                        break
                    else:
                        break
        cur.endEditBlock()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Backtab:
            self.dedent_selection()
            return
        if event.key() == Qt.Key_Tab:
            if self.textCursor().hasSelection():
                self.indent_selection()
            else:
                self.insertPlainText(self.INDENT)
            return
        super().keyPressEvent(event)

    def refresh_theme(self):
        from .style import tokens
        self._highlighter = ScadHighlighter(self.document(), tokens())
        self._gutter.update()
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

        # Masters tab: the reusable-definition store as its own tree, with
        # buttons to create one and drop a Linked copy into the scene
        self.masters_tree = MastersTree(model)
        masters_tab = QWidget()
        mbox = QVBoxLayout(masters_tab)
        mbox.setContentsMargins(4, 4, 4, 0)
        mbox.setSpacing(4)
        mrow = QHBoxLayout()
        new_master = QPushButton(icons.icon("mdi.plus"), " New")
        new_master.setToolTip("Create a new empty master")
        new_master.clicked.connect(
            lambda: self.masters_tree.select_nodes(
                [self.model.new_master()]))
        add_scene = QPushButton(icons.icon("mdi.link-variant"),
                                " Add to Scene")
        add_scene.setToolTip(
            "Add a Linked copy of the selected master to the scene")
        add_scene.clicked.connect(self._instance_selected_masters)
        mrow.addWidget(new_master)
        mrow.addWidget(add_scene)
        mrow.addStretch()
        mbox.addLayout(mrow)
        mbox.addWidget(self.masters_tree)

        # Code tab: a text-editor toolbar + the editable program + an
        # Apply button that parses it back into the object tree
        code_tab = QWidget()
        cbox = QVBoxLayout(code_tab)
        cbox.setContentsMargins(0, 0, 0, 0)
        cbox.setSpacing(4)
        cbox.addWidget(self._build_code_toolbar())
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
        self.addTab(masters_tab, icons.icon("mdi.folder-star-outline"),
                    "Masters")
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

    def _build_code_toolbar(self) -> QToolBar:
        """A text-editor toolbar for the Code tab: undo/redo, cut/copy/
        paste and indent/dedent, acting on the code editor."""
        tb = QToolBar("Code")
        tb.setIconSize(QSize(18, 18))
        c = self.code
        tb.addAction(icons.icon("mdi.undo"), "Undo (Ctrl+Z)", c.undo)
        tb.addAction(icons.icon("mdi.redo"), "Redo (Ctrl+Y)", c.redo)
        tb.addSeparator()
        tb.addAction(icons.icon("mdi.content-cut"), "Cut (Ctrl+X)", c.cut)
        tb.addAction(icons.icon("mdi.content-copy"), "Copy (Ctrl+C)",
                     c.copy)
        tb.addAction(icons.icon("mdi.content-paste"), "Paste (Ctrl+V)",
                     c.paste)
        tb.addSeparator()
        tb.addAction(icons.icon("mdi.format-indent-increase"),
                     "Indent (Tab)", c.indent_selection)
        tb.addAction(icons.icon("mdi.format-indent-decrease"),
                     "Dedent (Shift+Tab)", c.dedent_selection)
        return tb

    def _instance_selected_masters(self):
        """Drop a Linked copy of each selected master into the scene."""
        for node in self.masters_tree._top_level_selection():
            self.model.instance_master(node)

    def refresh_theme(self):
        self.code.refresh_theme()
        self.tree.set_errors(self.tree.errors)

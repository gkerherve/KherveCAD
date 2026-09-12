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

from PyQt5.QtCore import (QEvent, QRect, QRectF, QSize, Qt,
                          pyqtSignal)
from PyQt5.QtGui import (QBrush, QColor, QFont, QIcon, QKeySequence,
                         QPainter, QPen, QPixmap, QSyntaxHighlighter,
                         QTextCharFormat, QTextCursor)
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

# item data role beyond the primary node id (Qt.UserRole)
ROLE_TAG = Qt.UserRole + 1         # True -> paint a "(hidden)" tag
ROLE_PLACEMENT = Qt.UserRole + 2   # True -> synthetic Position/Rotation
#                                    row under a part (selects the part)

CLIPBOARD_FORMAT = "kcad-clipboard"


def _swatch_icon(color: str, size: int = 12) -> QIcon:
    """A small filled square of *color* — the icon for a part's Color
    row, so the tree shows the colour itself rather than a generic
    palette glyph. Falls back to the palette icon for an unusable
    value, so a typed colour never leaves a blank row."""
    value = QColor(color)
    if not value.isValid():
        return icons.icon(NODE_TYPES["color"]["icon"])
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(value))
        painter.setPen(QPen(QColor(0, 0, 0, 90)))
        # QRectF, not six floats: PyQt has no float x/y overload, and
        # the TypeError would escape mid-paint and take the app down
        painter.drawRoundedRect(
            QRectF(0.5, 0.5, size - 1.0, size - 1.0), 2.5, 2.5)
    finally:
        painter.end()
    return QIcon(pixmap)


class _RowDelegate(QStyledItemDelegate):
    """Paints a faint '(hidden)' tag after an explicitly-hidden object's
    name (kept out of the item text so renaming stays clean)."""

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        if not index.data(ROLE_TAG):
            return
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


#: operations offered by the "Apply" context submenu.
APPLY_OPS = ["linear_extrude", "rotate_extrude", "offset", "translate",
             "rotate", "scale", "mirror", "difference", "intersection",
             "hull", "minkowski", "for_loop", "while_loop", "if_else"]


class ObjectTree(QTreeWidget):
    """The work tree: one item per CadNode, checkbox = visibility."""

    selection_changed = pyqtSignal(list)     # list of CadNode
    #: an Object was double-clicked / "opened" — edit it in the Object
    #: tab (carries the component CadNode).
    open_component = pyqtSignal(object)
    #: "Add anchor" was chosen — the main window starts a face/edge
    #: pick in the 3D view (carries the component CadNode).
    pick_anchor = pyqtSignal(object)
    #: start the two-click Snap tool (pick a face on each of two
    #: Objects in the 3D view).
    snap_objects = pyqtSignal()

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
        self.itemDoubleClicked.connect(self._double_clicked)
        model.structure_changed.connect(self.rebuild)
        model.node_changed.connect(self._refresh_node)
        self.rebuild()

    def _double_clicked(self, item, _col):
        """Double-click opens an Object for editing (Object tab);
        everything else starts an in-place rename."""
        if item.data(0, ROLE_PLACEMENT):
            return          # placement rows are edited via Properties
        node = self.node_of(item)
        if node is not None and node.type == "component" \
                and not self.IS_MASTERS:
            self.open_component.emit(node)
        else:
            self.editItem(item, 0)

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
        # a part and its placement rows share the node id — dedupe so
        # selecting both never lists the part twice
        seen, out = set(), []
        for item in self.selectedItems():
            node = self.node_of(item)
            if node is not None and node.id not in seen:
                seen.add(node.id)
                out.append(node)
        return out

    def _top_nodes(self):
        """The nodes shown at the top level of this tree — the document
        root's children with the Masters store and the Object
        *definitions* (hidden components — they live in the Object tab
        and appear here only through their instances) filtered out."""
        return [c for c in self.model.root.children
                if c.type != "masters"
                and not (c.type == "component" and not c.visible)]

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

    def _is_opaque(self, node):
        """A node shown as one solid row, its internals hidden — an
        Object (component) in the Main assembly: you see the part, not
        how it is built (edit that in the Object tab). Overridden off
        in the Object tab's own tree."""
        return node.type == "component"

    #: node types whose placement (x/y/z/rx/ry/rz params — what a mate
    #: or drag writes) shows as Position/Rotation rows in the tree.
    _PLACED_TYPES = ("component", "reference", "union")

    @staticmethod
    def _placement_texts(node):
        """``[(text, icon node type, kind)]`` describing what *node*
        carries as a part: its non-zero placement — the translate/
        rotate that snapping, dragging or Properties wrote, mirrored as
        tree rows so the tree matches the ``translate(...) rotate(...)``
        the code emits — and its own colour, which the part carries the
        same way and which `color(...)` emits alongside them."""
        def fmt(value):
            if isinstance(value, str):
                return value.strip() or "0"
            try:
                return f"{float(value):g}"
            except (TypeError, ValueError):
                return str(value)

        def nonzero(value):
            try:
                return float(value) != 0.0
            except (TypeError, ValueError):
                return bool(str(value).strip())

        out = []
        for label, keys, icon_type in (
                ("Position", ("x", "y", "z"), "translate"),
                ("Rotation", ("rx", "ry", "rz"), "rotate")):
            vals = [node.params.get(k, 0.0) for k in keys]
            if any(nonzero(v) for v in vals):
                out.append((f"{label} ({', '.join(fmt(v) for v in vals)})",
                            icon_type, "placement"))
        color = str(node.params.get("color", "")).strip()
        if color:
            try:
                opacity = float(node.params.get("alpha", 1.0))
            except (TypeError, ValueError):
                opacity = 1.0
            text = f"Color ({color}"
            if opacity < 1.0:
                text += f", {opacity:g} opacity"
            out.append((text + ")", "color", "color"))
        return out

    def _insert_placement_rows(self, item, node):
        """Add *node*'s Position/Rotation rows as its first children.
        They carry the part's node id (clicking selects the part) and
        are edited via Properties / Attach, never in place."""
        mate = node.params.get("mate") \
            if node.type in self._PLACED_TYPES else None
        mated = isinstance(mate, dict) and mate.get("parent")
        for index, (text, icon_type, kind) in enumerate(
                self._placement_texts(node)):
            row = QTreeWidgetItem()
            row.setText(0, text)
            if kind == "color":
                row.setIcon(0, _swatch_icon(
                    str(node.params.get("color", ""))))
                row.setToolTip(0, "The part's colour — change it in "
                                  "Properties or right-click > Colour")
            else:
                row.setIcon(0, icons.icon(NODE_TYPES[icon_type]["icon"]))
                row.setToolTip(0, (
                    f"Solved from the mate to {mate['parent']} — adjust "
                    f"via Attach / snap to..." if mated else
                    "The part's placement — edit x/y/z and rotation in "
                    "Properties"))
            row.setData(0, Qt.UserRole, node.id)
            row.setData(0, ROLE_PLACEMENT, True)
            row.setFlags((row.flags() | Qt.ItemNeverHasChildren)
                         & ~(Qt.ItemIsEditable | Qt.ItemIsDropEnabled
                             | Qt.ItemIsDragEnabled
                             | Qt.ItemIsUserCheckable))
            item.insertChild(index, row)

    def _refresh_placement_rows(self, item, node):
        """Re-sync the Position/Rotation rows after the node moved
        (a mate re-solve, a drag, a Properties edit)."""
        i = 0
        while i < item.childCount():
            if item.child(i).data(0, ROLE_PLACEMENT):
                item.takeChild(i)
            else:
                i += 1
        self._insert_placement_rows(item, node)

    def _build_node(self, node, parent_item, selected):
        """One row per node — colour/translate/rotate wrappers show as
        their own rows, so the whole structure is visible. An opaque
        node (an assembly Object) is a single leaf: its construction
        tree stays in the Object tab, but its assembly placement (the
        translate/rotate a snap wrote) shows as child rows."""
        item = self._new_item(parent_item, node)
        item.setData(0, Qt.UserRole, node.id)
        self._decorate(item, node)
        if node.type in self._PLACED_TYPES:
            self._insert_placement_rows(item, node)
        if self._is_opaque(node) or node.type == "reference":
            if item.childCount() and self._expand_state.get(node.id,
                                                            True):
                item.setExpanded(True)
            if node.id in selected:
                item.setSelected(True)
            return
        if node.is_container():
            default_open = node.type != "variables"
            if self._expand_state.get(node.id, default_open):
                item.setExpanded(True)
        if node.id in selected:
            item.setSelected(True)
        for child in node.children:
            self._build_node(child, item, selected)

    def _visibility_root(self):
        """Ancestor at which the effective-visibility walk stops
        (exclusive). None = walk to the document root. The Object tab
        overrides this with the active Object, whose own hidden-in-Main
        flag is a definition detail that must not grey its contents."""
        return None

    def _model_visible(self, node):
        """True only if *node* and every ancestor up to (but not
        including) `_visibility_root()` is visible — hiding a parent
        effectively hides the whole subtree below it."""
        stop = self._visibility_root()
        n = node
        while n is not None and n is not stop:
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
        error = self.errors.get(node.id)
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
            mate = node.params.get("mate") \
                if node.type == "component" else None
            if isinstance(mate, dict) and mate.get("parent"):
                item.setToolTip(
                    0, f"{label} — attached to {mate['parent']} "
                       f"({mate.get('parent_anchor', '')})")
            else:
                item.setToolTip(0, label)

    def set_errors(self, errors: dict):
        """Paint nodes with problems red (tooltip = the message)."""
        self.errors = errors or {}
        self._updating = True
        for item in self._all_items():
            if item.data(0, ROLE_PLACEMENT):
                continue                 # synthetic Position/Rotation
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
            if node.type in self._PLACED_TYPES:
                # a mate re-solve / drag / Properties edit moved it:
                # keep the Position/Rotation rows in sync
                self._refresh_placement_rows(item, node)
            self._updating = False

    def _decorate_subtree(self, item):
        if item.data(0, ROLE_PLACEMENT):
            return          # synthetic rows keep their own text
        node = self.node_of(item)
        if node is not None:
            self._decorate(item, node)
        for i in range(item.childCount()):
            self._decorate_subtree(item.child(i))

    def _item_changed(self, item, column):
        # only rename now — visibility is toggled via Space / context menu
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
        parent, index = self._drop_container(), None
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
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():        # a file drag -> open it
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():        # forward a dropped file
            win = self.window()
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if path and hasattr(win, "open_any"):
                    win.open_any(path)
                    break
            event.acceptProposedAction()
            return
        moving = self.selected_nodes()
        fallback = self._drop_container()
        target_item = self.itemAt(event.pos())
        target = self.node_of(target_item) or fallback
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
                self.model.move_node(node, fallback)

    #: the Main tree offers "Insert Object" (assembly instances);
    #: the Object tab's tree and the Masters tree do not.
    SHOWS_INSERT_OBJECT = True
    #: the Object tab's tree lets the groups building a part be snapped
    #: together (secondary anchors); the Main tree does not.
    ALLOWS_GROUP_MATES = False

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
            self._insert_object_menu(menu)
            menu.addAction(icons.icon("mdi.content-paste"),
                           "Paste\tCtrl+V", self.paste_clipboard)
            if self.IS_MASTERS:
                menu.addAction(icons.icon("mdi.plus"), "New master",
                               lambda: self.select_nodes(
                                   [self.model.new_master()]))
        if menu.actions():
            menu.exec_(self.viewport().mapToGlobal(pos))

    def _insert_object_menu(self, menu):
        """"Insert Object" — place an instance of a defined Object into
        the Main assembly (the part/assembly model: definitions live in
        the Object tab, the assembly calls the ones it wants)."""
        if self.IS_MASTERS or not self.SHOWS_INSERT_OBJECT:
            return
        comps = self.model.components()
        if not comps:
            return
        sub = menu.addMenu(icons.icon("mdi.package-variant-plus"),
                           "Insert Object")
        for comp in comps:
            sub.addAction(
                icons.icon("mdi.package-variant-closed"), comp.name,
                lambda _=False, c=comp:
                    self.select_nodes([self.model.add_instance(c)]))

    def _part_menu(self, menu, part):
        """Assembly-part actions for one Object or instance: edit its
        definition in the Object tab, anchors, and mates."""
        from .mates import AttachDialog, definition_of, detach, mate_of
        definition = definition_of(self.model, part) or part
        menu.addAction(
            icons.icon("mdi.pencil-box-outline"), "Edit in Object tab",
            lambda: self.open_component.emit(definition))
        if part.type == "component":
            self._anchor_menu(menu, part)
        else:
            self._instance_anchor_menu(menu, part, definition)
        menu.addAction(
            icons.icon("mdi.magnet-on"),
            "Snap by clicking faces\tJ", self.snap_objects.emit)
        menu.addAction(
            icons.icon("mdi.magnet"), "Attach / snap to...",
            lambda: AttachDialog(self.model, part, self).exec_())
        mate = mate_of(part)
        if mate is not None:
            menu.addAction(
                icons.icon("mdi.link-off"),
                f"Detach from {mate['parent']}",
                lambda: detach(self.model, part))
        menu.addSeparator()

    def _group_part_menu(self, menu, group):
        """Snap / anchor / attach a group (union) while building an
        Object — the "secondary" anchors that arrange sub-parts inside
        a definition, distinct from the assembly anchors on Objects."""
        from .mates import AttachDialog, detach, mate_of
        sub = menu.addMenu(icons.icon("mdi.anchor"), "Anchors")
        sub.addAction(
            icons.icon("mdi.target"),
            "Add anchor (pick face/edge in 3D)...",
            lambda: self.pick_anchor.emit(group))
        from . import anchors as anc
        users = anc.user_anchors(group)
        if users:
            remove_menu = sub.addMenu(icons.icon("mdi.delete-outline"),
                                      "Remove anchor")
            for anchor in users:
                remove_menu.addAction(
                    anchor["name"],
                    lambda _=False, n=anchor["name"]:
                        anc.remove_user_anchor(self.model, group, n))
        menu.addAction(
            icons.icon("mdi.magnet-on"),
            "Snap by clicking faces\tJ", self.snap_objects.emit)
        menu.addAction(
            icons.icon("mdi.magnet"), "Attach / snap to...",
            lambda: AttachDialog(self.model, group, self).exec_())
        mate = mate_of(group)
        if mate is not None:
            menu.addAction(
                icons.icon("mdi.link-off"),
                f"Detach from {mate['parent']}",
                lambda: detach(self.model, group))
        menu.addSeparator()

    def _instance_anchor_menu(self, menu, part, definition):
        """Anchors reachable from an instance: picked anchors live on
        the *definition*, so every instance of the Object shares
        them."""
        from . import anchors as anc
        sub = menu.addMenu(icons.icon("mdi.anchor"), "Anchors")
        sub.addAction(
            icons.icon("mdi.target"),
            "Add anchor (pick face/edge in 3D)...",
            lambda: self.pick_anchor.emit(part))
        users = anc.user_anchors(definition)
        if users:
            remove_menu = sub.addMenu(icons.icon("mdi.delete-outline"),
                                      "Remove anchor")
            for anchor in users:
                remove_menu.addAction(
                    anchor["name"],
                    lambda _=False, n=anchor["name"]:
                        anc.remove_user_anchor(self.model, definition,
                                               n))

    def _anchor_menu(self, menu, comp):
        """The Anchors submenu of one Object: add a picked anchor,
        re-base the origin onto any anchor, remove picked ones."""
        from . import anchors as anc
        sub = menu.addMenu(icons.icon("mdi.anchor"), "Anchors")
        sub.addAction(
            icons.icon("mdi.target"),
            "Add anchor (pick face/edge in 3D)...",
            lambda: self.pick_anchor.emit(comp))
        env = anc.doc_env(self.model)
        fn = self.model.effective_fn()
        origin_menu = sub.addMenu(icons.icon("mdi.axis-arrow"),
                                  "Set origin at")
        for anchor in anc.auto_anchors(comp, env=env, fn=fn):
            if anchor["kind"] in ("face", "corner"):
                origin_menu.addAction(
                    anchor["name"],
                    lambda _=False, p=list(anchor["pos"]):
                        anc.set_origin(self.model, comp, p, env))
        users = anc.user_anchors(comp)
        for anchor in users:
            origin_menu.addAction(
                f"{anchor['name']} (picked)",
                lambda _=False, p=list(anchor["pos"]):
                    anc.set_origin(self.model, comp, p, env))
        if users:
            remove_menu = sub.addMenu(icons.icon("mdi.delete-outline"),
                                      "Remove anchor")
            for anchor in users:
                remove_menu.addAction(
                    anchor["name"],
                    lambda _=False, n=anchor["name"]:
                        anc.remove_user_anchor(self.model, comp, n))

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
        from .mates import definition_of
        parts_sel = [n for n in roots
                     if n.type == "component"
                     or (n.type == "reference"
                         and definition_of(self.model, n) is not None)]
        if len(parts_sel) == 1:
            self._part_menu(menu, parts_sel[0])
        elif self.ALLOWS_GROUP_MATES and len(roots) == 1 \
                and roots[0].type == "union":
            self._group_part_menu(menu, roots[0])
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
                lambda _=False, o=op: self.model.wrap_nodes(roots, o))
        apply_menu.addSeparator()
        apply_menu.addAction(
            icons.icon("mdi.blur"), "Round edges (3D)",
            lambda: self.model.round_edges(roots))
        fillet = roots[0] if len(roots) == 1 and roots[0].type == "fillet" \
            else (roots[0].parent if len(roots) == 1 and roots[0].parent
                  is not None and roots[0].parent.type == "fillet"
                  else None)
        win = self.window()
        if fillet is not None and hasattr(win, "start_fillet_pick"):
            menu.addAction(
                icons.icon("mdi.rounded-corner"), "Pick fillet edges...",
                lambda: win.start_fillet_pick(fillet))
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
        win = self.window()
        if hasattr(win, "view3d"):              # Analyse (analysis_dialog)
            from .analysis_dialog import open_analysis
            menu.addSeparator()
            menu.addAction(icons.icon("mdi.scale-balance"),
                           "Mass properties...",
                           lambda: open_analysis(win, "mass", roots))
            menu.addAction(icons.icon("mdi.printer-3d-nozzle-outline"),
                           "Check for 3D printing...",
                           lambda: open_analysis(win, "print", roots))
            menu.addAction(icons.icon("mdi.set-center"),
                           "Check interference...",
                           lambda: open_analysis(win, "interference",
                                                 roots))
            menu.addSeparator()
        if len(roots) == 1:
            menu.addAction(
                icons.icon("mdi.link-variant"),
                "Linked copy (updates with master)",
                lambda: self.model.add_linked_copy(roots[0]))
        promotable = [n for n in roots if n.type not in
                      ("assign", "variables", "masters", "reference")]
        objectable = [n for n in promotable if n.type != "component"]
        if objectable:
            menu.addAction(
                icons.icon("mdi.package-variant-closed"),
                "Make Object",
                lambda: [self.model.make_component(n)
                         for n in objectable])
        if promotable:
            menu.addAction(
                icons.icon("mdi.folder-star-outline"),
                "Make Master (moves to Masters tab)",
                lambda: [self.model.make_master(n)
                         for n in promotable])
        self._insert_object_menu(menu)
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
    sync when variables are changed elsewhere.

    Variables are **scoped**: the dropdown picks between the document's
    Global variables (outside every Object) and each Object's own —
    and it follows the Object tab's active Object automatically."""

    def __init__(self, model: DocumentModel, parent=None):
        super().__init__(parent)
        self.model = model
        self._updating = False
        self._rows = []
        self._scope_name = None                # None -> Global

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        from PyQt5.QtWidgets import QComboBox, QLabel
        scope_row = QHBoxLayout()
        scope_row.addWidget(QLabel("Scope:"))
        self.scope_combo = QComboBox()
        self.scope_combo.setToolTip(
            "Whose variables to show — the document's globals or one "
            "Object's own (module-local) variables")
        self.scope_combo.currentIndexChanged.connect(self._scope_picked)
        scope_row.addWidget(self.scope_combo, 1)
        layout.addLayout(scope_row)
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

        model.structure_changed.connect(self._structure_changed)
        model.node_changed.connect(self._node_changed)
        self._structure_changed()

    # ------------------------------------------------------------ scope
    def _structure_changed(self):
        self._sync_scopes()
        self.rebuild()

    def scope_node(self):
        """The Object whose variables are shown, or None for Global."""
        if self._scope_name is None:
            return None
        for comp in self.model.components():
            if comp.name == self._scope_name:
                return comp
        return None

    def set_scope(self, node):
        """Follow the Object tab: show *node*'s variables (or Global
        when *node* is None)."""
        name = node.name if node is not None else None
        if name != self._scope_name:
            self._scope_name = name
            self._sync_scopes()
            self.rebuild()

    def _sync_scopes(self):
        """Rebuild the scope dropdown; a vanished Object falls back to
        Global."""
        self._updating = True
        self.scope_combo.clear()
        self.scope_combo.addItem("Global (document)")
        index = 0
        for i, comp in enumerate(self.model.components(), start=1):
            self.scope_combo.addItem(
                icons.icon("mdi.package-variant-closed"), comp.name)
            if comp.name == self._scope_name:
                index = i
        if index == 0:
            self._scope_name = None
        self.scope_combo.setCurrentIndex(index)
        self._updating = False

    def _scope_picked(self, index):
        if self._updating:
            return
        self._scope_name = None if index <= 0 \
            else self.scope_combo.itemText(index)
        self.rebuild()

    def _assigns(self):
        scope = self.scope_node()
        if scope is not None:
            return [n for n in scope.walk() if n.type == "assign"]
        return self.model.global_assigns()

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
        # keep new variables in the variable block, ahead of geometry —
        # inside the scoped Object when one is selected
        if assigns:
            last = assigns[-1]
            last.parent.add(node, last.index() + 1)
        else:
            (self.scope_node() or self.model.root).add(node, 0)
        self.model.structure_changed.emit()

    def _remove(self):
        row = self.table.currentRow()
        if 0 <= row < len(self._rows):
            self.model.remove_node(self._rows[row])


class BuilderPanel(QTabWidget):
    """Main (assembly) + Object + Masters + Variables + Code tabs, kept
    in sync with the model.

    The **Main** tab is the whole document; the **Object** tab edits
    one Object (component) at a time; **Variables** is scoped to the
    active Object (or Global); **Code** can show the whole program or
    just the active Object's module.

    Also owns the error state: static validation runs on every change
    and OpenSCAD compiler errors are merged in by the main window;
    broken nodes turn red in the tree and their lines red in the
    code."""

    #: the Object tab's active Object changed (CadNode or None).
    active_component_changed = pyqtSignal(object)

    def __init__(self, model: DocumentModel, parent=None):
        super().__init__(parent)
        from .objecttab import ObjectTab       # here: avoids the cycle
        self.model = model
        self.tree = ObjectTree(model)
        self.object_tab = ObjectTab(model)
        self.code = CodeView()
        self._spans = {}
        self._engine_errors = {}
        self._selected_ids = []

        # Main tab: a common-segments toggle pinned above the tree
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
        from PyQt5.QtWidgets import QComboBox
        self.code_scope = QComboBox()
        self.code_scope.addItems(["Whole program", "Active object"])
        self.code_scope.setToolTip(
            "Show / apply the whole program, or only the active "
            "Object's module")
        self.code_scope.currentIndexChanged.connect(
            lambda _i: self.refresh_code())
        crow.addWidget(self.code_scope)
        crow.addStretch()
        self.apply_btn = QPushButton(icons.icon("mdi.check"),
                                     " Apply code")
        self.apply_btn.setToolTip(
            "Parse the edited program back into the object tree "
            "(replaces the document; Ctrl+Z to undo)")
        self.apply_btn.clicked.connect(self._apply_code)
        crow.addWidget(self.apply_btn)
        cbox.addLayout(crow)

        self._main_page = objects
        self.addTab(objects, icons.icon("mdi.file-tree"), "Main")
        self.addTab(self.object_tab,
                    icons.icon("mdi.package-variant-closed"), "Object")
        self.addTab(masters_tab, icons.icon("mdi.folder-star-outline"),
                    "Masters")
        self.addTab(self.variables, icons.icon("mdi.table"), "Variables")
        self.addTab(code_tab, icons.icon("mdi.code-braces"), "Code")
        self.tree.open_component.connect(self.open_component)
        self.object_tab.tree.open_component.connect(self.open_component)
        self.object_tab.active_changed.connect(self._active_changed)
        self.currentChanged.connect(self._tab_changed)
        model.structure_changed.connect(self.refresh_code)
        model.structure_changed.connect(self._sync_fn_ui)
        model.node_changed.connect(lambda _n: self.refresh_code())
        self.refresh_code()

    # --------------------------------------------------- active object
    def open_component(self, node):
        """Activate *node* in the Object tab and switch to it."""
        self.object_tab.set_active(node)
        self.setCurrentWidget(self.object_tab)

    def isolated_component(self):
        """The active Object while the Object tab is current — what
        the viewers isolate to. None otherwise."""
        if self.currentWidget() is self.object_tab:
            return self.object_tab.active_component()
        return None

    def active_tree(self):
        """The tree the user is working in: the Object tab's while that
        tab is current, else the Main assembly tree.

        Every command that acts on the *selection* — apply an
        operation, group/ungroup, delete, duplicate, the clipboard,
        reorder — must go through this. Reading the Main tree while the
        Object tab is up finds nothing selected, so the command
        silently did nothing (Difference in an Object appeared dead)."""
        if self.currentWidget() is self.object_tab:
            return self.object_tab.tree
        return self.tree

    def _tab_changed(self, index):
        """The Code tab shows whatever tree you last worked in: coming
        from Main it scopes to the whole program, coming from the
        Object tab it scopes to the active Object."""
        widget = self.widget(index)
        if widget is self._main_page:
            self._set_code_scope(0)
        elif widget is self.object_tab:
            self._set_code_scope(
                1 if self.object_tab.active_component() else 0)

    def _set_code_scope(self, index):
        if self.code_scope.currentIndex() != index:
            self.code_scope.blockSignals(True)
            self.code_scope.setCurrentIndex(index)
            self.code_scope.blockSignals(False)
            self.refresh_code()

    def _active_changed(self, node):
        """The Object tab's active Object changed: scope the Variables
        sheet (and, while the Object tab is current, the Code tab) to
        it, then tell the main window."""
        self.variables.set_scope(node)
        if node is None:
            self._set_code_scope(0)
        elif self.currentWidget() is self.object_tab:
            self._set_code_scope(1)
        self.refresh_code()
        self.active_component_changed.emit(node)

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

    def _code_component(self):
        """The Object the Code tab is scoped to, or None for the whole
        program."""
        if self.code_scope.currentIndex() == 1:
            return self.object_tab.active_component()
        return None

    def refresh_code(self):
        comp = self._code_component()
        code, self._spans = self.model.to_scad_map(only=comp) \
            if comp is not None else self.model.to_scad_map()
        self.code.set_code(code)
        self._refresh_errors()

    def _apply_code(self):
        """Parse the edited program back into the object tree. In
        "Active object" scope only that Object is replaced (plus any
        edited global variables); otherwise the whole document is.
        Only the supported subset survives; anything else is reported
        and skipped."""
        from .scadparse import parse_scad
        comp = self._code_component()
        try:
            root, warnings = parse_scad(self.code.toPlainText())
        except Exception as exc:
            QMessageBox.warning(self, "Apply code",
                                f"Could not parse the program:\n{exc}")
            return
        if comp is not None:
            if not self._apply_component_code(comp, root):
                return
        else:
            self.model.root = root
            self.model.group_variables()
            self.model.structure_changed.emit()   # regenerates + undoable
        if warnings:
            QMessageBox.information(
                self, "Apply code",
                "Applied, but some constructs were skipped:\n- "
                + "\n- ".join(warnings[:12])
                + ("\n…" if len(warnings) > 12 else ""))

    def _apply_component_code(self, comp, root) -> bool:
        """Swap the active Object for the one parsed from the scoped
        code and write edited globals back by name."""
        new_comps = [n for n in root.children if n.type == "component"]
        if len(new_comps) != 1:
            QMessageBox.warning(
                self, "Apply code",
                "Object scope expects exactly one Object (a "
                "zero-argument module plus its call). Switch the scope "
                "to 'Whole program' to replace the document.")
            return False
        by_var = {a.params.get("variable"): a
                  for a in self.model.global_assigns()}
        for assign in [n for n in root.children if n.type == "assign"]:
            var = assign.params.get("variable")
            target = by_var.get(var)
            if target is not None:
                target.params["value"] = assign.params.get("value", 0)
            else:
                self.model.root.add(
                    CadNode("assign", f"{var} =", dict(assign.params)),
                    0)
        new = new_comps[0]
        root.remove(new)
        parent, index = comp.parent, comp.index()
        parent.remove(comp)
        parent.add(new, index)
        self.object_tab.set_active(new)
        self.model.structure_changed.emit()
        return True

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

# KherveCAD — GPL-3.0-or-later. See LICENSE.
"""The **Work tree** tab — where the document's parts are, as folders.

The first tab of the browser (2026-11-03, the user: "a folder tree with
everything that is in there", so the user sees where they are going).
Assemblies and sub-assemblies (Objects made of other Objects) are
folders holding the parts they place; plain Objects are leaves. Buttons
create a new Object, sub-assembly or assembly (inside the selected
assembly when one is selected); a double-click opens an Object in the
Object tab.

The lists can be ARRANGED (2026-11-13, the user: "we should be able to
arrange the objects list"): drag a row onto another of the same list,
right-click ▸ Move Up / Move Down (Ctrl+Up / Ctrl+Down) or Sort A to Z /
Z to A. It is the document's own order that changes (`move_among`,
`sort_among`), so the Object drop-down, the Code tab and the saved file
follow, and one Ctrl+Z puts it back.
"""

import re

from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtWidgets import (QAbstractItemView, QHBoxLayout, QMenu,
                             QToolButton, QTreeWidget, QTreeWidgetItem,
                             QVBoxLayout, QWidget)

from . import icons, language
from .model import CadNode

ROLE = Qt.UserRole


def parts_in(node):
    """The Objects and instances directly under *node*, looking through
    groups, colours and transforms."""
    out = []
    for child in node.children:
        if child.type in ("component", "reference"):
            out.append(child)
        else:
            out.extend(parts_in(child))
    return out


#: role of the node the row stands for where it sits (the instance in
#: Main, the Object itself elsewhere) — what is moved
PLACE = Qt.UserRole + 1
#: the parts a list is arranged among: Objects and their instances
PARTS = ("component", "reference")


def _siblings(node):
    return [c for c in node.parent.children if c.type in PARTS] \
        if node.parent is not None else []


def move_among(model, node, delta):
    """Move *node* *delta* places among the Objects / instances of its
    parent (other nodes keep their places). True when it moved."""
    sibs = _siblings(node)
    if node not in sibs:
        return False
    k = sibs.index(node)
    j = max(0, min(len(sibs) - 1, k + delta))
    if j == k:
        return False
    return place_by(model, node, sibs[j], after=delta > 0)


def place_by(model, node, target, after=False):
    """Put *node* just before (or *after*) *target*, a sibling."""
    parent = node.parent
    if parent is None or target is node or target.parent is not parent:
        return False
    parent.children.remove(node)
    i = parent.children.index(target) + (1 if after else 0)
    parent.children.insert(i, node)
    model.structure_changed.emit()
    return True


def natural_key(name):
    """'Exercise 10' after 'Exercise 9' (numbers as numbers)."""
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r"(\d+)", name or "")]


def sort_among(model, parent, reverse=False, only=None):
    """Sort the Objects / instances of *parent* by name in the places
    they hold; *only* limits it to those nodes (a list's rows)."""
    slots = [i for i, c in enumerate(parent.children)
             if c.type in PARTS and (only is None or c in only)]
    nodes = [parent.children[i] for i in slots]
    ordered = sorted(nodes, key=lambda n: natural_key(n.name),
                     reverse=reverse)
    if ordered == nodes:
        return False
    for i, n in zip(slots, ordered):
        parent.children[i] = n
    model.structure_changed.emit()
    return True


class _ArrangeTree(QTreeWidget):
    """The rows drag onto rows of the same list; the document is
    reordered and the tree rebuilt from it."""

    def __init__(self, tab):
        super().__init__(tab)
        self.tab = tab
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)

    def dropEvent(self, event):
        dragged = self.currentItem()
        target = self.itemAt(event.pos())
        event.setDropAction(Qt.IgnoreAction)
        event.accept()                 # the document moves, not the rows
        node = self.tab.place_of(dragged)
        other = self.tab.place_of(target)
        if node is None or other is None or other is node or \
                other.parent is not node.parent:
            return
        pos = self.dropIndicatorPosition()
        after = pos == QAbstractItemView.BelowItem
        self.tab.arranged(node, place_by(self.tab.model, node, other,
                                         after=after))

    def keyPressEvent(self, event):
        if event.modifiers() & Qt.ControlModifier and \
                event.key() in (Qt.Key_Up, Qt.Key_Down):
            self.tab.move_current(-1 if event.key() == Qt.Key_Up else 1)
            return
        super().keyPressEvent(event)


class WorkTreeTab(QWidget):
    #: double-click on an Object: open it in the Object tab
    open_component = pyqtSignal(object)

    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 0)
        layout.setSpacing(4)
        row = QHBoxLayout()
        row.setSpacing(2)
        for text, glyph, tip, slot in (
                ("New Object", "mdi.package-variant-closed-plus",
                 "A new empty Object (a part), inside the selected "
                 "assembly if one is selected", self.new_object),
                ("New Sub-assembly", "mdi.folder-plus-outline",
                 "A new Object made of other Objects, inside the "
                 "selected assembly", self.new_subassembly),
                ("New Assembly", "mdi.folder-plus",
                 "A new top-level assembly in Main", self.new_assembly)):
            b = QToolButton()
            b.setText(language.tr(text))
            b.setIcon(icons.icon(glyph))
            b.setIconSize(QSize(18, 18))
            b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            b.setAutoRaise(True)
            b.setToolTip(language.tr(tip))
            b.clicked.connect(slot)
            row.addWidget(b)
        row.addStretch(1)
        layout.addLayout(row)
        self.tree = _ArrangeTree(self)
        self.tree.setHeaderHidden(True)
        self.tree.setToolTip(language.tr(
            "Every part of the document — double-click one to edit it "
            "in the Object tab; drag a row (or Ctrl+Up / Down) to "
            "arrange the list, right-click to sort it"))
        self.tree.itemDoubleClicked.connect(self._picked)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._menu)
        layout.addWidget(self.tree)
        model.structure_changed.connect(self.rebuild)
        self.rebuild()

    # ------------------------------------------------------------ tree
    def _definition(self, node):
        if node.type != "reference":
            return node
        name = node.params.get("ref")
        for comp in self.model.all_components():
            if comp.name == name:
                return comp
        return None

    def rebuild(self):
        current = self.place_of(self.tree.currentItem())
        keep = current.id if current is not None else None
        self.tree.clear()
        top = QTreeWidgetItem([language.tr("Main")])
        top.setIcon(0, icons.icon("mdi.folder-open"))
        self.tree.addTopLevelItem(top)
        placed = set()
        found = []

        def add(parent, node, depth):
            comp = self._definition(node)
            if comp is None:
                return
            placed.add(comp.id)
            inner = parts_in(comp)
            item = QTreeWidgetItem([comp.name])
            item.setIcon(0, icons.icon(
                "mdi.folder" if inner or comp.params.get("assembly")
                else "mdi.package-variant-closed"))
            item.setData(0, ROLE, comp.id)
            item.setData(0, PLACE, node.id)
            parent.addChild(item)
            if node.id == keep:
                found.append(item)
            if depth < 12:
                for sub in inner:
                    add(item, sub, depth + 1)

        for node in parts_in(self.model.root):
            if node.type == "component" and not node.visible:
                continue
            add(top, node, 0)
        loose = [c for c in parts_in(self.model.root)
                 if c.type == "component" and not c.visible
                 and c.id not in placed]
        if loose:
            other = QTreeWidgetItem([language.tr("Not placed in Main")])
            other.setIcon(0, icons.icon("mdi.folder-outline"))
            self.tree.addTopLevelItem(other)
            for comp in loose:
                add(other, comp, 0)
        self.tree.expandAll()
        if found:
            self.tree.setCurrentItem(found[0])   # the row moved stays picked

    # ------------------------------------------------------ arranging
    def place_of(self, item):
        """The node *item* stands for where it sits (moved by arranging)."""
        if item is None:
            return None
        nid = item.data(0, PLACE)
        node = self.model.find(nid) if nid is not None else None
        return node if node is not None and node.parent is not None \
            else None

    def arranged(self, node, moved):
        if moved:
            for i in range(self.tree.topLevelItemCount()):
                self._select_place(self.tree.topLevelItem(i), node.id)

    def _select_place(self, item, nid):
        if item.data(0, PLACE) == nid:
            self.tree.setCurrentItem(item)
            return True
        return any(self._select_place(item.child(k), nid)
                   for k in range(item.childCount()))

    def move_current(self, delta):
        node = self.place_of(self.tree.currentItem())
        if node is not None and move_among(self.model, node, delta):
            self.arranged(node, True)

    def sort_list(self, item, reverse=False):
        """Sort the list *item* is in (its rows' nodes, in their places)."""
        node = self.place_of(item)
        if node is None:
            return False
        holder = item.parent()
        rows = [holder.child(k) for k in range(holder.childCount())] \
            if holder is not None else [item]
        nodes = {self.place_of(r) for r in rows} - {None}
        nodes = [n for n in nodes if n.parent is node.parent]
        return sort_among(self.model, node.parent, reverse, only=nodes)

    def _menu(self, pos):
        item = self.tree.itemAt(pos)
        node = self.place_of(item)
        if node is None:
            return
        menu = QMenu(self)
        sibs = _siblings(node)
        k = sibs.index(node) if node in sibs else -1
        up = menu.addAction(language.tr("Move Up") + "\tCtrl+Up")
        up.setEnabled(k > 0)
        up.triggered.connect(lambda: self.move_current(-1))
        down = menu.addAction(language.tr("Move Down") + "\tCtrl+Down")
        down.setEnabled(0 <= k < len(sibs) - 1)
        down.triggered.connect(lambda: self.move_current(1))
        menu.addSeparator()
        menu.addAction(language.tr("Sort A to Z")).triggered.connect(
            lambda: self.sort_list(item))
        menu.addAction(language.tr("Sort Z to A")).triggered.connect(
            lambda: self.sort_list(item, reverse=True))
        menu.addSeparator()
        menu.addAction(language.tr("Open in Object tab")).triggered.connect(
            lambda: self._picked(item, 0))
        self.tree.setCurrentItem(item)
        menu.exec_(self.tree.viewport().mapToGlobal(pos))

    def _picked(self, item, _column):
        node_id = item.data(0, ROLE)
        node = self.model.find(node_id) if node_id is not None else None
        if node is not None:
            self.open_component.emit(node)

    # ------------------------------------------------------- creating
    def _selected_assembly(self):
        item = self.tree.currentItem()
        node_id = item.data(0, ROLE) if item is not None else None
        node = self.model.find(node_id) if node_id is not None else None
        if node is not None and (parts_in(node)
                                 or node.params.get("assembly")):
            return node
        return None

    def _create(self, base, assembly):
        holder = self._selected_assembly()
        name = ""
        if base:
            taken = {n.name for n in self.model.root.walk()}
            name = next(f"{base} {i}" for i in range(1, 10000)
                        if f"{base} {i}" not in taken)
        comp = self.model.new_component(name, visible=False)
        if assembly:
            comp.params["assembly"] = True
        if holder is not None:
            # placed in the selected assembly by an instance
            holder.add(CadNode("reference", f"{comp.name} 1",
                               dict(ref=comp.name)))
        else:
            self.model.add_instance(comp)
        self.model.structure_changed.emit()
        self.open_component.emit(comp)
        return comp

    def new_object(self):
        return self._create("", False)

    def new_subassembly(self):
        return self._create("Sub-assembly", True)

    def new_assembly(self):
        self.tree.setCurrentItem(None)
        return self._create("Assembly", True)

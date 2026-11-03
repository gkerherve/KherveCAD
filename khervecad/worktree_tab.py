# KherveCAD — GPL-3.0-or-later. See LICENSE.
"""The **Work tree** tab — where the document's parts are, as folders.

The first tab of the browser (2026-11-03, the user: "a folder tree with
everything that is in there", so the user sees where they are going).
Assemblies and sub-assemblies (Objects made of other Objects) are
folders holding the parts they place; plain Objects are leaves. Buttons
create a new Object, sub-assembly or assembly (inside the selected
assembly when one is selected); a double-click opens an Object in the
Object tab.
"""

from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtWidgets import (QHBoxLayout, QToolButton, QTreeWidget,
                             QTreeWidgetItem, QVBoxLayout, QWidget)

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
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setToolTip(language.tr(
            "Every part of the document — double-click one to edit it "
            "in the Object tab"))
        self.tree.itemDoubleClicked.connect(self._picked)
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
        self.tree.clear()
        top = QTreeWidgetItem([language.tr("Main")])
        top.setIcon(0, icons.icon("mdi.folder-open"))
        self.tree.addTopLevelItem(top)
        placed = set()

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
            parent.addChild(item)
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

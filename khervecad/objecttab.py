"""The Object tab — edit one Object (component) at a time.

The Main tab shows the whole assembly; this tab roots the same tree
widget at a single **active Object** picked from a dropdown (or by
double-clicking the Object in Main). Both viewers isolate to the
active Object while this tab is current, so a busy assembly never
gets in the way of editing one part.

The dropdown lists every Object in the document, nested ones included
(an imported program's modules often sit inside a colour). Its
toolbar is icons only: New, Rename, Delete (the Object and every
instance placing it, one Ctrl+Z) and To Main.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtCore import QSize, pyqtSignal
from PyQt5.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QMessageBox,
                             QToolButton, QVBoxLayout, QWidget)

from . import icons
from .model import DocumentModel
from .treepanel import ObjectTree

#: (attribute, mdi icon, tooltip) of the Object toolbar, left to right
BUTTONS = (
    ("new_btn", "mdi.plus-box-outline",
     "New Object — create an empty part and edit it here (hidden in "
     "Main until you place it)"),
    ("rename_btn", "mdi.pencil-outline",
     "Rename this Object (its instances, mates and Linked copies "
     "follow)"),
    ("delete_btn", "mdi.delete-outline",
     "Delete this Object and every instance of it in Main — Ctrl+Z "
     "brings them back"),
    ("insert_btn", "mdi.package-down",
     "To Main — place an instance of this Object in the Main assembly "
     "(anchors and snapping live there)"),
)


class ComponentTree(ObjectTree):
    """The Main tree, rooted at the active Object: it lists only that
    Object's contents, and drops/pastes land inside it."""

    #: instances belong to the Main assembly, not inside a definition.
    SHOWS_INSERT_OBJECT = False
    #: groups inside the edited Object can be snapped together — the
    #: secondary anchors that build a part from sub-parts.
    ALLOWS_GROUP_MATES = True

    def __init__(self, model: DocumentModel, active_getter, parent=None):
        #: callable returning the active component node (or None) —
        #: set before super().__init__ because that first rebuild()
        #: already calls _top_nodes().
        self._active_getter = active_getter
        super().__init__(model, parent)

    def _active(self):
        return self._active_getter()

    def _visibility_root(self):
        # the active Object is hidden in Main (it is a definition), so
        # stop the grey/italic visibility walk at it — its contents are
        # edited here at full strength regardless.
        return self._active()

    def _is_opaque(self, node):
        # the active Object's own contents are the point of this tab, so
        # show them; only a *nested* Object stays a single row (edit it
        # from its own tab).
        return node.type == "component" and node is not self._active()

    def _top_nodes(self):
        active = self._active()
        return list(active.children) if active is not None else []

    def _drop_container(self):
        return self._active() or self.model.root

    def step_selection(self, delta: int):
        """Tab / Q / A walk only the active Object's contents here."""
        active = self._active()
        if active is None:
            return
        order = [n for n in active.walk() if n is not active]
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


class ObjectTab(QWidget):
    """Dropdown of the document's Objects + the tree of the active one.

    The active Object is tracked by node id with a name fallback, so
    it survives renames within a session and undo restores (which
    rebuild the tree with fresh ids) alike.
    """

    #: the active Object changed — carries the CadNode or None.
    active_changed = pyqtSignal(object)

    def __init__(self, model: DocumentModel, parent=None):
        super().__init__(parent)
        self.model = model
        self._active_id = None
        self._active_name = None
        self._updating = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 0)
        layout.setSpacing(4)
        row = QHBoxLayout()
        row.setSpacing(2)
        row.addWidget(QLabel("Object:"))
        self.combo = QComboBox()
        self.combo.setToolTip("The Object being edited — every Object "
                              "in the document is listed here, nested "
                              "ones included")
        self.combo.currentIndexChanged.connect(self._combo_picked)
        row.addWidget(self.combo, 1)
        slots = {"new_btn": self.new_object,
                 "rename_btn": self.rename_active,
                 "delete_btn": lambda: self.delete_active(),
                 "insert_btn": self._insert_into_main}
        for attr, glyph, tip in BUTTONS:
            button = QToolButton()
            button.setIcon(icons.icon(glyph))
            button.setIconSize(QSize(20, 20))
            button.setAutoRaise(True)
            button.setToolTip(tip)
            button.clicked.connect(slots[attr])
            setattr(self, attr, button)
            row.addWidget(button)
        layout.addLayout(row)

        self.tree = ComponentTree(model, self.active_component)
        layout.addWidget(self.tree)

        model.structure_changed.connect(self._sync_combo)
        model.node_changed.connect(lambda _n: self._sync_combo())
        self._sync_combo()

    # ------------------------------------------------------ active state
    def active_component(self):
        """The active Object node, re-resolved against the live tree
        (id first, then name) — or None."""
        comps = self.model.all_components()
        for comp in comps:
            if comp.id == self._active_id:
                self._active_name = comp.name
                return comp
        for comp in comps:
            if comp.name == self._active_name:
                self._active_id = comp.id
                return comp
        return None

    def set_active(self, node):
        """Make *node* (a component, or None) the edited Object."""
        previous = self.active_component()
        self._active_id = node.id if node is not None else None
        self._active_name = node.name if node is not None else None
        self._sync_combo()
        if self.active_component() is not previous:
            self.tree.rebuild()
            self.active_changed.emit(self.active_component())

    def new_object(self):
        # hidden in the Main assembly until the user shows it — the
        # Object tab shows it regardless (independent visibility)
        comp = self.model.new_component(visible=False)
        self.set_active(comp)
        return comp

    def _insert_into_main(self):
        """Place an instance of the edited Object into the assembly."""
        comp = self.active_component()
        if comp is not None:
            self.model.add_instance(comp)

    def rename_active(self):
        """Rename the edited Object (mates and Linked copies follow)."""
        comp = self.active_component()
        if comp is None:
            return
        from PyQt5.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Rename Object", "Name:",
                                        text=comp.name)
        name = name.strip()
        if ok and name and name != comp.name:
            self.model.rename(comp, name)
            self._active_name = name
            self._sync_combo()

    def delete_active(self, confirm: bool = True) -> bool:
        """Delete the edited Object and every instance placing it,
        after asking (unless *confirm* is False). One undo step."""
        comp = self.active_component()
        if comp is None:
            return False
        uses = [n for n in self.model.root.walk()
                if n.type == "reference" and n.params.get("ref") == comp.name]
        if confirm:
            extra = (f"\n\nIts {len(uses)} instance"
                     f"{'s' if len(uses) != 1 else ''} in Main will go "
                     "too." if uses else "")
            answer = QMessageBox.question(
                self, "Delete Object",
                f"Delete the Object “{comp.name}”?{extra}\n\n"
                "Ctrl+Z brings it back.",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes:
                return False
        self.model.delete_component(comp)
        self.set_active(None)
        return True

    # ------------------------------------------------------------ combo
    def _sync_combo(self):
        """Rebuild the dropdown from the document's Objects; if the
        active one vanished (deleted / undone), fall back to none."""
        comps = self.model.all_components()
        active = self.active_component()
        self._updating = True
        self.combo.clear()
        self.combo.addItem("(no object)", None)
        for comp in comps:
            self.combo.addItem(icons.icon("mdi.package-variant-closed"),
                               comp.name, comp.id)
            if comp.parent is not None and comp.parent is not self.model.root:
                self.combo.setItemData(
                    self.combo.count() - 1,
                    f"Inside {comp.parent.name}", 3)      # Qt.ToolTipRole
        index = 0
        if active is not None:
            for i in range(1, self.combo.count()):
                if self.combo.itemData(i) == active.id:
                    index = i
                    break
        self.combo.setCurrentIndex(index)
        self._updating = False
        for attr in ("rename_btn", "delete_btn", "insert_btn"):
            getattr(self, attr).setEnabled(active is not None)
        if active is None and self._active_id is not None:
            # the active Object no longer exists
            self._active_id = self._active_name = None
            self.tree.rebuild()
            self.active_changed.emit(None)

    def _combo_picked(self, index):
        if self._updating:
            return
        node_id = self.combo.itemData(index)
        node = self.model.find(node_id) if node_id is not None else None
        self.set_active(node)

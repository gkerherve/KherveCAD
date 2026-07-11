"""Properties panel — edit the parameters of the selected object.

Every node type declares a parameter schema in ``model.NODE_TYPES``;
this panel turns the schema of the selected node into live editors
(x/y/radius for a circle, height/twist for a linear extrude, ...).
Edits go straight into the model, so the 2D view, 3D view and code
tab follow immediately.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License or (at your
option) any later version, as published by the Free Software
Foundation, either version 3 of the License.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QCheckBox, QDoubleSpinBox, QFormLayout,
                             QHBoxLayout, QLabel, QLineEdit,
                             QPushButton, QScrollArea, QSpinBox,
                             QTableWidget, QTableWidgetItem, QVBoxLayout,
                             QWidget)

from . import icons
from .model import NODE_TYPES, DocumentModel, fmt


class ExprEdit(QLineEdit):
    """Editor for numeric params that also accepts expressions.

    "12.5" stores a float; "i * 10 + 2" stores the expression string
    (evaluated by codegen/preview with the loop variables in scope).
    """

    def __init__(self, on_commit, parent=None):
        super().__init__(parent)
        self._on_commit = on_commit
        self.setPlaceholderText("number or expression")
        self.editingFinished.connect(self._commit)

    def set_value(self, value):
        self.setText(fmt(value) if not isinstance(value, str)
                     else value)

    def _commit(self):
        text = self.text().strip()
        if not text:
            return
        try:
            value = float(text)
        except ValueError:
            value = text
        self._on_commit(value)


class PointsEditor(QWidget):
    """Small table editor for polygon points."""

    def __init__(self, points, on_change, parent=None):
        super().__init__(parent)
        self._on_change = on_change
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget(len(points), 2)
        self.table.setHorizontalHeaderLabels(["X", "Y"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.setMaximumHeight(180)
        for row, (x, y) in enumerate(points):
            self.table.setItem(row, 0, QTableWidgetItem(f"{x:g}"))
            self.table.setItem(row, 1, QTableWidgetItem(f"{y:g}"))
        self.table.itemChanged.connect(lambda _i: self._emit())
        layout.addWidget(self.table)

        buttons = QHBoxLayout()
        add = QPushButton(icons.icon("mdi.plus"), "")
        add.setToolTip("Add point")
        add.clicked.connect(self._add_row)
        remove = QPushButton(icons.icon("mdi.minus"), "")
        remove.setToolTip("Remove selected point")
        remove.clicked.connect(self._remove_row)
        buttons.addWidget(add)
        buttons.addWidget(remove)
        buttons.addStretch()
        layout.addLayout(buttons)

    def _add_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem("0"))
        self.table.setItem(row, 1, QTableWidgetItem("0"))
        self._emit()

    def _remove_row(self):
        row = self.table.currentRow()
        if row >= 0 and self.table.rowCount() > 3:
            self.table.removeRow(row)
            self._emit()

    def _emit(self):
        points = []
        for row in range(self.table.rowCount()):
            try:
                x = float(self.table.item(row, 0).text())
                y = float(self.table.item(row, 1).text())
            except (TypeError, ValueError, AttributeError):
                return
            points.append([x, y])
        self._on_change(points)


class PropertiesPanel(QScrollArea):
    """Bottom-left panel: parameter editors for the selected node."""

    def __init__(self, model: DocumentModel, parent=None):
        super().__init__(parent)
        self.model = model
        self.node = None
        self._updating = False
        self.setWidgetResizable(True)
        self._body = QWidget()
        self.setWidget(self._body)
        self._layout = QVBoxLayout(self._body)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._editors = {}
        model.node_changed.connect(self._node_changed)
        model.structure_changed.connect(self._structure_changed)
        self.set_node(None)

    # ---------------------------------------------------------- build
    def set_node(self, node):
        self.node = node
        self._editors.clear()
        self._clear_layout(self._layout)
        if node is None:
            hint = QLabel("Select an object in the tree\n"
                          "to edit its properties.")
            hint.setAlignment(Qt.AlignCenter)
            hint.setEnabled(False)
            self._layout.addStretch()
            self._layout.addWidget(hint)
            self._layout.addStretch()
            return

        spec = NODE_TYPES[node.type]
        title = QLabel(f"<b>{spec['label']}</b>")
        self._layout.addWidget(title)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        name_edit = QLineEdit(node.name)
        name_edit.editingFinished.connect(
            lambda: self._rename(name_edit.text()))
        form.addRow("Name", name_edit)

        for key, label, kind, minimum, maximum in spec["schema"]:
            editor = self._make_editor(key, kind, minimum, maximum)
            if editor is not None:
                self._editors[key] = editor
                form.addRow(label, editor)
        self._layout.addLayout(form)
        self._layout.addStretch()
        self._load_values()

    def _make_editor(self, key, kind, minimum, maximum):
        if kind == "float":
            return ExprEdit(lambda v, k=key: self._set_param(k, v))
        if kind == "int":
            box = QSpinBox()
            box.setRange(int(minimum), int(maximum))
            box.valueChanged.connect(
                lambda v, k=key: self._set_param(k, int(v)))
            return box
        if kind == "bool":
            box = QCheckBox()
            box.toggled.connect(
                lambda v, k=key: self._set_param(k, bool(v)))
            return box
        if kind == "str":
            box = QLineEdit()
            box.editingFinished.connect(
                lambda b=None, k=key: self._set_param(
                    k, self._editors[k].text()))
            return box
        if kind == "points":
            return PointsEditor(self.node.params[key],
                                lambda pts, k=key: self._set_param(k, pts))
        return None

    def _load_values(self):
        self._updating = True
        for key, editor in self._editors.items():
            value = self.node.params.get(key)
            if isinstance(editor, ExprEdit):
                editor.set_value(value)
            elif isinstance(editor, QDoubleSpinBox):
                editor.setValue(float(value))
            elif isinstance(editor, QSpinBox):
                editor.setValue(int(value))
            elif isinstance(editor, QCheckBox):
                editor.setChecked(bool(value))
            elif isinstance(editor, QLineEdit):
                editor.setText(str(value))
        self._updating = False

    # --------------------------------------------------------- events
    def _set_param(self, key, value):
        if not self._updating and self.node is not None:
            self.model.set_param(self.node, key, value)

    def _rename(self, name):
        if not self._updating and self.node is not None and name:
            self.model.rename(self.node, name)

    def _node_changed(self, node):
        # Param changed elsewhere (2D view drag): refresh the editors.
        if node is self.node and not self._updating:
            self._load_values()

    def _structure_changed(self):
        # The node may have been deleted from under us.
        if self.node is not None and \
                self.model.find(self.node.id) is None:
            self.set_node(None)

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            entry = layout.takeAt(0)
            widget = entry.widget()
            if widget is not None:
                widget.deleteLater()
            elif entry.layout() is not None:
                PropertiesPanel._clear_layout(entry.layout())

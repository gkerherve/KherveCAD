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

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox,
                             QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                             QPlainTextEdit, QPushButton, QScrollArea,
                             QSpinBox, QTableWidget, QTableWidgetItem,
                             QVBoxLayout, QWidget)

from . import icons
from .model import NODE_TYPES, DocumentModel, fmt


class VarOrValueEdit(QComboBox):
    """Editor for numeric params: type a fixed number or expression, or
    pick one of the document's variables from the dropdown.

    "12.5" stores a float; a variable name or "i * 10 + 2" stores the
    expression string (resolved by codegen/preview with variables and
    loop values in scope).
    """

    def __init__(self, on_commit, variables, parent=None):
        super().__init__(parent)
        self._on_commit = on_commit
        self._variables = variables            # callable -> list[str]
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)
        self.lineEdit().setPlaceholderText(
            "value, expression or variable")
        self.lineEdit().editingFinished.connect(self._commit)
        self.activated.connect(lambda _i: self._commit())

    def showPopup(self):
        # refresh the variable list every time the dropdown opens, so it
        # always reflects the current document
        text = self.currentText()
        self.blockSignals(True)
        self.clear()
        self.addItems(self._variables())
        self.setEditText(text)
        self.blockSignals(False)
        super().showPopup()

    def set_value(self, value):
        self.setEditText(fmt(value) if not isinstance(value, str)
                         else value)

    def _commit(self):
        text = self.currentText().strip()
        if not text:
            return
        try:
            value = float(text)
        except ValueError:
            value = text
        self._on_commit(value)


class MultilineEdit(QPlainTextEdit):
    """A monospaced multi-line editor (for the raw-OpenSCAD `code`
    param). Commits on focus-out, so the model doesn't regenerate on
    every keystroke."""

    def __init__(self, on_commit, parent=None):
        super().__init__(parent)
        self._on_commit = on_commit
        font = QFont("Consolas")
        font.setStyleHint(QFont.Monospace)
        self.setFont(font)
        self.setMinimumHeight(160)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self._on_commit(self.toPlainText())


class PointsEditor(QWidget):
    """Small table editor for polygon points."""

    #: the row (= vertex index) the user selected, -1 for none.
    point_selected = pyqtSignal(int)

    _ROW_H = 22

    def __init__(self, points, on_change, parent=None):
        super().__init__(parent)
        self._on_change = on_change
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget(len(points), 2)
        self.table.setHorizontalHeaderLabels(["X", "Y"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setDefaultSectionSize(self._ROW_H)
        for row, (x, y) in enumerate(points):
            self.table.setItem(row, 0, QTableWidgetItem(f"{x:g}"))
            self.table.setItem(row, 1, QTableWidgetItem(f"{y:g}"))
        self.table.itemChanged.connect(lambda _i: self._emit())
        self.table.currentCellChanged.connect(
            lambda cur, _c, _pr, _pc: self.point_selected.emit(cur))
        layout.addWidget(self.table)
        self._fit_height()

        buttons = QHBoxLayout()
        add = QPushButton(icons.icon("mdi.plus"), "")
        add.setToolTip("Insert a point after the selected one, on the "
                       "midpoint of its edge (keeps the outline)")
        add.clicked.connect(self._add_row)
        remove = QPushButton(icons.icon("mdi.minus"), "")
        remove.setToolTip("Remove the selected point")
        remove.clicked.connect(self._remove_row)
        up = QPushButton(icons.icon("mdi.arrow-up"), "")
        up.setToolTip("Move the point one place earlier — it lands "
                      "midway between its new neighbours")
        up.clicked.connect(lambda: self._move_row(-1))
        down = QPushButton(icons.icon("mdi.arrow-down"), "")
        down.setToolTip("Move the point one place later — it lands "
                        "midway between its new neighbours")
        down.clicked.connect(lambda: self._move_row(1))
        buttons.addWidget(add)
        buttons.addWidget(remove)
        buttons.addWidget(up)
        buttons.addWidget(down)
        buttons.addStretch()
        layout.addLayout(buttons)

    def _fit_height(self):
        """Size the table to its rows, up to 15, so it shows the points
        without its own scrollbar (the panel scrolls if needed)."""
        rows = min(max(self.table.rowCount(), 1), 15)
        header = self.table.horizontalHeader().sizeHint().height()
        self.table.setFixedHeight(header + rows * self._ROW_H + 6)

    def _read_points(self):
        """Current table contents as floats, or None if a cell is
        blank/invalid (an edit still in progress)."""
        points = []
        for row in range(self.table.rowCount()):
            try:
                x = float(self.table.item(row, 0).text())
                y = float(self.table.item(row, 1).text())
            except (TypeError, ValueError, AttributeError):
                return None
            points.append([x, y])
        return points

    def _fill(self, points):
        """Replace the whole table from a list of points."""
        self.table.blockSignals(True)
        self.table.setRowCount(len(points))
        for row, (x, y) in enumerate(points):
            self.table.setItem(row, 0, QTableWidgetItem(f"{x:g}"))
            self.table.setItem(row, 1, QTableWidgetItem(f"{y:g}"))
        self.table.blockSignals(False)
        self._fit_height()

    def _move_row(self, delta):
        """Move the selected point one place up/down in the ring and
        drop it midway between its two new neighbours."""
        pts = self._read_points()
        if not pts:
            return
        row = self.table.currentRow()
        new = row + delta
        if row < 0 or new < 0 or new >= len(pts):
            return
        pts.insert(new, pts.pop(row))          # reorder
        count = len(pts)
        prev = pts[(new - 1) % count]
        nxt = pts[(new + 1) % count]
        pts[new] = [round((prev[0] + nxt[0]) / 2, 4),
                    round((prev[1] + nxt[1]) / 2, 4)]
        self._fill(pts)
        self.table.setCurrentCell(new, 0)
        self._on_change(pts)

    def _add_row(self):
        # split the edge leaving the selected vertex: the new point sits
        # at that edge's midpoint, so the polygon keeps its shape and you
        # just get a fresh vertex to drag. With nothing selected, split
        # the closing edge (last -> first) rather than spiking to origin.
        pts = self._read_points()
        if not pts:
            return
        count = len(pts)
        cur = self.table.currentRow()
        idx = cur if 0 <= cur < count else count - 1
        nxt = (idx + 1) % count
        mx = round((pts[idx][0] + pts[nxt][0]) / 2, 4)
        my = round((pts[idx][1] + pts[nxt][1]) / 2, 4)
        self.table.blockSignals(True)
        self.table.insertRow(idx + 1)
        self.table.setItem(idx + 1, 0, QTableWidgetItem(f"{mx:g}"))
        self.table.setItem(idx + 1, 1, QTableWidgetItem(f"{my:g}"))
        self.table.blockSignals(False)
        self._fit_height()
        self.table.setCurrentCell(idx + 1, 0)       # ready to edit
        self._emit()

    def _remove_row(self):
        row = self.table.currentRow()
        if row < 0:
            row = self.table.rowCount() - 1
        if row >= 0 and self.table.rowCount() > 3:
            self.table.removeRow(row)
            self._fit_height()
            self.table.selectRow(min(row, self.table.rowCount() - 1))
            self._emit()

    def _emit(self):
        points = self._read_points()
        if points is not None:
            self._on_change(points)


class PropertiesPanel(QScrollArea):
    """Bottom-left panel: parameter editors for the selected node."""

    #: (polygon node, vertex index) selected in a Points table, so the
    #: 2D view can highlight that vertex.
    point_selected = pyqtSignal(object, int)

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

    def _variable_names(self):
        """Names of every document variable, offered in numeric fields."""
        names = []
        for node in self.model.root.walk():
            if node.type == "assign":
                var = str(node.params.get("variable", "")).strip()
                if var and var not in names:
                    names.append(var)
        return names

    def _make_editor(self, key, kind, minimum, maximum):
        if kind == "float":
            return VarOrValueEdit(
                lambda v, k=key: self._set_param(k, v),
                self._variable_names)
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
        if kind == "text":
            return MultilineEdit(
                lambda v, k=key: self._set_param(k, v))
        if kind == "points":
            editor = PointsEditor(
                self.node.params[key],
                lambda pts, k=key: self._set_param(k, pts))
            editor.point_selected.connect(
                lambda idx: self.point_selected.emit(self.node, idx))
            return editor
        if kind == "color":
            button = QPushButton()
            button.clicked.connect(lambda _=False, k=key, b=button:
                                   self._pick_color(k, b))
            return button
        return None

    def _pick_color(self, key, button):
        from PyQt5.QtGui import QColor
        from PyQt5.QtWidgets import QColorDialog
        current = QColor(str(self.node.params.get(key, "#4a90d9")))
        chosen = QColorDialog.getColor(
            current if current.isValid() else QColor("#4a90d9"),
            self, "Colour")
        if chosen.isValid():
            self._set_param(key, chosen.name())
            self._swatch(button, chosen.name())

    @staticmethod
    def _swatch(button, color):
        button.setText(color)
        button.setStyleSheet(
            f"QPushButton {{ background: {color}; }}")

    def _load_values(self):
        self._updating = True
        defaults = NODE_TYPES.get(self.node.type, {}).get("params", {})
        for key, editor in self._editors.items():
            # fall back to the type's default: a node saved before a
            # param existed has no value for it, and feeding None to a
            # spin box raises straight through a Qt slot (which PyQt
            # turns into abort())
            value = self.node.params.get(key, defaults.get(key))
            if value is None:
                continue
            if isinstance(editor, VarOrValueEdit):
                editor.set_value(value)
            elif isinstance(editor, QDoubleSpinBox):
                editor.setValue(float(value))
            elif isinstance(editor, QSpinBox):
                editor.setValue(int(value))
            elif isinstance(editor, QCheckBox):
                editor.setChecked(bool(value))
            elif isinstance(editor, QPushButton):
                self._swatch(editor, str(value))
            elif isinstance(editor, MultilineEdit):
                editor.setPlainText(str(value))
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

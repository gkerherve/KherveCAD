"""Property editors for the "rows" and "choice" schema kinds.

Polygon points have their own two-column editor (properties.py). This
module edits any other list of rows — a polyhedron's [x, y, z] points
and its variable-length faces, a loft's [x, y, z, rx, ry] sections, a
lattice's corner offsets — and a fixed set of named options.

A schema entry reads ``(key, label, "rows", columns, None)`` where
*columns* names the fixed columns, or is None for free-length rows of
whole numbers typed as ``0, 1, 2``; and ``(key, label, "choice",
options, None)`` for a drop-down.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtWidgets import (QComboBox, QHBoxLayout, QPushButton,
                             QTableWidget, QTableWidgetItem, QVBoxLayout,
                             QWidget)

from . import icons


def _cell(value) -> str:
    return f"{value:g}" if isinstance(value, float) else str(value)


class RowsEditor(QWidget):
    """A table of rows that commits the whole list on every edit."""

    _ROW_H = 22

    def __init__(self, rows, columns, on_change, parent=None):
        super().__init__(parent)
        self._columns = list(columns) if columns else None
        self._on_change = on_change
        self._loading = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget(0, len(self._columns or [0]))
        self.table.setHorizontalHeaderLabels(self._columns
                                             or ["Point indices"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setDefaultSectionSize(self._ROW_H)
        self.table.itemChanged.connect(lambda _item: self._emit())
        layout.addWidget(self.table)
        buttons = QHBoxLayout()
        add = QPushButton(icons.icon("mdi.plus"), "")
        add.setToolTip("Add a row after the selected one (a copy of it)")
        add.clicked.connect(self._add_row)
        remove = QPushButton(icons.icon("mdi.minus"), "")
        remove.setToolTip("Remove the selected row")
        remove.clicked.connect(self._remove_row)
        buttons.addWidget(add)
        buttons.addWidget(remove)
        buttons.addStretch()
        layout.addLayout(buttons)
        self.set_rows(rows)

    def set_rows(self, rows):
        """Show *rows* without reporting them back as an edit."""
        self._loading = True
        try:
            rows = rows or []
            self.table.setRowCount(len(rows))
            for r, row in enumerate(rows):
                if self._columns:
                    width = len(self._columns)
                    values = (list(row) + [0.0] * width)[:width]
                    for c, value in enumerate(values):
                        self.table.setItem(r, c,
                                           QTableWidgetItem(_cell(value)))
                else:
                    text = ", ".join(_cell(v) for v in row)
                    self.table.setItem(r, 0, QTableWidgetItem(text))
            self._fit_height()
        finally:
            self._loading = False

    def rows(self):
        """The table as a list of rows, or None while a cell is blank or
        invalid (an edit still in progress). A fixed-column cell that is
        not a number is kept as text: an expression, like any numeric
        parameter."""
        out = []
        for r in range(self.table.rowCount()):
            if self._columns:
                row = []
                for c in range(len(self._columns)):
                    item = self.table.item(r, c)
                    text = item.text().strip() if item else ""
                    if not text:
                        return None
                    try:
                        row.append(float(text))
                    except ValueError:
                        row.append(text)
                out.append(row)
            else:
                item = self.table.item(r, 0)
                text = item.text() if item else ""
                try:
                    row = [int(float(v)) for v in
                           text.replace(";", ",").split(",") if v.strip()]
                except ValueError:
                    return None
                if not row:
                    return None
                out.append(row)
        return out

    def _emit(self):
        if self._loading:
            return
        rows = self.rows()
        if rows is not None:
            self._on_change(rows)

    def _add_row(self):
        r = self.table.currentRow()
        if r < 0:
            r = self.table.rowCount() - 1
        blank = "0" if self._columns else "0, 1, 2"
        texts = []
        for c in range(self.table.columnCount()):
            item = self.table.item(r, c) if r >= 0 else None
            texts.append(item.text() if item else blank)
        self._loading = True
        self.table.insertRow(r + 1)
        for c, text in enumerate(texts):
            self.table.setItem(r + 1, c, QTableWidgetItem(text))
        self._loading = False
        self._fit_height()
        self._emit()

    def _remove_row(self):
        r = self.table.currentRow()
        if r < 0 or self.table.rowCount() <= 1:
            return
        self.table.removeRow(r)
        self._fit_height()
        self._emit()

    def _fit_height(self):
        rows = min(max(self.table.rowCount(), 1), 12)
        header = self.table.horizontalHeader().sizeHint().height()
        self.table.setFixedHeight(header + rows * self._ROW_H + 6)


class ChoiceBox(QComboBox):
    """A drop-down of fixed options (the "choice" kind)."""

    def __init__(self, options, parent=None):
        super().__init__(parent)
        self.addItems([str(o) for o in options or []])

    def set_value(self, value):
        index = self.findText(str(value))
        if index >= 0:
            self.setCurrentIndex(index)

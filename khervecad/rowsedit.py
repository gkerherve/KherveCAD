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


def fit_table_height(table, cap, row_h):
    """Make *table* exactly as tall as its rows (up to *cap*), measured
    from the real row and header heights: a fixed guess per row came up
    short once a stylesheet padded the rows (an Interface Style), and
    three points got a scroll bar."""
    n = table.rowCount()
    shown = min(max(n, 1), cap)
    rows = sum(table.rowHeight(r) for r in range(min(n, shown)))
    rows += (shown - min(n, shown)) * row_h          # the empty slot
    header = max(table.horizontalHeader().height(),
                 table.horizontalHeader().sizeHint().height())
    table.setFixedHeight(header + rows + 2 * table.frameWidth() + 2)


#: row lists that may be empty (nothing = the feature is off): the last
#: row can be removed from these
OPTIONAL_ROWS = {"paths", "corners", "within", "region", "fillets",
                 "chamfers", "edges", "pushes", "strokes", "targets",
                 "warp", "pose", "garments", "tints", "creases", "pins",
                 "anchors", "keys", "options"}


def compact_table(table, row_h=20):
    """Narrow columns, a short header and a slim row number column: a
    table of x / y / z numbers needs ~50 px a column, not a quarter of
    the panel (the user, 2026-10-21)."""
    from PyQt5.QtWidgets import QHeaderView
    head = table.horizontalHeader()
    head.setDefaultSectionSize(54)
    head.setMinimumSectionSize(28)
    head.setSectionResizeMode(QHeaderView.Interactive)
    head.setStretchLastSection(False)
    head.setStyleSheet("QHeaderView::section { padding: 0 2px; "
                       "font-size: 10px; }")
    head.setFixedHeight(18)
    side = table.verticalHeader()
    side.setDefaultSectionSize(row_h)
    side.setMinimumSectionSize(row_h)
    side.setStyleSheet("QHeaderView::section { padding: 0 2px; "
                       "font-size: 10px; }")
    side.setFixedWidth(20)
    font = table.font()
    font.setPointSizeF(max(8.0, font.pointSizeF() - 1))
    table.setFont(font)


def fit_columns(table, least=54, most=110):
    """Each column as wide as its numbers (54-110 px): narrow columns
    cut 0.0001 to '0....' (the user)."""
    table.resizeColumnsToContents()
    for c in range(table.columnCount()):
        table.setColumnWidth(c, max(least, min(most,
                                               table.columnWidth(c) + 6)))


#: the Properties panel, tighter (the user: "make all properties smaller")
COMPACT_QSS = """
QLabel, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
QTableWidget {
    font-size: 11px; }
QLineEdit, QComboBox { padding: 1px 4px; min-height: 16px; }
QSpinBox, QDoubleSpinBox { padding: 1px 18px 1px 4px; min-height: 16px; }
"""


def small_button(glyph, tip, slot):
    """A slim + / − button."""
    from PyQt5.QtCore import QSize
    from PyQt5.QtWidgets import QToolButton
    b = QToolButton()
    b.setIcon(icons.icon(glyph))
    b.setIconSize(QSize(14, 14))
    b.setFixedSize(22, 20)
    b.setAutoRaise(True)
    b.setToolTip(tip)
    b.clicked.connect(slot)
    return b


class RowsEditor(QWidget):
    """A table of rows that commits the whole list on every edit."""

    _ROW_H = 20

    def __init__(self, rows, columns, on_change, parent=None,
                 allow_empty=False, on_add=None):
        super().__init__(parent)
        #: + calls this instead of adding a blank row (a fillet's + picks
        #: edges / faces on the model)
        self._on_add = on_add
        #: an optional list (a polygon's paths, its rounded corners) may
        #: lose its last row; a required one keeps one
        self._allow_empty = allow_empty
        self._columns = list(columns) if columns else None
        self._on_change = on_change
        self._loading = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget(0, len(self._columns or [0]))
        self.table.setHorizontalHeaderLabels(self._columns
                                             or ["Point indices"])
        compact_table(self.table, self._ROW_H)
        if not self._columns:            # free-length index lists
            self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemChanged.connect(lambda _item: self._emit())
        layout.setSpacing(2)
        layout.addWidget(self.table)
        buttons = QHBoxLayout()
        buttons.setSpacing(2)
        add = small_button("mdi.plus", "Add a row after the selected one "
                           "(a copy of it)", self._add_row)
        remove = small_button("mdi.minus", "Remove the selected row",
                              self._remove_row)
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
            if self._columns:
                fit_columns(self.table)
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
        if self._on_add is not None:
            self._on_add()
            return
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
        if r < 0 and self.table.rowCount() == 1:
            r = 0                         # the only row: no need to pick
        if r < 0 or (self.table.rowCount() <= 1
                     and not self._allow_empty):
            return
        self.table.removeRow(r)
        self._fit_height()
        self._emit()

    def _fit_height(self):
        fit_table_height(self.table, 12, self._ROW_H)


class ChoiceBox(QComboBox):
    """A drop-down of fixed options (the "choice" kind)."""

    def __init__(self, options, parent=None):
        super().__init__(parent)
        self.addItems([str(o) for o in options or []])

    def set_value(self, value):
        index = self.findText(str(value))
        if index >= 0:
            self.setCurrentIndex(index)

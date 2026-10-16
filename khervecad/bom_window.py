"""File ▸ Bill of Materials…: the BOM as an editable, exportable table.

One non-modal window per main window (`open_bom`). The tree is
`bom.build` of the document: assemblies, parts and their labelled
components, indented, with every column of `bom.COLUMNS`. Part no.,
description, material (a drop-down of the densities `bom` knows),
finish, supplier, unit cost, mass, unit and notes are typed straight
into the table; the value lands on the line's nodes as `params["bom"]`
(one undo step, saved in the .kcad) and the BOM is rebuilt. Clicking a
line selects its parts in the main window. Export writes CSV, Excel,
HTML or JSON; "Place on Blueprint" puts the parts list and numbered
balloons on the drawing.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from pathlib import Path

from PyQt5.QtCore import QSettings, Qt, QTimer
from PyQt5.QtGui import QBrush, QColor, QFont
from PyQt5.QtWidgets import (QAbstractItemView, QComboBox, QFileDialog,
                             QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                             QMainWindow, QMessageBox, QPushButton,
                             QStyledItemDelegate, QToolBar, QTreeWidget,
                             QTreeWidgetItem, QVBoxLayout, QWidget)

from . import bom, icons

DETAILS = (("Components (every labelled piece)", "components"),
           ("Parts", "parts"), ("Assemblies only", "assemblies"))
#: table column -> the override it edits
EDIT_KEYS = {"part_no": "part_no", "description": "description",
             "material": "material", "finish": "finish",
             "supplier": "supplier", "cost_each": "cost",
             "mass_each": "mass", "unit": "unit", "notes": "notes"}
ROLE_LINE = Qt.UserRole + 1


class _MaterialDelegate(QStyledItemDelegate):
    """The Material column edits with a drop-down of known materials
    (any text may still be typed)."""

    def __init__(self, column, parent=None):
        super().__init__(parent)
        self.column = column

    def createEditor(self, parent, option, index):
        if index.column() != self.column:
            return super().createEditor(parent, option, index)
        combo = QComboBox(parent)
        combo.setEditable(True)
        combo.addItems(sorted(bom.DENSITY))
        return combo

    def setEditorData(self, editor, index):
        if isinstance(editor, QComboBox):
            text = str(index.data() or "").replace(" (est.)", "")
            editor.setCurrentText(text)
        else:
            super().setEditorData(editor, index)

    def setModelData(self, editor, model, index):
        if isinstance(editor, QComboBox):
            model.setData(index, editor.currentText())
        else:
            super().setModelData(editor, model, index)


class BomWindow(QMainWindow):
    def __init__(self, main):
        super().__init__(main)
        self.main = main
        self.model = main.model
        self.setWindowTitle("Bill of materials")
        self.resize(1300, 720)
        self._bom = None
        self._filling = False
        self._stale = False
        self._build_ui()
        self.model.structure_changed.connect(self._model_changed)
        self.model.node_changed.connect(self._model_changed)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(600)
        self._timer.timeout.connect(self.refresh)
        self.refresh()

    # -- layout
    def _build_ui(self):
        bar = QToolBar(self)
        bar.setMovable(False)
        self.addToolBar(bar)
        bar.addWidget(QLabel(" Detail "))
        self.detail = QComboBox()
        for text, _key in DETAILS:
            self.detail.addItem(text)
        saved = QSettings("Kherve", "KherveCAD").value("bom/detail", 0)
        try:
            self.detail.setCurrentIndex(int(saved))
        except (TypeError, ValueError):
            pass
        self.detail.currentIndexChanged.connect(self._detail_changed)
        bar.addWidget(self.detail)
        bar.addSeparator()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter (name, material, supplier…)")
        self.search.setClearButtonEnabled(True)
        self.search.setMaximumWidth(260)
        self.search.textChanged.connect(self._apply_filter)
        bar.addWidget(self.search)
        bar.addSeparator()
        for glyph, text, slot in (
                ("mdi.refresh", "Refresh", self.refresh),
                ("mdi.unfold-more-horizontal", "Expand all",
                 lambda: self.tree.expandAll()),
                ("mdi.unfold-less-horizontal", "Collapse to parts",
                 lambda: self.tree.expandToDepth(0)),
                ("mdi.file-export-outline", "Export…", self.export),
                ("mdi.drawing-box", "Place on Blueprint",
                 self.place_on_blueprint)):
            act = bar.addAction(icons.icon(glyph), text, slot)
            act.setToolTip(text)
        central = QWidget(self)
        lay = QVBoxLayout(central)
        lay.setContentsMargins(6, 6, 6, 6)
        self.tree = QTreeWidget()
        self.tree.setColumnCount(len(bom.COLUMNS))
        self.tree.setHeaderLabels([h for _k, h in bom.COLUMNS])
        self.tree.setAlternatingRowColors(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.setEditTriggers(QAbstractItemView.DoubleClicked |
                                  QAbstractItemView.EditKeyPressed |
                                  QAbstractItemView.SelectedClicked)
        keys = [k for k, _h in bom.COLUMNS]
        self.tree.setItemDelegate(_MaterialDelegate(keys.index("material"),
                                                    self.tree))
        header = self.tree.header()
        header.setSectionResizeMode(QHeaderView.Interactive)
        widths = {"item": 90, "part_no": 130, "name": 220,
                  "description": 300, "qty": 60, "unit": 45,
                  "material": 150, "finish": 130, "size": 130,
                  "mass_each": 90, "mass_total": 95, "cost_each": 80,
                  "cost_total": 85, "supplier": 120, "source": 140,
                  "notes": 160}
        for i, key in enumerate(keys):
            self.tree.setColumnWidth(i, widths.get(key, 100))
        self.tree.itemChanged.connect(self._edited)
        self.tree.itemSelectionChanged.connect(self._selected)
        lay.addWidget(self.tree, 1)
        row = QHBoxLayout()
        self.totals = QLabel()
        self.totals.setTextInteractionFlags(Qt.TextSelectableByMouse)
        row.addWidget(self.totals, 1)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        row.addWidget(close)
        lay.addLayout(row)
        self.setCentralWidget(central)

    # -- data
    def detail_key(self):
        return DETAILS[max(0, self.detail.currentIndex())][1]

    def _detail_changed(self, index):
        QSettings("Kherve", "KherveCAD").setValue("bom/detail", index)
        self.refresh()

    def _model_changed(self, *_a):
        if self._filling:
            return
        if self.isVisible():
            self._timer.start()
        else:
            self._stale = True

    def showEvent(self, event):
        super().showEvent(event)
        if self._stale:
            self._stale = False
            self.refresh()

    def build(self):
        return bom.build(self.model, self.detail_key())

    def refresh(self):
        open_items = self._expanded_items()
        self._bom = self.build()
        keys = [k for k, _h in bom.COLUMNS]
        self._filling = True
        self.tree.setUpdatesEnabled(False)
        try:
            self.tree.clear()

            def add(parent, line):
                row = bom.line_row(line)
                item = QTreeWidgetItem([_cell(row[k]) for k in keys])
                item.setData(0, ROLE_LINE, line)
                flags = item.flags() | Qt.ItemIsEditable
                item.setFlags(flags)
                for c, k in enumerate(keys):
                    if isinstance(row[k], (int, float)):
                        item.setTextAlignment(c, Qt.AlignRight |
                                              Qt.AlignVCenter)
                if line.kind in ("assembly", "part"):
                    f = QFont(item.font(0))
                    f.setBold(True)
                    for c in range(len(keys)):
                        item.setFont(c, f)
                if line.estimated:
                    item.setForeground(keys.index("material"),
                                       QBrush(QColor(130, 130, 130)))
                    item.setToolTip(keys.index("material"),
                                    "Estimated from the label or colour — "
                                    "double-click to set it")
                if isinstance(parent, QTreeWidget):
                    parent.addTopLevelItem(item)
                else:
                    parent.addChild(item)
                for child in line.children:
                    add(item, child)
                return item
            for line in self._bom.lines:
                add(self.tree, line)
            self.tree.expandToDepth(1)
            for path in open_items:
                item = self._item_at(path)
                if item is not None:
                    item.setExpanded(True)
        finally:
            self.tree.setUpdatesEnabled(True)
            self._filling = False
        self._show_totals()
        self._apply_filter(self.search.text())

    def _show_totals(self):
        t = self._bom.totals()
        mats = self._bom.summary_by_material()
        top = ", ".join(f"{m} {kg:g} kg" for m, kg in list(mats.items())[:5])
        cost = f" · cost {t['cost']:.2f} {t['currency']}" if t["cost"] \
            else ""
        self.totals.setText(
            f"<b>{self._bom.title}</b> — {t['lines']} lines, "
            f"{t['unique_items']} different items · total mass "
            f"<b>{t['mass_kg']:g} kg</b> (solid estimate){cost}"
            + (f" · {top}" if top else ""))

    def _expanded_items(self):
        paths = []

        def walk(item, path):
            for i in range(item.childCount()):
                ch = item.child(i)
                if ch.isExpanded():
                    paths.append(path + (i,))
                walk(ch, path + (i,))
        walk(self.tree.invisibleRootItem(), ())
        return paths

    def _item_at(self, path):
        item = self.tree.invisibleRootItem()
        for i in path:
            if i >= item.childCount():
                return None
            item = item.child(i)
        return item

    def _apply_filter(self, text):
        text = (text or "").strip().lower()

        def walk(item):
            shown = False
            for i in range(item.childCount()):
                ch = item.child(i)
                hit = not text or any(
                    text in ch.text(c).lower()
                    for c in range(self.tree.columnCount()))
                below = walk(ch)
                ch.setHidden(not (hit or below))
                shown = shown or hit or below
            return shown
        walk(self.tree.invisibleRootItem())

    # -- editing
    def _edited(self, item, column):
        if self._filling:
            return
        key = bom.COLUMNS[column][0]
        line = item.data(0, ROLE_LINE)
        field = EDIT_KEYS.get(key)
        if line is None or field is None:
            QTimer.singleShot(0, self.refresh)     # put the value back
            return
        value = item.text(column).strip().replace(" (est.)", "")
        if field in ("cost", "mass") and value:
            try:
                value = float(value.replace(",", "."))
            except ValueError:
                QMessageBox.warning(self, "Bill of materials",
                                    f"{value!r} is not a number.")
                QTimer.singleShot(0, self.refresh)
                return
        set_line_fields(self.model, line, {field: value})
        QTimer.singleShot(0, self.refresh)

    def _selected(self):
        nodes = []
        for item in self.tree.selectedItems():
            line = item.data(0, ROLE_LINE)
            if line is not None:
                nodes += [n for n in line.nodes if n is not None]
        if not nodes:
            return
        try:
            self.main.builder.active_tree().select_nodes(nodes)
        except Exception:                          # noqa: BLE001
            pass

    # -- output
    def export(self):
        stem = (self._bom.title or "bom").replace("/", "-")
        start = str(Path(getattr(self.main, "_path", "") or
                         Path.home() / "Documents").with_name(
            f"{stem} BOM.xlsx")) if getattr(self.main, "_path", "") else \
            str(Path.home() / "Documents" / f"{stem} BOM.xlsx")
        path, _f = QFileDialog.getSaveFileName(
            self, "Export bill of materials", start,
            "Excel workbook (*.xlsx);;CSV (*.csv);;Web page (*.html);;"
            "JSON (*.json)")
        if not path:
            return
        try:
            bom.export(self._bom, path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Bill of materials", str(exc))
            return
        self.statusBar().showMessage(f"Written {path}", 8000)

    def place_on_blueprint(self):
        board = self.main.open_blueprint()
        board.add_bom(detail=self.detail_key(), balloons=True)


def _cell(value):
    if isinstance(value, float):
        return f"{value:g}" if abs(value) >= 0.001 or value == 0 else \
            f"{value:.2e}"
    return str(value)


def set_line_fields(model, line, fields):
    """Hand-typed *fields* onto every node of a BOM *line* — one undo
    step (node_changed schedules the snapshot)."""
    nodes = [n for n in line.nodes if n is not None]
    if line.kind != "component":
        nodes = nodes[:1]          # an Object's own line, not its call
    bom.set_fields(nodes, fields)
    for n in nodes:
        model.node_changed.emit(n)


def open_bom(main):
    win = getattr(main, "_bom_window", None)
    if win is None:
        win = main._bom_window = BomWindow(main)
    else:
        win.refresh()
    win.show()
    win.raise_()
    win.activateWindow()
    return win

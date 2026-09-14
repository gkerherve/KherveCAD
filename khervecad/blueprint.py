"""Blueprint — the 2D engineering drawing of the finished model
(File ▸ Blueprint…, Ctrl+Shift+D).

A window of its own: the sheet in the middle, a toolbar of annotation
tools down the left (smart / horizontal / vertical / aligned / diameter
/ radius / angle dimensions, notes, balloons, centre marks and lines,
surface finish, datums, geometric tolerances, sketch lines, detail
views), the sheet controls across the top (export PDF / DXF / SVG /
PNG, print, undo, update from the model, auto-dimension, auto-arrange,
sheet size, scale, white paper or blueprint blue, hidden lines, insert
a view, a section, a shaded picture or the parts list) and a Properties
panel on the right for whatever is selected — the title block's title,
drawing number, material, finish, mass, who drew and checked it.

The first time it opens it lays the model out by itself: third-angle
Front / Top / Right views and an isometric at the largest standard
scale that fits, overall dimensions, every hole's diameter and centre
mark, and a filled-in title block with the mass worked out from the
volume and the material. Everything after that is the user's: views
drag (Top and Right stay aligned to Front), dimensions and notes drag
by their labels, and every change is one undo step.

The sheet is saved in the .kcad (`DocumentModel.drawing`): views by
name and position, annotations in each view's MODEL coordinates. The
geometry is not saved — it is re-projected from the model on open and
on "Update from model", so the drawing follows the part.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import copy
import re
from pathlib import Path

from PyQt5.QtCore import QRectF, QSettings, Qt, QTimer
from PyQt5.QtGui import QKeySequence, QPainter
from PyQt5.QtWidgets import (QAction, QActionGroup, QApplication, QCheckBox,
                             QComboBox, QDialog, QDialogButtonBox,
                             QDockWidget, QDoubleSpinBox, QFileDialog,
                             QFormLayout, QGraphicsView, QInputDialog,
                             QLabel, QLineEdit, QMainWindow, QMenu,
                             QMessageBox, QPlainTextEdit, QSpinBox,
                             QToolBar, QToolButton, QUndoCommand,
                             QUndoStack, QVBoxLayout, QWidget)

from . import analysis, blueprint_export, drawing, icons
from . import blueprint_items as bi
from .blueprint_tools import make_tools
from .blueprint_scene import (  # noqa: F401 — re-exported
    ALIGN, DEFAULT_SHEET, GAP, LETTERS, PROJECTIONS, SECTION_LOOK,
    SECTION_PARENT, BlueprintScene, Geometry, default_fields,
    mass_text)


_SETTINGS = ("Kherve", "KherveCAD")

# ── undo ───────────────────────────────────────────────────────────

class _StateCommand(QUndoCommand):
    """One edit to the sheet: the whole state before and after, like
    the model's own snapshots — correct for every operation."""

    def __init__(self, win, before, after, label):
        super().__init__(label)
        self.win, self.before, self.after = win, before, after
        self._first = True

    def redo(self):
        if self._first:
            self._first = False
            return
        self.win.restore(self.after)

    def undo(self):
        self.win.restore(self.before)


# ── the sheet view ─────────────────────────────────────────────────

class SheetView(QGraphicsView):
    """The paper on screen: wheel zoom about the cursor, middle-drag
    (or the Pan tool) to pan, and every click handed to the tool."""

    def __init__(self, scene, win):
        super().__init__(scene)
        self.win = win
        self.setRenderHints(QPainter.Antialiasing
                            | QPainter.SmoothPixmapTransform
                            | QPainter.TextAntialiasing)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setViewportUpdateMode(QGraphicsView.SmartViewportUpdate)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setMouseTracking(True)
        self._pan = None
        self._fitted = False

    def px_to_mm(self, px):
        return px / max(abs(self.transform().m11()), 1e-6)

    def fit(self):
        self.fitInView(self.scene().sheet_rect().adjusted(-6, -6, 6, 6),
                       Qt.KeepAspectRatio)

    def zoom(self, factor):
        now = abs(self.transform().m11())
        factor = max(0.2 / now, min(factor, 80.0 / now))
        self.scale(factor, factor)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._fitted:
            self._fitted = True
            QTimer.singleShot(0, self.fit)

    def wheelEvent(self, event):
        self.zoom(1.0015 ** event.angleDelta().y())

    def _tool(self):
        return self.win.tool

    def mousePressEvent(self, event):
        tool = self._tool()
        if event.button() == Qt.MiddleButton or (
                tool.key == "pan" and event.button() == Qt.LeftButton):
            self._pan = event.pos()
            self.viewport().setCursor(Qt.ClosedHandCursor)
            return
        if event.button() == Qt.RightButton and tool.key != "select":
            if not tool.cancel():
                self.win.set_tool("select")
            return
        if tool.key == "select":
            self._raise_view_of(self._note_at(event.pos()))
            super().mousePressEvent(event)
            return
        if event.button() == Qt.LeftButton:
            tool.press(self.mapToScene(event.pos()), event)

    def _note_at(self, pos):
        """The annotation under viewport point *pos*, if any — even one
        stacked under a neighbouring view."""
        for item in self.items(pos):
            if isinstance(item, bi.SheetItem) and \
                    item.flags() & item.ItemIsSelectable and \
                    not getattr(item, "transient", False):
                return item
        return None

    def _raise_view_of(self, note):
        """A child item stacks above its own view only, so a label that
        hangs out of its view into the next one lay under that view's
        click area and could not be selected, dragged or deleted: lift
        its view above the others before the click is delivered."""
        if note is None or note.parentItem() is None:
            return
        for view in self.scene().views.values():
            view.setZValue(1)
        note.parentItem().setZValue(2)

    def mouseMoveEvent(self, event):
        if self._pan is not None:
            delta = event.pos() - self._pan
            self._pan = event.pos()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - delta.y())
            return
        pos = self.mapToScene(event.pos())
        self.win.cursor_moved(pos)
        tool = self._tool()
        if tool.key in ("select", "pan"):
            super().mouseMoveEvent(event)
        else:
            tool.move(pos, event)

    def mouseReleaseEvent(self, event):
        if self._pan is not None and event.button() in (Qt.MiddleButton,
                                                        Qt.LeftButton):
            self._pan = None
            self.viewport().unsetCursor()
            return
        tool = self._tool()
        if tool.key == "select":
            super().mouseReleaseEvent(event)
            return
        tool.release(self.mapToScene(event.pos()), event)

    def mouseDoubleClickEvent(self, event):
        if self._tool().key != "select":
            return
        item = self._note_at(event.pos()) or self.itemAt(event.pos())
        while item is not None and not isinstance(
                item, (bi.SheetItem, bi.ViewItem)):
            item = item.parentItem()
        if item is not None:
            self.win.edit_item(item)

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Escape:
            if not self._tool().cancel():
                self.win.set_tool("select")
                self.scene().clearSelection()
            return
        if key in (Qt.Key_Delete, Qt.Key_Backspace):
            self.win.delete_selected()
            return
        steps = {Qt.Key_Left: (-1, 0), Qt.Key_Right: (1, 0),
                 Qt.Key_Up: (0, -1), Qt.Key_Down: (0, 1)}
        if key in steps and self.scene().selectedItems():
            k = 10.0 if event.modifiers() & Qt.ShiftModifier else 1.0
            self.win.nudge(steps[key][0] * k, steps[key][1] * k)
            return
        super().keyPressEvent(event)


# ── properties ─────────────────────────────────────────────────────

class PropertiesPanel(QWidget):
    """Editors for the selected item, built from its FIELDS (the title
    block: every field of the block)."""

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.item = None
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self.heading = QLabel()
        self.heading.setStyleSheet("font-weight: bold; font-size: 13px;")
        self._layout.addWidget(self.heading)
        self.body = QWidget()
        self.form = QFormLayout(self.body)
        self.form.setContentsMargins(0, 4, 0, 0)
        self._layout.addWidget(self.body)
        self.info = QLabel()
        self.info.setWordWrap(True)
        self.info.setStyleSheet("color: #888;")
        self._layout.addWidget(self.info)
        self._layout.addStretch(1)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(600)
        self._pending = None
        self._timer.timeout.connect(self._flush)
        self.show_item(None)

    def _clear(self):
        self._flush()
        while self.form.rowCount():
            self.form.removeRow(0)

    def _fields(self, item):
        if isinstance(item, bi.TitleBlockItem):
            return [(k, label, "material" if k == "material" else "text",
                     None) for k, label in drawing.TITLE_FIELDS]
        return list(getattr(item, "FIELDS", ()))

    def show_item(self, item):
        self._clear()
        self.item = item
        if item is None:
            self.heading.setText("Sheet")
            self.info.setText(
                "Select a view, a dimension, a note or the title block to "
                "edit it here. Double-click the title block to fill it "
                "in; drag views and labels to move them.")
            return
        title = getattr(item, "TITLE", "Item")
        if isinstance(item, bi.ViewItem):
            title = item.label_text().title()
        self.heading.setText(title)
        self.info.setText(self._describe(item))
        for key, label, kind, options in self._fields(item):
            getter = getattr(item, "field", None)
            value = getter(key) if getter else item.data.get(key, "")
            self.form.addRow(label, self._editor(item, key, kind, options,
                                                 value))

    def _describe(self, item):
        if isinstance(item, bi.DimensionItem):
            from .units import symbol
            unit = ("°" if item.data.get("kind") == "angle"
                    else " " + symbol(self.win.scene.unit))
            return (f"Measured on the model: "
                    f"{bi.fmt(item.value(), 4)}{unit}. Drag the dimension "
                    f"to move it; type a Text to override the number.")
        if isinstance(item, bi.TitleBlockItem):
            return ("Leave Mass empty to work it out from the volume and "
                    "the material's density.")
        if isinstance(item, bi.ViewItem):
            return f"Scale {drawing.scale_label(item.scale_)}."
        return ""

    def _editor(self, item, key, kind, options, value):
        def commit(v, now=True):
            if now:
                self.win.set_field(item, key, v)
            else:
                self._pending = (item, key, v)
                self._timer.start()
        if kind == "multiline":
            edit = QPlainTextEdit(str(value or ""))
            edit.setFixedHeight(80)
            edit.textChanged.connect(
                lambda: commit(edit.toPlainText(), False))
            return edit
        if kind == "float":
            spin = QDoubleSpinBox()
            lo, hi = options or (0.0, 1000.0)
            spin.setRange(lo, hi)
            spin.setDecimals(2)
            spin.setValue(float(value or 0.0))
            spin.valueChanged.connect(lambda v: commit(v))
            return spin
        if kind == "int":
            spin = QSpinBox()
            lo, hi = options or (0, 1000)
            spin.setRange(lo, hi)
            spin.setValue(int(value or 0))
            spin.valueChanged.connect(lambda v: commit(v))
            return spin
        if kind == "bool":
            box = QCheckBox()
            box.setChecked(bool(value))
            box.toggled.connect(lambda v: commit(v))
            return box
        if kind == "choice":
            combo = QComboBox()
            for k, label in options:
                combo.addItem(label, k)
            combo.setCurrentIndex(max(combo.findData(value), 0))
            combo.currentIndexChanged.connect(
                lambda _i: commit(combo.currentData()))
            return combo
        if kind == "material":
            combo = QComboBox()
            combo.setEditable(True)
            combo.addItems(list(analysis.MATERIALS))
            combo.setCurrentText(str(value or ""))
            combo.lineEdit().editingFinished.connect(
                lambda: commit(combo.currentText()))
            combo.activated.connect(lambda _i: commit(combo.currentText()))
            return combo
        edit = QLineEdit(str(value if value is not None else ""))
        if isinstance(item, bi.TitleBlockItem) and key == "mass":
            edit.setPlaceholderText(
                "auto: " + (mass_text(self.win.scene.geometry.volume(),
                                      str(item.field("material")),
                                      self.win.scene.unit)
                            or "set a known material"))
        edit.editingFinished.connect(lambda: commit(edit.text()))
        return edit

    def discard_pending(self):
        """Forget an edit not yet applied (the sheet is being replaced)."""
        self._pending = None
        self._timer.stop()

    def _flush(self):
        if self._pending is not None:
            item, key, value = self._pending
            self._pending = None
            self._timer.stop()
            self.win.set_field(item, key, value)


class FcfDialog(QDialog):
    """What a feature control frame says."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Geometric tolerance")
        form = QFormLayout(self)
        self.symbol = QComboBox()
        for key, label in bi.GDT:
            self.symbol.addItem(label, key)
        self.tolerance = QLineEdit("Ø0.1")
        self.datums = QLineEdit("A B")
        form.addRow("Characteristic", self.symbol)
        form.addRow("Tolerance", self.tolerance)
        form.addRow("Datums", self.datums)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok
                                   | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self):
        return {"symbol": self.symbol.currentData(),
                "tolerance": self.tolerance.text(),
                "datums": self.datums.text()}


# ── the window ─────────────────────────────────────────────────────

def _tip(title, what, how=""):
    body = f"<b>{title}</b><br>{what}"
    if how:
        body += f"<br><i>{how}</i>"
    return f"<div style='max-width:320px'>{body}</div>"


#: the annotation toolbar: (tool key, icon, label, shortcut, what, how)
ANNOTATE = (
    ("select", "mdi.cursor-default-outline", "Select / Move", "Esc",
     "Select views and annotations; drag a view to move it (Top and "
     "Right stay aligned to Front), drag a dimension or note by its "
     "label.", "Arrow keys nudge, Shift+arrow 10 mm, Delete removes."),
    ("pan", "mdi.cursor-move", "Pan", "",
     "Drag to slide the sheet around.", "The wheel zooms; the middle "
     "button pans with any tool."),
    None,
    ("dim_smart", "mdi.ruler", "Smart dimension", "D",
     "One tool for most dimensions: a round edge gives Ø (or R), a "
     "straight edge its length, two points their distance.",
     "Click, then move the mouse: above/below gives horizontal, "
     "left/right vertical, elsewhere aligned. Click to place."),
    ("dim_horizontal", "mdi.arrow-left-right", "Horizontal dimension", "",
     "The horizontal distance between two points.",
     "Click two points (they snap to corners, midpoints, centres), "
     "then place."),
    ("dim_vertical", "mdi.arrow-up-down", "Vertical dimension", "",
     "The vertical distance between two points.",
     "Click two points, then place."),
    ("dim_aligned", "mdi.vector-line", "Aligned dimension", "",
     "The true distance between two points, along the line joining "
     "them.", "Click two points, then place."),
    ("dim_diameter", "mdi.diameter-outline", "Diameter", "",
     "The diameter of a hole or boss, as Ø.",
     "Click the rim, then place the number."),
    ("dim_radius", "mdi.radius-outline", "Radius", "",
     "The radius of an arc or fillet, as R.",
     "Click the arc, then place the number."),
    ("dim_angle", "mdi.angle-acute", "Angle", "",
     "The angle between two straight edges.",
     "Click one edge, then the other, then place the arc."),
    None,
    ("leader", "mdi.comment-arrow-right-outline", "Note with leader", "N",
     "A note pointing at a feature — '4 HOLES THROUGH', 'BREAK EDGES'.",
     "Click what it points at, then where the text goes."),
    ("text", "mdi.format-text", "Text", "T",
     "Free text anywhere on the sheet — general notes, a revision "
     "remark.", "Click where it goes and type."),
    ("balloon", "mdi.numeric-1-circle-outline", "Balloon", "B",
     "An item number in a circle, pointing at a part — matched to the "
     "parts list.", "Click the part, then where the balloon goes."),
    None,
    ("centre_mark", "mdi.plus-circle-outline", "Centre mark", "",
     "The chain-line cross that marks the centre of a hole.",
     "Click a round edge."),
    ("centre_line", "mdi.dots-horizontal", "Centre line", "",
     "A chain line along an axis of symmetry.", "Click two points."),
    None,
    ("finish", "mdi.square-root", "Surface finish", "",
     "The ISO 1302 roughness symbol (Ra) on a surface.",
     "Click the surface's edge and pick the roughness."),
    ("datum", "mdi.alpha-a-box-outline", "Datum feature", "",
     "A datum letter in a box with its triangle, for geometric "
     "tolerances to refer to.", "Click the datum edge, then where the "
     "letter goes."),
    ("fcf", "mdi.card-text-outline", "Geometric tolerance", "",
     "A feature control frame: position, flatness, perpendicularity... "
     "with the tolerance and datums.",
     "Click the feature, then where the frame goes."),
    None,
    ("sketch_line", "mdi.slash-forward", "Line", "",
     "A line drawn on the paper (thick, thin, dashed or chain — set it "
     "in Properties).", "Click the start, then the end."),
    ("sketch_rect", "mdi.rectangle-outline", "Rectangle", "",
     "A rectangle on the paper — a frame round a note, a table.",
     "Click one corner, then the other."),
    ("sketch_circle", "mdi.circle-outline", "Circle", "",
     "A circle on the paper.", "Click the centre, then the rim."),
    None,
    ("detail", "mdi.magnify-scan", "Detail view", "",
     "An enlarged view (2:1) of a small area, lettered on its parent.",
     "Click the centre of the area, then its edge; drag the detail "
     "where it fits."),
)


class BlueprintWindow(QMainWindow):
    """File ▸ Blueprint… — the drawing of the model, with the tools to
    dimension and annotate it."""

    def __init__(self, main):
        super().__init__(main)
        self.setWindowFlag(Qt.Window, True)
        self.main = main
        self.model = main.model
        self.resize(1400, 900)
        self.scene = BlueprintScene(self)
        self.scene.unit = self.model.unit
        self.scene.on_edit = self.commit
        self.scene.picture = self._picture
        self.sheet = SheetView(self.scene, self)
        self.setCentralWidget(self.sheet)
        self.undo_stack = QUndoStack(self)
        self._state = None
        self._saving = False
        self._restoring = False
        self._stale = False
        self.tools = make_tools(self)
        self.tool = self.tools["select"]
        self._build_ui()
        self.scene.selectionChanged.connect(self._selection_changed)
        self.model.structure_changed.connect(self._model_changed)
        self.model.node_changed.connect(lambda _n: self._model_changed())
        self.model.drawing_changed.connect(self._drawing_replaced)
        self.model.unit_changed.connect(self._unit_changed)
        self.load()

    def _unit_changed(self, unit):
        """The title block's UNITS and mass follow the document; the
        dimensions are the model's numbers and need nothing."""
        self.scene.unit = unit
        self.scene.refresh_title()

    # -- building the UI
    def _action(self, glyph, text, slot=None, shortcut="", tip="",
                checkable=False):
        act = QAction(icons.icon(glyph), text, self)
        if shortcut:
            act.setShortcut(QKeySequence(shortcut))
            act.setShortcutContext(Qt.WindowShortcut)
        if tip:
            act.setToolTip(tip)
            act.setStatusTip(re.sub(r"<[^>]+>", " ", tip).strip())
        act.setCheckable(checkable)
        if slot is not None:
            act.triggered.connect(slot)
        return act

    def _build_ui(self):
        menu = self.menuBar()
        files = menu.addMenu("&File")
        top = QToolBar("Sheet")
        top.setObjectName("blueprint_sheet")
        top.setIconSize(top.iconSize() * 1.1)
        self.addToolBar(Qt.TopToolBarArea, top)
        for ext, glyph, label, key in (
                (".pdf", "mdi.file-pdf-box", "Export PDF", "Ctrl+E"),
                (".dxf", "mdi.file-cad", "Export DXF", ""),
                (".svg", "mdi.svg", "Export SVG", ""),
                (".png", "mdi.image-outline", "Export PNG", "")):
            act = self._action(glyph, label + "…",
                               lambda _=False, e=ext: self.export_as(e), key,
                               _tip(label, {
                                   ".pdf": "The sheet as a vector PDF at "
                                           "its real size — to print or "
                                           "send.",
                                   ".dxf": "Layered DXF in sheet "
                                           "millimetres for any CAD or CAM "
                                           "program (VISIBLE, HIDDEN, "
                                           "CENTER, DIM, TEXT...).",
                                   ".svg": "Vector SVG for the web or an "
                                           "illustration program.",
                                   ".png": "A picture of the sheet at 8 "
                                           "pixels per millimetre."}[ext]))
            files.addAction(act)
            top.addAction(act)
        self.print_act = self._action(
            "mdi.printer", "Print…", self.print_sheet, "Ctrl+P",
            _tip("Print", "Print the sheet, fitted to the page."))
        files.addAction(self.print_act)
        top.addAction(self.print_act)
        files.addSeparator()
        files.addAction("&Close", self.close, "Ctrl+W")
        top.addSeparator()

        edit = menu.addMenu("&Edit")
        undo = self.undo_stack.createUndoAction(self, "Undo")
        undo.setIcon(icons.icon("mdi.undo"))
        undo.setShortcut(QKeySequence.Undo)
        redo = self.undo_stack.createRedoAction(self, "Redo")
        redo.setIcon(icons.icon("mdi.redo"))
        redo.setShortcuts([QKeySequence("Ctrl+Y"), QKeySequence.Redo])
        delete = self._action("mdi.delete-outline", "Delete",
                              self.delete_selected, "",
                              _tip("Delete", "Remove the selected views "
                                   "and annotations (a view takes its "
                                   "dimensions with it).", "Delete key"))
        for act in (undo, redo, delete):
            edit.addAction(act)
            top.addAction(act)
        edit.addAction("Select &All", self._select_all, "Ctrl+A")
        top.addSeparator()

        tools_menu = menu.addMenu("&Tools")
        self.update_act = self._action(
            "mdi.refresh", "Update from model", self.update_from_model,
            "F5", _tip("Update from model", "Re-project every view from "
                       "the model as it is now; your dimensions and notes "
                       "stay."))
        auto = self._action(
            "mdi.auto-fix", "Auto-dimension", self.auto_dimension, "",
            _tip("Auto-dimension", "Add the overall sizes and every "
                 "hole's diameter and centre mark. Running it again "
                 "replaces what it added before."))
        arrange = self._action(
            "mdi.view-grid-plus-outline", "Auto-arrange views",
            self.auto_arrange, "",
            _tip("Auto-arrange", "Put the projected views back in the "
                 "third-angle arrangement at the best scale."))
        for act in (self.update_act, auto, arrange):
            tools_menu.addAction(act)
            top.addAction(act)
        tools_menu.addSeparator()
        tools_menu.addAction("Start a &new sheet…", self._new_sheet)
        self.stale_label = QLabel("  ⚠ The model changed — Update  ")
        self.stale_label.setStyleSheet(
            "color: #b35900; font-weight: bold;")
        self._stale_act = top.addWidget(self.stale_label)
        self._stale_act.setVisible(False)
        top.addSeparator()

        top.addWidget(QLabel(" Sheet "))
        self.sheet_combo = QComboBox()
        self.sheet_combo.addItems(list(drawing.SHEETS))
        self.sheet_combo.setToolTip("Paper size (landscape)")
        self.sheet_combo.activated.connect(self._sheet_chosen)
        top.addWidget(self.sheet_combo)
        top.addWidget(QLabel(" Scale "))
        self.scale_combo = QComboBox()
        self.scale_combo.addItem("Best fit", None)
        for s in drawing.SCALES:
            self.scale_combo.addItem(drawing.scale_label(s), s)
        self.scale_combo.setToolTip("Drawing scale — the title block "
                                    "follows")
        self.scale_combo.activated.connect(self._scale_chosen)
        top.addWidget(self.scale_combo)
        self.style_combo = QComboBox()
        for key, label in bi.STYLE_NAMES.items():
            self.style_combo.addItem(icons.icon("mdi.palette-outline"),
                                     label, key)
        self.style_combo.setToolTip("White paper, or the classic blueprint "
                                    "blue — exports follow")
        self.style_combo.activated.connect(self._style_chosen)
        top.addWidget(self.style_combo)
        self.hidden_act = self._action(
            "mdi.eye-off-outline", "Hidden lines", self._hidden_toggled, "",
            _tip("Hidden lines", "Show the edges behind the surface as "
                 "dashed lines. Turn off for threaded or very detailed "
                 "parts."), checkable=True)
        top.addAction(self.hidden_act)
        top.addSeparator()
        view_menu = menu.addMenu("&View")
        for glyph, label, slot, key in (
                ("mdi.magnify-plus-outline", "Zoom in",
                 lambda: self.sheet.zoom(1.25), "Ctrl++"),
                ("mdi.magnify-minus-outline", "Zoom out",
                 lambda: self.sheet.zoom(0.8), "Ctrl+-"),
                ("mdi.fit-to-page-outline", "Fit sheet", self.sheet.fit,
                 "F")):
            act = self._action(glyph, label, slot, key,
                               _tip(label, "The sheet on screen; the "
                                    "wheel zooms about the cursor."))
            view_menu.addAction(act)
            top.addAction(act)

        insert = QToolBar("Insert")
        insert.setObjectName("blueprint_insert")
        self.addToolBar(Qt.TopToolBarArea, insert)
        insert_menu = menu.addMenu("&Insert")
        views_menu = QMenu("Projected view", self)
        for name in PROJECTIONS:
            views_menu.addAction(name, lambda n=name: self.add_projected(n))
        sections_menu = QMenu("Section view", self)
        for axis, label in (("y", "A-A through the middle, front to back "
                                  "(Y)"),
                            ("x", "Side to side (X)"),
                            ("z", "Top to bottom (Z)")):
            sections_menu.addAction(label,
                                    lambda a=axis: self.add_section(a))
        for glyph, label, sub, what in (
                ("mdi.cube-outline", "Projected view", views_menu,
                 "Add Front, Top, Right, Left, Back, Bottom or an "
                 "isometric view."),
                ("mdi.content-cut", "Section view", sections_menu,
                 "A hatched cut through the middle of the part, with its "
                 "cutting line drawn on the view it cuts.")):
            button = QToolButton()
            button.setIcon(icons.icon(glyph))
            button.setText(label)
            button.setToolTip(_tip(label, what))
            button.setMenu(sub)
            button.setPopupMode(QToolButton.InstantPopup)
            insert.addWidget(button)
            insert_menu.addMenu(sub)
        for glyph, label, slot, what in (
                ("mdi.image-filter-hdr", "Shaded picture",
                 self.add_shaded, "The model as the 3D view paints it, "
                                  "from the isometric corner — a picture "
                                  "for whoever reads the drawing."),
                ("mdi.table", "Parts list", self.add_bom,
                 "The bill of materials: every Object with its quantity "
                 "and material, above the title block."),
                ("mdi.form-textbox", "Title block", self.edit_title,
                 "Fill in the title, drawing number, material, finish, "
                 "who drew and checked it.")):
            act = self._action(glyph, label, slot, "", _tip(label, what))
            insert.addAction(act)
            insert_menu.addAction(act)

        left = QToolBar("Annotate")
        left.setObjectName("blueprint_annotate")
        self.addToolBar(Qt.LeftToolBarArea, left)
        annotate_menu = menu.addMenu("&Annotate")
        self.tool_group = QActionGroup(self)
        self.tool_actions = {}
        for row in ANNOTATE:
            if row is None:
                left.addSeparator()
                annotate_menu.addSeparator()
                continue
            key, glyph, label, shortcut, what, how = row
            act = self._action(glyph, label,
                               lambda _=False, k=key: self.set_tool(k),
                               shortcut, _tip(label, what, how),
                               checkable=True)
            self.tool_group.addAction(act)
            left.addAction(act)
            annotate_menu.addAction(act)
            self.tool_actions[key] = act
        self.tool_actions["select"].setChecked(True)

        self.panel = PropertiesPanel(self)
        dock = QDockWidget("Properties", self)
        dock.setObjectName("blueprint_properties")
        dock.setWidget(self.panel)
        dock.setFeatures(QDockWidget.DockWidgetMovable
                         | QDockWidget.DockWidgetFloatable)
        dock.setMinimumWidth(270)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        self.position_label = QLabel()
        self.statusBar().addPermanentWidget(self.position_label)

    # -- model <-> sheet
    def _model_tris(self):
        """What the 3D view shows — each part's exact mesh once OpenSCAD
        has rendered it, so holes are cut and dimensions are true."""
        from .engine import wait_until_idle
        engine = getattr(self.main, "engine", None)
        if engine is not None:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                wait_until_idle(engine, 60.0)
            finally:
                QApplication.restoreOverrideCursor()
        return list(self.main.view3d.model_mesh or ())   # never the cut

    def _doc_title(self):
        builder = getattr(self.main, "builder", None)
        part = builder.isolated_component() if builder is not None else None
        if part is not None:
            return part.name
        path = getattr(self.main, "_path", None)
        return Path(path).stem if path else "Part"

    def load(self):
        """Build the sheet: the saved one, or a fresh automatic layout."""
        self.tool.reset()
        self.panel.discard_pending()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.scene.geometry = Geometry(self._model_tris())
            state = self.model.drawing
            if state and state.get("views"):
                self.scene.load_state(state)
            else:
                self._fresh()
        finally:
            QApplication.restoreOverrideCursor()
        self._state = self.scene.state()
        self.undo_stack.clear()
        self._set_stale(False)
        self.sync_controls()
        self._save()
        if not self.scene.geometry.tris:
            self.status("The model has no solid to draw yet — build "
                        "something, then Update from model.")

    def _fresh(self):
        self.scene.load_state({"sheet": DEFAULT_SHEET,
                               "fields": default_fields(self._doc_title())})
        if self.scene.geometry.tris:
            self.scene.new_layout()
            self.scene.auto_dimension()

    def _new_sheet(self):
        if QMessageBox.question(
                self, "Blueprint", "Start again from an automatic layout? "
                "Your dimensions and notes on this sheet go (Undo brings "
                "them back).") != QMessageBox.Yes:
            return
        fields = dict(self.scene.fields)
        self._fresh()
        self.scene.fields.update(fields)
        self.scene.refresh_title()
        self.commit("New sheet")

    def update_from_model(self):
        state = self.scene.state()
        self.scene.geometry = Geometry(self._model_tris())
        self.scene.load_state(state)
        if any(n.data.get("auto") for n in self.scene.notes()):
            self.scene.auto_dimension()
        self._set_stale(False)
        self.commit("Update from model")
        self.status("Every view re-projected from the model.")

    def _model_changed(self):
        if self.isVisible():
            self._set_stale(True)

    def _set_stale(self, stale):
        self._stale = stale
        self._stale_act.setVisible(stale)

    def _drawing_replaced(self):
        """Another document was opened (or New): show its sheet."""
        if self._saving or not self.isVisible():
            return
        if self.model.drawing != self._state:
            self.load()

    def _save(self):
        self._saving = True
        try:
            self.model.drawing = copy.deepcopy(self._state)
            self.model.drawing_changed.emit()
        finally:
            self._saving = False

    def commit(self, label="Edit"):
        """One change to the sheet: an undo step, saved in the document.
        Never while an undo/redo is rebuilding the sheet: a commit from
        inside QUndoStack.undo() pushed a step mid-undo."""
        if self._restoring:
            return
        new = self.scene.state()
        if new == self._state:
            return
        self.undo_stack.push(_StateCommand(self, self._state, new, label))
        self._state = new
        self._save()
        self.setWindowTitle(f"Blueprint — {self.scene.title_text()}")

    def restore(self, state):
        """Undo/redo: the sheet rebuilt from *state*. What was half made
        goes — an unapplied edit in Properties, a tool's preview and the
        views it had picked, all of which belong to the sheet being
        replaced (a tool kept clicking into a view no longer shown)."""
        self._restoring = True
        try:
            self.panel.discard_pending()
            self.tool.reset()
            self.scene.load_state(state)
            self._state = copy.deepcopy(state)
            self._save()
            self.sync_controls()
        finally:
            self._restoring = False

    def flush_pending(self):
        """Apply an edit still waiting in Properties (typed text is
        applied a moment after the last key) — before the document is
        saved or the window closes, so nothing typed is lost."""
        self.panel._flush()

    def sync_controls(self):
        for combo, value in ((self.sheet_combo, self.scene.sheet),):
            combo.blockSignals(True)
            combo.setCurrentText(value)
            combo.blockSignals(False)
        self.scale_combo.blockSignals(True)
        index = self.scale_combo.findData(self.scene.scale)
        self.scale_combo.setCurrentIndex(max(index, 0))
        self.scale_combo.blockSignals(False)
        self.style_combo.blockSignals(True)
        self.style_combo.setCurrentIndex(
            max(self.style_combo.findData(self.scene.look.style), 0))
        self.style_combo.blockSignals(False)
        self.hidden_act.blockSignals(True)
        self.hidden_act.setChecked(self.scene.hidden_lines)
        self.hidden_act.blockSignals(False)
        self.setWindowTitle(f"Blueprint — {self.scene.title_text()}")
        self.panel.show_item(None)

    # -- tools
    def set_tool(self, key):
        tool = self.tools.get(key, self.tools["select"])
        if tool is not self.tool:
            self.tool.deactivate()
            self.tool = tool
        self.tool_actions[tool.key].setChecked(True)
        self.sheet.setDragMode(QGraphicsView.RubberBandDrag
                               if tool.key == "select"
                               else QGraphicsView.NoDrag)
        self.sheet.viewport().setCursor(
            Qt.ArrowCursor if tool.key == "select" else
            Qt.OpenHandCursor if tool.key == "pan" else Qt.CrossCursor)
        if tool.key != "select":
            self.scene.clearSelection()
        tool.activate()

    def status(self, text):
        self.statusBar().showMessage(text, 12000)

    def cursor_moved(self, pos):
        text = f"x {pos.x():.1f}  y {self.scene.H - pos.y():.1f} mm"
        view = self.scene.view_at(pos)
        if view is not None and view.data.get("kind") != "shaded":
            q = view.mapFromScene(pos)
            u, v = view.to_model((q.x(), q.y()))
            from .units import symbol
            text = f"{view.label_text().title()}: {u:.2f}, {v:.2f} " \
                   f"{symbol(self.scene.unit)}   ·   sheet {text}"
        self.position_label.setText(text)

    def ask_text(self, title, label, default="", multiline=False):
        if multiline:
            value, ok = QInputDialog.getMultiLineText(self, title, label,
                                                      default)
        else:
            value, ok = QInputDialog.getText(self, title, label,
                                             text=default)
        return value if ok else None

    def ask_choice(self, title, label, items, current=0):
        value, ok = QInputDialog.getItem(self, title, label, items, current,
                                         True)
        return value if ok else None

    def ask_fcf(self):
        dialog = FcfDialog(self)
        return dialog.values() if dialog.exec_() == QDialog.Accepted \
            else None

    # -- editing
    def add_note(self, data, view, label="Add annotation"):
        item = self.scene.add_note(data, view)
        self.commit(label)
        return item

    def add_projected(self, name):
        existing = self.scene.projected(name)
        if existing is not None:
            self.scene.clearSelection()
            existing.setSelected(True)
            self.status(f"The {name} view is already on the sheet.")
            return existing
        item = self.scene.add_view({"kind": "projected", "name": name})
        self._place_new(item)
        self.commit(f"Add {name} view")
        return item

    def _place_new(self, item):
        """A new view goes where third-angle puts it if there is room,
        else in the first free spot."""
        w, h = item.size()
        front = self.scene.front()
        name = item.data.get("name")
        spot = None
        if front is not None and item.data.get("kind") == "projected":
            fr = front.mapRectToScene(front.content_rect())
            spot = {"Left": (fr.left() - GAP - w, fr.bottom()),
                    "Bottom": (fr.left(), fr.bottom() + GAP + h)}.get(name)
            if name == "Back":
                right = self.scene.projected("Right")
                edge = right.mapRectToScene(right.content_rect()).right() \
                    if right is not None else fr.right()
                spot = (edge + GAP, fr.bottom())
        area = self.scene.usable_rect()
        if spot is None or not area.contains(
                QRectF(spot[0], spot[1] - h, w, h)):
            spot = self.scene.free_spot(w, h)
        self.scene._moving = True
        try:
            item.setPos(*spot)
        finally:
            self.scene._moving = False

    def add_section(self, axis):
        item = self.scene.add_view({"kind": "section", "axis": axis,
                                    "letter": self.scene.next_letter()})
        self._place_new(item)
        self.scene.update_marks()
        self.commit("Add section")
        return item

    def add_detail(self, parent, centre, radius, factor=2.0):
        source = parent.data.get("name") if parent.data.get(
            "kind", "projected") == "projected" else "Front"
        item = self.scene.add_view({
            "kind": "detail", "parent": parent.data["id"],
            "source": source, "centre": [float(centre[0]), float(centre[1])],
            "radius": float(radius), "factor": float(factor),
            "letter": self.scene.next_letter()})
        self._place_new(item)
        self.scene.update_marks()
        self.commit("Add detail view")
        self.set_tool("select")
        return item

    def _picture(self, data):
        view3d = self.main.view3d
        if not view3d.model_mesh:
            return None
        px = int(float(data.get("width", 80.0)) * 12)
        stage, view3d.stage = view3d.stage, False
        try:
            image, _cam = view3d.snapshot(
                px, int(px * 0.75), yaw=float(data.get("yaw", -65.0)),
                pitch=float(data.get("pitch", 30.0)), frame=True,
                clean=True, transparent=True,
                pixel_ratio=max(1.0, px / 700.0), uncut=True)
        finally:
            view3d.stage = stage
        return image

    def add_shaded(self):
        item = self.scene.add_view({"kind": "shaded", "width": 80.0,
                                    "yaw": -65.0, "pitch": 30.0})
        self._place_new(item)
        self.commit("Add shaded picture")
        return item

    def bom_rows(self):
        material = str(self.scene.fields.get("material", ""))
        rows = []
        for comp in self.model.components():
            if not comp.children:
                continue
            qty = len(self.model.instances_of(comp)) + (1 if comp.visible
                                                        else 0)
            if qty:
                rows.append([str(len(rows) + 1), comp.name, str(qty),
                             material])
        return rows or [["1", self.scene.title_text(), "1", material]]

    def add_bom(self):
        existing = [n for n in self.scene.notes() if n.KIND == "bom"]
        self.scene.remove(existing)
        item = bi.BomItem({"rows": self.bom_rows()})
        m = bi.FrameItem.MARGIN
        x = self.scene.W - m - item.width()
        y = self.scene.H - m - drawing.TITLE_H - item.height()
        self.scene.add_note({"type": "bom", "rows": item.data["rows"],
                             "x": x, "y": y})
        self.commit("Add parts list")

    def edit_title(self):
        self.set_tool("select")
        self.scene.clearSelection()
        self.scene.title.setSelected(True)

    def edit_item(self, item):
        """Double-click: text straight into its editor."""
        if isinstance(item, (bi.TextItem, bi.LeaderItem)):
            value = self.ask_text(item.TITLE, "Text:", item.data.get(
                "text", ""), True)
            if value is not None:
                self.set_field(item, "text", value)
            return
        if isinstance(item, bi.DimensionItem):
            value = self.ask_text("Dimension", "Text (blank = the measured "
                                  "value):", item.data.get("text", ""))
            if value is not None:
                self.set_field(item, "text", value)
            return
        item.setSelected(True)

    def set_field(self, item, key, value):
        if isinstance(item, bi.TitleBlockItem):
            self.scene.fields[key] = value
            if key in ("company", "drawn", "material"):
                QSettings(*_SETTINGS).setValue(f"blueprint/{key}", value)
            self.scene.refresh_title()
        else:
            item.set_field(key, value)
            if isinstance(item, bi.ViewItem):
                self.scene.update_marks()
        self.commit("Edit " + str(key).replace("_", " "))

    def delete_selected(self):
        items = [i for i in self.scene.selectedItems()
                 if isinstance(i, bi.ViewItem) or i in self.scene.note_items]
        if not items:
            return
        self.tool.reset()               # it may have picked a view going now
        self.scene.remove(items)
        self.commit("Delete")

    def nudge(self, dx, dy):
        moved = False
        for item in self.scene.selectedItems():
            if isinstance(item, bi.ViewItem) or getattr(item, "MOVABLE",
                                                        False):
                item.moveBy(dx, dy)
                moved = True
        if moved:
            self.commit("Nudge")

    def _select_all(self):
        for item in list(self.scene.views.values()) + self.scene.notes():
            item.setSelected(True)

    def _selection_changed(self):
        items = self.scene.selectedItems()
        self.panel.show_item(items[0] if len(items) == 1 else None)

    # -- sheet controls
    def _sheet_chosen(self, _index):
        self.scene.set_sheet(self.sheet_combo.currentText())
        self.sheet.fit()
        self.commit("Sheet size")

    def _scale_chosen(self, _index):
        self.scene.set_scale(self.scale_combo.currentData())
        self.sync_controls()
        self.commit("Scale")

    def _style_chosen(self, _index):
        self.scene.look.style = self.style_combo.currentData()
        self.scene.update()
        self.commit("Style")

    def _hidden_toggled(self, on):
        self.scene.hidden_lines = bool(on)
        self.scene.refill()
        self.commit("Hidden lines")

    def auto_dimension(self):
        self.scene.auto_dimension()
        self.commit("Auto-dimension")

    def auto_arrange(self):
        self.scene.arrange()
        self.sync_controls()
        self.commit("Auto-arrange")

    # -- output
    def export_as(self, ext):
        settings = QSettings(*_SETTINGS)
        path = getattr(self.main, "_path", None)
        folder = str(settings.value("blueprint/dir", "") or (
            Path(path).parent if path else Path.home()))
        stem = re.sub(r"[^\w.-]+", "-", self.scene.title_text()).strip("-")
        start = str(Path(folder) / f"{stem or 'blueprint'}{ext}")
        path, _f = QFileDialog.getSaveFileName(
            self, "Export blueprint", start, blueprint_export.FILTERS)
        if not path:
            return None
        if Path(path).suffix.lower() not in blueprint_export.WRITERS:
            path += ext
        try:
            blueprint_export.export(self.scene, path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Blueprint",
                                f"Could not write the drawing:\n{exc}")
            return None
        settings.setValue("blueprint/dir", str(Path(path).parent))
        self.status(f"Blueprint saved: {path}")
        return path

    def print_sheet(self):
        blueprint_export.print_sheet(self.scene, self)

    def closeEvent(self, event):
        self.flush_pending()
        self.tool.deactivate()
        super().closeEvent(event)


def open_blueprint(main):
    """File ▸ Blueprint… — one window per document window, raised if it
    is already open."""
    win = getattr(main, "_blueprint", None)
    if win is None:
        win = main._blueprint = BlueprintWindow(main)
    elif not win.isVisible():
        win.load()
    win.show()
    win.raise_()
    win.activateWindow()
    return win


def export_saved(main, path):
    """Write the document's saved Blueprint to *path* without opening
    the window (the export_drawing MCP tool). Returns the scene."""
    from .engine import wait_until_idle
    if getattr(main, "engine", None) is not None:
        wait_until_idle(main.engine, 60.0)
    scene = BlueprintScene()
    scene.unit = main.model.unit
    scene.geometry = Geometry(list(main.view3d.model_mesh or ()))
    scene.load_state(main.model.drawing)
    blueprint_export.export(scene, path)
    return scene

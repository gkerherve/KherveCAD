"""File ▸ P&ID (Process Diagram)…: the piping and instrumentation
diagram editor.

One non-modal window per main window (`open_pid`): a searchable
PALETTE of every `pid_symbols` symbol grouped like a P&ID template
(equipment, heat transfer, vessels, valves, actuated valves, safety,
instruments, fittings), the SHEET (`PidCanvas`, painted by `pid_render`
— what you see is what PDF, SVG, PNG and DXF get), a PROPERTIES panel
and the SCHEDULES (equipment, valves, instruments, lines, check).

Tools: Select (click, drag to move — lines follow; R turns, M mirrors,
Delete), Connect (click a port — they light up under the cursor — then
any waypoints, then the other port; the line takes the toolbar's kind,
service, size and material and gets its line number), Note, and
placing a symbol (pick it in the palette, click the sheet; Esc stops).
Wheel zooms about the cursor, middle- or right-drag pans, F fits.

The diagram is the document's (`DocumentModel.pid`, saved in the .kcad)
and has its own undo stack of whole-diagram states. A symbol may name
the 3D part it stands for ("3D part"); selecting it selects that part in
the main window. "From model" starts a diagram from the 3D parts it
recognises by name.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import copy
from pathlib import Path

from PyQt5.QtCore import QPointF, QSize, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import (QAbstractItemView, QAction, QActionGroup,
                             QCheckBox, QComboBox, QDockWidget, QFileDialog,
                             QFormLayout, QHBoxLayout, QInputDialog, QLabel,
                             QLineEdit, QListWidget, QListWidgetItem,
                             QMainWindow, QMessageBox, QPlainTextEdit,
                             QPushButton, QSpinBox, QTabWidget,
                             QTableWidget, QTableWidgetItem, QToolBar,
                             QUndoCommand, QUndoStack, QVBoxLayout, QWidget)

from . import icons
from . import pid as P
from . import pid_render as R
from . import pid_symbols as ps


# ── the document's diagram ─────────────────────────────────────────

def diagram_of(main):
    """The open window's live diagram, else one read from the model."""
    win = getattr(main, "_pid_window", None)
    if win is not None:
        return P.Diagram(win.diagram.to_dict())
    return P.Diagram(main.model.pid or {"fields": _default_fields(main)})


def store(main, diagram, label="Edit"):
    """Make *diagram* the document's: through the window's undo stack
    when it is open, else straight into the model."""
    win = getattr(main, "_pid_window", None)
    if win is not None:
        win.replace(diagram, label)
    else:
        main.model.pid = diagram.to_dict()
        _dirty(main)


def _dirty(main):
    if hasattr(main, "_dirty"):
        main._dirty = True
        if hasattr(main, "_update_title"):
            main._update_title()


def _default_fields(main):
    import datetime
    import getpass
    title = ""
    comps = [c.name for c in main.model.components() if c.visible]
    if len(comps) == 1:
        title = comps[0]
    try:
        user = getpass.getuser()
    except Exception:                              # noqa: BLE001
        user = ""
    return {"title": (title + " — P&ID") if title else
            "Process and instrumentation diagram",
            "number": "PID-001", "revision": "A", "drawn": user,
            "date": datetime.date.today().isoformat()}


class _StateCommand(QUndoCommand):
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


def symbol_icon(kind, size=40):
    """The palette picture: the symbol drawn into a square."""
    sym = ps.SYMBOLS[kind]
    pix = QPixmap(size, size)
    pix.fill(Qt.white)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing, True)
    span = max(sym.w, sym.h, 10.0) + 4.0
    k = size / span
    p.translate(size / 2.0, size / 2.0)
    p.scale(k, k)
    R.paint_prims(p, ps.placed_prims(kind, 0, 0), R.INK, widen=0.25)
    p.end()
    return QIcon(pix)


# ── the sheet ──────────────────────────────────────────────────────

class PidCanvas(QWidget):
    changed = pyqtSignal(str)            # an edit to commit (its label)
    selection_changed = pyqtSignal()
    status = pyqtSignal(str)

    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumSize(500, 360)
        self.tool = "select"
        self.place_kind = None
        self.selection = []
        self.hover = None
        self._zoom = 2.0
        self._pan = QPointF(20, 20)
        self._drag = None
        self._pan_from = None
        self._connect = None        # {"from": end, "points": [...]}
        self._cursor = None
        self._fitted = False

    # -- coordinates
    @property
    def d(self):
        return self.win.diagram

    def to_sheet(self, pos):
        return ((pos.x() - self._pan.x()) / self._zoom,
                (pos.y() - self._pan.y()) / self._zoom)

    def fit(self):
        W, H = self.d.size
        if self.width() < 10 or self.height() < 10:
            return
        k = min((self.width() - 20) / W, (self.height() - 20) / H)
        self._zoom = max(k, 0.2)
        self._pan = QPointF((self.width() - W * self._zoom) / 2.0,
                            (self.height() - H * self._zoom) / 2.0)
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._fitted:
            self._fitted = True
            self.fit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self._fitted:
            return

    # -- painting
    def paintEvent(self, _event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(120, 126, 134))
        p.translate(self._pan)
        p.scale(self._zoom, self._zoom)
        R.paint(p, self.d, self.selection, self.hover, grid=True)
        if self._connect is not None and self._cursor is not None:
            pts = [self._port_xy(self._connect["from"])] + \
                self._connect["points"] + [self._snap_cursor()]
            pen = QPen(R.SELECT, 0.4)
            pen.setDashPattern([3, 2])
            p.setPen(pen)
            for a, b in zip(pts, pts[1:]):
                p.drawLine(QPointF(*a), QPointF(*b))
        if self.tool == "place" and self.place_kind and \
                self._cursor is not None:
            x, y = P._snap(self._cursor[0]), P._snap(self._cursor[1])
            p.setOpacity(0.5)
            R.paint_prims(p, ps.placed_prims(self.place_kind, x, y),
                          R.SELECT)
            p.setOpacity(1.0)
        p.end()

    def _port_xy(self, end):
        return tuple(self.d.port(end)[0])

    def _snap_cursor(self):
        x, y = self._cursor
        if self._connect is not None:
            # keep the next leg straight: snap to the axis nearest
            last = (self._connect["points"][-1] if
                    self._connect["points"] else
                    self._port_xy(self._connect["from"]))
            if abs(x - last[0]) > abs(y - last[1]):
                y = last[1]
            else:
                x = last[0]
        return (P._snap(x), P._snap(y))

    # -- hit testing
    def symbol_at(self, x, y):
        edge = None
        for s in reversed(self.d.symbols):
            x0, y0, x1, y1 = self.d.box(s)
            if not (x0 - 1 <= x <= x1 + 1 and y0 - 1 <= y <= y1 + 1):
                continue
            if s["kind"] == "boundary":
                # a boundary is picked by its edge: what it encloses
                # must stay clickable
                if min(abs(x - x0), abs(x - x1), abs(y - y0),
                       abs(y - y1)) < 1.5:
                    edge = edge or s
                continue
            return s
        return edge

    def line_at(self, x, y, tol=1.5):
        for ln in reversed(self.d.lines):
            pts = ln.get("points") or []
            for i, (a, b) in enumerate(zip(pts, pts[1:])):
                if P._on_segment((x, y), a, b, tol):
                    return ln, i
        return None, None

    def note_at(self, x, y):
        for n in reversed(self.d.notes):
            rows = str(n.get("text", "")).splitlines() or [""]
            w = max(R.text_width(r, n.get("size", 3.0)) for r in rows)
            h = len(rows) * n.get("size", 3.0) * 1.6
            if n["x"] <= x <= n["x"] + w and n["y"] <= y <= n["y"] + h:
                return n
        return None

    # -- mouse
    def mousePressEvent(self, event):
        self.setFocus()
        if event.button() in (Qt.MiddleButton, Qt.RightButton):
            if event.button() == Qt.RightButton and self._connect:
                self._connect = None
                self.update()
                return
            self._pan_from = (event.pos(), QPointF(self._pan))
            return
        if event.button() != Qt.LeftButton:
            return
        x, y = self.to_sheet(event.pos())
        if self.tool == "place" and self.place_kind:
            s = self.d.add_symbol(self.place_kind, x, y)
            self.selection = [s["id"]]
            self.changed.emit("Add " + ps.SYMBOLS[self.place_kind].label)
            self.selection_changed.emit()
            return
        if self.tool == "note":
            text, ok = QInputDialog.getMultiLineText(self, "Note", "Text:")
            if ok and text.strip():
                n = self.d.add_note(text, x, y)
                self.selection = [n["id"]]
                self.changed.emit("Add note")
                self.selection_changed.emit()
            return
        if self.tool == "connect":
            port = self.d.nearest_port(x, y, 4.0 / max(self._zoom / 2, 0.5))
            if self._connect is None:
                if port is None:
                    self.status.emit("Click a PORT to start the line "
                                     "(ports light up under the cursor).")
                    return
                self._connect = {"from": port, "points": []}
                self.status.emit("Click waypoints, then the other port. "
                                 "Right click or Esc cancels.")
                return
            if port is not None and port != self._connect["from"]:
                self.win.finish_connect(self._connect, port)
                self._connect = None
                return
            ln, _i = self.line_at(x, y)
            if ln is not None and self._connect["points"]:
                # ends on another line: a tee
                end = {"x": self._snap_cursor()[0],
                       "y": self._snap_cursor()[1]}
                self.win.finish_connect(self._connect, end)
                self._connect = None
                return
            self._connect["points"].append(list(self._snap_cursor()))
            self.update()
            return
        # select
        s = self.symbol_at(x, y)
        n = None if s else self.note_at(x, y)
        ln, seg = (None, None) if (s or n) else self.line_at(x, y)
        target = s or n or ln
        additive = event.modifiers() & Qt.ShiftModifier
        if target is None:
            if not additive:
                self.selection = []
        elif additive:
            if target["id"] in self.selection:
                self.selection.remove(target["id"])
            else:
                self.selection.append(target["id"])
        elif target["id"] not in self.selection:
            self.selection = [target["id"]]
        self.selection_changed.emit()
        if s is not None or n is not None:
            moving = [i for i in self.selection]
            self._drag = {"kind": "move", "start": (x, y), "ids": moving,
                          "orig": {i: self._xy(i) for i in moving},
                          "moved": False}
        elif ln is not None:
            self._drag = {"kind": "segment", "line": ln["id"], "seg": seg,
                          "start": (x, y),
                          "orig": copy.deepcopy(ln["points"]),
                          "moved": False}
        self.update()

    def _xy(self, oid):
        for s in self.d.symbols:
            if s["id"] == oid:
                return (s["x"], s["y"])
        for n in self.d.notes:
            if n["id"] == oid:
                return (n["x"], n["y"])
        return None

    def mouseMoveEvent(self, event):
        if self._pan_from is not None:
            pos, pan = self._pan_from
            self._pan = pan + QPointF(event.pos() - pos)
            self.update()
            return
        x, y = self.to_sheet(event.pos())
        self._cursor = (x, y)
        if self._drag is not None and event.buttons() & Qt.LeftButton:
            dx, dy = x - self._drag["start"][0], y - self._drag["start"][1]
            if self._drag["kind"] == "move":
                for oid, orig in self._drag["orig"].items():
                    if orig is None:
                        continue
                    for s in self.d.symbols:
                        if s["id"] == oid:
                            s["x"] = P._snap(orig[0] + dx)
                            s["y"] = P._snap(orig[1] + dy)
                            self.d.reroute(oid)
                    for n in self.d.notes:
                        if n["id"] == oid:
                            n["x"], n["y"] = orig[0] + dx, orig[1] + dy
                self._drag["moved"] = True
            else:
                ln = self.d.line(self._drag["line"])
                pts = copy.deepcopy(self._drag["orig"])
                i = self._drag["seg"]
                a, b = pts[i], pts[i + 1]
                if 0 < i < len(pts) - 2:
                    if abs(a[0] - b[0]) < 1e-6:      # vertical: move x
                        a[0] = b[0] = P._snap(a[0] + dx)
                    else:
                        a[1] = b[1] = P._snap(a[1] + dy)
                    ln["points"] = pts
                    ln["auto"] = False
                    self._drag["moved"] = True
            self.update()
            return
        hover = None
        if self.tool in ("connect", "select"):
            port = self.d.nearest_port(x, y, 4.0)
            if port is not None:
                hover = port
            else:
                s = self.symbol_at(x, y)
                if s is not None and self.tool == "connect":
                    hover = {"symbol": s["id"]}
        if hover != self.hover or self.tool in ("place", "connect"):
            self.hover = hover
            self.update()
        sx, sy = P._snap(x), P._snap(y)
        self.status.emit(f"x {sx:.1f}  y {sy:.1f} mm")

    def mouseReleaseEvent(self, event):
        if self._pan_from is not None:
            self._pan_from = None
            return
        drag, self._drag = self._drag, None
        if drag is not None and drag.get("moved"):
            self.changed.emit("Move" if drag["kind"] == "move"
                              else "Reshape line")

    def mouseDoubleClickEvent(self, event):
        x, y = self.to_sheet(event.pos())
        s = self.symbol_at(x, y)
        if s is not None and self.tool == "select":
            self.win.focus_property("tag")

    def wheelEvent(self, event):
        k = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        pos = QPointF(event.pos())
        before = self.to_sheet(event.pos())
        self._zoom = max(0.2, min(40.0, self._zoom * k))
        self._pan = pos - QPointF(before[0] * self._zoom,
                                  before[1] * self._zoom)
        self.update()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Escape:
            if self._connect is not None:
                self._connect = None
            else:
                self.win.set_tool("select")
            self.update()
            return
        if key in (Qt.Key_Delete, Qt.Key_Backspace):
            self.win.delete_selected()
            return
        if key == Qt.Key_R:
            self.win.rotate_selected(
                -90 if event.modifiers() & Qt.ShiftModifier else 90)
            return
        if key == Qt.Key_M:
            self.win.mirror_selected()
            return
        if key == Qt.Key_F:
            self.fit()
            return
        if key in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            step = P.GRID * (4 if event.modifiers() & Qt.ShiftModifier
                             else 1)
            dx = {Qt.Key_Left: -step, Qt.Key_Right: step}.get(key, 0)
            dy = {Qt.Key_Up: -step, Qt.Key_Down: step}.get(key, 0)
            moved = False
            for s in self.d.symbols:
                if s["id"] in self.selection:
                    self.d.move(s["id"], s["x"] + dx, s["y"] + dy)
                    moved = True
            if moved:
                self.changed.emit("Nudge")
            return
        super().keyPressEvent(event)


# ── the window ─────────────────────────────────────────────────────

class PidWindow(QMainWindow):
    def __init__(self, main):
        super().__init__(main)
        self.main = main
        self.setWindowTitle("P&ID — piping and instrumentation diagram")
        self.resize(1500, 950)
        self.diagram = P.Diagram(main.model.pid or {
            "fields": _default_fields(main)})
        self._state = self.diagram.to_dict()
        self._restoring = False
        self._filling = False
        self._saving = False
        self.undo = QUndoStack(self)
        self.canvas = PidCanvas(self)
        self.setCentralWidget(self.canvas)
        self.canvas.changed.connect(self.commit)
        self.canvas.selection_changed.connect(self._selection_changed)
        self.canvas.status.connect(
            lambda t: self.statusBar().showMessage(t))
        self._build_toolbar()
        self._build_palette()
        self._build_properties()
        self._build_schedules()
        main.model.drawing_changed.connect(self._document_replaced)
        self._refresh_side()

    # -- toolbar
    def _act(self, glyph, text, slot, shortcut="", checkable=False):
        a = QAction(icons.icon(glyph), text, self)
        if shortcut:
            a.setShortcut(shortcut)
            text += f" ({shortcut})"
        a.setToolTip(text)
        a.setCheckable(checkable)
        if slot is not None:
            a.triggered.connect(slot)
        return a

    def _build_toolbar(self):
        bar = QToolBar("P&ID", self)
        bar.setMovable(False)
        bar.setIconSize(QSize(20, 20))
        self.addToolBar(bar)
        group = QActionGroup(self)
        self._tool_acts = {}
        for key, glyph, text, sc in (
                ("select", "mdi.cursor-default-outline", "Select / move",
                 "S"),
                ("connect", "mdi.vector-polyline", "Connect ports", "C"),
                ("note", "mdi.format-text", "Note", "T")):
            a = self._act(glyph, text, lambda _=False, k=key:
                          self.set_tool(k), sc, True)
            group.addAction(a)
            bar.addAction(a)
            self._tool_acts[key] = a
        self._tool_acts["select"].setChecked(True)
        bar.addSeparator()
        bar.addWidget(QLabel(" Line "))
        self.line_kind = QComboBox()
        for k, (label, _w, _s) in P.LINE_KINDS.items():
            self.line_kind.addItem(label, k)
        bar.addWidget(self.line_kind)
        self.service = QComboBox()
        for k, (meaning, _c) in P.SERVICES.items():
            self.service.addItem(f"{k} — {meaning}" if k else meaning, k)
        self.service.setToolTip("Service: what flows in the line (colour)")
        bar.addWidget(self.service)
        self.size_edit = QLineEdit()
        self.size_edit.setPlaceholderText("size")
        self.size_edit.setMaximumWidth(56)
        self.size_edit.setToolTip("Nominal size (28, DN25, 1/2\")")
        bar.addWidget(self.size_edit)
        self.material = QComboBox()
        for k, name in P.MATERIAL_CODES.items():
            self.material.addItem(f"{k} {name}".strip() or "—", k)
        bar.addWidget(self.material)
        bar.addSeparator()
        for glyph, text, slot, sc in (
                ("mdi.rotate-right", "Rotate", lambda: self.rotate_selected(
                    90), "R"),
                ("mdi.flip-horizontal", "Mirror", self.mirror_selected,
                 "M"),
                ("mdi.delete-outline", "Delete", self.delete_selected, ""),
                ("mdi.vector-polyline-edit", "Re-route lines",
                 self.reroute, "")):
            a = self._act(glyph, text, slot)
            bar.addAction(a)
        bar.addSeparator()
        u = self.undo.createUndoAction(self, "Undo")
        u.setIcon(icons.icon("mdi.undo"))
        u.setShortcut("Ctrl+Z")
        r = self.undo.createRedoAction(self, "Redo")
        r.setIcon(icons.icon("mdi.redo"))
        r.setShortcut("Ctrl+Y")
        bar.addAction(u)
        bar.addAction(r)
        bar.addSeparator()
        bar.addAction(self._act("mdi.fit-to-page-outline", "Fit sheet",
                                self.canvas.fit, "F"))
        bar.addAction(self._act("mdi.cube-scan", "Start from 3D model",
                                self.from_model))
        bar.addAction(self._act("mdi.check-decagram-outline", "Check",
                                self.show_check))
        bar.addAction(self._act("mdi.file-export-outline", "Export…",
                                self.export, "Ctrl+E"))
        bar.addWidget(QLabel(" Sheet "))
        self.sheet_combo = QComboBox()
        self.sheet_combo.addItems(list(P.SHEETS))
        self.sheet_combo.setCurrentText(self.diagram.sheet)
        self.sheet_combo.currentTextChanged.connect(self._sheet_chosen)
        bar.addWidget(self.sheet_combo)
        self.colour_box = QCheckBox("Colour by service")
        self.colour_box.setChecked(self.diagram.colour_lines)
        self.colour_box.toggled.connect(self._colour_toggled)
        bar.addWidget(self.colour_box)

    def _build_palette(self):
        dock = QDockWidget("Symbols", self)
        dock.setFeatures(QDockWidget.DockWidgetMovable)
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 4, 4, 4)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search symbols…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter_palette)
        lay.addWidget(self.search)
        self.palette = QListWidget()
        self.palette.setIconSize(QSize(36, 36))
        self.palette.itemClicked.connect(self._palette_clicked)
        for group, items in ps.by_group():
            head = QListWidgetItem(group.upper())
            head.setFlags(Qt.NoItemFlags)
            f = head.font()
            f.setBold(True)
            head.setFont(f)
            self.palette.addItem(head)
            for kind, sym in items:
                it = QListWidgetItem(symbol_icon(kind), sym.label)
                it.setData(Qt.UserRole, kind)
                it.setToolTip(sym.description or sym.label)
                self.palette.addItem(it)
        lay.addWidget(self.palette)
        hint = QLabel("Click a symbol, then click the sheet. Connect: "
                      "click a port, waypoints, the other port.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray")
        lay.addWidget(hint)
        dock.setWidget(w)
        dock.setMinimumWidth(220)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)

    def _filter_palette(self, text):
        text = text.lower().strip()
        for i in range(self.palette.count()):
            it = self.palette.item(i)
            kind = it.data(Qt.UserRole)
            if kind is None:
                it.setHidden(bool(text))
                continue
            sym = ps.SYMBOLS[kind]
            hay = f"{sym.label} {sym.group} {sym.prefix} {kind} " \
                  f"{sym.description}".lower()
            it.setHidden(bool(text) and text not in hay)

    def _palette_clicked(self, item):
        kind = item.data(Qt.UserRole)
        if kind is None:
            return
        self.canvas.place_kind = kind
        self.set_tool("place")
        self.statusBar().showMessage(
            f"Click the sheet to place {ps.SYMBOLS[kind].label}; Esc "
            "stops.")

    def _build_properties(self):
        dock = QDockWidget("Properties", self)
        dock.setFeatures(QDockWidget.DockWidgetMovable)
        self.props = QWidget()
        self.props_layout = QFormLayout(self.props)
        dock.setWidget(self.props)
        dock.setMinimumWidth(280)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        self._prop_widgets = {}

    def _build_schedules(self):
        dock = QDockWidget("Schedules", self)
        dock.setFeatures(QDockWidget.DockWidgetMovable)
        self.tabs = QTabWidget()
        self.tables = {}
        for name in ("Equipment", "Valves", "Instruments", "Lines"):
            t = QTableWidget()
            t.setEditTriggers(QAbstractItemView.NoEditTriggers)
            t.setSelectionBehavior(QAbstractItemView.SelectRows)
            t.cellDoubleClicked.connect(
                lambda r, _c, n=name: self._schedule_pick(n, r))
            self.tables[name] = t
            self.tabs.addTab(t, name)
        self.check_list = QListWidget()
        self.tabs.addTab(self.check_list, "Check")
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.addWidget(self.tabs)
        row = QHBoxLayout()
        row.addStretch(1)
        b = QPushButton("Export schedules…")
        b.clicked.connect(self.export_schedules)
        row.addWidget(b)
        lay.addLayout(row)
        dock.setWidget(w)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)
        dock.setMinimumHeight(170)

    # -- state
    def commit(self, label="Edit"):
        if self._restoring:
            return
        after = self.diagram.to_dict()
        if after == self._state:
            self._refresh_side()
            return
        self.undo.push(_StateCommand(self, self._state, after, label))
        self._state = after
        self._save()
        self._refresh_side()
        self.canvas.update()

    def replace(self, diagram, label="Edit"):
        """A whole new diagram (MCP, From model) — one undo step."""
        self.diagram = diagram
        self.canvas.selection = [i for i in self.canvas.selection
                                 if self._exists(i)]
        self.sheet_combo.blockSignals(True)
        self.sheet_combo.setCurrentText(diagram.sheet)
        self.sheet_combo.blockSignals(False)
        self.commit(label)

    def restore(self, state):
        self._restoring = True
        try:
            self.diagram = P.Diagram(state)
            self._state = copy.deepcopy(state)
            self.canvas.selection = [i for i in self.canvas.selection
                                     if self._exists(i)]
            self._save()
            self._refresh_side()
            self.canvas.update()
        finally:
            self._restoring = False

    def _exists(self, oid):
        return any(o["id"] == oid for o in self.diagram.symbols +
                   self.diagram.lines + self.diagram.notes)

    def _save(self):
        self._saving = True
        try:
            self.main.model.pid = self.diagram.to_dict()
            _dirty(self.main)
        finally:
            self._saving = False

    def _document_replaced(self):
        """Another document opened (or New): show its diagram."""
        if self._saving:
            return
        pid = self.main.model.pid
        if pid == self._state:
            return
        self.diagram = P.Diagram(pid or {"fields":
                                         _default_fields(self.main)})
        self._state = self.diagram.to_dict()
        self.undo.clear()
        self.canvas.selection = []
        self._refresh_side()
        self.canvas.update()

    # -- commands
    def set_tool(self, key):
        self.canvas.tool = key
        self.canvas._connect = None
        if key in self._tool_acts:
            self._tool_acts[key].setChecked(True)
        else:
            for a in self._tool_acts.values():
                a.setChecked(False)
        self.canvas.setCursor(Qt.CrossCursor if key != "select"
                              else Qt.ArrowCursor)
        self.canvas.update()

    def finish_connect(self, pending, end):
        try:
            ln = self.diagram.connect(
                pending["from"], end, self.line_kind.currentData(),
                self.service.currentData(), self.size_edit.text().strip(),
                self.material.currentData(),
                points=self._with_ends(pending, end)
                if pending["points"] else None)
        except P.PidError as exc:
            QMessageBox.warning(self, "P&ID", str(exc))
            return
        self.canvas.selection = [ln["id"]]
        self.commit("Connect")
        self._selection_changed()

    def _with_ends(self, pending, end):
        (p0, _d0) = self.diagram.port(pending["from"])
        (p1, _d1) = self.diagram.port(end)
        pts = [list(p0)] + [list(p) for p in pending["points"]] + \
            [list(p1)]
        # square every leg: a bend where two points are not aligned
        out = [pts[0]]
        for p in pts[1:]:
            last = out[-1]
            if abs(last[0] - p[0]) > 1e-6 and abs(last[1] - p[1]) > 1e-6:
                out.append([p[0], last[1]])
            out.append(p)
        return out

    def delete_selected(self):
        if not self.canvas.selection:
            return
        self.diagram.remove(self.canvas.selection)
        self.canvas.selection = []
        self.commit("Delete")

    def rotate_selected(self, deg=90):
        hit = False
        for s in self.diagram.symbols:
            if s["id"] in self.canvas.selection:
                self.diagram.set_symbol(s["id"], rot=s.get("rot", 0) + deg)
                hit = True
        if hit:
            self.commit("Rotate")

    def mirror_selected(self):
        hit = False
        for s in self.diagram.symbols:
            if s["id"] in self.canvas.selection:
                self.diagram.set_symbol(s["id"],
                                        mirror=not s.get("mirror"))
                hit = True
        if hit:
            self.commit("Mirror")

    def reroute(self):
        for ln in self.diagram.lines:
            if not self.canvas.selection or ln["id"] in \
                    self.canvas.selection:
                ln["auto"] = True
        self.diagram.reroute()
        self.commit("Re-route")

    def _sheet_chosen(self, name):
        self.diagram.sheet = name
        self.commit("Sheet size")
        self.canvas.fit()

    def _colour_toggled(self, on):
        self.diagram.colour_lines = bool(on)
        self.commit("Line colours")

    def from_model(self):
        if self.diagram.symbols and QMessageBox.question(
                self, "P&ID", "Start again from the 3D model? The symbols "
                "on this sheet are replaced (Undo brings them back).") \
                != QMessageBox.Yes:
            return
        d = P.Diagram({"sheet": self.diagram.sheet,
                       "fields": self.diagram.fields})
        d, found = P.from_model(self.main.model, d)
        self.replace(d, "Start from model")
        self.statusBar().showMessage(
            f"{len(found)} parts recognised — arrange them and connect "
            "their ports.", 10000)

    def show_check(self):
        self.tabs.setCurrentWidget(self.check_list)
        problems = self.diagram.check()
        self.statusBar().showMessage(
            "No problems found." if not problems else
            f"{len(problems)} problem(s) — see the Check tab.", 8000)

    def export(self):
        stem = self.diagram.fields.get("number") or "PID"
        path, _f = QFileDialog.getSaveFileName(
            self, "Export P&ID", str(Path.home() / "Documents" / stem) +
            ".pdf", "PDF (*.pdf);;DXF for CAD (*.dxf);;SVG (*.svg);;"
            "PNG (*.png)")
        if not path:
            return
        try:
            R.export(self.diagram, path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "P&ID", str(exc))
            return
        self.statusBar().showMessage(f"Written {path}", 8000)

    def export_schedules(self):
        stem = (self.diagram.fields.get("number") or "PID") + " schedules"
        path, _f = QFileDialog.getSaveFileName(
            self, "Export schedules", str(Path.home() / "Documents" /
                                          stem) + ".xlsx",
            "Excel workbook (*.xlsx);;CSV (*.csv)")
        if not path:
            return
        try:
            R.export_schedules(self.diagram, path)
        except OSError as exc:
            QMessageBox.warning(self, "P&ID", str(exc))
            return
        self.statusBar().showMessage(f"Written {path}", 8000)

    # -- side panels
    def _refresh_side(self):
        self._fill_schedules()
        self._fill_properties()

    def _fill_schedules(self):
        rows = R.schedule_rows(self.diagram)
        for name, table in self.tables.items():
            data = rows[name]
            table.clear()
            table.setColumnCount(len(data[0]))
            table.setHorizontalHeaderLabels(data[0])
            table.setRowCount(len(data) - 1)
            for r, row in enumerate(data[1:]):
                for c, v in enumerate(row):
                    table.setItem(r, c, QTableWidgetItem(str(v)))
            table.resizeColumnsToContents()
            self.tabs.setTabText(list(self.tables).index(name),
                                 f"{name} ({len(data) - 1})")
        self.check_list.clear()
        problems = self.diagram.check()
        for p in problems or ["No problems."]:
            self.check_list.addItem(p)
        self.tabs.setTabText(4, f"Check ({len(problems)})")

    def _schedule_pick(self, name, row):
        table = self.tables[name]
        key = table.item(row, 0).text() if table.item(row, 0) else ""
        for o in self.diagram.symbols + self.diagram.lines:
            if key and key in (o.get("tag"), o.get("number")):
                self.canvas.selection = [o["id"]]
                self._selection_changed()
                self.canvas.update()
                return

    def _selection_changed(self):
        self._fill_properties()
        self._select_in_model()
        self.canvas.update()

    def _select_in_model(self):
        names = []
        for s in self.diagram.symbols:
            if s["id"] in self.canvas.selection and s.get("node"):
                names.append(s["node"])
        if not names:
            return
        from .model import name_tag
        hits = [n for n in self.main.model.root.walk()
                if n.name in names or name_tag(n.name) in names]
        if hits:
            try:
                self.main.builder.active_tree().select_nodes(hits[:20])
            except Exception:                      # noqa: BLE001
                pass

    def focus_property(self, key):
        w = self._prop_widgets.get(key)
        if w is not None:
            w.setFocus()
            if isinstance(w, QLineEdit):
                w.selectAll()

    def _clear_props(self):
        while self.props_layout.rowCount():
            self.props_layout.removeRow(0)
        self._prop_widgets = {}

    def _line_edit(self, key, value, apply):
        e = QLineEdit(str(value or ""))
        e.editingFinished.connect(lambda: apply(e.text()))
        self._prop_widgets[key] = e
        return e

    def _fill_properties(self):
        self._filling = True
        try:
            self._clear_props()
            sel = self.canvas.selection
            d = self.diagram
            obj = None
            if len(sel) == 1:
                for o in d.symbols + d.lines + d.notes:
                    if o["id"] == sel[0]:
                        obj = o
            if obj is None:
                self._sheet_props()
            elif "kind" in obj and obj["kind"] in ps.SYMBOLS and \
                    "x" in obj and obj in d.symbols:
                self._symbol_props(obj)
            elif obj in d.lines:
                self._line_props(obj)
            else:
                self._note_props(obj)
        finally:
            self._filling = False

    def _set_and_commit(self, fn, label):
        if self._filling:
            return
        try:
            fn()
        except P.PidError as exc:
            QMessageBox.warning(self, "P&ID", str(exc))
            return
        self.commit(label)
        self.canvas.update()

    def _sheet_props(self):
        lay = self.props_layout
        lay.addRow(QLabel("<b>Sheet</b> — select a symbol or line to "
                          "edit it"))
        f = self.diagram.fields
        for key, label in (("title", "Title"), ("number", "Drawing no."),
                           ("revision", "Revision"), ("project", "Project"),
                           ("company", "Company"), ("drawn", "Drawn"),
                           ("checked", "Checked"), ("approved", "Approved"),
                           ("date", "Date"), ("standard", "Standard")):
            lay.addRow(label, self._line_edit(
                key, f.get(key, ""), lambda v, k=key: self._set_and_commit(
                    lambda: f.__setitem__(k, v), "Title block")))
        n = len(self.diagram.symbols)
        lay.addRow(QLabel(f"{n} symbols, {len(self.diagram.lines)} lines, "
                          f"{len(self.diagram.notes)} notes"))

    def _symbol_props(self, s):
        lay = self.props_layout
        sym = ps.SYMBOLS[s["kind"]]
        d = self.diagram
        lay.addRow(QLabel(f"<b>{sym.label}</b>"))
        kind = QComboBox()
        for k, other in ps.SYMBOLS.items():
            if other.group == sym.group:
                kind.addItem(other.label, k)
        kind.setCurrentIndex(max(0, kind.findData(s["kind"])))
        kind.currentIndexChanged.connect(lambda _i: self._set_and_commit(
            lambda: d.set_symbol(s["id"], kind=kind.currentData()),
            "Change symbol"))
        lay.addRow("Symbol", kind)
        for key, label in (("tag", "Tag"), ("label", "Description")):
            lay.addRow(label, self._line_edit(
                key, s.get(key, ""), lambda v, k=key: self._set_and_commit(
                    lambda: d.set_symbol(s["id"], **{k: v}), "Edit " + k)))
        rot = QComboBox()
        rot.addItems(["0", "90", "180", "270"])
        rot.setCurrentText(str(s.get("rot", 0)))
        rot.currentTextChanged.connect(lambda t: self._set_and_commit(
            lambda: d.set_symbol(s["id"], rot=int(t)), "Rotate"))
        lay.addRow("Rotation", rot)
        mir = QCheckBox()
        mir.setChecked(bool(s.get("mirror")))
        mir.toggled.connect(lambda on: self._set_and_commit(
            lambda: d.set_symbol(s["id"], mirror=on), "Mirror"))
        lay.addRow("Mirrored", mir)
        part = QComboBox()
        part.setEditable(True)
        part.addItem("")
        for c in self.main.model.all_components():
            part.addItem(c.name)
        part.setCurrentText(s.get("node", ""))
        part.lineEdit().editingFinished.connect(
            lambda: self._set_and_commit(lambda: d.set_symbol(
                s["id"], node=part.currentText()), "Link 3D part"))
        part.activated.connect(lambda _i: self._set_and_commit(
            lambda: d.set_symbol(s["id"], node=part.currentText()),
            "Link 3D part"))
        lay.addRow("3D part", part)
        for field in sym.fields:
            lay.addRow(field.replace("_", " ").capitalize(), self._line_edit(
                "data." + field, (s.get("data") or {}).get(field, ""),
                lambda v, k=field: self._set_and_commit(
                    lambda: d.set_symbol(s["id"], data={k: v}),
                    "Edit data")))
        ports = ", ".join(sorted(ps.SYMBOLS[s["kind"]].ports)) or "none"
        lay.addRow(QLabel(f"Ports: {ports}"))

    def _line_props(self, ln):
        lay = self.props_layout
        d = self.diagram
        lay.addRow(QLabel(f"<b>Line {ln.get('number', '')}</b>"))
        kind = QComboBox()
        for k, (label, _w, _s) in P.LINE_KINDS.items():
            kind.addItem(label, k)
        kind.setCurrentIndex(max(0, kind.findData(ln.get("kind"))))
        kind.currentIndexChanged.connect(lambda _i: self._set_and_commit(
            lambda: d.set_line(ln["id"], kind=kind.currentData()),
            "Line kind"))
        lay.addRow("Kind", kind)
        svc = QComboBox()
        for k, (meaning, _c) in P.SERVICES.items():
            svc.addItem(f"{k} — {meaning}" if k else meaning, k)
        svc.setCurrentIndex(max(0, svc.findData(ln.get("service", ""))))
        svc.currentIndexChanged.connect(lambda _i: self._set_and_commit(
            lambda: d.set_line(ln["id"], service=svc.currentData()),
            "Service"))
        lay.addRow("Service", svc)
        for key, label in (("number", "Line no."), ("size", "Size"),
                           ("material", "Material code"),
                           ("label", "Note")):
            lay.addRow(label, self._line_edit(
                key, ln.get(key, ""), lambda v, k=key: self._set_and_commit(
                    lambda: d.set_line(ln["id"], **{k: v}), "Edit line")))
        for key, label in (("arrow", "Flow arrow"),
                           ("insulated", "Insulated")):
            box = QCheckBox()
            box.setChecked(bool(ln.get(key, key == "arrow")))
            box.toggled.connect(lambda on, k=key: self._set_and_commit(
                lambda: d.set_line(ln["id"], **{k: on}), "Edit line"))
            lay.addRow(label, box)
        b = QPushButton("Re-route automatically")
        b.clicked.connect(self.reroute)
        lay.addRow(b)
        lay.addRow(QLabel(f"Length on sheet {P.length(ln['points']):.0f} "
                          "mm"))

    def _note_props(self, n):
        lay = self.props_layout
        lay.addRow(QLabel("<b>Note</b>"))
        edit = QPlainTextEdit(str(n.get("text", "")))
        edit.setFixedHeight(90)

        def apply():
            n["text"] = edit.toPlainText()
            self.commit("Edit note")
            self.canvas.update()
        b = QPushButton("Apply")
        b.clicked.connect(apply)
        lay.addRow(edit)
        lay.addRow(b)
        size = QSpinBox()
        size.setRange(1, 12)
        size.setValue(int(n.get("size", 3)))
        size.valueChanged.connect(lambda v: self._set_and_commit(
            lambda: n.__setitem__("size", float(v)), "Note size"))
        lay.addRow("Height (mm)", size)


def open_pid(main):
    win = getattr(main, "_pid_window", None)
    if win is None:
        win = main._pid_window = PidWindow(main)
    win.show()
    win.raise_()
    win.activateWindow()
    return win

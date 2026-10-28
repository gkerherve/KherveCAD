"""The TOOL PANEL: one window per tool that says what to do and holds its
options — SolidWorks' PropertyManager, SolidCraft's tool windows
(2026-10-28, the user: "very easy, very descriptive ... I would like this
for many types of tools").

`ToolPanel(window, view, title)` stands BESIDE *view* (over the tree
column) in the main window — on the drawing it hid what to click — or
inside a bare view. It is themed from the app's own tokens (`style.
tokens`), so it looks like the rest of the program in every theme, and is
built from rows:

- `selection(key, caption, empty)` — a box filled by clicks in the view;
  the active one is outlined in the accent colour, a click makes a box
  active (`on_activate`);
- `choice(caption, options, value, on_change)` — a drop-down;
- `number(caption, value, on_change, suffix)` — a spin box;
- `check(caption, value, on_change)`, `section(title)`, `hint(text)`;
- OK / Cancel (`set_ok_enabled`), Enter / Esc are the view's.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtCore import QEvent, QPoint, Qt
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFrame,
                             QGridLayout, QHBoxLayout, QLabel, QLayout,
                             QPushButton, QVBoxLayout, QWidget)

WIDTH = 290


def _qss():
    from .style import tokens
    t = tokens()
    accent = t.get("select", "#2176c7")
    return f"""
QFrame#toolPanel {{ background: {t['card']}; border: 1px solid {t['border']};
    border-radius: 8px; }}
QFrame#toolPanel QLabel {{ color: {t['text']}; background: transparent; }}
QLabel#toolTitle {{ font-weight: 700; font-size: 14px; }}
QLabel#toolHint {{ color: {t['icon']}; }}
QLabel#toolSection {{ font-weight: 700; color: {t['icon']};
    letter-spacing: 1px; }}
QFrame#toolBox {{ background: {t['editor']}; border: 1px solid {t['border']};
    border-radius: 6px; }}
QLabel#toolBoxCaption {{ font-weight: 700; }}
QPushButton#toolOk {{ background: {accent}; color: white; border: none;
    border-radius: 5px; padding: 6px 18px; font-weight: 700; }}
QPushButton#toolOk:disabled {{ background: {t['border']};
    color: {t['card']}; }}
QPushButton#toolCancel {{ background: {t['window']}; color: {t['text']};
    border: 1px solid {t['border']}; border-radius: 5px;
    padding: 6px 14px; }}
QPushButton#toolCancel:hover {{ background: {t['hover']}; }}
"""


class _Box(QFrame):
    """A selection box: caption and what it holds; a click activates."""

    def __init__(self, panel, key, caption, on_activate):
        super().__init__(panel)
        self.key, self._on_activate = key, on_activate
        self.setObjectName("toolBox")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 5, 8, 6)
        lay.setSpacing(2)
        self.caption = QLabel(caption, self)
        self.caption.setObjectName("toolBoxCaption")
        self.body = QLabel(self)
        self.body.setWordWrap(True)
        self.body.setFixedWidth(WIDTH - 44)
        lay.addWidget(self.caption)
        lay.addWidget(self.body)
        self.setCursor(Qt.PointingHandCursor)

    def set_text(self, text):
        self.body.setText(text)

    def set_active(self, on):
        # its own small stylesheet: re-polishing through self.style()
        # handed PyQt the panel's style-sheet style, which Qt replaces
        # when a sheet is set again — the stale handle crashed PyQt's
        # clean-up at exit
        if on:
            from .style import tokens
            t = tokens()
            self.setStyleSheet(
                "QFrame#toolBox { border: 2px solid %s; background: %s; }"
                % (t.get("select", "#2176c7"), t["hover"]))
        else:
            self.setStyleSheet("")

    def mousePressEvent(self, event):
        if self._on_activate is not None:
            self._on_activate(self.key)
        event.accept()


class ToolPanel(QFrame):
    """A tool's window: title, rows, OK / Cancel."""

    def __init__(self, view, title, on_ok=None, on_cancel=None):
        win = view.window()
        # the drawing area: a QGraphicsView's viewport, else the widget
        # itself (the 3D view)
        area = view.viewport() if hasattr(view, "viewport") else view
        self._beside = win is not None and win is not view
        super().__init__(win if self._beside else area)
        self.view, self.area = view, area
        self.setObjectName("toolPanel")
        self.setStyleSheet(_qss())
        self.boxes, self.fields, self._rows = {}, {}, {}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 12)
        lay.setSpacing(7)
        lay.setSizeConstraint(QLayout.SetFixedSize)   # always fits
        self.title = QLabel(title, self)
        self.title.setObjectName("toolTitle")
        lay.addWidget(self.title)
        self._body = lay
        self._grid = None
        row = QHBoxLayout()
        row.addStretch(1)
        self.cancel = QPushButton("Cancel", self)
        self.cancel.setObjectName("toolCancel")
        self.ok = QPushButton("OK", self)
        self.ok.setObjectName("toolOk")
        for b in (self.cancel, self.ok):
            b.setFocusPolicy(Qt.NoFocus)          # keys stay with the view
            b.setCursor(Qt.PointingHandCursor)
            row.addWidget(b)
        if on_ok is not None:
            self.ok.clicked.connect(on_ok)
        if on_cancel is not None:
            self.cancel.clicked.connect(on_cancel)
        self._buttons = row
        self.hide()
        area.installEventFilter(self)
        if self._beside:
            self.parentWidget().installEventFilter(self)

    # ------------------------------------------------------------ rows
    def hint(self, text):
        label = QLabel(text, self)
        label.setObjectName("toolHint")
        label.setWordWrap(True)
        label.setFixedWidth(WIDTH - 24)
        self._body.addWidget(label)
        self._grid = None
        return label

    def section(self, title):
        label = QLabel(title.upper(), self)
        label.setObjectName("toolSection")
        self._body.addWidget(label)
        self._grid = None
        return label

    def selection(self, key, caption, empty="", on_activate=None):
        box = _Box(self, key, caption, on_activate)
        box.set_text(empty)
        self._body.addWidget(box)
        self.boxes[key] = box
        self._grid = None
        return box

    def _grid_row(self, caption, widget, key):
        if self._grid is None:
            holder = QWidget(self)
            self._grid = QGridLayout(holder)
            self._grid.setContentsMargins(0, 0, 0, 0)
            self._grid.setHorizontalSpacing(10)
            self._grid.setVerticalSpacing(6)
            self._grid.setColumnMinimumWidth(1, 150)
            self._body.addWidget(holder)
        r = self._grid.rowCount()
        label = QLabel(caption, self)
        self._grid.addWidget(label, r, 0)
        self._grid.addWidget(widget, r, 1)
        self.fields[key] = widget
        self._rows[key] = (label, widget)
        return widget

    def choice(self, key, caption, options, value, on_change):
        """*options* [(value, label)]."""
        combo = QComboBox(self)
        for v, text in options:
            combo.addItem(text, v)
        i = max(0, combo.findData(value))
        combo.setCurrentIndex(i)
        combo.currentIndexChanged.connect(
            lambda _i: on_change(combo.currentData()))
        return self._grid_row(caption, combo, key)

    def number(self, key, caption, value, on_change, suffix=" mm",
               minimum=0.0, maximum=1e6, step=1.0, decimals=2):
        spin = QDoubleSpinBox(self)
        spin.setRange(minimum, maximum)
        spin.setDecimals(decimals)
        spin.setSingleStep(step)
        spin.setSuffix(suffix)
        spin.setKeyboardTracking(False)        # one change per value typed
        spin.setValue(float(value))
        spin.valueChanged.connect(on_change)
        return self._grid_row(caption, spin, key)

    def check(self, key, caption, value, on_change):
        box = QCheckBox(caption, self)
        box.setChecked(bool(value))
        box.toggled.connect(on_change)
        self._body.addWidget(box)
        self.fields[key] = box
        self._rows[key] = (box, box)
        self._grid = None
        return box

    def finish(self):
        """Adds OK / Cancel under the rows; call once the rows are in."""
        self._body.addLayout(self._buttons)

    # ---------------------------------------------------------- state
    def set_value(self, key, value):
        """Show *value* in a field without calling its handler."""
        w = self.fields.get(key)
        if w is None:
            return
        w.blockSignals(True)
        try:
            if isinstance(w, QDoubleSpinBox):
                w.setValue(float(value))
            elif isinstance(w, QComboBox):
                i = w.findData(value)
                if i >= 0:
                    w.setCurrentIndex(i)
            elif isinstance(w, QCheckBox):
                w.setChecked(bool(value))
        finally:
            w.blockSignals(False)

    def show_row(self, key, on):
        for w in self._rows.get(key, ()):
            w.setVisible(on)

    def set_active(self, key):
        for k, box in self.boxes.items():
            box.set_active(k == key)

    def set_ok_enabled(self, on):
        self.ok.setEnabled(bool(on))

    def open(self):
        self.setStyleSheet(_qss())             # the theme of the moment
        self.show()
        self.adjustSize()
        self.place()

    def place(self):
        if self._beside:
            vp = self.area
            if not vp.isVisible():
                return
            top_left = vp.mapTo(self.parentWidget(), QPoint(0, 0))
            x = top_left.x() - self.width() - 6
            if x >= 0:
                self.move(x, top_left.y() + 8)
            else:
                self.move(top_left.x() + 12, top_left.y() + 12)
        else:
            self.move(12, 12)
        self.raise_()

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Resize, QEvent.Move, QEvent.Show) \
                and self.isVisible():
            self.place()
        return False

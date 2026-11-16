"""The little box that asks for ONE value — a Smart Dimension's size, a
fillet's radius, a text — shown as a POPUP (2026-11-16, the user: a
dimension pressed by accident asks for a value, "I try to click somewhere
else to come out of there but it is not possible and I have to press
enter").

The old QInputDialog was modal: the rest of the window ignored every
click until Enter or Cancel. A popup closes by itself on a click anywhere
else — and counts as Cancel; Enter keeps the value, Esc cancels too.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLineEdit,
                             QPushButton, QVBoxLayout)


def make(parent, title, label, text=""):
    """The popup (not yet shown): `edit` is its line, `result()` the typed
    text once it has closed — None when it was cancelled."""
    dlg = QDialog(parent, Qt.Popup)
    dlg.setObjectName("ValuePopup")
    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(10, 8, 10, 8)
    head = QLabel("<b>%s</b>" % title)
    lay.addWidget(head)
    lay.addWidget(QLabel(label))
    row = QHBoxLayout()
    dlg.edit = QLineEdit(str(text))
    dlg.edit.setMinimumWidth(180)
    dlg.edit.returnPressed.connect(dlg.accept)
    row.addWidget(dlg.edit)
    ok = QPushButton("✓")
    ok.setFixedWidth(34)
    ok.setToolTip("Keep this value (Enter)")
    ok.clicked.connect(dlg.accept)
    row.addWidget(ok)
    lay.addLayout(row)
    hint = QLabel("Esc or a click elsewhere cancels")
    hint.setStyleSheet("color: #777; font-size: 11px;")
    lay.addWidget(hint)
    dlg.edit.selectAll()
    dlg.result = lambda: (dlg.edit.text().strip()
                          if dlg.result_code == QDialog.Accepted
                          and dlg.edit.text().strip() else None)
    dlg.result_code = QDialog.Rejected
    dlg.finished.connect(lambda code: setattr(dlg, "result_code", code))
    return dlg


def ask(parent, title, label, text=""):
    """Ask for a value next to the mouse; the text, or None (Esc, a
    click elsewhere, an empty box)."""
    dlg = make(parent, title, label, text)
    dlg.adjustSize()
    pos = QCursor.pos()
    dlg.move(pos.x() - 20, pos.y() + 12)
    dlg.show()
    dlg.edit.setFocus()
    dlg.exec_()
    return dlg.result()

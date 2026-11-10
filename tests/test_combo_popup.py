# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""Every combo box drops its whole list below itself, and the arrows
of combos and spin boxes are drawn, in every theme and window style
(the user could see one row of a Fillet's Kind list)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import (QApplication, QComboBox, QFormLayout,
                             QSpinBox, QWidget)

from khervecad import interface_windows, style


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("theme", ["Light", "Dark"])
@pytest.mark.parametrize("look", [None, "Fusion", "SolidWorks"])
def test_combo_list_drops_below_with_every_row(app, theme, look):
    saved = app.styleSheet()
    old = style._current
    try:
        style._current = theme
        interface_windows.apply_stylesheet(look, theme == "Dark")
        sheet = app.styleSheet()
        assert "combobox-popup: 0" in sheet
        assert "QComboBox::down-arrow" in sheet
        assert "QSpinBox::up-arrow" in sheet
        w = QWidget()
        form = QFormLayout(w)
        combo = QComboBox()
        combo.addItems(["fillet", "chamfer", "a", "b"])
        combo.setCurrentIndex(1)
        form.addRow("Kind", combo)
        form.addRow("Segments", QSpinBox())
        w.show()
        QTest.qWait(20)
        combo.showPopup()
        QTest.qWait(20)
        view = combo.view()
        popup = view.window()
        below = combo.mapToGlobal(combo.rect().bottomLeft()).y()
        assert popup.geometry().top() >= below - 1
        rows = view.sizeHintForRow(0)
        assert view.height() >= 4 * rows
        combo.hidePopup()
        w.close()
    finally:
        style._current = old
        app.setStyleSheet(saved)

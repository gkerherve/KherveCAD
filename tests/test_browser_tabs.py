"""Hiding the Variables / Code tabs and the detached, live Code window.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import QApplication

from khervecad import browser_tabs
from khervecad.model import DocumentModel
from khervecad.treepanel import BuilderPanel


_APP = QApplication.instance() or QApplication([])


def _panel():
    return BuilderPanel(DocumentModel())


def test_variables_and_code_start_hidden_and_come_back():
    QSettings("Kherve", "KherveCAD").remove(browser_tabs.SETTING)
    panel = _panel()
    code = panel.indexOf(panel._code_page)
    assert not panel.isTabVisible(code)
    assert not panel.isTabVisible(panel.indexOf(panel.variables))
    browser_tabs.show_tab(panel, "code", True, current=True)
    assert panel.isTabVisible(code)
    assert panel.currentWidget() is panel._code_page


def test_detached_code_keeps_changing():
    panel = _panel()
    browser_tabs.detach(panel)
    assert browser_tabs.is_detached(panel)
    assert panel.indexOf(panel._code_page) < 0
    panel.setCurrentIndex(0)                 # Main in front
    panel.model.add_node("cube", dict(size_x=7))
    assert "cube(" in panel.code.toPlainText()
    browser_tabs.attach(panel)
    assert panel.indexOf(panel._code_page) >= 0
    assert not browser_tabs.is_detached(panel)


def test_history_switch_in_both_tabs():
    from khervecad import tree_history
    panel = _panel()
    try:
        panel.object_tab.history_btn.setChecked(True)
        assert panel.history_btn.isChecked() and tree_history.enabled()
        panel.history_btn.setChecked(False)
        assert not panel.object_tab.history_btn.isChecked()
    finally:
        tree_history.set_enabled(False)

"""Which ribbon tabs show (2026-11-10, the user: "way too many").

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import QApplication

from khervecad import ribbon_tabs, toolbar_style
from khervecad.mainwindow import MainWindow


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(app):
    settings = QSettings("Kherve", "KherveCAD")
    settings.remove(ribbon_tabs.SETTING)          # a user's first start
    w = MainWindow()
    toolbar_style.apply(w, "SolidWorks")
    yield w
    toolbar_style.apply(w, "KherveCAD")
    w._dirty = False
    w.close()
    settings.setValue(ribbon_tabs.SETTING, "none")


def _shown(rb):
    return [rb.order[i][0] for i in range(rb.tabs.count())
            if rb.tabs.isTabVisible(i)]


def test_the_usual_tabs_show_and_the_rest_are_a_tick_away(win):
    rb = win.ribbon
    assert _shown(rb) == ["features", "sketch", "surface", "sheetmetal",
                          "inspect", "library", "publish"]
    menu = ribbon_tabs.menu(rb)
    ticks = {a.text(): a for a in menu.actions() if a.isCheckable()}
    assert not ticks["Sculpt"].isChecked() and ticks["Features"].isChecked()
    assert not ticks["Features"].isEnabled()      # always there
    ticks["Sculpt"].setChecked(True)
    assert "form" in _shown(rb)
    assert rb.order[rb.tabs.currentIndex()][0] == "form"   # and opened
    assert "form" not in ribbon_tabs.hidden()     # remembered


def test_unticking_the_open_tab_goes_to_one_that_shows(win):
    rb = win.ribbon
    rb.show_tab("publish")
    ribbon_tabs.set_shown(rb, "publish", False)
    assert "publish" not in _shown(rb)
    assert rb.order[rb.tabs.currentIndex()][0] in _shown(rb)


def test_a_command_of_a_hidden_tab_shows_it_for_the_session(win):
    rb = win.ribbon
    assert "utilities" not in _shown(rb)
    rb.show_tab("utilities")                      # the search box does this
    assert "utilities" in _shown(rb)
    assert "utilities" in ribbon_tabs.hidden()    # not remembered


def test_every_tab_and_the_usual_ones(win):
    rb = win.ribbon
    menu = ribbon_tabs.menu(rb)
    by = {a.text(): a for a in menu.actions()}
    by["Show every tab"].trigger()
    assert len(_shown(rb)) == len(rb.order)
    by["Show the usual tabs"].trigger()
    assert len(_shown(rb)) == len(rb.order) - len(ribbon_tabs.DEFAULT_HIDDEN)


def test_the_tabs_have_a_button_and_a_right_click_menu(win):
    from PyQt5.QtCore import Qt
    rb = win.ribbon
    assert rb.more_tabs.text() == "⋯"
    assert rb.tabs.contextMenuPolicy() == Qt.CustomContextMenu

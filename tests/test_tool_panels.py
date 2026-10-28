"""The tool windows (tool_panel.py): Extrude's, by mouse and keyboard in
the real window; Mirror Entities' look.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import QPoint, QRect, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

import test_lever_by_mouse as L
from khervecad import drag_feature, extrude_panel

win = L.win                                     # the same window fixture


def _rect_extrude(w):
    L._open_top_sketch(w)
    w.view2d.set_tool("rect")
    L._drag(w.view2d.viewport(), L._at(w, 0, 0), L._at(w, 30, 20))
    L._extruded_boss(w)
    QTest.qWait(50)
    panel = extrude_panel._panel(w)
    assert panel is not None and panel.isVisible()
    return panel, panel.ext


def _type(spin, text):
    spin.setFocus()
    spin.selectAll()
    QTest.keyClicks(spin, text)
    QTest.keyClick(spin, Qt.Key_Return)
    QTest.qWait(30)


def _choose(combo, label):
    combo.setCurrentIndex(combo.findText(label))
    QTest.qWait(30)


def test_the_extrude_window_opens_beside_the_3d_view_in_the_theme(win):
    from khervecad.style import tokens
    panel, ext = _rect_extrude(win)
    assert panel.title.text() == "Extrude"
    vp = win.view3d
    view_rect = QRect(vp.mapTo(win, QPoint(0, 0)), vp.size())
    assert not panel.geometry().intersects(view_rect)
    assert tokens()["card"] in panel.styleSheet()     # the app's colours
    assert "rgba(32, 38, 46" not in panel.styleSheet()
    assert "region" in panel.boxes["profiles"].body.text() or \
        "Rectangle" in panel.boxes["profiles"].body.text()


def test_typing_the_distance_and_choosing_the_direction(win):
    panel, ext = _rect_extrude(win)
    _type(panel.fields["height"], "12")
    assert ext.params["height"] == pytest.approx(12)
    _choose(panel.fields["direction"], "Symmetric")
    assert ext.params["center"] is True
    _choose(panel.fields["direction"], "Two sides")
    assert not ext.params["center"]
    assert panel.fields["height2"].isVisible()
    _type(panel.fields["height2"], "5")
    assert ext.params["height2"] == pytest.approx(5)
    _choose(panel.fields["direction"], "One side")
    assert ext.params["height2"] == 0 and not panel.fields["height2"].isVisible()
    QTest.mouseClick(panel.fields["reverse"], Qt.LeftButton)
    assert drag_feature.reversed_of(ext) is not None
    assert extrude_panel._panel(win) is panel          # still open
    QTest.mouseClick(panel.fields["reverse"], Qt.LeftButton)
    assert drag_feature.reversed_of(ext) is None
    _choose(panel.fields["extent"], "Through all")
    assert ext.params["extent"] == "through_all"
    assert not panel.fields["height"].isEnabled()


def test_dragging_the_arrow_updates_the_distance_field(win):
    panel, ext = _rect_extrude(win)
    L._drag_arrow(win, 8.0)
    assert ext.params["height"] == pytest.approx(8)
    assert panel.fields["height"].value() == pytest.approx(8)


def test_cancel_takes_a_new_extrude_back(win):
    panel, ext = _rect_extrude(win)
    _type(panel.fields["height"], "7")
    QTest.mouseClick(panel.cancel, Qt.LeftButton)
    QTest.qWait(50)
    assert not any(n.type == "linear_extrude"
                   for n in win.model.root.walk())
    assert extrude_panel._panel(win) is None


def test_ok_keeps_it_and_closes(win):
    panel, ext = _rect_extrude(win)
    _type(panel.fields["height"], "7")
    QTest.mouseClick(panel.ok, Qt.LeftButton)
    QTest.qWait(50)
    assert extrude_panel._panel(win) is None
    assert any(n is ext for n in win.model.root.walk())
    assert ext.params["height"] == pytest.approx(7)


def test_reverse_keeps_the_window_open(win):
    panel, ext = _rect_extrude(win)
    QTest.mouseClick(panel.fields["reverse"], Qt.LeftButton)
    QTest.qWait(50)
    assert extrude_panel._panel(win) is panel and panel.isVisible()
    assert drag_feature.reversed_of(ext) is not None
    assert win.view3d.edit_tool is panel.tool

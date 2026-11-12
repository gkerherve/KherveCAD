"""What pressing every button of the Evaluate tab by hand turned up
(2026-11-12, the user: "look at the Evaluate ribbon ... check them
manually and see if they work like they are supposed to for a human ...
also the surface icons seem to have changed").

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import QEvent, QPoint, QPointF, Qt
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from khervecad import analysis, analysis_dialog, ribbon, toolbar_style
from khervecad.mcp_tools import McpToolExecutor


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(app):
    from khervecad.mainwindow import MainWindow
    w = MainWindow()
    w.resize(1500, 950)
    toolbar_style.apply(w, "SolidWorks", remember=False)
    w.show()
    QTest.qWait(50)
    yield w
    toolbar_style.apply(w, "KherveCAD", remember=False)
    w._dirty = False
    w.close()


def _build(win, code):
    McpToolExecutor(win).execute("apply_code", {"code": code})
    QTest.qWait(150)


def _named(win, name):
    for panel in ("analyse", "checks", "dimension"):
        for act in ribbon.panel_actions(win, panel)[1]:
            if act.text().replace("\n", " ").replace("&", "") == name:
                return act
    raise AssertionError(name)


def _click(view, world):
    q = view._project(*view._camera(), world)
    p = QPoint(int(q[0]), int(q[1]))
    QApplication.sendEvent(view, QMouseEvent(
        QEvent.MouseMove, QPointF(p), Qt.NoButton, Qt.NoButton,
        Qt.NoModifier))
    QTest.mouseClick(view, Qt.LeftButton, Qt.NoModifier, p)
    QTest.qWait(250)


def test_surface_icons_stay_painted_when_the_panels_are_read_again(win):
    """The search box reads every panel again: the Surfaces buttons went
    back to blue glyphs (and their long menu names)."""
    acts = ribbon.panel_actions(win, "surfaces")[1]
    assert len(acts) == 6
    before = [a.icon().cacheKey() for a in acts]
    again = ribbon.panel_actions(win, "surfaces")[1]
    assert [a.icon().cacheKey() for a in again] == before
    assert all(a.property("kc_painted") == "SolidWorks" for a in again)


def test_measure_on_evaluate_measures_in_the_3d_view(win):
    """It chose the 2D sketch ruler, whose view is not on show: nothing
    happened. Now: click a face, then another, read the distance."""
    _build(win, "cube([40, 30, 20]); // Block\n"
                "translate([60, 0, 0]) cylinder(h = 30, r = 10); // Pin\n")
    _named(win, "Measure").trigger()
    QTest.qWait(100)
    view = win.view3d
    assert view._pick_cb is not None and "Measure" in view._pick_banner
    assert win.scene.tool == "select"
    _click(view, (20, 15, 20))
    assert win._measure["result"]["text"][0].startswith("Face area: 1200")
    _click(view, (60, 0, 30))
    text = win._measure["result"]["text"]
    assert text[0].startswith("Face to face: 10 ")
    card = win._measure["card"]
    assert card.isVisible() and card.y() >= 120       # under the view cube


def test_measure_with_no_part_says_so(win):
    _named(win, "Measure").trigger()
    QTest.qWait(50)
    assert win.view3d._pick_cb is None
    assert "no part" in win.statusBar().currentMessage()


def test_mass_window_without_a_material_does_not_blame_millimetres():
    props = analysis.mass_properties(
        [((0, 0, 0), (1, 0, 0), (0, 1, 0)), ((0, 0, 0), (0, 1, 0), (0, 0, 1)),
         ((0, 0, 0), (0, 0, 1), (1, 0, 0)), ((1, 0, 0), (0, 0, 1), (0, 1, 0))])
    html = analysis_dialog.mass_html(props, "Undefined", 20.0, "€", "mm")
    assert "no printer works" not in html
    assert "choose a material" in html
    # a unit no printer works in still says so
    html = analysis_dialog.mass_html(props, "Undefined", 20.0, "€", "nm")
    assert "no printer works" in html


def test_explode_with_one_part_does_not_stay_lit(win):
    _build(win, "cube([40, 30, 20]); // Block\n")
    act = _named(win, "Explode the Assembly")
    act.trigger()
    QTest.qWait(50)
    assert not act.isChecked() and not win._explode["on"]
    assert "two or more parts" in win.statusBar().currentMessage()


def test_explode_with_two_parts_explodes(win):
    _build(win, "cube([40, 30, 20]); // Block\n"
                "translate([60, 0, 0]) cylinder(h = 30, r = 10); // Pin\n")
    act = _named(win, "Explode the Assembly")
    act.trigger()
    QTest.qWait(50)
    assert act.isChecked() and win._explode["on"]
    act.trigger()


def test_compare_to_reference_without_a_picture_says_what_is_missing(win):
    act = _named(win, "Compare to Reference Image (overlay)")
    was = win.view3d.overlay
    win.view3d.overlay = False
    act.setChecked(False)
    act.trigger()
    QTest.qWait(50)
    assert not act.isChecked() and not win.view3d.overlay
    assert "reference image" in win.statusBar().currentMessage()
    win.view3d.overlay = was


def test_smart_dimension_on_evaluate_is_the_one_that_works_in_3d(win):
    """It was the old 2D Add dimension tool under Smart Dimension's
    name: the window jumped into a Top-plane sketch without a word."""
    acts = ribbon.panel_actions(win, "dimension")[1]
    assert acts[0].data() == "con_dimension"
    assert all(a.data() != "dimension" for a in acts)
    _build(win, "cube([40, 30, 20]); // Block\n")
    acts[0].trigger()
    QTest.qWait(100)
    assert not getattr(win, "_sketching", False)
    assert type(win.view3d.edit_tool).__name__ == "Constrain3D"

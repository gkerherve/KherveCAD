"""Select / stop: the first ribbon button and Esc end any running tool.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from khervecad import stop_tool


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    win.show()
    yield win
    win._dirty = False
    win.close()


def test_stop_ends_a_fillet_pick_and_a_sketch_tool(window):
    m = window.model
    cube = m.add_node("cube")
    window.builder.active_tree().select_nodes([cube])
    window._apply_operation("fillet")
    assert window.view3d._pick_cb is not None
    assert stop_tool.stop(window)
    assert window.view3d._pick_cb is None
    window._set_tool("con_horizontal")
    stop_tool.stop(window)
    assert window.view2d.scene().tool == "select"


def test_escape_stops_wherever_the_focus_is(window):
    m = window.model
    cube = m.add_node("cube")
    window.builder.active_tree().select_nodes([cube])
    window._apply_operation("fillet")
    window.builder.active_tree().setFocus()
    QApplication.processEvents()
    QTest.keyClick(window.builder.active_tree(), Qt.Key_Escape)
    assert window.view3d._pick_cb is None


def test_select_is_the_first_button_of_every_tab(window):
    from khervecad import ribbon, toolbar_style
    toolbar_style.apply(window, "Fusion")
    try:
        assert stop_tool.action(window).data() == "stop_select"
        from PyQt5.QtWidgets import QToolButton
        for i in range(window.ribbon.stack.count()):
            page = window.ribbon.stack.widget(i)
            buttons = [b for b in page.findChildren(QToolButton)
                       if b.defaultAction() is not None]
            assert buttons and buttons[0].defaultAction().data() == \
                "stop_select"
    finally:
        toolbar_style.apply(window, "KherveCAD")


def test_gumball_moves_the_part_inside_the_object(window):
    """In the Object tab the Gumball climbed to the Object itself, whose
    placement the Object tab does not show: nothing seemed to move."""
    from khervecad import gumball, mates, mesh
    m = window.model
    obj = m.add_node("component", {})
    obj.visible = True
    m.add_node("cube", {}, parent=obj)
    cyl = m.add_node("cylinder", {}, parent=obj)
    QApplication.processEvents()
    window.builder.open_component(obj)
    QApplication.processEvents()
    window.builder.active_tree().select_nodes([cyl])
    QApplication.processEvents()
    g = gumball.Gumball(window)
    target = g.target()
    assert target is cyl
    part = mates.ensure_part(m, target)
    assert part is not obj and part.parent is obj
    before = mesh.tessellate(obj)
    m.set_param(part, "x", 30.0)
    after = mesh.tessellate(obj)
    assert max(v[0] for t in after for v in t) > \
        max(v[0] for t in before for v in t) + 15

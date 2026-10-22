"""Cylinder size handles in the 3D view.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import QEvent, QPointF, Qt
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtWidgets import QApplication

from khervecad import shape_handles

_APP = QApplication.instance() or QApplication([])


@pytest.fixture
def win():
    from khervecad.mainwindow import MainWindow
    w = MainWindow()
    w.resize(1200, 800)
    w.show()
    yield w
    w._dirty = False
    w.close()


def _ev(kind, x, y):
    return QMouseEvent(kind, QPointF(x, y), Qt.LeftButton, Qt.LeftButton,
                       Qt.NoModifier)


def test_dragging_the_height_handle_sets_the_height_on_release(win):
    m = win.model
    cyl = m.add_node("cylinder", dict(height=20, radius_bottom=5,
                                      radius_top=5))
    _APP.processEvents()
    win.builder.active_tree().select_nodes([cyl])
    _APP.processEvents()
    win.view3d.set_view("Front", animate=False)
    _APP.processEvents()
    tool = win.view3d.edit_tool
    assert isinstance(tool, shape_handles.CylinderTool)
    s = tool._project()(tool.points()["height"][0])
    view = win.view3d
    assert tool.mouse_press(_ev(QEvent.MouseButtonPress, s[0], s[1]))
    assert tool.drag["key"] == "height"
    tool.mouse_move(_ev(QEvent.MouseMove, s[0], s[1] - 50))
    assert float(cyl.params["height"]) == 20            # not yet
    want = tool.drag["value"]
    assert want > 20 and round(want, 1) == want
    tool.mouse_release(_ev(QEvent.MouseButtonRelease, s[0], s[1] - 50))
    assert float(cyl.params["height"]) == want
    del view


def test_radius_handles_change_each_radius(win):
    m = win.model
    cyl = m.add_node("cylinder", dict(height=20, radius_bottom=5,
                                      radius_top=5))
    _APP.processEvents()
    win.builder.active_tree().select_nodes([cyl])
    _APP.processEvents()
    tool = win.view3d.edit_tool
    d = dict(start=5.0, px_per_mm=10.0)
    assert tool.value_for("r2", 23.0, d) == 7.3
    assert tool.value_for("r1", -80.0, d) == 0.0
    win.builder.active_tree().select_nodes([])
    _APP.processEvents()
    assert win.view3d.edit_tool is None

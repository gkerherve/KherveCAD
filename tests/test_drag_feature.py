"""Extrude / revolve by dragging the arrow in the 3D view.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import QEvent, QPoint, QPointF, Qt
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtWidgets import QApplication

from khervecad import drag_feature

_APP = QApplication.instance() or QApplication([])


def _ev(kind, x, y, mods=Qt.NoModifier):
    return QMouseEvent(kind, QPointF(x, y), Qt.LeftButton, Qt.LeftButton,
                       mods)


@pytest.fixture
def win():
    from khervecad.mainwindow import MainWindow
    w = MainWindow()
    w.resize(1200, 800)
    w.show()
    yield w
    w._dirty = False
    w.close()


def _drag(tool, scr, pixels):
    a, b = scr["a"], scr["b"]
    import math
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = math.hypot(dx, dy)
    mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    assert tool.mouse_press(_ev(QEvent.MouseButtonPress, *mid))
    tool.mouse_move(_ev(QEvent.MouseMove, mid[0] + dx / n * pixels,
                        mid[1] + dy / n * pixels))
    tool.mouse_release(None)


def test_extrude_shows_an_arrow_that_pulls_the_height(win):
    m = win.model
    rect = m.add_node("rect", dict(width=20, height=10))
    win.builder.tree.select_nodes([rect])
    win._apply_operation("linear_extrude")
    tool = win.view3d.edit_tool
    assert isinstance(tool, drag_feature.DragFeature)
    ext = tool.target()
    assert ext.type == "linear_extrude"
    h0 = float(ext.params["height"])
    scr = tool._screen()
    assert scr["kind"] == "linear"
    _drag(tool, scr, 40)
    assert float(ext.params["height"]) > h0
    _drag(tool, tool._screen(), -5000)
    assert float(ext.params["height"]) == drag_feature.MIN_HEIGHT
    tool.key_press(type("K", (), {"key": lambda self: Qt.Key_Escape})())
    assert win.view3d.edit_tool is None


def test_revolve_arc_sets_the_angle(win):
    m = win.model
    rect = m.add_node("rect", dict(x=5, width=4, height=10))
    win.builder.tree.select_nodes([rect])
    win._apply_operation("rotate_extrude")
    tool = win.view3d.edit_tool
    rev = tool.target()
    assert rev.type == "rotate_extrude"
    m.set_param(rev, "angle", 180)
    scr = tool._screen()
    assert scr["kind"] == "revolve"
    a = scr["a"]
    per = scr["per"]
    import math
    n = math.hypot(*per)
    assert tool.mouse_press(_ev(QEvent.MouseButtonPress, a[0] + per[0] / n
                                * 10, a[1] + per[1] / n * 10))
    tool.mouse_move(_ev(QEvent.MouseMove, a[0] + per[0] / n * 60,
                        a[1] + per[1] / n * 60))
    tool.mouse_release(None)
    assert 180 < float(rev.params["angle"]) <= 360


def test_linear_handle_geometry():
    from khervecad.model import DocumentModel
    m = DocumentModel()
    ext = m.add_node("linear_extrude", dict(height=12))
    m.add_node("rect", dict(width=20, height=10), parent=ext)
    mm, tris = drag_feature.frame(ext)
    base, axis, scale = drag_feature.linear_handle(ext, mm, tris)
    assert base == pytest.approx((10, 5, 12)) and axis == (0, 0, 1)

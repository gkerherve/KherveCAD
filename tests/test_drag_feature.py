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
    # dragged below the sketch: it stops at zero, never goes negative
    _drag(tool, tool._screen(), -5000)
    assert drag_feature.reversed_of(ext) is None
    assert float(ext.params["height"]) == drag_feature.MIN_HEIGHT
    # Cancel (Esc) takes the new extrude away: the rectangle is back
    tool.key_press(type("K", (), {"key": lambda self: Qt.Key_Escape})())
    assert win.view3d.edit_tool is None
    assert rect.parent is m.root and ext.parent is None


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


def test_a_handle_behind_the_camera_never_breaks_the_paint(win):
    """The user's crash: the arrow's point fell behind the camera, the
    projection was None and the paint raised."""
    m = win.model
    rect = m.add_node("rect", dict(width=20, height=10))
    win.builder.tree.select_nodes([rect])
    win._apply_operation("linear_extrude")
    tool = win.view3d.edit_tool
    tool._project = lambda: (lambda p: None)
    assert tool._screen() is None
    from PyQt5.QtGui import QPainter, QPixmap
    pix = QPixmap(50, 50)
    p = QPainter(pix)
    tool.paint(p, None)                         # must not raise
    p.end()
    assert tool.mouse_press(_ev(QEvent.MouseButtonPress, 5, 5)) is False


def test_no_buttons_and_the_arrow_follows_the_selection(win):
    m = win.model
    rect = m.add_node("rect", dict(width=20, height=10))
    other = m.add_node("cube", dict(x=60))
    win.builder.tree.select_nodes([rect])
    win._apply_operation("linear_extrude")
    tool = win.view3d.edit_tool
    ext = tool.target()
    assert tool.buttons == []                   # no OK / Cancel
    _drag(tool, tool._screen(), -5000)          # down: stops at zero
    assert float(ext.params["height"]) == drag_feature.MIN_HEIGHT
    _drag(tool, tool._screen(), 3000)           # and back up
    assert drag_feature.reversed_of(ext) is None
    assert drag_feature.signed_height(ext) > drag_feature.MIN_HEIGHT
    win.builder.tree.select_nodes([other])      # selected away: it goes
    assert win.view3d.edit_tool is None
    assert ext.parent is m.root                 # and the extrude stays
    win.builder.tree.select_nodes([ext])        # selected again: back
    assert isinstance(win.view3d.edit_tool, drag_feature.DragFeature)


def test_clicking_a_flat_shape_in_3d_extrudes_it(win):
    m = win.model
    rect = m.add_node("rect", dict(width=20, height=10))
    win.builder.tree.select_nodes([])
    drag_feature.action(win).trigger()           # nothing selected: pick
    cb = win.view3d._pick_cb
    assert cb is not None
    cb(dict(kind="face", pos=[10, 5, 0], dir=[0, 0, 1]), rect)
    tool = win.view3d.edit_tool
    assert isinstance(tool, drag_feature.DragFeature)
    assert tool.target().type == "linear_extrude"
    assert rect.parent is tool.target()


def test_only_2d_shapes_are_picked_and_an_extruded_one_comes_back(win):
    m = win.model
    m.add_node("cube", dict(width=5, depth=5, height=5))
    tall = m.add_node("linear_extrude", dict(height=30))
    inner = m.add_node("rect", dict(width=10, height=10), parent=tall)
    loose = m.add_node("circle", dict(x=40, radius=4))
    names = {n.name for n, _t in drag_feature.flat_shapes(win)}
    assert names == {inner.name, loose.name}         # no cube
    win.builder.tree.select_nodes([])
    drag_feature.pick(win)
    win.view3d._pick_cb(dict(kind="face", pos=[5, 5, 0], dir=[0, 0, 1]),
                        inner)
    tool = win.view3d.edit_tool
    assert tool.target() is tall and not tool.created
    tool.cancel()                                    # nothing removed
    assert tall.parent is m.root and inner.parent is tall


def test_selecting_an_extrude_shows_its_arrow_and_the_value_types(win):
    m = win.model
    ext = m.add_node("linear_extrude", dict(height=12))
    m.add_node("rect", dict(width=20, height=10), parent=ext)
    other = m.add_node("cube", dict(x=50))
    win.builder.tree.select_nodes([ext])
    tool = win.view3d.edit_tool
    assert isinstance(tool, drag_feature.DragFeature) and tool.auto
    # the value drawn beside the arrow is a box to type in
    from PyQt5.QtGui import QPixmap, QPainter
    pix = QPixmap(win.view3d.size())
    p = QPainter(pix)
    tool.paint(p, None)
    p.end()
    assert tool._label is not None
    centre = tool._label.center()
    assert tool.mouse_press(_ev(QEvent.MouseButtonPress, centre.x(),
                                centre.y()))
    box = tool.editor
    box.setText("25")
    box.returnPressed.emit()
    assert float(ext.params["height"]) == 25
    tool.edit_value().setText("-7.5")            # a minus stops at zero
    tool.editor.returnPressed.emit()
    assert float(ext.params["height"]) == drag_feature.MIN_HEIGHT
    # something else selected: the arrow goes
    win.builder.tree.select_nodes([other])
    assert win.view3d.edit_tool is None


def test_an_arrow_from_selection_makes_way_for_the_gumball(win):
    from khervecad import gumball
    m = win.model
    ext = m.add_node("linear_extrude", dict(height=12))
    m.add_node("rect", dict(width=20, height=10), parent=ext)
    win.builder.tree.select_nodes([ext])
    assert isinstance(win.view3d.edit_tool, drag_feature.DragFeature)
    assert gumball.toggle(win, True)
    assert isinstance(win.view3d.edit_tool, gumball.Gumball)
    gumball.toggle(win, False)


def test_linear_extrude_with_nothing_selected_takes_the_lone_shape(win):
    """One free shape: extruded at once, as a sketch of several is (it
    asked for a click on it in 3D, 2026-10-29)."""
    m = win.model
    poly = m.add_node("polygon", dict(points=[[0, 0], [10, 0], [10, 10]]))
    win.builder.tree.select_nodes([])
    win._apply_operation("linear_extrude")
    assert win.view3d._pick_cb is None
    assert poly.parent.type == "linear_extrude"
    tool = win.view3d.edit_tool
    assert tool.target().type == "linear_extrude" and tool.created
    assert poly.parent is tool.target()
    win.builder.tree.select_nodes([])
    tool.exit()
    win._apply_operation("rotate_extrude")      # revolve the same way
    circle = m.add_node("circle", dict(x=20, radius=3))
    win.view3d._pick_cb(dict(kind="face", pos=[20, 0, 0], dir=[0, 0, 1]),
                        circle)
    assert circle.parent.type == "rotate_extrude"


def test_the_model_changes_only_on_release(win):
    m = win.model
    rect = m.add_node("rect", dict(width=20, height=10))
    win.builder.tree.select_nodes([rect])
    win._apply_operation("linear_extrude")
    tool = win.view3d.edit_tool
    ext = tool.target()
    _drag(tool, tool._screen(), 0)          # settle the first height
    changed = []
    m.node_changed.connect(lambda *a: changed.append(a))
    scr = tool._screen()
    import math
    a, b = scr["a"], scr["b"]
    n = math.hypot(b[0] - a[0], b[1] - a[1])
    mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    tool.mouse_press(_ev(QEvent.MouseButtonPress, *mid))
    tool.mouse_move(_ev(QEvent.MouseMove, mid[0] + (b[0] - a[0]) / n * 60,
                        mid[1] + (b[1] - a[1]) / n * 60))
    assert not changed                       # only the preview grew
    tool.mouse_release(None)
    assert changed and float(ext.params["height"]) > 1

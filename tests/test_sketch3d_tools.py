"""The whole Sketch tab in the 3D view: every tool, by clicks.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtTest import QTest

from khervecad import cut_feature, face_sketch as fs, sketch3d_tools as more
from khervecad import sketch_constraints as sc, sketch_modify as sm
from khervecad import sketch_tools as st, sketch_tools2 as st2
from khervecad.view2d import POLYGON, TEXT
from test_lever_by_mouse import win  # noqa: F401


@pytest.fixture
def sketch(win, monkeypatch):
    from khervecad import sketch3d
    monkeypatch.setattr(cut_feature, "IN_3D", True)
    m = win.model
    part = m.add_node("cube", dict(width=60, depth=60, height=10))
    QTest.qWait(50)
    win.view3d.resize(800, 600)
    win.view3d.set_view("Top", animate=False)
    win.view3d.fit()
    win.view2d.scene().ask_value = lambda k, v: "3" if k != "text" else "Hi"
    tool = sketch3d.start(win, "rect")
    g = fs.make(win, part, (30, 30, 10), (0, 0, 1), open_2d=False)
    tool.use_group(g)
    return tool


CLICKS = {
    st.RECT_CENTER: [(30, 30), (40, 35)],
    st.ARC_CENTER: [(30, 30), (40, 30), (30, 40)],
    st.ARC_3PT: [(20, 30), (40, 30), (30, 40)],
    st.ELLIPSE: [(30, 30), (40, 35)],
    st.SLOT: [(20, 30), (40, 30), (40, 34)],
    st2.CONST_LINE: [(20, 30), (40, 30)],
    st2.POINT: [(20, 30)],
    st2.RECT_3PT: [(20, 20), (40, 20), (40, 30)],
    st2.CIRCLE_2PT: [(20, 20), (40, 20)],
    st2.CIRCLE_3PT: [(20, 20), (40, 20), (30, 35)],
    st2.POLY_REG: [(30, 30), (40, 30)],
    st2.CONIC: [(20, 20), (30, 40), (40, 20)],
}


@pytest.mark.parametrize("tool", sorted(CLICKS))
def test_click_tools_make_a_shape_in_the_sketch(sketch, tool):
    sketch.tool_icon(tool)
    for p in CLICKS[tool]:
        sketch.place(fs.to_local(sketch.group, (*p, 10)))
    assert sketch.group.children
    sketch.finish()


@pytest.mark.parametrize("tool", [st.SPLINE, st2.POLYLINE, st2.BSPLINE,
                                  POLYGON])
def test_any_number_of_clicks_ends_with_enter(sketch, tool):
    from PyQt5.QtCore import QEvent, Qt
    from PyQt5.QtGui import QKeyEvent
    sketch.tool_icon(tool)
    for p in [(20, 20), (40, 20), (40, 40), (20, 45)]:
        sketch.place(fs.to_local(sketch.group, (*p, 10)))
    assert not sketch.group.children
    sketch.key_press(QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier))
    assert sketch.group.children
    sketch.finish()


def test_text(sketch):
    sketch.tool_icon(TEXT)
    sketch.place(fs.to_local(sketch.group, (20, 20, 10)))
    assert sketch.group.children[0].params["text"] == "Hi"
    sketch.finish()


def _lines(sketch, *pairs):
    m = sketch.window.model
    out = [m.add_node("line", dict(x1=a[0], y1=a[1], x2=b[0], y2=b[1],
                                   width=0.2), parent=sketch.group)
           for a, b in pairs]
    QTest.qWait(50)
    return out


def _at(tool, p):
    q = tool._project()((*p, 10))
    return q[0], q[1]


def test_trim_and_extend(sketch):
    a, _b = _lines(sketch, ((10, 30), (50, 30)), ((30, 10), (30, 50)))
    x, y = _at(constrain_tool(sketch, sm.TRIM), (45, 30))
    sketch.view.edit_tool.click(x, y)
    assert max(a.params["x1"], a.params["x2"]) == pytest.approx(30)


def test_extend_to_the_next_line(sketch):
    a, _b = _lines(sketch, ((10, 30), (25, 30)), ((30, 10), (30, 50)))
    tool = constrain_tool(sketch, sm.EXTEND)
    tool.click(*_at(tool, (24, 30)))
    assert max(a.params["x1"], a.params["x2"]) == pytest.approx(30)


def test_sketch_fillet_of_two_lines_and_a_rectangle_corner(sketch):
    m = sketch.window.model
    _lines(sketch, ((10, 10), (30, 10)), ((30, 10), (30, 30)))
    n = len(sketch.group.children)
    tool = constrain_tool(sketch, sm.FILLET)
    tool.click(*_at(tool, (20, 10)))
    tool.click(*_at(tool, (30, 20)))
    assert len(sketch.group.children) > n


def test_mirror_about_a_centerline(sketch):
    from khervecad import sketch_tools2
    a, c = _lines(sketch, ((10, 10), (20, 15)), ((30, 5), (30, 55)))
    sketch_tools2.toggle_construction(sketch.window.model, [c])
    tool = constrain_tool(sketch, "sk_mirror")
    tool.click(*_at(tool, (15, 12.5)))
    tool.click(*_at(tool, (30, 30)))
    assert len(sketch.group.children) == 3


def test_construction_switches(sketch):
    from khervecad import sketch_tools2
    a, = _lines(sketch, ((10, 10), (30, 10)))
    tool = constrain_tool(sketch, "sk_construction")
    tool.click(*_at(tool, (20, 10)))
    assert sketch_tools2.is_construction(a)


def constrain_tool(sketch, name):
    sketch.tool_icon(name)
    return sketch.view.edit_tool


def test_tangent_circle_on_three_lines(sketch):
    _lines(sketch, ((10, 10), (50, 10)), ((50, 10), (30, 40)),
           ((30, 40), (10, 10)))
    sketch.tool_icon(st2.CIRCLE_TAN)
    for p in ((30, 10), (40, 25), (20, 25)):
        sketch.place(fs.to_local(sketch.group, (*p, 10)))
    assert [n for n in sketch.group.children if n.type == "circle"]


def test_a_drawing_tool_with_no_sketch_stays_in_3d(win, monkeypatch):
    from khervecad import sketch3d
    monkeypatch.setattr(cut_feature, "IN_3D", True)
    win.model.add_node("cube", dict(width=60, depth=60, height=10))
    QTest.qWait(50)
    win._set_tool(st.ELLIPSE)
    tool = win.view3d.edit_tool
    assert isinstance(tool, sketch3d.Sketch3DTool)
    assert tool.scene_tool == st.ELLIPSE
    tool.finish()


def test_drawing_tools_work_with_the_extrude_window_open(sketch):
    from khervecad import drag_feature, extrude_panel
    win = sketch.window
    sketch.place(fs.to_local(sketch.group, (10, 10, 10)))
    sketch.place(fs.to_local(sketch.group, (30, 30, 10)))
    ext = win.model.wrap_nodes(list(sketch.group.children), "linear_extrude")
    sketch.finish()
    drag_feature.start(win, ext, quiet=True, panel=True)
    assert extrude_panel._panel(win) is not None
    assert drag_feature.pause_for(win, st.ELLIPSE)
    assert win.view3d.edit_tool.scene_tool == st.ELLIPSE
    win.view3d.edit_tool.finish()

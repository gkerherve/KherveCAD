"""Sketch relations and Smart Dimensions in the 3D view (2026-11-01,
the user: clicking a constraint switched straight to 2D).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtTest import QTest

from test_lever_by_mouse import win  # noqa: F401


def _screen(tool, world):
    q = tool._project()(world)
    return q[0], q[1]


def _setup(win):
    m = win.model
    g = m.add_node("union", {}, name="Sketch")
    line = m.add_node("line", dict(x1=0, y1=0, x2=40, y2=6, width=0.2),
                      parent=g)
    QTest.qWait(50)
    v = win.view3d
    v.resize(800, 600)
    v.set_view("Top", animate=False)
    v.fit()
    return g, line


def test_horizontal_by_a_click_in_3d(win):
    from khervecad import constrain3d
    g, line = _setup(win)
    assert constrain3d.start(win, "con_horizontal")
    tool = win.view3d.edit_tool
    x, y = _screen(tool, (20, 3, 0))
    assert tool.pick_at(x, y)[:2] == (line, "l")       # it lights up
    tool.click(x, y)
    assert line.params["y1"] == pytest.approx(line.params["y2"])
    assert any(r["kind"] == "horizontal" for r in g.params["constraints"])


def test_smart_dimension_in_3d(win):
    from khervecad import constrain3d
    g, line = _setup(win)
    win.view2d.scene().ask_value = lambda kind, measured: "50"
    assert constrain3d.start(win, "con_dimension")
    tool = win.view3d.edit_tool
    x, y = _screen(tool, (10, 1.5, 0))
    tool.click(x, y)
    tool.click(5, 5)                       # empty: the line's length
    p = line.params
    assert ((p["x2"] - p["x1"]) ** 2 + (p["y2"] - p["y1"]) ** 2) ** 0.5 \
        == pytest.approx(50, abs=0.01)


def test_choosing_a_constraint_in_solidworks_stays_in_3d(win):
    from khervecad import constrain3d, sketch_mode
    _setup(win)
    win._interface_style = "SolidWorks"
    sketch_mode.tool_chosen(win, "con_vertical")
    assert isinstance(win.view3d.edit_tool, constrain3d.Constrain3D)
    assert not sketch_mode.sketching(win)


def test_command_plus_and_minus_zoom_the_3d_view(win):
    from khervecad import sketch_mode
    _setup(win)
    win._interface_style = "SolidWorks"
    assert not sketch_mode.sketching(win)
    v = win.view3d
    before = v.distance
    win._zoom(1.25)
    assert v.distance < before
    win._zoom(1 / 1.25)
    assert v.distance == __import__("pytest").approx(before, rel=0.01)


def _two_sketches(win):
    m = win.model
    g, line = _setup(win)
    other = m.add_node("union", {}, name="Other sketch")
    far = m.add_node("line", dict(x1=0, y1=30, x2=40, y2=30, width=0.2),
                     parent=other)
    round_ = m.add_node("circle", dict(x=70, y=30, radius=6), parent=other)
    mine = m.add_node("circle", dict(x=70, y=0, radius=3), parent=g)
    QTest.qWait(50)
    win.view3d.fit()
    return g, line, other, far, round_, mine


def test_a_relation_crosses_sketches_through_a_reference(win):
    from khervecad import constrain3d
    g, line, other, far, _r, _m = _two_sketches(win)
    constrain3d.start(win, "con_parallel")
    tool = win.view3d.edit_tool
    tool.click(*_screen(tool, (20, 3, 0)))
    tool.click(*_screen(tool, (20, 30, 0)))
    assert line.params["y1"] == pytest.approx(line.params["y2"], abs=1e-3)
    assert far.params["y1"] == 30 and "constraints" not in other.params
    assert [c.name for c in g.children if c.params.get("ref_source")] == [
        "Reference edge"]
    assert any(r["kind"] == "parallel" for r in g.params["constraints"])


def test_equal_circles_across_sketches_leaves_no_dimension(win):
    from khervecad import constrain3d
    g, _l, _o, _f, round_, mine = _two_sketches(win)
    constrain3d.start(win, "con_equal")
    tool = win.view3d.edit_tool
    tool.click(*_screen(tool, (73, 0, 0)))
    tool.click(*_screen(tool, (76, 30, 0)))
    assert float(mine.params["radius"]) == pytest.approx(6, abs=1e-3)
    assert round_.params["radius"] == 6
    assert not [r for r in g.params["constraints"] if "value" in r]


def test_a_refused_relation_leaves_no_reference(win):
    from khervecad import constrain3d, sketch_constraints as sc
    g, line, _o, _f, _r, _m = _two_sketches(win)
    sc.add(win.model, g, "vertical", [sc.ref_of(g, line, "l")])
    constrain3d.start(win, "con_parallel")
    tool = win.view3d.edit_tool
    x = line.params["x1"]
    tool.click(*_screen(tool, (x, (line.params["y1"] + line.params["y2"]) / 2,
                               0)))
    tool.click(*_screen(tool, (20, 30, 0)))
    assert not [c for c in g.children if c.params.get("ref_source")]

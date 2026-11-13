"""The middle of a rectangle's side, while sketching (2026-11-13, the
user: "we do not seem to be able to select the middle of the line in a
rectangle so that we can use that one for a centre of a circle"). A shape
just drawn stays selected, and the 2D snap skipped selected shapes, so a
circle's centre fell on the grid beside the middle. A point placed there is
tied by a Midpoint relation, so it stays in the middle. The Line tool and
the 3D sketch already snapped there; these keep them doing so.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import QPointF
from PyQt5.QtTest import QTest

from khervecad import face_sketch as fs, sketch_constraints as sc
from khervecad import sketch_line, sketch_touch
from khervecad.view2d import CIRCLE, LINE, RECT
from test_circle_snap import _drag
from test_lever_by_mouse import win  # noqa: F401


def _rect_by_mouse(win):
    v = win.view2d
    v.resetTransform()
    v.scale(8, -8)
    v.centerOn(20, 10)
    v.set_tool(RECT)
    _drag(v, (1.3, 2.7), (41.9, 22.9))
    rect = next(n for n in win.model.root.walk() if n.type == "rect")
    # off the grid, so a grid snap can never pass for the middle
    win.model.set_param(rect, "width", 41.3)
    win.model.set_param(rect, "height", 20.7)
    QTest.qWait(20)
    p = rect.params
    return v, rect, (p["x"] + p["width"] / 2, p["y"])


def test_a_circle_centre_on_the_middle_of_a_side_just_drawn(win):
    v, rect, mid = _rect_by_mouse(win)
    assert any(i.isSelected() for i in v.scene().items()
               if getattr(i, "node", None) is rect)   # still selected
    v.set_tool(CIRCLE)
    _drag(v, (mid[0] + 0.3, mid[1] + 0.25), (mid[0] + 6, mid[1] + 0.25))
    circle = [n for n in win.model.root.walk() if n.type == "circle"][-1]
    assert (circle.params["x"], circle.params["y"]) == \
        pytest.approx(mid, abs=1e-6)
    cont = circle.parent
    assert any(r["kind"] == "midpoint" and
               sc.ref_of(cont, circle, "c") in r["refs"]
               for r in sc.rows(cont))
    # the rectangle grows: the circle stays in the middle of its side
    win.model.set_param(rect, "width", 61.0)
    QTest.qWait(20)
    assert circle.params["x"] == pytest.approx(rect.params["x"] + 30.5,
                                               abs=1e-3)


def test_the_line_tool_snaps_to_side_middles(win):
    v, rect, mid = _rect_by_mouse(win)
    v.set_tool(LINE)
    q, _info = sketch_line.snap(v.scene(),
                                QPointF(mid[0] + 0.3, mid[1] + 0.25))
    assert (q.x(), q.y()) == pytest.approx(mid, abs=1e-6)
    # the left side's middle too
    p = rect.params
    left = (p["x"], p["y"] + p["height"] / 2)
    q, _info = sketch_line.snap(v.scene(),
                                QPointF(left[0] + 0.3, left[1] - 0.2))
    assert (q.x(), q.y()) == pytest.approx(left, abs=1e-6)


def test_in_the_3d_sketch_too(win, monkeypatch):
    from khervecad import cut_feature, sketch3d
    monkeypatch.setattr(cut_feature, "IN_3D", True)
    m = win.model
    part = m.add_node("cube", dict(width=60, depth=60, height=10))
    QTest.qWait(50)
    win.view3d.resize(800, 600)
    win.view3d.set_view("Top", animate=False)
    win.view3d.fit()
    tool = sketch3d.start(win, "rect")
    g = fs.make(win, part, (30, 30, 10), (0, 0, 1), open_2d=False)
    tool.use_group(g)
    tool.place(fs.to_local(g, (10, 15, 10)))
    tool.place(fs.to_local(g, (40, 35, 10)))
    rect = next(n for n in g.walk() if n.type == "rect")
    a = sc._line(rect, "e0", {})
    mid = ((a[0][0] + a[1][0]) / 2, (a[0][1] + a[1][1]) / 2)
    got = tool.snap_local(mid[0] + 0.2, mid[1] + 0.2)
    assert got == pytest.approx(mid, abs=1e-6)
    assert tool.snapped[2] == "middle"
    tool.tool_icon(CIRCLE)
    tool.place(mid)
    tool.place((mid[0] + 5, mid[1]))
    circle = next(n for n in g.walk() if n.type == "circle")
    assert any(r["kind"] == "midpoint" and
               sc.ref_of(g, circle, "c") in r["refs"] for r in sc.rows(g))

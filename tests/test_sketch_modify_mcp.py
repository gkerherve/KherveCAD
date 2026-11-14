"""MCP sketch_modify and the first-dimension scaling through
sketch_constraint.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtWidgets import QApplication

_APP = QApplication.instance() or QApplication([])


@pytest.fixture
def ex():
    from khervecad.mainwindow import MainWindow
    from khervecad.mcp_tools import McpToolExecutor
    win = MainWindow()
    yield McpToolExecutor(win)
    win._dirty = False
    win.close()


def test_trim_extend_and_fillet(ex):
    m = ex._w.model
    a = m.add_node("line", dict(x1=0, y1=0, x2=20, y2=0))
    m.add_node("line", dict(x1=10, y1=-5, x2=10, y2=5))
    out = ex.execute("sketch_modify", dict(action="trim", node_id=a.id,
                                           point=[15, 0]))
    assert "error" not in out, out
    assert out["line"]["x2"] == pytest.approx(10)
    poly = m.add_node("polygon", dict(points=[[0, 0], [10, 0], [10, 10],
                                              [0, 10]]))
    out = ex.execute("sketch_modify", dict(action="fillet", node_id=poly.id,
                                           vertex=2, size=2))
    assert "error" not in out, out
    assert out["corners"]
    cube = m.add_node("cube", dict())
    bad = ex.execute("sketch_modify", dict(action="trim", node_id=cube.id,
                                           point=[0, 0]))
    assert "error" in bad


def test_trim_a_circle_and_a_rectangle_side_construction(ex):
    """The pattern exercise's lug (ogsBu7TcfDI): a Center Rectangle and a
    circle on its top side; the circle's lower half is trimmed away and
    the top side made construction — an assistant could do neither."""
    m = ex._w.model
    r = m.add_node("rect", dict(x=-50, y=120, width=100, height=55))
    c = m.add_node("circle", dict(x=0, y=175, radius=50))
    out = ex.execute("sketch_modify", dict(action="trim", node_id=c.id,
                                           point=[0, 125]))
    assert "error" not in out, out
    assert out["result"] == "opened"
    arc = m.find(c.id)
    assert arc.type == "line" and arc.params.get("bulge")
    out = ex.execute("sketch_modify", dict(
        action="construction", node_id=r.id, point=[0, 175]))
    assert "error" not in out, out
    top = m.find(out["node_id"])
    assert top.type == "line" and top.params.get("modifier") == "%"
    assert top.params["y1"] == pytest.approx(175)
    assert top.params["y2"] == pytest.approx(175)
    others = [n for n in m.root.children
              if n.type == "line" and n is not top and n is not arc]
    assert len(others) == 3 and all(
        n.params.get("modifier", "") != "%" for n in others)


def test_first_dimension_scales_through_mcp(ex, monkeypatch):
    from khervecad import sketch_constraints as sc
    monkeypatch.setattr(sc, "scale_first_enabled", lambda: True)
    m = ex._w.model
    a = m.add_node("line", dict(x1=0, y1=0, x2=10, y2=0))
    c = m.add_node("circle", dict(x=20, y=0, radius=2))
    i = m.root.children.index(a)
    out = ex.execute("sketch_constraint", dict(
        action="add", kind="length", refs=["%d.l" % i], value=20))
    assert "error" not in out, out
    assert out["scaled"] is True
    assert c.params["radius"] == pytest.approx(4)


def test_convert_entities_on_a_plane_through_the_part(ex):
    """Convert Entities through MCP (Exercise 50: the R100 and R25 of
    a mid-plane plate brought into a Front Plane sketch)."""
    w = ex._w
    sk = ex.execute("reference_geometry", dict(
        action="sketch", origin=[0, 0, 0], normal=[0, -1, 0]))["sketch_id"]
    ex.execute("add_node", dict(type="circle", parent_id=sk,
                                params=dict(x=0, y=0, radius=20)))
    ex.execute("add_node", dict(type="rect", parent_id=sk,
                                params=dict(x=0, y=-10, width=40,
                                            height=20)))
    out = ex.execute("sketch_feature", dict(node_id=sk, depth=10,
                                            mid_plane=True))
    assert "error" not in out, out
    s2 = ex.execute("reference_geometry", dict(
        action="sketch", origin=[0, 0, 0], normal=[0, -1, 0]))["sketch_id"]
    out = ex.execute("sketch_modify", dict(action="convert", node_id=s2,
                                           point=[-20, 0]))
    assert "error" not in out, out
    made = [w.model.find(i) for i in out["node_ids"]]
    assert made and all(n.parent.id == s2 for n in made)
    arc = [n for n in made if n.params.get("bulge")]
    assert arc, [n.params for n in made]
    out = ex.execute("sketch_modify", dict(action="convert", node_id=s2,
                                           point=[30, -10]))
    assert "error" not in out, out
    line = w.model.find(out["node_ids"][0])
    assert line.type == "line"
    assert line.params["y1"] == pytest.approx(-10, abs=0.01)
    bad = ex.execute("sketch_modify", dict(action="convert", node_id=s2,
                                           point=[500, 500]))
    assert "error" in bad

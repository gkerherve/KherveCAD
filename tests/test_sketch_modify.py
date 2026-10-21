"""Trim, extend and sketch fillet / chamfer.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

import pytest
from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from khervecad import sketch_modify as sm
from khervecad.model import DocumentModel


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _cross_lines(m):
    h = m.add_node("line", dict(x1=0, y1=0, x2=40, y2=0))
    m.add_node("line", dict(x1=10, y1=-10, x2=10, y2=10))
    m.add_node("line", dict(x1=30, y1=-10, x2=30, y2=10))
    return h


def test_trim_shortens_splits_and_deletes(app):
    m = DocumentModel()
    h = _cross_lines(m)
    assert sm.trim(m, h, (35, 0)) == "shortened"
    assert h.params["x2"] == pytest.approx(30)
    # now 0..30, ending ON the third line: the piece 10..30 is an end
    assert sm.trim(m, h, (20, 0)) == "shortened"
    assert h.params["x2"] == pytest.approx(10)
    long_ = m.add_node("line", dict(x1=0, y1=5, x2=40, y2=5))
    assert sm.trim(m, long_, (20, 5)) == "split"
    pieces = sorted((n.params["x1"], n.params["x2"])
                    for n in m.root.children if n.params.get("y1") == 5)
    assert pieces == [(0, 10), (30, 40)]
    lone = m.add_node("line", dict(x1=100, y1=100, x2=120, y2=100))
    assert sm.trim(m, lone, (110, 100)) == "deleted"
    assert lone not in m.root.children


def test_extend_meets_the_next_line(app):
    m = DocumentModel()
    a = m.add_node("line", dict(x1=0, y1=0, x2=5, y2=0))
    m.add_node("line", dict(x1=20, y1=-10, x2=20, y2=10))
    assert sm.extend(m, a, (5, 0)) == (20, 0)
    assert sm.extend(m, a, (0, 0)) is None


def test_fillet_and_chamfer_a_rectangle_corner(app):
    m = DocumentModel()
    r = m.add_node("rect", dict(width=20, height=10))
    sm.corner(m, r, 2, 3)
    assert r.type == "polygon"
    pts = r.params["points"]
    assert len(pts) == 4 + sm.ARC_STEPS
    # the arc stays 3 mm from its centre (17, 7)
    for x, y in pts[2:2 + sm.ARC_STEPS + 1]:
        assert math.hypot(x - 17, y - 7) == pytest.approx(3, abs=1e-3)
    sm.corner(m, r, 0, 2, round_=False)
    assert [0, 2] in r.params["points"] and [2, 0] in r.params["points"]
    with pytest.raises(ValueError):
        sm.corner(m, r, 1, 50)


def test_fillet_two_lines(app):
    m = DocumentModel()
    a = m.add_node("line", dict(x1=0, y1=0, x2=20, y2=0))
    b = m.add_node("line", dict(x1=20, y1=0, x2=20, y2=20))
    arc = sm.line_corner(m, a, b, 5)
    assert a.params["x2"] == pytest.approx(15)
    assert b.params["y1"] == pytest.approx(5)
    assert arc.type == "polygon" and m.root.children.index(arc) == 1


def test_click_tools(app):
    from khervecad.view2d import SketchScene, SketchView
    scene = SketchScene(DocumentModel())
    scene.snap_enabled = False
    view = SketchView(scene)
    view.resize(600, 500)
    view.show()
    view.centerOn(20, 0)
    try:
        h = _cross_lines(scene.model)
        view.set_tool(sm.TRIM)
        QTest.mouseClick(view.viewport(), Qt.LeftButton, Qt.NoModifier,
                         view.mapFromScene(QPointF(36, 0)))
        assert h.params["x2"] == pytest.approx(30)
        r = scene.model.add_node("rect", dict(x=50, y=0, width=20,
                                              height=10))
        scene.ask_value = lambda tool, default: "2"
        view.set_tool(sm.FILLET)
        QTest.mouseClick(view.viewport(), Qt.LeftButton, Qt.NoModifier,
                         view.mapFromScene(QPointF(70, 10)))
        assert r.type == "polygon"
    finally:
        view.close()


def test_a_fillet_keeps_the_constraints_on_their_edges(app):
    """The user's L-shape: H / V on its edges, fillet a corner. The
    constraints named edges by number, the arc's 12 new points shifted
    them onto arc pieces and the solver made a staircase."""
    from khervecad import sketch_constraints as sc
    m = DocumentModel()
    p = m.add_node("polygon", dict(points=[[0, 0], [20, 0], [20, 5],
                                           [5, 5], [5, 15], [0, 15]]))
    r = m.root
    for e in (0, 2, 4):
        sc.add(m, r, "horizontal", ["0.e%d" % e])
    for e in (1, 3, 5):
        sc.add(m, r, "vertical", ["0.e%d" % e])
    sm.corner(m, p, 4, 2)                    # round the top-right corner
    sc.refresh(m)
    pts = p.params["points"]
    n = len(pts)
    assert n == 6 + sm.ARC_STEPS
    # every remaining constraint still names a straight edge
    for row in sc.rows(r):
        a, b = sc._line(p, row["refs"][0].split(".")[1], {})
        if row["kind"] == "horizontal":
            assert abs(a[1] - b[1]) < 1e-6
        else:
            assert abs(a[0] - b[0]) < 1e-6
    # and the arc is still round: 2 mm from its centre (3, 13)
    for x, y in pts[4:4 + sm.ARC_STEPS + 1]:
        assert math.hypot(x - 3, y - 13) == pytest.approx(2, abs=1e-3)


def test_deleting_a_shape_renumbers_the_others(app):
    from khervecad import sketch_constraints as sc
    m = DocumentModel()
    a = m.add_node("line", dict(x1=0, y1=0, x2=10, y2=0))
    b = m.add_node("line", dict(x1=0, y1=5, x2=10, y2=6))
    c = m.add_node("line", dict(x1=0, y1=9, x2=10, y2=12))
    sc.add(m, m.root, "parallel", ["1.l", "2.l"])
    m.remove_node(a)
    assert sc.rows(m.root)[0]["refs"] == ["0.l", "1.l"]
    m.remove_node(b)
    assert sc.rows(m.root) == []

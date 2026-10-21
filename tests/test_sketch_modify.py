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
    # the corner stays a corner; the arc is a row, drawn by expand
    assert r.params["points"] == [[0, 0], [20, 0], [20, 10], [0, 10]]
    assert r.params["corners"] == [[2, 3.0, 0]]
    pts = sm.expand(r.params["points"], r.params["corners"])
    assert len(pts) == 4 + sm.ARC_STEPS
    for x, y in pts[2:2 + sm.ARC_STEPS + 1]:
        assert math.hypot(x - 17, y - 7) == pytest.approx(3, abs=1e-3)
    sm.corner(m, r, 0, 2, round_=False)
    pts = sm.expand(r.params["points"], r.params["corners"])
    assert pts[0] == pytest.approx((0, 2)) and pts[1] == pytest.approx((2, 0))
    with pytest.raises(ValueError):
        sm.corner(m, r, 1, 50)


def test_the_arc_follows_a_moved_corner(app):
    """The user's gaps: baked arc points stayed behind when the solver
    moved the edges. Now the arc is worked out from the corner."""
    m = DocumentModel()
    p = m.add_node("polygon", dict(points=[[0, 0], [20, 0], [20, 10],
                                           [0, 10]]))
    sm.corner(m, p, 2, 2)
    p.params["points"][2] = [30, 15]
    p.params["points"][1] = [30, 0]
    p.params["points"][3] = [0, 15]
    pts = sm.expand(p.params["points"], p.params["corners"])
    for x, y in pts[2:2 + sm.ARC_STEPS + 1]:
        assert math.hypot(x - 28, y - 13) == pytest.approx(2, abs=1e-3)
    assert pts[2] == pytest.approx((30, 13)) and \
        pts[2 + sm.ARC_STEPS] == pytest.approx((28, 15))


def test_corners_survive_the_openscad_program(app):
    from khervecad import scadparse
    m = DocumentModel()
    p = m.add_node("polygon", dict(points=[[0, 0], [20, 0], [20, 10],
                                           [0, 10]]))
    sm.corner(m, p, 2, 2)
    sm.corner(m, p, 0, 1, round_=False)
    root, warnings = scadparse.parse_scad(m.to_scad())
    assert not warnings
    q = next(n for n in root.walk() if n.type == "polygon")
    assert q.params["points"] == [[0, 0], [20, 0], [20, 10], [0, 10]]
    assert q.params["corners"] == [[0, 1.0, 1], [2, 2.0, 0]]


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
    """The user's L-shape: H / V on its edges, fillet a corner, move it:
    the constraints still hold on the edges and the arc stays round and
    joined to them (it used to stair-step, then to leave gaps)."""
    from khervecad import sketch_constraints as sc
    m = DocumentModel()
    p = m.add_node("polygon", dict(points=[[0, 0], [20, 0], [20, 5],
                                           [5, 5], [5, 15], [0, 15]]))
    r = m.root
    for e in (0, 2, 4):
        sc.add(m, r, "horizontal", ["0.e%d" % e])
    for e in (1, 3, 5):
        sc.add(m, r, "vertical", ["0.e%d" % e])
    sm.corner(m, p, 4, 2)
    assert len(sc.rows(r)) == 6                 # nothing dropped
    p.params["points"][4] = [7, 18]             # drag the rounded corner
    sc.refresh(m, {p.id})
    pts = p.params["points"]
    assert pts[3][0] == pytest.approx(7, abs=1e-3)       # V followed
    assert pts[5][1] == pytest.approx(18, abs=1e-3)      # H followed
    arc = sm.expand(pts, p.params["corners"])[4:4 + sm.ARC_STEPS + 1]
    for x, y in arc:
        assert math.hypot(x - 5, y - 16) == pytest.approx(2, abs=1e-2)


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


def test_a_selected_profile_shows_what_it_is_combined_with(app):
    """Selecting the polygon of polygon-minus-circle showed the polygon
    alone: the circle cut from it was invisible in 2D."""
    from PyQt5.QtCore import Qt as _Qt
    from khervecad.view2d import SketchScene, SketchView
    m = DocumentModel()
    scene = SketchScene(m)
    view = SketchView(scene)
    view.show()
    try:
        e = m.add_node("linear_extrude", dict(height=5))
        d = m.add_node("difference", {}, parent=e)
        poly = m.add_node("polygon", dict(points=[[0, 0], [30, 0],
                                                  [30, 20], [0, 20]]),
                          parent=d)
        circ = m.add_node("circle", dict(x=15, y=10, radius=4), parent=d)
        scene.set_highlight([poly])
        QApplication.processEvents()
        assert poly.id in scene._items and circ.id in scene._items
        assert scene._items[poly.id].isSelected()
        assert scene._items[circ.id].pen().style() == _Qt.DashLine
    finally:
        view.close()

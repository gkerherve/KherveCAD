"""Mirror Entities: sketch shapes mirrored about a line, by the mouse.

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

from khervecad import sketch_constraints as sc
from khervecad import sketch_mirror as M
from khervecad.model import DocumentModel
from khervecad.view2d import SketchScene, SketchView


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def view(app):
    scene = SketchScene(DocumentModel())
    scene.snap_enabled = False
    v = SketchView(scene)
    v.resize(800, 600)
    v.show()
    v.resetTransform()
    v.scale(8, -8)
    v.centerOn(0, 10)
    yield v
    v.close()


def _click(view, x, y, button=Qt.LeftButton):
    QTest.mouseClick(view.viewport(), button, Qt.NoModifier,
                     view.mapFromScene(QPointF(x, y)))
    QApplication.processEvents()


def _left_side(view):
    m = view.scene().model
    centre = m.add_node("line", dict(x1=0, y1=-10, x2=0, y2=30, width=0.2,
                                     modifier="%"), name="Centerline")
    line = m.add_node("line", dict(x1=-20, y1=0, x2=-8, y2=12, width=0.2))
    circle = m.add_node("circle", dict(x=-14, y=20, radius=3))
    poly = m.add_node("polygon", dict(points=[[-30, 0], [-22, 0],
                                              [-26, 6]]))
    QApplication.processEvents()
    return centre, line, circle, poly


def test_click_the_shapes_then_the_centerline(view):
    m = view.scene().model
    centre, line, circle, poly = _left_side(view)
    view.set_tool(M.TOOL)
    _click(view, -14, 6)                    # the line
    _click(view, -14, 23)                   # the circle's rim
    _click(view, -26, 0)                    # the polygon's side
    assert [n.name for n in M._state(view.scene())["shapes"]] == \
        [line.name, circle.name, poly.name]
    _click(view, 0, 5)                      # the centerline: box 2
    st = M._state(view.scene())
    assert st["line"] is centre and M.ready(view.scene())
    panel = view._mirror_panel
    assert panel.isVisible() and panel.ok.isEnabled()
    assert circle.name in panel.box_shapes.body.text()
    assert centre.name in panel.box_line.body.text()
    QTest.mouseClick(panel.ok, Qt.LeftButton)  # OK: the copies
    assert not panel.isVisible()
    lines = [n for n in m.root.children if n.type == "line"
             and n is not line and n is not centre]
    circles = [n for n in m.root.children if n.type == "circle"]
    polys = [n for n in m.root.children if n.type == "polygon"]
    assert len(lines) == 1 and len(circles) == 2 and len(polys) == 2
    new = lines[0].params
    assert (new["x1"], new["y1"], new["x2"], new["y2"]) == \
        pytest.approx((20, 0, 8, 12))
    c2 = circles[1].params
    assert (c2["x"], c2["y"], c2["radius"]) == pytest.approx((14, 20, 3))
    pts = polys[1].params["points"]
    assert sorted(map(tuple, pts)) == sorted([(30, 0), (22, 0), (26, 6)])
    kinds = [r["kind"] for r in sc.rows(m.root)]
    assert kinds.count("symmetric") == 2 + 1 + 3 and "equal" in kinds
    # the halves stay mirrored: the original circle moved, the copy too
    m.set_param(circle, "x", -10)
    sc.refresh(m, {circle.id})
    a = (circle.params["x"], circle.params["y"])
    b = (circles[1].params["x"], circles[1].params["y"])
    assert a[0] > -13                                 # it did move
    mirrored = M.reflect(a, M.axis_of(centre))
    assert mirrored == pytest.approx(b, abs=1e-3)
    assert circles[1].params["radius"] == pytest.approx(
        circle.params["radius"], abs=1e-6)


def test_a_click_off_a_centerline_adds_and_drops_shapes(view):
    centre, line, circle, poly = _left_side(view)
    view.set_tool(M.TOOL)
    _click(view, -14, 6)
    _click(view, -14, 6)                    # again: dropped
    assert M._state(view.scene())["shapes"] == []
    _click(view, 0, 5)                      # a centerline, nothing picked
    st = M._state(view.scene())
    assert st["shapes"] == [centre] and st["line"] is None
    assert not view._mirror_panel.ok.isEnabled()
    assert len(view.scene().model.root.children) == 4


def test_enter_then_an_ordinary_line_mirrors_about_it(view):
    m = view.scene().model
    rect = m.add_node("rect", dict(x=-20, y=0, width=10, height=5))
    slant = m.add_node("line", dict(x1=0, y1=0, x2=10, y2=10, width=0.2))
    QApplication.processEvents()
    view.set_tool(M.TOOL)
    _click(view, -15, 0)                    # the rectangle's bottom side
    _click(view, 5, 5)                      # an ordinary line: picked
    assert slant in M._state(view.scene())["shapes"]
    _click(view, 5, 5)                      # dropped again
    panel = view._mirror_panel
    QTest.mouseClick(panel.box_line, Qt.LeftButton)   # box 2 active
    assert M._state(view.scene())["active"] == M.LINE
    _click(view, 5, 5)                      # now it is the mirror line
    QTest.keyClick(view.viewport(), Qt.Key_Return)    # Enter = OK
    polys = [n for n in m.root.children if n.type == "polygon"]
    assert len(polys) == 1                  # slanted: a polygon
    got = sorted(tuple(p) for p in polys[0].params["points"])
    want = sorted((y, x) for x, y in ((-20, 0), (-10, 0), (-10, 5),
                                      (-20, 5)))   # y = x swaps them
    assert got == pytest.approx(want)
    assert rect.parent is m.root            # the original stays


def test_rectangle_about_an_upright_line_stays_a_rectangle(app):
    m = DocumentModel()
    rect = m.add_node("rect", dict(x=2, y=1, width=6, height=4))
    axis = m.add_node("line", dict(x1=10, y1=0, x2=10, y2=9))
    copies, skipped = M.mirror(m, [rect], axis)
    assert not skipped and copies[0].type == "rect"
    p = copies[0].params
    assert (p["x"], p["y"], p["width"], p["height"]) == \
        pytest.approx((12, 1, 6, 4))


def test_an_arc_is_mirrored_with_its_start_angle(app):
    m = DocumentModel()
    arc = m.add_node("circle", dict(x=5, y=0, radius=2, angle=90,
                                    start_angle=0))
    axis = m.add_node("line", dict(x1=0, y1=-5, x2=0, y2=5))
    (copy,), _ = M.mirror(m, [arc], axis, relate=False)
    p = copy.params
    assert (p["x"], p["angle"]) == pytest.approx((-5, 90))
    # the arc from 0° to 90° (right, up) becomes 90°..180° (up, left)
    assert p["start_angle"] == pytest.approx(90)


def test_selected_shapes_and_centerline_fill_the_panel(app):
    from khervecad.mainwindow import MainWindow
    w = MainWindow()
    w.resize(1300, 850)
    w.show()
    try:
        m = w.model
        centre = m.add_node("line", dict(x1=0, y1=-10, x2=0, y2=30,
                                         width=0.2, modifier="%"))
        circle = m.add_node("circle", dict(x=-14, y=20, radius=3))
        QTest.qWait(50)
        w.builder.active_tree().select_nodes([centre, circle])
        QTest.qWait(50)
        act = next(a for a in M_actions(w) if a.data() == M.TOOL)
        act.trigger()
        QTest.qWait(50)
        panel = w.view2d._mirror_panel
        assert panel.isVisible() and panel.ok.isEnabled()  # both filled
        QTest.mouseClick(panel.ok, Qt.LeftButton)
        QTest.qWait(50)
        circles = [n for n in m.root.walk() if n.type == "circle"]
        assert len(circles) == 2
        assert circles[1].params["x"] == pytest.approx(14)
    finally:
        w._dirty = False
        w.close()


def M_actions(win):
    from khervecad import sketch_modify
    return sketch_modify.panel_actions(win)


def test_mcp_mirror(app):
    from khervecad.mainwindow import MainWindow
    from khervecad.mcp_tools import McpToolExecutor
    w = MainWindow()
    try:
        m = w.model
        axis = m.add_node("line", dict(x1=0, y1=0, x2=0, y2=10,
                                       modifier="%"))
        c = m.add_node("circle", dict(x=-4, y=3, radius=1))
        out = McpToolExecutor(w).execute("sketch_modify", {
            "action": "mirror", "node_ids": [c.id], "mirror_line": axis.id})
        assert out["result"] == "mirrored" and len(out["node_ids"]) == 1
        copy = m.find(out["node_ids"][0])
        assert copy.params["x"] == pytest.approx(4)
    finally:
        w._dirty = False
        w.close()


def test_a_polygon_with_its_own_origin_mirrors_in_place(app):
    """The polygon tool stores points relative to x, y: reflecting only
    the points put the copy elsewhere and its Symmetric relations then
    dragged the whole sketch (the centerline tilted)."""
    m = DocumentModel()
    axis = m.add_node("line", dict(x1=0, y1=-8, x2=0, y2=28, modifier="%"))
    poly = m.add_node("polygon", dict(x=-30, y=2, points=[[0, 0], [10, 0],
                                                          [5, 7]]))
    sc.add(m, m.root, "horizontal", ["1.e0"])
    before = dict(axis.params), dict(poly.params)
    (copy,), _ = M.mirror(m, [poly], axis)
    assert dict(axis.params) == before[0] and dict(poly.params) == before[1]
    world = sorted((copy.params["x"] + p[0], copy.params["y"] + p[1])
                   for p in copy.params["points"])
    assert world == pytest.approx(sorted([(30, 2), (20, 2), (25, 9)]))


def test_escape_and_cancel_leave_nothing(view):
    centre, line, circle, poly = _left_side(view)
    view.set_tool(M.TOOL)
    _click(view, -14, 23)
    panel = view._mirror_panel
    assert panel.isVisible()
    QTest.mouseClick(panel.cancel, Qt.LeftButton)
    assert not panel.isVisible()
    assert len(view.scene().model.root.children) == 4
    assert view.scene().tool == "select"


def test_in_the_window_the_panel_stands_beside_the_sketch(app):
    """Not over the drawing: it hid the shapes to click."""
    from khervecad.mainwindow import MainWindow
    from PyQt5.QtCore import QPoint, QRect
    w = MainWindow()
    w.resize(1400, 900)
    w.show()
    try:
        QTest.qWait(50)
        act = next(a for a in M_actions(w) if a.data() == M.TOOL)
        act.trigger()
        QTest.qWait(50)
        panel = w.view2d._mirror_panel
        assert panel.isVisible() and panel.parentWidget() is w
        vp = w.view2d.viewport()
        view_rect = QRect(vp.mapTo(w, QPoint(0, 0)), vp.size())
        assert not panel.geometry().intersects(view_rect)
        assert panel.geometry().right() < view_rect.left()
    finally:
        w._dirty = False
        w.close()


def test_a_centerline_is_not_drawn_in_3d(app):
    """Construction geometry is for the sketch: the 3D view draws
    nothing of a centerline or a construction circle; a % on a 3D part
    keeps its grey ghost."""
    from khervecad import mesh
    m = DocumentModel()
    centre = m.add_node("line", dict(x1=0, y1=-10, x2=0, y2=30,
                                     modifier="%"))
    point = m.add_node("circle", dict(x=5, y=5, radius=0.25,
                                      modifier="%"))
    shape = m.add_node("circle", dict(x=-14, y=20, radius=3))
    assert mesh.tessellate(centre) == [] and mesh.tessellate(point) == []
    assert mesh.tessellate(shape)
    cube = m.add_node("cube", dict(width=5, depth=5, height=5),)
    cube.params["modifier"] = "%"
    ghost = mesh.tessellate_colored(cube)
    assert ghost and ghost[0][1][0] == mesh.MODIFIER_TINT["%"][0]

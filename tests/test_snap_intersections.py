"""Snapping to where sketch lines cross (2026-11-11, the user: "we can
connect to middle, centre, but we need to connect to intersections too").

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import QPointF
from PyQt5.QtWidgets import QApplication

from khervecad import snap_cross, sketch_line
from khervecad.model import DocumentModel
from khervecad.view2d import SketchScene, SketchView


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_crossings_of_different_shapes_only():
    a = [((0, 0), (10, 10))]
    b = [((0, 10), (10, 0))]
    poly = [((0, 0), (4, 0)), ((4, 0), (4, 4)), ((4, 4), (0, 0))]
    got = snap_cross.crossings([a, b])
    assert [(round(x, 6), round(y, 6)) for x, y in got] == [(5.0, 5.0)]
    assert snap_cross.crossings([poly]) == []          # its own corners


def test_a_line_snaps_where_two_lines_cross_and_on_a_circle(app):
    scene = SketchScene(DocumentModel())
    view = SketchView(scene)
    view.resize(600, 500)
    view.show()
    view.resetTransform()
    view.scale(8, -8)
    view.centerOn(0, 0)
    m = scene.model
    m.add_node("line", dict(x1=-10, y1=-10, x2=10, y2=10, width=0.2))
    m.add_node("line", dict(x1=-10, y1=10, x2=10, y2=-10, width=0.2))
    m.add_node("circle", dict(x=0, y=0, radius=5))
    QApplication.processEvents()
    q, info = sketch_line.snap(scene, QPointF(0.3, -0.2))
    assert (round(q.x(), 4), round(q.y(), 4)) == (0, 0)
    # where the first line meets the circle: (3.5355, 3.5355)
    q, info = sketch_line.snap(scene, QPointF(3.7, 3.4))
    assert abs(q.x() - 3.5355) < 0.05 and abs(q.y() - 3.5355) < 0.05
    pts = scene.feature_points()                       # other tools too
    assert any(abs(p.x()) < 1e-6 and abs(p.y()) < 1e-6 for p in pts)
    view.close()


def test_the_3d_sketch_snaps_to_a_crossing(app, monkeypatch):
    from khervecad import cut_feature
    from khervecad.mainwindow import MainWindow
    from khervecad.mcp_tools import McpToolExecutor
    monkeypatch.setattr(cut_feature, "IN_3D", True)
    win = MainWindow()
    try:
        McpToolExecutor(win).execute(
            "apply_code", {"code": "cube([40, 30, 20]); // Block\n"})
        QApplication.processEvents()
        part = next(c for c in win.model.root.children
                    if c.visible and c.type != "assign")
        cut_feature.start(win, "extruded_cut")
        win.view3d._pick_cb(dict(kind="face", pos=(20, 15, 20),
                                 dir=(0, 0, 1)), part)
        tool = win.view3d.edit_tool
        win.view3d.resize(800, 600)
        win.view3d.fit()
        g = tool.group
        win.model.add_node("line", dict(x1=5, y1=10, x2=25, y2=10,
                                        width=0.2), parent=g)
        win.model.add_node("line", dict(x1=10, y1=5, x2=10, y2=25,
                                        width=0.2), parent=g)
        got = tool.snap_local(10.05, 9.95)
        assert got == pytest.approx((10, 10), abs=1e-6)
        assert tool.snapped[2] == "intersection"
        tool.finish()
    finally:
        win._dirty = False
        win.close()


def test_a_line_dragged_by_its_middle_snaps_its_end_2d(app):
    """2D: the middle grip moves the whole line; an end that comes near
    another line's end lands exactly on it."""
    from khervecad.view2d import LineShapeItem
    scene = SketchScene(DocumentModel())
    view = SketchView(scene)
    view.resize(600, 500)
    view.show()
    view.resetTransform()
    view.scale(8, -8)
    view.centerOn(0, 0)
    m = scene.model
    m.add_node("line", dict(x1=0, y1=0, x2=20, y2=0, width=0.2), name="A")
    b = m.add_node("line", dict(x1=0, y1=10, x2=10, y2=20, width=0.2),
                   name="B")
    QApplication.processEvents()
    item = next(i for i in scene.items()
                if isinstance(i, LineShapeItem) and i.node is b)
    assert "move" in [r for r, _q in item.handle_spec()]
    # its middle (5, 15) to (25.3, 4.8): its start lands near A's end (20, 0)
    item.handle_dragged("move", QPointF(25.3, 4.8))
    p = b.params
    assert (round(p["x1"], 6), round(p["y1"], 6)) == (20, 0)
    assert (round(p["x2"], 6), round(p["y2"], 6)) == (30, 10)   # same size
    view.close()


def test_a_line_dragged_by_its_middle_snaps_its_end_3d(app, monkeypatch):
    from khervecad import cut_feature
    from khervecad.mainwindow import MainWindow
    from khervecad.mcp_tools import McpToolExecutor
    monkeypatch.setattr(cut_feature, "IN_3D", True)
    win = MainWindow()
    try:
        McpToolExecutor(win).execute(
            "apply_code", {"code": "cube([40, 30, 20]); // Block\n"})
        QApplication.processEvents()
        part = next(c for c in win.model.root.children
                    if c.visible and c.type != "assign")
        cut_feature.start(win, "extruded_cut")
        win.view3d._pick_cb(dict(kind="face", pos=(20, 15, 20),
                                 dir=(0, 0, 1)), part)
        tool = win.view3d.edit_tool
        win.view3d.resize(800, 600)
        win.view3d.fit()
        g = tool.group
        win.model.add_node("line", dict(x1=5, y1=10, x2=25, y2=10,
                                        width=0.2), parent=g)
        b = win.model.add_node("line", dict(x1=5, y1=20, x2=9, y2=24,
                                            width=0.2), parent=g)
        grips = [r for n, r, _p in tool.handles() if n is b]
        assert "move" in grips
        # middle (7, 22) moved to (27.1, 11.9): start near (25, 10)
        tool.drag_to(b, "move", (27.1, 11.9))
        p = b.params
        assert (p["x1"], p["y1"]) == pytest.approx((25, 10), abs=1e-6)
        assert (p["x2"], p["y2"]) == pytest.approx((29, 14), abs=1e-6)
        tool.finish()
    finally:
        win._dirty = False
        win.close()


def test_a_point_is_an_origin_with_two_centerlines(app):
    """The Point tool: the point and X / Y centerlines through it, tied
    so they follow it (2026-11-11, the user)."""
    from PyQt5.QtCore import Qt
    from PyQt5.QtTest import QTest
    from khervecad import sketch_constraints as sc, sketch_tools2
    scene = SketchScene(DocumentModel())
    scene.snap_enabled = False
    view = SketchView(scene)
    view.resize(600, 500)
    view.show()
    view.resetTransform()
    view.scale(8, -8)
    view.centerOn(0, 0)
    view.set_tool(sketch_tools2.POINT)
    QTest.mouseClick(view.viewport(), Qt.LeftButton, Qt.NoModifier,
                     view.mapFromScene(QPointF(5, 3)))
    QApplication.processEvents()
    m = scene.model
    group = next(n for n in m.root.walk() if n.name == "Point")
    dot, h, v = group.children
    assert dot.type == "circle" and h.type == v.type == "line"
    assert all(n.params.get("modifier") == "%" for n in (dot, h, v))
    assert (h.params["y1"], h.params["y2"]) == (3, 3)
    assert (v.params["x1"], v.params["x2"]) == (5, 5)
    kinds = sorted(r["kind"] for r in group.params["constraints"])
    assert kinds == ["coincident", "coincident", "horizontal", "vertical"]
    # the point moved: both axes follow, centred on it
    dot.params.update(x=12.0, y=-4.0)
    sc.refresh(m, edited=(dot.id,))
    assert (h.params["x1"] + h.params["x2"]) / 2 == pytest.approx(12, abs=1e-4)
    assert h.params["y1"] == pytest.approx(-4, abs=1e-4)
    assert (v.params["y1"] + v.params["y2"]) / 2 == pytest.approx(-4,
                                                                  abs=1e-4)
    assert v.params["x2"] == pytest.approx(12, abs=1e-4)
    # their ends and crossing are snap points
    q, _info = sketch_line.snap(scene, QPointF(12.04, -3.96))
    assert (round(q.x(), 3), round(q.y(), 3)) == (12, -4)
    view.close()

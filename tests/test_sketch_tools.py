"""The extra sketch tools (centre rectangle, arcs, ellipse, slot,
spline) driven with real mouse events, and their nodes round-tripping
through OpenSCAD.

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

from khervecad import scadparse, sketch_tools as st
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
    v.resize(600, 500)
    v.show()
    v.centerOn(20, 20)
    yield v
    v.close()


def _click(view, x, y, button=Qt.LeftButton):
    QTest.mouseClick(view.viewport(), button, Qt.NoModifier,
                     view.mapFromScene(QPointF(x, y)))


def _nodes(view):
    return [n for n in view.scene().model.root.walk()
            if n is not view.scene().model.root]


def _draw(view, tool, pts):
    view.set_tool(tool)
    for x, y in pts:
        _click(view, x, y)


def _near(a, b, tol=0.3):
    return abs(a - b) < tol


def test_centre_rectangle(view):
    _draw(view, st.RECT_CENTER, [(20, 20), (30, 26)])
    (rect,) = _nodes(view)
    p = rect.params
    assert rect.type == "rect"
    assert _near(p["x"], 10) and _near(p["y"], 14)
    assert _near(p["width"], 20) and _near(p["height"], 12)


def test_centre_rectangle_by_drag(view):
    view.set_tool(st.RECT_CENTER)
    vp = view.viewport()
    QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier,
                     view.mapFromScene(QPointF(20, 20)))
    QTest.mouseMove(vp, view.mapFromScene(QPointF(30, 30)))
    QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier,
                       view.mapFromScene(QPointF(30, 30)))
    assert [n.type for n in _nodes(view)] == ["rect"]


def test_centre_arc(view):
    _draw(view, st.ARC_CENTER, [(0, 0), (20, 0), (0, 20)])
    (c,) = _nodes(view)
    assert c.type == "circle"
    assert _near(c.params["radius"], 20)
    assert _near(c.params["start_angle"], 0, 2)
    assert _near(c.params["angle"], 90, 2)


def test_three_point_arc(view):
    _draw(view, st.ARC_3PT, [(-20, 0), (20, 0), (0, 20)])
    (poly,) = _nodes(view)
    assert poly.type == "polygon"
    ox, oy = poly.params["x"], poly.params["y"]
    for px, py in poly.params["points"]:
        r = math.hypot(px + ox, py + oy)
        assert py + oy >= -0.5 and (r < 20.5)
    assert max(py + oy for _, py in poly.params["points"]) > 19


def test_ellipse(view):
    _draw(view, st.ELLIPSE, [(10, 10), (40, 20)])
    (sc,) = [n for n in _nodes(view) if n.type == "scale"]
    (circle,) = sc.children
    assert _near(sc.params["x"] * circle.params["radius"], 30)
    assert _near(circle.params["radius"], 10)
    assert _near(sc.params["x"] * circle.params["x"], 10)


def test_slot(view):
    _draw(view, st.SLOT, [(0, 0), (40, 0), (20, 5)])
    (slot,) = _nodes(view)
    assert slot.type == "line"
    assert _near(slot.params["width"], 10) and _near(slot.params["x2"], 40)


def test_spline_enter_finishes(view):
    _draw(view, st.SPLINE, [(0, 0), (30, 0), (30, 30), (0, 30)])
    assert not _nodes(view)
    QTest.keyClick(view.viewport(), Qt.Key_Return)
    (poly,) = _nodes(view)
    assert poly.type == "polygon"
    assert len(poly.params["points"]) == 4 * st.SPLINE_STEPS


def test_spline_right_click_and_escape(view):
    _draw(view, st.SPLINE, [(0, 0), (30, 0)])
    QTest.keyClick(view.viewport(), Qt.Key_Escape)
    _click(view, 10, 10, Qt.RightButton)
    assert not _nodes(view)
    _draw(view, st.SPLINE, [(0, 0), (30, 0), (15, 25)])
    _click(view, 5, 5, Qt.RightButton)
    assert [n.type for n in _nodes(view)] == ["polygon"]


def test_tool_change_drops_half_drawn(view):
    _draw(view, st.SLOT, [(0, 0), (40, 0)])
    view.set_tool(st.ELLIPSE)
    _click(view, 5, 5)
    assert not _nodes(view)
    assert not [i for i in view.scene().items() if i.zValue() >= 1e6
                and i not in view.scene()._sk_items]


@pytest.mark.parametrize("tool, pts", [
    (st.RECT_CENTER, [(20, 20), (30, 26)]),
    (st.ARC_CENTER, [(0, 0), (20, 0), (0, 20)]),
    (st.ARC_3PT, [(-20, 0), (20, 0), (0, 20)]),
    (st.ELLIPSE, [(10, 10), (40, 20)]),
    (st.SLOT, [(0, 0), (40, 0), (20, 5)]),
])
def test_round_trips_through_scad(view, tool, pts):
    _draw(view, tool, pts)
    model = view.scene().model
    code = model.to_scad()
    root, _w = scadparse.parse_scad(code)
    model2 = DocumentModel()
    model2.root = root
    assert model2.to_scad() == code


def test_geometry_refuses_degenerate():
    assert st.arc_3pt((0, 0), (10, 0), (20, 0)) is None
    assert st.slot((0, 0), (0, 0), (5, 5)) is None
    assert st.rect_center((0, 0), (0.1, 5)) is None


@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    yield win
    win._dirty = False
    win.close()


def test_sketch_tab_has_create_modify_insert(window):
    from khervecad import ribbon
    keys = dict((k, panels) for k, _f, _s, panels in ribbon.TABS)["sketch"]
    assert keys == ["sketch", "sketch_shapes", "sketch_modify",
                    "sketch_constrain", "sketch_insert"]
    _t, create = ribbon.panel_actions(window, "sketch")
    data = [a.data() for a in create]
    for tool, *_ in st.TOOLS:
        assert tool in data
    _t, modify = ribbon.panel_actions(window, "sketch_modify")
    assert [a.data() for a in modify][:6] == [
        "construction", "sk_trim", "sk_extend", "sk_fillet", "sk_chamfer",
        "offset"]
    assert {"mirror", "pattern"} <= {a.data() for a in modify}
    _t, insert = ribbon.panel_actions(window, "sketch_insert")
    assert [a.data() for a in insert] == ["import_2d"]


def test_ribbon_tool_sets_the_sketch_tool(window):
    from khervecad import ribbon
    _t, create = ribbon.panel_actions(window, "sketch")
    act = next(a for a in create if a.data() == st.SLOT)
    act.trigger()
    assert window.view2d.scene().tool == st.SLOT


def test_centre_rectangle_on_the_origin_keeps_its_centre(view):
    """Drawn from the origin, a dimension on a side resizes it about the
    origin (it used to move the corner and slide the centre away)."""
    from khervecad import sketch_constraints as sc
    _draw(view, st.RECT_CENTER, [(0, 0), (10, 6)])
    (rect,) = _nodes(view)
    model = view.scene().model
    parent = rect.parent
    sc.add(model, parent, "length", [sc.ref_of(parent, rect, "e0")], 40)
    p = rect.params
    assert _near(p["width"], 40)
    assert _near(p["x"] + p["width"] / 2, 0)
    assert _near(p["y"] + p["height"] / 2, 0)


def test_perimeter_circle_clicked_on_rectangle_sides_is_tangent(view):
    """SolidWorks' Perimeter Circle: clicks on a rectangle's top, bottom
    and right side give the circle touching all three, with Tangent
    relations (the user's video)."""
    from khervecad import sketch_tools2 as st2, sketch_constraints as sc
    _draw(view, st.RECT_CENTER, [(20, 20), (50, 30)])  # x -10..50, y 10..30
    view.set_tool(st2.CIRCLE_3PT)
    _click(view, 35, 30)     # top side
    _click(view, 35, 10)     # bottom side
    _click(view, 50, 22)     # right side
    circle = [n for n in _nodes(view) if n.type == "circle"][0]
    p = circle.params
    assert _near(p["radius"], 10) and _near(p["y"], 20) and _near(p["x"], 40)
    kinds = [r["kind"] for r in sc.rows(circle.parent)]
    assert kinds.count("tangent") == 3

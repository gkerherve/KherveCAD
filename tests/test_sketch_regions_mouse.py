"""Regions from ANY 2D edges, driven with the mouse: lines, polygon sides
and shape outlines all cut the sketch into faces, picked by area or by
contour, then made into a Regions node or extruded.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

import pytest
from PyQt5.QtCore import QEvent, QPoint, QPointF, Qt
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from khervecad import sketch_constraints as sc
from khervecad import sketch_constrain_ui as ui
from khervecad import sketch_regions as R
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
    v.resize(700, 600)
    v.show()
    v.centerOn(20, 15)
    v.resetTransform()
    v.scale(6, 6)
    v.centerOn(20, 15)
    yield v
    v.close()


def _at(view, x, y):
    return view.mapFromScene(QPointF(x, y))


def _click(view, x, y, button=Qt.LeftButton):
    QTest.mouseClick(view.viewport(), button, Qt.NoModifier, _at(view, x, y))


def _drag(view, a, b, steps=4):
    vp = view.viewport()
    s, e = _at(view, *a), _at(view, *b)
    QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, s)
    for i in range(1, steps + 1):
        p = QPoint(s.x() + (e.x() - s.x()) * i // steps,
                   s.y() + (e.y() - s.y()) * i // steps)
        QApplication.sendEvent(vp, QMouseEvent(
            QEvent.MouseMove, QPointF(p), Qt.NoButton, Qt.LeftButton,
            Qt.NoModifier))
    QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, e)


def _key(view, key):
    QTest.keyClick(view.viewport(), key)


def _rect(view, a, b):
    view.set_tool("rect")
    _drag(view, a, b)


def _circle(view, centre, rim):
    view.set_tool("circle")
    _drag(view, centre, rim)


def _lines(view, *points):
    """A chain of lines clicked point to point, ended with Esc."""
    view.set_tool("line")
    for p in points:
        _click(view, *p)
    _key(view, Qt.Key_Escape)


def _polygon(view, *points):
    view.set_tool("polygon")
    for p in points:
        _click(view, *p)
    _click(view, *points[0])              # back on the first: closes


def _faces(view):
    return R.faces(R.shapes_of(view.scene().model.root))


def _nodes(view, kind):
    return [n for n in view.scene().model.root.walk() if n.type == kind]


def _pick(view, tool, *points):
    """The regions tool: click each point, Enter to finish."""
    view.set_tool(tool)
    for p in points:
        _click(view, *p)
    return R._state(view.scene())["picked"]


def _area(node):
    return R._cross_section([p for p in [node.params["points"]]]).area() \
        if "paths" not in node.params else None


def _made(view):
    regions = _nodes(view, "regions")
    assert regions, "no Regions node was made"
    return regions[-1]


def _region_area(view, node):
    import manifold3d  # noqa: F401  (the tests need Manifold)
    from khervecad.mesh import collect_outlines
    outs = collect_outlines(node)
    return R._cross_section(outs).area()


# ------------------------------------------------------------- drawing
def test_a_line_drawn_across_a_rectangle_cuts_it_in_two(view):
    _rect(view, (0, 0), (30, 20))
    _lines(view, (10, -5), (10, 25))
    got = _faces(view)
    assert len(got) == 2
    assert R.face_at(got, (5, 10)) != R.face_at(got, (20, 10))
    areas = sorted(f[0].area() for f in got)
    assert areas == pytest.approx([200, 400], rel=1e-6)


def test_lines_alone_close_a_triangle(view):
    _lines(view, (0, 0), (30, 0), (15, 20), (0, 0))
    got = _faces(view)
    assert len(got) == 1
    assert got[0][0].area() == pytest.approx(300, rel=1e-6)


def test_a_dangling_line_end_cuts_nothing(view):
    _rect(view, (0, 0), (30, 20))
    _lines(view, (10, -5), (10, 10))       # stops half way in
    got = _faces(view)
    assert len(got) == 1
    assert got[0][0].area() == pytest.approx(600, rel=1e-6)


def test_a_polygon_and_a_circle_split_into_three(view):
    _polygon(view, (0, 0), (30, 0), (30, 20), (0, 20))
    _circle(view, (30, 10), (38, 10))
    got = _faces(view)
    assert len(got) == 3
    inside_both = R.face_at(got, (27, 10))
    assert sorted(got[inside_both][2]) == [0, 1]


def test_a_line_crosses_a_polygon_like_any_other_edge(view):
    _polygon(view, (0, 0), (30, 0), (15, 25))
    _lines(view, (-5, 8), (35, 8))
    got = _faces(view)
    assert len(got) == 2
    total = sum(f[0].area() for f in got)
    assert total == pytest.approx(375, rel=1e-6)


def test_a_circle_inside_a_rectangle_is_an_island(view):
    _rect(view, (0, 0), (40, 30))
    _circle(view, (20, 15), (25, 15))
    got = _faces(view)
    assert len(got) == 2
    ring = got[R.face_at(got, (2, 2))][0].area()
    assert ring == pytest.approx(1200 - math.pi * 25, rel=1e-2)


def _rim(c, r, deg, k=1.0):
    a = math.radians(deg)
    return (c[0] + k * r * math.cos(a), c[1] + k * r * math.sin(a))


BIG, SMALL = ((0, 0), 10), ((30, 20), 6)


def test_a_line_ending_just_off_a_circle_rests_on_it(view):
    _circle(view, BIG[0], _rim(*BIG, 0))
    _circle(view, SMALL[0], _rim(*SMALL, 0))
    # each end 0.2 mm inside its rim: still closes the band
    _lines(view, _rim(*BIG, 125, 0.98), _rim(*SMALL, 125, 0.97))
    _lines(view, _rim(*BIG, -55, 0.98), _rim(*SMALL, -55, 0.97))
    got = _faces(view)
    assert R.face_at(got, (15, 10)) is not None       # the band
    assert len(got) == 3


def test_two_lines_crossing_make_no_region_on_their_own(view):
    _lines(view, (0, 0), (20, 20))
    _lines(view, (0, 20), (20, 0))
    assert _faces(view) == []


def test_a_star_of_lines_through_a_circle_cuts_it_into_slices(view):
    _circle(view, (0, 0), (10, 0))
    for deg in (0, 60, 120):
        a = math.radians(deg)
        _lines(view, (-15 * math.cos(a), -15 * math.sin(a)),
               (15 * math.cos(a), 15 * math.sin(a)))
    got = _faces(view)
    assert len(got) == 6
    areas = [f[0].area() for f in got]
    assert max(areas) == pytest.approx(min(areas), rel=0.05)


# ---------------------------------------------------------- picking
def test_click_inside_picks_the_area(view):
    _rect(view, (0, 0), (30, 20))
    _lines(view, (10, -5), (10, 25))
    picked = _pick(view, R.MAKE, (5, 10))
    assert len(picked) == 1
    _click(view, 5, 10)                       # again: off
    assert not R._state(view.scene())["picked"]


def test_click_on_a_circle_outline_picks_everything_inside(view):
    _rect(view, (0, 0), (30, 20))
    _circle(view, (30, 10), (38, 10))
    got = _faces(view)
    picked = _pick(view, R.MAKE, (38, 10))     # ON the circle's rim
    want = {i for i, f in enumerate(got) if 1 in f[2]}
    assert picked == want and len(want) == 2
    _click(view, 38, 10)                       # the rim again: all off
    assert not R._state(view.scene())["picked"]


def test_click_on_a_line_picks_the_face_beside_it(view):
    _rect(view, (0, 0), (30, 20))
    _lines(view, (10, 0), (10, 20))
    got = _faces(view)
    picked = _pick(view, R.MAKE, (10, 10))     # ON the dividing line
    assert picked == {R.face_at(got, (5, 10))}  # the smaller side


def test_create_region_by_mouse_groups_without_extruding(view):
    _rect(view, (0, 0), (30, 20))
    _circle(view, (30, 10), (38, 10))
    _pick(view, R.MAKE, (15, 10), (27, 10), (36, 10))
    _key(view, Qt.Key_Return)
    node = _made(view)
    assert not _nodes(view, "linear_extrude")
    assert _region_area(view, node) == pytest.approx(
        600 + math.pi * 64 / 2, rel=2e-2)


def test_extrude_regions_by_mouse(view):
    _rect(view, (0, 0), (30, 20))
    _lines(view, (10, -5), (10, 25))
    _pick(view, R.REGIONS, (20, 10))
    _click(view, 20, 10, Qt.RightButton)        # right click finishes
    ext = _nodes(view, "linear_extrude")
    assert ext
    assert _region_area(view, _made(view)) == pytest.approx(400, rel=1e-4)


def test_lever_of_two_holed_circles_and_lines_is_one_outline(view):
    for (c, r) in (BIG, SMALL, (BIG[0], 4), (SMALL[0], 2.5)):
        _circle(view, c, _rim(c, r, 0))
    _lines(view, _rim(*BIG, 125), _rim(*SMALL, 125))
    _lines(view, _rim(*BIG, -55), _rim(*SMALL, -55))
    got = _faces(view)
    for c, r in (BIG, SMALL):                 # each ring is one face
        assert R.face_at(got, _rim(c, r, 90, 0.7)) == \
            R.face_at(got, _rim(c, r, -90, 0.7))
    # every face but the holes, picked by area
    _pick(view, R.MAKE, _rim(*BIG, 200, 0.7), (15, 10),
          _rim(*SMALL, 20, 0.7))
    _key(view, Qt.Key_Return)
    from khervecad.mesh import collect_outlines
    loops = collect_outlines(_made(view))
    assert len(loops) == 3                    # outline + two holes


# ------------------------------------------------------- constraints
def test_lines_made_coincident_by_clicks_still_close_a_region(view):
    m = view.scene().model
    _lines(view, (0, 0), (30, 0))
    _lines(view, (30.8, 0.4), (15, 20))       # a little off the end
    _lines(view, (15, 20), (0, 0))
    view.set_tool(ui.tool_of("coincident"))
    _click(view, 30, 0)
    _click(view, 30.8, 0.4)
    assert any(r["kind"] == "coincident" for r in sc.rows(m.root))
    got = _faces(view)
    assert len(got) == 1
    assert got[0][0].area() == pytest.approx(300, rel=1e-3)


def test_a_region_follows_a_constrained_dimension(view, monkeypatch):
    m = view.scene().model
    _rect(view, (0, 0), (30, 20))
    _lines(view, (10, -5), (10, 25))
    _pick(view, R.MAKE, (20, 10))
    _key(view, Qt.Key_Return)
    node = _made(view)
    assert _region_area(view, node) == pytest.approx(400, rel=1e-4)
    rect = next(n for n in node.walk() if n.type == "rect")
    m.set_param(rect, "width", 40)
    R.refresh(m)
    QApplication.processEvents()
    assert _region_area(view, node) == pytest.approx(600, rel=1e-4)


def test_horizontal_constraint_by_click_then_region(view):
    m = view.scene().model
    _lines(view, (0, 0), (30, 1.5))           # not quite level
    _lines(view, (30, 1.5), (30, 20), (0, 20), (0, 0))
    view.set_tool(ui.tool_of("horizontal"))
    _click(view, 15, 0.75)
    first = next(n for n in _nodes(view, "line")
                 if n.params["x1"] == 0 and n.params["y1"] == 0
                 and n.params["x2"] > 20)
    assert first.params["y2"] == pytest.approx(first.params["y1"], abs=1e-4)
    got = _faces(view)
    assert len(got) == 1


def test_many_shapes_stay_fast(view):
    import time
    m = view.scene().model
    for i in range(12):
        m.add_node("circle", dict(x=i * 8, y=0, radius=5))
    m.add_node("line", dict(x1=-10, y1=0, x2=100, y2=0))
    t = time.perf_counter()
    got = _faces(view)
    assert time.perf_counter() - t < 3
    assert len(got) > 12


# ------------------------------------------------- editing by mouse
def _select(view, x, y):
    view.set_tool("select")
    _click(view, x, y)
    QApplication.processEvents()


def test_drag_a_circle_by_its_centre_and_the_faces_follow(view):
    m = view.scene().model
    _rect(view, (0, 0), (30, 20))
    _circle(view, (30, 10), (36, 10))
    assert len(_faces(view)) == 3
    circle = _nodes(view, "circle")[0]
    _select(view, 36, 10)                       # its rim selects it
    assert circle in view.scene().selected_nodes()
    _drag(view, (30, 10), (50, 10))             # by the centre handle
    QApplication.processEvents()
    assert circle.params["x"] == pytest.approx(50, abs=0.3)
    assert circle.params["radius"] == pytest.approx(6, abs=1e-6)
    assert len(_faces(view)) == 2               # apart now
    del m


def test_drag_a_line_end_and_the_region_follows(view):
    m = view.scene().model
    _rect(view, (0, 0), (30, 20))
    _lines(view, (10, -5), (10, 25))
    _pick(view, R.MAKE, (20, 10))
    _key(view, Qt.Key_Return)
    node = _made(view)
    line = next(n for n in node.walk() if n.type == "line")
    # the line slants: its lower end moves to x = 20
    line.params["x1"] = 20.0
    m.node_changed.emit(line)
    R.refresh(m)
    QApplication.processEvents()
    assert _region_area(view, node) == pytest.approx(300, rel=1e-3)


def test_a_typed_length_reshapes_the_triangle_region(view):
    m = view.scene().model
    _lines(view, (0, 0), (30, 0), (15, 20), (0, 0))
    view.scene().ask_value = lambda kind, measured: "40"
    view.set_tool(ui.tool_of("length"))
    _click(view, 15, 0)                         # the base line
    base = next(n for n in _nodes(view, "line")
                if n.params["y1"] == pytest.approx(0)
                and n.params["y2"] == pytest.approx(0))
    assert abs(base.params["x2"] - base.params["x1"]) == pytest.approx(
        40, abs=1e-3)
    got = _faces(view)
    assert len(got) == 1                        # still closed
    del m


def test_click_on_a_polygon_side_picks_the_polygon(view):
    _polygon(view, (0, 0), (30, 0), (30, 20), (0, 20))
    _lines(view, (15, -5), (15, 25))
    got = _faces(view)
    picked = _pick(view, R.MAKE, (30, 10))      # ON the polygon's side
    assert picked == set(range(len(got))) and len(got) == 2
    _key(view, Qt.Key_Return)
    assert _region_area(view, _made(view)) == pytest.approx(600, rel=1e-4)


def test_escape_drops_the_picks_and_undo_takes_a_region_back(view):
    m = view.scene().model
    m.UNDO_MERGE_S = -1.0                       # one step per edit
    _rect(view, (0, 0), (30, 20))
    _lines(view, (10, -5), (10, 25))
    _pick(view, R.MAKE, (5, 10))
    _key(view, Qt.Key_Escape)
    assert not R._state(view.scene())["picked"]
    assert not _nodes(view, "regions")
    _pick(view, R.MAKE, (5, 10))
    QApplication.processEvents()
    _key(view, Qt.Key_Return)
    assert _nodes(view, "regions")
    QApplication.processEvents()
    m.undo_stack.undo()
    QApplication.processEvents()
    assert not _nodes(view, "regions")
    assert len(_nodes(view, "rect")) == 1


def test_lines_and_shapes_mixed_freely(view):
    """A rectangle, a circle on its corner, a polygon over its other
    corner and a line across them all: every face found, every one
    pickable, the union one region."""
    _rect(view, (0, 0), (40, 20))
    _circle(view, (0, 0), (8, 0))
    _polygon(view, (35, 15), (50, 15), (50, 30), (35, 30))
    _lines(view, (-10, 10), (55, 10))
    got = _faces(view)
    # rect above / below the line, circle in / out of it, polygon in /
    # out of it
    assert len(got) == 6
    for cs, _loops, _in in got:                 # each one clickable
        pt = R.seed(cs)
        assert R.face_at(got, tuple(pt)) is not None
    view.set_tool(R.MAKE)
    for cs, _loops, _in in got:
        _click(view, *R.seed(cs))
    assert len(R._state(view.scene())["picked"]) == len(got)
    _key(view, Qt.Key_Return)
    total = _region_area(view, _made(view))
    assert total == pytest.approx(800 + math.pi * 64 * 0.75 + 225 - 25,
                                  rel=2e-2)


def test_the_line_stops_when_it_closes_on_its_first_point(view):
    m = view.scene().model
    view.set_tool("line")
    for p in ((0, 0), (30, 0), (15, 20), (0, 0)):
        _click(view, *p)
    from khervecad import sketch_line
    assert sketch_line._state(view.scene())["start"] is None   # stopped
    _click(view, 40, 40)                     # a fresh line starts here
    _key(view, Qt.Key_Escape)
    assert len(_nodes(view, "line")) == 3
    rows = [r for r in sc.rows(m.root) if r["kind"] == "coincident"]
    assert len(rows) == 3                    # every corner joined once
    assert len(_faces(view)) == 1

"""Open arcs, slots, the line tool's arc and Delete, by mouse (2026-10-29,
the user: arcs "incomplete" with just their 3 points, the line turning
into an arc when going back to its last point, the slot drawn as a line,
and Delete zooming onto what is gone).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest

from khervecad import mesh, sketch_arc
from test_clevis_by_mouse import (_click_areas, _frame, _ids, _shot, _sketch,
                                  _sketch_of, _snap, _volume, _window_ok)
from test_lever_by_mouse import _at, _extruded_boss, _move, win  # noqa


def _clicks(win, tool, *points):
    v2 = win.view2d
    v2.set_tool(tool)
    for pt in points:
        p = _at(win, *pt)
        _move(v2.viewport(), p)
        QTest.mouseClick(v2.viewport(), Qt.LeftButton, Qt.NoModifier, p)
        QTest.qWait(20)


def _lines_of(win, before):
    return [n for n in win.model.root.walk()
            if n.id not in before and n.type == "line"]


def test_three_point_and_centre_arcs_are_open_with_three_handles(win):
    before = _ids(win)
    _sketch(win, "Front (XZ)")
    _snap(win)
    _frame(win, -40, -40, 80, 80)
    _clicks(win, "arc_3pt", (20, 0), (-20, 0), (0, 20))
    arc = _lines_of(win, before)[-1]
    assert sketch_arc.is_arc(arc)
    assert sketch_arc.middle(20, 0, -20, 0, sketch_arc.bulge_of(
        arc.params)) == pytest.approx((0, 20), abs=1e-3)
    item = win.view2d.scene()._items[arc.id]
    roles = [r for r, _p in item.handle_spec()]
    assert roles == ["p1", "p2", "mid"]                # three, not 32
    # no area: an open arc is an edge, like a line
    assert mesh.collect_outlines(arc)          # drawn as a thin stroke
    before = _ids(win)
    _clicks(win, "arc_center", (0, -20), (10, -20), (0, -10))
    quarter = _lines_of(win, before)[-1]
    g = sketch_arc.geometry(10, -20, 0, -10, sketch_arc.bulge_of(
        quarter.params))
    assert math.degrees(g[4]) == pytest.approx(90, abs=0.01)
    assert (g[0], g[1], g[2]) == pytest.approx((0, -20, 10), abs=1e-3)
    _shot(win, "a1-open-arcs")


def test_dragging_the_middle_handle_bends_the_arc(win):
    before = _ids(win)
    _sketch(win, "Front (XZ)")
    _snap(win)
    _frame(win, -40, -40, 80, 80)
    _clicks(win, "arc_3pt", (20, 0), (-20, 0), (0, 10))
    arc = _lines_of(win, before)[-1]
    item = win.view2d.scene()._items[arc.id]
    from PyQt5.QtCore import QPointF
    item.handle_dragged("mid", QPointF(0, 20))
    assert sketch_arc.middle(20, 0, -20, 0, sketch_arc.bulge_of(
        arc.params)) == pytest.approx((0, 20), abs=1e-3)


def test_a_line_and_an_arc_close_an_area_to_extrude(win):
    """A D: a straight line and a 3-point arc on its ends — Extruded Boss
    picks the area they close."""
    before = _ids(win)
    _sketch(win, "Top (XY)")
    _snap(win)
    _frame(win, -40, -40, 80, 80)
    _clicks(win, "line", (-20, 0), (20, 0))
    QTest.keyClick(win.view2d.viewport(), Qt.Key_Escape)
    _clicks(win, "arc_3pt", (20, 0), (-20, 0), (0, 20))
    sk = _sketch_of(win, before)
    _shot(win, "a2-d-sketch")
    _extruded_boss(win)
    if win.view3d._pick_cb is not None:
        _click_areas(win, sk, [(0, 8)])
    _window_ok(win, distance=10)
    _shot(win, "a3-d-extruded")
    v = _volume(win)
    assert v["volume"] == pytest.approx(math.pi * 400 / 2 * 10, rel=0.01)


def test_back_on_the_last_point_the_line_turns_into_a_tangent_arc(win):
    before = _ids(win)
    _sketch(win, "Top (XY)")
    _snap(win)
    _frame(win, -10, -30, 60, 60)
    v2 = win.view2d
    v2.set_tool("line")
    for pt in ((0, 0), (20, 0)):
        p = _at(win, *pt)
        _move(v2.viewport(), p)
        QTest.mouseClick(v2.viewport(), Qt.LeftButton, Qt.NoModifier, p)
    # just leaving the point is a LINE: no arc
    for pt in ((20.2, 0), (21, 3), (24, 8)):
        _move(v2.viewport(), _at(win, *pt))
        QTest.qWait(10)
    assert not win.view2d.scene()._ln.get("arc")
    # drawn out first, back onto (20, 0), away again: the arc
    for pt in ((35, 10), (20.2, 0), (21, 3), (24, 8), (20, 20)):
        _move(v2.viewport(), _at(win, *pt))
        QTest.qWait(10)
    p = _at(win, 20, 20)
    QTest.mouseClick(v2.viewport(), Qt.LeftButton, Qt.NoModifier, p)
    _shot(win, "a4-line-then-arc")
    # and straight again after it
    for pt in ((0, 20),):
        p = _at(win, *pt)
        _move(v2.viewport(), p)
        QTest.mouseClick(v2.viewport(), Qt.LeftButton, Qt.NoModifier, p)
    QTest.keyClick(v2.viewport(), Qt.Key_Escape)
    made = _lines_of(win, before)
    assert len(made) == 3, [n.params for n in made]
    first, arc, last = made
    assert not sketch_arc.is_arc(first) and not sketch_arc.is_arc(last)
    assert sketch_arc.is_arc(arc)
    # tangent to the first line at (20, 0): a half turn to (20, 20)
    g = sketch_arc.geometry(20, 0, 20, 20, sketch_arc.bulge_of(arc.params))
    assert math.degrees(g[4]) == pytest.approx(180, abs=0.5)
    assert (g[0], g[1]) == pytest.approx((20, 10), abs=0.05)


def test_a_slot_is_drawn_as_a_slot(win):
    before = _ids(win)
    _sketch(win, "Top (XY)")
    _snap(win)
    _frame(win, -40, -40, 80, 80)
    _clicks(win, "slot", (-15, 0), (15, 0), (0, 5))
    slot = _lines_of(win, before)[-1]
    item = win.view2d.scene()._items[slot.id]
    box = item.mapRectToScene(item.boundingRect())
    assert box.height() >= 10 - 0.1              # its width, not a hair
    assert box.width() >= 40 - 0.1
    _shot(win, "a5-slot")


def test_open_spline_and_conic_are_curves_not_shapes(win):
    before = _ids(win)
    _sketch(win, "Top (XY)")
    _snap(win)
    _frame(win, -10, -20, 60, 60)
    _clicks(win, "spline", (0, 0), (10, 10), (20, 0), (30, 10))
    QTest.keyClick(win.view2d.viewport(), Qt.Key_Return)
    QTest.qWait(30)
    made = _lines_of(win, before)
    assert made and all(n.type == "line" for n in made)
    ends = {(n.params["x1"], n.params["y1"]) for n in made} | \
        {(n.params["x2"], n.params["y2"]) for n in made}
    assert (0, 0) in ends and (30, 10) in ends       # open: two ends
    assert not any(n.type == "polygon" for n in win.model.root.walk()
                   if n.id not in before)
    _shot(win, "a6-spline")


def test_deleting_keeps_the_view(win):
    """Select a shape (the view frames it), Delete: the view goes back to
    where it was, never onto the neighbour the tree selects next."""
    _sketch(win, "Top (XY)")
    _snap(win)
    _frame(win, -100, -100, 200, 200)
    v2 = win.view2d
    v2.set_tool("rect")
    from test_lever_by_mouse import _drag
    _drag(v2.viewport(), _at(win, -60, -60), _at(win, -50, -50))
    _drag(v2.viewport(), _at(win, 50, 50), _at(win, 60, 60))
    v2.set_tool("select")
    QTest.qWait(50)

    def view():
        c = v2.mapToScene(v2.viewport().rect().center())
        return (round(v2.transform().m11(), 3), round(c.x(), 1),
                round(c.y(), 1))
    start = view()
    rects = [n for n in win.model.root.walk() if n.type == "rect"]
    tree = win.builder.active_tree()
    tree.select_nodes([rects[0]])
    QTest.qWait(50)
    assert view() != start                     # the pick framed it
    tree.setFocus()
    QTest.keyClick(tree, Qt.Key_Delete)
    QTest.qWait(100)
    assert rects[0].parent is None
    assert view() == start

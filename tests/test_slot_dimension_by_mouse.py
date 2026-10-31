"""Smart Dimension from a slot to a part's edge, and the slot's centre
line (2026-10-29, the user: "I am unable to get a smart dimension from
the slot to the bottom of the rectangle ... for a slot I should see the
centre lines").

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest

from test_clevis_by_mouse import _frame, _ids, _rect, _shot, _sketch, _snap
from test_lever_by_mouse import _extruded_boss, win  # noqa
from test_open_arcs_by_mouse import _clicks, _lines_of
from test_clevis_by_mouse import _window_ok
from test_smart_dimension_by_mouse import _dimension


def _base_and_slot(win):
    _sketch(win, "Top (XY)")
    _snap(win)
    _frame(win, -10, -10, 120, 90)
    _rect(win, (0, 0), (100, 60))
    _extruded_boss(win)
    _window_ok(win, distance=10)
    before = _ids(win)
    _sketch(win, "Top (XY)")
    _snap(win)
    _frame(win, -10, -10, 120, 90)
    _clicks(win, "slot", (60, 30), (80, 30), (70, 35))
    return _lines_of(win, before)[-1]


def test_slot_centre_to_the_parts_bottom_edge(win):
    slot = _base_and_slot(win)
    # the slot's left end centre, then the part's bottom edge
    asked = _dimension(win, (60, 30), (30, 0), value=25)
    assert asked, win.statusBar().currentMessage()
    assert slot.params["y1"] == pytest.approx(25, abs=0.01)
    assert slot.params["y2"] == pytest.approx(25, abs=0.01)   # level
    _shot(win, "slot-to-edge")


def test_slot_centre_line_to_the_parts_bottom_edge(win):
    slot = _base_and_slot(win)
    # the slot's centre LINE (between the end centres), then the edge
    asked = _dimension(win, (70, 30), (30, 0), value=20)
    assert asked, win.statusBar().currentMessage()
    assert (slot.params["y1"], slot.params["y2"]) == \
        (pytest.approx(20, abs=0.01), pytest.approx(20, abs=0.01))


def test_a_click_on_the_slots_outline_takes_its_centre_line(win):
    slot = _base_and_slot(win)
    r = slot.params["width"] / 2
    asked = _dimension(win, (70, 30 - r), (30, 0), value=15)
    assert asked, win.statusBar().currentMessage()
    assert slot.params["y1"] == pytest.approx(15, abs=0.01)


def test_a_slot_drawn_on_a_rectangles_side_stays_on_it(win):
    """2026-10-31, the user: a slot's end drawn on the rectangle's side
    should be related to it (SolidWorks' On Edge), so a dimension keeps
    it there."""
    _sketch(win, "Top (XY)")
    _snap(win)
    _frame(win, -10, -10, 130, 90)
    _rect(win, (0, 0), (100, 60))
    before = _ids(win)
    _clicks(win, "slot", (60, 30), (100, 30), (80, 35))
    slot = _lines_of(win, before)[-1]
    rows = slot.parent.params.get("constraints") or []
    on = [r for r in rows if r["kind"] == "point_on"]
    assert on, rows
    # widen the rectangle: the slot's end goes with its side
    asked = _dimension(win, (50, 0), (50, -6), value=120)
    assert asked, win.statusBar().currentMessage()
    rect = [n for n in slot.parent.children if n.type == "rect"][0]
    assert slot.params["x2"] == pytest.approx(rect.params["x"] + rect.params["width"], abs=0.01)
    assert slot.params["y1"] == pytest.approx(slot.params["y2"], abs=0.01)
    _shot(win, "slot-on-edge")


def test_a_click_on_a_slots_round_end_gives_its_radius(win):
    """2026-10-31, the user could not pick the slot's radius."""
    slot = _base_and_slot(win)
    r = slot.params["width"] / 2
    asked = _dimension(win, (80 + r, 30), (80 + r, 30), value=4)
    assert asked, win.statusBar().currentMessage()
    assert slot.params["width"] == pytest.approx(8, abs=0.01)
    rows = slot.parent.params.get("constraints") or []
    assert any(r["kind"] == "radius" for r in rows), rows


def test_a_dimension_behind_the_part_is_not_drawn_through_it(win):
    """2026-10-31, the user: dimensions showed through the solid. The
    slot's sketch lies on the plate's BOTTOM face (z = 0): seen from
    below its dimension shows, from above the plate hides it."""
    from PyQt5.QtTest import QTest
    slot = _base_and_slot(win)
    assert _dimension(win, (60, 30), (30, 0), value=25)
    cont = slot.parent
    i = next(i for i, r in enumerate(cont.params["constraints"])
             if "value" in r)
    from khervecad import sketch_mode
    sketch_mode.finish(win)
    QTest.qWait(300)
    v3 = win.view3d

    def drawn(view):
        v3.set_view(view, animate=False)
        v3.repaint()
        QTest.qWait(50)
        return any(h[1] is cont and h[2] == i for h in win._dims3d_hits)

    assert drawn("Bottom")
    assert not drawn("Top")


def test_hovering_a_slots_end_lights_that_arc_then_gives_its_radius(win):
    """2026-10-31, the user: hover the arc, it lights up, click it, then
    the radius — as for any arc."""
    from PyQt5.QtTest import QTest
    from test_smart_dimension_by_mouse import _at, _move
    slot = _base_and_slot(win)
    r = slot.params["width"] / 2
    v2 = win.view2d
    v2.set_tool("con_dimension")
    _move(v2.viewport(), _at(win, 80 + r * 0.7071, 30 + r * 0.7071))
    QTest.qWait(30)
    hot = v2.scene()._con_hover
    assert hot is not None and hot[0] is slot and hot[1] == "a2", hot
    v2.viewport().repaint()
    _shot(win, "slot-arc-hover")
    # inside the slot, near its end: not the end's arc
    _move(v2.viewport(), _at(win, 80 - r * 0.9, 30 + r * 0.43))
    QTest.qWait(30)
    hot = v2.scene()._con_hover
    assert hot is None or hot[1] != "a2", hot
    v2.set_tool("select")
    asked = _dimension(win, (80 + r * 0.7071, 30 + r * 0.7071), (95, 55),
                       value=3)
    assert asked and asked[0][0] == "radius", asked
    assert slot.params["width"] == pytest.approx(6, abs=0.01)

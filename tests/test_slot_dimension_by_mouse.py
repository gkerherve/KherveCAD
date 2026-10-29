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

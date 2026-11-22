"""Several Smart Dimensions in one tool session after a trim
(2026-11-22, Exercise 170: the lug's arc R20 centred 37 from the origin).

The second dimension of a session took the value typed for the first and
deformed the arc: a click on the arc's CENTRE and then on its rim made no
dimension at all (the values queue then ran one behind), and a trimmed
arc's ends were tied to nothing, so any later dimension pulled them off
the lines they were trimmed by.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest

from khervecad import sketch_modify
from test_clevis_by_mouse import _circle, _frame, _lines, _sketch
from test_lever_by_mouse import win  # noqa: F401
from test_open_arcs_by_mouse import _lines_of
from test_smart_dimension_by_mouse import _at, _move


def _lug(win):
    """The exercise's lug: lines z = 80 / 40 to x = 15 and the R20 circle
    at (-37, 60), trimmed to the arc on the left."""
    from test_clevis_by_mouse import _ids
    before = _ids(win)
    _sketch(win, "Front (XZ)")
    sc = win.view2d.scene()
    sc.snap_enabled = True
    sc.grid_size = 1.0
    _frame(win, -80, 20, 110, 80)
    v2 = win.view2d
    _lines(v2, [(-37, 80), (15, 80), (15, 40), (-37, 40)])
    _circle(win, (-37, 60), 20)
    v2.set_tool(sketch_modify.TRIM)
    p = _at(win, -17, 60)
    _move(v2.viewport(), p)
    QTest.mouseClick(v2.viewport(), Qt.LeftButton, Qt.NoModifier, p)
    QTest.keyClick(v2.viewport(), Qt.Key_Escape)
    QTest.qWait(30)
    arc = next(n for n in win.model.root.walk()
               if n.type == "line" and n.params.get("bulge"))
    new = [n for n in _lines_of(win, before) if n is not arc]
    return arc, new


def _session(win, steps):
    """ONE Smart Dimension tool session: each step is (value, clicks...),
    the typed values are handed out in order, one per dimension asked."""
    v2 = win.view2d
    scene = v2.scene()
    values = [str(s[0]) for s in steps]
    asked = []

    def ask(kind, measured):
        asked.append((kind, measured))
        return values.pop(0) if values else None
    scene.ask_value = ask
    v2.set_tool("con_dimension")
    for _value, *clicks in steps:
        for pt in clicks:
            p = _at(win, *pt)
            _move(v2.viewport(), p)
            QTest.mouseClick(v2.viewport(), Qt.LeftButton, Qt.NoModifier, p)
            QTest.qWait(30)
    v2.set_tool("select")
    return asked


def _rows(arc, kind):
    return [r for r in arc.parent.params.get("constraints") or []
            if r["kind"] == kind]


def test_radius_then_distance_in_one_session(win):
    arc, _lines_ = _lug(win)
    asked = _session(win, [(20, (-57, 60), (-45, 90)),
                           (37, (0, 0), (-37, 60), (-18, -8))])
    assert [k for k, _m in asked] == ["radius", "hdistance"], asked
    assert arc.params["bulge"] == pytest.approx(1.0, abs=1e-3)
    assert (arc.params["x1"], arc.params["y1"]) == \
        (pytest.approx(-37, abs=1e-3), pytest.approx(80, abs=1e-3))
    assert (arc.params["x2"], arc.params["y2"]) == \
        (pytest.approx(-37, abs=1e-3), pytest.approx(40, abs=1e-3))


def test_the_centre_then_the_rim_is_its_radius(win):
    """The way the exercise was clicked: the arc's centre, its rim, then
    the place of the number. It made nothing, and the typed 20 went to
    the distance that followed."""
    arc, _lines_ = _lug(win)
    asked = _session(win, [(20, (-37, 60), (-57, 60)),
                           (37, (0, 0), (-37, 60), (-18, -8))])
    assert [k for k, _m in asked] == ["radius", "hdistance"], asked
    assert _rows(arc, "radius")[0]["value"] == 20
    assert _rows(arc, "hdistance")[0]["value"] == 37
    assert arc.params["bulge"] == pytest.approx(1.0, abs=1e-3)
    assert arc.params["y1"] == pytest.approx(80, abs=1e-3)


def test_a_new_radius_keeps_the_arc_on_its_lines(win):
    """The trim leaves the arc's ends where the lines end: a radius of
    22 must not pull them off."""
    arc, lines = _lug(win)
    _session(win, [(22, (-57, 60), (-45, 90)),
                   (40, (0, 0), (-37, 60), (-18, -8))])
    top = next(n for n in lines if n.name == "Line 1")
    bottom = next(n for n in lines if n.name == "Line 3")
    assert (arc.params["x1"], arc.params["y1"]) == (
        pytest.approx(top.params["x1"], abs=1e-3),
        pytest.approx(top.params["y1"], abs=1e-3))
    assert (arc.params["x2"], arc.params["y2"]) == (
        pytest.approx(bottom.params["x2"], abs=1e-3),
        pytest.approx(bottom.params["y2"], abs=1e-3))

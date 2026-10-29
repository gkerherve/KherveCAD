"""Smart Dimension with the mouse (2026-10-29, the user: "make sure that
smart dimension works with line where we can select the middle and going
to an origin, on a circle, and we can change the extrude later on by
changing the smart dimensions").

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest

from khervecad import sketch_constraints as sc
from test_clevis_by_mouse import (_shot, _circle, _click_areas, _frame, _ids,
                                  _lines, _rect, _sketch, _sketch_of, _snap,
                                  _volume, _window_ok)
from test_lever_by_mouse import _at, _extruded_boss, _move, win  # noqa


def _dimension(win, *points, value):
    """Smart Dimension: click each sketch point, type *value*."""
    v2 = win.view2d
    sc_ = v2.scene()
    asked = []
    sc_.ask_value = lambda kind, measured: (asked.append((kind, measured))
                                            or str(value))
    v2.set_tool("con_dimension")
    for pt in points:
        p = _at(win, *pt)
        _move(v2.viewport(), p)
        QTest.mouseClick(v2.viewport(), Qt.LeftButton, Qt.NoModifier, p)
        QTest.qWait(30)
    v2.set_tool("select")
    return asked


def test_line_middle_to_origin_and_circle_then_change_the_extrude(win):
    v2 = win.view2d
    before = _ids(win)
    _sketch(win, "Front (XZ)")
    _snap(win)
    _frame(win, -60, -20, 120, 120)
    _rect(win, (-20, 10), (20, 50))
    _lines(v2, [(-20, 60), (20, 60)])
    _circle(win, (0, 30), 10)
    sk = _sketch_of(win, before)
    # the middle of the line (0, 60) to the origin: 60 -> 70
    asked = _dimension(win, (0, 60), (0, 0), value=70)
    assert asked and asked[0][1] == pytest.approx(60, abs=0.01), asked
    line = next(c for c in sk.children if c.type == "line")
    assert (line.params["y1"] + line.params["y2"]) / 2 == \
        pytest.approx(70, abs=0.01)
    _shot(win, "sd1-line-middle-to-origin")
    # the circle: a click on it, then on empty space -> its diameter
    circle = next(c for c in sk.children if c.type == "circle"
                  and c.params.get("radius") == 10)
    asked = _dimension(win, (10, 30), (45, 80), value=16)
    assert asked and asked[0][0] == "diameter", asked
    assert circle.params["radius"] == pytest.approx(8, abs=0.01)
    _shot(win, "sd2-circle-diameter")
    # the origin first, then the circle: its centre's distance 30 -> 25
    asked = _dimension(win, (0, 0), (8, 30), value=25)
    assert asked and asked[0] == ("distance", pytest.approx(30, abs=0.01))
    assert circle.params["y"] == pytest.approx(25, abs=0.01)
    _shot(win, "sd3-origin-to-circle")
    # the rectangle's top edge middle to the origin: 50 -> 40
    asked = _dimension(win, (0, 50), (0, 0), value="52 - 12")
    assert asked and asked[0][1] == pytest.approx(50, abs=0.01), asked
    # extrude the rectangle with its hole
    _extruded_boss(win)
    _click_areas(win, sk, [(-15, 15)])  # beside the hole
    _window_ok(win, distance=20)
    _shot(win, "sd4-extruded")
    v0 = _volume(win)["volume"]
    rect = next(c for c in win.model.root.walk() if c.type == "rect")
    h = float(rect.params["height"])
    assert v0 == pytest.approx(40 * h * 20 - 3.14159 * 64 * 20, rel=0.02)
    # afterwards: click the Ø value in the 3D view, type 24, Enter —
    # the solid follows
    v3 = win.view3d
    QTest.mouseClick(v3.nav_bar.buttons["fit"], Qt.LeftButton)
    v3.repaint()
    QTest.qWait(100)
    hits = getattr(win, "_dims3d_hits", [])
    cont = circle.parent
    i = next(i for i, r in enumerate(sc.rows(cont))
             if r["kind"] == "diameter")
    rect = next(h[0] for h in hits if h[1] is cont and h[2] == i)
    p = rect.center().toPoint()
    QTest.mousePress(v3, Qt.LeftButton, Qt.NoModifier, p)
    QTest.mouseRelease(v3, Qt.LeftButton, Qt.NoModifier, p)
    QTest.qWait(50)
    box = v3._dim3d_editor
    box.selectAll()
    QTest.keyClicks(box, "30 - 6")      # a calculation: 24
    QTest.keyClick(box, Qt.Key_Return)
    QTest.qWait(300)
    assert circle.params["radius"] == pytest.approx(12, abs=0.01)
    _shot(win, "sd5-diameter-changed-in-3d")
    v1 = _volume(win)["volume"]
    assert v1 == pytest.approx(40 * h * 20 - 3.14159 * 144 * 20, rel=0.02)

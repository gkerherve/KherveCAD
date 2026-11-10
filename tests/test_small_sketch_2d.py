"""Sketch Mode (the 2D sketch) on a part a millimetre across (2026-11-10,
the user: "not able to create sketches on the boss extrude" — a 0.84 x
0.5 mm face).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import QPointF
from PyQt5.QtTest import QTest

from test_lever_by_mouse import _drag, win  # noqa


def _zoomed(win, px_per_mm=120.0):
    v2 = win.view2d
    v2.resize(900, 700)
    k = px_per_mm / abs(v2.transform().m11())
    v2.scale(k, k)
    v2.centerOn(QPointF(0.4, 0.25))
    QTest.qWait(50)
    return v2


def _at(v2, x, y):
    return v2.mapFromScene(QPointF(x, y))


def _made(win, kind):
    return [n for n in win.model.root.walk() if n.type == kind]


def test_a_circle_a_fifth_of_a_millimetre_across_is_kept(win):
    """Anything under 0.5 mm was thrown away as "too small"."""
    v2 = _zoomed(win)
    v2.set_tool("circle")
    _drag(v2.viewport(), _at(v2, 0.4, 0.2), _at(v2, 0.6, 0.2))
    (c,) = _made(win, "circle")
    assert c.params["radius"] == pytest.approx(0.2, abs=0.02)


def test_a_small_rectangle_and_line_are_kept(win):
    v2 = _zoomed(win)
    v2.set_tool("rect")
    _drag(v2.viewport(), _at(v2, 0.1, 0.1), _at(v2, 0.4, 0.3))
    (r,) = _made(win, "rect")
    assert (r.params["width"], r.params["height"]) == pytest.approx(
        (0.3, 0.2), abs=0.02)


def test_the_snap_grid_follows_the_zoom(win):
    v2 = _zoomed(win)
    scene = v2.scene()
    scene.grid_size = 0.5
    scene.snap_enabled = True
    assert scene.snap_step() == pytest.approx(0.1)
    p = scene.snap(QPointF(0.33, 0.21))
    assert (p.x(), p.y()) == pytest.approx((0.3, 0.2))
    # zoomed out, the grid is the grid
    v2.resetTransform()
    v2.scale(4.0, -4.0)
    assert scene.snap_step() == 0.5


def test_a_slip_of_two_pixels_still_makes_nothing(win):
    v2 = _zoomed(win, 20.0)
    v2.set_tool("rect")
    a = _at(v2, 0.0, 0.0)
    from PyQt5.QtCore import QPoint
    _drag(v2.viewport(), a, QPoint(a.x() + 6, a.y() + 1))
    assert not _made(win, "rect")


def test_a_stale_extent_error_is_said_once(win):
    m = win.model
    ext = m.add_node("linear_extrude", dict(height=5.0))
    m.add_node("rect", dict(x=0, y=0, width=4, height=4), parent=ext)
    ext.params["extent"] = "up_to"
    m.add_node("cube", {})                   # said now, the first time
    QTest.qWait(50)
    assert "Up to" in win.statusBar().currentMessage()
    win.statusBar().showMessage("a tool's hint")
    m.add_node("cube", {})                   # ... and not again
    QTest.qWait(50)
    assert win.statusBar().currentMessage() == "a tool's hint"

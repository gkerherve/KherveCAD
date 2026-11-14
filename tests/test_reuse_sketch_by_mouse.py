"""One sketch, two features, by MOUSE (2026-11-14, Exercise 52: the
column extruded from Sketch3, then the bearing ring from the SAME sketch;
the M8 hole cut from a sketch its boss used). Extruded Boss with the
extruded sketch selected → click the second area in 3D → OK; then the
same with Operation ▸ Cut, which must cut the WHOLE part.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

import pytest
from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtTest import QTest

from test_lever_by_mouse import (win, _extruded_boss, _move,  # noqa: F401
                                 _wait)
from test_rib import _volume
from test_feature_mcp import _sketch
from test_clevis_by_mouse import _type


def _click_area(win, sketch, x, y):
    from khervecad import region_panel, sketch_section
    v3 = win.view3d
    assert _wait(lambda: v3._pick_cb is not None), "no area pick"
    QTest.mouseClick(v3.nav_bar.buttons["fit"], Qt.LeftButton)
    QTest.qWait(100)
    o, r, u, _n = sketch_section._frame(sketch)
    world = tuple(o[i] + r[i] * x + u[i] * y for i in range(3))
    q = v3._project(*v3._camera(), world)
    p = QPoint(int(round(q[0])), int(round(q[1])))
    _move(v3, p)
    QTest.mouseClick(v3, Qt.LeftButton, Qt.NoModifier, p)
    QTest.qWait(30)
    QTest.mouseClick(region_panel.ok_button(win), Qt.LeftButton)
    QTest.qWait(100)


def _select(win, node):
    win.builder.active_tree().select_nodes([node])
    QTest.qWait(50)


def _setup(win):
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(win)
    s = _sketch(win)
    m = win.model
    m.add_node("rect", dict(x=-30, y=-30, width=60, height=60), parent=s)
    ex.execute("sketch_feature", {"node_id": s.id, "depth": 10})
    QTest.qWait(50)
    s2 = _sketch(win, z=10)
    m.add_node("circle", dict(x=0, y=0, radius=10), parent=s2)
    m.add_node("circle", dict(x=0, y=0, radius=4), parent=s2)
    out = ex.execute("sketch_feature", {"node_id": s2.id, "depth": 5,
                                        "regions": [[7, 0]]})
    assert "error" not in out, out
    QTest.qWait(50)
    reg = next(n for n in s2.walk() if n.type == "regions")
    return s2, reg


RING = math.pi * (100 - 16) * 5


def test_a_second_area_of_an_extruded_sketch_by_mouse(win):
    s2, reg = _setup(win)
    before = _volume(win)
    assert before == pytest.approx(3600 * 10 + RING, rel=0.02)
    _select(win, reg)
    _extruded_boss(win)
    _click_area(win, s2, 0, 0)                 # the Ø8 in the middle
    from khervecad import extrude_panel
    panel = extrude_panel._panel(win)
    assert panel is not None, "no Extrude window"
    _type(panel.fields["height"], 10)               # Distance: 10
    QTest.mouseClick(panel.ok, Qt.LeftButton)
    QTest.qWait(100)
    grown = _volume(win) - before
    assert grown == pytest.approx(math.pi * 16 * 10, rel=0.05)


def test_a_cut_from_an_extruded_sketch_cuts_the_whole_part(win):
    from khervecad import extrude_panel
    s2, reg = _setup(win)
    before = _volume(win)
    _select(win, reg)
    _extruded_boss(win)
    _click_area(win, s2, 0, 0)
    panel = extrude_panel._panel(win)
    assert panel is not None
    combo = panel.fields["operation"]
    combo.setCurrentIndex(combo.findData("cut"))
    QTest.qWait(100)
    QTest.mouseClick(panel.ok, Qt.LeftButton)
    QTest.qWait(100)
    # Through All down the Ø8: the base's 10 mm (the ring is open there)
    assert before - _volume(win) == pytest.approx(math.pi * 16 * 10,
                                                  rel=0.05)

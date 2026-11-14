"""MCP sketch_feature `regions` — SolidWorks' Selected Contours
(2026-11-14, Exercise 52: a column and its bearing ring drawn in ONE
sketch, extruded 8 then 34 mm by picking areas). Without it the whole
closed area was extruded at once, and the sketch could not be picked
again for the second feature.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

import pytest
from PyQt5.QtTest import QTest

from test_lever_by_mouse import win  # noqa: F401
from test_rib import _volume
from test_feature_mcp import _sketch


def _square_and_ring(win, group):
    """A 40 square of lines with a ring (Ø20 / Ø10) on its top edge."""
    m = win.model
    pts = [(-20, 0), (20, 0), (20, 40), (-20, 40)]
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        m.add_node("line", dict(x1=x1, y1=y1, x2=x2, y2=y2, width=0.2),
                   parent=group)
    m.add_node("circle", dict(x=0, y=40, radius=10), parent=group)
    m.add_node("circle", dict(x=0, y=40, radius=5), parent=group)


SQUARE = 1600 - math.pi * 100 / 2          # the square, less half Ø20
RING = math.pi * (100 - 25)                # the whole ring


def test_regions_extrude_only_the_picked_area(win):
    from khervecad.mcp_tools import McpToolExecutor
    group = _sketch(win)
    _square_and_ring(win, group)
    out = McpToolExecutor(win).execute("sketch_feature", {
        "node_id": group.id, "depth": 5, "regions": [[0, 10]]})
    assert "error" not in out, out
    QTest.qWait(50)
    assert _volume(win) == pytest.approx(SQUARE * 5, rel=0.02)


def test_a_second_feature_picks_the_same_sketch_again(win):
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(win)
    group = _sketch(win)
    _square_and_ring(win, group)
    ex.execute("sketch_feature", {"node_id": group.id, "depth": 5,
                                  "regions": [[0, 10]]})
    QTest.qWait(50)
    out = ex.execute("sketch_feature", {
        "node_id": group.id, "depth": 20, "regions": [[0, 32], [0, 48]]})
    assert "error" not in out, out
    QTest.qWait(50)
    assert _volume(win) == pytest.approx(SQUARE * 5 + RING * 20, rel=0.03)


def test_a_cut_picks_an_area_of_a_sketch_a_boss_used(win):
    """Cut-Extrude2: the Ø8 of the sketch whose Ø17 ring was the boss."""
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(win)
    s = _sketch(win)
    win.model.add_node("rect", dict(x=-20, y=-20, width=40, height=40),
                       parent=s)
    ex.execute("sketch_feature", {"node_id": s.id, "depth": 10})
    QTest.qWait(50)
    s2 = _sketch(win, z=10)
    win.model.add_node("circle", dict(x=0, y=0, radius=8), parent=s2)
    win.model.add_node("circle", dict(x=0, y=0, radius=4), parent=s2)
    ex.execute("sketch_feature", {"node_id": s2.id, "depth": 5,
                                  "regions": [[6, 0]]})
    QTest.qWait(50)
    out = ex.execute("sketch_feature", {
        "node_id": s2.id, "kind": "extruded_cut", "regions": [[0, 0]],
        "through_all": True})
    assert "error" not in out, out
    QTest.qWait(50)
    assert _volume(win) == pytest.approx(
        1600 * 10 + math.pi * (64 - 16) * 5 - math.pi * 16 * 10, rel=0.03)


def test_a_point_on_no_area_is_refused(win):
    from khervecad.mcp_tools import McpToolExecutor
    group = _sketch(win)
    _square_and_ring(win, group)
    out = McpToolExecutor(win).execute("sketch_feature", {
        "node_id": group.id, "regions": [[200, 200]]})
    assert "error" in out
